# main_paper.py
import asyncio
import os
import yaml
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, "env"))

from core.models import Mode
from core.data_client import DataClient
from core.events import EventBus, EventType
from core.execution import ExecutionEngine
from core.execution_router import TradeIntent, execute_intent
from core.exchange_factory import create_exchange

from services.scanner import ScannerService
from services.risk import RiskManager
from services.portfolio import PortfolioTracker
from services.heartbeat import Heartbeat

from interfaces.telegram_bot import TelegramBot
from storage.db import TradeRepository
from ai.advisor import AIAdvisor
from storage.trade_exporter import TradeCsvExporter
from storage.top_movers import get_top_movers
from storage.signal_exporter import SignalCsvExporter
from storage.order_exporter import OrderCsvExporter
from ai.post_trade_schema import PostTradeContext
from ai.confidence_justification import compute_confidence
from core.time_filters import is_us_open_2h






def load_settings() -> dict:
    cfg_path = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    # Override BTCC credentials from environment (keeps secrets out of settings.yaml)
    btcc_env = {
        "base_url": os.getenv("BTCC_BASE_URL"),
        "user_name": os.getenv("BTCC_USER_NAME"),
        "password": os.getenv("BTCC_PASSWORD"),
        "api_key": os.getenv("BTCC_API_KEY"),
        "secret_key": os.getenv("BTCC_SECRET_KEY"),
        "company_id": os.getenv("BTCC_COMPANY_ID"),
    }
    # Only merge if at least one env var is set
    if any(v for v in btcc_env.values()):
        cfg.setdefault("btcc", {})
        if btcc_env["base_url"]:
            cfg["btcc"]["base_url"] = btcc_env["base_url"]
        if btcc_env["user_name"]:
            cfg["btcc"]["user_name"] = btcc_env["user_name"]
        if btcc_env["password"]:
            cfg["btcc"]["password"] = btcc_env["password"]
        if btcc_env["api_key"]:
            cfg["btcc"]["api_key"] = btcc_env["api_key"]
        if btcc_env["secret_key"]:
            cfg["btcc"]["secret_key"] = btcc_env["secret_key"]
        if btcc_env["company_id"]:
            try:
                cfg["btcc"]["company_id"] = int(btcc_env["company_id"])
            except Exception:
                pass

    return cfg


