"""
TradeMindIQ Portfolio Tracker Dashboard + Trade Management
==========================================================
Real-time dashboard showing positions across all exchanges.
Safe, read-only - only reads data, never executes trades.
Scale-out / partial take-profit strategy for professional trade management.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from services.analytics import PerformanceAnalytics


@dataclass
class Position:
    """Current open position."""
    symbol: str
    exchange: str
    side: str
    entry_price: float
    current_price: float
    quantity: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_time: datetime
    duration_seconds: float


@dataclass
class PortfolioSummary:
    """Portfolio overview."""
    total_equity: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    open_positions: List[Position]
    positions_by_exchange: Dict[str, List[Position]]
    positions_by_symbol: Dict[str, Position]
    top_performers: List[Position]
    worst_performers: List[Position]
    exposure_by_symbol: Dict[str, float]
    exposure_by_side: Dict[str, float]


class PortfolioTracker:
    """
    Portfolio tracking and dashboard.
    Reads from trades.db and exchange APIs (simulated).
    Safe, read-only operations.
    Scale-out / partial take-profit strategy for professional trade management.
    """
    
    def __init__(self, db_path: str = "trades.db", telegram=None):
        self.db_path = db_path
        self.analytics = PerformanceAnalytics(db_path)
        self._positions: Dict[str, List[Position]] = defaultdict(list)
        self._current_prices: Dict[str, float] = {}
        self._open_orders: List = []  # Track open orders
        self.telegram = telegram  # Optional Telegram bot for notifications
        
        # Initialize with some simulated current prices
        self._initialize_simulated_prices()
    
    @property
    def open_orders(self) -> List:
        """Return list of open orders."""
        return getattr(self, '_open_orders', [])
    
    def register_order(self, order) -> None:
        """Register a new order/position."""
        if hasattr(order, 'symbol'):
            # Create a Position-like object for tracking
            try:
                entry = float(getattr(order, 'entry_price', getattr(order, 'filled_price', 0)) or 0)
                qty = float(getattr(order, 'qty', 0) or 0)
                side = getattr(order, 'side', 'BUY') or 'BUY'
                
                position = Position(
                    symbol=getattr(order, 'symbol', 'UNKNOWN'),
                    exchange="kucoin",
                    side=side,
                    entry_price=entry,
                    current_price=entry,
                    quantity=qty,
                    unrealized_pnl=0,
                    unrealized_pnl_pct=0,
                    entry_time=datetime.now(),
                    duration_seconds=0
                )
                self._positions["kucoin"].append(position)
                self._open_orders.append(order)
            except Exception as e:
                print(f"[PortfolioTracker] Error registering order: {e}")
    
    def _initialize_simulated_prices(self):
        """Initialize with realistic current prices."""
        self._current_prices = {
            "BTC/USDT": 100000.0,
            "ETH/USDT": 3500.0,
            "SOL/USDT": 200.0,
            "BNB/USDT": 700.0,
            "XRP/USDT": 2.5,
            "ADA/USDT": 0.35,
            "DOGE/USDT": 0.08,
            "AVAX/USDT": 25.0,
            "LINK/USDT": 15.0,
            "LTC/USDT": 95.0,
            "MATIC/USDT": 0.4,
            "DOT/USDT": 5.0,
            "UNI/USDT": 10.0,
            "ATOM/USDT": 8.0,
            "XMR/USDT": 150.0,
            "NEAR/USDT": 4.0,
            "APT/USDT": 8.0,
            "ARB/USDT": 0.6,
            "OP/USDT": 1.5,
            "SUI/USDT": 2.5,
        }
    
    # ==================== SCALE-OUT STRATEGY ====================
    
    def on_price_tick(self, symbol: str, current_price: float) -> Optional[dict]:
        """
        Monitor price ticks for scale-out signals.
        
        Returns:
            Dict with scale_out event info if TP1 hit, None otherwise
        """
        # Get open positions for this symbol
        summary = self.get_portfolio_summary()
        position = summary.positions_by_symbol.get(symbol)
        
        if not position:
            return None
        
        # Initialize scale-out state if not exists
        if not hasattr(position, "meta") or position.meta is None:
            position.meta = {}
        
        meta = position.meta
        
        # Initialize state tracking
        if "remaining_qty" not in meta:
            meta["remaining_qty"] = position.quantity
        if "tp1_done" not in meta:
            meta["tp1_done"] = False
        if "fills" not in meta:
            meta["fills"] = []
        if "entry_price" not in meta:
            meta["entry_price"] = position.entry_price
        if "stop_init" not in meta:
            meta["stop_init"] = getattr(position, "stop_price", None) or position.entry_price * 0.99
        if "risk_per_unit" not in meta:
            meta["risk_per_unit"] = abs(meta["entry_price"] - meta["stop_init"])
        
        # Check if already fully closed
        if meta.get("remaining_qty", 0) <= 0:
            return None
        
        # Get scale-out config
        scale_cfg = self._get_scale_out_config()
        if not scale_cfg.get("enabled", False):
            return None
        
        # Calculate direction and prices
        side = position.side.upper()
        sign = 1 if side == "BUY" else -1
        entry = meta["entry_price"]
        risk_per_unit = meta.get("risk_per_unit", abs(entry - meta["stop_init"]))
        
        # TP1 calculation
        tp1_r = scale_cfg.get("tp1_r", 1.0)
        tp1_price = entry + sign * (tp1_r * risk_per_unit)
        
        # Check TP1 hit
        tp1_hit = False
        if sign > 0:  # Long
            tp1_hit = current_price >= tp1_price
        else:  # Short
            tp1_hit = current_price <= tp1_price
        
        if tp1_hit and not meta.get("tp1_done"):
            # Execute TP1 partial close
            tp1_frac = scale_cfg.get("tp1_frac", 0.5)
            remaining_qty = meta["remaining_qty"]
            qty_to_close = remaining_qty * tp1_frac
            
            # Calculate PnL for this fill
            pnl1 = (current_price - entry) * qty_to_close * sign
            
            # Record the fill
            fill_record = {
                "reason": "TP1",
                "qty": qty_to_close,
                "price": current_price,
                "pnl_usd": pnl1,
                "timestamp": datetime.now().isoformat()
            }
            meta["fills"].append(fill_record)
            meta["realized_pnl_usd"] = meta.get("realized_pnl_usd", 0) + pnl1
            meta["remaining_qty"] = remaining_qty - qty_to_close
            meta["tp1_done"] = True
            
            # Move stop to breakeven (entry + small buffer for fees)
            buffer = scale_cfg.get("breakeven_buffer", 0.001)
            meta["stop_price"] = entry * (1 + buffer * sign)
            
            # Send Telegram notification
            self._send_scale_out_notification("TP1", symbol, qty_to_close, current_price, pnl1, meta["remaining_qty"])
            
            return {
                "event": "TP1_HIT",
                "symbol": symbol,
                "qty_closed": qty_to_close,
                "price": current_price,
                "pnl_usd": pnl1,
                "remaining_qty": meta["remaining_qty"],
                "new_stop": meta["stop_price"]
            }
        
        # Check TP2 exit for remaining position
        tp2_enabled = scale_cfg.get("tp2_enabled", True)
        if tp2_enabled and meta.get("tp1_done") and meta.get("remaining_qty", 0) > 0:
            tp2_r = scale_cfg.get("tp2_r", 3.0)
            tp2_price = entry + sign * (tp2_r * risk_per_unit)
            
            tp2_hit = False
            if sign > 0:  # Long
                tp2_hit = current_price >= tp2_price
            else:  # Short
                tp2_hit = current_price <= tp2_price
            
            if tp2_hit:
                remaining_qty = meta["remaining_qty"]
                pnl2 = (current_price - entry) * remaining_qty * sign
                
                fill_record = {
                    "reason": "TP2",
                    "qty": remaining_qty,
                    "price": current_price,
                    "pnl_usd": pnl2,
                    "timestamp": datetime.now().isoformat()
                }
                meta["fills"].append(fill_record)
                meta["realized_pnl_usd"] = meta.get("realized_pnl_usd", 0) + pnl2
                meta["remaining_qty"] = 0
                meta["exit_reason"] = "TP2"
                
                # Send Telegram notification
                self._send_scale_out_notification("TP2", symbol, remaining_qty, current_price, pnl2, 0)
                
                return {
                    "event": "TP2_HIT",
                    "symbol": symbol,
                    "qty_closed": remaining_qty,
                    "price": current_price,
                    "pnl_usd": pnl2,
                    "remaining_qty": 0,
                    "exit_reason": "TP2"
                }
        
        return None
    
    def _get_scale_out_config(self) -> dict:
        """Load scale-out config from settings."""
        # Try to load from config file
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.yaml")
        try:
            import yaml
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("trade_mgmt", {}).get("scale_out", {})
        except Exception:
            # Default config if file not found
            return {
                "enabled": True,
                "tp1_r": 1.0,
                "tp1_frac": 0.5,
                "tp2_enabled": True,
                "tp2_r": 3.0,
                "breakeven_buffer": 0.001
            }
    
    def _send_scale_out_notification(self, stage: str, symbol: str, qty: float, price: float, pnl: float, remaining: float) -> None:
        """Send Telegram notification for scale-out events."""
        if not self.telegram:
            return
        
        try:
            emoji = "🟢" if pnl >= 0 else "🔴"
            
            if stage == "TP1":
                msg = (
                    f"🎯 **SCALE-OUT {stage}** {emoji}\n\n"
                    f"**{symbol}**\n"
                    f"Closed: {qty:.4f} @ ${price:.4f}\n"
                    f"P/L: ${pnl:+.2f}\n"
                    f"Remaining: {remaining:.4f}\n"
                    f"Stop moved to breakeven"
                )
            else:  # TP2
                total_pnl = pnl  # This is the final fill PnL
                msg = (
                    f"🏁 **SCALE-OUT {stage} - FULL EXIT** {emoji}\n\n"
                    f"**{symbol}**\n"
                    f"Closed: {qty:.4f} @ ${price:.4f}\n"
                    f"P/L: ${pnl:+.2f}\n"
                    f"Position fully closed"
                )
            
            self.telegram._send_text_with_menu(msg)
        except Exception:
            pass
    
    def get_scale_out_status(self, symbol: str) -> dict:
        """Get scale-out status for a position."""
        summary = self.get_portfolio_summary()
        position = summary.positions_by_symbol.get(symbol)
        
        if not position:
            return {"error": "No position found"}
        
        meta = getattr(position, "meta", {}) or {}
        
        return {
            "symbol": symbol,
            "entry_price": meta.get("entry_price", position.entry_price),
            "remaining_qty": meta.get("remaining_qty", position.quantity),
            "tp1_done": meta.get("tp1_done", False),
            "realized_pnl_usd": meta.get("realized_pnl_usd", 0),
            "fills": meta.get("fills", []),
            "stop_price": meta.get("stop_price", None)
        }
    
    def initialize_trade_scale_out(self, symbol: str, entry_price: float, qty: float, stop_price: float) -> None:
        """Initialize scale-out tracking for a new trade."""
        position = None
        for p in self._positions.get("kucoin", []):
            if p.symbol == symbol:
                position = p
                break
        
        if not position:
            # Create a tracking entry
            from dataclasses import asdict
            position = Position(
                symbol=symbol,
                exchange="kucoin",
                side="BUY",
                entry_price=entry_price,
                current_price=entry_price,
                quantity=qty,
                unrealized_pnl=0,
                unrealized_pnl_pct=0,
                entry_time=datetime.now(),
                duration_seconds=0
            )
            self._positions["kucoin"].append(position)
        
        # Initialize meta
        if not hasattr(position, "meta") or position.meta is None:
            position.meta = {}
        
        position.meta.update({
            "remaining_qty": qty,
            "tp1_done": False,
            "fills": [],
            "realized_pnl_usd": 0,
            "entry_price": entry_price,
            "stop_init": stop_price,
            "risk_per_unit": abs(entry_price - stop_price)
        })
    
    def _fetch_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch current prices from exchange APIs.
        In production, this would call KuCoin, Alpaca, etc.
        """
        # For now, return simulated prices
        # In production:
        # prices = {}
        # for symbol in symbols:
        #     if "kucoin" in enabled_exchanges:
        #         prices[symbol] = await fetch_kucoin_price(symbol)
        #     elif "alpaca" in enabled_exchanges:
        #         prices[symbol] = await fetch_alpaca_price(symbol)
        
        return {s: self._current_prices.get(s, 100.0) for s in symbols}
    
    def _calculate_unrealized_pnl(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_price: float,
        quantity: float
    ) -> Tuple[float, float]:
        """Calculate unrealized P&L and percentage."""
        if side.upper() == "BUY":
            pnl = (current_price - entry_price) * quantity
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl = (entry_price - current_price) * quantity
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        return pnl, pnl_pct
    
    def scan_for_open_positions(self) -> List[Position]:
        """
        Scan trades database for open positions.
        In production, this would check exchange APIs directly.
        """
        # Try to read from trades.db, fall back to demo mode on error
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, side, entry, exit_price, pnl, created_at, closed_at
                FROM trades
                WHERE closed_at IS NULL
                LIMIT 50
            """)
            rows = cursor.fetchall()
            conn.close()
        except Exception:
            rows = []
        
        # Simulate open positions based on recent activity
        # In production, you'd query exchange APIs for actual open positions
        open_positions = []
        
        # Get unique symbols from database
        symbols = list(set(row[0] for row in rows)) if rows else []
        
        # If no positions in DB, use demo positions for display
        if not symbols:
            symbols = ["BTC/USDT", "SOL/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT"]
        
        current_prices = self._fetch_current_prices(symbols)
        
        # Demo positions for showcase
        now = datetime.now()
        demo_positions = [
            {"symbol": "BTC/USDT", "side": "BUY", "entry": 98500.0, "qty": 0.01},
            {"symbol": "SOL/USDT", "side": "BUY", "entry": 195.0, "qty": 2.0},
            {"symbol": "ETH/USDT", "side": "BUY", "entry": 3400.0, "qty": 0.2},
        ]
        
        for pos in demo_positions:
            symbol = pos["symbol"]
            current = current_prices.get(symbol, 100.0)
            pnl, pnl_pct = self._calculate_unrealized_pnl(
                symbol, pos["side"], pos["entry"], current, pos["qty"]
            )
            
            position = Position(
                symbol=symbol,
                exchange="kucoin",
                side=pos["side"],
                entry_price=pos["entry"],
                current_price=current,
                quantity=pos["qty"],
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                entry_time=now - timedelta(minutes=30),
                duration_seconds=1800
            )
            open_positions.append(position)
        
        self._positions["kucoin"] = open_positions
        return open_positions
    
    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get complete portfolio overview."""
        positions = self.scan_for_open_positions()
        
        # Calculate totals
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        
        # Get realized P&L from analytics
        analytics_summary = self.analytics.calculate_performance_summary()
        total_realized = analytics_summary.total_pnl
        
        # Group by exchange
        positions_by_exchange = defaultdict(list)
        for p in positions:
            positions_by_exchange[p.exchange].append(p)
        
        # Group by symbol
        positions_by_symbol = {p.symbol: p for p in positions}
        
        # Sort performers
        sorted_by_pnl = sorted(positions, key=lambda p: p.unrealized_pnl, reverse=True)
        top_performers = sorted_by_pnl[:3]
        worst_performers = sorted_by_pnl[-3:]
        
        # Calculate exposure
        exposure_by_symbol = {}
        exposure_by_side = {"BUY": 0.0, "SELL": 0.0}
        
        for p in positions:
            exposure = p.current_price * p.quantity
            exposure_by_symbol[p.symbol] = exposure
            exposure_by_side[p.side] += exposure
        
        total_equity = total_realized + total_unrealized + 500  # Initial equity
        
        return PortfolioSummary(
            total_equity=total_equity,
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            open_positions=positions,
            positions_by_exchange=dict(positions_by_exchange),
            positions_by_symbol=positions_by_symbol,
            top_performers=top_performers,
            worst_performers=worst_performers,
            exposure_by_symbol=exposure_by_symbol,
            exposure_by_side=exposure_by_side
        )
    
    def generate_dashboard(self) -> str:
        """Generate formatted dashboard text."""
        summary = self.get_portfolio_summary()
        
        lines = [
            "=" * 50,
            "🤖 TRADEMINDIQ PORTFOLIO DASHBOARD",
            "=" * 50,
            f"Last Updated: {datetime.now().strftime('%H:%M:%S')}",
            "",
            "📊 PORTFOLIO SUMMARY",
            "-" * 40,
            f"Total Equity:     ${summary.total_equity:,.2f}",
            f"Realized P/L:     ${summary.total_realized_pnl:,.2f}",
            f"Unrealized P/L:   ${summary.total_unrealized_pnl:,.2f}",
            f"Net P/L:          ${summary.total_realized_pnl + summary.total_unrealized_pnl:,.2f}",
            f"Open Positions:   {len(summary.open_positions)}",
            "",
        ]
        
        if summary.open_positions:
            lines.extend([
                "📍 OPEN POSITIONS",
                "-" * 40,
            ])
            
            for p in summary.open_positions:
                emoji = "🟢" if p.unrealized_pnl > 0 else "🔴"
                lines.append(
                    f"{emoji} {p.symbol:<12} {p.side:<4} "
                    f"Entry: ${p.entry_price:.4f}  "
                    f"Cur: ${p.current_price:.4f}  "
                    f"P/L: ${p.unrealized_pnl:>8.2f} ({p.unrealized_pnl_pct:>5.2f}%)"
                )
            
            lines.extend([
                "",
                "🏆 TOP PERFORMERS",
                "-" * 40,
            ])
            
            for p in summary.top_performers:
                lines.append(f"  {p.symbol:<12} +${p.unrealized_pnl:.2f}")
            
            if summary.worst_performers:
                lines.extend([
                    "",
                    "⚠️ UNDERPERFORMERS",
                    "-" * 40,
                ])
                
                for p in summary.worst_performers:
                    lines.append(f"  {p.symbol:<12} ${p.unrealized_pnl:.2f}")
        
        else:
            lines.append("📭 No open positions")
        
        if summary.exposure_by_side:
            lines.extend([
                "",
                "📈 EXPOSURE BY SIDE",
                "-" * 40,
                f"  LONG:  ${summary.exposure_by_side.get('BUY', 0):,.2f}",
                f"  SHORT: ${summary.exposure_by_side.get('SELL', 0):,.2f}",
            ])
        
        lines.extend([
            "",
            "=" * 50,
        ])
        
        return "\n".join(lines)
    
    def generate_compact_dashboard(self) -> str:
        """Generate compact dashboard for Telegram."""
        summary = self.get_portfolio_summary()
        
        emoji = "🟢" if summary.total_realized_pnl + summary.total_unrealized_pnl >= 0 else "🔴"
        
        lines = [
            f"🤖 **TradeMindIQ Dashboard**",
            "",
            f"**Equity:** ${summary.total_equity:,.2f}",
            f"**Net P/L:** {emoji} ${summary.total_realized_pnl + summary.total_unrealized_pnl:,.2f}",
            f"**Open:** {len(summary.open_positions)} positions",
            "",
        ]
        
        if summary.open_positions:
            for p in summary.open_positions[:5]:  # Max 5 for Telegram
                pos_emoji = "🟢" if p.unrealized_pnl > 0 else "🔴"
                lines.append(
                    f"{pos_emoji} {p.symbol:<10} {p.side:<4} "
                    f"${p.unrealized_pnl:>7.2f}"
                )
        
        if len(summary.open_positions) > 5:
            lines.append(f"... and {len(summary.open_positions) - 5} more")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def export_positions_json(self, filepath: str = "positions.json"):
        """Export positions to JSON."""
        summary = self.get_portfolio_summary()
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_equity": round(summary.total_equity, 2),
            "total_realized_pnl": round(summary.total_realized_pnl, 2),
            "total_unrealized_pnl": round(summary.total_unrealized_pnl, 2),
            "open_positions": [
                {
                    "symbol": p.symbol,
                    "exchange": p.exchange,
                    "side": p.side,
                    "entry_price": round(p.entry_price, 6),
                    "current_price": round(p.current_price, 6),
                    "quantity": round(p.quantity, 6),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(p.unrealized_pnl_pct, 2),
                    "duration_seconds": p.duration_seconds
                }
                for p in summary.open_positions
            ],
            "exposure_by_symbol": {k: round(v, 2) for k, v in summary.exposure_by_symbol.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Positions exported to {filepath}")
        return data
    
    def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        summary = self.get_portfolio_summary()
        return summary.positions_by_symbol.get(symbol)


# Convenience functions
def portfolio_dashboard():
    """Print portfolio dashboard."""
    tracker = PortfolioTracker()
    print(tracker.generate_dashboard())


def portfolio_dashboard_compact():
    """Print compact dashboard for Telegram."""
    tracker = PortfolioTracker()
    print(tracker.generate_compact_dashboard())


def export_all_positions():
    """Export all positions to JSON."""
    tracker = PortfolioTracker()
    return tracker.export_positions_json()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "compact":
            portfolio_dashboard_compact()
        elif command == "export":
            export_all_positions()
        else:
            print("Usage: python portfolio.py [compact|export]")
    else:
        portfolio_dashboard()


# Backwards-compatible alias for code that expects PortfolioService
PortfolioService = PortfolioTracker
