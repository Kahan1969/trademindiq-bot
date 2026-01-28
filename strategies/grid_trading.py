"""
Grid Trading Strategy for TradeMindIQ
======================================
Strategy that places orders at regular price intervals.
Profits from volatility by buying low and selling high in ranges.
Safe, standalone strategy - does not modify core logic.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from core.models import Signal, Side
from .base import BaseStrategy


class GridTradingStrategy(BaseStrategy):
    """
    Grid trading strategy that:
    - Defines a price range (grid)
    - Places buy orders at grid levels below price
    - Places sell orders at grid levels above price
    - Profits from price oscillating within the range
    """
    
    name = "grid_trading"
    
    def __init__(
        self,
        # Grid settings
        grid_levels: int = 5,
        grid_spacing_pct: float = 0.5,  # 0.5% between grid levels
        # Range settings
        range_width_pct: float = 5.0,  # 5% total range width
        # Trading settings
        risk_per_trade: float = 0.10,
        max_positions: int = 3,
        # Session
        session_start_utc: int = 0,  # 24/7 for crypto
        session_end_utc: int = 23,
    ):
        self.grid_levels = grid_levels
        self.grid_spacing_pct = grid_spacing_pct / 100
        self.range_width_pct = range_width_pct / 100
        self.base_risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.session_start_utc = session_start_utc
        self.session_end_utc = session_end_utc
        
        # Track grid state
        self._grid_levels: Dict[str, List[float]] = {}  # symbol -> price levels
        self._active_grids: Dict[str, Dict] = {}  # symbol -> grid state
        self._last_price: Dict[str, float] = {}  # symbol -> last price
    
    def _in_session(self, last_ts_ms: int) -> bool:
        """Check if within trading session."""
        ts = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc)
        hour = ts.hour
        return self.session_start_utc <= hour < self.session_end_utc
    
    def _calculate_grid_levels(self, current_price: float) -> List[float]:
        """Calculate grid price levels around current price."""
        center = current_price
        half_range = current_price * self.range_width_pct / 2
        
        # Create levels centered on current price
        levels = []
        for i in range(self.grid_levels):
            offset = (i - self.grid_levels // 2) * (half_range * 2 / max(1, self.grid_levels - 1))
            level = center + offset
            levels.append(round(level, current_price.bit_length() if current_price > 1 else 6))
        
        return sorted(levels)
    
    def _init_grid(self, symbol: str, current_price: float) -> Dict:
        """Initialize a new grid for a symbol."""
        levels = self._calculate_grid_levels(current_price)
        self._grid_levels[symbol] = levels
        
        return {
            "symbol": symbol,
            "center_price": current_price,
            "levels": levels,
            "buy_orders": [],  # List of (level, filled_qty)
            "sell_orders": [],
            "total_buy_qty": 0.0,
            "total_sell_qty": 0.0,
            "realized_pnl": 0.0,
            "initialized_at": datetime.now(timezone.utc)
        }
    
    def _update_grid(self, symbol: str, current_price: float) -> Tuple[Optional[Signal], Dict]:
        """
        Update grid state and return signal if orders should be placed.
        
        Returns:
            Tuple of (Signal or None, updated grid state)
        """
        if symbol not in self._active_grids:
            grid = self._init_grid(symbol, current_price)
            self._active_grids[symbol] = grid
            return None, grid
        
        grid = self._active_grids[symbol]
        
        # Check if price moved significantly - reset grid
        price_move_pct = abs(current_price - grid["center_price"]) / grid["center_price"]
        if price_move_pct > self.range_width_pct:
            grid = self._init_grid(symbol, current_price)
            self._active_grids[symbol] = grid
        
        # Check if we should place new orders
        signal = None
        
        # Count active positions
        active_buys = len(grid["buy_orders"])
        active_sells = len(grid["sell_orders"])
        
        # Look for order fills based on price crossing levels
        for level in grid["levels"]:
            # Buy order fills when price drops to or below level
            if current_price <= level and level not in [o[0] for o in grid["buy_orders"]]:
                if active_buys < self.max_positions:
                    # Place buy order at this level
                    buy_qty = 0.1  # Fixed size per grid level
                    grid["buy_orders"].append((level, buy_qty))
                    grid["total_buy_qty"] += buy_qty
                    active_buys += 1
                    
                    # Generate signal
                    stop = level * (1 - self.grid_spacing_pct)
                    target = level * (1 + self.grid_spacing_pct)
                    
                    return Signal(
                        symbol=symbol,
                        exchange="kucoin",  # Default, can be overridden
                        timeframe="1m",
                        side=Side.BUY,
                        entry=level,
                        stop=stop,
                        target=target,
                        qty=buy_qty,
                        grid_level=level,
                        grid_type="buy",
                    ), grid
            
            # Sell order fills when price rises to or above level
            if current_price >= level and level not in [o[0] for o in grid["sell_orders"]]:
                if active_sells < self.max_positions:
                    # Place sell order at this level
                    sell_qty = 0.1  # Fixed size per grid level
                    grid["sell_orders"].append((level, sell_qty))
                    grid["total_sell_qty"] += sell_qty
                    active_sells += 1
        
        return signal, grid
    
    def _calculate_pnl_from_fills(
        self, 
        entry: float, 
        exit: float, 
        qty: float, 
        side: Side
    ) -> float:
        """Calculate P&L from a filled order."""
        if side == Side.BUY:
            return (exit - entry) * qty
        else:
            return (entry - exit) * qty
    
    def generate_signal(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        candles: List[List[float]],
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Generate grid trading signal."""
        if len(candles) < 10:
            return None
        
        last_ts = int(candles[-1][0])
        if not self._in_session(last_ts):
            return None
        
        current_price = float(candles[-1][4])
        self._last_price[symbol] = current_price
        
        # Update grid and check for signals
        signal, grid = self._update_grid(symbol, current_price)
        self._active_grids[symbol] = grid
        
        if signal:
            # Add exchange and timeframe to signal
            signal.exchange = exchange
            signal.timeframe = timeframe
        
        return signal
    
    def get_grid_status(self, symbol: str) -> Optional[Dict]:
        """Get current grid status for a symbol."""
        if symbol not in self._active_grids:
            return None
        
        grid = self._active_grids[symbol]
        return {
            "symbol": symbol,
            "center_price": grid["center_price"],
            "grid_levels": grid["levels"],
            "active_buy_orders": len(grid["buy_orders"]),
            "active_sell_orders": len(grid["sell_orders"]),
            "total_buy_qty": grid["total_buy_qty"],
            "total_sell_qty": grid["total_sell_qty"],
            "realized_pnl": grid["realized_pnl"],
            "initialized_at": grid["initialized_at"].isoformat()
        }
    
    def reset_grid(self, symbol: str):
        """Reset grid for a symbol (call when price breaks range)."""
        if symbol in self._active_grids:
            del self._active_grids[symbol]
        if symbol in self._grid_levels:
            del self._grid_levels[symbol]


