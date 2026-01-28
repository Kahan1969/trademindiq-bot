import csv
import os
from datetime import datetime

class SignalCsvExporter:
    def __init__(self, filepath: str = "signals_export.csv"):
        self.filepath = filepath
        self._ensure_header()

    def _ensure_header(self):
        if os.path.exists(self.filepath):
            return
        with open(self.filepath, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "created_at", "symbol", "side", "entry", "stop", "target", "qty", "rel_vol", "gap_pct"
            ])

    def write_signal(self, signal):
        with open(self.filepath, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                getattr(signal, "created_at", datetime.utcnow()).isoformat(),
                getattr(signal, "symbol", ""),
                getattr(signal, "side", ""),
                f"{getattr(signal, 'entry', 0.0):.6f}",
                f"{getattr(signal, 'stop', 0.0):.6f}",
                f"{getattr(signal, 'target', 0.0):.6f}",
                f"{getattr(signal, 'qty', 0.0):.6f}",
                f"{getattr(signal, 'rel_vol', 0.0):.2f}",
                f"{getattr(signal, 'gap_pct', 0.0):.2f}",
            ])