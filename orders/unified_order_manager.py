"""
Unified Order Manager

Master orchestrator that consolidates off-book, automated, and manual orders
into a single unified system.

This manager:
- Accepts UnifiedOrderConfig from any source (form, preset, API)
- Validates and prepares orders for submission
- Routes orders to appropriate backends (IBKR, local condition monitoring)
- Tracks order lifecycle across all three modes
- Provides consistent interface regardless of order type
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import uuid

from orders.unified_order_model import (
    UnifiedOrderConfig, OrderMode, OrderStatus,
    EntryConditionConfig, StopLossConfig, TargetConfig, SessionConfig
)
from orders.unified_order_constants import (
    PRICE_REFERENCE_TYPES, ENTRY_CONDITION_TYPES, STOP_LOSS_TYPES, TARGET_TYPES,
    validate_stop_loss_config, validate_target_config
)
from orders.price_resolver import PriceResolver, PriceResolutionContext
from orders.share_calculator import ShareCalculator
from orders.session_handler import SessionHandler, TradingSession

logger = logging.getLogger("unified_order_manager")


class UnifiedOrderManager:
    """
    Master order manager for unified order system.
    
    Responsibilities:
    1. Store and track all orders (off-book, automated, manual)
    2. Validate order configurations
    3. Calculate prices and shares
    4. Route to appropriate backends
    5. Track order lifecycle
    6. Provide order retrieval and filtering
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize manager.
        
        Args:
            storage_dir: Directory for persisting orders to disk
        """
        self.orders: Dict[str, UnifiedOrderConfig] = {}
        self.storage_dir = Path(storage_dir) if storage_dir else None
        
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized UnifiedOrderManager (storage: {self.storage_dir})")
    
    # =========================================================================
    # ORDER CREATION & REGISTRATION
    # =========================================================================
    
    def register_order(self, order: UnifiedOrderConfig) -> Tuple[bool, str]:
        """
        Register an order in the system.
        
        This validates the order and stores it. The order is not yet submitted
        to IBKR or the local condition monitor.
        
        Args:
            order: UnifiedOrderConfig to register
        
        Returns:
            (success, error_message_or_order_id)
        """
        # Validate
        is_valid, error_msg = order.validate()
        if not is_valid:
            logger.error(f"Order validation failed: {error_msg}")
            return False, f"Validation error: {error_msg}"
        
        # Store
        self.orders[order.order_id] = order
        logger.info(f"Registered order {order.order_id}: {order.symbol} {order.side} {order.quantity}sh")
        
        # Persist
        if self.storage_dir:
            self._save_order_to_disk(order)
        
        return True, order.order_id
    
    def create_offbook_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_condition: EntryConditionConfig,
        stop_loss: Optional[StopLossConfig] = None,
        notes: str = "",
    ) -> Tuple[bool, str]:
        """Create and register an off-book (condition-based) order"""
        order = UnifiedOrderConfig(
            mode=OrderMode.OFFBOOK.value,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry=entry_condition,
            stop_loss=stop_loss,
            notes=notes,
            status=OrderStatus.PENDING.value,
        )
        return self.register_order(order)
    
    def create_automated_order(
        self,
        symbol: str,
        side: str,
        entry: EntryConditionConfig,
        targets: List[TargetConfig],
        stop_loss: Optional[StopLossConfig] = None,
        quantity: int = 100,
        notes: str = "",
    ) -> Tuple[bool, str]:
        """Create and register an automated (multi-level) order"""
        order = UnifiedOrderConfig(
            mode=OrderMode.AUTOMATED.value,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry=entry,
            stop_loss=stop_loss,
            targets=targets,
            notes=notes,
            status=OrderStatus.PENDING.value,
        )
        return self.register_order(order)
    
    def create_manual_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        profit_target: Optional[TargetConfig] = None,
        stop_loss: Optional[StopLossConfig] = None,
        notes: str = "",
    ) -> Tuple[bool, str]:
        """Create and register a manual order (direct configuration)"""
        entry_config = EntryConditionConfig(
            condition_type='immediate',
            order_type='limit',
        )
        
        order = UnifiedOrderConfig(
            mode=OrderMode.MANUAL.value,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry=entry_config,
            entry_price=entry_price,
            stop_loss=stop_loss,
            targets=[profit_target] if profit_target else [],
            notes=notes,
            status=OrderStatus.PENDING.value,
        )
        return self.register_order(order)
    
    # =========================================================================
    # ORDER RETRIEVAL & FILTERING
    # =========================================================================
    
    def get_order(self, order_id: str) -> Optional[UnifiedOrderConfig]:
        """Get order by ID"""
        return self.orders.get(order_id)
    
    def get_orders_by_symbol(self, symbol: str, status: Optional[str] = None) -> List[UnifiedOrderConfig]:
        """Get all orders for a symbol, optionally filtered by status"""
        orders = [o for o in self.orders.values() if o.symbol == symbol]
        if status:
            orders = [o for o in orders if o.status == status]
        return orders
    
    def get_orders_by_mode(self, mode: str, status: Optional[str] = None) -> List[UnifiedOrderConfig]:
        """Get all orders of a specific mode (offbook, automated, manual)"""
        orders = [o for o in self.orders.values() if o.mode == mode]
        if status:
            orders = [o for o in orders if o.status == status]
        return orders
    
    def get_pending_orders(self) -> List[UnifiedOrderConfig]:
        """Get all pending orders"""
        return [o for o in self.orders.values() if o.status == OrderStatus.PENDING.value]
    
    def get_active_orders(self) -> List[UnifiedOrderConfig]:
        """Get all active orders"""
        return [o for o in self.orders.values() if o.status == OrderStatus.ACTIVE.value]
    
    def get_offbook_active(self) -> List[UnifiedOrderConfig]:
        """Get all active off-book orders"""
        return self.get_orders_by_mode(OrderMode.OFFBOOK.value, status=OrderStatus.ACTIVE.value)
    
    # =========================================================================
    # ORDER PREPARATION & PRICE CALCULATION
    # =========================================================================
    
    def calculate_prices(
        self,
        order: UnifiedOrderConfig,
        context: PriceResolutionContext,
    ) -> Tuple[bool, str]:
        """
        Calculate entry, stop, and target prices.
        
        Updates the order with calculated prices.
        
        Args:
            order: UnifiedOrderConfig
            context: PriceResolutionContext with market data
        
        Returns:
            (success, error_message)
        """
        try:
            # Resolve entry price
            if order.entry.condition_type == 'immediate':
                # For immediate entry with limit offset
                if order.entry.order_type == 'market':
                    order.entry_price = context.current_price
                else:
                    # Apply limit offset
                    multiplier = 1.0 + (order.entry.limit_offset_pct / 100.0)
                    order.entry_price = round(context.current_price * multiplier, 2)
            else:
                # For conditional entry (candle breakout, MA crossover), resolve at trigger time
                price, error = PriceResolver.resolve_price(
                    f"{order.entry.condition_type}_ref",
                    order.entry.limit_offset_pct,
                    context,
                )
                if error:
                    logger.warning(f"Could not resolve entry price: {error}")
                else:
                    order.entry_price = price
            
            # Resolve stop price
            if order.stop_loss:
                stop_price, error = PriceResolver.resolve_stop_price(
                    order.entry_price or context.current_price,
                    order.stop_loss,
                    context,
                )
                if error:
                    logger.warning(f"Could not resolve stop price: {error}")
                else:
                    order.stop_price = stop_price
            
            # Resolve target prices
            order.target_prices = []
            for target in order.targets:
                target_price, error = PriceResolver.resolve_target_price(
                    order.entry_price or context.current_price,
                    target,
                    context,
                )
                if error:
                    logger.warning(f"Could not resolve target price for {target.target_type}: {error}")
                else:
                    order.target_prices.append(target_price)
            
            return True, ""
        
        except Exception as e:
            error_msg = f"Error calculating prices: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def calculate_shares(
        self,
        order: UnifiedOrderConfig,
        current_price: float,
        account_size: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Calculate share quantity.
        
        Updates order.quantity with calculated value.
        
        Args:
            order: UnifiedOrderConfig
            current_price: Current price for amount-based calculations
            account_size: Account size for risk-based calculations
        
        Returns:
            (success, error_message)
        """
        try:
            config = order.shares_config
            
            if config.calculation_method == 'fixed_quantity':
                order.quantity = config.fixed_quantity
            
            elif config.calculation_method == 'from_amount':
                shares, error = ShareCalculator.calculate_from_amount(
                    config.amount_dollars,
                    current_price,
                )
                if error:
                    return False, f"Share calculation error: {error}"
                order.quantity = shares
            
            elif config.calculation_method == 'from_percent_risk':
                if not account_size:
                    account_size = config.account_size
                
                shares, error = ShareCalculator.calculate_from_percent_risk(
                    account_size,
                    config.risk_percent,
                    order.entry_price or current_price,
                    order.stop_price or (current_price * 0.95),  # Default to 5% below
                )
                if error:
                    return False, f"Share calculation error: {error}"
                order.quantity = shares
            
            logger.info(f"Calculated {order.quantity} shares for {order.symbol}")
            return True, ""
        
        except Exception as e:
            error_msg = f"Error calculating shares: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def prepare_for_submission(
        self,
        order: UnifiedOrderConfig,
        price_context: Optional[PriceResolutionContext] = None,
        current_price: Optional[float] = None,
        account_size: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Fully prepare order for submission.
        
        This:
        1. Calculates prices
        2. Calculates shares
        3. Validates session constraints
        4. Updates status to 'pending_submission'
        
        Args:
            order: UnifiedOrderConfig
            price_context: PriceResolutionContext (required for price calculation)
            current_price: Current price (required if calculating shares)
            account_size: Account size (optional, for risk-based shares)
        
        Returns:
            (success, [warnings])
        """
        warnings = []
        
        # Calculate prices if context provided
        if price_context:
            success, error = self.calculate_prices(order, price_context)
            if not success:
                warnings.append(f"⚠️  Price calculation: {error}")
        
        # Calculate shares if current_price provided
        if current_price:
            success, error = self.calculate_shares(order, current_price, account_size)
            if not success:
                warnings.append(f"⚠️  Share calculation: {error}")
        
        # Validate for current session
        session = SessionHandler.get_current_session()
        is_valid, session_issues = SessionHandler.validate_order_for_session(order, session)
        warnings.extend(session_issues)
        
        # Prepare session settings
        success, error = SessionHandler.prepare_order_for_submission(order, session)
        if not success:
            warnings.append(f"⚠️  Session preparation: {error}")
        
        # Update status
        order.status = OrderStatus.PENDING.value
        order.modified_at = datetime.utcnow().isoformat()
        
        return True, warnings
    
    # =========================================================================
    # ORDER SUBMISSION ROUTING
    # =========================================================================
    
    def submit_order(self, order: UnifiedOrderConfig) -> Tuple[bool, str]:
        """
        Submit order to appropriate backend.
        
        Routes based on order.mode:
        - offbook: Register with condition monitor
        - automated: Submit to IBKR via multiLevelOrderAdvanced
        - manual: Submit to IBKR via standard order endpoint
        
        Args:
            order: UnifiedOrderConfig
        
        Returns:
            (success, message_or_error)
        
        Note: Actual routing to IBKR/monitors not implemented here.
              This is handled by dedicated backends.
        """
        if order.status not in [OrderStatus.PENDING.value, OrderStatus.PENDING.value]:
            return False, f"Cannot submit order in {order.status} status"
        
        try:
            order.status = OrderStatus.ACTIVE.value
            order.submitted_at = datetime.utcnow().isoformat()
            order.modified_at = datetime.utcnow().isoformat()
            
            logger.info(f"Submitted order {order.order_id} ({order.mode} mode)")
            
            # Persist
            if self.storage_dir:
                self._save_order_to_disk(order)
            
            # TODO: Route to actual backends:
            # if order.mode == OrderMode.OFFBOOK.value:
            #     held_orders_manager.add_order(order)
            # elif order.mode == OrderMode.AUTOMATED.value:
            #     ibkr_api.multiLevelOrderAdvanced(order)
            # elif order.mode == OrderMode.MANUAL.value:
            #     ibkr_api.placeOrder(order)
            
            return True, order.order_id
        
        except Exception as e:
            error_msg = f"Error submitting order: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    # =========================================================================
    # ORDER PERSISTENCE
    # =========================================================================
    
    def _save_order_to_disk(self, order: UnifiedOrderConfig):
        """Save order to disk as JSON"""
        if not self.storage_dir:
            return
        
        try:
            order_file = self.storage_dir / f"{order.order_id}.json"
            order_file.write_text(order.to_json(), encoding='utf-8')
            logger.debug(f"Saved order {order.order_id} to disk")
        except Exception as e:
            logger.error(f"Error saving order to disk: {str(e)}")
    
    def _load_order_from_disk(self, order_id: str) -> Optional[UnifiedOrderConfig]:
        """Load order from disk"""
        if not self.storage_dir:
            return None
        
        try:
            order_file = self.storage_dir / f"{order_id}.json"
            if not order_file.exists():
                return None
            
            json_str = order_file.read_text(encoding='utf-8')
            order = UnifiedOrderConfig.from_json(json_str)
            logger.debug(f"Loaded order {order_id} from disk")
            return order
        except Exception as e:
            logger.error(f"Error loading order from disk: {str(e)}")
            return None
    
    def load_all_from_disk(self):
        """Load all orders from disk"""
        if not self.storage_dir:
            return
        
        try:
            json_files = self.storage_dir.glob("*.json")
            for json_file in json_files:
                order_id = json_file.stem
                order = self._load_order_from_disk(order_id)
                if order:
                    self.orders[order.order_id] = order
            logger.info(f"Loaded {len(self.orders)} orders from disk")
        except Exception as e:
            logger.error(f"Error loading orders from disk: {str(e)}")
    
    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================
    
    def get_statistics(self) -> Dict:
        """Get order statistics"""
        all_orders = list(self.orders.values())
        
        return {
            'total_orders': len(all_orders),
            'by_mode': {
                'offbook': len([o for o in all_orders if o.mode == OrderMode.OFFBOOK.value]),
                'automated': len([o for o in all_orders if o.mode == OrderMode.AUTOMATED.value]),
                'manual': len([o for o in all_orders if o.mode == OrderMode.MANUAL.value]),
            },
            'by_status': {
                'pending': len([o for o in all_orders if o.status == OrderStatus.PENDING.value]),
                'active': len([o for o in all_orders if o.status == OrderStatus.ACTIVE.value]),
                'triggered': len([o for o in all_orders if o.status == OrderStatus.TRIGGERED.value]),
                'executed': len([o for o in all_orders if o.status == OrderStatus.EXECUTED.value]),
                'cancelled': len([o for o in all_orders if o.status == OrderStatus.CANCELLED.value]),
            },
            'by_side': {
                'long': len([o for o in all_orders if o.side == 'long']),
                'short': len([o for o in all_orders if o.side == 'short']),
            },
        }
