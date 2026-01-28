#!/usr/bin/env python3
"""automated_smoke_test.py
Runs a miniature end-to-end smoke test using mocked exchange and repo.
"""
import asyncio
import time
import logging
from types import SimpleNamespace

logging.basicConfig(level=logging.DEBUG)

from core.events import EventBus, EventType
from core.models import Mode
from services.scanner import ScannerService
from core.execution import ExecutionEngine
from services.portfolio import PortfolioService
from services.risk import RiskManager


class MockExchange:
    def __init__(self):
        self.name = "mock"
        self.id = "mock"

    async def get_ohlcv(self, symbol, timeframe, limit=200):
        now = int(time.time())
        candles = []
        close = 100.0
        for i in range(max(60, limit)):
            ts = now - (limit - i) * 60
            o = close - 0.1
            h = close + 0.2
            l = close - 0.3
            c = close
            v = 1000 + i * 10
            candles.append([ts, o, h, l, c, v])
            close += 0.01
        return candles[-limit:]

    async def create_order(self, symbol, type_, side, qty, price=None, params=None):
        return {
            "id": f"MOCK-{int(time.time())}",
            "status": "filled" if type_ == "market" else "open",
            "price": float(price or 100.0),
            "average": float(price or 100.0),
        }

    async def fetch_order_book(self, symbol, limit=50):
        bids = [[100.0 - i * 0.1, 1 + i] for i in range(limit)]
        asks = [[100.0 + i * 0.1, 1 + i] for i in range(limit)]
        return {"bids": bids, "asks": asks}

    async def fetch_trades(self, symbol, limit=60):
        trades = []
        for i in range(limit):
            side = "buy" if i % 2 == 0 else "sell"
            trades.append({"side": side, "price": 100.0 + i * 0.001, "amount": 0.5 + i * 0.01})
        return trades

    async def cancel_order(self, oid, symbol):
        return {"id": oid, "status": "canceled"}


class MockRepo:
    def __init__(self):
        self.trades = []

    def save_trade(self, trade):
        print("repo.save_trade", getattr(trade, "symbol", None), getattr(trade, "pnl", None))
        self.trades.append(trade)

    def get_recent_trades(self, limit=5):
        return list(self.trades)[-limit:]

    def get_summary_stats(self):
        return {"trades": len(self.trades)}


async def main():
    bus = EventBus()
    exchange = MockExchange()
    client = SimpleNamespace(exchange=exchange)
    # compatibility shims: ScannerService expects get_ohlcv/fetch_ohlcv on client or client.exchange
    client.get_ohlcv = exchange.get_ohlcv
    client.fetch_ohlcv = exchange.get_ohlcv
    exchange.fetch_ohlcv = exchange.get_ohlcv

    risk = RiskManager()
    repo = MockRepo()
    portfolio = PortfolioService(repo, risk, bus, exchange=exchange)
    exec_engine = ExecutionEngine(exchange, Mode.PAPER)

    # Scanner with mock client
    scanner = ScannerService(
        client=client,
        bus=bus,
        symbols=["TEST/USDT"],
        timeframe="1m",
        mode=Mode.PAPER,
        equity=1000,
        risk_per_trade=0.001,
        r_multiple=0.6,
        min_rel_vol=1.0,
        min_gap_pct=0.0,
        ai_advisor=None,
        candle_limit=120,
    )

    print("START: automated smoke test")
    # Force scanner to emit test signals for this smoke run
    if hasattr(scanner, "set_test_force_signals"):
        scanner.set_test_force_signals(True)
    if hasattr(scanner, "reset_forced_symbols"):
        scanner.reset_forced_symbols()

    # handlers
    async def handle_signal(sig):
        print("handle_signal: executing", sig.symbol)
        order = await exec_engine.execute_signal(sig)
        bus.publish(EventType.ORDER_PLACED, order)
        portfolio.register_order(order)

    def on_signal(payload):
        s, candles, indicators = payload
        asyncio.create_task(handle_signal(s))

    bus.subscribe(EventType.SIGNAL_CREATED, on_signal)

    # simple prints for order/trade
    bus.subscribe(EventType.ORDER_PLACED, lambda o: print("ORDER_PLACED ->", getattr(o, "order_id", None)))
    bus.subscribe(EventType.TRADE_CLOSED, lambda t: print("TRADE_CLOSED ->", getattr(t, "symbol", None), getattr(t, "pnl", None)))

    # Run one scan
    print("Running scanner._scan_symbol...")
    await scanner._scan_symbol("TEST/USDT")
    print("AFTER SCAN")

    # simulate price tick to hit target
    await asyncio.sleep(0.5)
    bus.publish(EventType.PRICE_TICK, {"symbol": "TEST/USDT", "price": 9999.0})
    print("Published PRICE_TICK")

    # give tasks time
    await asyncio.sleep(1.0)
    print("Smoke test DONE")

if __name__ == "__main__":
    asyncio.run(main())