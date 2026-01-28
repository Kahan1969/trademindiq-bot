# core/pnl.py
from __future__ import annotations

def calc_pnl_usd(side: str, entry: float, exit_: float, qty: float) -> float:
    side = side.lower()
    if side in ("buy", "long"):
        return (exit_ - entry) * qty
    if side in ("sell", "short"):
        return (entry - exit_) * qty
    raise ValueError(f"Unknown side: {side}")
