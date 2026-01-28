"""
TradeMindIQ Performance Analytics Module
=========================================
Safe, non-intrusive analytics that reads from trades.db
Does NOT modify any existing data or core logic.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import json


@dataclass
class TradeMetrics:
    """Metrics for a single trade."""
    id: int
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    duration_seconds: float
    exit_reason: str
    created_at: datetime
    closed_at: datetime


@dataclass
class SymbolStats:
    """Statistics for a symbol."""
    symbol: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    best_trade: Optional[TradeMetrics]
    worst_trade: Optional[TradeMetrics]
    avg_hold_time_seconds: float


@dataclass
class PerformanceSummary:
    """Overall performance summary."""
    total_trades: int
    total_wins: int
    total_losses: float  # actually count
    win_rate: float
    total_pnl: float
    avg_pnl_per_trade: float
    best_trade: Optional[TradeMetrics]
    worst_trade: Optional[TradeMetrics]
    avg_hold_time_seconds: float
    pnl_by_symbol: Dict[str, SymbolStats]
    exit_reason_counts: Dict[str, int]
    daily_pnl: Dict[str, float]


class PerformanceAnalytics:
    """
    Read-only analytics for TradeMindIQ trades database.
    Safe to use - never modifies data.
    """
    
    def __init__(self, db_path: str = "trades.db"):
        """
        Initialize analytics with path to trades database.
        
        Args:
            db_path: Path to trades.db (relative or absolute)
        """
        self.db_path = db_path
        self._db_exists = False
        self._check_db_exists()
    
    def _check_db_exists(self) -> bool:
        """Check if database file exists and is valid."""
        try:
            import os
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
                if cursor.fetchone():
                    self._db_exists = True
                conn.close()
        except Exception:
            self._db_exists = False
        return self._db_exists
    
    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        import os
        if not os.path.exists(self.db_path):
            # Create a temporary in-memory database for demo purposes
            conn = sqlite3.connect(":memory:")
            self._create_demo_schema(conn)
            return conn
        return sqlite3.connect(self.db_path)
    
    def _create_demo_schema(self, conn) -> None:
        """Create demo schema and sample data for when DB doesn't exist."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                entry REAL,
                exit_price REAL,
                pnl REAL,
                entry_time TIMESTAMP,
                closed_at TIMESTAMP,
                exit_reason TEXT
            )
        """)
        conn.commit()
    
    def _row_to_trade(self, row: tuple, columns: List[str]) -> TradeMetrics:
        """Convert database row to TradeMetrics object."""
        return TradeMetrics(
            id=row[columns.index('id')],
            symbol=row[columns.index('symbol')],
            side=row[columns.index('side')],
            entry_price=row[columns.index('entry')],
            exit_price=row[columns.index('exit_price')],
            pnl=row[columns.index('pnl')],
            pnl_pct=self._calculate_pnl_pct(
                row[columns.index('entry')],
                row[columns.index('exit_price')],
                row[columns.index('side')]
            ),
            duration_seconds=self._calculate_duration(
                row[columns.index('created_at')],
                row[columns.index('closed_at')]
            ),
            exit_reason=row[columns.index('exit_reason')],
            created_at=datetime.fromisoformat(row[columns.index('created_at')]),
            closed_at=datetime.fromisoformat(row[columns.index('closed_at')])
        )
    
    def _calculate_pnl_pct(self, entry: float, exit: float, side: str) -> float:
        """Calculate P&L percentage."""
        if side == 'BUY':
            return ((exit - entry) / entry) * 100
        else:
            return ((entry - exit) / entry) * 100
    
    def _calculate_duration(self, created: str, closed: str) -> float:
        """Calculate trade duration in seconds."""
        start = datetime.fromisoformat(created)
        end = datetime.fromisoformat(closed)
        return (end - start).total_seconds()
    
    def get_all_trades(self) -> List[TradeMetrics]:
        """Fetch all closed trades from database."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC")
            rows = cursor.fetchall()
            if not rows:
                conn.close()
                return []
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return [self._row_to_trade(row, columns) for row in rows]
        except Exception:
            return []
    
    def get_trades_by_date(self, start_date: datetime, end_date: datetime) -> List[TradeMetrics]:
        """Get trades within a date range."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades WHERE closed_at BETWEEN ? AND ? ORDER BY closed_at DESC",
                (start_date.isoformat(), end_date.isoformat())
            )
            rows = cursor.fetchall()
            if not rows:
                conn.close()
                return []
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return [self._row_to_trade(row, columns) for row in rows]
        except Exception:
            return []
    
    def get_trades_by_symbol(self, symbol: str) -> List[TradeMetrics]:
        """Get all trades for a specific symbol."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades WHERE symbol = ? AND closed_at IS NOT NULL ORDER BY closed_at DESC",
                (symbol,)
            )
            rows = cursor.fetchall()
            if not rows:
                conn.close()
                return []
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return [self._row_to_trade(row, columns) for row in rows]
        except Exception:
            return []
    
    def calculate_performance_summary(self, trades: Optional[List[TradeMetrics]] = None) -> PerformanceSummary:
        """Calculate overall performance metrics."""
        if trades is None:
            trades = self.get_all_trades()
        
        if not trades:
            return PerformanceSummary(
                total_trades=0, total_wins=0, total_losses=0,
                win_rate=0, total_pnl=0, avg_pnl_per_trade=0,
                best_trade=None, worst_trade=None, avg_hold_time_seconds=0,
                pnl_by_symbol={}, exit_reason_counts={}, daily_pnl={}
            )
        
        # Basic counts
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        
        # Total P&L
        total_pnl = sum(t.pnl for t in trades)
        
        # Best/Worst trades
        best_trade = min(trades, key=lambda t: t.pnl) if losses else None
        worst_trade = max(trades, key=lambda t: t.pnl) if wins else None
        
        # Average hold time
        avg_hold = sum(t.duration_seconds for t in trades) / len(trades)
        
        # P&L by symbol
        symbol_groups = defaultdict(list)
        for t in trades:
            symbol_groups[t.symbol].append(t)
        
        pnl_by_symbol = {}
        for symbol, symbol_trades in symbol_groups.items():
            win_count = sum(1 for t in symbol_trades if t.pnl > 0)
            symbol_total_pnl = sum(t.pnl for t in symbol_trades)
            symbol_avg_hold = sum(t.duration_seconds for t in symbol_trades) / len(symbol_trades)
            symbol_best = min(symbol_trades, key=lambda t: t.pnl) if any(t.pnl <= 0 for t in symbol_trades) else None
            symbol_worst = max(symbol_trades, key=lambda t: t.pnl) if any(t.pnl > 0 for t in symbol_trades) else None
            
            pnl_by_symbol[symbol] = SymbolStats(
                symbol=symbol,
                total_trades=len(symbol_trades),
                wins=win_count,
                losses=len(symbol_trades) - win_count,
                win_rate=(win_count / len(symbol_trades)) * 100,
                total_pnl=symbol_total_pnl,
                avg_pnl=symbol_total_pnl / len(symbol_trades),
                best_trade=symbol_best,
                worst_trade=symbol_worst,
                avg_hold_time_seconds=symbol_avg_hold
            )
        
        # Exit reason counts
        exit_reasons = defaultdict(int)
        for t in trades:
            exit_reasons[t.exit_reason] += 1
        
        # Daily P&L
        daily = defaultdict(float)
        for t in trades:
            day = t.closed_at.strftime('%Y-%m-%d')
            daily[day] += t.pnl
        
        return PerformanceSummary(
            total_trades=len(trades),
            total_wins=len(wins),
            total_losses=len(losses),
            win_rate=(len(wins) / len(trades)) * 100,
            total_pnl=total_pnl,
            avg_pnl_per_trade=total_pnl / len(trades),
            best_trade=min(trades, key=lambda t: t.pnl) if losses else None,
            worst_trade=max(trades, key=lambda t: t.pnl) if wins else None,
            avg_hold_time_seconds=avg_hold,
            pnl_by_symbol=dict(sorted(pnl_by_symbol.items(), key=lambda x: x[1].total_pnl, reverse=True)),
            exit_reason_counts=dict(exit_reasons),
            daily_pnl=dict(sorted(daily.items()))
        )
    
    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, float, float]]:
        """
        Get top/bottom performing symbols.
        
        Returns:
            List of (symbol, total_pnl, win_rate) sorted by P&L descending
        """
        summary = self.calculate_performance_summary()
        return [
            (symbol, stats.total_pnl, stats.win_rate)
            for symbol, stats in summary.pnl_by_symbol.items()
        ][:limit]
    
    def get_recent_performance(self, days: int = 7) -> PerformanceSummary:
        """Get performance for last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        trades = self.get_trades_by_date(start_date, end_date)
        return self.calculate_performance_summary(trades)
    
    def generate_report(self, days: Optional[int] = None) -> str:
        """Generate a formatted text report."""
        if days:
            summary = self.get_recent_performance(days)
            period = f"Last {days} days"
        else:
            summary = self.calculate_performance_summary()
            period = "All time"
        
        lines = [
            "=" * 60,
            f"TradeMindIQ Performance Report - {period}",
            "=" * 60,
            "",
            "📊 OVERALL PERFORMANCE",
            "-" * 40,
            f"Total Trades:     {summary.total_trades}",
            f"Win Rate:         {summary.win_rate:.1f}%",
            f"Total P&L:        ${summary.total_pnl:,.2f}",
            f"Avg P/L per Trade: ${summary.avg_pnl_per_trade:,.2f}",
            f"Avg Hold Time:    {summary.avg_hold_time_seconds/60:.1f} minutes",
            "",
            "🏆 BEST TRADE",
            "-" * 40,
        ]
        
        if summary.best_trade:
            t = summary.best_trade
            lines.extend([
                f"Symbol:           {t.symbol}",
                f"P/L:              ${t.pnl:,.2f}",
                f"Entry:            ${t.entry_price:.4f}",
                f"Exit:             ${t.exit_price:.4f}",
                f"Exit Reason:      {t.exit_reason}",
            ])
        else:
            lines.append("No winning trades yet")
        
        lines.extend([
            "",
            "⚠️ WORST TRADE",
            "-" * 40,
        ])
        
        if summary.worst_trade:
            t = summary.worst_trade
            lines.extend([
                f"Symbol:           {t.symbol}",
                f"P/L:              ${t.pnl:,.2f}",
                f"Entry:            ${t.entry_price:.4f}",
                f"Exit:             ${t.exit_price:.4f}",
                f"Exit Reason:      {t.exit_reason}",
            ])
        else:
            lines.append("No losing trades")
        
        lines.extend([
            "",
            "📈 PERFORMANCE BY SYMBOL",
            "-" * 40,
        ])
        
        for symbol, stats in list(summary.pnl_by_symbol.items())[:15]:
            emoji = "🟢" if stats.total_pnl > 0 else "🔴"
            lines.append(f"{emoji} {symbol:<12} ${stats.total_pnl:>10,.2f} ({stats.win_rate:.0f}% WR)")
        
        lines.extend([
            "",
            "🚪 EXIT REASONS",
            "-" * 40,
        ])
        
        for reason, count in sorted(summary.exit_reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {reason:<15} {count} trades")
        
        lines.extend([
            "",
            "📅 DAILY P&L",
            "-" * 40,
        ])
        
        for day, pnl in list(summary.daily_pnl.items())[-7:]:
            emoji = "🟢" if pnl > 0 else "🔴"
            lines.append(f"  {emoji} {day} ${pnl:>10,.2f}")
        
        lines.extend([
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def export_to_json(self, days: Optional[int] = None) -> str:
        """Export performance data as JSON."""
        if days:
            summary = self.get_recent_performance(days)
        else:
            summary = self.calculate_performance_summary()
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "period": f"last_{days}_days" if days else "all_time",
            "summary": {
                "total_trades": summary.total_trades,
                "win_rate": round(summary.win_rate, 2),
                "total_pnl": round(summary.total_pnl, 2),
                "avg_pnl_per_trade": round(summary.avg_pnl_per_trade, 2),
                "avg_hold_time_minutes": round(summary.avg_hold_time_seconds / 60, 2)
            },
            "best_trade": {
                "symbol": summary.best_trade.symbol,
                "pnl": round(summary.best_trade.pnl, 2),
                "exit_reason": summary.best_trade.exit_reason
            } if summary.best_trade else None,
            "worst_trade": {
                "symbol": summary.worst_trade.symbol,
                "pnl": round(summary.worst_trade.pnl, 2),
                "exit_reason": summary.worst_trade.exit_reason
            } if summary.worst_trade else None,
            "by_symbol": {
                symbol: {
                    "total_trades": stats.total_trades,
                    "win_rate": round(stats.win_rate, 2),
                    "total_pnl": round(stats.total_pnl, 2),
                    "avg_pnl": round(stats.avg_pnl, 2)
                }
                for symbol, stats in summary.pnl_by_symbol.items()
            },
            "exit_reasons": summary.exit_reason_counts,
            "daily_pnl": summary.daily_pnl
        }
        
        return json.dumps(data, indent=2)


# Convenience functions for CLI usage
def main():
    """Quick analytics summary from command line."""
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "trades.db"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    analytics = PerformanceAnalytics(db_path)
    
    if "--json" in sys.argv:
        print(analytics.export_to_json(days))
    else:
        print(analytics.generate_report(days))


if __name__ == "__main__":
    main()
