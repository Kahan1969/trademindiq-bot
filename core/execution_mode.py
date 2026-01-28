from __future__ import annotations

from typing import Any, Dict


class DryRunMixin:
    """Reusable helper to standardize paper/live execution behavior.

    Convention:
      trading:
        mode: paper | live

    Any mode other than "live" is treated as dry-run.
    """

    cfg: Dict[str, Any]

    def _is_dry_run(self) -> bool:
        mode = (self.cfg.get("trading", {}) or {}).get("mode", "paper")
        return str(mode).strip().lower() != "live"

    def _dry_run_payload(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "dry_run": True,
            "action": action,
            "payload": payload,
        }
