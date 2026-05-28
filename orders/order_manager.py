"""
Multi-Level Order Management System

Handles the creation, configuration, and management of multi-level orders
with flexible entry/exit points based on technical indicators and price references.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime

# Import Fibonacci calculator from indicators
try:
    from scanner.indicators import FibonacciCalculator
except ImportError:
    FibonacciCalculator = None

logger = logging.getLogger("order_manager")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PriceReference:
    """
    Represents a price reference (entry/exit/stop point).
    
    Supported types:
    - Indicators: vwap, sma_fast, sma_medium, sma_slow, ema_fast, ema_slow, rsi, atr
    - Fibonacci: fibonacci_23.6, fibonacci_38.2, fibonacci_50.0, fibonacci_61.8, fibonacci_78.6
    - Pivot Points: pivot, support_1, support_2, resistance_1, resistance_2
    - Price Levels: prev_close, day_high, day_low, high_of_day, low_of_day
    - Price Targets: percent_target (% above/below prev_close)
    - Special: custom, trailing_stop, trailing_percent, trailing_candle
    """
    
    type: str  # Price reference type (see above)
    offset_pct: float  # Percentage offset (positive = up, negative = down)
    order_type: str = 'limit'  # 'limit', 'market', 'stop', 'stop_limit', 'bracket', 'trail', 'trail_percent', 'trail_candle'
    trailing_amount: Optional[float] = None  # For trailing stops/candles
    trailing_type: str = 'amount'  # 'amount', 'percent', or 'candles'
    custom_price: Optional[float] = None  # For custom price references
    notes: str = ""  # Optional notes for this reference

    def resolve_price(self, indicator_value: float) -> float:
        """
        Resolve the final price based on indicator value and offset.
        
        Args:
            indicator_value: The base indicator value (e.g., VWAP, SMA)
        
        Returns:
            Final price after applying offset percentage
        """
        if indicator_value is None:
            return None
        
        if self.type == 'custom':
            return round(self.custom_price, 2)
        
        if self.type == 'percent_target':
            # For percent targets, the offset_pct is the % gain above the base price
            # e.g., offset_pct=5 means 5% above prev_close
            offset_multiplier = 1 + (self.offset_pct / 100.0)
            final_price = indicator_value * offset_multiplier
            return round(final_price, 2)
        
        # For all other indicators, apply offset percentage
        # offset_pct positive = move up, negative = move down
        offset_multiplier = 1 + (self.offset_pct / 100.0)
        final_price = indicator_value * offset_multiplier
        return round(final_price, 2)


@dataclass
class SellTarget:
    """
    Represents a single profit target within an order level.
    
    Allows multiple exit points per level with allocation percentages.
    Example: Sell 50% at Fib 61.8%, 30% at 30% above prev_close, 20% on trailing stop.
    """
    
    type: str  # Price reference type (same as PriceReference)
    offset_pct: float  # Percentage offset
    order_type: str = 'limit'  # 'limit', 'market', 'stop', 'stop_limit', 'bracket', 'trail', 'trail_percent'
    percent_of_position: float = 100.0  # % of position to allocate to this target (should sum to ~100%)
    trailing_amount: Optional[float] = None  # For trailing stops
    trailing_type: str = 'amount'  # 'amount', 'percent', or 'candles'
    notes: str = ""  # Optional notes for this target
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'type': self.type,
            'offset_pct': self.offset_pct,
            'order_type': self.order_type,
            'percent_of_position': self.percent_of_position,
            'trailing_amount': self.trailing_amount,
            'trailing_type': self.trailing_type,
            'notes': self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SellTarget':
        """Create SellTarget from dictionary."""
        return cls(
            type=data['type'],
            offset_pct=data['offset_pct'],
            order_type=data.get('order_type', 'limit'),
            percent_of_position=data.get('percent_of_position', 100.0),
            trailing_amount=data.get('trailing_amount'),
            trailing_type=data.get('trailing_type', 'amount'),
            notes=data.get('notes', ''),
        )


@dataclass
class OrderLevel:
    """
    Represents a single level in a multi-level order.
    
    Supports multiple sell targets per level, allowing complex exit strategies.
    """
    
    level_num: int
    quantity: int
    entry: PriceReference
    stop_loss: Optional[PriceReference] = None
    sell_targets: List[SellTarget] = field(default_factory=list)  # Multiple exit points
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'level_num': self.level_num,
            'quantity': self.quantity,
            'entry': asdict(self.entry),
            'sell_targets': [st.to_dict() for st in self.sell_targets],
            'notes': self.notes,
        }
        if self.stop_loss:
            result['stop_loss'] = asdict(self.stop_loss)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderLevel':
        """Create OrderLevel from dictionary."""
        entry = PriceReference(**data['entry'])
        stop_loss = None
        if 'stop_loss' in data and data['stop_loss']:
            stop_loss = PriceReference(**data['stop_loss'])
        
        sell_targets = []
        for st_data in data.get('sell_targets', []):
            sell_targets.append(SellTarget.from_dict(st_data))
        
        return cls(
            level_num=data['level_num'],
            quantity=data['quantity'],
            entry=entry,
            stop_loss=stop_loss,
            sell_targets=sell_targets,
            notes=data.get('notes', '')
        )


@dataclass
class MultiLevelOrder:
    """Represents a complete multi-level order setup."""
    
    name: str
    symbol: str
    levels: List[OrderLevel]
    strategy_notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used: Optional[str] = None
    
    def total_quantity(self) -> int:
        """Calculate total quantity across all levels."""
        return sum(level.quantity for level in self.levels)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'symbol': self.symbol,
            'strategy_notes': self.strategy_notes,
            'created_at': self.created_at,
            'last_used': self.last_used,
            'levels': [level.to_dict() for level in self.levels],
            'total_quantity': self.total_quantity(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultiLevelOrder':
        """Create MultiLevelOrder from dictionary."""
        levels = []
        for level_data in data.get('levels', []):
            # Support both old format (with 'exit') and new format (with 'sell_targets')
            sell_targets = []
            if 'sell_targets' in level_data and level_data['sell_targets']:
                for st_data in level_data['sell_targets']:
                    sell_targets.append(SellTarget.from_dict(st_data))
            elif 'exit' in level_data and level_data['exit']:
                # Convert old 'exit' to new 'sell_targets' format for backwards compatibility
                exit_ref = level_data['exit']
                sell_targets.append(SellTarget(
                    type=exit_ref['type'],
                    offset_pct=exit_ref['offset_pct'],
                    order_type=exit_ref.get('order_type', 'limit'),
                    percent_of_position=100.0,
                    trailing_amount=exit_ref.get('trailing_amount'),
                    trailing_type=exit_ref.get('trailing_type', 'amount'),
                ))
            
            entry = PriceReference(**level_data['entry'])
            stop_loss = None
            if 'stop_loss' in level_data and level_data['stop_loss']:
                stop_loss = PriceReference(**level_data['stop_loss'])
            
            level = OrderLevel(
                level_num=level_data['level_num'],
                quantity=level_data['quantity'],
                entry=entry,
                stop_loss=stop_loss,
                sell_targets=sell_targets,
                notes=level_data.get('notes', '')
            )
            levels.append(level)
        
        return cls(
            name=data['name'],
            symbol=data['symbol'],
            levels=levels,
            strategy_notes=data.get('strategy_notes', ''),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            last_used=data.get('last_used'),
        )


# =============================================================================
# Order Manager
# =============================================================================

class OrderPresetManager:
    """Manages saving and loading of multi-level order presets."""
    
    def __init__(self, presets_dir: Path = Path("order_presets")):
        """
        Initialize the preset manager.
        
        Args:
            presets_dir: Directory where presets are stored
        """
        self.presets_dir = Path(presets_dir)
        self.presets_dir.mkdir(exist_ok=True)
    
    def save_preset(self, order: MultiLevelOrder) -> Path:
        """
        Save a multi-level order preset to disk.
        
        Args:
            order: MultiLevelOrder instance to save
        
        Returns:
            Path to saved file
        """
        # Create filename from name, sanitizing it
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' 
                           for c in order.name)
        filename = f"{safe_name}_{order.symbol}_{int(datetime.utcnow().timestamp())}.json"
        filepath = self.presets_dir / filename
        
        data = order.to_dict()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved preset: {filepath}")
        return filepath
    
    def load_preset(self, filepath: Path) -> MultiLevelOrder:
        """
        Load a multi-level order preset from disk.
        
        Args:
            filepath: Path to preset file
        
        Returns:
            MultiLevelOrder instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        order = MultiLevelOrder.from_dict(data)
        order.last_used = datetime.utcnow().isoformat()
        
        logger.info(f"Loaded preset: {filepath}")
        return order
    
    def list_presets(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available presets, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            List of preset metadata dictionaries
        """
        presets = []
        
        for filepath in sorted(self.presets_dir.glob("*.json")):
            try:
                order = self.load_preset(filepath)
                
                if symbol and order.symbol != symbol:
                    continue
                
                presets.append({
                    'name': order.name,
                    'symbol': order.symbol,
                    'filename': filepath.name,
                    'num_levels': len(order.levels),
                    'total_qty': order.total_quantity(),
                    'created_at': order.created_at,
                    'last_used': order.last_used,
                    'strategy_notes': order.strategy_notes,
                })
            except Exception as e:
                logger.error(f"Error loading preset {filepath}: {e}")
        
        return presets
    
    def delete_preset(self, filename: str) -> bool:
        """
        Delete a preset file.
        
        Args:
            filename: Name of the preset file
        
        Returns:
            True if successful, False otherwise
        """
        filepath = self.presets_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Preset not found: {filepath}")
            return False
        
        filepath.unlink()
        logger.info(f"Deleted preset: {filepath}")
        return True


# =============================================================================
# Price Reference Resolver
# =============================================================================

class PriceReferenceResolver:
    """
    Resolves price references using calculated indicator values.
    
    This class bridges the gap between price reference specifications
    (e.g., "VWAP - 2%") and actual prices based on market data.
    """
    
    def __init__(self, indicator_values: Dict[str, float]):
        """
        Initialize with indicator values.
        
        Args:
            indicator_values: Dictionary of indicator values
                {
                    'vwap': 123.45,
                    'sma_fast': 122.10,
                    'sma_medium': 121.50,
                    'sma_slow': 120.00,
                    'ema_fast': 122.50,
                    'ema_slow': 121.00,
                    'prev_close': 122.75,
                    'current_price': 123.00,
                    'day_high': 124.00,
                    'day_low': 121.00,
                    'atr': 1.50,
                }
        """
        self.indicator_values = indicator_values
        self._fibonacci_cache = {}
    
    def resolve(self, price_ref: PriceReference) -> Optional[float]:
        """
        Resolve a price reference to an actual price.
        
        Args:
            price_ref: PriceReference specification
        
        Returns:
            Resolved price or None if resolution fails
        """
        if price_ref.type == 'custom':
            return round(price_ref.custom_price, 2) if price_ref.custom_price else None
        
        if price_ref.type == 'percent_target':
            # For percent targets, directly apply offset to prev_close
            base_value = self.indicator_values.get('prev_close')
            if base_value is None:
                logger.warning("Could not resolve percent_target: prev_close not available")
                return None
            return price_ref.resolve_price(base_value)
        
        # Get the base indicator value
        base_value = self._get_indicator_value(price_ref.type)
        
        if base_value is None:
            logger.warning(f"Could not resolve price reference: {price_ref.type}")
            return None
        
        return price_ref.resolve_price(base_value)
    
    def _get_indicator_value(self, ref_type: str) -> Optional[float]:
        """
        Get the indicator value for a given reference type.
        
        Args:
            ref_type: Reference type identifier
        
        Returns:
            Indicator value or None
        """
        # Direct indicator mappings
        mapping = {
            'vwap': 'vwap',
            'sma_fast': 'sma_fast',
            'sma_medium': 'sma_medium',
            'sma_slow': 'sma_slow',
            'ema_fast': 'ema_fast',
            'ema_slow': 'ema_slow',
            'rsi': 'rsi',
            'atr': 'atr',
            'prev_close': 'prev_close',
            'current_price': 'current_price',
            'day_high': 'day_high',
            'high_of_day': 'day_high',
            'day_low': 'day_low',
            'low_of_day': 'day_low',
            'gap_close': 'prev_close',  # Gap close = previous close
        }
        
        # Support/Resistance (based on simple day high/low)
        if ref_type == 'support_1':
            return self.indicator_values.get('day_low')
        elif ref_type == 'support_2':
            # Support 2 = lower of support 1 and previous day's low
            return self.indicator_values.get('day_low')
        elif ref_type == 'resistance_1':
            return self.indicator_values.get('day_high')
        elif ref_type == 'resistance_2':
            # Resistance 2 = higher of resistance 1 and previous day's high
            return self.indicator_values.get('day_high')
        elif ref_type == 'pivot':
            # Pivot = (High + Low + Close) / 3
            high = self.indicator_values.get('day_high')
            low = self.indicator_values.get('day_low')
            close = self.indicator_values.get('prev_close')
            if all([high, low, close]):
                return round((high + low + close) / 3, 2)
            return None
        
        # Fibonacci levels are calculated from swing high/low
        if ref_type.startswith('fibonacci_'):
            return self._calculate_fibonacci(ref_type)
        
        key = mapping.get(ref_type)
        return self.indicator_values.get(key) if key else None
    
    def _calculate_fibonacci(self, fib_type: str) -> Optional[float]:
        """
        Calculate Fibonacci level using FibonacciCalculator.
        
        Args:
            fib_type: Format 'fibonacci_XX.X' (e.g., 'fibonacci_38.2' or 'fibonacci_61.8')
        
        Returns:
            Fibonacci level price or None
        """
        if not FibonacciCalculator:
            logger.warning("FibonacciCalculator not available for Fibonacci calculations")
            return None
        
        try:
            # Extract percentage from type (e.g., 38.2 from 'fibonacci_38.2')
            pct_str = fib_type.replace('fibonacci_', '')
            pct = float(pct_str)  # This will be 23.6, 38.2, 50.0, 61.8, or 78.6
            
            # Check cache first
            cache_key = f"{pct:.3f}"
            if cache_key in self._fibonacci_cache:
                return self._fibonacci_cache[cache_key]
            
            # Get swing high and low from previous day's data
            prev_close = self.indicator_values.get('prev_close', 0)
            day_high = self.indicator_values.get('day_high', 0)
            day_low = self.indicator_values.get('day_low', prev_close)
            
            if prev_close is None or day_high is None:
                logger.warning(f"Cannot calculate Fibonacci: missing prev_close or day_high")
                return None
            
            # Calculate Fibonacci levels using standard formula
            # For uptrend: Low + (High - Low) * percentage
            # For downtrend: High - (High - Low) * percentage
            swing_range = day_high - day_low
            if swing_range <= 0:
                swing_range = day_high - prev_close if day_high > prev_close else prev_close - day_low
            
            if swing_range <= 0:
                logger.warning("Cannot calculate Fibonacci: no price swing data")
                return None
            
            # Calculate level at percentage
            pct_decimal = pct / 100.0
            fib_level = day_low + (swing_range * pct_decimal)
            
            result = round(fib_level, 2)
            self._fibonacci_cache[cache_key] = result
            
            logger.debug(f"Calculated Fibonacci {pct}% level: {result} (range: {day_low}-{day_high})")
            return result
        
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Error calculating Fibonacci level {fib_type}: {e}")
            return None


# =============================================================================
# Example Usage
# =============================================================================

def create_sample_preset() -> MultiLevelOrder:
    """Create a sample multi-level order for testing."""
    
    # First level: Entry at VWAP - 2%, Multiple sell targets
    level1 = OrderLevel(
        level_num=1,
        quantity=100,
        entry=PriceReference(
            type='vwap',
            offset_pct=-2.0,
            order_type='limit',
            notes="Entry at VWAP support"
        ),
        stop_loss=PriceReference(
            type='pivot',
            offset_pct=-0.5,
            order_type='stop',
            notes="Stop below pivot"
        ),
        sell_targets=[
            SellTarget(
                type='fibonacci_61.8',
                offset_pct=1.0,
                order_type='limit',
                percent_of_position=50.0,
                notes="Sell 50% at Fib 61.8% + 1%"
            ),
            SellTarget(
                type='percent_target',
                offset_pct=30.0,
                order_type='limit',
                percent_of_position=30.0,
                notes="Sell 30% at 30% above previous close"
            ),
            SellTarget(
                type='resistance_1',
                offset_pct=0.0,
                order_type='limit',
                percent_of_position=20.0,
                notes="Sell remaining 20% at resistance"
            ),
        ],
        notes="Initial entry with three profit targets"
    )
    
    # Second level: Entry at Fibonacci 50% - 1%, Different exit strategy
    level2 = OrderLevel(
        level_num=2,
        quantity=50,
        entry=PriceReference(
            type='fibonacci_50.0',
            offset_pct=-1.0,
            order_type='limit',
            notes="Scaled entry at Fib pullback"
        ),
        stop_loss=PriceReference(
            type='pivot',
            offset_pct=-0.5,
            order_type='stop'
        ),
        sell_targets=[
            SellTarget(
                type='day_high',
                offset_pct=0.0,
                order_type='limit',
                percent_of_position=50.0,
                notes="Sell 50% at High of Day"
            ),
            SellTarget(
                type='trailing_percent',
                offset_pct=0.0,
                order_type='trail',
                percent_of_position=50.0,
                trailing_amount=5.0,
                trailing_type='percent',
                notes="Sell 50% on 5% trailing stop"
            ),
        ],
        notes="Scaled entry with mixed exit types"
    )
    
    order = MultiLevelOrder(
        name="Advanced Multi-Target Strategy",
        symbol="AAPL",
        levels=[level1, level2],
        strategy_notes="Two-level entry using Fibonacci with multiple profit targets per level"
    )
    
    return order


if __name__ == "__main__":
    # Test the models
    sample = create_sample_preset()
    print(json.dumps(sample.to_dict(), indent=2))
