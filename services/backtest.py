"""
TradeMindIQ Backtesting Module
==============================
Test strategies on historical data without executing real trades.
Safe, non-intrusive - only reads data, never trades.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict
import random


@dataclass
class Candle:
    """OHLCV candle data."""
    timestamp: int  # milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def body(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def range(self) -> float:
        return self.high - self.low
    
    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


@dataclass
class BacktestTrade:
    """Trade result from backtest."""
    symbol: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    side: str
    pnl: float
    pnl_pct: float
    exit_reason: str  # TARGET, STOP, TIME, END
    duration_seconds: float


@dataclass
class BacktestConfig:
    """Configuration for backtest."""
    symbols: List[str]
    timeframe: str = "1m"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_equity: float = 500.0
    risk_per_trade: float = 0.10  # 10%
    r_multiple: float = 2.0
    max_hold_seconds: int = 180  # 3 min max
    cooldown_seconds: int = 90
    max_open_positions: int = 2
    daily_loss_cap: float = 25.0


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    config: BacktestConfig
    trades: List[BacktestTrade]
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    equity_curve: List[Tuple[datetime, float]]
    pnl_by_symbol: Dict[str, Dict]
    hourly_stats: Dict[int, Dict]
    daily_stats: Dict[str, Dict]
    
    def to_dict(self) -> Dict:
        return {
            "config": {
                "symbols": self.config.symbols,
                "timeframe": self.config.timeframe,
                "initial_equity": self.config.initial_equity,
                "risk_per_trade": self.config.risk_per_trade,
            },
            "results": {
                "total_trades": self.total_trades,
                "wins": self.wins,
                "losses": self.losses,
                "win_rate": round(self.win_rate, 2),
                "total_pnl": round(self.total_pnl, 2),
                "max_drawdown": round(self.max_drawdown, 2),
            },
            "equity_curve": [(t.isoformat(), e) for t, e in self.equity_curve],
            "pnl_by_symbol": self.pnl_by_symbol,
            "hourly_stats": self.hourly_stats,
            "daily_stats": self.daily_stats,
        }


class Backtester:
    """
    Backtesting engine for TradeMindIQ strategies.
    
    Usage:
        1. Create Backtester with data source
        2. Configure backtest parameters
        3. Run backtest with a strategy function
        4. Analyze results
    """
    
    def __init__(self, data_source: str = "trades.db"):
        """
        Initialize backtester.
        
        Args:
            data_source: Path to trades.db or directory containing historical data
        """
        self.data_source = data_source
        self._price_data: Dict[str, List[Candle]] = {}
    
    def load_historical_data(
        self, 
        symbols: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, List[Candle]]:
        """
        Load historical candle data for backtesting.
        
        In production, this would fetch from exchange APIs.
        For demo, generates realistic synthetic data.
        """
        self._price_data = {}
        
        for symbol in symbols:
            self._price_data[symbol] = self._generate_synthetic_candles(
                symbol, start_date, end_date
            )
        
        return self._price_data
    
    def _generate_synthetic_candles(
        self, 
        symbol: str, 
        start: datetime, 
        end: datetime
    ) -> List[Candle]:
        """Generate realistic synthetic candle data for testing."""
        # Base price varies by symbol
        base_prices = {
            "BTC/USDT": 100000.0,
            "ETH/USDT": 3500.0,
            "SOL/USDT": 200.0,
            "BNB/USDT": 700.0,
        }
        base_price = base_prices.get(symbol, 50.0)
        
        candles = []
        current_price = base_price
        current_time = start
        
        while current_time < end:
            # Random walk with momentum
            change = random.gauss(0, 0.002)  # 0.2% typical move
            trend_factor = random.gauss(0, 0.001)
            current_price = current_price * (1 + change + trend_factor)
            
            # Generate OHLC
            volatility = 0.003  # 0.3% volatility
            open_price = current_price
            close_price = current_price * (1 + random.gauss(0, volatility))
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility)))
            
            # Ensure high >= open,close >= low
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            volume = random.gauss(1000000, 300000)
            
            candles.append(Candle(
                timestamp=int(current_time.timestamp() * 1000),
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume
            ))
            
            # Move to next minute
            current_time += timedelta(minutes=1)
            current_price = close_price
        
        return candles
    
    def run_backtest(
        self,
        config: BacktestConfig,
        strategy_fn: Callable
    ) -> BacktestResult:
        """
        Run backtest with given configuration and strategy.
        
        Args:
            config: Backtest configuration
            strategy_fn: Function that takes candles and returns trade signals
                        Signature: (symbol, candles, index) -> dict or None
                        
        Returns:
            BacktestResult with all metrics
        """
        # Load data if not already loaded
        if not self._price_data:
            start = config.start_date or datetime.now() - timedelta(days=7)
            end = config.end_date or datetime.now()
            self.load_historical_data(config.symbols, start, end)
        
        # Initialize tracking
        equity = config.initial_equity
        equity_curve = [(datetime.now(), equity)]
        open_positions = []
        closed_trades: List[BacktestTrade] = []
        daily_pnl: Dict[str, float] = defaultdict(float)
        hourly_stats: Dict[int, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        pnl_by_symbol: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
        last_trade_time: Dict[str, datetime] = {}
        daily_loss = 0.0
        daily_date = datetime.now().date()
        
        max_equity = equity
        max_drawdown = 0.0
        
        # Run through all candles for all symbols
        for symbol, candles in self._price_data.items():
            for i, candle in enumerate(candles):
                candle_time = datetime.fromtimestamp(candle.timestamp / 1000)
                
                # Check daily reset
                if candle_time.date() != daily_date:
                    daily_loss = 0.0
                    daily_date = candle_time.date()
                
                # Skip if daily loss cap hit
                if daily_loss >= config.daily_loss_cap:
                    continue
                
                # Check cooldown
                if symbol in last_trade_time:
                    time_since = (candle_time - last_trade_time[symbol]).total_seconds()
                    if time_since < config.cooldown_seconds:
                        continue
                
                # Check max open positions
                if len(open_positions) >= config.max_open_positions:
                    continue
                
                # Get indicators for this candle
                indicators = self._calculate_indicators(candles[:i+1])
                
                # Run strategy
                signal = strategy_fn(symbol, candles, i, indicators)
                
                if signal and not any(p["symbol"] == symbol for p in open_positions):
                    # Calculate position size
                    entry_price = signal.get("entry", candle.close)
                    stop_price = signal.get("stop", candle.close * 0.995)
                    target_price = signal.get("target", candle.close * 1.01)
                    
                    risk = abs(entry_price - stop_price)
                    if risk <= 0:
                        continue
                    
                    dollar_risk = equity * config.risk_per_trade
                    qty = dollar_risk / risk
                    
                    position = {
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "stop_price": stop_price,
                        "target_price": target_price,
                        "qty": qty,
                        "entry_time": candle_time,
                        "side": signal.get("side", "BUY"),
                    }
                    open_positions.append(position)
                    last_trade_time[symbol] = candle_time
        
        # Close all open positions at end
        final_time = datetime.now()
        for pos in open_positions:
            trade = self._close_position(pos, pos["entry_price"], final_time, "END")
            closed_trades.append(trade)
            equity += trade.pnl
            daily_pnl[trade.exit_time.date().isoformat()] += trade.pnl
            hourly_stats[trade.exit_time.hour]["trades"] += 1
            if trade.pnl > 0:
                hourly_stats[trade.exit_time.hour]["wins"] += 1
            hourly_stats[trade.exit_time.hour]["pnl"] += trade.pnl
            pnl_by_symbol[trade.symbol]["trades"] += 1
            if trade.pnl > 0:
                pnl_by_symbol[trade.symbol]["wins"] += 1
            pnl_by_symbol[trade.symbol]["pnl"] += trade.pnl
            
            # Track drawdown
            max_equity = max(max_equity, equity)
            drawdown = (max_equity - equity) / max_equity * 100
            max_drawdown = max(max_drawdown, drawdown)
            daily_loss += trade.pnl if trade.pnl < 0 else 0
        
        # Calculate metrics
        wins = sum(1 for t in closed_trades if t.pnl > 0)
        losses = len(closed_trades) - wins
        total_pnl = sum(t.pnl for t in closed_trades)
        
        # Build symbol stats
        symbol_stats = {}
        for symbol, stats in pnl_by_symbol.items():
            symbol_stats[symbol] = {
                "total_trades": stats["trades"],
                "wins": stats["wins"],
                "losses": stats["trades"] - stats["wins"],
                "win_rate": (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0,
                "total_pnl": round(stats["pnl"], 2)
            }
        
        # Convert hourly stats to regular dict
        hourly_stats_dict = {
            hour: {
                "trades": data["trades"],
                "wins": data["wins"],
                "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] > 0 else 0,
                "pnl": round(data["pnl"], 2)
            }
            for hour, data in hourly_stats.items()
        }
        
        return BacktestResult(
            config=config,
            trades=closed_trades,
            total_trades=len(closed_trades),
            wins=wins,
            losses=losses,
            win_rate=(wins / len(closed_trades) * 100) if closed_trades else 0,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            equity_curve=equity_curve,
            pnl_by_symbol=symbol_stats,
            hourly_stats=hourly_stats_dict,
            daily_stats=dict(daily_pnl)
        )
    
    def _calculate_indicators(self, candles: List[Candle]) -> Dict[str, Any]:
        """Calculate technical indicators for a set of candles."""
        if not candles:
            return {}
        
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        
        # Simple EMA calculations
        ema9 = self._ema(closes, 9)
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        
        # ATR
        atr14 = self._atr(candles, 14)
        
        # Relative volume
        avg_vol = sum(volumes[-20:]) / min(20, len(volumes))
        rel_vol = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
        
        # Gap percentage
        if len(candles) >= 2:
            gap_pct = (candles[-1].close - candles[-2].close) / candles[-2].close * 100
        else:
            gap_pct = 0
        
        return {
            "closes": closes,
            "ema9": ema9,
            "ema20": ema20,
            "ema50": ema50,
            "atr14": atr14,
            "rel_vol": rel_vol,
            "gap_pct": gap_pct,
            "volume": volumes[-1] if volumes else 0
        }
    
    def _ema(self, data: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return data[:]
        
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        
        for price in data[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    def _atr(self, candles: List[Candle], period: int) -> List[float]:
        """Calculate Average True Range."""
        if len(candles) < period:
            return [0] * len(candles)
        
        true_ranges = []
        for i, candle in enumerate(candles):
            if i == 0:
                tr = candle.high - candle.low
            else:
                prev_close = candles[i-1].close
                tr = max(
                    candle.high - candle.low,
                    abs(candle.high - prev_close),
                    abs(candle.low - prev_close)
                )
            true_ranges.append(tr)
        
        # Simple ATR (not full EMA version for simplicity)
        atr = [sum(true_ranges[:period]) / period]
        for tr in true_ranges[period:]:
            atr.append((atr[-1] * (period - 1) + tr) / period)
        
        # Pad to match candle length
        while len(atr) < len(candles):
            atr.insert(0, atr[0])
        
        return atr
    
    def _close_position(
        self, 
        position: Dict, 
        exit_price: float, 
        exit_time: datetime, 
        reason: str
    ) -> BacktestTrade:
        """Close a position and calculate results."""
        entry_price = position["entry_price"]
        qty = position["qty"]
        side = position["side"]
        
        if side == "BUY":
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty
        
        pnl_pct = (pnl / (entry_price * qty)) * 100
        
        duration = (exit_time - position["entry_time"]).total_seconds()
        
        return BacktestTrade(
            symbol=position["symbol"],
            entry_time=position["entry_time"],
            entry_price=entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            side=side,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            duration_seconds=duration
        )
    
    def run_warrior_momentum_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_equity: float = 500.0
    ) -> BacktestResult:
        """Run backtest using Warrior Momentum strategy rules."""
        
        def warrior_strategy(symbol: str, candles: List[Candle], index: int, indicators: Dict) -> Optional[Dict]:
            if index < 50:
                return None
            
            close = candles[index].close
            ema9 = indicators["ema9"][-1]
            ema20 = indicators["ema20"][-1]
            ema50 = indicators["ema50"][-1]
            rel_vol = indicators["rel_vol"]
            gap_pct = indicators["gap_pct"]
            
            # Warrior filters
            if rel_vol < 2.0:
                return None
            if gap_pct < 0.5:
                return None
            if not (close > ema9 > ema20 > ema50):
                return None
            
            # Price filters
            if close < 0.10 or close > 1000:
                return None
            
            # Calculate stop and target
            atr = indicators["atr14"][-1]
            if atr <= 0:
                return None
            
            stop = min(ema20, candles[index-1].low)
            if stop >= close:
                return None
            
            target = close + 2.0 * (close - stop)
            
            return {
                "symbol": symbol,
                "entry": close,
                "stop": stop,
                "target": target,
                "side": "BUY"
            }
        
        config = BacktestConfig(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_equity=initial_equity,
            risk_per_trade=0.10,
            r_multiple=2.0
        )
        
        return self.run_backtest(config, warrior_strategy)
    
    def generate_report(self, result: BacktestResult) -> str:
        """Generate formatted backtest report."""
        lines = [
            "=" * 60,
            "TradeMindIQ Backtest Report",
            "=" * 60,
            "",
            f"Period: {result.config.start_date} to {result.config.end_date}",
            f"Symbols: {', '.join(result.config.symbols)}",
            f"Initial Equity: ${result.config.initial_equity:,.2f}",
            "",
            "📊 PERFORMANCE SUMMARY",
            "-" * 40,
            f"Total Trades:    {result.total_trades}",
            f"Win Rate:        {result.win_rate:.1f}%",
            f"Total P/L:       ${result.total_pnl:,.2f}",
            f"Max Drawdown:    {result.max_drawdown:.2f}%",
            "",
            "🏆 BEST SYMBOLS",
            "-" * 40,
        ]
        
        sorted_symbols = sorted(
            result.pnl_by_symbol.items(), 
            key=lambda x: x[1]["total_pnl"], 
            reverse=True
        )
        
        for symbol, stats in sorted_symbols[:10]:
            emoji = "🟢" if stats["total_pnl"] > 0 else "🔴"
            lines.append(f"{emoji} {symbol:<12} ${stats['total_pnl']:>8.2f} ({stats['win_rate']:.0f}% WR)")
        
        lines.extend([
            "",
            "⏰ BEST HOURS",
            "-" * 40,
        ])
        
        sorted_hours = sorted(
            result.hourly_stats.items(),
            key=lambda x: x[1]["pnl"],
            reverse=True
        )
        
        for hour, stats in sorted_hours[:5]:
            lines.append(f"  {hour:02d}:00 - ${stats['pnl']:>8.2f} ({stats['trades']} trades)")
        
        lines.extend([
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def export_results(self, result: BacktestResult, filepath: str = "backtest_results.json"):
        """Export backtest results to JSON."""
        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Results exported to {filepath}")


# Convenience function
def quick_backtest(
    symbols: List[str] = None,
    days: int = 7,
    initial_equity: float = 500.0
) -> BacktestResult:
    """Quick backtest with default settings."""
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT"]
    
    end = datetime.now()
    start = end - timedelta(days=days)
    
    backtester = Backtester()
    result = backtester.run_warrior_momentum_backtest(
        symbols=symbols,
        start_date=start,
        end_date=end,
        initial_equity=initial_equity
    )
    
    print(backtester.generate_report(result))
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        result = quick_backtest()
        result.backtester.export_results(result)
    else:
        quick_backtest()
