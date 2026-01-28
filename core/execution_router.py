# core/execution_router.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

from exchanges.base_exchange import BaseExchange

try:
    from ai.post_trade_schema import PostTradeContext
    from ai.post_trade_review_engine import generate_post_trade_review
except Exception:
    PostTradeContext = None  # type: ignore
    generate_post_trade_review = None  # type: ignore


@dataclass
class TradeIntent:
    symbol: str
    side: str             # "long" | "short" | "flat"
    qty: float
    leverage: int = 1
    price_hint: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


def execute_intent(
    exchange: BaseExchange,
    intent: TradeIntent,
    current_position: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generic execution:
      - If intent is flat: close existing
      - If intent is long/short:
          - if opposite position exists, close then open
          - if same direction exists, do nothing (or scale in if you want)
    """

    side = intent.side.lower().strip()

    # Close logic
    if side == "flat":
        if not current_position:
            return {"status": "no_position_to_close"}
        return exchange.close_position(
            position_id=int(current_position["id"]),
            qty=float(current_position.get("volume") or current_position.get("qty") or 0),
            price_hint=intent.price_hint,
        )

    # Determine if there is an opposite position
    if current_position:
        pos_dir = str(current_position.get("direction") or current_position.get("side") or "").lower()
        # normalize: accept many forms
        is_long = pos_dir in ("1", "buy", "long")
        is_short = pos_dir in ("2", "sell", "short")
        if (side == "long" and is_short) or (side == "short" and is_long):
            exchange.close_position(
                position_id=int(current_position["id"]),
                qty=float(current_position.get("volume") or current_position.get("qty") or 0),
                price_hint=intent.price_hint,
            )

    # Entry logic
    if side == "long":
        return exchange.market_buy(
            symbol=intent.symbol,
            qty=intent.qty,
            leverage=intent.leverage,
            price_hint=intent.price_hint,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
        )

    if side == "short":
        return exchange.market_sell(
            symbol=intent.symbol,
            qty=intent.qty,
            leverage=intent.leverage,
            price_hint=intent.price_hint,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
        )

    return {"status": "invalid_intent", "side": intent.side}
