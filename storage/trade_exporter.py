import csv
import os
from datetime import datetime

class TradeCsvExporter:
    def __init__(self, filepath: str = "trades_export.csv"):
        self.filepath = filepath
        self._ensure_header()

    def _ensure_header(self):
        if os.path.exists(self.filepath):
            return
        with open(self.filepath, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "closed_at",
                "symbol",
                "mode",
                "side",
                "entry",
                "stop",
                "target",
                "exit_price",
                "qty",
                "pnl",
                "exit_reason",
                "rel_vol",
                "gap_pct",
                "ai_conf",
                "ai_comment",
            ])

    def write_trade(self, trade, indicators=None):
        s = trade.signal
        indicators = indicators or {}
        ai_conf = indicators.get("_ai_conf", "")
        ai_comment = indicators.get("_ai_comment", "")

        with open(self.filepath, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                getattr(trade, "closed_at", datetime.utcnow()).isoformat(),
                getattr(s, "symbol", ""),
                getattr(trade.order, "mode", ""),
                getattr(s, "side", ""),
                f"{getattr(s, 'entry', 0.0):.6f}",
                f"{getattr(s, 'stop', 0.0):.6f}",
                f"{getattr(s, 'target', 0.0):.6f}",
                f"{getattr(trade, 'exit_price', 0.0):.6f}",
                f"{getattr(s, 'qty', 0.0):.6f}",
                f"{getattr(trade, 'realized_pnl', getattr(trade, 'pnl', 0.0)):.2f}",
                getattr(trade, "exit_reason", ""),
                f"{getattr(s, 'rel_vol', 0.0):.2f}",
                f"{getattr(s, 'gap_pct', 0.0):.2f}",
                ai_conf,
                ai_comment,
            ])
