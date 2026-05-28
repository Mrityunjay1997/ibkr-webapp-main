"""
Unified Order Management System - Core Data Models

This module consolidates all order configuration from:
- Off-book orders (condition-based with candle/MA triggers)
- Automated orders (indicator-based entry/exit)
- Manual orders (form-based configuration)

A single UnifiedOrderConfig represents ANY order, regardless of type.
This eliminates duplication and enables feature sharing across all three modes.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import json
import uuid
from orders.unified_order_constants import OrderTIF, ORDER_STATUSES, ORDER_MODES


class OrderMode(Enum):
    """Which order system this order uses"""
    OFFBOOK = "offbook"  # Condition-based, held locally
    AUTOMATED = "automated"  # Indicator-based, multi-level
    MANUAL = "manual"  # Direct form input


class OrderSide(Enum):
    """Order direction"""
    LONG = "long"
    SHORT = "short"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"  # Created, waiting to submit
    ACTIVE = "active"  # Submitted to IBKR
    TRIGGERED = "triggered"  # Condition met (offbook only)
    EXECUTED = "executed"  # Filled
    CANCELLED = "cancelled"
    FAILED = "failed"


# =============================================================================
# ENTRY CONFIGURATION
# =============================================================================

@dataclass
class EntryConditionConfig:
    """Configuration for entry condition (when/how to enter)"""
    
    condition_type: str  # 'immediate', 'candle_breakout', 'ma_crossover', 'price_level_break'
    
    # For immediate entry
    order_type: str = 'limit'  # 'market' or 'limit'
    limit_offset_pct: float = 0.0  # Offset % if limit order
    
    # For candle breakout entry
    candle_timeframe: Optional[str] = None  # '1min', '5min', '15min', '1h', 'daily'
    candle_lookback: int = 5  # How many candles back to reference
    candle_break_direction: Optional[str] = None  # 'above_high' or 'below_low'
    candle_offset_pct: float = 0.0  # Offset % from breakout level
    
    # For MA crossover entry
    ma_type: Optional[str] = None  # 'sma' or 'ema'
    ma_period: int = 20  # Period for the MA
    ma_timeframe: Optional[str] = None  # '1min', '5min', etc
    ma_cross_direction: Optional[str] = None  # 'above' or 'below'
    ma_cross_offset_pct: float = 0.0  # Offset % from MA
    
    # For price level break
    price_level: Optional[str] = None  # Reference level (prev_close, day_high, etc)
    price_level_offset_pct: float = 0.0
    
    # For indicator-based entry (automated orders)
    indicator_type: Optional[str] = None  # 'vwap', 'sma_fast', 'ema_slow', etc
    indicator_offset_pct: float = 0.0
    
    notes: str = ""


@dataclass
class StopLossConfig:
    """Configuration for stop-loss placement"""
    
    stop_type: str  # Type of stop (see unified_order_constants.STOP_LOSS_TYPES)
    
    # Fixed price stop
    fixed_price: Optional[float] = None
    
    # Price reference stop (indicator/level based)
    price_ref_type: Optional[str] = None  # 'vwap', 'prev_close', 'candle_low', etc
    price_ref_offset_pct: float = 0.0
    
    # ATR-based stop
    atr_multiplier: float = 1.0  # e.g., 1.5 = entry - (1.5 × ATR)
    
    # Percent-based stop
    loss_percent: float = 1.0  # Max loss as % (e.g., 2% loss)
    
    # Trailing stop
    trail_amount: Optional[float] = None  # Dollar amount for trailing stop
    trail_percent: Optional[float] = None  # Percent for trailing stop
    
    # Trailing candle stop (NEW feature from off-book)
    trail_candle_timeframe: Optional[str] = None  # '1min', '5min', '15min', '1h', 'daily'
    trail_candle_offset_pct: float = 0.0  # Offset % from candle low
    
    # For shorts - high of day with offset
    high_of_day_offset_pct: float = 0.0
    
    order_type: str = 'stop'  # 'stop' or 'stop_limit'
    
    notes: str = ""


@dataclass
class TargetConfig:
    """Configuration for a single profit target"""
    
    target_type: str  # Type of target (see unified_order_constants.TARGET_TYPES)
    
    # Fixed price target
    fixed_price: Optional[float] = None
    
    # Price reference target
    price_ref_type: Optional[str] = None  # 'vwap', 'prev_close', 'candle_high', etc
    price_ref_offset_pct: float = 0.0
    
    # Fibonacci target
    fib_level: Optional[str] = None  # 'fibonacci_23_6', 'fibonacci_61_8', 'fibonacci_100_0', etc
    fib_offset_pct: float = 0.0  # Additional offset from Fib level
    
    # ATR-based target
    atr_multiplier: float = 1.0  # e.g., 2.0 = entry + (2.0 × ATR)
    
    # Percent-based target
    gain_percent: float = 5.0  # Profit target as % (e.g., 5% gain)
    
    # Risk-reward ratio target
    rr_ratio: float = 2.0  # e.g., 2.0 = 1:2 ratio (2× the risk)
    
    # Allocation and exit
    percent_of_position: float = 100.0  # % of position to exit at this target
    order_type: str = 'limit'  # 'limit' or 'market'
    
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class SessionConfig:
    """Configuration for pre-market and after-hours trading"""
    
    session_type: str  # 'regular', 'premarket', 'afterhours', 'extended', 'all_hours'
    
    # Time constraints
    use_premarket: bool = False  # Enable pre-market (4 AM - 9:30 AM)
    use_afterhours: bool = False  # Enable after-hours (4 PM - 8 PM)
    
    # Order constraints
    outsideRth: bool = False  # Set automatically based on session
    time_in_force: str = 'DAY'  # 'DAY' or 'GTC'
    
    # Bracket order handling
    split_bracket_pm_ah: bool = False  # Split bracket orders into PM and AH components
    
    notes: str = ""


@dataclass
class ShareCalculationConfig:
    """Configuration for calculating shares from amount"""
    
    calculation_method: str  # 'fixed_quantity', 'from_amount', 'from_percent_risk'
    
    # For fixed quantity
    fixed_quantity: int = 100
    
    # For from_amount
    amount_dollars: float = 1000.0  # Dollar amount to risk/trade
    
    # For from_percent_risk
    account_size: float = 100000.0  # Total account size
    risk_percent: float = 1.0  # % of account to risk per trade
    
    notes: str = ""


# =============================================================================
# UNIFIED ORDER CONFIG
# =============================================================================

@dataclass
class UnifiedOrderConfig:
    """
    Master configuration class for ANY order.
    
    This single class replaces:
    - HeldOrder + HeldOrderCondition (off-book)
    - Multi-level order levels (automated)
    - Form-based manual orders
    
    A UnifiedOrderConfig contains one entry point and can have multiple
    stop-loss and target configurations, making it flexible for all order modes.
    """
    
    # ========================================================================
    # BASIC ORDER INFO
    # ========================================================================
    
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: str = 'manual'  # 'offbook', 'automated', 'manual'
    
    symbol: str = ''
    side: str = 'long'  # 'long' or 'short'
    
    # Quantity/shares
    quantity: int = 100
    shares_config: ShareCalculationConfig = field(default_factory=ShareCalculationConfig)
    
    # ========================================================================
    # ENTRY CONFIGURATION
    # ========================================================================
    
    entry: EntryConditionConfig = field(default_factory=EntryConditionConfig)
    entry_price: Optional[float] = None  # Resolved entry price (calculated at submission)
    
    # ========================================================================
    # STOP-LOSS CONFIGURATION
    # ========================================================================
    
    stop_loss: Optional[StopLossConfig] = None
    stop_price: Optional[float] = None  # Resolved stop price (calculated at submission)
    
    # ========================================================================
    # PROFIT TARGETS
    # ========================================================================
    
    targets: List[TargetConfig] = field(default_factory=list)  # Can have multiple targets
    target_prices: List[float] = field(default_factory=list)  # Resolved target prices
    
    # ========================================================================
    # SESSION CONFIGURATION
    # ========================================================================
    
    session: SessionConfig = field(default_factory=SessionConfig)
    
    # ========================================================================
    # STATUS & METADATA
    # ========================================================================
    
    status: str = 'pending'  # 'pending', 'active', 'triggered', 'executed', 'cancelled', 'failed'
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    submitted_at: Optional[str] = None
    executed_at: Optional[str] = None
    executed_price: Optional[float] = None
    
    notes: str = ""
    
    # ========================================================================
    # PRESET/TEMPLATE REFERENCE
    # ========================================================================
    
    preset_name: Optional[str] = None  # Reference to saved preset/template
    strategy_name: Optional[str] = None  # Reference to strategy template
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire config to dictionary for serialization"""
        return {
            'order_id': self.order_id,
            'mode': self.mode,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'shares_config': asdict(self.shares_config),
            'entry': asdict(self.entry),
            'entry_price': self.entry_price,
            'stop_loss': asdict(self.stop_loss) if self.stop_loss else None,
            'stop_price': self.stop_price,
            'targets': [asdict(t) for t in self.targets],
            'target_prices': self.target_prices,
            'session': asdict(self.session),
            'status': self.status,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'submitted_at': self.submitted_at,
            'executed_at': self.executed_at,
            'executed_price': self.executed_price,
            'notes': self.notes,
            'preset_name': self.preset_name,
            'strategy_name': self.strategy_name,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedOrderConfig':
        """Create instance from dictionary"""
        return cls(
            order_id=data.get('order_id', str(uuid.uuid4())),
            mode=data.get('mode', 'manual'),
            symbol=data.get('symbol', ''),
            side=data.get('side', 'long'),
            quantity=int(data.get('quantity', 100)),
            shares_config=ShareCalculationConfig(**data.get('shares_config', {})),
            entry=EntryConditionConfig(**data.get('entry', {})),
            entry_price=data.get('entry_price'),
            stop_loss=StopLossConfig(**data.get('stop_loss', {})) if data.get('stop_loss') else None,
            stop_price=data.get('stop_price'),
            targets=[TargetConfig(**t) for t in data.get('targets', [])],
            target_prices=data.get('target_prices', []),
            session=SessionConfig(**data.get('session', {})),
            status=data.get('status', 'pending'),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            modified_at=data.get('modified_at', datetime.utcnow().isoformat()),
            submitted_at=data.get('submitted_at'),
            executed_at=data.get('executed_at'),
            executed_price=data.get('executed_price'),
            notes=data.get('notes', ''),
            preset_name=data.get('preset_name'),
            strategy_name=data.get('strategy_name'),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UnifiedOrderConfig':
        """Create instance from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def add_target(self, target: TargetConfig):
        """Add a profit target"""
        self.targets.append(target)
        self.modified_at = datetime.utcnow().isoformat()
    
    def set_stop_loss(self, stop: StopLossConfig):
        """Set stop-loss configuration"""
        self.stop_loss = stop
        self.modified_at = datetime.utcnow().isoformat()
    
    def clear_targets(self):
        """Remove all targets"""
        self.targets = []
        self.target_prices = []
        self.modified_at = datetime.utcnow().isoformat()
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate order configuration.
        
        Returns:
            (is_valid, error_message)
        """
        if not self.symbol:
            return False, "Symbol required"
        
        if not self.side in ['long', 'short']:
            return False, f"Invalid side: {self.side}"
        
        if self.quantity <= 0:
            return False, f"Quantity must be positive: {self.quantity}"
        
        if self.mode not in ['offbook', 'automated', 'manual']:
            return False, f"Invalid mode: {self.mode}"
        
        # Validate targets add up to ~100% (allow +/- 5% for rounding)
        total_allocation = sum(t.percent_of_position for t in self.targets)
        if self.targets and (total_allocation < 95 or total_allocation > 105):
            return False, f"Target allocations must sum to 100% (got {total_allocation}%)"
        
        # Validate stop loss if present
        if self.stop_loss:
            from orders.unified_order_constants import validate_stop_loss_config
            is_valid, msg = validate_stop_loss_config(self.stop_loss.stop_type, asdict(self.stop_loss))
            if not is_valid:
                return False, f"Invalid stop loss: {msg}"
        
        return True, "Valid"


# =============================================================================
# CONVENIENCE BUILDERS
# =============================================================================

def create_offbook_order(symbol: str, side: str, quantity: int, 
                         entry_condition: EntryConditionConfig,
                         stop_loss: Optional[StopLossConfig] = None) -> UnifiedOrderConfig:
    """Create an off-book order (condition-based)"""
    order = UnifiedOrderConfig(
        mode='offbook',
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry=entry_condition,
        stop_loss=stop_loss,
    )
    return order


def create_automated_order(symbol: str, side: str, 
                          entry: EntryConditionConfig,
                          targets: List[TargetConfig],
                          stop_loss: Optional[StopLossConfig] = None) -> UnifiedOrderConfig:
    """Create an automated multi-level order"""
    order = UnifiedOrderConfig(
        mode='automated',
        symbol=symbol,
        side=side,
        entry=entry,
        stop_loss=stop_loss,
        targets=targets,
    )
    return order


def create_manual_order(symbol: str, side: str, quantity: int,
                       entry_price: float,
                       profit_target: Optional[TargetConfig] = None,
                       stop_loss: Optional[StopLossConfig] = None) -> UnifiedOrderConfig:
    """Create a manual order (direct configuration)"""
    order = UnifiedOrderConfig(
        mode='manual',
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=stop_loss,
    )
    if profit_target:
        order.add_target(profit_target)
    return order
