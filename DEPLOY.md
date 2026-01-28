# TradeMindIQ Bot Deployment

## Deploy to Streamlit Cloud (Free)

### 1. Push to GitHub
```bash
cd ~/Downloads/TradeMindIQBot
git init
git add .
git commit -m "Initial trade bot deployment"
gh repo create trademindiq-bot --public --source=. --push
```

### 2. Deploy
- Go to https://share.streamlit.io
- Sign in with GitHub
- Select your `trademindiq-bot` repo
- Set: `Main file path: trademindiq_app.py`
- Click "Deploy"

### 3. Configuration
Streamlit Cloud will automatically use `requirements.txt` or `pyproject.toml`.

## Environment Variables (Streamlit Cloud)
Set these in Streamlit Cloud Settings > Secrets:
```toml
OPENAI_API_KEY = "your-key-here"
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
```

## Local Development
```bash
cd ~/Downloads/TradeMindIQBot
./venv/bin/python -m streamlit run trademindiq_app.py
```

## Access
- Local: http://localhost:8501
- Cloud: https://your-app-name.streamlit.app
