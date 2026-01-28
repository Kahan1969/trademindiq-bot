# exchanges/alpaca_exchange.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import requests

from exchanges.base_exchange import BaseExchange, ExchangeCapabilities


def _iso_z(dt: datetime) -> str:
    """RFC3339 with Z suffix (what Alpaca expects)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class AlpacaExchange(BaseExchange):
    """
    Alpaca adapter (Equities/ETFs) for TradeMindIQ.

    Expected settings.yaml keys (example):

    exchange:
      name: alpaca
      type: equities

    alpaca:
      trading_mode: paper          # paper | live
      base_url_paper: "https://paper-api.alpaca.markets"
      base_url_live:  "https://api.alpaca.markets"
      data_url:       "https://data.alpaca.markets"
      api_key_id:     "YOUR_KEY_ID"
      api_secret_key: "YOUR_SECRET_KEY"
      feed: "iex"                  # iex | sip (sip requires subscription)
      extended_hours: false

    Notes:
    - Alpaca uses BOTH API Key ID and API Secret Key. If you only have one value,
      you likely copied only the Key ID. You need the secret as well to auth.
    """

    capabilities: ExchangeCapabilities = ExchangeCapabilities(
        supports_equities=True,
        supports_crypto=False,
        supports_spot=True,
        supports_futures=False,
        supports_bars=True,
        supports_quotes=True,
        supports_orderflow=False,
        supports_market_orders=True,
        supports_limit_orders=True,
        supports_sl_tp_native=False,
        supports_ws=False,
        supports_ohlcv=True,
        supports_live_trading=True,
        qty_is_contracts=False,
        qty_is_base_units=False,
        supports_partial_close=True,
    )

    runtime_capabilities: Dict[str, Any] = {
        "asset_class": "equities",          # crypto | equities | fx
        "supports_short": True,             # depends on your account permissions
        "supports_premarket": True,
        "supports_fractional_qty": True,    # if account enabled
        "supports_orderflow": False,
    }

    def __init__(self, cfg: Dict[str, Any]) -> None:
        super().__init__(cfg)

        a = (cfg or {}).get("alpaca") or {}

        trading_mode = str(a.get("trading_mode", a.get("mode", "paper"))).lower().strip()
        base_paper = a.get("base_url_paper", "https://paper-api.alpaca.markets")
        base_live = a.get("base_url_live", "https://api.alpaca.markets")

        self.base_url = base_live if trading_mode == "live" else base_paper
        self.data_url = a.get("data_url", "https://data.alpaca.markets")

        self.api_key_id = a.get("api_key_id") or a.get("key_id") or a.get("api_key")
        self.api_secret_key = a.get("api_secret_key") or a.get("secret_key") or a.get("secret")

        self.feed = str(a.get("feed", "iex")).lower().strip()  # iex | sip
        self.extended_hours = bool(a.get("extended_hours", False))

        self.headers = {
            "APCA-API-KEY-ID": str(self.api_key_id or ""),
            "APCA-API-SECRET-KEY": str(self.api_secret_key or ""),
            "Content-Type": "application/json",
        }

        # light internal state
        self._connected: bool = False

    # ---------------------------
    # BaseExchange required API
    # ---------------------------

    def connect(self) -> None:
        """
        Alpaca is REST-based; no persistent socket needed.
        Validate credentials by calling account endpoint.
        """
        if not self.api_key_id or not self.api_secret_key:
            raise RuntimeError(
                "Alpaca credentials missing. You need BOTH api_key_id and api_secret_key "
                "in settings.yaml under alpaca: ..."
            )

        r = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Alpaca connect failed HTTP {r.status_code}: {r.text}")
        self._connected = True

    def get_balance(self, asset: str = "USD") -> float:
        """
        Returns cash for USD (most useful for risk sizing).
        """
        self._ensure_connected()

        r = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Alpaca get_balance failed HTTP {r.status_code}: {r.text}")
        acct = r.json() or {}

        if asset.upper() in ("USD", "USDT", "CASH"):
            return float(acct.get("cash") or 0.0)
        return 0.0

    def get_open_positions(self, symbol: Optional[str] = None):
        """
        Returns normalized positions.
        If symbol is provided, filters to that symbol.
        """
        self._ensure_connected()

        r = requests.get(f"{self.base_url}/v2/positions", headers=self.headers, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Alpaca get_open_positions failed HTTP {r.status_code}: {r.text}")
        positions = r.json() or []

        out: List[Dict[str, Any]] = []
        for p in positions:
            sym = p.get("symbol")
            if symbol and sym != symbol:
                continue

            qty = float(p.get("qty") or 0.0)
            out.append(
                {
                    "symbol": sym,
                    "qty": qty,
                    "side": "long" if qty > 0 else "short",
                    "avg_entry_price": float(p.get("avg_entry_price") or 0.0),
                    "market_value": float(p.get("market_value") or 0.0) if p.get("market_value") is not None else None,
                    "unrealized_pl": float(p.get("unrealized_pl") or 0.0) if p.get("unrealized_pl") is not None else None,
                    # optional raw for debugging
                    "raw": p,
                }
            )
        return out

    def market_buy(
        self,
        symbol: str,
        qty: float,
        leverage: int = 1,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Market buy. (Alpaca equities are not leverage-param driven at order-time.
        Leverage/margin is account-level, so leverage is ignored here.)
        """
        return self._place_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            order_type="market",
            time_in_force="day",
            extended_hours=self.extended_hours,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def market_sell(
        self,
        symbol: str,
        qty: float,
        leverage: int = 1,
        price_hint: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Market sell.
        """
        return self._place_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            order_type="market",
            time_in_force="day",
            extended_hours=self.extended_hours,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def close_position(
        self,
        position_id: int,
        qty: float,
        price_hint: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Alpaca closes positions by SYMBOL endpoint:
          DELETE /v2/positions/{symbol} (full close)
          DELETE /v2/positions/{symbol}?qty=... (partial close)

        Your BaseExchange signature uses position_id:int.
        In this codebase, many strategies actually pass a symbol or position object.
        So we allow:
          - position_id as an int that represents "index" in open positions list (fallback)
          - or a string symbol (works best)

        If you want strict behavior, change your engine to pass symbol explicitly.
        """
        self._ensure_connected()

        # Best-case: caller passes symbol even though annotation says int.
        if isinstance(position_id, str):
            return self.close_position_by_symbol(position_id, qty=qty)

        # Fallback: interpret int as index into open positions list
        positions = self.get_open_positions()
        if not positions:
            return {"ok": True, "closed": False, "reason": "no_open_positions"}

        if position_id < 0 or position_id >= len(positions):
            raise ValueError(
                f"close_position received position_id={position_id}, but only "
                f"{len(positions)} open positions exist. Pass symbol instead."
            )

        sym = positions[position_id]["symbol"]
        return self.close_position_by_symbol(sym, qty=qty)

    # ---------------------------
    # Market data helpers
    # ---------------------------

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 200) -> List[List[float]]:
        """
        CCXT-style candles: [ts_ms, o, h, l, c, v]
        Uses explicit start/end to avoid empty defaults.
        """
        self._ensure_connected(auth_only=False)

        tf_map = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}
        if timeframe not in tf_map:
            raise ValueError(f"Unsupported timeframe={timeframe}. Supported: {list(tf_map.keys())}")

        end = datetime.now(timezone.utc)
        # request a wider range than limit to avoid sparse minutes; Alpaca will cap via limit anyway
        lookback_minutes = max(120, int(limit) * 3)
        start = end - timedelta(minutes=lookback_minutes)

        url = f"{self.data_url}/v2/stocks/{symbol}/bars"
        params = {
            "timeframe": tf_map[timeframe],
            "start": _iso_z(start),
            "end": _iso_z(end),
            "limit": int(limit),
            "feed": self.feed,          # iex | sip
            "adjustment": "raw",
        }

        r = requests.get(url, headers=self.headers, params=params, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Alpaca bars HTTP {r.status_code}: {r.text}")

        data = r.json() or {}
        bars = data.get("bars") or []

        out: List[List[float]] = []
        for b in bars:
            # Alpaca v2 bars: t,o,h,l,c,v (t is RFC3339)
            t = b.get("t")
            if isinstance(t, str):
                ts = datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
            else:
                # if ever returned numeric
                ts = float(t or 0.0)
            ts_ms = int(ts * 1000)

            out.append(
                [
                    ts_ms,
                    float(b.get("o") or 0.0),
                    float(b.get("h") or 0.0),
                    float(b.get("l") or 0.0),
                    float(b.get("c") or 0.0),
                    float(b.get("v") or 0.0),
                ]
            )
        return out

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def close_position_by_symbol(self, symbol: str, qty: float = 0.0) -> Dict[str, Any]:
        """
        Close by symbol (preferred).
        qty=0.0 closes full position. qty>0.0 requests partial close.
        """
        self._ensure_connected()

        url = f"{self.base_url}/v2/positions/{symbol}"
        params = {}
        if qty and qty > 0:
            # Alpaca expects qty as a string for safety with fractions
            params["qty"] = str(qty)

        r = requests.delete(url, headers=self.headers, params=params, timeout=20)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Alpaca close_position HTTP {r.status_code}: {r.text}")

        # DELETE may return JSON (200) or empty (204)
        payload: Any = None
        try:
            payload = r.json()
        except Exception:
            payload = None

        return {"ok": True, "symbol": symbol, "qty": qty, "raw": payload}

    def _place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        extended_hours: bool = False,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        self._ensure_connected()

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }

        if order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            payload["limit_price"] = str(limit_price)

        # extended_hours only valid for certain order types/TIF
        if extended_hours:
            payload["extended_hours"] = True

        # Optional bracket order (native SL/TP) only if you actually want it.
        # If your engine handles stops/targets itself, keep supports_sl_tp_native=False
        # and do NOT set this.
        if stop_loss is not None and take_profit is not None:
            payload["order_class"] = "bracket"
            payload["take_profit"] = {"limit_price": str(take_profit)}
            payload["stop_loss"] = {"stop_price": str(stop_loss)}

        r = requests.post(f"{self.base_url}/v2/orders", headers=self.headers, json=payload, timeout=20)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Alpaca order HTTP {r.status_code}: {r.text}")

        o = r.json() or {}
        # normalize minimal fields expected by your router/logging
        return {
            "ok": True,
            "id": o.get("id") or o.get("client_order_id"),
            "symbol": symbol,
            "side": side,
            "qty": float(o.get("qty") or qty),
            "status": o.get("status"),
            "raw": o,
        }

    def _ensure_connected(self, auth_only: bool = True) -> None:
        """
        If auth_only=True, we only need headers present.
        If auth_only=False, we require connect() to have validated creds.
        """
        if not self.api_key_id or not self.api_secret_key:
            raise RuntimeError(
                "Alpaca credentials missing. Set alpaca.api_key_id and alpaca.api_secret_key in settings.yaml."
            )
        if not auth_only and not self._connected:
            # allow lazy connect for market-data calls
            self.connect()
