"""
Gap Playbook Engine

Multi-playbook trading framework for Fibonacci gap pullback analysis.
Supports configurable playbooks with different trading strategies,
risk parameters, and technical indicator combinations.

Each playbook can:
- Define preferred Fibonacci levels
- Set risk/reward requirements
- Include/exclude specific indicators
- Apply different entry/exit logic
- Run at multiple timeframes
- Generate automated trading signals
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from decimal import Decimal

from scanner.indicators import FibonacciGapPullbackAnalyzer, RiskRewardEvaluator

logger = logging.getLogger("gap_playbook_engine")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PlaybookConfig:
    """Configuration for a single gap playbook."""
    
    name: str
    description: str
    trade_direction: str = 'long'  # 'long' or 'short'
    
    # Fibonacci level preferences
    preferred_levels: List[float] = field(default_factory=lambda: [0.382, 0.5, 0.618])
    min_level: float = 0.236
    max_level: float = 1.0
    
    # Risk/reward requirements
    min_reward_risk_ratio: float = 1.5
    max_risk_per_trade_pct: float = 2.0
    
    # Gap requirements
    min_gap_pct: float = 1.0  # Minimum gap size to consider
    max_gap_pct: float = 15.0  # Maximum gap size
    
    # Recent context
    lookback_days: int = 20
    use_recent_peak: bool = True
    
    # Technical indicators to use
    indicators: List[str] = field(default_factory=lambda: ['sma_20', 'sma_50'])
    
    # Entry/exit logic
    entry_offset_pct: float = 0.0  # Offset from calculated Fib level
    stop_loss_pct: float = 2.0  # As % of gap move
    target_profit_pct: float = 2.0  # As % of gap move
    
    # Filters
    minimum_confidence_score: float = 70.0
    only_within_market_hours: bool = True
    
    # Advanced
    enabled: bool = True
    active_at_time: Optional[str] = None  # Time of day to activate (e.g., "09:30", "14:00")
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlaybookConfig':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PlaybookSignal:
    """Trading signal generated from a playbook."""
    
    playbook_name: str
    symbol: str
    signal_type: str  # 'entry', 'exit', 'alert'
    direction: str  # 'long', 'short'
    
    entry_price: float
    stop_loss: float
    target_price: float
    
    confidence_score: float
    fib_level: float
    fib_level_percent: float
    
    gap_size: float
    gap_pct: float
    
    # Additional context
    current_price: float
    distance_from_entry: float
    risk_reward_ratio: float
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PlaybookResult:
    """Result from running a playbook analysis."""
    
    playbook_name: str
    symbol: str
    status: str  # 'success', 'no_gap', 'no_setup', 'failed'
    
    signal: Optional[PlaybookSignal] = None
    analysis: Optional[Dict[str, Any]] = None
    
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.signal:
            data['signal'] = self.signal.to_dict()
        return data


# =============================================================================
# Playbook Engine
# =============================================================================

class GapPlaybookEngine:
    """
    Main engine for running gap pullback playbooks.
    
    Manages:
    - Multiple playbook configurations
    - Signal generation from playbooks
    - Playbook saving/loading
    - Multi-playbook execution and result aggregation
    """
    
    def __init__(self, playbooks_dir: str = './setups'):
        """
        Initialize the playbook engine.
        
        Args:
            playbooks_dir: Directory to store playbook configurations
        """
        self.playbooks_dir = Path(playbooks_dir)
        self.playbooks_dir.mkdir(exist_ok=True)
        
        self.playbooks: Dict[str, PlaybookConfig] = {}
        self.analyzer = FibonacciGapPullbackAnalyzer()
        self.evaluator = RiskRewardEvaluator()
        
        # Load existing playbooks
        self.load_all_playbooks()
    
    # =========================================================================
    # Playbook Management
    # =========================================================================
    
    def create_playbook(self, config: PlaybookConfig) -> None:
        """Create and register a new playbook."""
        self.playbooks[config.name] = config
        logger.info(f"Created playbook: {config.name}")
    
    def delete_playbook(self, name: str) -> bool:
        """Delete a playbook."""
        if name in self.playbooks:
            del self.playbooks[name]
            playbook_file = self.playbooks_dir / f"{name}.json"
            if playbook_file.exists():
                playbook_file.unlink()
            logger.info(f"Deleted playbook: {name}")
            return True
        return False
    
    def get_playbook(self, name: str) -> Optional[PlaybookConfig]:
        """Get a playbook by name."""
        return self.playbooks.get(name)
    
    def list_playbooks(self, enabled_only: bool = False) -> List[str]:
        """List all playbook names."""
        if enabled_only:
            return [name for name, pb in self.playbooks.items() if pb.enabled]
        return list(self.playbooks.keys())
    
    def save_playbook(self, name: str) -> bool:
        """Save a playbook to file."""
        if name not in self.playbooks:
            return False
        
        config = self.playbooks[name]
        playbook_file = self.playbooks_dir / f"{name}.json"
        
        with open(playbook_file, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)
        
        logger.info(f"Saved playbook: {name}")
        return True
    
    def load_playbook(self, name: str, filepath: Optional[str] = None) -> bool:
        """Load a playbook from file."""
        if not filepath:
            filepath = str(self.playbooks_dir / f"{name}.json")
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            config = PlaybookConfig.from_dict(data)
            self.playbooks[name] = config
            logger.info(f"Loaded playbook: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load playbook {name}: {e}")
            return False
    
    def load_all_playbooks(self) -> int:
        """Load all playbooks from directory."""
        count = 0
        for filepath in self.playbooks_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                config = PlaybookConfig.from_dict(data)
                self.playbooks[config.name] = config
                count += 1
            except Exception as e:
                logger.warning(f"Failed to load playbook {filepath}: {e}")
        
        if count > 0:
            logger.info(f"Loaded {count} playbooks from {self.playbooks_dir}")
        return count
    
    # =========================================================================
    # Signal Generation
    # =========================================================================
    
    def run_playbook(self, playbook_name: str, symbol: str, price_data: Dict[str, Any],
                    recent_daily_data: Optional[List[Dict]] = None) -> PlaybookResult:
        """
        Run a single playbook analysis on a symbol.
        
        Args:
            playbook_name: Name of the playbook to run
            symbol: Stock symbol
            price_data: Current price data with keys:
                - prev_close: Previous close price
                - today_high: Today's high
                - today_low: Today's low
                - current_price: Current intraday price
            recent_daily_data: List of recent daily candles (optional)
        
        Returns:
            PlaybookResult with signal or error
        """
        playbook = self.get_playbook(playbook_name)
        if not playbook:
            return PlaybookResult(
                playbook_name=playbook_name,
                symbol=symbol,
                status='failed',
                error_message=f'Playbook not found: {playbook_name}'
            )
        
        if not playbook.enabled:
            return PlaybookResult(
                playbook_name=playbook_name,
                symbol=symbol,
                status='failed',
                error_message=f'Playbook is disabled: {playbook_name}'
            )
        
        try:
            # Run gap pullback analysis
            analysis = self.analyzer.analyze_gap_pullback(
                prev_close=price_data['prev_close'],
                today_high=price_data['today_high'],
                today_low=price_data['today_low'],
                current_price=price_data['current_price'],
                recent_daily_data=recent_daily_data or [],
                trade_direction=playbook.trade_direction
            )
            
            # Check if gap is valid
            if 'error' in analysis or not analysis['gap_analysis']['is_valid_gap']:
                return PlaybookResult(
                    playbook_name=playbook_name,
                    symbol=symbol,
                    status='no_gap',
                    analysis=analysis
                )
            
            # Evaluate gap against playbook criteria
            gap_pct = abs(analysis['gap_analysis']['gap_pct'])
            if gap_pct < playbook.min_gap_pct or gap_pct > playbook.max_gap_pct:
                return PlaybookResult(
                    playbook_name=playbook_name,
                    symbol=symbol,
                    status='no_setup',
                    error_message=f'Gap {gap_pct:.2f}% outside range [{playbook.min_gap_pct}, {playbook.max_gap_pct}]',
                    analysis=analysis
                )
            
            # Filter levels by playbook preferences
            ranked_levels = analysis['ranked_levels']
            filtered_levels = self._filter_levels_by_playbook(ranked_levels, playbook)
            
            if not filtered_levels:
                return PlaybookResult(
                    playbook_name=playbook_name,
                    symbol=symbol,
                    status='no_setup',
                    error_message='No levels match playbook criteria',
                    analysis=analysis
                )
            
            # Create signal from best level
            signal = self._create_signal_from_level(
                playbook_name,
                symbol,
                filtered_levels[0],
                analysis,
                playbook
            )
            
            if signal.confidence_score < playbook.minimum_confidence_score:
                return PlaybookResult(
                    playbook_name=playbook_name,
                    symbol=symbol,
                    status='no_setup',
                    error_message=f'Confidence {signal.confidence_score} below minimum {playbook.minimum_confidence_score}',
                    analysis=analysis,
                    signal=signal
                )
            
            return PlaybookResult(
                playbook_name=playbook_name,
                symbol=symbol,
                status='success',
                signal=signal,
                analysis=analysis
            )
        
        except Exception as e:
            logger.error(f"Error running playbook {playbook_name} on {symbol}: {e}")
            return PlaybookResult(
                playbook_name=playbook_name,
                symbol=symbol,
                status='failed',
                error_message=str(e)
            )
    
    def run_all_playbooks(self, symbol: str, price_data: Dict[str, Any],
                         recent_daily_data: Optional[List[Dict]] = None,
                         enabled_only: bool = True) -> List[PlaybookResult]:
        """
        Run all playbooks on a symbol.
        
        Args:
            symbol: Stock symbol
            price_data: Current price data
            recent_daily_data: Recent daily data
            enabled_only: Only run enabled playbooks
        
        Returns:
            List of PlaybookResult objects
        """
        results = []
        playbook_names = self.list_playbooks(enabled_only=enabled_only)
        
        for playbook_name in playbook_names:
            result = self.run_playbook(playbook_name, symbol, price_data, recent_daily_data)
            results.append(result)
        
        return results
    
    # =========================================================================
    # Filtering and Signal Creation
    # =========================================================================
    
    @staticmethod
    def _filter_levels_by_playbook(ranked_levels: List[Dict], 
                                   playbook: PlaybookConfig) -> List[Dict]:
        """Filter Fibonacci levels based on playbook preferences."""
        filtered = []
        
        for level_data in ranked_levels:
            level = level_data['level']
            
            # Check level range
            if level < playbook.min_level or level > playbook.max_level:
                continue
            
            # Prefer levels in playbook's preference list
            if playbook.preferred_levels and level not in playbook.preferred_levels:
                continue
            
            # Check confidence score minimum
            if level_data['total_score'] < playbook.minimum_confidence_score:
                continue
            
            filtered.append(level_data)
        
        return filtered
    
    @staticmethod
    def _create_signal_from_level(playbook_name: str, symbol: str, level_data: Dict,
                                  analysis: Dict, playbook: PlaybookConfig) -> PlaybookSignal:
        """Create a trading signal from a Fibonacci level."""
        
        entry_price = level_data['entry']
        current_price = level_data['current_price']
        level = level_data['level']
        confidence_score = level_data['total_score']
        
        # Calculate stop and target
        gap_move = abs(analysis['gap_analysis']['gap_size'])
        stop_loss = entry_price - (gap_move * playbook.stop_loss_pct / 100.0)
        target = entry_price + (gap_move * playbook.target_profit_pct / 100.0)
        
        risk = entry_price - stop_loss
        reward = target - entry_price
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        return PlaybookSignal(
            playbook_name=playbook_name,
            symbol=symbol,
            signal_type='entry',
            direction=playbook.trade_direction,
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            confidence_score=round(confidence_score, 1),
            fib_level=level,
            fib_level_percent=round(level * 100, 1),
            gap_size=round(gap_move, 2),
            gap_pct=round(analysis['gap_analysis']['gap_pct'], 2),
            current_price=round(current_price, 2),
            distance_from_entry=round(abs(entry_price - current_price), 2),
            risk_reward_ratio=round(risk_reward_ratio, 2),
            notes=f"Gap pullback at {level*100:.1f}% level - {analysis['gap_analysis']['gap_type']} gap"
        )


# =============================================================================
# Preset Playbooks
# =============================================================================

def create_default_playbooks() -> Dict[str, PlaybookConfig]:
    """Create a set of default playbook configurations."""
    
    playbooks = {
        'Conservative Long': PlaybookConfig(
            name='Conservative Long',
            description='Conservative long playbook - prefers 50%+ retracements with strong R:R',
            trade_direction='long',
            preferred_levels=[0.5, 0.618, 0.786],
            min_reward_risk_ratio=2.0,
            max_risk_per_trade_pct=1.5,
            min_gap_pct=1.5,
            max_gap_pct=8.0,
            minimum_confidence_score=75.0,
            tags=['conservative', 'long']
        ),
        
        'Aggressive Long': PlaybookConfig(
            name='Aggressive Long',
            description='Aggressive long playbook - enters at shallower retracements',
            trade_direction='long',
            preferred_levels=[0.236, 0.382],
            min_reward_risk_ratio=1.5,
            max_risk_per_trade_pct=2.5,
            min_gap_pct=1.0,
            max_gap_pct=12.0,
            minimum_confidence_score=60.0,
            tags=['aggressive', 'long']
        ),
        
        'Mid-Range Long': PlaybookConfig(
            name='Mid-Range Long',
            description='Balanced long playbook - 38.2% to 61.8% range',
            trade_direction='long',
            preferred_levels=[0.382, 0.5, 0.618],
            min_reward_risk_ratio=1.8,
            max_risk_per_trade_pct=2.0,
            min_gap_pct=1.2,
            max_gap_pct=10.0,
            minimum_confidence_score=70.0,
            tags=['balanced', 'long']
        ),
        
        'Conservative Short': PlaybookConfig(
            name='Conservative Short',
            description='Conservative short playbook - gap down pullback',
            trade_direction='short',
            preferred_levels=[0.5, 0.618, 0.786],
            min_reward_risk_ratio=2.0,
            max_risk_per_trade_pct=1.5,
            min_gap_pct=1.5,
            max_gap_pct=8.0,
            minimum_confidence_score=75.0,
            tags=['conservative', 'short']
        ),
        
        'Quick Scalp': PlaybookConfig(
            name='Quick Scalp',
            description='Quick scalp playbook - small gaps, quick profits',
            trade_direction='long',
            preferred_levels=[0.236, 0.382],
            min_reward_risk_ratio=1.2,
            max_risk_per_trade_pct=1.0,
            min_gap_pct=1.0,
            max_gap_pct=3.0,
            minimum_confidence_score=65.0,
            stop_loss_pct=1.0,
            target_profit_pct=1.5,
            tags=['scalp', 'long', 'quick']
        ),
    }
    
    return playbooks


def save_default_playbooks(engine: GapPlaybookEngine) -> int:
    """Save all default playbooks to engine."""
    defaults = create_default_playbooks()
    
    for name, config in defaults.items():
        engine.create_playbook(config)
        engine.save_playbook(name)
    
    logger.info(f"Saved {len(defaults)} default playbooks")
    return len(defaults)
