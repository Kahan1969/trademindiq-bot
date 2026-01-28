from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Mode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass
class Signal:
    symbol: str
    exchange: str
    timeframe: str
    side: Side
    entry: float
    stop: float
    target: float
    qty: float
    rel_vol: float
    gap_pct: float
    sentiment_score: float
    sentiment_label: str
    news_links: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderResult:
    signal: Signal
    order_id: str
    mode: Mode
    filled_price: float
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Trade:
    signal: Signal
    order: OrderResult
    exit_price: float
    pnl: float
    exit_reason: str
    closed_at: datetime = field(default_factory=datetime.utcnow)
