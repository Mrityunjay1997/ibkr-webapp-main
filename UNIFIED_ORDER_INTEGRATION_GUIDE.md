# Unified Order System - Integration Guide

**Date**: May 13, 2026

This guide explains how to integrate the new Unified Order System into your existing Flask web application without losing existing functionality.

---

## Phase 1: Parallel Integration (Non-Breaking)

In Phase 1, the new system runs **alongside** your existing off-book, automated, and manual order systems. No existing code is changed.

### Step 1: Enable New Modules

1. Copy these files to your project root:
   - `unified_order_constants.py`
   - `unified_order_model.py`
   - `price_resolver.py`
   - `share_calculator.py`
   - `session_handler.py`
   - `unified_order_manager.py`

2. Add to your Flask app (`__init__.py` or main app file):

```python
from unified_order_manager import UnifiedOrderManager

# Initialize unified order manager
unified_order_manager = UnifiedOrderManager(
    storage_dir='./orders/unified'  # Directory for persisting orders
)

# Load existing orders from disk if any
unified_order_manager.load_all_from_disk()
```

### Step 2: Add Flask Routes

Add these routes to your Flask app to expose the new system:

```python
from flask import Blueprint, request, jsonify
from unified_order_model import UnifiedOrderConfig, EntryConditionConfig, TargetConfig, StopLossConfig
from price_resolver import PriceResolutionContext

unified_bp = Blueprint('unified_orders', __name__, url_prefix='/api/unified')

# =========================================================================
# CREATE ORDERS
# =========================================================================

@unified_bp.route('/orders/offbook', methods=['POST'])
def create_offbook():
    """Create off-book (condition-based) order"""
    data = request.json
    
    entry = EntryConditionConfig(**data.get('entry', {}))
    stop = StopLossConfig(**data.get('stop', {})) if data.get('stop') else None
    
    success, result = unified_order_manager.create_offbook_order(
        symbol=data['symbol'],
        side=data.get('side', 'long'),
        quantity=int(data.get('quantity', 100)),
        entry_condition=entry,
        stop_loss=stop,
        notes=data.get('notes', ''),
    )
    
    if success:
        return jsonify({'status': 'success', 'order_id': result}), 201
    else:
        return jsonify({'status': 'error', 'message': result}), 400


@unified_bp.route('/orders/automated', methods=['POST'])
def create_automated():
    """Create automated (multi-level) order"""
    data = request.json
    
    entry = EntryConditionConfig(**data.get('entry', {}))
    stop = StopLossConfig(**data.get('stop', {})) if data.get('stop') else None
    targets = [TargetConfig(**t) for t in data.get('targets', [])]
    
    success, result = unified_order_manager.create_automated_order(
        symbol=data['symbol'],
        side=data.get('side', 'long'),
        entry=entry,
        targets=targets,
        stop_loss=stop,
        quantity=int(data.get('quantity', 100)),
        notes=data.get('notes', ''),
    )
    
    if success:
        return jsonify({'status': 'success', 'order_id': result}), 201
    else:
        return jsonify({'status': 'error', 'message': result}), 400


@unified_bp.route('/orders/manual', methods=['POST'])
def create_manual():
    """Create manual order"""
    data = request.json
    
    target = TargetConfig(**data.get('target', {})) if data.get('target') else None
    stop = StopLossConfig(**data.get('stop', {})) if data.get('stop') else None
    
    success, result = unified_order_manager.create_manual_order(
        symbol=data['symbol'],
        side=data.get('side', 'long'),
        quantity=int(data['quantity']),
        entry_price=float(data['entry_price']),
        profit_target=target,
        stop_loss=stop,
        notes=data.get('notes', ''),
    )
    
    if success:
        return jsonify({'status': 'success', 'order_id': result}), 201
    else:
        return jsonify({'status': 'error', 'message': result}), 400


# =========================================================================
# RETRIEVE ORDERS
# =========================================================================

@unified_bp.route('/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get order by ID"""
    order = unified_order_manager.get_order(order_id)
    if not order:
        return jsonify({'status': 'error', 'message': 'Order not found'}), 404
    
    return jsonify({'status': 'success', 'order': order.to_dict()}), 200


@unified_bp.route('/orders/symbol/<symbol>', methods=['GET'])
def get_orders_by_symbol(symbol):
    """Get all orders for a symbol"""
    status = request.args.get('status')
    orders = unified_order_manager.get_orders_by_symbol(symbol, status)
    
    return jsonify({
        'status': 'success',
        'count': len(orders),
        'orders': [o.to_dict() for o in orders]
    }), 200


@unified_bp.route('/orders/mode/<mode>', methods=['GET'])
def get_orders_by_mode(mode):
    """Get all orders of a specific mode"""
    status = request.args.get('status')
    orders = unified_order_manager.get_orders_by_mode(mode, status)
    
    return jsonify({
        'status': 'success',
        'count': len(orders),
        'orders': [o.to_dict() for o in orders]
    }), 200


@unified_bp.route('/orders/pending', methods=['GET'])
def get_pending_orders():
    """Get all pending orders"""
    orders = unified_order_manager.get_pending_orders()
    
    return jsonify({
        'status': 'success',
        'count': len(orders),
        'orders': [o.to_dict() for o in orders]
    }), 200


@unified_bp.route('/orders/active', methods=['GET'])
def get_active_orders():
    """Get all active orders"""
    orders = unified_order_manager.get_active_orders()
    
    return jsonify({
        'status': 'success',
        'count': len(orders),
        'orders': [o.to_dict() for o in orders]
    }), 200


# =========================================================================
# PREPARE & SUBMIT ORDERS
# =========================================================================

@unified_bp.route('/orders/<order_id>/prepare', methods=['POST'])
def prepare_order(order_id):
    """Prepare order for submission"""
    order = unified_order_manager.get_order(order_id)
    if not order:
        return jsonify({'status': 'error', 'message': 'Order not found'}), 404
    
    data = request.json or {}
    
    # Build price context from request
    context = PriceResolutionContext()
    context.current_price = float(data.get('current_price', 0))
    context.bid = float(data.get('bid', context.current_price))
    context.ask = float(data.get('ask', context.current_price))
    context.prev_close = float(data.get('prev_close', context.current_price))
    context.day_high = float(data.get('day_high', context.current_price))
    context.day_low = float(data.get('day_low', context.current_price))
    context.vwap = float(data.get('vwap', context.current_price))
    context.sma_fast = float(data.get('sma_fast', context.current_price))
    context.atr = float(data.get('atr', 1.0))
    # ... add other indicators as needed
    
    success, warnings = unified_order_manager.prepare_for_submission(
        order=order,
        price_context=context,
        current_price=float(data.get('current_price', 0)),
        account_size=float(data.get('account_size', 100000.0)),
    )
    
    if success:
        return jsonify({
            'status': 'success',
            'order': order.to_dict(),
            'warnings': warnings,
        }), 200
    else:
        return jsonify({'status': 'error', 'warnings': warnings}), 400


@unified_bp.route('/orders/<order_id>/submit', methods=['POST'])
def submit_order_route(order_id):
    """Submit order to backend"""
    order = unified_order_manager.get_order(order_id)
    if not order:
        return jsonify({'status': 'error', 'message': 'Order not found'}), 404
    
    success, msg = unified_order_manager.submit_order(order)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'Order submitted',
            'order_id': msg,
        }), 200
    else:
        return jsonify({'status': 'error', 'message': msg}), 400


# =========================================================================
# STATISTICS
# =========================================================================

@unified_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get order statistics"""
    stats = unified_order_manager.get_statistics()
    return jsonify({'status': 'success', 'statistics': stats}), 200


# Register blueprint
app.register_blueprint(unified_bp)
```

