import time, math
from types import SimpleNamespace
from interfaces.telegram_bot import TelegramBot

# ---- build fake candle data ----
now = int(time.time())
candles = []
closes = []
price = 100.0

for i in range(60):
    ts = (now - (59 - i) * 60) * 1000
    price += math.sin(i / 6) * 0.2
    o = price - 0.05
    h = price + 0.10
    l = price - 0.10
    c = price
    v = 1000 + i
    candles.append([ts, o, h, l, c, v])
    closes.append(c)

# ---- simple EMA helper ----
def ema(arr, n):
    k = 2 / (n + 1)
    out = []
    e = arr[0]
    for x in arr:
        e = x * k + e * (1 - k)
        out.append(e)
    return out

ema9  = ema(closes, 9)
ema20 = ema(closes, 20)
ema50 = ema(closes, 50)

import os

tg = TelegramBot(
    token=os.getenv("TELEGRAM_BOT_TOKEN"),
    chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    cfg={
        "telegram": {
            "format": "legacy",
            "include_chart": True,
            "include_news": True,
            "include_sentiment": True,
        }
    }
)


trade = SimpleNamespace(
    symbol="SOL/USDT",
    entry_price=100.0,
    exit_price=101.0,
    qty=1.0,
    exit_reason="TARGET",
    meta={
        "status": "WIN",
        "pnl_usd": 100.0,
        "pnl_r": 2.0,
        "hold_seconds": 90,
        "signal_snapshot": {
            "sentiment_label": "Bullish",
            "sentiment_score": 0.67,
            "news_links": [
                {"title": "Example catalyst headline", "url": "https://example.com/news1"}
            ],
            "candles": candles,
            "ema9": ema9,
            "ema20": ema20,
            "ema50": ema50,
        }
    }
)

print("LOCAL PREVIEW:\n", tg._format_trade_closed_legacy(trade))
tg.on_trade(trade)
print("Sent chart trade-close.")

