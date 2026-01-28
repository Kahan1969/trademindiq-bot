from core.models import Signal, OrderResult, Mode

# support helper for sync/async exchange wrappers
import asyncio
import inspect

async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class ExecutionEngine:
    def __init__(self, exchange, mode: Mode):
        self.exchange = exchange
        self.mode = mode
        # requires explicit arming before allowing LIVE orders
        self.live_armed = False

    def arm_live(self, armed: bool) -> None:
        self.live_armed = bool(armed)

    async def execute_signal(self, signal: Signal) -> OrderResult:
        if self.mode == Mode.LIVE:
            # require explicit arm for live trading
            if not getattr(self, "live_armed", False):
                raise RuntimeError("LIVE trading is not armed. Send CONFIRM LIVE in Telegram.")

            # place entry order
            entry_order = await _maybe_await(self.exchange.create_order(signal.symbol, "market", "buy", signal.qty))
            filled_price = float(entry_order.get("average") or entry_order.get("price") or signal.entry)
            status = entry_order.get("status", "submitted")
            order_id = str(entry_order.get("id", ""))

            # place bracket exits (TP + SL) and capture exit orders
            exits = []
            try:
                exits = await self._place_bracket_exits(signal.symbol, signal.qty, float(signal.stop), float(signal.target))
            except Exception:
                exits = []

            res = OrderResult(
                signal=signal,
                order_id=order_id,
                mode=self.mode,
                filled_price=float(filled_price or signal.entry),
                status=str(status),
            )
            # attach optional fields dynamically to remain compatible with different OrderResult signatures
            try:
                setattr(res, "qty", float(signal.qty))
                setattr(res, "stop", float(signal.stop))
                setattr(res, "target", float(signal.target))
                setattr(res, "meta", {"entry_order": entry_order, "exit_orders": exits})
            except Exception:
                pass
            return res

        else:
            filled = signal.entry
            status = "filled"
            order_id = f"PAPER-{signal.symbol}-{int(signal.created_at.timestamp())}"

            res = OrderResult(
                signal=signal,
                order_id=order_id,
                mode=self.mode,
                filled_price=filled,
                status=status,
            )
            try:
                setattr(res, "qty", signal.qty)
                setattr(res, "stop", signal.stop)
                setattr(res, "target", signal.target)
            except Exception:
                pass
            return res

    async def _place_bracket_exits(self, symbol, qty, stop, limit_price):
        exits: list[dict] = []

        # 1) Take profit: LIMIT sell
        try:
            tp = await _maybe_await(self.exchange.create_order(symbol, "limit", "sell", qty, limit_price))
            exits.append(tp or {})
        except Exception as e:
            exits.append({"warning": f"tp_failed: {e}"})

        # 2) Stop loss: KuCoin Spot stop-market sell via params
        stop_placed = False
        stop_param_candidates = [
            {"stop": "loss", "stopPrice": stop},      # common KuCoin pattern
            {"stopPrice": stop},                          # fallback
            {"stop": "loss", "triggerPrice": stop},   # some wrappers
        ]

        for params in stop_param_candidates:
            try:
                sl = await _maybe_await(self.exchange.create_order(symbol, "market", "sell", qty, None, dict(params)))
                exits.append(sl or {})
                stop_placed = True
                break
            except Exception:
                continue

        if not stop_placed:
            # stop-limit fallback (less ideal)
            try:
                params = {"stop": "loss", "stopPrice": stop}
                sl = await _maybe_await(self.exchange.create_order(symbol, "limit", "sell", qty, stop, params))
                exits.append(sl or {})
                stop_placed = True
            except Exception as e:
                exits.append({"warning": f"sl_failed: {e}"})

        if not stop_placed:
            # Safety fallback: rely on PortfolioService PRICE_TICK to close by market
            exits.append({"warning": "stop_order_not_supported; relying_on_monitor_close"})

        return exits

