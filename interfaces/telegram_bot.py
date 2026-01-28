# interfaces/telegram_bot.py
import threading
import time
from typing import Optional, Any, Dict, List

import requests
import os

from core.events import EventBus, EventType
from core.models import Mode


class TelegramBot:
    """
    - Subscribes to EventBus events and posts to Telegram.
    - Long-polls Telegram for inbound commands (background thread).
    - Supports one-tap controls: STRICT/LOOSE, PAPER/LIVE (with confirm), PAUSE/RESUME.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        bus: Optional[EventBus] = None,
        repo: Optional[Any] = None,
        portfolio: Optional[Any] = None,
        scanner: Optional[Any] = None,
        exec_engine: Optional[Any] = None,
        cfg: Optional[Dict[str, Any]] = None,
    ):
        # Env-only credentials: ignore passed args to avoid placeholder configuration.
        # (Signature kept for backward compatibility with existing call sites.)
        token = (os.getenv("TELEGRAM_BOT_TOKEN") or token or "").strip()
        chat_id = (os.getenv("TELEGRAM_CHAT_ID") or chat_id or "").strip()

        # If env vars are set, they win.
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        if os.getenv("TELEGRAM_CHAT_ID"):
            chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

        if not token or ":" not in token:
            if str(os.getenv("TELEGRAM_DEBUG", "0")).strip().lower() in ("1", "true", "yes", "y"):
                print("[TELEGRAM_DEBUG] invalid TELEGRAM_BOT_TOKEN (missing ':' or empty)")
        if not chat_id:
            if str(os.getenv("TELEGRAM_DEBUG", "0")).strip().lower() in ("1", "true", "yes", "y"):
                print("[TELEGRAM_DEBUG] missing TELEGRAM_CHAT_ID")

        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

        self.cfg = cfg or {}

        self.bus = bus
        self.repo = repo
        self.portfolio = portfolio
        self.scanner = scanner
        self.exec_engine = exec_engine

        self._poll_thread: Optional[threading.Thread] = None
        self._stop_poll = False
        self._update_offset: Optional[int] = None

        self._paused = False
        self._live_arm_pending = False

        if bus is not None:
            bus.subscribe(EventType.HEARTBEAT, self.on_heartbeat)
            bus.subscribe(EventType.SIGNAL_CREATED, self.on_signal)
            bus.subscribe(EventType.ORDER_PLACED, self.on_order)
            bus.subscribe(EventType.TRADE_CLOSED, self.on_trade)

    # -----------------------------
    # Telegram send helpers
    # -----------------------------
    def _tg_debug(self) -> bool:
        return str(os.getenv("TELEGRAM_DEBUG", "0")).strip().lower() in ("1", "true", "yes", "y")

    def _send_text(self, text: str) -> None:
        try:
            r = requests.get(
                f"{self.base}/sendMessage",
                params={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendMessage status=", r.status_code, "resp=", r.text)
                except Exception:
                    pass
        except Exception as e:
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendMessage exception=", repr(e))
                except Exception:
                    pass
            pass

    def _get_menu_keyboard(self) -> dict:
        """Return the inline keyboard for the main menu."""
        return {
            "inline_keyboard": [
                [
                    {"text": "Status", "callback_data": "status"},
                    {"text": "Open Trades", "callback_data": "open_trades"}
                ],
                [
                    {"text": "Past Trades", "callback_data": "past_trades"},
                    {"text": "AI Review", "callback_data": "ai_review"}
                ],
                [
                    {"text": "Pause", "callback_data": "pause"},
                    {"text": "Resume", "callback_data": "resume"}
                ]
            ]
        }

    def _send_text_with_menu(self, text: str) -> None:
        """Send text message while preserving the inline keyboard menu."""
        try:
            import json
            keyboard = self._get_menu_keyboard()
            r = requests.get(
                f"{self.base}/sendMessage",
                params={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(keyboard)
                },
                timeout=10,
            )
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendTextWithMenu status=", r.status_code, "resp=", r.text)
                except Exception:
                    pass
        except Exception as e:
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendTextWithMenu exception=", repr(e))
                except Exception:
                    pass
            # Fallback to regular text if menu fails
            self._send_text(text)

    def send_menu(self) -> None:
        """Send main menu with inline keyboard buttons."""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "Status", "callback_data": "status"},
                    {"text": "Open Trades", "callback_data": "open_trades"}
                ],
                [
                    {"text": "Past Trades", "callback_data": "past_trades"},
                    {"text": "AI Review", "callback_data": "ai_review"}
                ],
                [
                    {"text": "Pause", "callback_data": "pause"},
                    {"text": "Resume", "callback_data": "resume"}
                ]
            ]
        }
        
        try:
            import json
            r = requests.get(
                f"{self.base}/sendMessage",
                params={
                    "chat_id": self.chat_id,
                    "text": "📊 <b>TradeMindIQ Bot Dashboard</b>\n\nSelect an option:",
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(keyboard)
                },
                timeout=10,
            )
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] send_menu status=", r.status_code, "resp=", r.text)
                except Exception:
                    pass
        except Exception as e:
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] send_menu exception=", repr(e))
                except Exception:
                    pass

    def _send_photo(self, photo_bytes: bytes, caption: Optional[str] = None) -> None:
        try:
            files = {"photo": ("chart.png", photo_bytes)}
            data = {"chat_id": self.chat_id}
            if caption:
                data["caption"] = caption[:1024]
                data["parse_mode"] = "HTML"
            r = requests.post(f"{self.base}/sendPhoto", data=data, files=files, timeout=20)
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendPhoto status=", r.status_code, "resp=", r.text)
                except Exception:
                    pass
        except Exception as e:
            if self._tg_debug():
                try:
                    print("[TELEGRAM_DEBUG] sendPhoto exception=", repr(e))
                except Exception:
                    pass
            pass

    # -----------------------------
    # Telegram formatting config
    # -----------------------------
    def _tg_cfg(self) -> Dict[str, Any]:
        return (self.cfg.get("telegram") or {}) if isinstance(self.cfg, dict) else {}

    def _fmt_mode(self) -> str:
        fmt = str(self._tg_cfg().get("format", "legacy")).strip().lower()
        return fmt if fmt in ("legacy", "compact") else "legacy"

    def _include_chart(self) -> bool:
        return bool(self._tg_cfg().get("include_chart", True))

    def _include_news(self) -> bool:
        return bool(self._tg_cfg().get("include_news", True))

    def _include_sentiment(self) -> bool:
        return bool(self._tg_cfg().get("include_sentiment", True))

    def _format_signal_legacy(self, signal: Any, indicators: Dict[str, Any], mode_txt: str, candles: Any) -> str:
        symbol = getattr(signal, "symbol", "")
        exch = getattr(signal, "exchange", "")
        tf = getattr(signal, "timeframe", "")
        entry = float(getattr(signal, "entry", 0.0))
        stop = float(getattr(signal, "stop", 0.0))
        target = float(getattr(signal, "target", 0.0))
        qty = float(getattr(signal, "qty", 0.0))

        relv = float(getattr(signal, "rel_vol", indicators.get("rel_vol", 0.0)) or 0.0)
        gap = float(getattr(signal, "gap_pct", indicators.get("gap_pct", 0.0)) or 0.0)

        ai_comment = indicators.get("_ai_comment")
        ai_block = f"\n\n🤖 {ai_comment}" if ai_comment else ""

        news_block = ""
        if self._include_news():
            news_links = indicators.get("news_links") or getattr(signal, "news_links", None) or []
            if isinstance(news_links, list) and news_links:
                lines = []
                for item in news_links[:3]:
                    if isinstance(item, str):
                        lines.append(f"• {item}")
                    elif isinstance(item, dict):
                        title = item.get("title", "News")
                        url = item.get("url", "")
                        lines.append(f"• {title} — {url}".strip())
                if lines:
                    news_block = "\n\nNews:\n" + "\n".join(lines)

        sentiment_block = ""
        if self._include_sentiment():
            sentiment_label = getattr(signal, "sentiment_label", None) or indicators.get("sentiment_label") or "Neutral"
            sentiment_score = getattr(signal, "sentiment_score", None)
            if sentiment_score is None:
                sentiment_score = indicators.get("sentiment_score", 0.0)
            try:
                sentiment_score = float(sentiment_score)
            except Exception:
                sentiment_score = 0.0
            sentiment_block = f"\nSentiment: {sentiment_label} ({sentiment_score:+.2f})"

        return (
            f"[ALERT] {symbol} — {exch}\n"
            f"Mode: <b>{mode_txt}</b> | TF: {tf}\n"
            f"Entry: {entry:.6f} | Stop: {stop:.6f} | Take: {target:.6f}\n"
            f"Qty: {qty:.6f} | RelVol: {relv:.2f} | Gap%: {gap:.2f}"
            f"{sentiment_block}"
            f"{news_block}"
            f"{ai_block}"
        )

    def _format_signal_compact(self, signal: Any, indicators: Dict[str, Any], mode_txt: str) -> str:
        symbol = getattr(signal, "symbol", "")
        tf = getattr(signal, "timeframe", "")
        entry = float(getattr(signal, "entry", 0.0))
        stop = float(getattr(signal, "stop", 0.0))
        target = float(getattr(signal, "target", 0.0))
        relv = float(getattr(signal, "rel_vol", indicators.get("rel_vol", 0.0)) or 0.0)
        gap = float(getattr(signal, "gap_pct", indicators.get("gap_pct", 0.0)) or 0.0)
        return (
            f"📣 <b>{symbol}</b> {tf} | <b>{mode_txt}</b>\n"
            f"E {entry:.6f} | S {stop:.6f} | T {target:.6f}\n"
            f"RV {relv:.2f} | Gap {gap:.2f}%"
        )

    def send_signal_alert(self, signal: Any, candles: Any, indicators: Dict[str, Any]) -> None:
        mode_txt = "PAPER"
        try:
            if self.exec_engine and getattr(self.exec_engine, "mode", None) == Mode.LIVE:
                mode_txt = "LIVE"
        except Exception:
            pass

        if self._fmt_mode() == "compact":
            self._send_text(self._format_signal_compact(signal, indicators or {}, mode_txt))
            return

        msg = self._format_signal_legacy(signal, indicators or {}, mode_txt, candles)

        chart_bytes = None
        if self._include_chart():
            try:
                from interfaces.charting import build_ema_chart

                # Extract closes from CCXT-style candles: [ts, o, h, l, c, v]
                closes: List[float] = []
                if isinstance(candles, list):
                    for c in candles:
                        try:
                            closes.append(float(c[4]))
                        except Exception:
                            continue

                # Prefer precomputed EMA arrays from indicators if present
                ema9 = indicators.get("ema9") or indicators.get("ema_9") or []
                ema20 = indicators.get("ema20") or indicators.get("ema_20") or []
                ema50 = indicators.get("ema50") or indicators.get("ema_50") or []
                if not isinstance(ema9, list):
                    ema9 = []
                if not isinstance(ema20, list):
                    ema20 = []
                if not isinstance(ema50, list):
                    ema50 = []

                # Keep charting satisfied with equal-length series
                if closes:
                    if len(ema9) != len(closes):
                        ema9 = closes
                    if len(ema20) != len(closes):
                        ema20 = closes
                    if len(ema50) != len(closes):
                        ema50 = closes

                    chart_bytes = build_ema_chart(
                        closes,
                        ema9,
                        ema20,
                        ema50,
                        title=f"{getattr(signal, 'symbol', '')} - {getattr(signal, 'timeframe', '')}",
                    )
            except Exception:
                chart_bytes = None

        if chart_bytes:
            self._send_photo(chart_bytes, caption=msg)
        else:
            self._send_text(msg)

    # -----------------------------
    # Event handlers (outbound)
    # -----------------------------
    def on_heartbeat(self, payload: Any) -> None:
        # Keep heartbeat lightweight to avoid spam. Show only if explicitly asked via Status.
        pass

    def on_signal(self, payload: Any) -> None:
        if self._paused:
            return
        try:
            signal, candles, indicators = payload
        except Exception:
            return
        self.send_signal_alert(signal, candles, indicators or {})

    def on_order(self, order: Any) -> None:
        try:
            msg = (
                f"✅ {getattr(order, 'mode', 'ORDER')} {getattr(order, 'side', '')} "
                f"{getattr(order, 'symbol', '')} @ {float(getattr(order, 'entry', 0.0)):.6f}\n"
                f"stop {float(getattr(order, 'stop', 0.0)):.6f} | "
                f"target {float(getattr(order, 'target', 0.0)):.6f} | "
                f"qty {float(getattr(order, 'qty', 0.0)):.6f}"
            )
            self._send_text(msg)
        except Exception:
            self._send_text("✅ ORDER placed.")

    def on_trade(self, trade: Any) -> None:
        """TRADE_CLOSED handler."""
        try:
            if self._fmt_mode() == "compact":
                self._send_text(self._format_trade_closed_compact(trade))
                return

            msg = self._format_trade_closed_legacy(trade)
            chart_bytes = self._try_build_trade_chart(trade) if self._include_chart() else None
            if chart_bytes:
                self._send_photo(chart_bytes, caption=msg)
            else:
                self._send_text(msg)
        except Exception as e:
            if self._tg_debug():
                try:
                    import traceback

                    print("[TELEGRAM_DEBUG] on_trade exception:", repr(e))
                    traceback.print_exc()
                except Exception:
                    pass
            self._send_text("📊 TRADE CLOSED")

    def _format_trade_closed_legacy(self, trade: Any) -> str:
        symbol = getattr(trade, "symbol", "") or getattr(getattr(trade, "signal", None), "symbol", "")
        meta = getattr(trade, "meta", {}) or {}
        exit_reason = (meta.get("exit_reason") or getattr(trade, "exit_reason", "") or "UNKNOWN")
        snap = meta.get("signal_snapshot", {}) if isinstance(meta.get("signal_snapshot", {}), dict) else {}

        status = str(meta.get("status") or getattr(trade, "result", "") or "CLOSED").upper()

        sig = getattr(trade, "signal", None)
        entry_price = float(getattr(trade, "entry_price", getattr(sig, "entry", 0.0)) or 0.0)
        exit_price = float(getattr(trade, "exit_price", 0.0) or 0.0)
        qty = float(getattr(trade, "qty", getattr(sig, "qty", 0.0)) or 0.0)

        pnl_usd = meta.get("pnl_usd", None)
        if pnl_usd is None:
            pnl_usd = float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0)
        pnl_usd = float(pnl_usd or 0.0)

        pnl_r = meta.get("pnl_r", None)
        pnl_r_txt = ""
        if pnl_r is not None:
            try:
                pnl_r_txt = f" | R: {float(pnl_r):+.2f}"
            except Exception:
                pnl_r_txt = ""

        hold_seconds = meta.get("hold_seconds", getattr(trade, "hold_seconds", None))
        hold_txt = ""
        if hold_seconds is not None:
            try:
                hold_txt = f" | Hold: {int(float(hold_seconds))}s"
            except Exception:
                hold_txt = ""

        extra_lines = []
        if self._include_sentiment():
            sl = snap.get("sentiment_label")
            ss = snap.get("sentiment_score")
            if sl is not None or ss is not None:
                try:
                    ss_f = float(ss) if ss is not None else 0.0
                except Exception:
                    ss_f = 0.0
                extra_lines.append(f"Sentiment: {sl or 'Neutral'} ({ss_f:+.2f})")

        if self._include_news():
            news_links = (
                snap.get("news_links")
                or snap.get("news")
                or meta.get("news_links")
                or meta.get("news")
                or []
            )
            if isinstance(news_links, list) and news_links:
                lines = []
                for item in news_links[:3]:
                    if isinstance(item, str):
                        lines.append(f"• {item}")
                    elif isinstance(item, dict):
                        title = item.get("title", "News")
                        url = item.get("url", "")
                        lines.append(f"• {title} — {url}".strip())
                if lines:
                    extra_lines.append("News:\n" + "\n".join(lines))

        extra_block = ("\n\n" + "\n".join(extra_lines)) if extra_lines else ""

        return (
            f"📊 <b>TRADE CLOSED — {status}</b>\n"
            f"{symbol} | Exit: {exit_reason}{hold_txt}\n"
            f"Entry: {entry_price:.6f} | Exit: {exit_price:.6f} | Qty: {qty:.6f}\n"
            f"PnL: <b>${pnl_usd:+.2f}</b>{pnl_r_txt}"
            f"{extra_block}"
        )

    def _format_trade_closed_compact(self, trade: Any) -> str:
        symbol = getattr(trade, "symbol", "") or getattr(getattr(trade, "signal", None), "symbol", "")
        meta = getattr(trade, "meta", {}) or {}
        exit_reason = (meta.get("exit_reason") or getattr(trade, "exit_reason", "") or "UNKNOWN")
        status = str(meta.get("status") or getattr(trade, "result", "") or "CLOSED").upper()

        pnl_usd = meta.get("pnl_usd", None)
        if pnl_usd is None:
            pnl_usd = float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0)
        pnl_usd = float(pnl_usd or 0.0)

        pnl_r = meta.get("pnl_r", None)
        pnl_r_txt = ""
        if pnl_r is not None:
            try:
                pnl_r_txt = f" ({float(pnl_r):+.2f}R)"
            except Exception:
                pnl_r_txt = ""
        return f"📊 {symbol} {status} | {exit_reason} | ${pnl_usd:+.2f}{pnl_r_txt}"

    def _try_build_trade_chart(self, trade: Any) -> Optional[bytes]:
        """Best-effort chart bytes. Uses any stored candles/ema arrays in trade.meta."""
        try:
            meta = getattr(trade, "meta", {}) or {}
            snap = meta.get("signal_snapshot", {}) if isinstance(meta.get("signal_snapshot", {}), dict) else {}

            candles = snap.get("candles") or meta.get("candles")
            if not isinstance(candles, list) or not candles:
                return None

            closes: List[float] = []
            for c in candles:
                try:
                    closes.append(float(c[4]))
                except Exception:
                    continue
            if len(closes) < 10:
                return None

            ema9 = snap.get("ema9") or []
            ema20 = snap.get("ema20") or []
            ema50 = snap.get("ema50") or []
            if not isinstance(ema9, list):
                ema9 = []
            if not isinstance(ema20, list):
                ema20 = []
            if not isinstance(ema50, list):
                ema50 = []

            # charting expects lists of same length; fall back to closes if missing
            if len(ema9) != len(closes):
                ema9 = closes
            if len(ema20) != len(closes):
                ema20 = closes
            if len(ema50) != len(closes):
                ema50 = closes

            from interfaces.charting import build_ema_chart

            title = f"{getattr(trade, 'symbol', '')} - TRADE"
            return build_ema_chart(closes, ema9, ema20, ema50, title=title)
        except Exception:
            return None

    # -----------------------------
    # Command routing
    # -----------------------------
    def handle_command(self, text: str) -> None:
        t = (text or "").strip()
        low = t.lower()
        cmd = t.strip().lower()

        # CONFIRM LIVE
        if cmd in ("/confirm live", "confirm live"):
            if not self.exec_engine:
                self._send_text("❌ Execution engine not available.")
                return

            # use module-level Mode imported above
            self.exec_engine.mode = Mode.LIVE
            if hasattr(self.exec_engine, "arm_live"):
                self.exec_engine.arm_live(True)

            self._send_text("🚨 LIVE TRADING ENABLED AND ARMED")
            return

        # PAPER / DISARM
        if cmd in ("/paper", "paper", "/disarm", "disarm"):
            if self.exec_engine:
                if hasattr(self.exec_engine, "arm_live"):
                    self.exec_engine.arm_live(False)
                self.exec_engine.mode = Mode.PAPER
            self._send_text("✅ Switched to PAPER mode. Live trading disarmed.")
            return

        # Normalize button labels
        if low in ("/start", "start"):
            self.send_menu()
            return

        if low in ("/status", "status") or t == "Status":
            self._send_status()
            return

        if low in ("/open", "open") or t == "Open Trades":
            self._send_open_trades()
            return

        if low in ("/closed", "closed") or t == "Past Trades":
            self._send_recent_trades()
            return

        if low in ("/stats", "stats") or t == "Stats":
            self._send_stats()
            return

        if t == "Pause" or low in ("/pause", "pause"):
            self._paused = True
            self._send_text("⏸️ Scanner alerts paused.")
            return

        if t == "Resume" or low in ("/resume", "resume"):
            self._paused = False
            self._send_text("▶️ Scanner alerts resumed.")
            return

        # STRICT / LOOSE toggles
        if t == "STRICT" or low in ("/strict", "strict"):
            if self.scanner and hasattr(self.scanner, "set_mode_preset"):
                self.scanner.set_mode_preset("strict")
                self._send_text("✅ Scanner set to STRICT (loosen_factor=0.0)")
            else:
                self._send_text("❌ Scanner not wired for STRICT.")
            return

        if t.startswith("LOOSE") or low.startswith("/loose") or low.startswith("loose"):
            if not self.scanner:
                self._send_text("❌ Scanner not wired for LOOSE.")
                return

            # allow: "LOOSE 0.40"
            parts = t.replace("/", "").split()
            if len(parts) == 2:
                try:
                    val = float(parts[1])
                    if hasattr(self.scanner, "set_loosen_factor"):
                        self.scanner.set_loosen_factor(val)
                        self._send_text(f"✅ loosen_factor set to {val:.2f}")
                    else:
                        self._send_text("❌ Scanner missing set_loosen_factor().")
                except Exception:
                    self._send_text("Usage: LOOSE or LOOSE 0.30")
            else:
                if hasattr(self.scanner, "set_mode_preset"):
                    self.scanner.set_mode_preset("loose")
                    self._send_text("✅ Scanner set to LOOSE (loosen_factor=0.30)")
                else:
                    self._send_text("❌ Scanner missing set_mode_preset().")
            return

        # PAPER / LIVE toggles (LIVE requires confirmation)
        if t == "Mode: PAPER" or low in ("/paper", "paper"):
            if self.exec_engine:
                try:
                    self.exec_engine.mode = Mode.PAPER
                    self._send_text("✅ PAPER mode enabled.")
                except Exception as e:
                    self._send_text(f"❌ Failed to set PAPER: {e}")
            else:
                self._send_text("❌ Exec engine not wired.")
            return

        if t == "Mode: LIVE" or low in ("/live", "live"):
            if not self.exec_engine:
                self._send_text("❌ Exec engine not wired.")
                return
            self._live_arm_pending = True
            self._send_text("⚠️ LIVE requested. Type: <b>CONFIRM LIVE</b> to enable live trading.")
            return

        if low in ("confirm live", "/confirm_live"):
            if not self.exec_engine:
                self._send_text("❌ Exec engine not wired.")
                return
            if not self._live_arm_pending:
                self._send_text("No pending LIVE request. Tap Mode: LIVE first.")
                return
            self._live_arm_pending = False
            try:
                self.exec_engine.mode = Mode.LIVE
                self._send_text("✅ LIVE mode ENABLED.")
            except Exception as e:
                self._send_text(f"❌ Failed to enable LIVE: {e}")
            return

        # One-tap actions (safe placeholders unless you wire manual execution)
        if t == "One-Tap BUY":
            self._send_text("One-Tap BUY tapped. (Wire a manual buy action here if desired.)")
            return

        if t == "One-Tap SELL":
            self._send_text("One-Tap SELL tapped. (Wire a manual sell action here if desired.)")
            return

        # Test mode controls
        if low in ("/test_on", "test on"):
            if self.scanner and hasattr(self.scanner, "set_test_force_signals"):
                self.scanner.set_test_force_signals(True)
                if hasattr(self.scanner, "reset_forced_symbols"):
                    self.scanner.reset_forced_symbols()
                self._send_text("✅ TEST MODE ON: forcing signals.")
            else:
                self._send_text("❌ Scanner not wired for test mode.")
            return

        if low in ("/test_off", "test off"):
            if self.scanner and hasattr(self.scanner, "set_test_force_signals"):
                self.scanner.set_test_force_signals(False)
                self._send_text("✅ TEST MODE OFF: normal strategy rules.")
            return

        if low in ("/test_once", "test once"):
            if self.scanner and hasattr(self.scanner, "reset_forced_symbols"):
                self.scanner.reset_forced_symbols()
            if self.scanner and hasattr(self.scanner, "set_test_force_signals"):
                self.scanner.set_test_force_signals(True)
            self._send_text("✅ TEST ONCE armed. Next scan will force 1 signal per symbol.")
            return

        # AI buttons (placeholders unless you wire advisor methods)
        if t == "AI Review":
            self._send_text("AI Review: will appear on each signal + post-trade. (Already wired if AI is enabled.)")
            return

        if t == "AI Optimize":
            self._send_text("AI Optimize: post-trade parameter suggestions will be sent after trade close.")
            return

        if t == "Daily Summary":
            self._send_text("Daily Summary: not yet implemented.")
            return

        if t == "Weekly Summary":
            self._send_text("Weekly Summary: not yet implemented.")
            return

        self._send_text("Unknown command. Tap a menu button or use /status, /open, /closed, /stats.")

    def handle_dashboard_callback(self, call_data: str) -> None:
        """Handle callback queries from inline keyboards."""
        if call_data == "status":
            self._send_status_with_menu()
        elif call_data == "open_trades":
            self._send_open_trades_with_menu()
        elif call_data == "past_trades":
            self._send_recent_trades_with_menu()
        elif call_data == "ai_review":
            self._send_text_with_menu("AI Review: will appear on each signal + post-trade. (Already wired if AI is enabled.)")
        elif call_data == "pause":
            self._paused = True
            self._send_text_with_menu("⏸️ Scanner alerts paused.")
        elif call_data == "resume":
            self._paused = False
            self._send_text_with_menu("▶️ Scanner alerts resumed.")

    # -----------------------------
    # Info helpers
    # -----------------------------
    def _send_status(self) -> None:
        mode_txt = "UNKNOWN"
        try:
            if self.exec_engine and getattr(self.exec_engine, "mode", None):
                mode_txt = getattr(self.exec_engine.mode, "name", str(self.exec_engine.mode))
        except Exception:
            pass

        loosen_txt = "n/a"
        try:
            if self.scanner and hasattr(self.scanner, "loosen_factor"):
                loosen_txt = f"{float(self.scanner.loosen_factor):.2f}"
        except Exception:
            pass

        paused_txt = "YES" if self._paused else "NO"
        msg = (
            "Status: online\n"
            f"Mode: <b>{mode_txt}</b>\n"
            f"Paused: {paused_txt}\n"
            f"loosen_factor: {loosen_txt}"
        )
        self._send_text(msg)

    def _send_status_with_menu(self) -> None:
        """Send status with inline keyboard menu."""
        mode_txt = "UNKNOWN"
        try:
            if self.exec_engine and getattr(self.exec_engine, "mode", None):
                mode_txt = getattr(self.exec_engine.mode, "name", str(self.exec_engine.mode))
        except Exception:
            pass

        loosen_txt = "n/a"
        try:
            if self.scanner and hasattr(self.scanner, "loosen_factor"):
                loosen_txt = f"{float(self.scanner.loosen_factor):.2f}"
        except Exception:
            pass

        paused_txt = "YES" if self._paused else "NO"
        msg = (
            "Status: online\n"
            f"Mode: <b>{mode_txt}</b>\n"
            f"Paused: {paused_txt}\n"
            f"loosen_factor: {loosen_txt}"
        )
        self._send_text_with_menu(msg)

    def _send_open_trades(self) -> None:
        if not self.portfolio:
            self._send_text("No portfolio service wired.")
            return
        try:
            open_trades = self.portfolio.get_open_positions()
        except Exception:
            open_trades = []

        if not open_trades:
            self._send_text("No open trades.")
            return

        lines = ["<b>Open Trades</b>"]
        for t in open_trades:
            try:
                lines.append(
                    f"{t.symbol} @ {float(getattr(t,'entry_price', getattr(t,'entry',0.0))):.6f} | "
                    f"qty {float(getattr(t,'qty',0.0)):.6f} | "
                    f"uPnL: {float(getattr(t,'unrealized_pnl',0.0)):.2f}"
                )
            except Exception:
                continue
        self._send_text("\n".join(lines))

    def _send_open_trades_with_menu(self) -> None:
        """Send open trades with inline keyboard menu."""
        if not self.portfolio:
            self._send_text_with_menu("No portfolio service wired.")
            return
        try:
            open_trades = self.portfolio.get_open_positions()
        except Exception:
            open_trades = []

        if not open_trades:
            self._send_text_with_menu("No open trades.")
            return

        lines = ["<b>Open Trades</b>"]
        for t in open_trades:
            try:
                lines.append(
                    f"{t.symbol} @ {float(getattr(t,'entry_price', getattr(t,'entry',0.0))):.6f} | "
                    f"qty {float(getattr(t,'qty',0.0)):.6f} | "
                    f"uPnL: {float(getattr(t,'unrealized_pnl',0.0)):.2f}"
                )
            except Exception:
                continue
        self._send_text_with_menu("\n".join(lines))

    def _send_recent_trades(self, limit: int = 5) -> None:
        if not self.repo:
            self._send_text("No trade repository wired.")
            return
        try:
            trades = self.repo.get_recent_trades(limit)
        except Exception:
            trades = []

        if not trades:
            self._send_text("No recent trades.")
            return

        lines = [f"<b>Last {len(trades)} closed trades</b>"]
        for t in trades:
            try:
                lines.append(
                    f"{getattr(t,'closed_at','')} | {getattr(t,'symbol','')} | "
                    f"{getattr(t,'side','')} | PnL: {float(getattr(t,'realized_pnl',0.0)):.2f}"
                )
            except Exception:
                continue
        self._send_text("\n".join(lines))

    def _send_recent_trades_with_menu(self, limit: int = 5) -> None:
        """Send recent trades with inline keyboard menu."""
        if not self.repo:
            self._send_text_with_menu("No trade repository wired.")
            return
        try:
            trades = self.repo.get_recent_trades(limit)
        except Exception:
            trades = []

        if not trades:
            self._send_text_with_menu("No recent trades.")
            return

        lines = [f"<b>Last {len(trades)} closed trades</b>"]
        for t in trades:
            try:
                lines.append(
                    f"{getattr(t,'closed_at','')} | {getattr(t,'symbol','')} | "
                    f"{getattr(t,'side','')} | PnL: {float(getattr(t,'realized_pnl',0.0)):.2f}"
                )
            except Exception:
                continue
        self._send_text_with_menu("\n".join(lines))

    def _send_stats(self) -> None:
        if not self.repo:
            self._send_text("No trade repository wired.")
            return
        try:
            stats = self.repo.get_summary_stats()
        except Exception:
            stats = {}

        if not stats:
            self._send_text("No stats available yet.")
            return

        lines = ["<b>Performance Stats</b>"]
        for k, v in stats.items():
            lines.append(f"{k}: {v}")
        self._send_text("\n".join(lines))

    # -----------------------------
    # Polling mechanism
    # -----------------------------
    def _poll_loop(self) -> None:
        """Background thread that polls Telegram for updates."""
        while not self._stop_poll:
            try:
                params = {"timeout": 30}
                if self._update_offset is not None:
                    params["offset"] = self._update_offset

                r = requests.get(
                    f"{self.base}/getUpdates",
                    params=params,
                    timeout=35,
                )
                
                if r.status_code != 200:
                    time.sleep(1)
                    continue

                data = r.json()
                if not data.get("ok"):
                    time.sleep(1)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    self._update_offset = update.get("update_id", 0) + 1
                    
                    # Handle callback queries
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        call_data = callback.get("data", "")
                        callback_id = callback.get("id", "")
                        
                        # Answer callback query to remove loading state
                        try:
                            requests.get(
                                f"{self.base}/answerCallbackQuery",
                                params={"callback_query_id": callback_id},
                                timeout=5,
                            )
                        except Exception:
                            pass
                        
                        # Handle the callback
                        self.handle_dashboard_callback(call_data)
                    
                    # Handle text messages
                    elif "message" in update:
                        msg = update["message"]
                        text = msg.get("text", "")
                        if text:
                            self.handle_command(text)

            except Exception as e:
                if self._tg_debug():
                    try:
                        print("[TELEGRAM_DEBUG] poll_loop exception=", repr(e))
                    except Exception:
                        pass
                time.sleep(1)

    def start_polling(self) -> None:
        """Start polling for updates in a background thread."""
        if self._poll_thread is not None and self._poll_thread.is_alive():
            if self._tg_debug():
                print("[TELEGRAM_DEBUG] Polling already running")
            return
        
        self._stop_poll = False
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        
        if self._tg_debug():
            print("[TELEGRAM_DEBUG] Polling started")

    def stop_polling(self) -> None:
        """Stop the polling thread."""
        self._stop_poll = True
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=5)
        
        if self._tg_debug():
            print("[TELEGRAM_DEBUG] Polling stopped")
