from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from core.models import Signal


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        candles: List[List[float]],
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        ...
