"""
TradeMindIQ Telegram Hook for Clawdbot
=======================================
Handles /trademindiq commands and inline button callbacks.
"""

import json
import sys
import os

# Add TradeMindIQBot to path
sys.path.insert(0, '/Users/kahangabar/Downloads/TradeMindIQBot')

from services.telegram_dashboard import TelegramDashboard


def trademindiq_hook(update: dict) -> dict:
    """
    Handle /trademindiq command.
    
    Returns:
        Dict with 'text' and 'reply_markup' for Telegram API
    """
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('main_menu')


def portfolio_hook(update: dict) -> dict:
    """
    Handle /portfolio command.
    
    Returns:
        Compact portfolio dashboard
    """
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('portfolio_dashboard')


def analytics_hook(update: dict) -> dict:
    """
    Handle /analytics command.
    
    Returns:
        Full analytics report
    """
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('analytics_full')


def reports_hook(update: dict) -> dict:
    """
    Handle /reports command.
    
    Returns:
        Weekly report
    """
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('report_weekly')


def trademindiq_callback(update: dict) -> dict:
    """
    Handle inline button callbacks.
    
    Callback data format: trademindiq_<action>
    e.g., trademindiq_analytics_full, trademindiq_portfolio_dashboard
    
    Returns:
        Updated response with new menu
    """
    callback_data = update.get('data', '')
    
    # Remove prefix
    if callback_data.startswith('trademindiq_'):
        action = callback_data[len('trademindiq_'):]
    else:
        action = callback_data
    
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message(action)


def quick_stats(update: dict) -> str:
    """
    Quick stats for compact display.
    
    Returns:
        Plain text response (no keyboard)
    """
    from services.analytics import PerformanceAnalytics
    
    analytics = PerformanceAnalytics()
    summary = analytics.calculate_performance_summary()
    
    emoji = "🟢" if summary.total_pnl >= 0 else "🔴"
    
    return (
        f"🤖 **TradeMindIQ Quick Stats**\n\n"
        f"**Trades:** {summary.total_trades}\n"
        f"**Win Rate:** {summary.win_rate:.1f}%\n"
        f"**P/L:** {emoji} ${summary.total_pnl:.2f}"
    )


if __name__ == "__main__":
    # Test the hook
    print("Testing TradeMindIQ Telegram Hook...")
    
    # Test main menu
    response = trademindiq_hook({})
    print("\n📱 Main Menu Response:")
    print(response['text'][:100] + "...")
    
    # Test portfolio
    response = portfolio_hook({})
    print("\n💼 Portfolio Response:")
    print(response['text'])
    
    # Test analytics
    response = analytics_hook({})
    print("\n📊 Analytics Response:")
    print(response['text'][:100] + "...")
