# TradeMindIQ Telegram Integration Guide

## Quick Start

### Test the Dashboard
```bash
cd ~/Downloads/TradeMindIQBot
./trademindiq_telegram.sh menu
./trademindiq_telegram.sh portfolio
./trademindiq_telegram.sh stats
```

---

## Option 1: Direct Command Access (Simplest)

Add these commands to your Clawdbot configuration:

**In Telegram, just say:**
- "trademindiq" → Opens main dashboard
- "portfolio" → Shows current positions  
- "analytics" → Shows performance metrics
- "weekly" → Shows weekly report
- "stats" → Quick stats summary

---

## Option 2: Clawdbot Subagent (Recommended)

### Create the subagent:
```bash
mkdir -p ~/.clawdbot/subagents/trademindiq
```

### Create agent configuration:
```bash
cat > ~/.clawdbot/subagents/trademindiq/agent.json << 'EOF'
{
  "name": "TradeMindIQ",
  "description": "Trading bot analytics and portfolio dashboard",
  "workspace": "/Users/kahangabar/Downloads/TradeMindIQBot",
  "model": { "primary": "minimax/MiniMax-M2.1" },
  "telegram": {
    "enabled": true,
    "commands": [
      {"command": "trademindiq", "description": "Open dashboard"},
      {"command": "portfolio", "description": "View positions"},
      {"command": "analytics", "description": "View metrics"},
      {"command": "reports", "description": "View reports"}
    ]
  }
}
EOF
```

### Register with Clawdbot:
```bash
clawdbot subagents add trademindiq
```

---

## Option 3: Direct Integration (Advanced)

### 1. Create a simple Python handler
```python
from services.telegram_dashboard import TelegramDashboard

def handle_trademindiq(update):
    dashboard = TelegramDashboard()
    return dashboard.generate_menu_message('main_menu')
```

### 2. Add to your existing Telegram bot
```python
# In your Telegram bot handler:
if text == '/trademindiq':
    response = handle_trademindiq(update)
    send_telegram_message(response['text'], reply_markup=response['reply_markup'])
```

### 3. Handle callbacks
```python
# When user clicks a button:
if callback_data.startswith('trademindiq_'):
    action = callback_data.replace('trademindiq_', '')
    response = handle_trademindiq_callback({'data': action})
    edit_message(response['text'], reply_markup=response['reply_markup'])
```

---

## Available Commands

| Command | Description |
|---------|-------------|
| `/trademindiq` | Main dashboard with buttons |
| `/portfolio` | Open positions & P/L |
| `/analytics` | Full performance report |
| `/reports` | Weekly/Monthly summaries |
| `/stats` | Quick stats summary |

## Button Menu Structure

```
🤖 TradeMindIQ Control Center
├── 📊 Analytics
│   ├── Full Report
│   ├── By Symbol
│   ├── Last 7 Days
│   └── Export JSON
├── 📝 Reports
│   ├── Weekly Report
│   ├── Monthly Report
│   ├── Export Weekly
│   └── Export Monthly
├── 💼 Portfolio
│   └── Dashboard
├── 🎯 Strategies
│   ├── Warrior Momentum
│   ├── Mean Reversion
│   ├── Grid Trading
│   └── Adaptive Grid
└── 🔙 Back
```

---

## Testing

### Test from command line:
```bash
cd ~/Downloads/TradeMindIQBot
python3 services/trademindiq_hook.py
```

### Expected output:
- Main menu with buttons
- Portfolio dashboard
- Analytics report

---

## Files Created

```
TradeMindIQBot/
├── services/
│   ├── telegram_dashboard.py    # Main dashboard with buttons
│   ├── telegram_integration.py  # Command handlers
│   └── trademindiq_hook.py      # Clawdbot hook
├── trademindiq_telegram.sh      # Command wrapper script
└── docs/
    └── TELEGRAM_INTEGRATION.md  # Full documentation
```

---

## Next Steps

1. **Test locally first:**
   ```bash
   cd ~/Downloads/TradeMindIQBot
   ./trademindiq_telegram.sh portfolio
   ```

2. **Add to Clawdbot:**
   ```bash
   clawdbot subagents add trademindiq
   ```

3. **Test from Telegram:**
   - Send `/trademindiq`
   - Click buttons to navigate

4. **Customize as needed:**
   - Edit `services/telegram_dashboard.py` for custom menus
   - Modify button callbacks in `handle_callback()` method
