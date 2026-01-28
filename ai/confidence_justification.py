# ai/confidence_justification.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional

from ai.post_trade_schema import PostTradeContext


@dataclass
class ConfidenceBreakdown:
    score: int
    reasons: List[str] = field(default_factory=list)
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "reasons": self.reasons, "components": self.components}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_confidence(ctx: PostTradeContext) -> ConfidenceBreakdown:
    """
    Produces:
      - a 0-100 score
      - human-readable justification
      - component scores (0-1 each)
    Deterministic and explainable.
    """

    components: Dict[str, float] = {}
    reasons: List[str] = []

    # Setup quality components
    if ctx.body_pct is None:
        body = 0.5
        reasons.append("Body strength unavailable; defaulted to neutral.")
    else:
        body = _clamp((ctx.body_pct - 0.40) / (0.70 - 0.40))
        reasons.append(f"Body strength contributed {body:.2f} based on body_pct={ctx.body_pct:.2f}.")
    components["body_strength"] = body

    if ctx.upper_wick_pct is None:
        wick = 0.5
        reasons.append("Upper wick unavailable; defaulted to neutral.")
    else:
        wick = _clamp((0.45 - ctx.upper_wick_pct) / (0.45 - 0.15))
        reasons.append(f"Wick quality contributed {wick:.2f} based on upper_wick_pct={ctx.upper_wick_pct:.2f}.")
    components["wick_quality"] = wick

    if ctx.vol_spike is None:
        vol = 0.5
        reasons.append("Volume spike unavailable; defaulted to neutral.")
    else:
        vol = _clamp((ctx.vol_spike - 1.0) / (3.0 - 1.0))
        reasons.append(f"Volume expansion contributed {vol:.2f} based on vol_spike={ctx.vol_spike:.2f}x.")
    components["volume_expansion"] = vol

    # Orderflow components (only if enabled)
    if ctx.orderflow_enabled:
        if ctx.bid_ask_ratio is None:
            book = 0.5
            reasons.append("Order book ratio unavailable; defaulted to neutral.")
        else:
            book = _clamp((ctx.bid_ask_ratio - 1.0) / (2.0 - 1.0))
            reasons.append(f"Order book contributed {book:.2f} based on bid_ask_ratio={ctx.bid_ask_ratio:.2f}.")
        components["orderbook"] = book

        if ctx.buy_sell_ratio is None:
            tape = 0.5
            reasons.append("Tape ratio unavailable; defaulted to neutral.")
        else:
            tape = _clamp((ctx.buy_sell_ratio - 1.0) / (2.0 - 1.0))
            reasons.append(f"Tape contributed {tape:.2f} based on buy_sell_ratio={ctx.buy_sell_ratio:.2f}.")
        components["tape"] = tape
    else:
        components["orderbook"] = 0.5
        components["tape"] = 0.5
        reasons.append("Orderflow disabled; orderflow components set to neutral.")

    # Exit quality / follow-through
    exit_quality_map = {
        "TARGET": 1.0,
        "TRAIL": 0.75,
        "TIME": 0.45,
        "STOP": 0.10,
        "MANUAL": 0.50,
        "LIQUIDATION": 0.0,
        "ERROR": 0.0,
        "UNKNOWN": 0.50,
    }
    exit_q = exit_quality_map.get(ctx.exit_reason, 0.5)
    components["exit_quality"] = exit_q
    reasons.append(f"Exit quality contributed {exit_q:.2f} based on exit_reason={ctx.exit_reason}.")

    # Execution penalties
    exec_penalty = 0.0
    if ctx.rejections > 0:
        exec_penalty += min(0.25, 0.08 * ctx.rejections)
        reasons.append(f"Execution penalty applied for rejections={ctx.rejections}.")
    if ctx.slippage_bps is not None and ctx.slippage_bps > 10:
        exec_penalty += min(0.25, (ctx.slippage_bps - 10) / 100)
        reasons.append(f"Execution penalty applied for slippage_bps={ctx.slippage_bps:.1f}.")
    if ctx.data_quality != "ok":
        exec_penalty += 0.15
        reasons.append(f"Execution penalty applied for data_quality={ctx.data_quality}.")
    components["execution_penalty"] = _clamp(exec_penalty, 0.0, 1.0)

    # Weighted score
    weights = {
        "body_strength": 0.18,
        "wick_quality": 0.12,
        "volume_expansion": 0.18,
        "orderbook": 0.14,
        "tape": 0.14,
        "exit_quality": 0.24,
    }
    base = sum(components[k] * w for k, w in weights.items())
    base = _clamp(base, 0.0, 1.0)

    score = int(round(base * 100))
    score = int(round((score - (components["execution_penalty"] * 100 * 0.35))))
    score = max(0, min(100, score))

    # Short “top reasons” summary
    top_reasons = [
        f"Setup: body={components['body_strength']:.2f}, wick={components['wick_quality']:.2f}, vol={components['volume_expansion']:.2f}",
        f"Orderflow: book={components['orderbook']:.2f}, tape={components['tape']:.2f}",
        f"Exit: {components['exit_quality']:.2f}",
    ]
    reasons = top_reasons + reasons

    return ConfidenceBreakdown(score=score, reasons=reasons, components=components)
