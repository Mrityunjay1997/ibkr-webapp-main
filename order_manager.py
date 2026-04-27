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
    from indicators import FibonacciCalculator
except ImportError:
    FibonacciCalculator = None

logger = logging.getLogger("order_manager")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PriceReference:
    """Represents a price reference (entry/exit/stop point)."""
    
    type: str  # 'vwap', 'sma_fast', 'sma_medium', 'sma_slow', 'ema_fast', 'ema_slow',
               # 'fibonacci_23.6', 'fibonacci_38.2', 'fibonacci_50.0', 'fibonacci_61.8',
               # 'fibonacci_78.6', 'prev_close', 'support_1', 'resistance_1', 'custom'
    offset_pct: float  # Percentage offset (positive = up, negative = down)
    order_type: str = 'limit'  # 'limit', 'market', 'stop', 'trail'
    trailing_amount: Optional[float] = None  # For trailing stops/candles
    trailing_type: str = 'amount'  # 'amount' or 'percent'
    custom_price: Optional[float] = None  # For custom price references

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
        
        # Apply offset percentage
        offset_multiplier = 1 + (self.offset_pct / 100.0)
        final_price = indicator_value * offset_multiplier
        return round(final_price, 2)


@dataclass
class OrderLevel:
    """Represents a single level in a multi-level order."""
    
    level_num: int
    quantity: int
    entry: PriceReference
    exit: PriceReference
    stop_loss: Optional[PriceReference] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'level_num': self.level_num,
            'quantity': self.quantity,
            'entry': asdict(self.entry),
            'exit': asdict(self.exit),
            'notes': self.notes,
        }
        if self.stop_loss:
            result['stop_loss'] = asdict(self.stop_loss)
        return result


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
            entry = PriceReference(**level_data['entry'])
            exit_ref = PriceReference(**level_data['exit'])
            stop_loss = None
            if 'stop_loss' in level_data and level_data['stop_loss']:
                stop_loss = PriceReference(**level_data['stop_loss'])
            
            level = OrderLevel(
                level_num=level_data['level_num'],
                quantity=level_data['quantity'],
                entry=entry,
                exit=exit_ref,
                stop_loss=stop_loss,
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
            return price_ref.resolve_price(price_ref.custom_price)
        
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
            'prev_close': 'prev_close',
            'current_price': 'current_price',
            'day_high': 'day_high',
            'day_low': 'day_low',
            'support_1': 'day_low',  # Simple support = day low
            'resistance_1': 'day_high',  # Simple resistance = day high
        }
        
        # Fibonacci levels are calculated from swing high/low
        if ref_type.startswith('fibonacci_'):
            return self._calculate_fibonacci(ref_type)
        
        key = mapping.get(ref_type)
        return self.indicator_values.get(key) if key else None
    
    def _calculate_fibonacci(self, fib_type: str) -> Optional[float]:
        """
        Calculate Fibonacci level using FibonacciCalculator.
        
        Args:
            fib_type: Format 'fibonacci_XX.X' (e.g., 'fibonacci_38.2')
        
        Returns:
            Fibonacci level price or None
        """
        if not FibonacciCalculator:
            logger.warning("FibonacciCalculator not available")
            return None
        
        try:
            # Extract percentage from type (e.g., 0.382 from 'fibonacci_38.2')
            pct_str = fib_type.replace('fibonacci_', '').replace('.', '')
            # Convert "382" to 0.382
            if len(pct_str) == 3:
                pct = float(pct_str[0] + '.' + pct_str[1:]) / 100.0
            else:
                pct = float(pct_str.replace(',', '.')) / 100.0
            
            # Check cache first
            cache_key = f"{pct:.3f}"
            if cache_key in self._fibonacci_cache:
                return self._fibonacci_cache[cache_key]
            
            # Get swing high and low
            prev_close = self.indicator_values.get('prev_close')
            day_high = self.indicator_values.get('day_high')
            
            if prev_close is None or day_high is None:
                return None
            
            # Calculate using FibonacciCalculator
            calc = FibonacciCalculator(prev_close=prev_close, high_of_day=day_high)
            levels = calc.calculate_levels()
            
            # Find the matching level
            for key, level_data in levels.items():
                if abs(level_data['level'] - pct) < 0.001:
                    result = level_data['entry']
                    self._fibonacci_cache[cache_key] = result
                    return round(result, 2)
            
            logger.warning(f"Could not calculate Fibonacci level: {fib_type}")
            return None
        
        except (ValueError, KeyError) as e:
            logger.warning(f"Error calculating Fibonacci level {fib_type}: {e}")
            return None


# =============================================================================
# Example Usage
# =============================================================================

def create_sample_preset() -> MultiLevelOrder:
    """Create a sample multi-level order for testing."""
    
    # First level: Entry at VWAP - 2%, Target at Fibonacci 61.8% + 1%, Stop below support
    level1 = OrderLevel(
        level_num=1,
        quantity=100,
        entry=PriceReference(
            type='vwap',
            offset_pct=-2.0,
            order_type='limit'
        ),
        exit=PriceReference(
            type='fibonacci_61.8',
            offset_pct=1.0,
            order_type='limit'
        ),
        stop_loss=PriceReference(
            type='support_1',
            offset_pct=-0.5,
            order_type='stop'
        ),
        notes="Initial entry at VWAP support"
    )
    
    # Second level: Entry at Fibonacci 50% - 1%, Target trailing stop, Stop same as level 1
    level2 = OrderLevel(
        level_num=2,
        quantity=50,
        entry=PriceReference(
            type='fibonacci_50.0',
            offset_pct=-1.0,
            order_type='limit'
        ),
        exit=PriceReference(
            type='trailing_stop',
            trailing_amount=0.50,
            trailing_type='amount',
            order_type='trail'
        ),
        stop_loss=PriceReference(
            type='support_1',
            offset_pct=-0.5,
            order_type='stop'
        ),
        notes="Scaled entry at Fib pullback"
    )
    
    order = MultiLevelOrder(
        name="Fibonacci Reversal 2-Level",
        symbol="AAPL",
        levels=[level1, level2],
        strategy_notes="Two-level entry using Fibonacci pullback levels with mixed exit strategies"
    )
    
    return order


if __name__ == "__main__":
    # Test the models
    sample = create_sample_preset()
    print(json.dumps(sample.to_dict(), indent=2))
