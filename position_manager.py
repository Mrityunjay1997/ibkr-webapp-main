"""
Position Manager - Dynamic Position Tracking and Exit Logic

This module handles:
1. Tracking filled positions (entries, quantities, entry prices, entry times)
2. Monitoring for exit conditions based on multiple factors
3. Dynamic stop/target calculation
4. Partial position exits
5. Exit events (full or partial exits)

Architecture:
- Position: Single filled trade (entry_price, quantity, entry_time, etc.)
- ExitCondition: Evaluator for when to exit (profit target, news age, time of day, etc.)
- PositionManager: Manages all open positions and evaluates exit conditions
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


# ============================================================================
# Profit Taking System - Dynamic Target Calculation & Stop Escalation
# ============================================================================

@dataclass
class ProfitTarget:
    """Single profit target with exit percentage and stop level"""
    target_price: float
    exit_percent: float  # What % of remaining position to exit (0-100)
    stop_floor: float  # Minimum stop (profit protection floor)
    description: str = ""  # e.g., "50% of daily move", "Fib .618", etc
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ProfitTakingConfig:
    """Configuration for dynamic profit taking"""
    # Entry conditions
    prev_close: float  # Previous day's close
    high_of_day: float  # Today's high (or swing high)
    current_price: float  # Current price
    
    # Market data for calculation
    fib_levels: Dict[str, float] = field(default_factory=dict)  # Fib retracement/extension prices
    support_levels: List[float] = field(default_factory=list)  # Recent support levels
    resistance_levels: List[float] = field(default_factory=list)  # Recent resistance levels
    gaps: List[Dict] = field(default_factory=list)  # [{'direction': 'up'/'down', 'level': 152.5}, ...]
    
    # Strategy settings
    daily_move_extension: float = 1.618  # How far to extend daily move (1.0 = at high, 1.618 = Fibonacci extension)
    aggressive_mode: bool = False  # True: more targets closer together, False: conservative spacing
    
    def to_dict(self):
        return asdict(self)


class DynamicProfitTargetCalculator:
    """
    Calculates dynamic profit targets considering:
    - Daily % move (entry point relative to swing)
    - Fibonacci extensions and retracements
    - Support/resistance levels
    - Previous gaps
    - Historical volatility patterns
    
    Returns multiple targets for scaling out of position
    """
    
    def __init__(self, config: ProfitTakingConfig):
        self.cfg = config
        self.daily_move = self.cfg.high_of_day - self.cfg.prev_close
        self.daily_move_percent = (self.daily_move / self.cfg.prev_close) * 100 if self.cfg.prev_close > 0 else 0
    
    def calculate_targets(self) -> List[ProfitTarget]:
        """
        Calculate profit targets and their associated stop levels.
        
        Returns list of ProfitTarget objects ordered by price (lowest to highest)
        """
        targets = []
        entry_price = self.cfg.prev_close  # Use previous close as entry reference
        
        # Target 1: Early partial exit (50% of daily move progress)
        # Exit 30% of position, lock in small profit
        target1_price = entry_price + (self.daily_move * 0.50)
        target1_stop = entry_price + (self.daily_move * 0.10)  # Stop at 10% of daily move
        targets.append(ProfitTarget(
            target_price=target1_price,
            exit_percent=30,
            stop_floor=target1_stop,
            description=f"50% daily move ({self.daily_move_percent:.2f}% move) - Exit 30%, stop to +{((target1_stop-entry_price)/entry_price)*100:.2f}%"
        ))
        
        # Target 2: Mid-point (75% of daily move progress)  
        # Exit another 30-40%, now 2/3 position sold
        target2_price = entry_price + (self.daily_move * 0.75)
        target2_stop = (entry_price + target2_price) / 2  # Stop at midpoint between entry and target
        targets.append(ProfitTarget(
            target_price=target2_price,
            exit_percent=35,
            stop_floor=target2_stop,
            description=f"75% daily move - Exit 35%, stop to +{((target2_stop-entry_price)/entry_price)*100:.2f}%"
        ))
        
        # Target 3: Full daily move (100% of daily move)
        # Exit another 20%, leaving 15% for runners
        target3_price = entry_price + self.daily_move
        target3_stop = entry_price + (self.daily_move * 0.50)  # Stop at 50% of daily move
        targets.append(ProfitTarget(
            target_price=target3_price,
            exit_percent=20,
            stop_floor=target3_stop,
            description=f"Full daily move ({self.daily_move_percent:.2f}%) - Exit 20%, hold rest for extension"
        ))
        
        # Target 4: Fibonacci extension (1.618 of daily move) - if applicable
        # This extends the move further, hold remaining 15% long-term
        target4_price = entry_price + (self.daily_move * self.cfg.daily_move_extension)
        target4_stop = entry_price + (self.daily_move * 0.618)  # Stop at golden ratio
        targets.append(ProfitTarget(
            target_price=target4_price,
            exit_percent=15,  # Exit final portion or hold for home run
            stop_floor=target4_stop,
            description=f"Fib extension ({self.cfg.daily_move_extension}x daily move) - Exit 15% or hold, stop to +{((target4_stop-entry_price)/entry_price)*100:.2f}%"
        ))
        
        # Target 5: Resistance or gap-based target (if available)
        resistance = self._get_next_resistance(entry_price, target4_price)
        if resistance and resistance > target4_price:
            target5_stop = target4_price + (self.daily_move * 0.236)  # Stop at Fib .236 above T4
            targets.append(ProfitTarget(
                target_price=resistance,
                exit_percent=10,  # Home run exit
                stop_floor=target5_stop,
                description=f"Resistance level at ${resistance:.2f} - Last home run exit"
            ))
        
        return targets
    
    def _get_next_resistance(self, entry: float, current: float) -> Optional[float]:
        """Find nearest resistance level above current price"""
        resistances = [r for r in self.cfg.resistance_levels if r > current]
        if resistances:
            return min(resistances)  # Nearest resistance above current
        
        # Check gaps
        gaps_above = [g['level'] for g in self.cfg.gaps if g.get('direction') == 'up' and g['level'] > current]
        if gaps_above:
            return min(gaps_above)
        
        # Check Fibonacci levels
        fib_above = [p for p in self.cfg.fib_levels.values() if isinstance(p, (int, float)) and p > current]
        if fib_above:
            return min(fib_above)
        
        return None
    
    def calculate_stop_escalation(self, current_price: float, entry_price: float, 
                                  targets: List[ProfitTarget]) -> float:
        """
        Calculate current stop price based on progress toward targets.
        
        Logic:
        - Find which target is most relevant
        - Set stop to that target's stop_floor, or track higher lows
        - If approaching target, escalate stop to protect profit
        
        Args:
            current_price: Current stock price
            entry_price: Entry price
            targets: List of profit targets
        
        Returns:
            Recommended stop price
        """
        if current_price <= entry_price:
            return entry_price - (abs(self.daily_move) * 0.50)  # Stop below entry if losing
        
        # Find which target we're closest to
        remaining_targets = [t for t in targets if current_price < t.target_price]
        
        if not remaining_targets:
            # Past all targets, hold the last target's stop
            return targets[-1].stop_floor
        
        next_target = remaining_targets[0]
        distance_to_target = next_target.target_price - current_price
        total_distance = next_target.target_price - entry_price
        
        if total_distance == 0:
            return entry_price
        
        progress = (current_price - entry_price) / total_distance
        
        # Escalate stop based on progress
        if progress >= 0.75:
            # 75% of the way: move stop to 70% of the move
            return entry_price + (self.daily_move * 0.70)
        elif progress >= 0.50:
            # 50% of the way: move stop to 25% of the move
            return entry_price + (self.daily_move * 0.25)
        elif progress >= 0.25:
            # 25% of the way: move stop to breakeven + small buffer
            return entry_price + (self.daily_move * 0.05)
        else:
            # Early: strict stop
            return entry_price - (self.daily_move * 0.25)
    
    def should_exit_percent_now(self, current_price: float, entry_price: float) -> Optional[Dict]:
        """
        Determine if should exit a percentage of position based on price progress.
        
        Returns:
            Dict with exit_target, exit_percent, reasoning
            None if no action needed
        """
        # Check each target in order
        for target in self.calculate_targets():
            if current_price >= target.target_price:
                return {
                    'target_price': target.target_price,
                    'exit_percent': target.exit_percent,
                    'stop_floor': target.stop_floor,
                    'reasoning': target.description
                }
        
        return None


class ExitTrigger(Enum):
    """Reasons for exiting a position"""
    PROFIT_TARGET = "profit_target"
    FIBONACCI_LEVEL = "fibonacci_level"
    TIME_BASED = "time_based"
    NEWS_AGE = "news_age"
    INFLECTION_POINT = "inflection_point"
    TAPE_PATTERN = "tape_pattern"
    TRAILING_STOP = "trailing_stop"
    MANUAL = "manual"


@dataclass
class Position:
    """Represents a filled trade position"""
    symbol: str
    entry_price: float
    quantity: int
    entry_time: datetime
    order_id: int
    side: str = "long"  # "long" or "short"
    
    # Dynamic tracking
    current_price: float = 0.0
    high_price: float = 0.0  # Highest price since entry (for long)
    low_price: float = 0.0   # Lowest price since entry (for long)
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Exit planning
    target_prices: Dict[str, float] = field(default_factory=dict)  # {"38.2%": 109.27, "61.8%": 110.15}
    stop_loss_price: float = 0.0
    trailing_stop_price: float = 0.0
    
    # Partial exits
    quantity_remaining: int = 0
    partial_exits: List[Dict] = field(default_factory=list)  # [{qty: 10, price: 110, time: ..., trigger: ...}]
    
    def __post_init__(self):
        if self.quantity_remaining == 0:
            self.quantity_remaining = self.quantity
        if self.low_price == 0:
            self.low_price = self.entry_price
        if self.high_price == 0:
            self.high_price = self.entry_price
    
    def to_dict(self):
        """Convert to JSON-serializable dict"""
        d = asdict(self)
        d['entry_time'] = self.entry_time.isoformat()
        d['last_updated'] = self.last_updated.isoformat()
        for exit_info in d.get('partial_exits', []):
            if 'time' in exit_info and isinstance(exit_info['time'], datetime):
                exit_info['time'] = exit_info['time'].isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data):
        """Create Position from dict"""
        data = data.copy()
        if isinstance(data['entry_time'], str):
            data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        
        for exit_info in data.get('partial_exits', []):
            if isinstance(exit_info.get('time'), str):
                exit_info['time'] = datetime.fromisoformat(exit_info['time'])
        
        return cls(**data)
    
    def get_unrealized_pnl(self) -> Tuple[float, float]:
        """Return (pnl_amount, pnl_percent)"""
        if self.current_price == 0:
            return 0.0, 0.0
        
        pnl_amount = (self.current_price - self.entry_price) * self.quantity_remaining
        pnl_percent = ((self.current_price - self.entry_price) / self.entry_price) * 100
        return pnl_amount, pnl_percent
    
    def get_age_seconds(self) -> int:
        """Seconds since entry"""
        return int((datetime.now() - self.entry_time).total_seconds())
    
    def get_age_readable(self) -> str:
        """Human readable age"""
        age = self.get_age_seconds()
        if age < 60:
            return f"{age}s"
        elif age < 3600:
            return f"{age//60}m"
        elif age < 86400:
            return f"{age//3600}h"
        else:
            return f"{age//86400}d"


class ExitConditionEvaluator:
    """Base class for exit condition evaluators"""
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        """
        Evaluate if position should exit.
        
        Args:
            position: The Position to evaluate
            market_data: Dict with keys like:
                - current_price: float
                - fib_levels: dict of Fibonacci levels
                - news_headlines: list of recent news
                - time_of_day: str (e.g., "14:30")
                - tape_pattern: str (detection result)
                
        Returns:
            Dict with exit details if condition met, None otherwise
            {
                'trigger': ExitTrigger,
                'reason': str,
                'target_price': float,
                'exit_percent': float (0-100, % of position to exit)
            }
        """
        raise NotImplementedError


class ProfitTargetEvaluator(ExitConditionEvaluator):
    """Exit when profit target reached"""
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        if position.current_price == 0:
            return None
        
        # Check each target price
        for target_label, target_price in position.target_prices.items():
            if position.side == "long" and position.current_price >= target_price:
                return {
                    'trigger': ExitTrigger.PROFIT_TARGET.value,
                    'reason': f"Reached {target_label} target: ${target_price:.3f}",
                    'target_price': target_price,
                    'exit_percent': 50,  # Exit 50% at first target
                }
        
        return None


class FibonacciLevelEvaluator(ExitConditionEvaluator):
    """Exit at specific Fibonacci levels"""
    
    def __init__(self, target_levels: List[float] = None):
        self.target_levels = target_levels or [0.382, 0.618, 0.786]
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        if 'fib_levels' not in market_data or not market_data['fib_levels']:
            return None
        
        fib_data = market_data['fib_levels']
        
        for level in self.target_levels:
            level_key = f'{level:.3f}'
            if level_key in fib_data:
                fib_info = fib_data[level_key]
                target = fib_info.get('entry')
                
                if target and position.side == "long" and position.current_price >= target:
                    return {
                        'trigger': ExitTrigger.FIBONACCI_LEVEL.value,
                        'reason': f"Fibonacci {level*100:.1f}% level reached: ${target:.3f}",
                        'target_price': target,
                        'exit_percent': 30,  # Partial exit
                    }
        
        return None


class TimeBasedEvaluator(ExitConditionEvaluator):
    """Exit if position held for specified duration"""
    
    def __init__(self, max_hold_seconds: int = 3600):
        self.max_hold_seconds = max_hold_seconds
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        age = position.get_age_seconds()
        
        if age >= self.max_hold_seconds:
            # Exit if held long enough AND at least breaking even
            pnl_amount, pnl_percent = position.get_unrealized_pnl()
            
            if pnl_percent >= 0:  # Only exit if profitable or break-even
                return {
                    'trigger': ExitTrigger.TIME_BASED.value,
                    'reason': f"Max hold time ({position.get_age_readable()}) reached with +{pnl_percent:.1f}% gain",
                    'target_price': position.current_price,
                    'exit_percent': 100,  # Full exit
                }
        
        return None


class NewsAgeEvaluator(ExitConditionEvaluator):
    """Exit when news older than threshold and profit taken"""
    
    def __init__(self, max_news_age_seconds: int = 600):  # 10 minutes
        self.max_news_age_seconds = max_news_age_seconds
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        headlines = market_data.get('news_headlines', [])
        if not headlines:
            return None
        
        # Find most recent headline time
        latest_news_time = None
        for hl in headlines:
            if 'parsedTime' in hl:
                latest_news_time = datetime.fromisoformat(hl['parsedTime'])
                break
        
        if not latest_news_time:
            return None
        
        news_age = (datetime.now() - latest_news_time).total_seconds()
        
        # Exit if news is old AND position is profitable
        if news_age > self.max_news_age_seconds:
            pnl_amount, pnl_percent = position.get_unrealized_pnl()
            
            if pnl_percent >= 1.0:  # At least 1% profit
                return {
                    'trigger': ExitTrigger.NEWS_AGE.value,
                    'reason': f"News is {int(news_age/60)}min old, taking profit ({pnl_percent:.2f}%)",
                    'target_price': position.current_price,
                    'exit_percent': 50,  # Partial exit
                }
        
        return None


class InflectionPointEvaluator(ExitConditionEvaluator):
    """Exit when price fails at inflection point or key resistance"""
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        if 'inflection_points' not in market_data:
            return None
        
        inflection = market_data['inflection_points']
        if not inflection:
            return None
        
        current = position.current_price
        
        # If price bounced off key level
        if inflection.get('type') == 'rejection' and position.side == "long":
            # Price tested level and moved down
            test_level = inflection.get('level', 0)
            if test_level and current < test_level * 0.99:  # Back below by 1%
                pnl_amount, pnl_percent = position.get_unrealized_pnl()
                if pnl_percent > 0:
                    return {
                        'trigger': ExitTrigger.INFLECTION_POINT.value,
                        'reason': f"Price rejected at ${test_level:.3f}, closing half position",
                        'target_price': current,
                        'exit_percent': 50,
                    }
        
        return None


class TrailingStopEvaluator(ExitConditionEvaluator):
    """Exit if price drops below trailing stop"""
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        if position.trailing_stop_price <= 0:
            return None
        
        if position.side == "long" and position.current_price <= position.trailing_stop_price:
            return {
                'trigger': ExitTrigger.TRAILING_STOP.value,
                'reason': f"Trailing stop hit at ${position.trailing_stop_price:.3f}",
                'target_price': position.trailing_stop_price,
                'exit_percent': 100,
            }
        
        return None


class DynamicProfitTargetEvaluator(ExitConditionEvaluator):
    """
    Intelligently scale out of profitable positions using dynamic targets.
    
    Calculates targets based on:
    - Daily move percentage
    - Fibonacci extensions (1.618x)
    - Support/resistance levels
    - Previous gaps
    - Progress through move
    
    Escalates stops to protect profit as position moves in profit direction.
    """
    
    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive  # More/fewer targets closer together
    
    def evaluate(self, position: Position, market_data: Dict) -> Optional[Dict]:
        # Need minimum market data to calculate targets
        if 'prev_close' not in market_data or 'high_of_day' not in market_data:
            return None
        
        entry_price = position.entry_price
        current_price = position.current_price
        
        # Create profit taking config
        config = ProfitTakingConfig(
            prev_close=market_data['prev_close'],
            high_of_day=market_data['high_of_day'],
            current_price=current_price,
            fib_levels=market_data.get('fib_levels', {}),
            support_levels=market_data.get('support_levels', []),
            resistance_levels=market_data.get('resistance_levels', []),
            gaps=market_data.get('gaps', []),
            daily_move_extension=1.618 if not self.aggressive else 1.0,
            aggressive_mode=self.aggressive
        )
        
        calculator = DynamicProfitTargetCalculator(config)
        targets = calculator.calculate_targets()
        
        # Check if we've hit a target
        exit_action = calculator.should_exit_percent_now(current_price, entry_price)
        
        if exit_action:
            return {
                'trigger': ExitTrigger.PROFIT_TARGET.value,
                'reason': exit_action['reasoning'],
                'target_price': exit_action['target_price'],
                'exit_percent': exit_action['exit_percent'],
                'new_stop': exit_action['stop_floor'],
            }
        
        # Even if no target hit, check if should escalate stop
        # This is called as side-effect to update position's trailing stop
        new_stop = calculator.calculate_stop_escalation(current_price, entry_price, targets)
        
        if new_stop > position.stop_loss_price:
            # Update the stop on position (evaluator can't directly modify, 
            # but PositionManager will handle this in evaluate_exits)
            # Return as info-only recommendation
            pass
        
        return None


class PositionManager:
    """Manages all open positions and exit conditions"""
    
    def __init__(self, storage_file: str = "positions.json"):
        self.positions: Dict[str, List[Position]] = {}  # symbol -> [Position, ...]
        self.storage_file = storage_file
        self.evaluators: List[ExitConditionEvaluator] = [
            DynamicProfitTargetEvaluator(aggressive=False),  # Main intelligent scaler
            ProfitTargetEvaluator(),
            FibonacciLevelEvaluator([0.382, 0.618, 0.786]),
            TimeBasedEvaluator(max_hold_seconds=3600),  # 1 hour max
            NewsAgeEvaluator(max_news_age_seconds=600),  # 10 minutes
            InflectionPointEvaluator(),
            TrailingStopEvaluator(),
        ]
        self.exit_log: List[Dict] = []  # Track all exits
        
        self.load_positions()
    
    def add_position(self, position: Position) -> None:
        """Track a newly filled position"""
        if position.symbol not in self.positions:
            self.positions[position.symbol] = []
        
        self.positions[position.symbol].append(position)
        logger.info(f"Position added: {position.symbol} {position.quantity} @ ${position.entry_price:.3f}")
        self.save_positions()
    
    def update_position_prices(self, symbol: str, current_price: float) -> None:
        """Update market prices for all positions in a symbol"""
        if symbol not in self.positions:
            return
        
        for pos in self.positions[symbol]:
            pos.current_price = current_price
            pos.last_updated = datetime.now()
            
            # Update high/low
            if current_price > pos.high_price:
                pos.high_price = current_price
            if current_price < pos.low_price:
                pos.low_price = current_price
    
    def evaluate_exits(self, symbol: str, market_data: Dict) -> List[Dict]:
        """
        Evaluate all exit conditions for a symbol's positions.
        
        Also handles stop escalation from dynamic profit targets.
        
        Returns list of exit recommendations
        """
        if symbol not in self.positions:
            return []
        
        exit_recommendations = []
        
        for position in self.positions[symbol]:
            # Apply dynamic stop escalation first (from DynamicProfitTargetEvaluator)
            if 'prev_close' in market_data and 'high_of_day' in market_data:
                try:
                    config = ProfitTakingConfig(
                        prev_close=market_data['prev_close'],
                        high_of_day=market_data['high_of_day'],
                        current_price=position.current_price,
                        fib_levels=market_data.get('fib_levels', {}),
                        support_levels=market_data.get('support_levels', []),
                        resistance_levels=market_data.get('resistance_levels', []),
                        gaps=market_data.get('gaps', []),
                    )
                    calc = DynamicProfitTargetCalculator(config)
                    targets = calc.calculate_targets()
                    new_stop = calc.calculate_stop_escalation(
                        position.current_price,
                        position.entry_price,
                        targets
                    )
                    
                    # Update position's trailing stop if new stop is higher
                    if new_stop > position.trailing_stop_price:
                        position.trailing_stop_price = new_stop
                except Exception as e:
                    logger.warning(f"Failed to calculate stop escalation: {e}")
            
            # Evaluate all conditions
            for evaluator in self.evaluators:
                recommendation = evaluator.evaluate(position, market_data)
                if recommendation:
                    recommendation['position_id'] = position.order_id
                    recommendation['symbol'] = symbol
                    recommendation['current_price'] = position.current_price
                    recommendation['unrealized_pnl'] = position.get_unrealized_pnl()[1]
                    exit_recommendations.append(recommendation)
        
        return exit_recommendations
    
    def execute_partial_exit(self, symbol: str, order_id: int, quantity: int, 
                            exit_price: float, trigger: str) -> bool:
        """
        Execute partial position exit.
        
        Args:
            symbol: Stock symbol
            order_id: Position's order ID
            quantity: Number of shares to exit
            exit_price: Price at which exiting
            trigger: Reason for exit
        
        Returns: True if successful, False otherwise
        """
        if symbol not in self.positions:
            return False
        
        for position in self.positions[symbol]:
            if position.order_id == order_id:
                if quantity > position.quantity_remaining:
                    logger.warning(f"Cannot exit {quantity} shares, only {position.quantity_remaining} remaining")
                    return False
                
                position.quantity_remaining -= quantity
                exit_info = {
                    'quantity': quantity,
                    'price': exit_price,
                    'time': datetime.now(),
                    'trigger': trigger,
                    'pnl': (exit_price - position.entry_price) * quantity
                }
                position.partial_exits.append(exit_info)
                
                logger.info(f"Partial exit: {symbol} {quantity}@${exit_price:.3f} | Trigger: {trigger}")
                
                # Log to exit log
                self.exit_log.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'entry_price': position.entry_price,
                    'exit_price': exit_price,
                    'trigger': trigger,
                    'timestamp': datetime.now().isoformat(),
                    'pnl': exit_info['pnl']
                })
                
                self.save_positions()
                return True
        
        return False
    
    def execute_full_exit(self, symbol: str, order_id: int, exit_price: float, 
                         trigger: str) -> bool:
        """Close entire position"""
        if symbol not in self.positions:
            return False
        
        for i, position in enumerate(self.positions[symbol]):
            if position.order_id == order_id:
                quantity = position.quantity_remaining
                success = self.execute_partial_exit(symbol, order_id, quantity, exit_price, trigger)
                
                # Remove position if fully closed
                if position.quantity_remaining == 0:
                    self.positions[symbol].pop(i)
                    if not self.positions[symbol]:
                        del self.positions[symbol]
                    logger.info(f"Position closed: {symbol} {quantity}@${exit_price:.3f}")
                
                return success
        
        return False
    
    def get_all_positions(self) -> List[Position]:
        """Get flat list of all open positions"""
        all_pos = []
        for positions in self.positions.values():
            all_pos.extend([p for p in positions if p.quantity_remaining > 0])
        return all_pos
    
    def get_positions_summary(self) -> Dict:
        """Return summary stats for all positions"""
        positions = self.get_all_positions()
        
        total_cost = sum(p.entry_price * p.quantity_remaining for p in positions)
        total_value = sum(p.current_price * p.quantity_remaining for p in positions)
        total_unrealized_pnl = total_value - total_cost
        
        return {
            'open_positions': len(positions),
            'total_quantity': sum(p.quantity_remaining for p in positions),
            'total_cost': total_cost,
            'total_value': total_value,
            'unrealized_pnl': total_unrealized_pnl,
            'unrealized_pnl_percent': (total_unrealized_pnl / total_cost * 100) if total_cost > 0 else 0,
            'positions': [p.to_dict() for p in positions],
        }
    
    def save_positions(self) -> None:
        """Persist positions to file"""
        try:
            data = {
                'positions': {
                    symbol: [p.to_dict() for p in positions]
                    for symbol, positions in self.positions.items()
                },
                'exit_log': self.exit_log,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")
    
    def load_positions(self) -> None:
        """Load positions from file"""
        if not os.path.exists(self.storage_file):
            return
        
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
            
            for symbol, pos_list in data.get('positions', {}).items():
                self.positions[symbol] = [Position.from_dict(p) for p in pos_list]
            
            self.exit_log = data.get('exit_log', [])
            logger.info(f"Loaded {sum(len(p) for p in self.positions.values())} positions")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
    
    def clear_all(self) -> None:
        """Clear all positions (for testing/reset)"""
        self.positions.clear()
        self.exit_log.clear()
        self.save_positions()
