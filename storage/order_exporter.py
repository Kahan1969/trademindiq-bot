import csv
import os
from datetime import datetime

class OrderCsvExporter:
    def __init__(self, filepath: str = "orders_export.csv"):
        self.filepath = filepath
        self._ensure_header()

    def _ensure_header(self):
        if os.path.exists(self.filepath):
            return
        with open(self.filepath, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "created_at", "order_id", "symbol", "side", "entry", "stop", "target", "qty", "status"
            ])

    def write_order(self, order):
        s = getattr(order, "signal", None)
        with open(self.filepath, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                getattr(s, "created_at", datetime.utcnow()).isoformat() if s else "",
                getattr(order, "order_id", ""),
                getattr(s, "symbol", "") if s else "",
                getattr(s, "side", "") if s else "",
                f"{getattr(s, 'entry', 0.0):.6f}" if s else "",
                f"{getattr(s, 'stop', 0.0):.6f}" if s else "",
                f"{getattr(s, 'target', 0.0):.6f}" if s else "",
                f"{getattr(s, 'qty', 0.0):.6f}" if s else "",
                getattr(order, "status", ""),
            ])