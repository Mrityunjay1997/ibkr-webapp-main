"""
Held Orders API - Backend API endpoints for managing and monitoring held orders

This module provides Flask endpoints for:
- Creating held orders with entry/exit conditions
- Listing and viewing held orders
- Monitoring held order conditions
- Triggering held orders when conditions are met
- Canceling held orders
"""

import json
import logging
import time
from datetime import datetime
from flask import request, jsonify
from held_orders_manager import (
    HeldOrdersManager, HeldOrder, HeldOrderCondition,
    CandleBreakoutCondition, MovingAverageCondition, ConditionChecker
)
from ibkr_signal_engine import IBapi

logger = logging.getLogger("held_orders_api")

# Global held orders manager (singleton)
_held_orders_manager = None


def get_held_orders_manager():
    """Get or create the global held orders manager."""
    global _held_orders_manager
    if _held_orders_manager is None:
        _held_orders_manager = HeldOrdersManager()
    return _held_orders_manager


def register_held_orders_routes(app):
    """Register all held orders API routes with the Flask app."""
    
    @app.route("/held-orders/create", methods=["POST"])
    def create_held_order():
        """
        Create a new held order with entry conditions.
        
        Request JSON:
        {
            "symbol": "DGXX",
            "side": "long" or "short",
            "quantity": 100,
            "order_type": "limit" or "market",
            "limit_price": 155.50,  # optional, can be null
            "tif": "DAY",  # "DAY", "GTC", etc.
            "entry_conditions": [
                {
                    "condition_type": "candle_breakout",
                    "config": {
                        "timeframe": "5min",
                        "candles_to_check": 1,
                        "break_direction": "above_high",
                        "entry_offset_pct": 0.5,
                        "lookback_bars": 5
                    }
                }
            ],
            "exit_conditions": [],  # optional
            "notes": "Short DGXX at high of day +0.5%"
        }
        """
        try:
            data = request.get_json()
            
            # Validate required fields
            required = ["symbol", "side", "quantity", "order_type"]
            for field in required:
                if field not in data:
                    return {"status": "error", "message": f"Missing required field: {field}"}, 400
            
            symbol = data["symbol"].upper()
            side = data["side"].lower()
            quantity = int(data["quantity"])
            order_type = data["order_type"].lower()
            limit_price = data.get("limit_price")
            tif = data.get("tif", "DAY")
            notes = data.get("notes", "")
            
            # Validate inputs
            if side not in ["long", "short"]:
                return {"status": "error", "message": "side must be 'long' or 'short'"}, 400
            if quantity <= 0:
                return {"status": "error", "message": "quantity must be > 0"}, 400
            if order_type not in ["limit", "market"]:
                return {"status": "error", "message": "order_type must be 'limit' or 'market'"}, 400
            
            # Create the held order
            manager = get_held_orders_manager()
            order = manager.create_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=float(limit_price) if limit_price else None,
                notes=notes
            )
            
            # Add entry conditions
            for cond_data in data.get("entry_conditions", []):
                try:
                    condition_type = cond_data.get("condition_type", "").lower()
                    config = cond_data.get("config", {})
                    
                    condition = HeldOrderCondition(
                        condition_type=condition_type,
                        phase="entry",
                        config=config
                    )
                    manager.add_entry_condition(order.order_id, condition)
                    logger.info(f"Added entry condition {condition_type} to order {order.order_id}")
                except Exception as e:
                    logger.error(f"Error adding entry condition: {e}")
                    # Continue adding other conditions
            
            # Add exit conditions if provided
            for cond_data in data.get("exit_conditions", []):
                try:
                    condition_type = cond_data.get("condition_type", "").lower()
                    config = cond_data.get("config", {})
                    
                    condition = HeldOrderCondition(
                        condition_type=condition_type,
                        phase="exit",
                        config=config
                    )
                    manager.add_exit_condition(order.order_id, condition)
                    logger.info(f"Added exit condition {condition_type} to order {order.order_id}")
                except Exception as e:
                    logger.error(f"Error adding exit condition: {e}")
            
            logger.info(f"Created held order {order.order_id} for {symbol}")
            
            return {
                "status": "ok",
                "message": "Held order created",
                "order_id": order.order_id,
                "order": order.to_dict()
            }, 201
        
        except Exception as e:
            logger.exception("Error creating held order")
            return {"status": "error", "message": str(e)}, 500
    
    
    @app.route("/held-orders/list", methods=["GET"])
    def list_held_orders():
        """List all held orders or filter by symbol."""
        try:
            symbol = request.args.get("symbol", "").upper()
            manager = get_held_orders_manager()
            
            if symbol:
                orders = manager.get_active_orders_for_symbol(symbol)
            else:
                orders = list(manager.orders.values())
            
            return {
                "status": "ok",
                "orders": [o.to_dict() for o in orders],
                "count": len(orders)
            }, 200
        
        except Exception as e:
            logger.exception("Error listing held orders")
            return {"status": "error", "message": str(e)}, 500
    
    
    @app.route("/held-orders/<order_id>", methods=["GET"])
    def get_held_order(order_id):
        """Get details of a specific held order."""
        try:
            manager = get_held_orders_manager()
            order = manager.get_order(order_id)
            
            if not order:
                return {"status": "error", "message": "Order not found"}, 404
            
            return {
                "status": "ok",
                "order": order.to_dict()
            }, 200
        
        except Exception as e:
            logger.exception(f"Error getting held order {order_id}")
            return {"status": "error", "message": str(e)}, 500
    
    
    @app.route("/held-orders/<order_id>/cancel", methods=["POST"])
    def cancel_held_order(order_id):
        """Cancel a held order."""
        try:
            manager = get_held_orders_manager()
            order = manager.get_order(order_id)
            
            if not order:
                return {"status": "error", "message": "Order not found"}, 404
            
            manager.cancel_order(order_id)
            
            logger.info(f"Cancelled held order {order_id}")
            return {
                "status": "ok",
                "message": "Order cancelled",
                "order": order.to_dict()
            }, 200
        
        except Exception as e:
            logger.exception(f"Error cancelling held order {order_id}")
            return {"status": "error", "message": str(e)}, 500
    
    
    @app.route("/held-orders/check", methods=["POST"])
    def check_held_orders():
        """
        Monitor held orders and trigger those whose conditions are met.
        
        This endpoint should be called periodically (e.g., every second or via WebSocket)
        to check if conditions are met and submit orders to IBKR.
        
        Request JSON (optional):
        {
            "symbol": "DGXX"  # optional - check only this symbol
        }
        """
        try:
            from config import Config
            cfg = Config()
            
            data = request.get_json() or {}
            symbol_filter = data.get("symbol", "").upper()
            
            manager = get_held_orders_manager()
            triggered_orders = []
            
            # Get all active orders to check
            active_orders = manager.orders.values()
            if symbol_filter:
                active_orders = [o for o in active_orders 
                               if o.symbol == symbol_filter and o.status == 'active']
            else:
                active_orders = [o for o in active_orders if o.status == 'active']
            
            logger.info(f"Checking {len(active_orders)} held orders for condition triggers")
            
            for held_order in active_orders:
                try:
                    # Skip if already executed
                    if held_order.entry_executed:
                        continue
                    
                    # Fetch market data for this symbol
                    ib = IBapi()
                    ib.connect("127.0.0.1", cfg.ibkr_api_port, 200 + int(time.time()) % 100)
                    
                    import threading
                    api_thread = threading.Thread(target=ib.run, daemon=True)
                    api_thread.start()
                    
                    # Wait for connection
                    waited = 0.0
                    while not isinstance(ib.nextOrderId, int) and waited < 3:
                        time.sleep(0.1)
                        waited += 0.1
                    
                    # Get market data (this would be via historical data request)
                    # For now, we'll just evaluate conditions if we can
                    market_data = {}  # Would be populated with actual market data
                    
                    # Evaluate entry conditions
                    conditions_met, reason = ConditionChecker.evaluate_order_conditions(held_order, market_data)
                    
                    if conditions_met:
                        logger.info(f"Held order {held_order.order_id} conditions MET: {reason}")
                        
                        # Build and submit order to IBKR
                        # This would call the /sendorders endpoint or use IBAPI directly
                        
                        # For now, mark as triggered
                        held_order.status = 'triggered'
                        held_order.modified_at = datetime.utcnow().isoformat()
                        
                        triggered_orders.append({
                            "order_id": held_order.order_id,
                            "symbol": held_order.symbol,
                            "reason": reason
                        })
                    
                    try:
                        ib.disconnect()
                    except:
                        pass
                
                except Exception as e:
                    logger.error(f"Error evaluating held order {held_order.order_id}: {e}")
                    continue
            
            return {
                "status": "ok",
                "checked": len(active_orders),
                "triggered": len(triggered_orders),
                "triggered_orders": triggered_orders
            }, 200
        
        except Exception as e:
            logger.exception("Error checking held orders")
            return {"status": "error", "message": str(e)}, 500
    
    
    @app.route("/held-orders/status", methods=["GET"])
    def held_orders_status():
        """Get summary status of all held orders."""
        try:
            manager = get_held_orders_manager()
            
            total = len(manager.orders)
            active = len([o for o in manager.orders.values() if o.status == 'active'])
            triggered = len([o for o in manager.orders.values() if o.status == 'triggered'])
            executed = len([o for o in manager.orders.values() if o.status == 'executed'])
            cancelled = len([o for o in manager.orders.values() if o.status == 'cancelled'])
            
            return {
                "status": "ok",
                "summary": {
                    "total": total,
                    "active": active,
                    "triggered": triggered,
                    "executed": executed,
                    "cancelled": cancelled
                }
            }, 200
        
        except Exception as e:
            logger.exception("Error getting held orders status")
            return {"status": "error", "message": str(e)}, 500
