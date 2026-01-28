# exchanges/base_exchange.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExchangeCapabilities:
    """
    Strategy engine uses these flags to decide what it can safely call.
    """
    # Asset class coverage
    supports_equities: bool = False
    supports_crypto: bool = False

    supports_spot: bool = False
    supports_futures: bool = False

    # Market data
    supports_bars: bool = False
    supports_quotes: bool = False
    supports_orderflow: bool = False

    # Order types
    supports_market_orders: bool = True
    supports_limit_orders: bool = False
    supports_sl_tp_native: bool = False

    # Connectivity
    supports_ws: bool = False
    supports_ohlcv: bool = False

    # Execution
    supports_live_trading: bool = False

    # Sizing semantics
    qty_is_contracts: bool = False
    qty_is_base_units: bool = False
    supports_partial_close: bool = True


class BaseExchange(ABC):
    """
    All exchange adapters must implement this interface.
    """

    capabilities: ExchangeCapabilities = ExchangeCapabilities()

    runtime_capabilities: Dict[str, Any] = {
        "asset_class": "crypto",          # crypto | equities | fx
        "supports_short": True,
        "supports_premarket": False,
        "supports_fractional_qty": False,
    }

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.runtime_capabilities = dict(self.runtime_capabilities)

    # ---------- lifecycle ----------

    @abstractmethod
    def connect(self) -> None:
        """Validate credentials / initialize session"""
        ...

    # ---------- account ----------

    @abstractmethod
    def get_balance(self, asset: str = "USD") -> float:
        ...

    @abstractmethod
    def get_open_positions(self, symbol: Optional[str] = None):
        ...

    # ---------- market data ----------

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
    ):
        ...

    # ---------- execution ----------

    @abstractmethod
    def market_buy(
        self,
        symbol: str,
        qty: float,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def market_sell(
        self,
        symbol: str,
        qty: float,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def close_position(
        self,
        position_id: str,
        qty: Optional[float] = None,
        price_hint: float = 0.0,
    ) -> Dict[str, Any]:
        ...
