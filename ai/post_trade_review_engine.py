# ai/post_trade_review_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ai.post_trade_schema import PostTradeContext
from ai.post_trade_rules import generate_rule_notes
from ai.confidence_justification import compute_confidence


@dataclass
class PostTradeReview:
    confidence_score: int
    confidence_reasons: list[str]
    what_worked: list[str]
    what_failed: list[str]
    next_time: list[str]
    tags: list[str]
    llm_supplement: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "confidence_reasons": self.confidence_reasons,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "next_time": self.next_time,
            "tags": self.tags,
            "llm_supplement": self.llm_supplement,
        }


def generate_post_trade_review(ctx: PostTradeContext, llm_client: Optional[Any] = None) -> PostTradeReview:
    # 1) Deterministic notes
    notes = generate_rule_notes(ctx)

    # 2) Deterministic confidence + justification
    conf = compute_confidence(ctx)

    review = PostTradeReview(
        confidence_score=conf.score,
        confidence_reasons=conf.reasons[:6],  # keep message short; store full in DB if desired
        what_worked=notes.what_worked,
        what_failed=notes.what_failed,
        next_time=notes.next_time,
        tags=notes.tags,
        llm_supplement=None,
    )

    # 3) Optional LLM enhancement (future)
    #    This is intentionally a no-op unless you pass an llm_client.
    if llm_client is not None:
        # Provide a stable prompt contract. LLM returns only JSON. (Implement later.)
        prompt_payload = {
            "context": ctx.to_dict(),
            "rule_review": review.to_dict(),
            "instructions": "Return JSON with keys: summary, pattern, improvement, risk_note. Keep it concise.",
        }
        try:
            llm_json = llm_client.generate_json(prompt_payload)  # your future adapter
            review.llm_supplement = llm_json
        except Exception:
            review.llm_supplement = {"error": "LLM supplement failed"}

    return review
