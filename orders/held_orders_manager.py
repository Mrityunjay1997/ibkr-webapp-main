"""
Held Orders Off-Market Manager

Manages orders that are held locally until specified conditions are met:
- Candlestick breakouts (high/low breakout with % offset)
- Moving average crossovers (crosses above/below MA)

Orders can be set for entry AND exit conditions, supporting both long and short trades.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
import pandas as pd
from enum import Enum

logger = logging.getLogger("held_orders")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrderSide(Enum):
    """Order side (direction)"""
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """Order type"""
    LIMIT = "limit"
    MARKET = "market"


class ConditionType(Enum):
    """Condition type"""
    CANDLE_BREAKOUT = "candle_breakout"
    MA_CROSSOVER = "ma_crossover"


class ConditionPhase(Enum):
    """Whether condition is for entry or exit"""
    ENTRY = "entry"
    EXIT = "exit"


@dataclass
class CandleBreakoutCondition:
    """
    Candlestick breakout condition config.
    
    Monitors for a break of recent candle high/low with configurable lookback.
    """
    timeframe: str  # '1min', '5min', '15min', '1h', 'daily', etc
    candles_to_check: int  # Number of recent candles to get high/low from (e.g., 5)
    break_direction: str  # 'above_high' or 'below_low'
    entry_offset_pct: float  # % above/below reference level (for limit order)
    lookback_bars: int = 5  # How many bars back to get high/low from
    
    def __post_init__(self):
        """Validate inputs"""
        if self.break_direction not in ['above_high', 'below_low']:
            raise ValueError("break_direction must be 'above_high' or 'below_low'")
        if self.lookback_bars < 1 or self.lookback_bars > 100:
            raise ValueError("lookback_bars must be 1-100")


@dataclass
class MovingAverageCondition:
    """
    Moving average crossover condition config.
    
    Monitors for price crossing above/below a selected moving average with % offset.
    """
    timeframe: str  # '1min', '5min', '15min', '1h', 'daily', etc
    ma_type: str  # 'sma' or 'ema'
    ma_period: int  # Period for MA (e.g., 20, 50, 200)
    cross_direction: str  # 'above' or 'below'
    cross_offset_pct: float  # % offset from MA for entry
    
    def __post_init__(self):
        """Validate inputs"""
        if self.ma_type not in ['sma', 'ema']:
            raise ValueError("ma_type must be 'sma' or 'ema'")
        if self.cross_direction not in ['above', 'below']:
            raise ValueError("cross_direction must be 'above' or 'below'")
        if self.ma_period < 2 or self.ma_period > 500:
            raise ValueError("ma_period must be 2-500")


@dataclass
class HeldOrderCondition:
    """A condition configuration for a held order"""
    condition_type: str  # 'candle_breakout' or 'ma_crossover'
    phase: str  # 'entry' or 'exit'
    config: Dict  # Condition-specific config (see Candle/MA dataclasses)
    status: str = 'pending'  # 'pending', 'triggered', 'skipped'
    triggered_at: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HeldOrder:
    """
    A held order that waits for conditions to be met before execution.
    
    Can have multiple conditions (e.g., entry condition + exit condition).
    Order executes when ALL entry conditions are met.
    """
    order_id: str  # UUID
    symbol: str
    side: str  # 'long' or 'short'
    quantity: int
    order_type: str  # 'limit' or 'market'
    limit_price: Optional[float] = None  # For limit orders
    
    # Entry/Exit conditions
    entry_conditions: List[HeldOrderCondition] = field(default_factory=list)
    exit_conditions: List[HeldOrderCondition] = field(default_factory=list)
    
    # Status tracking
    status: str = 'active'  # 'active', 'triggered', 'executed', 'cancelled'
    entry_executed: bool = False
    entry_executed_at: Optional[str] = None
    entry_executed_price: Optional[float] = None
    
    # Metadata
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'order_type': self.order_type,
            'limit_price': self.limit_price,
            'entry_conditions': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.entry_conditions],
            'exit_conditions': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.exit_conditions],
            'status': self.status,
            'entry_executed': self.entry_executed,
            'entry_executed_at': self.entry_executed_at,
            'entry_executed_price': self.entry_executed_price,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'notes': self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HeldOrder':
        """Create from dictionary"""
        return cls(
            order_id=data.get('order_id', str(uuid.uuid4())),
            symbol=data.get('symbol', ''),
            side=data.get('side', 'long'),
            quantity=int(data.get('quantity', 1)),
            order_type=data.get('order_type', 'limit'),
            limit_price=data.get('limit_price'),
            entry_conditions=[HeldOrderCondition(**c) if isinstance(c, dict) else c 
                            for c in data.get('entry_conditions', [])],
            exit_conditions=[HeldOrderCondition(**c) if isinstance(c, dict) else c 
                           for c in data.get('exit_conditions', [])],
            status=data.get('status', 'active'),
            entry_executed=data.get('entry_executed', False),
            entry_executed_at=data.get('entry_executed_at'),
            entry_executed_price=data.get('entry_executed_price'),
            created_at=data.get('created_at', utc_now_iso()),
            modified_at=data.get('modified_at', utc_now_iso()),
            notes=data.get('notes', ''),
        )


class HeldOrdersManager:
    """Manager for held orders collection"""
    
    def __init__(self):
        self.orders: Dict[str, HeldOrder] = {}
    
    def create_order(self, symbol: str, side: str, quantity: int, 
                    order_type: str = 'limit', limit_price: Optional[float] = None,
                    notes: str = "") -> HeldOrder:
        """Create a new held order"""
        order = HeldOrder(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            notes=notes
        )
        self.orders[order.order_id] = order
        logger.info(f"Created held order {order.order_id} for {symbol} {side}")
        return order
    
    def add_entry_condition(self, order_id: str, condition: HeldOrderCondition):
        """Add an entry condition to an order"""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        self.orders[order_id].entry_conditions.append(condition)
        logger.info(f"Added entry condition to order {order_id}")
    
    def add_exit_condition(self, order_id: str, condition: HeldOrderCondition):
        """Add an exit condition to an order"""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        self.orders[order_id].exit_conditions.append(condition)
        logger.info(f"Added exit condition to order {order_id}")
    
    def get_active_orders_for_symbol(self, symbol: str) -> List[HeldOrder]:
        """Get all active held orders for a symbol"""
        return [o for o in self.orders.values() 
                if o.symbol == symbol and o.status == 'active']
    
    def mark_entry_executed(self, order_id: str, price: float):
        """Mark the entry as executed"""
        if order_id in self.orders:
            order = self.orders[order_id]
            order.entry_executed = True
            order.entry_executed_at = utc_now_iso()
            order.entry_executed_price = price
            logger.info(f"Order {order_id} entry executed at {price}")
    
    def cancel_order(self, order_id: str):
        """Cancel an order"""
        if order_id in self.orders:
            self.orders[order_id].status = 'cancelled'
            logger.info(f"Cancelled order {order_id}")
    
    def get_order(self, order_id: str) -> Optional[HeldOrder]:
        """Get order by ID"""
        return self.orders.get(order_id)
    
    def to_dict(self) -> Dict:
        """Serialize all orders"""
        return {
            order_id: order.to_dict() 
            for order_id, order in self.orders.items()
        }
    
    def from_dict(self, data: Dict):
        """Load orders from dict"""
        self.orders = {
            order_id: HeldOrder.from_dict(order_data)
            for order_id, order_data in data.items()
        }
        logger.info(f"Loaded {len(self.orders)} held orders")


# ============================================================================
# CONDITION CHECKING ENGINE
# ============================================================================

class ConditionChecker:
    """Evaluates whether held order conditions are met"""
    
    @staticmethod
    def check_candle_breakout(symbol: str, ohlc_data: pd.DataFrame, 
                            config: Dict) -> bool:
        """
        Check if price has broken above/below recent candle high/low.
        
        Args:
            symbol: Stock symbol
            ohlc_data: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
            config: Dict with keys: timeframe, break_direction, lookback_bars, entry_offset_pct
        
        Returns:
            True if breakout condition is met
        """
        if ohlc_data.empty or len(ohlc_data) < 2:
            return False
        
        try:
            lookback = int(config.get('lookback_bars', 5))
            lookback = min(lookback, len(ohlc_data) - 1)  # Can't look back further than data
            break_dir = config.get('break_direction', 'above_high')
            offset_pct = float(config.get('entry_offset_pct', 0))
            
            # Get recent candle high/low
            recent_candles = ohlc_data.iloc[-lookback-1:-1]  # Exclude current candle
            ref_high = recent_candles['high'].max()
            ref_low = recent_candles['low'].min()
            
            # Current price
            current_price = ohlc_data.iloc[-1]['close']
            
            # Check breakout with offset
            if break_dir == 'above_high':
                breakout_level = ref_high * (1 + offset_pct / 100.0)
                return current_price > breakout_level
            else:  # below_low
                breakout_level = ref_low * (1 - offset_pct / 100.0)
                return current_price < breakout_level
        
        except Exception as e:
            logger.error(f"Error checking candle breakout for {symbol}: {e}")
            return False
    
    @staticmethod
    def check_ma_crossover(symbol: str, price_data: pd.Series, 
                          ma_data: pd.Series, config: Dict) -> bool:
        """
        Check if price has crossed above/below moving average.
        
        Args:
            symbol: Stock symbol
            price_data: Series of prices (e.g., close prices)
            ma_data: Series of MA values (pre-calculated)
            config: Dict with keys: cross_direction, cross_offset_pct
        
        Returns:
            True if crossover condition is met
        """
        if len(price_data) < 2 or len(ma_data) < 2:
            return False
        
        try:
            cross_dir = config.get('cross_direction', 'above')
            offset_pct = float(config.get('cross_offset_pct', 0))
            
            # Current and previous price/MA
            current_price = price_data.iloc[-1]
            prev_price = price_data.iloc[-2]
            
            current_ma = ma_data.iloc[-1]
            prev_ma = ma_data.iloc[-2]
            
            # Apply offset to MA
            ma_with_offset = current_ma * (1 + offset_pct / 100.0) if cross_dir == 'above' else current_ma * (1 - offset_pct / 100.0)
            prev_ma_with_offset = prev_ma * (1 + offset_pct / 100.0) if cross_dir == 'above' else prev_ma * (1 - offset_pct / 100.0)
            
            # Check crossover
            if cross_dir == 'above':
                # Currently above MA and was below
                return current_price > ma_with_offset and prev_price <= prev_ma_with_offset
            else:  # below
                # Currently below MA and was above
                return current_price < ma_with_offset and prev_price >= prev_ma_with_offset
        
        except Exception as e:
            logger.error(f"Error checking MA crossover for {symbol}: {e}")
            return False
    
    @staticmethod
    def evaluate_order_conditions(held_order: HeldOrder, market_data: Dict) -> Tuple[bool, str]:
        """
        Evaluate if all entry conditions are met for a held order.
        
        Args:
            held_order: HeldOrder instance
            market_data: Dict with keys for each condition type's data
                e.g., {
                    'ohlc_1min': DataFrame,
                    'ohlc_5min': DataFrame,
                    'sma_20_5min': Series,
                    'ema_50_1h': Series,
                    ...
                }
        
        Returns:
            Tuple: (all_met: bool, reason: str)
        """
        if not held_order.entry_conditions:
            return False, "No entry conditions defined"
        
        reasons = []
        all_met = True
        
        for condition in held_order.entry_conditions:
            if condition.condition_type == 'candle_breakout':
                tf = condition.config.get('timeframe', '1min')
                ohlc_key = f'ohlc_{tf}'
                
                if ohlc_key not in market_data:
                    reasons.append(f"Missing OHLC data for {tf}")
                    all_met = False
                    continue
                
                if ConditionChecker.check_candle_breakout(
                    held_order.symbol,
                    market_data[ohlc_key],
                    condition.config
                ):
                    reasons.append(f"Candle breakout ({tf}) MET")
                else:
                    reasons.append(f"Candle breakout ({tf}) not met")
                    all_met = False
            
            elif condition.condition_type == 'ma_crossover':
                tf = condition.config.get('timeframe', '1min')
                ma_type = condition.config.get('ma_type', 'sma')
                ma_period = condition.config.get('ma_period', 20)
                
                price_key = f'close_{tf}'
                ma_key = f'{ma_type}_{ma_period}_{tf}'
                
                if price_key not in market_data or ma_key not in market_data:
                    reasons.append(f"Missing price/MA data for {ma_type}_{ma_period} on {tf}")
                    all_met = False
                    continue
                
                if ConditionChecker.check_ma_crossover(
                    held_order.symbol,
                    market_data[price_key],
                    market_data[ma_key],
                    condition.config
                ):
                    reasons.append(f"MA crossover ({ma_type}_{ma_period} on {tf}) MET")
                else:
                    reasons.append(f"MA crossover ({ma_type}_{ma_period} on {tf}) not met")
                    all_met = False
        
        reason = " | ".join(reasons)
        return all_met, reason


# ============================================================================
# HELD ORDER LIMIT PRICE CALCULATOR
# ============================================================================

class HeldOrderLimitPriceCalculator:
    """
    Calculates dynamic limit prices for held orders based on entry/exit criteria.
    
    Supports calculating limit prices from:
    - Candlestick patterns (high/low with lookback)
    - Moving averages (SMA, EMA)
    - Volatility measures (ATR)
    - Support/resistance levels
    
    Prices update dynamically as new market data arrives and candles update.
    """
    
    @staticmethod
    def calculate_entry_limit_price(symbol: str, side: str, market_data: Dict,
                                   entry_config: Dict, offset_pct: float = 0) -> Optional[float]:
        """
        Calculate entry limit price from entry criteria data.
        
        Args:
            symbol: Stock symbol
            side: 'long' or 'short'
            market_data: Current market data dict with indicators:
                - 'candlestick_high_{lookback}_{timeframe}': Recent high
                - 'candlestick_low_{lookback}_{timeframe}': Recent low
                - 'sma_{period}_{timeframe}': SMA value
                - 'ema_{period}_{timeframe}': EMA value
                - 'atr_{period}_{timeframe}': ATR value
                - 'close': Current close price
            entry_config: Dict with keys like:
                - 'type': 'candlestick_high', 'candlestick_low', 'sma', 'ema', 'atr', etc.
                - 'lookback_bars': For candlestick patterns
                - 'period': For moving averages/ATR
                - 'timeframe': '5min', '15min', '1h', 'daily', etc.
            offset_pct: Additional % offset from calculated level (for limit order slippage buffer)
        
        Returns:
            Calculated limit price, or None if calculation fails
        """
        if not market_data or not entry_config:
            return None
        
        try:
            config_type = entry_config.get('type', '').lower()
            timeframe = entry_config.get('timeframe', '1min')
            
            # Candlestick breakout entry (long: above recent high, short: below recent low)
            if config_type.startswith('candlestick'):
                lookback = entry_config.get('lookback_bars', 5)
                
                if side == 'long':
                    # Long entry: above recent high
                    data_key = f'candlestick_high_{lookback}_{timeframe}'
                    if data_key in market_data:
                        base_price = float(market_data[data_key])
                        # For limit orders on long breakout, set slightly above the high
                        limit_offset = entry_config.get('entry_offset_pct', 0.1)
                        final_price = base_price * (1 + (limit_offset + offset_pct) / 100.0)
                        return round(final_price, 2)
                
                else:  # short
                    # Short entry: below recent low
                    data_key = f'candlestick_low_{lookback}_{timeframe}'
                    if data_key in market_data:
                        base_price = float(market_data[data_key])
                        # For limit orders on short breakout, set slightly below the low
                        limit_offset = entry_config.get('entry_offset_pct', 0.1)
                        final_price = base_price * (1 - (limit_offset + offset_pct) / 100.0)
                        return round(final_price, 2)
            
            # SMA-based entry
            elif config_type == 'sma':
                period = entry_config.get('period', 20)
                data_key = f'sma_{period}_{timeframe}'
                
                if data_key in market_data:
                    base_price = float(market_data[data_key])
                    # Apply offset percentage
                    if side == 'long':
                        # Long entry: above SMA
                        limit_offset = entry_config.get('entry_offset_pct', 0)
                        final_price = base_price * (1 + (limit_offset + offset_pct) / 100.0)
                    else:
                        # Short entry: below SMA
                        limit_offset = entry_config.get('entry_offset_pct', 0)
                        final_price = base_price * (1 - (limit_offset + offset_pct) / 100.0)
                    return round(final_price, 2)
            
            # EMA-based entry
            elif config_type == 'ema':
                period = entry_config.get('period', 20)
                data_key = f'ema_{period}_{timeframe}'
                
                if data_key in market_data:
                    base_price = float(market_data[data_key])
                    if side == 'long':
                        limit_offset = entry_config.get('entry_offset_pct', 0)
                        final_price = base_price * (1 + (limit_offset + offset_pct) / 100.0)
                    else:
                        limit_offset = entry_config.get('entry_offset_pct', 0)
                        final_price = base_price * (1 - (limit_offset + offset_pct) / 100.0)
                    return round(final_price, 2)
            
            # ATR-based entry (volatility-adjusted)
            elif config_type == 'atr':
                period = entry_config.get('period', 14)
                data_key = f'atr_{period}_{timeframe}'
                close_key = 'close'
                
                if data_key in market_data and close_key in market_data:
                    atr_value = float(market_data[data_key])
                    current_close = float(market_data[close_key])
                    atr_multiplier = entry_config.get('atr_multiplier', 1.0)
                    
                    if side == 'long':
                        # Long entry: close + (ATR * multiplier)
                        final_price = current_close + (atr_value * atr_multiplier)
                    else:
                        # Short entry: close - (ATR * multiplier)
                        final_price = current_close - (atr_value * atr_multiplier)
                    return round(final_price, 2)
        
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Error calculating entry limit price for {symbol}: {e}")
        
        return None
    
    @staticmethod
    def calculate_exit_limit_price(symbol: str, side: str, market_data: Dict,
                                  exit_config: Dict, profit_target_pct: float = 0) -> Optional[float]:
        """
        Calculate exit/sell limit price from sell criteria data.
        
        Args:
            symbol: Stock symbol
            side: 'long' or 'short'
            market_data: Current market data dict with indicators
            exit_config: Dict with sell criteria like:
                - 'type': 'candlestick_high', 'sma', 'ema', 'atr', 'fixed_percent', etc.
                - 'lookback_bars': For candlestick patterns
                - 'period': For moving averages
                - 'timeframe': Timeframe for the data
            profit_target_pct: % profit target above/below entry price
        
        Returns:
            Calculated sell limit price, or None if calculation fails
        """
        if not market_data or not exit_config:
            return None
        
        try:
            config_type = exit_config.get('type', '').lower()
            timeframe = exit_config.get('timeframe', '1min')
            
            # Candlestick resistance/support levels for exit
            if config_type.startswith('candlestick'):
                lookback = exit_config.get('lookback_bars', 5)
                
                if side == 'long':
                    # Long exit: recent high (resistance)
                    data_key = f'candlestick_high_{lookback}_{timeframe}'
                    if data_key in market_data:
                        base_price = float(market_data[data_key])
                        exit_offset = exit_config.get('exit_offset_pct', 0)
                        final_price = base_price * (1 + (exit_offset - profit_target_pct) / 100.0)
                        return round(final_price, 2)
                
                else:  # short
                    # Short exit: recent low (support)
                    data_key = f'candlestick_low_{lookback}_{timeframe}'
                    if data_key in market_data:
                        base_price = float(market_data[data_key])
                        exit_offset = exit_config.get('exit_offset_pct', 0)
                        final_price = base_price * (1 - (exit_offset + profit_target_pct) / 100.0)
                        return round(final_price, 2)
            
            # SMA-based exit
            elif config_type == 'sma':
                period = exit_config.get('period', 20)
                data_key = f'sma_{period}_{timeframe}'
                
                if data_key in market_data:
                    base_price = float(market_data[data_key])
                    exit_offset = exit_config.get('exit_offset_pct', 0)
                    
                    if side == 'long':
                        final_price = base_price * (1 + (exit_offset + profit_target_pct) / 100.0)
                    else:
                        final_price = base_price * (1 - (exit_offset + profit_target_pct) / 100.0)
                    return round(final_price, 2)
            
            # EMA-based exit
            elif config_type == 'ema':
                period = exit_config.get('period', 20)
                data_key = f'ema_{period}_{timeframe}'
                
                if data_key in market_data:
                    base_price = float(market_data[data_key])
                    exit_offset = exit_config.get('exit_offset_pct', 0)
                    
                    if side == 'long':
                        final_price = base_price * (1 + (exit_offset + profit_target_pct) / 100.0)
                    else:
                        final_price = base_price * (1 - (exit_offset + profit_target_pct) / 100.0)
                    return round(final_price, 2)
            
            # ATR-based exit (trailing)
            elif config_type == 'atr':
                period = exit_config.get('period', 14)
                data_key = f'atr_{period}_{timeframe}'
                close_key = 'close'
                
                if data_key in market_data and close_key in market_data:
                    atr_value = float(market_data[data_key])
                    current_close = float(market_data[close_key])
                    atr_multiplier = exit_config.get('atr_multiplier', 2.0)
                    
                    if side == 'long':
                        # Long exit: close + (ATR * multiplier for profit target)
                        final_price = current_close + (atr_value * atr_multiplier)
                    else:
                        # Short exit: close - (ATR * multiplier for profit target)
                        final_price = current_close - (atr_value * atr_multiplier)
                    return round(final_price, 2)
            
            # Fixed percentage profit target
            elif config_type == 'fixed_percent':
                if 'entry_price' in market_data:
                    entry_price = float(market_data['entry_price'])
                    target_pct = exit_config.get('target_percent', 2.0)
                    
                    if side == 'long':
                        final_price = entry_price * (1 + target_pct / 100.0)
                    else:
                        final_price = entry_price * (1 - target_pct / 100.0)
                    return round(final_price, 2)
        
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Error calculating exit limit price for {symbol}: {e}")
        
        return None
    
    @staticmethod
    def update_held_order_limit_prices(held_order: HeldOrder, market_data: Dict) -> bool:
        """
        Update a held order's limit price based on current market data.
        
        This is called periodically (e.g., on each new candle) to recalculate
        the limit price based on updated market data.
        
        Args:
            held_order: HeldOrder object to update
            market_data: Current market data with all indicators
        
        Returns:
            True if limit price was updated, False otherwise
        """
        if not held_order or not market_data:
            return False
        
        try:
            # Get entry conditions to calculate entry limit
            if held_order.entry_conditions:
                entry_condition = held_order.entry_conditions[0]
                if hasattr(entry_condition, 'config') and entry_condition.config:
                    new_entry_limit = HeldOrderLimitPriceCalculator.calculate_entry_limit_price(
                        held_order.symbol,
                        held_order.side,
                        market_data,
                        entry_condition.config
                    )
                    
                    if new_entry_limit and new_entry_limit != held_order.limit_price:
                        old_price = held_order.limit_price
                        held_order.limit_price = new_entry_limit
                        held_order.modified_at = utc_now_iso()
                        logger.info(
                            f"Updated {held_order.symbol} {held_order.side} limit price: "
                            f"{old_price} -> {new_entry_limit}"
                        )
                        return True
        
        except Exception as e:
            logger.error(f"Error updating limit price for order {held_order.order_id}: {e}")
        
        return False