### Step 3: Add Frontend Integration (HTML/JavaScript)

Update `templates/multi_level_order_modal.html` to use the new API:

```javascript
// New function to create unified order
async function createUnifiedOrder(mode) {
    // mode = 'offbook', 'automated', or 'manual'
    
    const orderData = buildOrderDataFromForm();  // Your existing function
    
    const endpoint = `/api/unified/orders/${mode}`;
    
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData),
    });
    
    const result = await response.json();
    
    if (result.status === 'success') {
        alert(`✓ Order created: ${result.order_id}`);
        
        // Prepare for submission
        const prepareResponse = await fetch(
            `/api/unified/orders/${result.order_id}/prepare`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_price: getCurrentPrice(),
                    account_size: 100000,  // Your account
                    // ... add more market data
                }),
            }
        );
        
        const prepareResult = await prepareResponse.json();
        
        if (prepareResult.warnings && prepareResult.warnings.length > 0) {
            console.warn('Warnings:', prepareResult.warnings);
        }
        
        // Submit
        const submitResponse = await fetch(
            `/api/unified/orders/${result.order_id}/submit`,
            { method: 'POST' }
        );
        
        const submitResult = await submitResponse.json();
        if (submitResult.status === 'success') {
            alert('✓ Order submitted!');
        } else {
            alert(`✗ Submission failed: ${submitResult.message}`);
        }
    } else {
        alert(`✗ Error: ${result.message}`);
    }
}

// Call from your existing form submission
document.getElementById('submitOrderBtn').addEventListener('click', () => {
    const mode = document.getElementById('orderMode').value;  // offbook, automated, manual
    createUnifiedOrder(mode);
});
```

