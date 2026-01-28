#!/usr/bin/env python3
"""smoke_test.py
Quick smoke-test script to simulate EventBus events for pipeline verification.
Run: python smoke_test.py
"""
import time
from types import SimpleNamespace

from core.events import EventBus, EventType


def main():
    bus = EventBus()

    def on_heartbeat(p):
        print("[HEARTBEAT]", p)

    def on_signal(payload):
        s, candles, indicators = payload
        print("[SIGNAL_CREATED] symbol=", getattr(s, "symbol", None), "entry=", getattr(s, "entry", None))

    def on_order(o):
        print("[ORDER_PLACED] order_id=", getattr(o, "order_id", None), "filled=", getattr(o, "filled_price", getattr(o, "entry", None)))

    def on_price_tick(p):
        print("[PRICE_TICK]", p)

    def on_trade(t):
        print("[TRADE_CLOSED]", getattr(t, "symbol", None), "pnl=", getattr(t, "realized_pnl", getattr(t, "pnl", None)))

    # subscribe handlers
    bus.subscribe(EventType.HEARTBEAT, on_heartbeat)
    bus.subscribe(EventType.SIGNAL_CREATED, on_signal)
    bus.subscribe(EventType.ORDER_PLACED, on_order)
    bus.subscribe(EventType.PRICE_TICK, on_price_tick)
    bus.subscribe(EventType.TRADE_CLOSED, on_trade)

    # build fake signal / payloads
    symbol = "TEST/USDT"
    signal = SimpleNamespace(symbol=symbol, timeframe="1m", entry=100.0, stop=99.9, target=100.2, qty=1.0)
    candles = [[int(time.time()), 0, 0, 0, 100.0, 0]]
    indicators = {"rel_vol": 1.2, "gap_pct": 0.5}

    print("--> publishing heartbeat")
    bus.publish(EventType.HEARTBEAT, {"ts": int(time.time()), "mode": "PAPER"})
    time.sleep(0.1)

    print("--> publishing SIGNAL_CREATED")
    bus.publish(EventType.SIGNAL_CREATED, (signal, candles, indicators))
    time.sleep(0.1)

    print("--> publishing ORDER_PLACED (paper)")
    order = SimpleNamespace(order_id="PAPER-TEST-1", signal=signal, filled_price=signal.entry, status="filled", qty=signal.qty, stop=signal.stop, target=signal.target, meta={})
    bus.publish(EventType.ORDER_PLACED, order)
    time.sleep(0.1)

    print("--> publishing PRICE_TICK (simulate target hit)")
    bus.publish(EventType.PRICE_TICK, {"symbol": symbol, "price": 100.25})
    time.sleep(0.1)

    print("--> publishing TRADE_CLOSED")
    trade = SimpleNamespace(symbol=symbol, realized_pnl=0.25)
    bus.publish(EventType.TRADE_CLOSED, trade)

    print("Smoke test completed")


if __name__ == "__main__":
    main()
