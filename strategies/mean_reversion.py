"""
Mean Reversion Strategy for TradeMindIQ
========================================
Strategy that profits from price reversions to the mean.
Contrarian approach - buy dips, sell rips.
Safe, standalone strategy - does not modify core logic.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from core.models import Signal, Side
from .base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy that trades:
    - RSI oversold = potential long
    - RSI overbought = potential short
    - Price below VWAP = long
    - Price above VWAP = short
    - Bollinger Band touches = reversal signals
    """
    
    name = "mean_reversion"
    
    def __init__(
        self,
        risk_per_trade: float = 0.10,
        r_multiple: float = 1.5,
        # RSI settings
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        # Bollinger Band settings
        bb_period: int = 20,
        bb_std: float = 2.0,
        # VWAP settings
        vwap_window: int = 390,  # ~6.5 hours of 1m candles
        # Filters
        min_vol_ratio: float = 1.0,  # Must have at least average volume
        session_start_utc: int = 13,  # 1 PM UTC (~8 AM CT)
        session_end_utc: int = 20,    # 8 PM UTC (~3 PM CT)
    ):
        self.base_risk_per_trade = risk_per_trade
        self.r_multiple = r_multiple
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.vwap_window = vwap_window
        self.min_vol_ratio = min_vol_ratio
        self.session_start_utc = session_start_utc
        self.session_end_utc = session_end_utc
    
    def _in_session(self, last_ts_ms: int) -> bool:
        """Check if within trading session."""
        ts = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc)
        hour = ts.hour
        return self.session_start_utc <= hour < self.session_end_utc
    
    def _calculate_rsi(self, closes: List[float], period: int) -> List[float]:
        """Calculate RSI."""
        if len(closes) < period + 1:
            return [50.0] * len(closes)
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(0, d) for d in deltas]
        losses = [-min(0, d) for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            return [100.0] * len(closes)
        
        rs = avg_gain / avg_loss
        rsi = [100 - (100 / (1 + rs))]
        
        for i in range(period, len(closes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return rsi
    
    def _calculate_bollinger_bands(self, closes: List[float], period: int, std: float) -> tuple:
        """Calculate Bollinger Bands (middle, upper, lower)."""
        if len(closes) < period:
            sma = sum(closes) / len(closes) if closes else 0
            return [sma] * len(closes), [sma] * len(closes), [sma] * len(closes)
        
        middles = []
        uppers = []
        lowers = []
        
        for i in range(len(closes)):
            if i < period - 1:
                window = closes[:i+1]
            else:
                window = closes[i-period+1:i+1]
            
            sma = sum(window) / period
            variance = sum((c - sma) ** 2 for c in window) / period
            std_dev = variance ** 0.5
            
            middles.append(sma)
            uppers.append(sma + std_dev * std)
            lowers.append(sma - std_dev * std)
        
        return middles, uppers, lowers
    
    def _calculate_vwap(self, candles: List[List[float]], window: int) -> List[float]:
        """Calculate VWAP."""
        if not candles:
            return []
        
        vwaps = []
        cumulative_tpv = 0
        cumulative_vol = 0
        
        for i, candle in enumerate(candles):
            typical_price = (candle[2] + candle[3] + candle[4]) / 3  # (high + low + close) / 3
            volume = candle[5]
            
            cumulative_tpv += typical_price * volume
            cumulative_vol += volume
            
            if i >= window:
                # Reset window
                window_candles = candles[i-window+1:i+1]
                cumulative_tpv = sum(((c[2] + c[3] + c[4]) / 3) * c[5] for c in window_candles)
                cumulative_vol = sum(c[5] for c in window_candles)
            
            vwap = cumulative_tpv / cumulative_vol if cumulative_vol > 0 else typical_price
            vwaps.append(vwap)
        
        return vwaps
    
    def _calculate_atr(self, candles: List[List[float]], period: int) -> List[float]:
        """Calculate ATR for stop placement."""
        if len(candles) < period:
            return [0.0] * len(candles)
        
        true_ranges = []
        for i, candle in enumerate(candles):
            high, low, close = candle[2], candle[3], candle[4]
            if i == 0:
                tr = high - low
            else:
                prev_close = candles[i-1][4]
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
            true_ranges.append(tr)
        
        atr = [sum(true_ranges[:period]) / period]
        for i in range(period, len(true_ranges)):
            atr.append((atr[-1] * (period - 1) + true_ranges[i]) / period)
        
        # Pad to match candle length
        while len(atr) < len(candles):
            atr.insert(0, atr[0])
        
        return atr
    
    def generate_signal(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        candles: List[List[float]],
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Generate mean reversion signal."""
        if len(candles) < 60:
            return None
        
        last_ts = int(candles[-1][0])
        if not self._in_session(last_ts):
            return None
        
        closes = [c[4] for c in candles]  # close prices
        volumes = [c[5] for c in candles]
        
        # Calculate indicators
        rsi = self._calculate_rsi(closes, self.rsi_period)
        bb_middle, bb_upper, bb_lower = self._calculate_bollinger_bands(
            closes, self.bb_period, self.bb_std
        )
        vwap = self._calculate_vwap(candles, self.vwap_window)
        atr = self._calculate_atr(candles, 14)
        
        close = float(closes[-1])
        rsi_val = rsi[-1]
        bb_upper_val = bb_upper[-1]
        bb_lower_val = bb_lower[-1]
        bb_middle_val = bb_middle[-1]
        vwap_val = vwap[-1] if vwap else close
        atr_val = float(atr[-1]) if atr else close * 0.01
        
        # Volume filter
        avg_vol = sum(volumes[-20:]) / min(20, len(volumes))
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
        
        if vol_ratio < self.min_vol_ratio:
            return None
        
        # Price relative to VWAP
        price_vs_vwap = (close - vwap_val) / vwap_val * 100
        
        # Bollinger Band position
        bb_position = (close - bb_lower_val) / (bb_upper_val - bb_lower_val) if bb_upper_val != bb_lower_val else 0.5
        
        signal = None
        confidence = 0.0
        
        # LONG signals (mean reversion - buy when oversold)
        if rsi_val < self.rsi_oversold and price_vs_vwap < -0.5:
            # Strong oversold signal
            if bb_position < 0.1:  # Near lower band
                confidence = 0.8
                signal = Side.BUY
        
        elif rsi_val < 40 and price_vs_vwap < -1.0:
            # Moderate oversold
            if bb_position < 0.2:
                confidence = 0.6
                signal = Side.BUY
        
        # SHORT signals (mean reversion - sell when overbought)
        elif rsi_val > self.rsi_overbought and price_vs_vwap > 0.5:
            # Strong overbought signal
            if bb_position > 0.9:  # Near upper band
                confidence = 0.8
                signal = Side.SELL
        
        elif rsi_val > 60 and price_vs_vwap > 1.0:
            # Moderate overbought
            if bb_position > 0.8:
                confidence = 0.6
                signal = Side.SELL
        
        if signal is None:
            return None
        
        # Calculate stop and target
        if signal == Side.BUY:
            # Stop below recent low or VWAP
            stop = min(float(min(candles[-5:][3] for c in candles[-5:])), vwap_val * 0.995)
            risk = close - stop
            if risk <= 0:
                return None
            target = close + self.r_multiple * risk
        else:
            # Short: stop above recent high or VWAP
            stop = max(float(max(candles[-5:][2] for c in candles[-5:])), vwap_val * 1.005)
            risk = stop - close
            if risk <= 0:
                return None
            target = close - self.r_multiple * risk
        
        # Position sizing
        equity = context.get("equity", 500.0)
        dollar_risk = equity * self.base_risk_per_trade
        qty = dollar_risk / risk
        
        # Sentiment
        sentiment_score = context.get("sentiment_score", 0.0)
        
        return Signal(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            side=signal,
            entry=close,
            stop=stop,
            target=target,
            qty=qty,
            rsi=rsi_val,
            bb_position=bb_position,
            vwap_distance=price_vs_vwap,
            confidence=confidence,
            sentiment_score=sentiment_score,
        )
