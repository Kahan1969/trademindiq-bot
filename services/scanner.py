# services/scanner.py
import asyncio
import time
from typing import Any, Dict, List, Optional

import numpy as np
import logging

from core.events import EventBus, EventType
from core.models import Mode, Signal, Side


logger = logging.getLogger(__name__)


def _timeframe_to_seconds(tf: str) -> int:
    tf = tf.strip().lower()
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 3600
    if tf.endswith("d"):
        return int(tf[:-1]) * 86400
    return 60


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return values
    alpha = 2.0 / (period + 1.0)
    out = np.empty_like(values, dtype=float)
    out[0] = float(values[0])
    for i in range(1, len(values)):
        out[i] = alpha * float(values[i]) + (1.0 - alpha) * out[i - 1]
    return out


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(close)
    if n == 0:
        return np.array([], dtype=float)

    tr = np.empty(n, dtype=float)
    tr[0] = float(high[0] - low[0])
    for i in range(1, n):
        h_l = float(high[i] - low[i])
        h_pc = abs(float(high[i] - close[i - 1]))
        l_pc = abs(float(low[i] - close[i - 1]))
        tr[i] = max(h_l, h_pc, l_pc)

    atr = np.empty(n, dtype=float)
    atr[0] = tr[0]
    alpha = 1.0 / float(period)
    for i in range(1, n):
        atr[i] = (1.0 - alpha) * atr[i - 1] + alpha * tr[i]
    return atr


