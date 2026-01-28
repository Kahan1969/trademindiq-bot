from typing import List
from core.models import Trade, OrderResult, Signal
from datetime import date


class RiskManager:
    def __init__(self):
        self.daily_loss_cap = 25.0
        self.max_open_positions = 2
        self._daily_pnl = 0.0
        self._day = date.today()

    def configure(self, max_open_positions: int, daily_loss_cap: float):
        self.max_open_positions = int(max_open_positions)
        self.daily_loss_cap = float(daily_loss_cap)

    def register_open(self, symbol: str = None):
        # optional hook for bookkeeping; not required for can_open_new_trade which uses passed open_positions
        return

    def register_close(self, pnl: float):
        # reset daily if day changed
        if date.today() != self._day:
            self._day = date.today()
            self._daily_pnl = 0.0
        try:
            self._daily_pnl += float(pnl)
        except Exception:
            pass

    def can_open_new_trade(self, open_positions: int = 0):
        # ensure daily reset
        if date.today() != self._day:
            self._day = date.today()
            self._daily_pnl = 0.0

        if int(open_positions) >= int(self.max_open_positions):
            return (False, "max open positions reached")
        if self._daily_pnl <= -abs(self.daily_loss_cap):
            return (False, "daily loss cap hit")
        return (True, "")

    def apply_trailing_stop(self, signal: Signal, last_price: float) -> float:
        # simple example: trail stop to EMA or to last swing – you can paste old logic here
        return signal.stop

    def compute_pnl(self, order: OrderResult, exit_price: float) -> float:
        direction = 1 if order.signal.side.value == "BUY" else -1
        return (exit_price - order.filled_price) * order.signal.qty * direction