class AdaptiveGridStrategy(BaseStrategy):
    """
    Adaptive Grid Strategy that adjusts grid spacing based on volatility.
    Wider grids during high volatility, tighter during low volatility.
    """
    
    name = "adaptive_grid"
    
    def __init__(
        self,
        base_grid_levels: int = 5,
        base_spacing_pct: float = 0.5,
        volatility_lookback: int = 20,
        volatility_multiplier: float = 1.5,
        risk_per_trade: float = 0.10,
        max_positions: int = 3,
    ):
        self.base_grid_levels = base_grid_levels
        self.base_spacing_pct = base_spacing_pct / 100
        self.volatility_lookback = volatility_lookback
        self.volatility_multiplier = volatility_multiplier
        self.base_risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        
        # State
        self._grid_levels: Dict[str, List[float]] = {}
        self._active_grids: Dict[str, Dict] = {}
        self._volatility: Dict[str, float] = {}
    
    def _calculate_volatility(self, closes: List[float]) -> float:
        """Calculate volatility as ATR percentage."""
        if len(closes) < 2:
            return self.base_spacing_pct
        
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        
        if not returns:
            return self.base_spacing_pct
        
        std_dev = (sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / len(returns)) ** 0.5
        
        # Convert to percentage and scale
        volatility_pct = std_dev * self.volatility_multiplier
        
        # Ensure minimum spacing
        return max(volatility_pct, self.base_spacing_pct * 0.5)
    
    def _calculate_adaptive_grid_levels(
        self, 
        current_price: float, 
        volatility: float,
        range_width_pct: float = 0.05
    ) -> List[float]:
        """Calculate grid levels based on volatility."""
        levels = []
        num_levels = self.base_grid_levels
        spacing = max(volatility, self.base_spacing_pct)
        
        # Range width adapts to volatility
        actual_range_width = max(range_width_pct, volatility * 3)
        
        half_range = current_price * actual_range_width / 2
        
        for i in range(num_levels):
            offset = (i - num_levels // 2) * (half_range * 2 / max(1, num_levels - 1))
            level = current_price + offset
            # Round to appropriate precision
            if level > 100:
                level = round(level, 2)
            elif level > 1:
                level = round(level, 4)
            else:
                level = round(level, 6)
            levels.append(level)
        
        return sorted(levels)
    
    def generate_signal(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        candles: List[List[float]],
        indicators: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Signal]:
        """Generate adaptive grid signal."""
        if len(candles) < self.volatility_lookback:
            return None
        
        closes = [c[4] for c in candles]
        current_price = float(closes[-1])
        
        # Calculate volatility
        volatility = self._calculate_volatility(closes)
        self._volatility[symbol] = volatility
        
        # Calculate adaptive grid
        levels = self._calculate_adaptive_grid_levels(current_price, volatility)
        self._grid_levels[symbol] = levels
        
        # Find nearest grid level for signal
        nearest_level = min(levels, key=lambda x: abs(x - current_price))
        level_idx = levels.index(nearest_level)
        
        # Determine if price is moving toward unfilled levels
        above_levels = [l for l in levels if l > current_price]
        below_levels = [l for l in levels if l < current_price]
        
        signal = None
        
        # Check if we're near a grid level
        distance_pct = abs(current_price - nearest_level) / current_price
        
        if distance_pct < volatility * 0.5:
            # Price is near a grid level - check direction
            if level_idx < len(levels) - 1 and levels[level_idx + 1] > current_price:
                # Next level is above - could be going up
                if above_levels:
                    target = above_levels[0]
                    stop = below_levels[-1] if below_levels else current_price * 0.98
                    
                    signal = Signal(
                        symbol=symbol,
                        exchange=exchange,
                        timeframe=timeframe,
                        side=Side.BUY,
                        entry=current_price,
                        stop=stop,
                        target=target,
                        qty=0.1,
                        grid_level=nearest_level,
                        grid_type="adaptive",
                        volatility=volatility,
                    )
            
            elif level_idx > 0 and levels[level_idx - 1] < current_price:
                # Next level is below - could be going down
                if below_levels:
                    target = below_levels[-1]
                    stop = above_levels[0] if above_levels else current_price * 1.02
                    
                    signal = Signal(
                        symbol=symbol,
                        exchange=exchange,
                        timeframe=timeframe,
                        side=Side.SELL,
                        entry=current_price,
                        stop=stop,
                        target=target,
                        qty=0.1,
                        grid_level=nearest_level,
                        grid_type="adaptive",
                        volatility=volatility,
                    )
        
        return signal
    
    def get_grid_status(self, symbol: str) -> Optional[Dict]:
        """Get adaptive grid status."""
        if symbol not in self._active_grids:
            return None
        
        return {
            "symbol": symbol,
            "volatility": self._volatility.get(symbol, 0),
            "grid_levels": self._grid_levels.get(symbol, []),
            "grid": self._active_grids[symbol]
        }