def _rolling_mean(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.full_like(values, np.nan, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    csum = np.cumsum(values, dtype=float)
    out[period - 1] = csum[period - 1] / period
    for i in range(period, len(values)):
        out[i] = (csum[i] - csum[i - period]) / period
    return out


class ScannerService:
    """
    Scans symbols, computes indicators, generates Warrior-style momentum signals,
    optionally AI-gates them, then publishes events.

    Publishes:
      - EventType.HEARTBEAT (dict payload)
      - EventType.SIGNAL_CREATED ((signal, candles, indicators))
    """
    
    def set_loosen_factor(self, value: float) -> None:
        # clamp to sensible bounds
        v = float(value)
        if v < 0.0:
            v = 0.0
        if v > 0.60:
            v = 0.60
        self.loosen_factor = v

    def set_mode_preset(self, preset: str) -> None:
        p = preset.strip().lower()
        if p == "strict":
            self.set_loosen_factor(0.0)
        elif p == "loose":
            self.set_loosen_factor(0.30)
        else:
            # allow custom like "loose:0.4"
            if ":" in p:
                try:
                    self.set_loosen_factor(float(p.split(":", 1)[1]))
                except Exception:
                    pass

    # Test helpers
    def set_test_force_signals(self, enabled: bool) -> None:
        self.test_force_signals = bool(enabled)

    def reset_forced_symbols(self) -> None:
        self._forced_symbols = set()


    def __init__(
        self,
        client: Any,
        bus: EventBus,
        symbols: List[str],
        timeframe: str,
        mode: Mode,
        equity: float,
        risk_per_trade: float,
        r_multiple: float,
        min_rel_vol: float,
        min_gap_pct: float,
        ai_advisor: Optional[Any] = None,
        candle_limit: int = 200,
        min_price: float = 0.10,
        max_price: float = 100000.0,
        min_atr_fraction: float = 0.0008,  # ~0.08% of price
        breakout_lookback: int = 12,
        debug_heartbeat: bool = False,
        heartbeat: Optional[Any] = None,   # ← ADD THIS
        orderflow: Optional[Any] = None,
        min_bid_ask_ratio: float = 1.25,
        min_buy_sell_ratio: float = 1.15,
        loosen_factor: float = 0.30,  # 30% less strict for testing
    ):
        self.client = client
        self.bus = bus
        self.symbols = symbols
        self.timeframe = timeframe
        self.mode = mode
        self.equity = float(equity)

        self.risk_per_trade = float(risk_per_trade)
        self.r_multiple = float(r_multiple)
        self.min_rel_vol = float(min_rel_vol)
        self.min_gap_pct = float(min_gap_pct)

        self.ai_advisor = ai_advisor

        self.candle_limit = int(candle_limit)
        self.min_price = float(min_price)
        self.max_price = float(max_price)
        self.min_atr_fraction = float(min_atr_fraction)
        self.breakout_lookback = int(breakout_lookback)
        self.debug_heartbeat = bool(debug_heartbeat)
        self.heartbeat = heartbeat

        # Order-flow gating (optional)
        self.orderflow = orderflow
        self.min_bid_ask_ratio = float(min_bid_ask_ratio)
        self.min_buy_sell_ratio = float(min_buy_sell_ratio)

        # 0.30 means "30% less strict"
        self.loosen_factor = float(loosen_factor)

        # test flags (used in testing to force scanner to emit signals)
        self.test_force_signals = False
        self.test_force_once_per_symbol = True
        self._forced_symbols = set()

        # perf: skip work when candle hasn't changed
        self._last_ts: Dict[str, int] = {}

    async def run_forever(self) -> None:
        tf_seconds = _timeframe_to_seconds(self.timeframe)

        while True:
            loop_start = time.time()

            # heartbeat each loop
            self.bus.publish(
                EventType.HEARTBEAT,
                {"ts": int(time.time()), "mode": getattr(self.mode, "name", str(self.mode))},
            )

            for symbol in self.symbols:
                try:
                    await self._scan_symbol(symbol)
                    
                    if self.heartbeat:
                     self.heartbeat.on_scan()

                except Exception:
                    # keep scanner alive no matter what one symbol does
                    continue

            elapsed = time.time() - loop_start
            sleep_for = max(1.0, float(tf_seconds) - elapsed)
            await asyncio.sleep(sleep_for)


    async def _scan_symbol(self, symbol: str) -> None:
        candles = await self._fetch_candles(symbol)
        last_price = float(candles[-1][4])  # close

        logger.debug("_scan_symbol: %s last_price=%s candles=%d", symbol, last_price, len(candles))

        self.bus.publish(
            EventType.PRICE_TICK,
            {
                "symbol": symbol,
                "price": last_price,
            },
        )

        logger.debug("PRICE_TICK published for %s @ %s", symbol, last_price)

        if not candles or len(candles) < 60:
            return

        last_ts = int(candles[-1][0])
        if self._last_ts.get(symbol) == last_ts:
            return
        self._last_ts[symbol] = last_ts

        indicators = self._compute_indicators(candles)

        context: Dict[str, Any] = {
            "equity": self.equity,
            "symbol": symbol,
            "timeframe": self.timeframe,
            # Optional enrichment hooks (if you populate elsewhere):
            # "sentiment_score": ...,
            # "sentiment_label": ...,
            # "news_links": [...],
        }

        # Order-flow snapshot (Level2/Tape equivalent)
        if getattr(self, "orderflow", None) is not None:
            try:
                of = await self.orderflow.snapshot(symbol)
                # persist to indicators so downstream exporters/telegram have access
                indicators["orderflow"] = of or {}
                context.update(of or {})
            except Exception:
                of = {}
                indicators["orderflow"] = {}

        # --- TEST MODE: force signals for pipeline testing ---
        if getattr(self, "test_force_signals", False):
            if (not self.test_force_once_per_symbol) or (symbol not in self._forced_symbols):
                forced = self._force_test_signal(symbol, candles, indicators, context)
                if forced:
                    self._forced_symbols.add(symbol)
                    self.bus.publish(EventType.SIGNAL_CREATED, (forced, candles, indicators))
                    return

        signal = self._generate_signal(symbol, candles, indicators, context)
        if signal:
            logger.info("Signal generated for %s entry=%.6f stop=%.6f target=%.6f", symbol, signal.entry, signal.stop, signal.target)
        else:
            logger.debug("No signal for %s", symbol)

        # Optional per-symbol debug heartbeat so you can see if filters are too tight
        if self.debug_heartbeat:
            try:
                c = float(indicators["close"][-1])
                rv = float(indicators["rel_vol"])
                gap = float(indicators["gap_pct"])
                ema9 = float(indicators["ema9"][-1])
                ema20 = float(indicators["ema20"][-1])
                ema50 = float(indicators["ema50"][-1])
                brk_lvl = float(indicators["breakout_level"])
                atr = float(indicators["atr14"][-1]) if len(indicators["atr14"]) else 0.0
                loosen = self.loosen_factor
                ema_tol = loosen * atr
                breakout_buffer = loosen * atr
                ema_ok = (c > ema9 - ema_tol) and (ema9 > ema20 - ema_tol) and (ema20 > ema50 - ema_tol)
                brk_ok = c > (brk_lvl - breakout_buffer)
                self.bus.publish(
                    EventType.HEARTBEAT,
                    {
                        "symbol": symbol,
                        "close": c,
                        "rv": rv,
                        "gap": gap,
                        "ema_ok": ema_ok,
                        "brk_ok": brk_ok,
                        "signal": bool(signal),
                    },
                )
            except Exception:
                pass

        if not signal:
            return

        # --- AI review gate (optional) ---
        if self.ai_advisor is not None:
            try:
                review = self.ai_advisor.review(signal, indicators, context)
                # support either (approved, comment) or (approved, comment, conf)
                approved = False
                ai_comment = ""
                ai_conf = None
                if isinstance(review, tuple):
                    if len(review) >= 1:
                        approved = bool(review[0])
                    if len(review) >= 2:
                        ai_comment = review[1]
                    if len(review) >= 3:
                        ai_conf = review[2]
                else:
                    # unexpected return; treat as approved to avoid blocking
                    approved = True

                indicators["_ai_comment"] = ai_comment
                if ai_conf is not None:
                    indicators["_ai_conf"] = ai_conf
                indicators["_ai_approved"] = bool(approved)
                if not approved:
                    return
            except Exception:
                # AI should never break the trading flow
                pass

        self.bus.publish(EventType.SIGNAL_CREATED, (signal, candles, indicators))

    async def _fetch_candles(self, symbol: str) -> List[List[float]]:
        """
        Your DataClient.get_ohlcv is async -> MUST be awaited.
        Supports a few common client layouts.
        """
        if hasattr(self.client, "get_ohlcv"):
            return await self.client.get_ohlcv(symbol, self.timeframe, limit=self.candle_limit)

        if hasattr(self.client, "fetch_ohlcv"):
            return await self.client.fetch_ohlcv(symbol, self.timeframe, limit=self.candle_limit)

        if hasattr(self.client, "exchange") and hasattr(self.client.exchange, "fetch_ohlcv"):
            return await self.client.exchange.fetch_ohlcv(symbol, self.timeframe, limit=self.candle_limit)

        raise AttributeError("Data client has no async get_ohlcv/fetch_ohlcv method")

    def _compute_indicators(self, candles: List[List[float]]) -> Dict[str, Any]:
        arr = np.array(candles, dtype=float)
        ts = arr[:, 0].astype(np.int64)
        o = arr[:, 1]
        h = arr[:, 2]
        l = arr[:, 3]
        c = arr[:, 4]
        v = arr[:, 5]

        ema9 = _ema(c, 9)
        ema20 = _ema(c, 20)
        ema50 = _ema(c, 50)
        atr14 = _atr(h, l, c, 14)

        vol_ma20 = _rolling_mean(v, 20)
        rel_vol = float(v[-1] / vol_ma20[-1]) if not np.isnan(vol_ma20[-1]) and vol_ma20[-1] > 0 else 0.0
        vol_spike = float(v[-1] / vol_ma20[-1]) if not np.isnan(vol_ma20[-1]) and vol_ma20[-1] > 0 else 0.0

        prev_close = float(c[-2]) if len(c) >= 2 else float(c[-1])
        gap_pct = ((float(c[-1]) - prev_close) / prev_close * 100.0) if prev_close != 0 else 0.0

        lookback = min(self.breakout_lookback, len(h) - 1)
        if lookback >= 2:
            breakout_level = float(np.max(h[-(lookback + 1) : -1]))
        else:
            breakout_level = float(h[-1])

        return {
            "ts": ts,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "ema9": ema9,
            "ema20": ema20,
            "ema50": ema50,
            "atr14": atr14,
            "rel_vol": rel_vol,
            "vol_spike": vol_spike,
            "gap_pct": gap_pct,
            "breakout_level": breakout_level,
        }

    def _generate_signal(
        self,
        symbol: str,
        candles: List[List[float]],
        ind: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        close = float(ind["close"][-1])

        # -------------------------
        # 30% loosen factor
        # -------------------------
        loosen = self.loosen_factor  # default 0.30

        rel_vol_min = self.min_rel_vol * (1.0 - loosen)
        gap_min = self.min_gap_pct * (1.0 - loosen)

        if close < self.min_price or close > self.max_price:
            return None

        rel_vol = float(ind["rel_vol"])
        gap_pct = float(ind["gap_pct"])

        if rel_vol < rel_vol_min:
            return None
        if gap_pct < gap_min:
            return None

        # Candle structure filter (Warrior-style)
        if not self._candle_structure_ok(candles):
            return None

        # Volume spike filter
        min_vol_spike = float(getattr(self, "min_vol_spike", 1.8))
        if float(ind.get("vol_spike", 0.0)) < min_vol_spike:
            return None

        # Order-flow gating (if configured)
        of = ind.get("orderflow") or {}
        bid_ask_ratio = float(of.get("bid_ask_ratio") or 1.0)
        buy_sell_ratio = float(of.get("buy_sell_ratio") or 1.0)

        min_ba = float(getattr(self, "min_bid_ask_ratio", 1.25)) * (1.0 - float(getattr(self, "loosen_factor", 0.0)))
        min_bs = float(getattr(self, "min_buy_sell_ratio", 1.15)) * (1.0 - float(getattr(self, "loosen_factor", 0.0)))

        if bid_ask_ratio < min_ba or buy_sell_ratio < min_bs:
            return None

        ema9 = float(ind["ema9"][-1])
        ema20 = float(ind["ema20"][-1])
        ema50 = float(ind["ema50"][-1])

        atr = float(ind["atr14"][-1]) if len(ind["atr14"]) else 0.0
        if atr <= 0.0 or (atr / close) < self.min_atr_fraction:
            return None

        # Allow minor EMA compression (30% of ATR)
        ema_tol = loosen * atr
        if not (
            close > ema9 - ema_tol
            and ema9 > ema20 - ema_tol
            and ema20 > ema50 - ema_tol
        ):
            return None

        # Breakout confirmation: allow "near breakout" within 30% ATR
        breakout_level = float(ind["breakout_level"])
        breakout_buffer = loosen * atr
        if close <= (breakout_level - breakout_buffer):
            return None

        # Stop logic: below EMA20 and recent swing low (last 5 candles)
        recent_lows = [float(c[3]) for c in candles[-5:]]
        swing_low = min(recent_lows)
        stop = min(ema20, swing_low)
        if stop >= close:
            return None

        risk_per_unit = close - stop
        if risk_per_unit <= 0:
            return None

        equity = float(context.get("equity", self.equity))
        dollar_risk = equity * self.risk_per_trade
        qty = dollar_risk / risk_per_unit

        target = close + self.r_multiple * risk_per_unit

        sentiment_score = float(context.get("sentiment_score", 0.0))
        sentiment_label = context.get("sentiment_label") or (
            "Bullish" if sentiment_score > 0 else "Bearish" if sentiment_score < 0 else "Neutral"
        )
        news_links = context.get("news_links", [])

        exchange_name = getattr(self.client, "name", None)
        if exchange_name is None and hasattr(self.client, "exchange"):
            exchange_name = getattr(self.client.exchange, "id", None)
        exchange_name = exchange_name or "kucoin"

        return Signal(
            symbol=symbol,
            exchange=exchange_name,
            timeframe=self.timeframe,
            side=Side.BUY,
            entry=close,
            stop=stop,
            target=target,
            qty=qty,
            rel_vol=rel_vol,
            gap_pct=gap_pct,
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            news_links=news_links,
        )

    def _force_test_signal(self, symbol, candles, ind, context):
        close = float(ind["close"][-1])
        if close <= 0:
            return None

        # Small, predictable stop/target so closes happen fast
        stop = close * 0.999   # -0.1%
        target = close * 1.001 # +0.1%

        risk_per_unit = close - stop
        if risk_per_unit <= 0:
            return None

        equity = float(context.get("equity", self.equity))
        dollar_risk = equity * float(self.risk_per_trade)
        qty = dollar_risk / risk_per_unit

        from core.models import Signal, Side
        return Signal(
            symbol=symbol,
            exchange=getattr(self.client, "name", "kucoin"),
            timeframe=self.timeframe,
            side=Side.BUY,
            entry=close,
            stop=stop,
            target=target,
            qty=qty,
            rel_vol=float(ind.get("rel_vol", 0.0)),
            gap_pct=float(ind.get("gap_pct", 0.0)),
            sentiment_score=float(context.get("sentiment_score", 0.0)),
            sentiment_label=context.get("sentiment_label", "Neutral"),
            news_links=context.get("news_links", []),
        )

    def _candle_structure_ok(self, candles):
        # candles: [ts, open, high, low, close, volume]
        o = float(candles[-1][1])
        h = float(candles[-1][2])
        l = float(candles[-1][3])
        c = float(candles[-1][4])
        rng = max(1e-9, h - l)

        body = abs(c - o)
        upper_wick = h - max(o, c)

        body_pct = body / rng
        upper_wick_pct = upper_wick / rng

        min_body = float(getattr(self, "min_body_pct", 0.55))
        max_wick = float(getattr(self, "max_upper_wick_pct", 0.35))

        return (body_pct >= min_body) and (upper_wick_pct <= max_wick)
