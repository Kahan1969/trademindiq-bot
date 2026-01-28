# ai/signal_advisor.py

from typing import Tuple, Dict, Any, Optional
from core.models import Signal


class AISignalAdvisor:
    """
    Lightweight AI-style filter for signals.

    If openai_api_key is provided, you can wire real GPT calls later.
    For now, it uses deterministic rules and attaches an 'ai_comment'.
    """

    def __init__(self, openai_api_key: Optional[str] = None, gatekeep: bool = False):
        self.openai_api_key = openai_api_key
        self.gatekeep = gatekeep

    def review(
        self,
        signal: Signal,
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Returns (approved, comment)
        """
        comment_parts = []

        r = (signal.target - signal.entry) / (signal.entry - signal.stop)
        if r < 1.3:
            comment_parts.append(f"Low R/R ({r:.2f}).")

        if signal.rel_vol < 2.0:
            comment_parts.append(f"RelVol {signal.rel_vol:.2f} is low for momentum.")

        gap = signal.gap_pct if hasattr(signal, "gap_pct") else context.get("gap_pct", 0)
        if gap < 0.3:
            comment_parts.append(f"Gap {gap:.2f}% is small.")

        approved = True
        if self.gatekeep and comment_parts:
            approved = False

        if not comment_parts:
            comment = "AI check: setup looks reasonable."
        else:
            comment = "AI check flags: " + " ".join(comment_parts)

        return approved, comment
