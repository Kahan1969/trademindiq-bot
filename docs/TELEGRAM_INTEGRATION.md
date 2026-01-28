# TradeMindIQ Subagent for Clawdbot

This subagent handles all TradeMindIQ trading bot commands and dashboard requests.

## Setup

### 1. Create the subagent directory
```bash
mkdir -p ~/.clawdbot/subagents/trademindiq
```

### 2. Create the configuration file
```bash
cat > ~/.clawdbot/subagents/trademindiq/agent.json << 'EOF'
{
  "name": "TradeMindIQ",
  "description": "Trading bot analytics and portfolio dashboard",
  "system": "You are the TradeMindIQ trading bot assistant. You provide performance analytics, portfolio tracking, and strategy information for the crypto trading bot.",
  "workspace": "/Users/kahangabar/Downloads/TradeMindIQBot",
  "model": {
    "primary": "minimax/MiniMax-M2.1"
  },
  "commands": {
    "enabled": [
      "/trademindiq",
      "/portfolio",
      "/analytics", 
      "/reports",
      "/strategy"
    ]
  },
  "telegram": {
    "enabled": true,
    "commands": [
      {
        "command": "trademindiq",
        "description": "Open TradeMindIQ dashboard"
      },
      {
        "command": "portfolio",
        "description": "View current positions"
      },
      {
        "command": "analytics",
        "description": "View performance analytics"
      },
      {
        "command": "reports",
        "description": "View weekly/monthly reports"
      },
      {
        "command": "strategy",
        "description": "View strategy information"
      }
    ]
  }
}
EOF
```

### 3. Create the subagent script
```bash
cat > ~/.clawdbot/subagents/trademindiq/run.sh << 'EOF'
#!/bin/bash
cd /Users/kahangabar/Downloads/TradeMindIQBot
python3 -c "
import sys
sys.path.insert(0, '.')
from services.telegram_dashboard import TelegramDashboard

# Get command from args
command = sys.argv[1] if len(sys.argv) > 1 else 'main_menu'

dashboard = TelegramDashboard()
response = dashboard.generate_menu_message(command)
print(response['text'])
print('\n' + json.dumps(response['reply_markup']))
"
EOF
chmod +x ~/.clawdbot/subagents/trademindiq/run.sh
```

### 4. Register the subagent with Clawdbot
```bash
clawdbot subagents add trademindiq
```

## Usage in Telegram

Send these commands to your Clawdbot:

- `/trademindiq` - Open main dashboard with buttons
- `/portfolio` - Quick portfolio view
- `/analytics` - Performance analytics
- `/reports` - Weekly reports
- `/strategy warrior` - Warrior strategy info
- `/strategy mean_reversion` - Mean reversion info
- `/strategy grid` - Grid trading info

## Callback Query Handling

When users click inline buttons, the subagent handles the callback:

1. User clicks 📊 Analytics
2. Clawdbot receives callback query
3. Calls subagent with `analytics_menu`
4. Returns updated menu with analytics options

## File Structure
```
~/.clawdbot/subagents/trademindiq/
├── agent.json      # Subagent configuration
└── run.sh          # Entry point script
```

## Requirements

- Clawdbot with Telegram plugin enabled
- TradeMindIQBot installed at `/Users/kahangabar/Downloads/TradeMindIQBot`
- Python 3.8+ with sqlite3
