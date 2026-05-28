"""
Session-Aware Order Handler for Unified Order System

Handles pre-market and after-hours trading constraints:
- Detects current session (PM, regular hours, AH)
- Applies session-specific constraints (no bracket orders in extended hours)
- Splits orders appropriately for extended hours
- Sets outsideRth flag and time_in_force correctly

This ensures orders work correctly across all trading sessions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger("session_handler")


class TradingSession(Enum):
    """Current trading session"""
    PREMARKET = "premarket"  # 4 AM - 9:30 AM ET
    REGULAR = "regular"  # 9:30 AM - 4 PM ET
    AFTERHOURS = "afterhours"  # 4 PM - 8 PM ET


class SessionHandler:
    """Handles trading session constraints and order adjustments"""
    
    # Trading session times (ET)
    PREMARKET_START = time(4, 0)  # 4:00 AM
    REGULAR_START = time(9, 30)  # 9:30 AM
    REGULAR_END = time(16, 0)  # 4:00 PM
    AFTERHOURS_END = time(20, 0)  # 8:00 PM
    
    @staticmethod
    def get_current_session(timestamp: Optional[datetime] = None) -> TradingSession:
        """
        Determine current trading session.
        
        Args:
            timestamp: Datetime to check (defaults to now)
        
        Returns:
            TradingSession enum
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        current_time = timestamp.time()
        
        if current_time >= SessionHandler.PREMARKET_START and current_time < SessionHandler.REGULAR_START:
            return TradingSession.PREMARKET
        elif current_time >= SessionHandler.REGULAR_START and current_time < SessionHandler.REGULAR_END:
            return TradingSession.REGULAR
        elif current_time >= SessionHandler.REGULAR_END and current_time < SessionHandler.AFTERHOURS_END:
            return TradingSession.AFTERHOURS
        else:
            # Outside trading hours - return AFTERHOURS as default for extended hours
            return TradingSession.AFTERHOURS
    
    @staticmethod
    def is_extended_hours(session: TradingSession) -> bool:
        """Check if session is extended hours (PM or AH)"""
        return session in [TradingSession.PREMARKET, TradingSession.AFTERHOURS]
    
    @staticmethod
    def validate_order_for_session(
        unified_order_config,  # UnifiedOrderConfig
        session: Optional[TradingSession] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Validate if order configuration is valid for current/specified session.
        
        Args:
            unified_order_config: UnifiedOrderConfig to validate
            session: Session to validate for (uses current if None)
        
        Returns:
            (is_valid, [warnings/errors])
        """
        if session is None:
            session = SessionHandler.get_current_session()
        
        issues = []
        
        # Check if order type is supported in extended hours
        if SessionHandler.is_extended_hours(session):
            # Bracket orders not supported in extended hours
            if any(t.order_type == 'bracket' for t in unified_order_config.targets):
                issues.append(
                    f"⚠️  Bracket orders not supported in {session.value} - will use separate orders"
                )
            
            # Check entry condition
            if unified_order_config.entry.order_type == 'bracket':
                issues.append("⚠️  Bracket entry not supported in extended hours")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def prepare_order_for_submission(
        unified_order_config,  # UnifiedOrderConfig
        session: Optional[TradingSession] = None,
    ) -> Tuple[bool, str]:
        """
        Prepare order for submission with session-appropriate settings.
        
        Modifies:
        - session.outsideRth flag
        - session.time_in_force
        - Order type (converts bracket to separate orders if needed)
        
        Args:
            unified_order_config: UnifiedOrderConfig
            session: Session (uses current if None)
        
        Returns:
            (success, error_message)
        """
        if session is None:
            session = SessionHandler.get_current_session()
        
        try:
            # Set outsideRth flag based on session
            if SessionHandler.is_extended_hours(session):
                unified_order_config.session.outsideRth = True
                
                # Extended hours require GTC
                if unified_order_config.session.time_in_force != 'GTC':
                    logger.info(
                        f"Changing TIF from {unified_order_config.session.time_in_force} to GTC "
                        f"for {session.value} trading"
                    )
                    unified_order_config.session.time_in_force = 'GTC'
            else:
                unified_order_config.session.outsideRth = False
            
            # Handle bracket order constraints in extended hours
            if SessionHandler.is_extended_hours(session) and unified_order_config.targets:
                has_bracket = any(t.order_type == 'bracket' for t in unified_order_config.targets)
                
                if has_bracket:
                    logger.warning(
                        f"Bracket orders not supported in {session.value}. "
                        f"Converting to separate limit orders."
                    )
                    
                    # Convert bracket targets to regular limit orders
                    for target in unified_order_config.targets:
                        if target.order_type == 'bracket':
                            target.order_type = 'limit'
            
            return True, ""
        
        except Exception as e:
            return False, f"Error preparing order for submission: {str(e)}"
    
    @staticmethod
    def split_extended_hours_order(
        unified_order_config,  # UnifiedOrderConfig
    ) -> Tuple[Optional[object], Optional[object]]:
        """
        Split an extended hours order into PM and AH components if needed.
        
        For orders that should work across pre-market and after-hours,
        IBKR requires separate orders for bracket legs.
        
        Args:
            unified_order_config: UnifiedOrderConfig with session.session_type = 'extended'
        
        Returns:
            (pm_order, ah_order) - copies of the config configured for each session
        
        Example:
            If order.session.session_type == 'extended' and has bracket legs,
            this returns two orders with appropriate session settings.
        """
        if unified_order_config.session.session_type not in ['extended', 'all_hours']:
            return unified_order_config, None
        
        try:
            # Deep copy for PM order
            import copy
            pm_order = copy.deepcopy(unified_order_config)
            ah_order = copy.deepcopy(unified_order_config)
            
            # Configure PM order (pre-market)
            pm_order.session.session_type = 'premarket'
            pm_order.session.use_premarket = True
            pm_order.session.use_afterhours = False
            pm_order.session.outsideRth = True
            pm_order.notes = f"{pm_order.notes} [PreMarket]".strip()
            
            # Configure AH order (after-hours)
            ah_order.session.session_type = 'afterhours'
            ah_order.session.use_premarket = False
            ah_order.session.use_afterhours = True
            ah_order.session.outsideRth = True
            ah_order.notes = f"{ah_order.notes} [AfterHours]".strip()
            
            logger.info(f"Split extended hours order into PM and AH components")
            
            return pm_order, ah_order
        
        except Exception as e:
            logger.error(f"Error splitting extended hours order: {str(e)}")
            return unified_order_config, None


# =============================================================================
# SESSION UTILITY FUNCTIONS
# =============================================================================

def get_current_trading_session() -> str:
    """Get current trading session as string"""
    session = SessionHandler.get_current_session()
    return session.value


def is_extended_hours() -> bool:
    """Check if currently in extended hours"""
    session = SessionHandler.get_current_session()
    return SessionHandler.is_extended_hours(session)


def is_regular_hours() -> bool:
    """Check if currently in regular trading hours"""
    return SessionHandler.get_current_session() == TradingSession.REGULAR


def is_premarket() -> bool:
    """Check if currently in pre-market"""
    return SessionHandler.get_current_session() == TradingSession.PREMARKET


def is_afterhours() -> bool:
    """Check if currently in after-hours"""
    return SessionHandler.get_current_session() == TradingSession.AFTERHOURS
