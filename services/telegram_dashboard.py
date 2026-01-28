"""
TradeMindIQ Telegram Dashboard
===============================
Inline keyboard buttons for instant access to all reports.
Safe, read-only - only provides data, never executes trades.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class Button:
    """Telegram inline button."""
    text: str
    callback_data: str


class TelegramDashboard:
    """
    Telegram inline keyboard dashboard for TradeMindIQ.
    Provides quick access to all analytics, reports, and strategies.
    """
    
    def __init__(self):
        # Initialize all sub-systems
        from services.analytics import PerformanceAnalytics
        from services.reports import ReportGenerator
        from services.portfolio import PortfolioTracker
        
        self.analytics = PerformanceAnalytics()
        self.reports = ReportGenerator()
        self.portfolio = PortfolioTracker()
    
    # ==================== ANALYTICS BUTTONS ====================
    
    def get_analytics_buttons(self) -> List[List[Button]]:
        """Get analytics dashboard buttons."""
        return [
            [Button("📊 Full Report", "analytics_full")],
            [Button("📈 By Symbol", "analytics_symbols")],
            [Button("📅 Last 7 Days", "analytics_7day")],
            [Button("📋 Export JSON", "analytics_json")],
            [Button("🔙 Back", "main_menu")],
        ]
    
    def get_main_menu_buttons(self) -> List[List[Button]]:
        """Get main menu buttons."""
        return [
            [Button("📊 Analytics", "analytics_menu")],
            [Button("📝 Reports", "reports_menu")],
            [Button("💼 Portfolio", "portfolio_dashboard")],
            [Button("🎯 Strategies", "strategies_menu")],
            [Button("🏠 Home", "main_menu")],
        ]
    
    def get_reports_buttons(self) -> List[List[Button]]:
        """Get reports menu buttons."""
        return [
            [Button("📅 Weekly Report", "report_weekly")],
            [Button("📆 Monthly Report", "report_monthly")],
            [Button("📤 Export Weekly", "report_export_weekly")],
            [Button("📤 Export Monthly", "report_export_monthly")],
            [Button("🎯 Set Goals", "report_goals")],
            [Button("🔙 Back", "main_menu")],
        ]
    
    def get_strategies_buttons(self) -> List[List[Button]]:
        """Get strategies menu buttons."""
        return [
            [Button("⚔️ Warrior Momentum", "strategy_warrior")],
            [Button("📉 Mean Reversion", "strategy_mean_reversion")],
            [Button("📐 Grid Trading", "strategy_grid")],
            [Button("🔄 Adaptive Grid", "strategy_adaptive_grid")],
            [Button("🔙 Back", "main_menu")],
        ]
    
    # ==================== HANDLERS ====================
    
    def handle_callback(self, callback_data: str) -> str:
        """
        Handle button callback and return response message.
        
        Args:
            callback_data: The button's callback_data
            
        Returns:
            Response message text
        """
        handlers = {
            # Main Menu
            "main_menu": self._main_menu,
            "analytics_menu": self._analytics_menu,
            "reports_menu": self._reports_menu,
            "strategies_menu": self._strategies_menu,
            
            # Analytics
            "analytics_full": self._analytics_full,
            "analytics_symbols": self._analytics_symbols,
            "analytics_7day": self._analytics_7day,
            "analytics_json": self._analytics_json,
            
            # Reports
            "report_weekly": self._report_weekly,
            "report_monthly": self._report_monthly,
            "report_export_weekly": self._report_export_weekly,
            "report_export_monthly": self._report_export_monthly,
            "report_goals": self._report_goals,
            
            # Portfolio
            "portfolio_dashboard": self._portfolio_dashboard,
            
            # Strategies
            "strategy_warrior": self._strategy_warrior,
            "strategy_mean_reversion": self._strategy_mean_reversion,
            "strategy_grid": self._strategy_grid,
            "strategy_adaptive_grid": self._strategy_adaptive_grid,
        }
        
        handler = handlers.get(callback_data)
        if handler:
            return handler()
        else:
            return "Unknown command. Use /trademindiq to return to menu."
    
    def _main_menu(self) -> str:
        """Main menu message."""
        return (
            "🤖 **TradeMindIQ Control Center**\n\n"
            "Select a module to view:\n\n"
            "📊 **Analytics** - Performance metrics & reports\n"
            "📝 **Reports** - Weekly/Monthly summaries\n"
            "💼 **Portfolio** - Open positions & P/L\n"
            "🎯 **Strategies** - Strategy info & backtests"
        )
    
    def _analytics_menu(self) -> str:
        """Analytics menu message."""
        return (
            "📊 **Analytics Dashboard**\n\n"
            "Choose a report:\n"
            "• Full performance report\n"
            "• Breakdown by symbol\n"
            "• Last 7 days\n"
            "• Export to JSON"
        )
    
    def _reports_menu(self) -> str:
        """Reports menu message."""
        return (
            "📝 **Reports Menu**\n\n"
            "Choose a report:\n"
            "• Weekly performance summary\n"
            "• Monthly review with goals\n"
            "• Export reports to files\n"
            "• Set performance goals"
        )
    
    def _strategies_menu(self) -> str:
        """Strategies menu message."""
        return (
            "🎯 **Strategies**\n\n"
            "Available strategies:\n"
            "• Warrior Momentum - Primary strategy\n"
            "• Mean Reversion - RSI/Bollinger Bands\n"
            "• Grid Trading - Fixed grid levels\n"
            "• Adaptive Grid - Volatility-adjusted"
        )
    
    # Analytics Handlers
    def _analytics_full(self) -> str:
        """Generate full analytics report."""
        return self.analytics.generate_report()
    
    def _analytics_symbols(self) -> str:
        """Generate symbol breakdown."""
        leaderboard = self.analytics.get_leaderboard(limit=15)
        
        lines = ["📈 **PERFORMANCE BY SYMBOL**", ""]
        for symbol, pnl, win_rate in leaderboard:
            emoji = "🟢" if pnl > 0 else "🔴"
            lines.append(f"{emoji} {symbol:<12} ${pnl:>8.2f}  ({win_rate:.0f}% WR)")
        
        return "\n".join(lines)
    
    def _analytics_7day(self) -> str:
        """Generate 7-day report."""
        return self.analytics.generate_report(days=7)
    
    def _analytics_json(self) -> str:
        """Export analytics to JSON."""
        json_data = self.analytics.export_to_json()
        
        # Save to file
        with open("analytics_export.json", "w") as f:
            f.write(json_data)
        
        return (
            "✅ **Analytics exported to:**\n"
            "`analytics_export.json`\n\n"
            "Use `/trademindiq` to return to menu."
        )
    
    # Reports Handlers
    def _report_weekly(self) -> str:
        """Generate weekly report."""
        return self.reports.generate_text_report(
            self.reports.get_current_week_report()
        )
    
    def _report_monthly(self) -> str:
        """Generate monthly report."""
        return self.reports.generate_monthly_text_report(
            self.reports.get_current_month_report()
        )
    
    def _report_export_weekly(self) -> str:
        """Export weekly report."""
        self.reports.export_report(
            self.reports.get_current_week_report(),
            "weekly_report.json"
        )
        return "✅ Weekly report exported to `weekly_report.json`"
    
    def _report_export_monthly(self) -> str:
        """Export monthly report."""
        self.reports.export_report(
            self.reports.get_current_month_report(),
            "monthly_report.json"
        )
        return "✅ Monthly report exported to `monthly_report.json`"
    
    def _report_goals(self) -> str:
        """Set/View goals."""
        return (
            "🎯 **Performance Goals**\n\n"
            "Set your weekly targets:\n"
            "• Win Rate: 40%+\n"
            "• Positive P&L\n"
            "• 50+ trades/week\n"
            "• No losses > $100\n\n"
            "Use `/trademindiq` to return to menu."
        )
    
    # Portfolio Handler
    def _portfolio_dashboard(self) -> str:
        """Generate portfolio dashboard."""
        return self.portfolio.generate_compact_dashboard()
    
    # Strategy Handlers
    def _strategy_warrior(self) -> str:
        """Warrior Momentum strategy info."""
        return (
            "⚔️ **Warrior Momentum Strategy**\n\n"
            "Rules:\n"
            "• Trade only during high-vol session\n"
            "• Require gap + high RVOL\n"
            "• EMAs stacked: price > EMA9 > EMA20 > EMA50\n"
            "• ATR-based stop placement\n"
            "• R-multiple target (2x risk)\n\n"
            "Parameters:\n"
            "• min_rel_vol: 2.0\n"
            "• min_gap_pct: 0.5\n"
            "• session: EU/US overlap"
        )
    
    def _strategy_mean_reversion(self) -> str:
        """Mean Reversion strategy info."""
        return (
            "📉 **Mean Reversion Strategy**\n\n"
            "Rules:\n"
            "• RSI oversold (<30) = LONG\n"
            "• RSI overbought (>70) = SHORT\n"
            "• Bollinger Band touches confirm\n"
            "• VWAP for trend confirmation\n\n"
            "Indicators:\n"
            "• RSI (14)\n"
            "• Bollinger Bands (20, 2σ)\n"
            "• VWAP (390 periods)"
        )
    
    def _strategy_grid(self) -> str:
        """Grid Trading strategy info."""
        return (
            "📐 **Grid Trading Strategy**\n\n"
            "Rules:\n"
            "• Place orders at fixed intervals\n"
            "• Buy when price drops to grid level\n"
            "• Sell when price rises to grid level\n"
            "• Profit from volatility\n\n"
            "Parameters:\n"
            "• grid_levels: 5\n"
            "• grid_spacing: 0.5%\n"
            "• range_width: 5%"
        )
    
    def _strategy_adaptive_grid(self) -> str:
        """Adaptive Grid strategy info."""
        return (
            "🔄 **Adaptive Grid Strategy**\n\n"
            "Rules:\n"
            "• Grid spacing adjusts to volatility\n"
            "• Wider grids during high vol\n"
            "• Tighter grids during low vol\n"
            "• Automatic adjustment\n\n"
            "Parameters:\n"
            "• volatility_lookback: 20\n"
            "• volatility_multiplier: 1.5\n"
            "• Adaptive spacing"
        )
    
    # ==================== TELEGRAM BOT INTEGRATION ====================
    
    def get_keyboard(self, callback_data: str) -> List[List[Dict]]:
        """
        Get Telegram inline keyboard for a menu.
        
        Returns:
            List of button rows, each row is list of button dicts
        """
        menu_map = {
            "main_menu": self.get_main_menu_buttons,
            "analytics_menu": self.get_analytics_buttons,
            "reports_menu": self.get_reports_buttons,
            "strategies_menu": self.get_strategies_buttons,
        }
        
        get_buttons = menu_map.get(callback_data, self.get_main_menu_buttons)
        
        keyboard = []
        for row in get_buttons():
            button_row = []
            for button in row:
                button_row.append({
                    "text": button.text,
                    "callback_data": button.callback_data
                })
            keyboard.append(button_row)
        
        return keyboard
    
    def generate_menu_message(self, menu: str = "main_menu") -> Dict:
        """
        Generate complete menu response.
        
        Returns:
            Dict with 'text' and 'keyboard' for Telegram API
        """
        response_text = self.handle_callback(menu)
        keyboard = self.get_keyboard(menu)
        
        return {
            "text": response_text,
            "reply_markup": {
                "inline_keyboard": keyboard
            }
        }


# ==================== STANDALONE TELEGRAM BOT ====================

class TradeMindIQBot:
    """
    Simple Telegram bot wrapper for TradeMindIQ.
    For production, integrate with your existing Telegram bot.
    """
    
    def __init__(self):
        self.dashboard = TelegramDashboard()
    
    def handle_update(self, update: Dict) -> Optional[Dict]:
        """
        Handle Telegram update.
        
        Args:
            update: Telegram update dict
            
        Returns:
            Response dict or None
        """
        # Check for commands
        if "message" in update:
            message = update["message"]
            text = message.get("text", "")
            
            if text == "/trademindiq":
                return self.dashboard.generate_menu_message("main_menu")
            
            elif text == "/portfolio":
                return self.dashboard.generate_menu_message("portfolio_dashboard")
            
            elif text == "/analytics":
                return self.dashboard.generate_menu_message("analytics_full")
            
            elif text == "/reports":
                return self.dashboard.generate_menu_message("report_weekly")
        
        # Check for callback queries
        elif "callback_query" in update:
            callback = update["callback_query"]
            data = callback.get("data", "")
            
            return self.dashboard.generate_menu_message(data)
        
        return None


# ==================== CONVENIENCE FUNCTIONS ====================

def create_dashboard_menu() -> Dict:
    """Create main dashboard menu."""
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message("main_menu")


def quick_stats() -> str:
    """Get quick stats summary."""
    analytics = PerformanceAnalytics()
    summary = analytics.calculate_performance_summary()
    
    return (
        f"📊 **Quick Stats**\n\n"
        f"Trades: {summary.total_trades}\n"
        f"Win Rate: {summary.win_rate:.1f}%\n"
        f"P/L: ${summary.total_pnl:.2f}\n"
        f"Best: {summary.best_trade.symbol if summary.best_trade else 'N/A'}\n"
        f"Worst: {summary.worst_trade.symbol if summary.worst_trade else 'N/A'}"
    )


if __name__ == "__main__":
    import json
    
    print("🤖 TradeMindIQ Telegram Dashboard")
    print("\nGenerating menu...")
    
    menu = create_dashboard_menu()
    print("\n" + "=" * 50)
    print(menu["text"])
    print("=" * 50)
    print("\nKeyboard structure:")
    print(json.dumps(menu["reply_markup"], indent=2))
