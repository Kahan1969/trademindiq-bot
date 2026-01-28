import sqlite3
from core.models import Trade


class TradeRepository:
    def __init__(self, path: str = "trades.db"):
        self.conn = sqlite3.connect(path)
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            side TEXT,
            entry REAL,
            stop REAL,
            target REAL,
            filled_price REAL,
            exit_price REAL,
            pnl REAL,
            created_at TEXT,
            closed_at TEXT,
            exit_reason TEXT
        )
        """)
        self.conn.commit()

    def save_trade(self, trade: Trade):
        cur = self.conn.cursor()
        s = trade.signal
        cur.execute("""
        INSERT INTO trades(symbol, side, entry, stop, target, filled_price,
                           exit_price, pnl, created_at, closed_at, exit_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s.symbol,
            s.side.value,
            s.entry,
            s.stop,
            s.target,
            trade.order.filled_price,
            trade.exit_price,
            trade.pnl,
            s.created_at.isoformat(),
            trade.closed_at.isoformat(),
            trade.exit_reason,
        ))
        self.conn.commit()
