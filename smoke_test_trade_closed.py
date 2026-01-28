from interfaces.telegram_bot import TelegramBot


class DummyTrade:
    def __init__(self):
        self.symbol = "SOL/USDT"
        self.exit_reason = "STOP"
        self.result = "CLOSED"
        self.pnl = None
        self.realized_pnl = None
        self.meta = {
            "status": "LOSS",
            "pnl_usd": -50.00,
            "pnl_r": -1.00,
        }


trade = DummyTrade()

# Load your cfg the same way your bot does (adjust if needed)
import os
import yaml

cfg = yaml.safe_load(open("settings.yaml", "r")) or {}

# Prefer env to avoid placeholder values in settings.yaml
bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg.get("telegram") or {}).get("bot_token")
chat_id = os.getenv("TELEGRAM_CHAT_ID") or (cfg.get("telegram") or {}).get("chat_id")

# Safe diagnostics (do NOT print full token)
print("chat_id:", chat_id)
if bot_token:
    tok = str(bot_token).strip()
    print("token looks like:", tok[:8] + "..." + tok[-6:], "len=", len(tok), "has_colon=", (":" in tok))
else:
    print("token missing")

# Force Telegram debug to see API responses
os.environ.setdefault("TELEGRAM_DEBUG", "1")

tg = TelegramBot(
    token=str(bot_token).strip(),
    chat_id=str(chat_id).strip(),
    cfg=cfg,
)

# Call the handler directly
# NOTE: on_trade expects a trade-like object, not an event dict.
tg.on_trade(trade)
print("Sent synthetic TRADE_CLOSED to Telegram")