---

## Phase 2: Gradual Migration (6+ weeks)

Once Phase 1 is stable, gradually migrate existing systems:

### Week 1-2: Off-Book Orders

Update `held_orders_manager.py` to use `UnifiedOrderConfig` internally:

```python
from unified_order_model import UnifiedOrderConfig

class HeldOrdersManager:
    def __init__(self):
        self.unified_manager = unified_order_manager
    
    def create_order_legacy(self, ...):
        """Legacy API - creates UnifiedOrderConfig internally"""
        order = UnifiedOrderConfig(mode='offbook', ...)
        return self.unified_manager.register_order(order)
```

### Week 3-4: Automated Orders

Update `order_manager.py` to generate `UnifiedOrderConfig`:

```python
def multiLevelOrderAdvanced(symbol, levels, ...):
    """Convert legacy format to UnifiedOrderConfig"""
    order = UnifiedOrderConfig(
        mode='automated',
        symbol=symbol,
        ...
    )
    return unified_order_manager.submit_order(order)
```

### Week 5-6: Manual Orders

Update form processing to create `UnifiedOrderConfig`:

```python
@app.route('/sendorders', methods=['POST'])
def send_orders():
    """Updated to use unified system"""
    form = request.json
    
    order = UnifiedOrderConfig(
        mode='manual',
        symbol=form['symbol'],
        ...
    )
    
    return unified_order_manager.submit_order(order)
```

---

## Backward Compatibility

**Your existing code continues to work:**

```python
# Old way still works
held_order_manager.create_order(...)
multiLevelOrderAdvanced(...)
send_orders()

# New way also works
unified_order_manager.create_offbook_order(...)
unified_order_manager.create_automated_order(...)
unified_order_manager.create_manual_order(...)
```

Both systems can coexist during transition.

---

## API Endpoint Examples

### Create Off-Book Order

```bash
curl -X POST http://localhost:5000/api/unified/orders/offbook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "side": "long",
    "quantity": 100,
    "entry": {
      "condition_type": "candle_breakout",
      "candle_timeframe": "15min",
      "candle_lookback": 5,
      "candle_break_direction": "above_high"
    },
    "stop": {
      "stop_type": "fixed_price",
      "fixed_price": 150.00
    }
  }'
```

### Create Automated Multi-Level Order

```bash
curl -X POST http://localhost:5000/api/unified/orders/automated \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "side": "long",
    "quantity": 100,
    "entry": {
      "condition_type": "immediate",
      "indicator_type": "vwap",
      "indicator_offset_pct": -0.5
    },
    "targets": [
      {
        "target_type": "fibonacci",
        "fib_level": "fibonacci_61_8",
        "percent_of_position": 50.0
      },
      {
        "target_type": "percent_gain",
        "gain_percent": 10.0,
        "percent_of_position": 50.0
      }
    ],
    "stop": {
      "stop_type": "atr_multiple",
      "atr_multiplier": 1.5
    }
  }'
```

### Create Manual Order

