# main_paper.py

import os
import sys
import asyncio
import yaml
from dotenv import load_dotenv

# Ensure project root path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Imports
from core.models import Mode
from core.data_client import DataClient
from core.events import EventBus, EventType
from core.execution import ExecutionEngine
from services.scanner import ScannerService
from services.risk import RiskManager
from services.portfolio import PortfolioService
from interfaces.telegram_bot import TelegramBot
from storage.db import TradeRepository
from ai.advisor import AIAdvisor
from ai.signal_advisor import AISignalAdvisor


# Load env file
load_dotenv(os.path.join(PROJECT_ROOT, "env"))


def load_settings():
    with open(os.path.join(PROJECT_ROOT, "config/settings.yaml")) as f:
        return yaml.safe_load(f)


async def main():

    cfg = load_settings()

    # Load secrets
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    openai_key = os.getenv("OPENAI_API_KEY")
    ai_signal_advisor = AISignalAdvisor(openai_key, gatekeep=False)

    if not bot_token or not chat_id:
        raise RuntimeError("Missing bot token or chat_id in env file.")

    mode = Mode[cfg["mode"]]
    bus = EventBus()
    client = DataClient(cfg["exchange"])
    exec_engine = ExecutionEngine(client.exchange, mode)

    telegram = TelegramBot(bot_token, chat_id, bus)
    repo = TradeRepository(cfg["ai"]["db_path"])
    risk = RiskManager()
    portfolio = PortfolioService(repo, risk, bus)

    # AI Advisor
    advisor = None
    if cfg["ai"]["enabled"]:
        advisor = AIAdvisor(cfg["ai"]["db_path"], telegram, openai_key)

    # Event handlers
    async def handle_signal(signal):
        order = await exec_engine.execute_signal(signal)
        bus.publish(EventType.ORDER_PLACED, order)
        portfolio.register_order(order)

    def on_signal(payload):
        signal, candles, indicators = payload
        asyncio.create_task(handle_signal(signal))

    bus.subscribe(EventType.SIGNAL_CREATED, on_signal)

    if advisor:
        def on_trade_closed(trade):
            advisor.run()
        bus.subscribe(EventType.TRADE_CLOSED, on_trade_closed)

    # Scanner start
    scanner = ScannerService(
        client=client,
        bus=bus,
        symbols=cfg["symbols"],
        timeframe=cfg["timeframe"],
        mode=mode,
        equity=cfg["equity"],
        risk_per_trade=cfg["risk_per_trade"],
        r_multiple=cfg["r_multiple"],
        min_rel_vol=cfg["min_rel_vol"],
        min_gap_pct=cfg["min_gap_pct"],
    )

    await scanner.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
