from ai.post_trade_schema import PostTradeContext

def build_post_trade_context(trade) -> PostTradeContext:
    snap = (trade.meta or {}).get("signal_snapshot") or {}
    order_meta = (trade.meta or {}).get("order_meta") or {}

    return PostTradeContext(
        symbol=trade.symbol,
        exchange=getattr(trade, "exchange", None) or order_meta.get("exchange"),
        market_type=order_meta.get("market_type"),
        timeframe=snap.get("timeframe"),

        side=trade.side,
        strategy_name=getattr(trade, "strategy", None) or snap.get("strategy_name"),

        entry_ts=trade.entry_ts,
        exit_ts=trade.exit_ts,
        hold_seconds=(trade.exit_ts - trade.entry_ts) if trade.entry_ts and trade.exit_ts else None,

        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        qty=trade.qty,
        notional_usd=getattr(trade, "notional_usd", None),
        pnl_usd=trade.pnl_usd,
        pnl_r=getattr(trade, "pnl_r", None),
        fees_usd=getattr(trade, "fees_usd", None),
        slippage_bps=getattr(trade, "slippage_bps", None),

        # snapshot metrics (signal-time)
        breakout_level=snap.get("breakout_level"),
        breakout_close_above=snap.get("breakout_close_above"),
        gap_pct=snap.get("gap_pct"),
        body_pct=snap.get("body_pct"),
        upper_wick_pct=snap.get("upper_wick_pct"),
        vol_spike=snap.get("vol_spike"),
        ema_alignment=snap.get("ema_alignment"),

        orderflow_enabled=snap.get("orderflow_enabled"),
        book_depth=snap.get("book_depth"),
        bid_ask_ratio=snap.get("bid_ask_ratio"),
        buy_sell_ratio=snap.get("buy_sell_ratio"),
        spread_bps=snap.get("spread_bps"),

        exit_reason=getattr(trade, "exit_reason", None),
        max_favorable_excursion_r=getattr(trade, "mfe_r", None),
        max_adverse_excursion_r=getattr(trade, "mae_r", None),

        dry_run=(order_meta.get("trading_mode") == "paper"),

        indicators=snap.get("indicators") or {},
    )
