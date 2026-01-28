# ai/advisor.py
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


class AIAdvisor:
    """
    Provides:
      - review(signal, indicators, context) -> (approved, comment)  [pre-trade gate]
      - review_closed_trade(trade, context) -> dict                [post-trade review]
      - suggest_parameter_changes(trade_review, current_params) -> dict
    """

    def __init__(self, db_path: str, telegram: Any, openai_api_key: Optional[str] = None) -> None:
        self.db_path = db_path
        self.telegram = telegram
        self.openai_api_key = openai_api_key

    # -------------------------
    # Pre-trade AI gate
    # -------------------------
    def review(self, signal: Any, indicators: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Returns:
          approved: bool
          comment: str (include confidence score)
        """
        # Basic heuristic confidence (works even without LLM)
        conf = self._heuristic_confidence(signal, indicators)
        confidence_pct = int(conf * 100)

        # If no LLM key, fallback to heuristic text
        if not self.openai_api_key:
            approved = confidence_pct >= 55
            comment = (
                f"Confidence: {confidence_pct}/100\n"
                f"Reason: EMA stack + breakout + relvol checks. "
                f"{'Approved' if approved else 'Skipped'} by heuristic threshold."
            )
            return approved, comment

        # With LLM: provide structured prompt (still safe if LLM fails)
        prompt = self._build_signal_prompt(signal, indicators, context, confidence_pct)
        out = self._llm(prompt)
        if not out:
            approved = confidence_pct >= 55
            comment = f"Confidence: {confidence_pct}/100\nLLM unavailable. Using heuristic gate."
            return approved, comment

        # Expect JSON-like response
        parsed = self._safe_json(out)
        approved = bool(parsed.get("approved", confidence_pct >= 55))
        comment = parsed.get("comment") or f"Confidence: {confidence_pct}/100\nNo comment."
        # Ensure confidence is in the comment
        if "Confidence" not in comment:
            comment = f"Confidence: {confidence_pct}/100\n" + comment
        return approved, comment

    # -------------------------
    # Post-trade review
    # -------------------------
    def review_closed_trade(self, trade: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Returns dict:
          {
            "symbol": "...",
            "result": "WIN/LOSS/UNKNOWN",
            "pnl": float,
            "confidence": int (0-100),
            "what_worked": "...",
            "what_failed": "...",
            "next_time": "...",
            "tags": ["..."]
          }
        """
        context = context or {}
        symbol = getattr(trade, "symbol", "UNKNOWN")
        pnl = float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0)
        result = getattr(trade, "result", None)
        if not result:
            result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "UNKNOWN"
        else:
            result = str(result).upper()

        # Without LLM: simple deterministic review
        if not self.openai_api_key:
            confidence = 60 if result == "WIN" else 45 if result == "LOSS" else 50
            return {
                "symbol": symbol,
                "result": result,
                "pnl": pnl,
                "confidence": confidence,
                "what_worked": "Trend alignment and breakout logic." if result == "WIN" else "Entry was valid but follow-through failed.",
                "what_failed": "Minimal issues noted." if result == "WIN" else "Possible false breakout or insufficient momentum/volume.",
                "next_time": "Consider stricter breakout or higher relvol threshold on choppy conditions." if result == "LOSS" else "Continue; keep risk controlled.",
                "tags": ["post_trade_review", "heuristic"],
            }

        # LLM review
        prompt = self._build_trade_review_prompt(trade, context)
        out = self._llm(prompt)
        parsed = self._safe_json(out) if out else {}

        # Normalize output
        confidence = parsed.get("confidence")
        try:
            confidence = int(confidence)
        except Exception:
            confidence = 55 if result == "WIN" else 45

        review = {
            "symbol": parsed.get("symbol", symbol),
            "result": parsed.get("result", result),
            "pnl": float(parsed.get("pnl", pnl)),
            "confidence": max(0, min(100, confidence)),
            "what_worked": parsed.get("what_worked", ""),
            "what_failed": parsed.get("what_failed", ""),
            "next_time": parsed.get("next_time", ""),
            "tags": parsed.get("tags", ["post_trade_review"]),
        }

        # ---- normalize review payload (never blank sections) ----
        try:
            if not isinstance(review, dict):
                review = {"raw": review}

            # Deterministic confidence (if not already present)
            if "confidence_score" not in review or "confidence_reasons" not in review:
                try:
                    from ai.post_trade_schema import PostTradeContext
                    from ai.confidence_justification import compute_confidence

                    cfg = (context or {}).get("params", {}) if isinstance(context, dict) else {}
                    cfg = cfg or {}
                    of_cfg = cfg.get("orderflow", {}) or {}
                    dry_run = str((cfg.get("trading", {}) or {}).get("mode", "paper")).strip().lower() != "live"

                    sig = getattr(trade, "signal", None)
                    snap = (getattr(trade, "meta", {}) or {}).get("signal_snapshot", {}) or {}

                    entry_price = float(getattr(getattr(trade, "order", None), "filled_price", getattr(sig, "entry", 0.0)) or 0.0)
                    exit_price = float(getattr(trade, "exit_price", 0.0) or 0.0)
                    qty = float(getattr(getattr(trade, "order", None), "qty", getattr(sig, "qty", 0.0)) or 0.0)

                    ctx = PostTradeContext(
                        symbol=getattr(trade, "symbol", getattr(sig, "symbol", "")) or "",
                        exchange=getattr(sig, "exchange", "") or "",
                        market_type="futures" if isinstance(cfg.get("exchange"), dict) else "spot",
                        timeframe=getattr(sig, "timeframe", cfg.get("timeframe", "")) or "",
                        side="long",
                        strategy_name="momentum",
                        entry_ts=int(getattr(trade, "opened_at", getattr(trade, "entry_ts", 0)) or 0),
                        exit_ts=int(getattr(trade, "closed_at", getattr(trade, "exit_ts", 0)) or 0),
                        hold_seconds=int(getattr(trade, "hold_seconds", 0) or 0),
                        entry_price=entry_price,
                        exit_price=exit_price,
                        qty=qty,
                        notional_usd=float(entry_price * qty) if entry_price and qty else 0.0,
                        pnl_usd=float(getattr(trade, "pnl", getattr(trade, "realized_pnl", 0.0)) or 0.0),
                        pnl_r=float(getattr(trade, "pnl_r", 0.0) or 0.0),
                        fees_usd=float(getattr(trade, "fees_usd", 0.0) or 0.0),
                        slippage_bps=getattr(trade, "slippage_bps", None),
                        risk_per_trade=float(cfg.get("risk_per_trade", 0.0) or 0.0),
                        planned_stop_price=float(getattr(sig, "stop", 0.0) or 0.0) or None,
                        planned_target_price=float(getattr(sig, "target", 0.0) or 0.0) or None,
                        atr_value=snap.get("atr"),
                        stop_distance_atr=None,
                        breakout_lookback=int(cfg.get("breakout_lookback", 12) or 12),
                        breakout_level=snap.get("breakout_level"),
                        breakout_close_above=snap.get("breakout_close_above"),
                        body_pct=snap.get("body_pct"),
                        upper_wick_pct=snap.get("upper_wick_pct"),
                        vol_spike=snap.get("vol_spike"),
                        gap_pct=snap.get("gap_pct"),
                        ema_alignment=snap.get("ema_alignment"),
                        orderflow_enabled=bool(of_cfg.get("enabled", False)),
                        book_depth=int(of_cfg.get("book_depth", 0) or 0),
                        bid_ask_ratio=snap.get("bid_ask_ratio"),
                        buy_sell_ratio=snap.get("buy_sell_ratio"),
                        tape_trades=int(of_cfg.get("tape_trades", 0) or 0),
                        spread_bps=snap.get("spread_bps"),
                        exit_reason=str(getattr(trade, "exit_reason", "UNKNOWN") or "UNKNOWN"),
                        max_favorable_excursion_r=snap.get("mfe_r"),
                        max_adverse_excursion_r=snap.get("mae_r"),
                        rejections=int(snap.get("rejections", 0) or 0),
                        dry_run=bool(dry_run),
                        indicators=(snap.get("indicators") or {}),
                        data_quality="ok",
                    )
                    conf = compute_confidence(ctx)
                    review["confidence_score"] = int(conf.score)
                    review["confidence_reasons"] = list(conf.reasons or [])
                except Exception:
                    review.setdefault("confidence_score", int(review.get("confidence", 50) or 50))
                    review.setdefault("confidence_reasons", [])

            def _as_list(v):
                if v is None:
                    return []
                if isinstance(v, list):
                    return [str(x).strip() for x in v if str(x).strip()]
                s = str(v).strip()
                return [s] if s else []

            ww = _as_list(review.get("what_worked"))
            wf = _as_list(review.get("what_failed"))
            nt = _as_list(review.get("next_time"))

            if not ww:
                ww = ["No qualifying positives detected by rules."]
            if not wf:
                wf = ["No specific failure conditions detected by rules."]
            if not nt:
                nt = ["No actionable improvements suggested by rules."]

            review["what_worked"] = ww
            review["what_failed"] = wf
            review["next_time"] = nt

            # Back-compat for callers still reading scalar confidence
            review["confidence"] = int(review.get("confidence_score", review.get("confidence", 50)) or 50)
        except Exception:
            pass

        return review

    # -------------------------
    # Parameter suggestions
    # -------------------------
    def suggest_parameter_changes(self, trade_review: Dict[str, Any], current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns:
          {
            "apply": bool,
            "reason": "...",
            "changes": { "min_rel_vol": 2.2, "min_gap_pct": 0.4, ... }
          }
        """
        # Simple heuristic suggestions if no LLM
        if not self.openai_api_key:
            changes: Dict[str, Any] = {}
            reason = "Heuristic tuning."

            if trade_review.get("result") == "LOSS":
                # tighten slightly after loss
                if "min_rel_vol" in current_params:
                    changes["min_rel_vol"] = float(current_params["min_rel_vol"]) * 1.05
                if "min_gap_pct" in current_params:
                    changes["min_gap_pct"] = float(current_params["min_gap_pct"]) * 1.05
                reason = "Loss detected: tightening relvol/gap thresholds by 5% to reduce noise."
                return {"apply": True, "reason": reason, "changes": changes}

            # For wins: optionally loosen slightly or keep steady
            return {"apply": False, "reason": "Win/neutral: no change recommended.", "changes": {}}

        prompt = self._build_param_prompt(trade_review, current_params)
        out = self._llm(prompt)
        parsed = self._safe_json(out) if out else {}
        apply = bool(parsed.get("apply", False))
        changes = parsed.get("changes", {}) if isinstance(parsed.get("changes", {}), dict) else {}
        reason = parsed.get("reason", "No reason provided.")
        return {"apply": apply, "reason": reason, "changes": changes}

    # -------------------------
    # Helpers
    # -------------------------
    def _heuristic_confidence(self, signal: Any, indicators: Dict[str, Any]) -> float:
        """
        Returns 0..1 confidence based on relvol, gap, ema alignment, breakout distance.
        """
        try:
            rel_vol = float(getattr(signal, "rel_vol", indicators.get("rel_vol", 0.0)) or 0.0)
            gap = float(getattr(signal, "gap_pct", indicators.get("gap_pct", 0.0)) or 0.0)
            close = float(indicators["close"][-1])
            ema9 = float(indicators["ema9"][-1])
            ema20 = float(indicators["ema20"][-1])
            ema50 = float(indicators["ema50"][-1])
            brk = float(indicators.get("breakout_level", close))

            score = 0.0
            score += min(1.0, rel_vol / 3.0) * 0.35
            score += min(1.0, max(0.0, gap) / 1.0) * 0.15
            score += (1.0 if (close > ema9 > ema20 > ema50) else 0.5) * 0.30
            score += (1.0 if close > brk else 0.4) * 0.20
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.50

    def _build_signal_prompt(self, signal: Any, indicators: Dict[str, Any], context: Dict[str, Any], confidence_pct: int) -> str:
        return f"""
You are a trading assistant for a momentum strategy. Return ONLY valid JSON with keys:
approved (bool), comment (string). Include Confidence: {confidence_pct}/100 in the comment.

Signal:
symbol={getattr(signal,'symbol','')}
exchange={getattr(signal,'exchange','')}
timeframe={getattr(signal,'timeframe','')}
entry={getattr(signal,'entry',0)}
stop={getattr(signal,'stop',0)}
target={getattr(signal,'target',0)}
qty={getattr(signal,'qty',0)}
rel_vol={getattr(signal,'rel_vol',0)}
gap_pct={getattr(signal,'gap_pct',0)}

Indicators snapshot:
ema9_last={float(indicators.get('ema9', [0])[-1]) if indicators.get('ema9') is not None else 0}
ema20_last={float(indicators.get('ema20', [0])[-1]) if indicators.get('ema20') is not None else 0}
ema50_last={float(indicators.get('ema50', [0])[-1]) if indicators.get('ema50') is not None else 0}
atr14_last={float(indicators.get('atr14', [0])[-1]) if indicators.get('atr14') is not None else 0}
breakout_level={float(indicators.get('breakout_level',0))}

Context:
{json.dumps(context, default=str)[:2000]}
""".strip()

    def _build_trade_review_prompt(self, trade: Any, context: Dict[str, Any]) -> str:
        return f"""
You are a trading coach. Return ONLY valid JSON with keys:
symbol, result, pnl, confidence (0-100), what_worked, what_failed, next_time, tags (array of strings).

Trade:
symbol={getattr(trade,'symbol','')}
side={getattr(trade,'side','')}
entry={getattr(trade,'entry', getattr(trade,'entry_price',0))}
exit={getattr(trade,'exit', getattr(trade,'exit_price',0))}
pnl={getattr(trade,'realized_pnl', getattr(trade,'pnl',0))}
result={getattr(trade,'result','')}

Context:
{json.dumps(context, default=str)[:2000]}
""".strip()

    def _build_param_prompt(self, trade_review: Dict[str, Any], current_params: Dict[str, Any]) -> str:
        return f"""
Return ONLY valid JSON with keys:
apply (bool), reason (string), changes (object of param->value).

TradeReview:
{json.dumps(trade_review, default=str)}

CurrentParams:
{json.dumps(current_params, default=str)}

Goal:
If losses are due to chop/false breakouts, tighten filters slightly.
If missing moves due to over-filtering, loosen slightly.
""".strip()

    def _safe_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            # attempt to extract json block
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    return {}
            return {}

    def _llm(self, prompt: str) -> Optional[str]:
        """
        Plug your OpenAI call here if you already have one.
        For safety, we return None if not implemented.
        """
        # If you already have an OpenAI client elsewhere, replace this.
        # Keep it fail-safe: never raise.
        return None
