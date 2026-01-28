"""
TradeMindIQ Enhanced Reports Module
====================================
Weekly and monthly performance summaries with charts and exports.
Safe, non-intrusive - only reads from trades.db.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
from services.analytics import PerformanceAnalytics, PerformanceSummary


@dataclass
class WeeklyReport:
    """Weekly performance report."""
    week_start: datetime
    week_end: datetime
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    best_symbol: str
    worst_symbol: str
    top_trade: Dict
    daily_breakdown: List[Dict]
    hourly_heatmap: Dict[int, int]  # hour -> trade count
    exit_reason_breakdown: Dict[str, int]
    goals: Dict[str, bool]  # goal -> achieved
    notes: List[str]


@dataclass
class MonthlyReport:
    """Monthly performance report."""
    month: str  # "2026-01"
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_daily_pnl: float
    best_day: str
    worst_day: str
    best_symbol: str
    worst_symbol: str
    weekly_summaries: List[Dict]
    monthly_goal: float
    goal_achieved: bool
    trends: Dict[str, str]  # metric -> trend direction
    top_performers: List[Dict]
    improvement_areas: List[str]


class ReportGenerator:
    """
    Generate enhanced performance reports.
    Reads from trades.db, never modifies data.
    """
    
    def __init__(self, db_path: str = "trades.db"):
        self.db_path = db_path
        self.analytics = PerformanceAnalytics(db_path)
    
    def get_week_dates(self, week_start: datetime) -> Tuple[datetime, datetime]:
        """Get start and end of week."""
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
    
    def generate_weekly_report(
        self, 
        week_start: datetime,
        goals: Optional[Dict] = None
    ) -> WeeklyReport:
        """Generate weekly performance report."""
        week_end = week_start + timedelta(days=6)
        
        # Get trades for the week
        trades = self.analytics.get_trades_by_date(week_start, week_end)
        summary = self.analytics.calculate_performance_summary(trades)
        
        # Calculate daily breakdown
        daily_breakdown = []
        for day_str, pnl in summary.daily_pnl.items():
            day_date = datetime.fromisoformat(day_str)
            day_trades = [t for t in trades if t.closed_at.date() == day_date.date()]
            wins = sum(1 for t in day_trades if t.pnl > 0)
            daily_breakdown.append({
                "date": day_str,
                "trades": len(day_trades),
                "wins": wins,
                "losses": len(day_trades) - wins,
                "pnl": round(pnl, 2)
            })
        
        # Hourly heatmap
        hourly_heatmap = defaultdict(int)
        for t in trades:
            hourly_heatmap[t.closed_at.hour] += 1
        
        # Best/Worst symbols
        sorted_symbols = sorted(
            summary.pnl_by_symbol.items(), 
            key=lambda x: x[1].total_pnl, 
            reverse=True
        )
        best_symbol = sorted_symbols[0][0] if sorted_symbols else "N/A"
        worst_symbol = sorted_symbols[-1][0] if sorted_symbols else "N/A"
        
        # Top trade
        top_trade = None
        if summary.worst_trade:  # Worst trade = most negative, so best is min pnl
            top_trade = {
                "symbol": summary.best_trade.symbol,
                "pnl": round(summary.best_trade.pnl, 2),
                "exit_reason": summary.best_trade.exit_reason
            }
        
        # Evaluate goals
        goal_results = {}
        if goals:
            goal_results = {
                "win_rate_40%": summary.win_rate >= 40,
                "positive_pnl": summary.total_pnl > 0,
                "trades_50+": summary.total_trades >= 50,
                "no_big_loss": summary.best_trade.pnl > -100 if summary.best_trade else True,
            }
        
        # Generate notes
        notes = []
        if summary.win_rate >= 40:
            notes.append(f"Win rate of {summary.win_rate:.1f}% exceeds 40% target")
        if summary.total_pnl > 0:
            notes.append(f"Profitable week with ${summary.total_pnl:.2f} net")
        if summary.total_trades < 20:
            notes.append(f"Low trade volume ({summary.total_trades} trades) - consider increasing opportunities")
        
        return WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            total_trades=summary.total_trades,
            wins=summary.total_wins,
            losses=summary.total_losses,
            win_rate=summary.win_rate,
            total_pnl=summary.total_pnl,
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            top_trade=top_trade,
            daily_breakdown=daily_breakdown,
            hourly_heatmap=dict(hourly_heatmap),
            exit_reason_breakdown=summary.exit_reason_counts,
            goals=goal_results,
            notes=notes
        )
    
    def generate_monthly_report(
        self, 
        year: int, 
        month: int,
        monthly_goal: float = 100.0
    ) -> MonthlyReport:
        """Generate monthly performance report."""
        month_str = f"{year}-{month:02d}"
        start_date = datetime(year, month, 1)
        
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Get all trades for month
        trades = self.analytics.get_trades_by_date(start_date, end_date)
        summary = self.analytics.calculate_performance_summary(trades)
        
        # Calculate metrics
        total_days = (end_date - start_date).days + 1
        avg_daily = summary.total_pnl / total_days if total_days > 0 else 0
        
        # Best/Worst days
        daily_items = list(summary.daily_pnl.items())
        if daily_items:
            best_day = max(daily_items, key=lambda x: x[1])
            worst_day = min(daily_items, key=lambda x: x[1])
        else:
            best_day = ("N/A", 0)
            worst_day = ("N/A", 0)
        
        # Weekly summaries
        weekly_summaries = []
        current = start_date
        while current <= end_date:
            week_end = min(current + timedelta(days=6), end_date)
            week_summary = self.generate_weekly_report(current)
            weekly_summaries.append({
                "week": current.strftime("%Y-%m-%d"),
                "trades": week_summary.total_trades,
                "pnl": round(week_summary.total_pnl, 2),
                "win_rate": round(week_summary.win_rate, 1)
            })
            current = week_end + timedelta(days=1)
        
        # Best/Worst symbols
        sorted_symbols = sorted(
            summary.pnl_by_symbol.items(), 
            key=lambda x: x[1].total_pnl, 
            reverse=True
        )
        best_symbol = sorted_symbols[0][0] if sorted_symbols else "N/A"
        worst_symbol = sorted_symbols[-1][0] if sorted_symbols else "N/A"
        
        # Trends (simple comparison with previous period)
        prev_month = datetime(year, month, 1) - timedelta(days=1)
        prev_summary = self.analytics.get_recent_performance(days=30)
        
        trends = {}
        if prev_summary.total_trades > 0:
            trends["volume"] = "↑" if summary.total_trades > prev_summary.total_trades else "↓"
        else:
            trends["volume"] = "→"
        
        if prev_summary.win_rate > 0:
            trends["win_rate"] = "↑" if summary.win_rate > prev_summary.win_rate else "↓"
        else:
            trends["win_rate"] = "→"
        
        trends["pnl"] = "↑" if summary.total_pnl > 0 else "↓"
        
        # Top performers
        top_performers = []
        for symbol, stats in list(summary.pnl_by_symbol.items())[:5]:
            top_performers.append({
                "symbol": symbol,
                "trades": stats.total_trades,
                "win_rate": round(stats.win_rate, 1),
                "pnl": round(stats.total_pnl, 2)
            })
        
        # Improvement areas
        improvement_areas = []
        if summary.win_rate < 40:
            improvement_areas.append("Win rate below 40% - review entry criteria")
        if summary.total_pnl < 0:
            improvement_areas.append("Negative P&L - consider risk management review")
        
        # Exit reason analysis
        time_exits = summary.exit_reason_counts.get("TIME", 0)
        total_exits = sum(summary.exit_reason_counts.values())
        if total_exits > 0 and time_exits / total_exits > 0.8:
            improvement_areas.append("83%+ TIME exits - consider extending hold times")
        
        goal_achieved = summary.total_pnl >= monthly_goal
        
        return MonthlyReport(
            month=month_str,
            total_trades=summary.total_trades,
            wins=summary.total_wins,
            losses=summary.total_losses,
            win_rate=summary.win_rate,
            total_pnl=summary.total_pnl,
            avg_daily_pnl=avg_daily,
            best_day=best_day[0],
            worst_day=worst_day[0],
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            weekly_summaries=weekly_summaries,
            monthly_goal=monthly_goal,
            goal_achieved=goal_achieved,
            trends=trends,
            top_performers=top_performers,
            improvement_areas=improvement_areas
        )
    
    def generate_text_report(self, report: WeeklyReport) -> str:
        """Generate formatted weekly text report."""
        lines = [
            "=" * 60,
            f"WEEKLY PERFORMANCE REPORT",
            f"{report.week_start.strftime('%Y-%m-%d')} to {report.week_end.strftime('%Y-%m-%d')}",
            "=" * 60,
            "",
            "📊 SUMMARY",
            "-" * 40,
            f"Total Trades:    {report.total_trades}",
            f"Win Rate:        {report.win_rate:.1f}%",
            f"Net P/L:         ${report.total_pnl:,.2f}",
            f"Best Symbol:     {report.best_symbol}",
            f"Worst Symbol:    {report.worst_symbol}",
            "",
            "📅 DAILY BREAKDOWN",
            "-" * 40,
        ]
        
        for day in report.daily_breakdown:
            emoji = "🟢" if day["pnl"] > 0 else "🔴" if day["pnl"] < 0 else "⚪"
            lines.append(f"{emoji} {day['date']}: {day['trades']} trades, ${day['pnl']:,.2f}")
        
        lines.extend([
            "",
            "🎯 GOALS",
            "-" * 40,
        ])
        
        if report.goals:
            for goal, achieved in report.goals.items():
                status = "✅" if achieved else "❌"
                lines.append(f"{status} {goal}")
        else:
            lines.append("No goals set for this week")
        
        if report.notes:
            lines.extend([
                "",
                "📝 NOTES",
                "-" * 40,
            ])
            for note in report.notes:
                lines.append(f"• {note}")
        
        lines.extend([
            "",
            "🚪 EXIT REASONS",
            "-" * 40,
        ])
        
        for reason, count in sorted(report.exit_reason_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"  {reason:<10} {count} trades")
        
        lines.extend([
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def generate_monthly_text_report(self, report: MonthlyReport) -> str:
        """Generate formatted monthly text report."""
        lines = [
            "=" * 60,
            f"MONTHLY PERFORMANCE REPORT - {report.month}",
            "=" * 60,
            "",
            "📊 MONTHLY SUMMARY",
            "-" * 40,
            f"Total Trades:    {report.total_trades}",
            f"Win Rate:        {report.win_rate:.1f}%",
            f"Net P/L:         ${report.total_pnl:,.2f}",
            f"Daily Avg:       ${report.avg_daily_pnl:,.2f}",
            f"Monthly Goal:    ${report.monthly_goal:,.2f}",
            f"Goal Achieved:   {'✅ YES' if report.goal_achieved else '❌ NO'}",
            "",
            "🏆 TOP PERFORMERS",
            "-" * 40,
        ]
        
        for p in report.top_performers:
            lines.append(f"  {p['symbol']:<12} ${p['pnl']:>8.2f} ({p['trades']} trades)")
        
        lines.extend([
            "",
            "📈 WEEKLY BREAKDOWN",
            "-" * 40,
        ])
        
        for week in report.weekly_summaries:
            emoji = "🟢" if week["pnl"] > 0 else "🔴"
            lines.append(f"{emoji} Week of {week['week']}: {week['trades']} trades, ${week['pnl']:,.2f}")
        
        if report.improvement_areas:
            lines.extend([
                "",
                "🔧 IMPROVEMENT AREAS",
                "-" * 40,
            ])
            for area in report.improvement_areas:
                lines.append(f"• {area}")
        
        lines.extend([
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def export_report(self, report, filepath: str, format: str = "json"):
        """Export report to JSON or text file."""
        if format == "json":
            if hasattr(report, '__dict__'):
                data = {k: v for k, v in report.__dict__.items() if not k.startswith('_')}
                # Convert datetime objects
                for key in ['week_start', 'week_end']:
                    if key in data and isinstance(data[key], datetime):
                        data[key] = data[key].isoformat()
            else:
                data = report
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        else:
            if hasattr(report, 'week_start'):
                text = self.generate_text_report(report)
            else:
                text = self.generate_monthly_text_report(report)
            with open(filepath, 'w') as f:
                f.write(text)
        
        print(f"Report exported to {filepath}")
    
    def get_current_week_report(self, goals: Optional[Dict] = None) -> WeeklyReport:
        """Get report for current week."""
        today = datetime.now()
        # Find Monday of current week
        week_start = today - timedelta(days=today.weekday())
        return self.generate_weekly_report(week_start, goals)
    
    def get_current_month_report(self, goal: float = 100.0) -> MonthlyReport:
        """Get report for current month."""
        today = datetime.now()
        return self.generate_monthly_report(today.year, today.month, goal)


# Convenience functions
def weekly_checkin(goals: Optional[Dict] = None):
    """Quick weekly performance check-in."""
    generator = ReportGenerator()
    report = generator.get_current_week_report(goals)
    print(generator.generate_text_report(report))
    return report


def monthly_review(monthly_goal: float = 100.0):
    """Quick monthly review."""
    generator = ReportGenerator()
    report = generator.get_current_month_report(monthly_goal)
    print(generator.generate_monthly_text_report(report))
    return report


def export_weekly_report(filepath: str = "weekly_report.json"):
    """Export current week to JSON."""
    generator = ReportGenerator()
    report = generator.get_current_week_report()
    generator.export_report(report, filepath)
    return report


def export_monthly_report(filepath: str = "monthly_report.json"):
    """Export current month to JSON."""
    generator = ReportGenerator()
    report = generator.get_current_month_report()
    generator.export_report(report, filepath)
    return report


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "weekly":
            weekly_checkin()
        elif command == "monthly":
            monthly_review()
        elif command == "export-weekly":
            export_weekly_report()
        elif command == "export-monthly":
            export_monthly_report()
        else:
            print("Usage: python reports.py [weekly|monthly|export-weekly|export-monthly]")
    else:
        # Default: show weekly report
        print("TradeMindIQ Report Generator\n")
        weekly_checkin()
