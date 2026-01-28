# ai/post_trade_schema.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Literal, List

ExitReason = Literal[
    "TARGET", "STOP", "TIME", "TRAIL", "MANUAL", "LIQUIDATION", "ERROR", "UNKNOWN"
]

Side = Literal["long", "short"]
Timeframe = Literal["1m", "3m", "5m", "15m", "1h"]  # extend as needed


@dataclass
class PostTradeContext:
    """Frozen, serializable state used for deterministic post-trade rules."""

    # ---- required core identifiers ----
    symbol: str
    exchange: str
    market_type: str
    timeframe: str
    side: str
    strategy_name: str

    # ---- required timing/pricing ----
    entry_ts: int
    exit_ts: int
    hold_seconds: int
    entry_price: float
    exit_price: float
    qty: float
    notional_usd: float
    pnl_usd: float

    # ---- optional / defaulted fields (must come after required) ----
    pnl_r: float = 0.0
    fees_usd: float = 0.0
    slippage_bps: float | None = None
    risk_per_trade: float = 0.0
    planned_stop_price: float | None = None
    planned_target_price: float | None = None
    atr_value: float | None = None
    stop_distance_atr: float | None = None
    breakout_lookback: int = 12
    breakout_level: float | None = None
    breakout_close_above: bool | None = None
    body_pct: float | None = None
    upper_wick_pct: float | None = None
    vol_spike: float | None = None
    gap_pct: float | None = None
    ema_alignment: bool | None = None
    orderflow_enabled: bool = False
    book_depth: int = 0
    bid_ask_ratio: float | None = None
    buy_sell_ratio: float | None = None
    tape_trades: int = 0
    spread_bps: float | None = None
    exit_reason: str = "UNKNOWN"
    max_favorable_excursion_r: float | None = None
    max_adverse_excursion_r: float | None = None
    rejections: int = 0
    dry_run: bool = True
    indicators: dict = field(default_factory=dict)
    data_quality: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
