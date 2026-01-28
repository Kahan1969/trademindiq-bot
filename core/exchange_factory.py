# core/exchange_factory.py

from __future__ import annotations

from typing import Any, Dict


_ALIASES = {
    "btcc_futures": "btcc",
    "btcc-perp": "btcc",
    "alpaca_equities": "alpaca",
}


def _resolve_exchange_name(exchange_cfg: Any) -> str:
    # legacy: exchange: "kucoin"
    if isinstance(exchange_cfg, str):
        return exchange_cfg.strip().lower()

    # modern: exchange: { name: "BTCC", type: "futures" }
    if isinstance(exchange_cfg, dict):
        name = exchange_cfg.get("name")
        if not name:
            raise ValueError("exchange.name is required")
        return str(name).strip().lower()

    raise TypeError("exchange must be str or dict")


def create_exchange(cfg: Dict[str, Any]):
    exchange_cfg = cfg.get("exchange")
    if exchange_cfg is None:
        raise ValueError("Missing required config: exchange")

    name = _resolve_exchange_name(exchange_cfg)
    name = _ALIASES.get(name, name)

    if name == "btcc":
        # NOTE: your BTCC adapter currently lives under `Exchanges/` (capital E)
        from Exchanges.btcc_exchange import BTCCExchange

        return BTCCExchange(cfg)

    if name == "alpaca":
        from exchanges.alpaca_exchange import AlpacaExchange

        return AlpacaExchange(cfg)

    if name == "binance":
        from exchanges.binance_exchange import BinanceExchange

        return BinanceExchange(cfg)

    if name == "kucoin":
        from exchanges.kucoin_exchange import KucoinExchange

        return KucoinExchange(cfg)

    raise ValueError(f"Unknown exchange: {name}")
