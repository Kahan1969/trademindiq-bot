from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from core.models import Signal, Side
from .base import BaseStrategy

# Per-symbol profile so we can tune thresholds & risk by tier
SYMBOL_PROFILE: Dict[str, Dict[str, Any]] = {
    # Mega caps – move slower, allow smaller gaps/RVOL, less risk per trade
    "BTC/USDT": {"tier": "mega", "min_rel_vol": 1.5, "min_gap_pct": 0.20, "risk_factor": 0.6},
    "ETH/USDT": {"tier": "mega", "min_rel_vol": 1.6, "min_gap_pct": 0.25, "risk_factor": 0.6},
    "BNB/USDT": {"tier": "mega", "min_rel_vol": 1.8, "min_gap_pct": 0.30, "risk_factor": 0.6},

    # Leaders / fast movers – Warrior-style momentum sweet spot
    "SOL/USDT": {"tier": "leader", "min_rel_vol": 2.5, "min_gap_pct": 0.75, "risk_factor": 1.0},
    "AVAX/USDT": {"tier": "leader", "min_rel_vol": 2.3, "min_gap_pct": 0.70, "risk_factor": 1.0},
    "INJ/USDT":  {"tier": "leader", "min_rel_vol": 2.5, "min_gap_pct": 0.80, "risk_factor": 1.0},
    "NEAR/USDT": {"tier": "leader", "min_rel_vol": 2.2, "min_gap_pct": 0.70, "risk_factor": 1.0},
    "OP/USDT":   {"tier": "leader", "min_rel_vol": 2.2, "min_gap_pct": 0.70, "risk_factor": 1.0},
    "ARB/USDT":  {"tier": "leader", "min_rel_vol": 2.2, "min_gap_pct": 0.70, "risk_factor": 1.0},
    "SUI/USDT":  {"tier": "leader", "min_rel_vol": 2.3, "min_gap_pct": 0.70, "risk_factor": 1.0},

    # Mid caps – more volatile, require higher RVOL/gap but we keep base risk
    "XRP/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.8},
    "ADA/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.8},
    "DOGE/USDT": {"tier": "mid", "min_rel_vol": 2.2, "min_gap_pct": 0.60, "risk_factor": 0.9},
    "LINK/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.9},
    "MATIC/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.9},
    "DOT/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.9},
    "LTC/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.8},
    "BCH/USDT": {"tier": "mid", "min_rel_vol": 2.0, "min_gap_pct": 0.50, "risk_factor": 0.8},
    # ...other symbols will fall back to global defaults
}


class WarriorMomentumStrategy(BaseStrategy):
    """
    Warrior-style momentum rules adapted for crypto:
    - Only trade when there is a clear gap + high relative volume.
    - Price above EMA9 > EMA20 > EMA50.
    - Only trade during “session” hours (high-vol window).
    - Use ATR/swing-low-based stop with R-multiple profit target.
    """

    name = "warrior_momentum"

    def __init__(
        self,
        risk_per_trade: float,
        r_multiple: float,
        min_rel_vol: float,
        min_gap_pct: float,
        min_price: float = 0.10,
        max_price: float = 1000.0,
        session_start_utc: int = 12,  # approx start of EU/US overlap
        session_end_utc: int = 20,    # after NY open window
        min_atr_fraction: float = 0.0015,  # skip super-tight ranges (<0.15% of price)
    ):
        self.base_risk_per_trade = risk_per_trade
        self.r_multiple = r_multiple
        self.default_min_rel_vol = min_rel_vol
        self.default_min_gap_pct = min_gap_pct
        self.min_price = min_price
        self.max_price = max_price
        self.session_start_utc = session_start_utc
        self.session_end_utc = session_end_utc
        self.min_atr_fraction = min_atr_fraction

    def _thresholds_for_symbol(self, symbol: str) -> Dict[str, float]:
        profile = SYMBOL_PROFILE.get(symbol, {})
        return {
            "min_rel_vol": profile.get("min_rel_vol", self.default_min_rel_vol),
            "min_gap_pct": profile.get("min_gap_pct", self.default_min_gap_pct),
            "risk_factor": profile.get("risk_factor", 1.0),
        }

    def _in_session(self, last_ts_ms: int) -> bool:
        # candle timestamp is usually ms since epoch
        ts = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc)
        hour = ts.hour
        return self.session_start_utc <= hour < self.session_end_utc

    def generate_signal(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        candles: List[List[float]],
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        if len(candles) < 60:
            return None

        last_ts = int(candles[-1][0])
        if not self._in_session(last_ts):
            # mimic Warrior's "only morning session" filter
            return None

        closes = indicators["closes"]
        ema9 = indicators["ema9"]
        ema20 = indicators["ema20"]
        ema50 = indicators["ema50"]
        atr14 = indicators["atr14"]
        rel_vol_all = indicators["rel_vol"]
        gap_pct_all = indicators["gap_pct"]

        close = float(closes[-1])

        # price sanity filter
        if close < self.min_price or close > self.max_price:
            return None

        thresholds = self._thresholds_for_symbol(symbol)
        min_rel_vol = thresholds["min_rel_vol"]
        min_gap_pct = thresholds["min_gap_pct"]
        risk_factor = thresholds["risk_factor"]

        # Warrior-style filters: strong gap + RVOL
        if rel_vol_all < min_rel_vol:
            return None
        if gap_pct_all < min_gap_pct:
            return None

        # trend alignment: EMAs stacked and price above EMAs
        if not (close > ema9[-1] > ema20[-1] > ema50[-1]):
            return None

        # ATR-based "is there enough range to bother?"
        last_atr = float(atr14[-1]) if atr14[-1] == atr14[-1] else 0.0  # NaN check
        if last_atr <= 0 or (last_atr / close) < self.min_atr_fraction:
            return None

        # stop = below EMA20 and recent swing-low for protection
        recent_lows = [c[3] for c in candles[-5:]]
        swing_low = float(min(recent_lows))
        stop = min(float(ema20[-1]), swing_low)
        if stop >= close:
            return None
        print(
    f"[SIZING_PRE] symbol={symbol} entry={entry_price} stop={stop_price} "
    f"stop_dist={abs(entry_price - stop_price):.8f}"
)

        risk_per_unit = close - stop
        equity = context["equity"]
        # adjust risk per trade by symbol tier (mega uses 60% of base, leaders 100%, etc.)
        dollar_risk = equity * self.base_risk_per_trade * risk_factor
        qty = dollar_risk / risk_per_unit
        print(
    f"[SIZING] symbol={symbol} entry={entry_price} stop={stop_price} "
    f"risk_per_unit={risk_per_unit:.8f} dollar_risk={dollar_risk:.2f} qty={qty:.8f}"
)

        target = close + self.r_multiple * risk_per_unit

        sentiment_score = context.get("sentiment_score", 0.0)
        sentiment_label = context.get("sentiment_label") or (
            "Bullish" if sentiment_score > 0 else "Bearish" if sentiment_score < 0 else "Neutral"
        )
        news_links = context.get("news_links", [])

        return Signal(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            side=Side.BUY,
            entry=close,
            stop=stop,
            target=target,
            qty=qty,
            rel_vol=rel_vol_all,
            gap_pct=gap_pct_all,
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            news_links=news_links,
        )
