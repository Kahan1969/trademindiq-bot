from datetime import datetime, timedelta

class Heartbeat:
    def __init__(self, tg, cfg):
        self.tg = tg
        self.enabled = bool(cfg.get("telegram", {}).get("heartbeat", {}).get("enabled", True))
        self.interval = int(cfg.get("telegram", {}).get("heartbeat", {}).get("interval_minutes", 10)) * 60
        self.last_sent = 0
        self.started_at = datetime.utcnow()

        self.scans = 0
        self.trades = 0

    def on_startup(self, symbols: int, mode: str):
        if not self.enabled:
            return

        msg = f"🚀 TradeMindIQ started ({mode}) – scanning {symbols} symbols"
        self.tg._send_text(msg)

    def on_scan(self):
        self.scans += 1
        self._maybe_send()

    def on_trade(self):
        self.trades += 1

    def _maybe_send(self):
        if not self.enabled:
            return

        now = datetime.utcnow().timestamp()
        if now - self.last_sent < self.interval:
            return

        self.last_sent = now

        uptime = datetime.utcnow() - self.started_at
        mins = int(uptime.total_seconds() // 60)

        msg = (
            f"💓 Bot alive\n"
            f"Scans: {self.scans}\n"
            f"Trades: {self.trades}\n"
            f"Uptime: {mins}m"
        )

        self.tg._send_text(msg)
