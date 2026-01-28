#!/bin/bash
# TradeMindIQ Telegram Command Wrapper
# Usage: ./trademindiq_telegram.sh [command]
# 
# Commands:
#   menu      - Main dashboard menu (default)
#   portfolio - Portfolio dashboard
#   analytics - Full analytics report
#   weekly    - Weekly report
#   monthly   - Monthly report
#   stats     - Quick stats
#
# Add these to your Telegram bot commands:
# /trademindiq - Open dashboard
# /portfolio - View positions
# /analytics - View performance

cd /Users/kahangabar/Downloads/TradeMindIQBot

COMMAND=${1:-menu}

case $COMMAND in
    menu)
        python3 -c "
import sys
sys.path.insert(0, '.')
from services.telegram_dashboard import TelegramDashboard
d = TelegramDashboard()
r = d.generate_menu_message('main_menu')
print(r['text'])
print('---KEYBOARD---')
print(json.dumps(r['reply_markup']))
" | python3 -m json.tool 2>/dev/null || echo "Run with Python to get keyboard"
        ;;
    portfolio)
        python3 services/trademindiq_hook.py portfolio
        ;;
    analytics)
        python3 services/trademindiq_hook.py analytics
        ;;
    weekly)
        python3 services/trademindiq_hook.py report_weekly
        ;;
    monthly)
        python3 services/trademindiq_hook.py report_monthly
        ;;
    stats)
        python3 -c "
import sys
sys.path.insert(0, '.')
from services.analytics import PerformanceAnalytics
from services.trademindiq_hook import quick_stats
print(quick_stats({}))
"
        ;;
    *)
        echo "Usage: $0 [menu|portfolio|analytics|weekly|monthly|stats]"
        ;;
esac
