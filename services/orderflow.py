import math

class OrderFlowService:
    def __init__(self, exchange, book_depth=8, tape_trades=60):
        self.exchange = exchange
        self.book_depth = int(book_depth)
        self.tape_trades = int(tape_trades)

    async def snapshot(self, symbol: str):
        # Order book
        ob = await self.exchange.fetch_order_book(symbol, limit=max(20, self.book_depth * 2))
        bids = ob.get("bids") or []
        asks = ob.get("asks") or []

        # Sum top N by notional
        bd = bids[: self.book_depth]
        ad = asks[: self.book_depth]

        bid_notional = sum(float(p) * float(a) for p, a in bd) if bd else 0.0
        ask_notional = sum(float(p) * float(a) for p, a in ad) if ad else 0.0
        bid_ask_ratio = (bid_notional / ask_notional) if ask_notional > 0 else math.inf

        # Tape (recent trades)
        trades = await self.exchange.fetch_trades(symbol, limit=self.tape_trades)
        buy_notional = 0.0
        sell_notional = 0.0
        for t in trades or []:
            side = (t.get("side") or "").lower()
            price = float(t.get("price") or 0.0)
            amount = float(t.get("amount") or 0.0)
            notional = price * amount
            if side == "buy":
                buy_notional += notional
            elif side == "sell":
                sell_notional += notional

        buy_sell_ratio = (buy_notional / sell_notional) if sell_notional > 0 else math.inf

        return {
            "bid_notional": bid_notional,
            "ask_notional": ask_notional,
            "bid_ask_ratio": bid_ask_ratio,
            "buy_notional": buy_notional,
            "sell_notional": sell_notional,
            "buy_sell_ratio": buy_sell_ratio,
        }