```bash
curl -X POST http://localhost:5000/api/unified/orders/manual \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "MSFT",
    "side": "long",
    "quantity": 50,
    "entry_price": 380.50,
    "target": {
      "target_type": "percent_gain",
      "gain_percent": 5.0,
      "percent_of_position": 100.0
    },
    "stop": {
      "stop_type": "percent_loss",
      "loss_percent": 2.0
    }
  }'
```

### Prepare Order

```bash
curl -X POST http://localhost:5000/api/unified/orders/ABC123/prepare \
  -H "Content-Type: application/json" \
  -d '{
    "current_price": 150.25,
    "bid": 150.23,
    "ask": 150.27,
    "prev_close": 150.10,
    "day_high": 151.00,
    "day_low": 149.50,
    "vwap": 150.15,
    "sma_fast": 150.05,
    "atr": 1.50,
    "account_size": 100000.0
  }'
```

### Submit Order

```bash
curl -X POST http://localhost:5000/api/unified/orders/ABC123/submit
```

---

## Data Migration

If you have existing orders you want to migrate:

```python
# Convert old HeldOrder to UnifiedOrderConfig
from unified_order_model import UnifiedOrderConfig, EntryConditionConfig

def migrate_held_order(old_held_order):
    entry = EntryConditionConfig(**old_held_order.entry_conditions[0].config)
    
    order = UnifiedOrderConfig(
        mode='offbook',
        symbol=old_held_order.symbol,
        side=old_held_order.side,
        quantity=old_held_order.quantity,
        entry=entry,
    )
    
    return unified_order_manager.register_order(order)

# Migrate all existing orders
for old_order in held_orders_manager.orders.values():
    migrate_held_order(old_order)
```

---

## Testing

### Unit Tests

```python
import pytest
from unified_order_manager import UnifiedOrderManager
from unified_order_model import UnifiedOrderConfig

def test_create_offbook_order():
    manager = UnifiedOrderManager()
    
    entry = EntryConditionConfig(...)
    success, order_id = manager.create_offbook_order(
        'AAPL', 'long', 100, entry
    )
    
    assert success
    assert order_id
    
    order = manager.get_order(order_id)
    assert order.symbol == 'AAPL'
    assert order.status == 'pending'

# ... more tests
```

### Integration Tests

```python
def test_end_to_end_order_flow():
    # Create → Prepare → Submit flow
    manager = UnifiedOrderManager()
    
    # Create
    success, order_id = manager.create_manual_order(...)
    assert success
    
    # Prepare
    context = PriceResolutionContext()
    context.current_price = 100.00
    success, warnings = manager.prepare_for_submission(
        manager.get_order(order_id),
        context,
        100.00,
    )
    assert success
    
    # Submit
    success, msg = manager.submit_order(manager.get_order(order_id))
    assert success
```

---

## Monitoring & Debugging

### Enable Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('unified_order_manager')
logger.setLevel(logging.DEBUG)
```

### Check Order Status

```python
# Get statistics
stats = unified_order_manager.get_statistics()
print(f"Total orders: {stats['total_orders']}")
print(f"By mode: {stats['by_mode']}")
print(f"By status: {stats['by_status']}")

# Find orders
pending = unified_order_manager.get_pending_orders()
active = unified_order_manager.get_active_orders()
```

### Debug Price Calculation

```python
from price_resolver import PriceResolver

context = PriceResolutionContext()
context.current_price = 150.00
context.vwap = 150.15

price, error = PriceResolver.resolve_price(
    'vwap', -0.5, context
)

if error:
    print(f"Error: {error}")
else:
    print(f"Resolved price: {price}")
```

---

## Deployment Checklist

- [ ] Copy 6 new Python modules to project root
- [ ] Add imports to Flask app `__init__.py`
- [ ] Initialize UnifiedOrderManager
- [ ] Add Flask blueprint routes
- [ ] Update frontend JavaScript
- [ ] Test with sample orders
- [ ] Monitor for errors
- [ ] Gradually migrate existing orders
- [ ] Switch default order creation to unified system
- [ ] Deprecate old order systems (weeks 6+)

---

## Support

For issues or questions:

1. Check logs: `logs/unified_order_manager.log`
2. Review error messages in API responses
3. Validate order configuration with `order.validate()`
4. Check market data context completeness
5. Review integration guide above