async def main() -> None:
    # ---------- Load config + secrets ----------
    load_dotenv(os.path.join(PROJECT_ROOT, "env"))  # your file is named "env" (no dot)

    cfg = load_settings()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not bot_token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in env file")

    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Check TradeMindIQBot/env")

    # ---------- Core wiring ----------
    mode = Mode[str(cfg["mode"]).upper()]  # "PAPER" or "LIVE"
    bus = EventBus()

    client = DataClient(cfg["exchange"])
    exec_engine = ExecutionEngine(client.exchange, mode)

    # Optional unified execution adapter (e.g. BTCC). If not configured, fall back to ExecutionEngine.
    exchange_adapter = None
    try:
        exchange_adapter = create_exchange(cfg)
        if hasattr(exchange_adapter, "connect"):
            exchange_adapter.connect()
    except Exception:
        exchange_adapter = None

    repo = TradeRepository(cfg.get("ai", {}).get("db_path", "trades.db"))
    risk = RiskManager()
    portfolio = PortfolioTracker(db_path=cfg.get("ai", {}).get("db_path", "trades.db"))

    # OrderFlow wiring (optional)
    from services.orderflow import OrderFlowService
    orderflow_cfg = cfg.get("orderflow", {}) or {}
    orderflow = None
    if orderflow_cfg.get("enabled"):
        orderflow = OrderFlowService(
            client.exchange,
            book_depth=orderflow_cfg.get("book_depth", 8),
            tape_trades=orderflow_cfg.get("tape_trades", 60),
        )

    # configure risk and portfolio trade management
    tm = cfg.get("trade_mgmt", {}) or {}
    # Note: PortfolioTracker is read-only, doesn't need trade management config
    # portfolio.set_trade_mgmt(
    #     max_hold_seconds=tm.get("max_hold_seconds", 180),
    #     cooldown_seconds=tm.get("cooldown_seconds", 90),
    # )

    risk.configure(
        max_open_positions=tm.get("max_open_positions", 2),
        daily_loss_cap=tm.get("daily_loss_cap", 25.0),
    )

    # Telegram (wired to bus + services)
    telegram = TelegramBot(
        token=bot_token,
        chat_id=chat_id,
        bus=bus,
        repo=repo,
        portfolio=portfolio,
        # Optional: if your TelegramBot supports these, it will use them
        exec_engine=exec_engine,
        scanner=None,  # set after scanner constructed
        cfg=cfg,
    )
    heartbeat = Heartbeat(telegram, cfg)
    try:
        telegram._send_text("🚀 TradeMindIQ Bot started and scanning")
    except Exception:
        pass
    # AI advisor (pre-trade review + post-trade review)
    advisor = AIAdvisor(
        db_path=cfg.get("ai", {}).get("db_path", "trades.db"),
        telegram=telegram,
        openai_api_key=openai_key,
    )

    # If your TelegramBot has polling/menu helpers, start them safely
    if hasattr(telegram, "start_polling_background"):
        telegram.start_polling_background()
    if hasattr(telegram, "send_menu"):
        telegram.send_menu()

    # ---------- Event handlers ----------
    signal_exporter = SignalCsvExporter("signals_export.csv")
    order_exporter = OrderCsvExporter("orders_export.csv")

    async def handle_signal(sig):
        try:
            ok, reason = risk.can_open_new_trade(open_positions=len(portfolio.open_orders))
        except Exception:
            ok, reason = True, None

        if not ok:
            try:
                telegram._send_text(f"🛑 Risk block: {reason}")
            except Exception:
                pass
            return

        # If an adapter is present (e.g. BTCC), route execution via generic intent router.
        if exchange_adapter is not None:
            try:
                side = str(getattr(sig, "side", "")).lower()
                intent_side = "long" if "buy" in side else "short" if "sell" in side else side
                intent = TradeIntent(
                    symbol=sig.symbol,
                    side=intent_side,
                    qty=float(getattr(sig, "qty", 0.0) or 0.0),
                    leverage=int((cfg.get("risk", {}) or {}).get("leverage", 20)),
                    price_hint=float(getattr(sig, "entry", 0.0) or 0.0),
                    stop_loss=float(getattr(sig, "stop", 0.0) or 0.0) or None,
                    take_profit=float(getattr(sig, "target", 0.0) or 0.0) or None,
                )

                current_positions = []
                try:
                    current_positions = exchange_adapter.get_open_positions(symbol=sig.symbol) or []
                except Exception:
                    current_positions = []
                current_position = current_positions[0] if current_positions else None

                result = execute_intent(exchange_adapter, intent, current_position=current_position)
                bus.publish(EventType.ORDER_PLACED, result)
                try:
                    order_exporter.write_order(result)
                except Exception:
                    pass
                try:
                    telegram._send_text(f"✅ {intent_side.upper()} {sig.symbol} | result: {result.get('action', result.get('status','ok'))}")
                except Exception:
                    pass
                return
            except Exception as e:
                try:
                    telegram._send_text(f"🛑 Execution adapter error: {e}")
                except Exception:
                    pass

        order = await exec_engine.execute_signal(sig)

        # Attach signal-time snapshot for post-trade context (best effort)
        try:
            if not hasattr(order, "meta") or getattr(order, "meta", None) is None:
                order.meta = {}
            order.meta["signal_snapshot"] = {
                "rel_vol": float(getattr(sig, "rel_vol", 0.0) or 0.0),
                "gap_pct": float(getattr(sig, "gap_pct", 0.0) or 0.0),
            }
        except Exception:
            pass

        bus.publish(EventType.ORDER_PLACED, order)
        try:
            order_exporter.write_order(order)
        except Exception:
            pass
        portfolio.register_order(order)

        # notify risk manager of open (if supported)
        try:
            if hasattr(risk, "register_open"):
                risk.register_open(sig.symbol)
        except Exception:
            pass

    def on_signal(payload):
        sig, candles, indicators = payload
        try:
            signal_exporter.write_signal(sig)
        except Exception:
            pass
        # Pass signal-time indicator snapshot into execution path
        try:
            setattr(sig, "_indicators_snapshot", indicators or {})
        except Exception:
            pass
        asyncio.create_task(handle_signal(sig))

    bus.subscribe(EventType.SIGNAL_CREATED, on_signal)

    # Post-trade AI review + parameter suggestion (in-memory apply)
    exporter = TradeCsvExporter("trades_export.csv")

    def on_trade_closed(trade):
        try:
            review = advisor.review_closed_trade(trade, context={"params": cfg})

            # Deterministic confidence breakdown (best-effort, fills missing with defaults)
            try:
                # pull what we can from trade/signal + cfg
                sig = getattr(trade, "signal", None)
                exit_reason = getattr(trade, "exit_reason", "UNKNOWN") or "UNKNOWN"
                entry_price = float(getattr(trade, "entry_price", getattr(sig, "entry", 0.0)) or 0.0)
                exit_price = float(getattr(trade, "exit_price", 0.0) or 0.0)
                qty = float(getattr(trade, "qty", getattr(sig, "qty", 0.0)) or 0.0)
                pnl_usd = float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0)

                tm_local = cfg.get("trade_mgmt", {}) or {}
                of_cfg = cfg.get("orderflow", {}) or {}
                dry_run = str((cfg.get("trading", {}) or {}).get("mode", "paper")).strip().lower() != "live"

                ctx = PostTradeContext(
                    symbol=getattr(trade, "symbol", getattr(sig, "symbol", "")) or "",
                    exchange=getattr(sig, "exchange", cfg.get("exchange", "")) or "",
                    market_type="futures" if isinstance(cfg.get("exchange"), dict) else "spot",
                    timeframe=getattr(sig, "timeframe", cfg.get("timeframe", "1m")) or "1m",
                    side="long",
                    strategy_name="momentum",
                    entry_ts=int(getattr(trade, "opened_at", getattr(trade, "entry_ts", 0)) or 0),
                    exit_ts=int(getattr(trade, "closed_at", getattr(trade, "exit_ts", 0)) or 0),
                    hold_seconds=int(getattr(trade, "hold_seconds", 0) or 0),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    qty=qty,
                    notional_usd=float(entry_price * qty) if entry_price and qty else 0.0,
                    pnl_usd=pnl_usd,
                    pnl_r=float(getattr(trade, "pnl_r", 0.0) or 0.0),
                    fees_usd=float(getattr(trade, "fees_usd", 0.0) or 0.0),
                    slippage_bps=getattr(trade, "slippage_bps", None),
                    risk_per_trade=float(cfg.get("risk_per_trade", 0.0) or 0.0),
                    planned_stop_price=float(getattr(sig, "stop", 0.0) or 0.0) or None,
                    planned_target_price=float(getattr(sig, "target", 0.0) or 0.0) or None,
                    atr_value=None,
                    stop_distance_atr=None,
                    breakout_lookback=int(cfg.get("breakout_lookback", 12) or 12),
                    breakout_level=None,
                    breakout_close_above=None,
                    body_pct=None,
                    upper_wick_pct=None,
                    vol_spike=None,
                    gap_pct=float(getattr(sig, "gap_pct", 0.0) or 0.0),
                    ema_alignment=None,
                    orderflow_enabled=bool(of_cfg.get("enabled", False)),
                    book_depth=int(of_cfg.get("book_depth", 0) or 0),
                    bid_ask_ratio=None,
                    buy_sell_ratio=None,
                    tape_trades=int(of_cfg.get("tape_trades", 0) or 0),
                    spread_bps=None,
                    exit_reason=str(exit_reason),
                    max_favorable_excursion_r=None,
                    max_adverse_excursion_r=None,
                    rejections=int(getattr(trade, "rejections", 0) or 0),
                    dry_run=bool(dry_run),
                    indicators={},
                    data_quality="ok",
                )
                conf = compute_confidence(ctx)
                review["confidence"] = int(conf.score)
                # include 1-3 summary reasons for Telegram readability
                review["confidence_reasons"] = conf.reasons[:5]
            except Exception:
                pass

            # fallbacks (avoid blank sections)
            what_worked = (review.get("what_worked") or "(no notes)").strip()
            what_failed = (review.get("what_failed") or "(no notes)").strip()
            next_time = (review.get("next_time") or "(no notes)").strip()

            symbol = getattr(trade, "symbol", review.get("symbol", ""))
            result = (review.get("result") or getattr(trade, "result", "") or "").strip()
            pnl_val = float(review.get("pnl", getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0) or 0.0)
            conf_val = int(review.get("confidence", 50) or 50)
            exit_reason = getattr(trade, "exit_reason", "")
            entry_price = getattr(trade, "entry_price", getattr(getattr(trade, "signal", None), "entry", 0.0))
            exit_price = getattr(trade, "exit_price", 0.0)

            conf_reasons = review.get("confidence_reasons") or []
            conf_reason_text = "\n".join([f"- {r}" for r in conf_reasons]) if conf_reasons else "(no breakdown)"

            msg = (
                "🧠 Post-Trade AI Review\n"
                f"{symbol} | {result}\n"
                f"PnL: {pnl_val:.2f} | Confidence: {conf_val}/100\n"
                f"Exit: {exit_reason} | Entry: {float(entry_price or 0.0):.6f} | Exit: {float(exit_price or 0.0):.6f}\n\n"
                f"Confidence breakdown:\n{conf_reason_text}\n\n"
                f"What worked: {what_worked}\n"
                f"What failed: {what_failed}\n"
                f"Next time: {next_time}"
            )
            telegram._send_text(msg)

            current_params = {
                "min_rel_vol": cfg.get("min_rel_vol"),
                "min_gap_pct": cfg.get("min_gap_pct"),
                "r_multiple": cfg.get("r_multiple"),
                "risk_per_trade": cfg.get("risk_per_trade"),
            }

            suggestion = advisor.suggest_parameter_changes(review, current_params)

            if suggestion.get("apply") and suggestion.get("changes"):
                ch = suggestion["changes"]

                if "min_rel_vol" in ch:
                    cfg["min_rel_vol"] = float(ch["min_rel_vol"])
                if "min_gap_pct" in ch:
                    cfg["min_gap_pct"] = float(ch["min_gap_pct"])
                if "r_multiple" in ch:
                    cfg["r_multiple"] = float(ch["r_multiple"])
                if "risk_per_trade" in ch:
                    cfg["risk_per_trade"] = float(ch["risk_per_trade"])

                telegram._send_text(
                    "⚙️ AI Parameter Suggestions (APPLIED in-memory)\n"
                    f"Reason: {suggestion.get('reason','')}\n"
                    f"Changes: {suggestion.get('changes')}"
                )
            else:
                telegram._send_text(
                    "⚙️ AI Parameter Suggestions\n"
                    f"Reason: {suggestion.get('reason', 'No change')}"
                )

        except Exception as e:
            telegram._send_text(f"AI post-trade review failed: {e}")

        # tell risk manager about the closed trade
        try:
            if hasattr(risk, "register_close"):
                pnl = float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0)
                risk.register_close(getattr(trade, "symbol", ""), pnl)
        except Exception:
            pass

        # Export row to CSV
        exporter.write_trade(trade)

    bus.subscribe(
        EventType.PRICE_TICK,
        lambda p: portfolio.on_price_tick(p["symbol"], p["price"]),
    )

    # Subscribe post-trade review handler to trade closed events
    bus.subscribe(EventType.TRADE_CLOSED, on_trade_closed)

    # ---------- Scanner ----------
    # Universe/session filtering (optional): prefer universes.crypto/equities_us when present.
    universes = cfg.get("universes", {}) or {}
    eq_u = universes.get("equities_us", {}) or {}
    cr_u = universes.get("crypto", {}) or {}

    selected_symbols = list(cfg.get("symbols", []) or [])
    if eq_u.get("enabled"):
        session = str(eq_u.get("session", "us_rth")).strip().lower()
        if session == "us_open_2h" and not is_us_open_2h():
            selected_symbols = []
        else:
            selected_symbols = list(eq_u.get("symbols", []) or [])
    elif cr_u.get("enabled"):
        selected_symbols = list(cr_u.get("symbols", []) or [])

    if not selected_symbols:
        try:
            telegram._send_text("⏱️ Session filter active: no symbols scheduled for scanning right now.")
        except Exception:
            pass

    # Heartbeat startup ping (best-effort)
    try:
        heartbeat.on_startup(
            symbols=len(list(selected_symbols)),
            mode=(cfg.get("trading", {}) or {}).get("mode", (cfg.get("mode") or "paper")),
        )
    except Exception:
        pass

    # Top movers rotation: pick a subset per session/day (defaults to 20 if not configured)
    try:
        rot_n = int((cfg.get("top_movers") or {}).get("count", 20))
    except Exception:
        rot_n = 20
    symbols_rotated = get_top_movers(list(selected_symbols), n=rot_n)

    scanner = ScannerService(
        client=client,
        bus=bus,
        symbols=symbols_rotated,
        timeframe=cfg["timeframe"],
        mode=mode,
        equity=cfg["equity"],
        risk_per_trade=cfg["risk_per_trade"],
        r_multiple=cfg["r_multiple"],
        min_rel_vol=cfg["min_rel_vol"],
        min_gap_pct=cfg["min_gap_pct"],
        breakout_lookback=cfg.get("breakout_lookback", 12),
        ai_advisor=advisor,                 # pre-trade AI gate + comment
        orderflow=orderflow,
        min_bid_ask_ratio=orderflow_cfg.get("min_bid_ask_ratio", 1.25),
        min_buy_sell_ratio=orderflow_cfg.get("min_buy_sell_ratio", 1.15),
        loosen_factor=float(cfg.get("loosen_factor", 0.0)),  # default strict until toggled
        debug_heartbeat=bool(cfg.get("debug_heartbeat", False)),
    )

    # allow Telegram strict/loose switching
    telegram.scanner = scanner

    # allow Telegram live/paper switching (if your TelegramBot uses exec_engine)
    if hasattr(telegram, "exec_engine"):
        telegram.exec_engine = exec_engine

    await scanner.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
