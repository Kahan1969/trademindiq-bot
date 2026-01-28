#!/usr/bin/env python3
"""
TradeMindIQ Telegram Integration for Clawdbot
==============================================
Handles /trademindiq commands and callback queries.
"""

import json
import sys
import os

# Add TradeMindIQBot to path
sys.path.insert(0, '/Users/kahangabar/Downloads/TradeMindIQBot')

from services.telegram_dashboard import TelegramDashboard

def handle_command(command: str) -> dict:
    """
    Handle Telegram command and return response.
    
    Args:
        command: The command text (e.g., '/trademindiq', 'analytics_full')
        
    Returns:
        Dict with 'text' and optional 'reply_markup' for Telegram
    """
    dashboard = TelegramDashboard()
    
    # Map commands to callback data
    command_map = {
        '/trademindiq': 'main_menu',
        '/portfolio': 'portfolio_dashboard', 
        '/analytics': 'analytics_full',
        '/reports': 'report_weekly',
        '/weekly': 'report_weekly',
        '/monthly': 'report_monthly',
        '/strategy': 'strategies_menu',
    }
    
    callback_data = command_map.get(command, command.lstrip('/'))
    
    return dashboard.generate_menu_message(callback_data)


def handle_callback(callback_data: str) -> dict:
    """
    Handle inline button callback query.
    
    Args:
        callback_data: The callback_data from the button
        
    Returns:
        Dict with 'text' and 'reply_markup' for Telegram
    """
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message(callback_data)


def get_dashboard() -> dict:
    """Get the main dashboard menu."""
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('main_menu')


def get_quick_stats() -> str:
    """Get quick stats for compact display."""
    from services.analytics import PerformanceAnalytics
    
    analytics = PerformanceAnalytics()
    summary = analytics.calculate_performance_summary()
    
    emoji = "🟢" if summary.total_pnl >= 0 else "🔴"
    
    return (
        f"🤖 **TradeMindIQ Quick Stats**\n\n"
        f"**Trades:** {summary.total_trades}\n"
        f"**Win Rate:** {summary.win_rate:.1f}%\n"
        f"**P/L:** {emoji} ${summary.total_pnl:.2f}\n"
        f"**Open:** {summary.total_wins + summary.total_losses} positions"
    )


if __name__ == "__main__":
    # Test the integration
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command.startswith('/'):
            response = handle_command(command)
        else:
            response = handle_callback(command)
        
        print(json.dumps(response, indent=2))
    else:
        # Show main menu
        response = get_dashboard()
        print(json.dumps(response, indent=2))
