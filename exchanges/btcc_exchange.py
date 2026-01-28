from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.execution_mode import DryRunMixin

from .base_exchange import BaseExchange, ExchangeCapabilities
from .btcc_client import BTCCClient


class BTCCExchange(DryRunMixin, BaseExchange):
    """TradeMindIQ adapter for BTCC (REST).

    This adapter focuses on execution/account operations.
    Market data (candles/tickers) should still come from your existing market-data
    client unless you also add BTCC market-data endpoints.
    """

    capabilities: ExchangeCapabilities = ExchangeCapabilities(
        supports_futures=True,
        supports_spot=False,
        supports_market_orders=True,
        supports_limit_orders=False,
        supports_sl_tp_native=True,
        supports_ws=False,
        supports_ohlcv=False,
        qty_is_contracts=True,
        qty_is_base_units=False,
        supports_partial_close=True,
    )

    def qty_from_notional(
        self,
        symbol: str,
        notional_usd: float,
        price: float,
        contract_value_usd: float = 1.0,
    ) -> float:
        """Convert a USD-notional into the exchange's expected quantity units.

        Default behavior assumes $1 contracts (common for derivatives). Adjust
        contract_value_usd per-symbol once you confirm BTCC contract specs.
        """
        n = float(notional_usd)
        p = float(price) if price else 0.0
        if self.capabilities.qty_is_contracts:
            return max(1.0, n / max(float(contract_value_usd), 1e-9))
        if self.capabilities.qty_is_base_units:
            return n / max(p, 1e-9)
        return n

    def _normalize_qty(self, symbol: str, qty: float, price_hint: float) -> float:
        """Internal helper for converting strategy qty to BTCC request_volume.

        If cfg.btcc.qty_mode == 'notional_usd', interpret qty as USD notional.
        Otherwise, assume qty is already the exchange-native unit.
        """
        btcc_cfg = (self.cfg.get("btcc") or {})
        qty_mode = str(btcc_cfg.get("qty_mode", "native")).strip().lower()
        if qty_mode in ("notional", "notional_usd", "usd"):
            contract_value_usd = float(btcc_cfg.get("contract_value_usd", 1.0) or 1.0)
            return float(self.qty_from_notional(symbol, float(qty), float(price_hint), contract_value_usd))
        return float(qty)

    def __init__(self, cfg: Dict[str, Any]) -> None:
        super().__init__(cfg)
        btcc_cfg = (cfg or {}).get("btcc") or {}
        self.client = BTCCClient(
            base_url=btcc_cfg["base_url"],
            user_name=btcc_cfg["user_name"],
            password=btcc_cfg["password"],
            api_key=btcc_cfg["api_key"],
            secret_key=btcc_cfg["secret_key"],
            company_id=int(btcc_cfg.get("company_id", 1)),
        )

    # ---- lifecycle ----

    def connect(self) -> None:
        # Even in dry-run, login can be useful to validate credentials.
        self.client.ensure_logged_in()

    # ---- account / positions ----

    def get_balance(self, asset: str = "USDT") -> float:
        acct = self.client.get_account_info()
        return float(acct.get("equity", acct.get("balance", 0.0)) or 0.0)

    def get_open_positions(self, symbol: Optional[str] = None):
        data = self.client.get_positions()
        positions = data.get("positions", []) or []
        if symbol:
            positions = [p for p in positions if p.get("symbol") == symbol]
        return positions

    # ---- orders ----

    def market_buy(
        self,
        symbol: str,
        qty: float,
        leverage: int = 20,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        req_qty = self._normalize_qty(symbol, qty, price_hint)
        payload = {
            "symbol": symbol,
            "qty": float(qty),
            "request_volume": float(req_qty),
            "leverage": int(leverage),
            "price_hint": float(price_hint),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        if self._is_dry_run():
            return self._dry_run_payload("market_buy", payload)

        return self.client.open_position(
            symbol=symbol,
            direction=1,
            volume=float(req_qty),
            price=float(price_hint),
            stop_loss=stop_loss,
            take_profit=take_profit,
            multiple=int(leverage),
        )

    def market_sell(
        self,
        symbol: str,
        qty: float,
        leverage: int = 20,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        req_qty = self._normalize_qty(symbol, qty, price_hint)
        payload = {
            "symbol": symbol,
            "qty": float(qty),
            "request_volume": float(req_qty),
            "leverage": int(leverage),
            "price_hint": float(price_hint),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        if self._is_dry_run():
            return self._dry_run_payload("market_sell", payload)

        return self.client.open_position(
            symbol=symbol,
            direction=2,
            volume=float(req_qty),
            price=float(price_hint),
            stop_loss=stop_loss,
            take_profit=take_profit,
            multiple=int(leverage),
        )

    def close_position(self, position_id: int, qty: float, price_hint: float = 0.0) -> Dict[str, Any]:
        payload = {
            "position_id": int(position_id),
            "qty": float(qty),
            "price_hint": float(price_hint),
        }
        if self._is_dry_run():
            return self._dry_run_payload("close_position", payload)

        return self.client.close_position(
            position_id=int(position_id),
            volume=float(qty),
            price=float(price_hint),
        )
