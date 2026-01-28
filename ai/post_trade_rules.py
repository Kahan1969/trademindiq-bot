# ai/post_trade_rules.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

from ai.post_trade_schema import PostTradeContext


@dataclass
class ReviewNotes:
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    next_time: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "next_time": self.next_time,
            "tags": self.tags,
        }


def _fmt_ratio(label: str, val: float, good: bool) -> str:
    direction = "strong" if good else "weak"
    return f"{label} was {direction} ({val:.2f})."


def generate_rule_notes(ctx: PostTradeContext) -> ReviewNotes:
    n = ReviewNotes()

    # --- Setup quality ---
    if ctx.breakout_close_above is True:
        n.what_worked.append("Breakout confirmed (close above level).")
    elif ctx.breakout_close_above is False:
        n.what_failed.append("Breakout was not confirmed by close above level.")

    if ctx.body_pct is not None:
        if ctx.body_pct >= 0.55:
            n.what_worked.append(f"Candle body strength met threshold (body {ctx.body_pct:.2f}).")
        else:
            n.what_failed.append(f"Weak body (body {ctx.body_pct:.2f}) reduced momentum quality.")
            n.next_time.append("Require stronger candle body before entry or reduce size.")

    if ctx.upper_wick_pct is not None:
        if ctx.upper_wick_pct <= 0.35:
            n.what_worked.append(f"Upper wick within limits (wick {ctx.upper_wick_pct:.2f}).")
        else:
            n.what_failed.append(f"Upper wick too large (wick {ctx.upper_wick_pct:.2f}) signaling supply.")
            n.next_time.append("Avoid entries with heavy upper wicks; wait for a clean re-break.")

    if ctx.vol_spike is not None:
        if ctx.vol_spike >= 1.8:
            n.what_worked.append(f"Volume expansion confirmed (spike {ctx.vol_spike:.2f}x).")
        else:
            n.what_failed.append(f"Insufficient volume expansion (spike {ctx.vol_spike:.2f}x).")
            n.next_time.append("Prioritize high volume spikes; rotate to top movers if volume is muted.")

    # --- Orderflow gates ---
    if ctx.orderflow_enabled:
        if ctx.bid_ask_ratio is not None:
            if ctx.bid_ask_ratio >= 1.25:
                n.what_worked.append(_fmt_ratio("Bid/ask depth ratio", ctx.bid_ask_ratio, True))
            else:
                n.what_failed.append(_fmt_ratio("Bid/ask depth ratio", ctx.bid_ask_ratio, False))
                n.next_time.append("Require stronger book imbalance or reduce size when ratio is marginal.")

        if ctx.buy_sell_ratio is not None:
            if ctx.buy_sell_ratio >= 1.15:
                n.what_worked.append(_fmt_ratio("Tape buy/sell ratio", ctx.buy_sell_ratio, True))
            else:
                n.what_failed.append(_fmt_ratio("Tape buy/sell ratio", ctx.buy_sell_ratio, False))
                n.next_time.append("Wait for tape confirmation (buy pressure) before entry.")

        if ctx.spread_bps is not None and ctx.spread_bps > 8:
            n.what_failed.append(f"Spread was elevated ({ctx.spread_bps:.1f} bps) increasing slippage risk.")
            n.next_time.append("Avoid wide-spread conditions or use limit orders for entry.")

    # --- Trade management & exit ---
    if ctx.exit_reason == "TARGET":
        n.what_worked.append("Exit hit target as planned.")
        n.tags.append("clean_target")
    elif ctx.exit_reason == "STOP":
        n.what_failed.append("Exit hit stop; momentum thesis invalidated.")
        n.next_time.append("Tighten entry filters or wait for confirmation re-test before re-entry.")
        n.tags.append("stopped")
    elif ctx.exit_reason == "TIME":
        n.what_failed.append("Time-based exit suggests momentum stalled.")
        n.next_time.append("Consider faster partials or skip setups lacking follow-through.")
        n.tags.append("time_exit")
    elif ctx.exit_reason == "TRAIL":
        n.what_worked.append("Trailing exit protected profits / reduced give-back.")
        n.tags.append("trail_exit")

    # --- R multiple diagnostics ---
    if ctx.pnl_r >= 0.5:
        n.what_worked.append(f"Trade delivered positive R (R={ctx.pnl_r:.2f}).")
    elif ctx.pnl_r < 0:
        n.what_failed.append(f"Trade delivered negative R (R={ctx.pnl_r:.2f}).")

    if ctx.max_favorable_excursion_r is not None and ctx.pnl_r is not None:
        if ctx.max_favorable_excursion_r >= 1.0 and ctx.pnl_r < 0.3:
            n.what_failed.append("Significant MFE but profits not captured (give-back).")
            n.next_time.append("Add partial take-profits or tighten trail after strong extension.")

    # --- Execution issues ---
    if ctx.rejections > 0:
        n.what_failed.append(f"Order rejections occurred ({ctx.rejections}).")
        n.next_time.append("Review order type/params and exchange limits; add retries/backoff.")
        n.tags.append("execution_issue")

    if ctx.slippage_bps is not None and ctx.slippage_bps > 10:
        n.what_failed.append(f"Slippage was high ({ctx.slippage_bps:.1f} bps).")
        n.next_time.append("Consider limit entries or avoid thin books during spikes.")
        n.tags.append("slippage")

    if ctx.data_quality != "ok":
        n.what_failed.app_
