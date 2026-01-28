from enum import Enum, auto
from typing import Any, Callable, Dict, List


class EventType(Enum):
    HEARTBEAT = "HEARTBEAT"
    SIGNAL_CREATED = "SIGNAL_CREATED"
    ORDER_PLACED = "ORDER_PLACED"
    TRADE_CLOSED = "TRADE_CLOSED"
    PRICE_TICK = "PRICE_TICK"


class EventBus:
    def __init__(self):
        self._subs: Dict[EventType, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Any], None]):
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event_type: EventType, payload: Any):
        for h in self._subs.get(event_type, []):
            h(payload)
