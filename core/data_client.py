from typing import List
import ccxt.async_support as ccxt  # async version


class DataClient:
    def __init__(self, exchange_name: str, api_key: str = "", secret: str = "", password: str = ""):
        ex_class = getattr(ccxt, exchange_name)
        self.exchange = ex_class({
            "apiKey": api_key,
            "secret": secret,
            "password": password,
            "enableRateLimit": True,
        })

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> List[List[float]]:
        return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    async def get_last_price(self, symbol: str) -> float:
        ticker = await self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])
