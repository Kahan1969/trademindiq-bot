# TradeMindIQ - Crypto Trading Bot

<div align="center">

![TradeMindIQ](https://img.shields.io/badge/TradeMindIQ-v1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

**Automated crypto trading bot with multi-strategy support and Telegram dashboard.**

[Features](#features) • [Quick Start](#quick-start) • [Commands](#commands) • [Strategies](#strategies) • [Telegram](#telegram) • [Configuration](#configuration)

</div>

---

## 📋 Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)
3. [Commands](#commands)
   - [Analytics Commands](#analytics-commands)
   - [Report Commands](#report-commands)
   - [Portfolio Commands](#portfolio-commands)
   - [Strategy Commands](#strategy-commands)
   - [Backtesting Commands](#backtesting-commands)
4. [Strategies](#strategies)
5. [Telegram Dashboard](#telegram-dashboard)
6. [Configuration](#configuration)
7. [File Structure](#file-structure)
8. [API Keys](#api-keys)
9. [Troubleshooting](#troubleshooting)

---

## ✨ Features

- **Multi-Strategy Trading**
  - Warrior Momentum (primary)
  - Mean Reversion (RSI/Bollinger Bands)
  - Grid Trading (fixed levels)
  - Adaptive Grid (volatility-adjusted)

- **Analytics & Reporting**
  - Real-time performance tracking
  - Weekly/Monthly reports
  - Symbol-level breakdown
  - Export to JSON

- **Backtesting**
  - Test strategies on historical data
  - Performance comparison
  - Strategy optimization

- **Portfolio Management**
  - Multi-exchange support
  - Position tracking
  - P&L monitoring

- **Telegram Integration**
  - Inline button dashboard
  - Real-time notifications
  - Command-based access

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+
python3 --version

# Required packages (in requirements.txt)
pip install -r requirements.txt
```

### Installation

```bash
# Clone or navigate to the bot directory
cd ~/Downloads/TradeMindIQBot

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp settings.yaml.txt settings.yaml
# Edit settings.yaml with your API keys
```

### First Run

```bash
# Paper trading mode (recommended for testing)
python3 main_paper.py

# Check logs
tail -f logs/trademindiq.log
```

---

## 📟 Commands

### Analytics Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `analytics` | Full performance report | `/analytics` or `show analytics` |
| `analytics symbols` | Performance by symbol | `/analytics symbols` |
| `analytics 7day` | Last 7 days report | `/analytics 7day` |
| `analytics json` | Export to JSON | `/analytics json` |
| `stats` | Quick stats summary | `/stats` or `quick stats` |

**Examples:**
```
/analytics
/analytics symbols
/analytics 7day
/stats
```

---

### Report Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `weekly` | Weekly performance report | `/weekly` or `weekly report` |
| `monthly` | Monthly performance review | `/monthly` or `monthly report` |
| `export weekly` | Export weekly to JSON | `/export weekly` |
| `export monthly` | Export monthly to JSON | `/export monthly` |
| `goals` | Set/View performance goals | `/goals` |

**Examples:**
```
/weekly
/monthly
/export weekly
/export monthly
/goals
```

**Sample Weekly Report:**
```
============================================================
WEEKLY PERFORMANCE REPORT
2026-01-26 to 2026-02-01
============================================================

📊 SUMMARY
----------------------------------------
Total Trades:    26
Win Rate:        42.3%
Net P/L:         $2.59
Best Symbol:     AAVE/USDT
Worst Symbol:    NEAR/USDT

📅 DAILY BREAKDOWN
----------------------------------------
🟢 2026-01-26: 2 trades, $1.39
🟢 2026-01-27: 23 trades, $0.48
🟢 2026-01-28: 1 trades, $0.72

🎯 GOALS
----------------------------------------
✅ win_rate_40%
✅ positive_pnl
```

---

### Portfolio Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `portfolio` | Open positions dashboard | `/portfolio` or `show portfolio` |
| `positions` | List all positions | `/positions` |
| `exposure` | Exposure by symbol/side | `/exposure` |

**Examples:**
```
/portfolio
/positions
/exposure
```

**Sample Portfolio Dashboard:**
```
🤖 **TradeMindIQ Dashboard**

**Equity:** $-811.89
**Net P/L:** 🔴 $-1,311.89
**Open:** 3 positions

🔴 BTC/USDT   BUY  $-984.00
🔴 SOL/USDT   BUY  $-190.00
🟢 ETH/USDT   BUY  $  20.00
```

---

### Strategy Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `strategy` | List all strategies | `/strategy` or `show strategies` |
| `strategy warrior` | Warrior Momentum info | `/strategy warrior` |
| `strategy mean_reversion` | Mean Reversion info | `/strategy mean_reversion` |
| `strategy grid` | Grid Trading info | `/strategy grid` |
| `strategy adaptive` | Adaptive Grid info | `/strategy adaptive` |
| `backtest` | Run backtest | `/backtest` |
| `backtest warrior` | Backtest Warrior | `/backtest warrior` |
| `backtest mean` | Backtest Mean Reversion | `/backtest mean` |

**Examples:**
```
/strategy
/strategy warrior
/strategy mean_reversion
/strategy grid
/backtest
/backtest warrior
```

**Sample Strategy Info:**
```
⚔️ **Warrior Momentum Strategy**

Rules:
• Trade only during high-vol session
• Require gap + high RVOL
• EMAs stacked: price > EMA9 > EMA20 > EMA50
• ATR-based stop placement
• R-multiple target (2x risk)

Parameters:
• min_rel_vol: 2.0
• min_gap_pct: 0.5
• session: EU/US overlap
```

---

### Backtesting Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `backtest` | Run default backtest | `/backtest` |
| `backtest full` | Full backtest report | `/backtest full` |
| `backtest json` | Export to JSON | `/backtest json` |

**Examples:**
```
/backtest
/backtest full
/backtest json
```

**Sample Backtest Report:**
```
============================================================
TradeMindIQ Backtest Report
============================================================

Period: 2026-01-26 to 2026-01-27
Symbols: BTC/USDT, ETH/USDT
Initial Equity: $500.00

📊 PERFORMANCE SUMMARY
----------------------------------------
Total Trades:    0
Win Rate:        0.0%
Total P/L:       $0.00
Max Drawdown:    0.00%
```

---

## 🎯 Strategies

### 1. Warrior Momentum (Primary)

**File:** `strategies/warrior_momentum.py`

**Logic:**
- Trade only during high-volatility session (EU/US overlap)
- Require clear gap + high relative volume
- Price must be above stacked EMAs (EMA9 > EMA20 > EMA50)
- ATR-based stop placement
- R-multiple profit target (2x risk)

**Best For:** Trending markets with clear momentum

---

### 2. Mean Reversion

**File:** `strategies/mean_reversion.py`

**Logic:**
- RSI oversold (< 30) + near lower Bollinger Band = LONG
- RSI overbought (> 70) + near upper Bollinger Band = SHORT
- VWAP for trend confirmation

**Indicators:**
- RSI (14-period)
- Bollinger Bands (20, 2σ)
- VWAP (390 periods)

**Best For:** Range-bound markets

---

### 3. Grid Trading

**File:** `strategies/grid_trading.py`

**Logic:**
- Place orders at fixed price intervals
- Buy when price drops to grid level
- Sell when price rises to grid level
- Profit from volatility within range

**Parameters:**
- grid_levels: 5
- grid_spacing: 0.5%
- range_width: 5%

**Best For:** Sideways/volatile markets

---

### 4. Adaptive Grid

**File:** `strategies/grid_trading.py`

**Logic:**
- Grid spacing adjusts to volatility
- Wider grids during high volatility
- Tighter grids during low volatility

**Parameters:**
- volatility_lookback: 20
- volatility_multiplier: 1.5

**Best For:** Variable volatility environments

---

## 📱 Telegram Dashboard

### Setup

**Option 1: Clawdbot Integration**
```bash
clawdbot subagents add trademindiq --workspace ~/Downloads/TradeMindIQBot
```

**Option 2: Direct Commands**
Just say these in Telegram:
- `trademindiq` → Main dashboard with buttons
- `portfolio` → Open positions
- `analytics` → Performance metrics
- `reports` → Weekly/Monthly reports

### Dashboard Menu

```
🤖 TradeMindIQ Control Center

📊 Analytics
├── 📊 Full Report
├── 📈 By Symbol
├── 📅 Last 7 Days
└── 📋 Export JSON

📝 Reports
├── 📅 Weekly Report
├── 📆 Monthly Report
├── 📤 Export Weekly
└── 📤 Export Monthly

💼 Portfolio
└── 💼 Dashboard

🎯 Strategies
├── ⚔️ Warrior Momentum
├── 📉 Mean Reversion
├── 📐 Grid Trading
└── 🔄 Adaptive Grid
```

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/trademindiq` | Open main dashboard |
| `/portfolio` | View positions |
| `/analytics` | View metrics |
| `/reports` | View reports |
| `/stats` | Quick stats |

---

## ⚙️ Configuration

### settings.yaml

```yaml
# Trading mode: paper | live
trading:
  mode: "paper"

# Exchange: kucoin | BTCC
exchange: kucoin

# Trading parameters
timeframe: 1m
symbols:
  - BTC/USDT
  - ETH/USDT
  - SOL/USDT
  # ... more symbols

equity: 500
risk_usd_per_trade: 50
r_multiple: 2.0

# Strategy parameters
breakout_lookback: 12
min_body_pct: 0.55
min_vol_spike: 1.8

# Telegram notifications
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  heartbeat:
    enabled: true
    interval_minutes: 10
```

### Environment Variables

```bash
# API Keys (in settings.yaml or .env)
export ALPACA_API_KEY="your_alpaca_key"
export ALPACA_SECRET_KEY="your_alpaca_secret"
export BTCC_API_KEY="your_btcc_key"
export BTCC_SECRET_KEY="your_btcc_secret"
export CRYPTOPANIC_TOKEN="your_cryptopanic_token"
export TELEGRAM_BOT_TOKEN="your_bot_token"
```

---

## 📁 File Structure

```
TradeMindIQBot/
├── main_paper.py           # Main entry point (paper trading)
├── main_live.py            # Main entry point (live trading)
├── settings.yaml           # Configuration file
├── settings.yaml.txt       # Template
├── requirements.txt        # Python dependencies
│
├── core/                   # Core trading engine
│   ├── execution.py        # Order execution
│   ├── exchange_factory.py # Exchange adapters
│   ├── indicators.py       # Technical indicators
│   ├── models.py           # Data models
│   └── time_filters.py     # Session filters
│
├── strategies/             # Trading strategies
│   ├── base.py             # Base strategy class
│   ├── warrior_momentum.py # Warrior Momentum
│   ├── mean_reversion.py   # Mean Reversion
│   └── grid_trading.py     # Grid & Adaptive Grid
│
├── services/               # Business logic
│   ├── analytics.py        # Performance analytics
│   ├── backtest.py         # Backtesting engine
│   ├── reports.py          # Weekly/Monthly reports
│   ├── portfolio.py        # Portfolio tracking
│   ├── scanner.py          # Opportunity scanner
│   ├── news_service.py     # News attachment
│   ├── orderflow.py        # Order flow analysis
│   ├── telegram_dashboard.py  # Telegram dashboard
│   └── telegram_integration.py # Telegram commands
│
├── exchanges/              # Exchange adapters
│   ├── kucoin.py           # KuCoin adapter
│   └── btcc.py             # BTCC adapter
│
├── interfaces/             # External interfaces
│   └── alpaca.py           # Alpaca (equities)
│
├── storage/                # Data storage
│   └── trades.db           # SQLite database
│
├── logs/                   # Log files
├── config/                 # Config files
├── ai/                     # AI/ML models
├── docs/                   # Documentation
└── assets/                 # Static assets
```

---

## 🔑 API Keys

### KuCoin (Crypto Spot)

1. Go to https://www.kucoin.com/account/api
2. Create new API key
3. Enable: Spot trading, Reading
4. Copy Key and Secret to settings.yaml

### BTCC (Crypto Futures)

1. Go to https://www.btcc.com/en-us/account/api
2. Create API credentials
3. Copy to settings.yaml under `btcc:` section

### Alpaca (Equities - Optional)

1. Go to https://alpaca.markets/
2. Create paper/live account
3. Generate API key and secret
4. Copy to settings.yaml under `alpaca:` section

### Telegram Bot

1. Message @BotFather on Telegram
2. Create new bot: `/newbot`
3. Copy bot token to settings.yaml

---

## 🔧 Troubleshooting

### Bot won't start

```bash
# Check Python version
python3 --version

# Install dependencies
pip install -r requirements.txt

# Check config
cat settings.yaml | grep -v "^#" | grep -v "^$"
```

### No trades executing

```bash
# Check if market is open
python3 -c "from core.time_filters import TimeFilter; print(TimeFilter().is_market_open())"

# Check API connectivity
python3 -c "from exchanges.kucoin import KuCoin; k = KuCoin(); print(k.test_connection())"

# Check logs
tail -50 logs/trademindiq.log
```

### Telegram not working

```bash
# Test bot token
curl -s https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Check chat ID
curl -s https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

### Database issues

```bash
# Reset trades database
rm storage/trades.db
python3 main_paper.py  # Will recreate

# View trades
sqlite3 storage/trades.db "SELECT * FROM trades LIMIT 10"
```

---

## 📊 Performance Metrics

### Key Metrics Tracked

| Metric | Description | Target |
|--------|-------------|--------|
| Win Rate | % of profitable trades | > 40% |
| P/L | Net profit/loss | Positive |
| Avg Hold Time | Average trade duration | < 5 min |
| Max Drawdown | Largest peak-to-trough | < 10% |
| Sharpe Ratio | Risk-adjusted return | > 1.0 |

### Weekly Goals

- [ ] Win Rate: 40%+
- [ ] Positive P&L
- [ ] 50+ trades
- [ ] No losses > $100

---

## 📝 Logging

Logs are written to `logs/trademindiq.log`

```bash
# View recent logs
tail -f logs/trademindiq.log

# Search for errors
grep -i error logs/trademindiq.log

# View trade logs
grep -i "TRADE" logs/trademindiq.log
```

Log levels:
- `INFO` - Normal operations
- `WARNING` - Issues requiring attention
- `ERROR` - Errors requiring action

---

## 🔄 Updating

```bash
# Pull latest changes
cd ~/Downloads/TradeMindIQBot
git pull

# Install new dependencies
pip install -r requirements.txt

# Restart bot
pkill -f main_paper.py
python3 main_paper.py &
```

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-strategy`)
3. Commit changes (`git commit -am 'Add new strategy'`)
4. Push to branch (`git push origin feature/new-strategy`)
5. Create Pull Request

---

## 📞 Support

- **Issues:** Open a GitHub issue
- **Telegram:** @your_bot
- **Documentation:** See /docs folder

---

<div align="center">

**TradeMindIQ v1.0.0** | Built with ❤️

</div>
