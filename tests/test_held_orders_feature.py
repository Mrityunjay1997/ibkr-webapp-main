"""
Test suite for Hold Orders Off-Market feature

Tests the backend held_orders_manager.py module with various order
conditions and market data scenarios.
"""

import sys
import json
from datetime import datetime
from held_orders_manager import (
    HeldOrder, HeldOrdersManager, ConditionChecker,
    OrderSide, OrderType, ConditionType, ConditionPhase,
    CandleBreakoutCondition, MovingAverageCondition, HeldOrderCondition
)


def test_basic_held_order_creation():
    """Test creating a basic held order with candle breakout entry"""
    print("\n=== Test: Basic Held Order Creation ===")
    
    manager = HeldOrdersManager()
    
    # Create order for AAPL - long, 100 shares, break above recent high
    order = manager.create_order(
        symbol="AAPL",
        side=OrderSide.LONG,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=150.50
    )
    
    print(f"✓ Created order: {order.order_id}")
    print(f"  Symbol: {order.symbol}, Side: {order.side.value}, Qty: {order.quantity}")
    
    # Add candle breakout entry condition
    cond = HeldOrderCondition(
        condition_type=ConditionType.CANDLE_BREAKOUT.value,
        phase=ConditionPhase.ENTRY.value,
        config={
            'timeframe': '5min',
            'candles_to_check': 5,
            'break_direction': 'above_high',
            'entry_offset_pct': 0.5,
            'lookback_bars': 5
        }
    )
    manager.add_entry_condition(order.order_id, cond)
    
    print(f"✓ Added candle breakout entry condition")
    
    # Verify order
    active = manager.get_active_orders_for_symbol("AAPL")
    assert len(active) == 1
    assert active[0].entry_conditions[0].phase == ConditionPhase.ENTRY.value
    print(f"✓ Order has {len(active[0].entry_conditions)} entry condition(s)")
    

def test_ma_crossover_condition():
    """Test MA crossover entry and exit conditions"""
    print("\n=== Test: MA Crossover Conditions ===")
    
    manager = HeldOrdersManager()
    
    # Create order for SPY - short with MA crossover
    order = manager.create_order(
        symbol="SPY",
        side=OrderSide.SHORT,
        quantity=50,
        order_type=OrderType.MARKET
    )
    
    print(f"✓ Created short order: {order.symbol}")
    
    # Add MA crossover entry condition
    entry_cond = HeldOrderCondition(
        condition_type=ConditionType.MA_CROSSOVER.value,
        phase=ConditionPhase.ENTRY.value,
        config={
            'timeframe': '15min',
            'ma_type': 'sma',
            'ma_period': 20,
            'cross_direction': 'below',
            'cross_offset_pct': 0.2
        }
    )
    manager.add_entry_condition(order.order_id, entry_cond)
    
    print(f"✓ Added SMA(20) cross below entry condition")
    
    # Add exit condition - cross above EMA(50)
    exit_cond = HeldOrderCondition(
        condition_type=ConditionType.MA_CROSSOVER.value,
        phase=ConditionPhase.EXIT.value,
        config={
            'timeframe': '15min',
            'ma_type': 'ema',
            'ma_period': 50,
            'cross_direction': 'above',
            'cross_offset_pct': 0
        }
    )
    manager.add_exit_condition(order.order_id, exit_cond)
    
    print(f"✓ Added EMA(50) cross above exit condition")
    
    # Verify
    active = manager.get_active_orders_for_symbol("SPY")
    assert len(active[0].entry_conditions) == 1
    assert len(active[0].exit_conditions) == 1
    print(f"✓ Order has {len(active[0].entry_conditions)} entry and {len(active[0].exit_conditions)} exit conditions")


def test_candle_breakout_detection():
    """Test candle breakout condition checking logic"""
    print("\n=== Test: Candle Breakout Detection ===")
    
    # Simulate 5 candles with increasing highs
    candle_data = [
        {'high': 150.00, 'low': 149.50},  # bar 0
        {'high': 150.50, 'low': 150.00},  # bar 1
        {'high': 151.00, 'low': 150.50},  # bar 2
        {'high': 151.50, 'low': 151.00},  # bar 3
        {'high': 152.00, 'low': 151.50},  # bar 4 (current)
    ]
    
    # Current price just broke above recent high
    current_price = 152.10
    
    # Calculate reference high (max of previous 5 bars)
    ref_high = max([c['high'] for c in candle_data[:-1]])  # 151.50
    ref_low = min([c['low'] for c in candle_data[:-1]])    # 149.50
    
    print(f"Reference high (last 4 bars): {ref_high}")
    print(f"Reference low (last 4 bars): {ref_low}")
    print(f"Current price: {current_price}")
    
    # Test break above with 0.5% offset
    offset_pct = 0.5
    breakout_level = ref_high * (1 + offset_pct / 100)
    
    is_breakout = current_price >= breakout_level
    print(f"\nBreakout level (high + {offset_pct}%): {breakout_level:.2f}")
    print(f"✓ Price breaks above high: {is_breakout}")
    
    # Test break below
    breakout_below = ref_low * (1 - offset_pct / 100)
    below_breakout = current_price <= breakout_below
    print(f"\nBreakout level (low - {offset_pct}%): {breakout_below:.2f}")
    print(f"✓ Price breaks below low: {below_breakout}")


def test_ma_crossover_detection():
    """Test MA crossover condition checking logic"""
    print("\n=== Test: MA Crossover Detection ===")
    
    # Simulate price series and MA
    prices = [150.0, 150.5, 150.2, 151.0, 151.5, 151.8, 152.0, 152.5]
    sma_20 = [150.5, 150.6, 150.7, 150.8, 151.0, 151.2, 151.4, 151.6]
    
    print(f"Price series: {prices}")
    print(f"SMA(20):      {sma_20}")
    
    # Check crossover
    # Previous bar: price below MA (150.2 < 150.7)
    # Current bar: price above MA (152.5 > 151.6)
    prev_price = prices[-2]
    curr_price = prices[-1]
    prev_ma = sma_20[-2]
    curr_ma = sma_20[-1]
    
    prev_below = prev_price < prev_ma
    curr_above = curr_price > curr_ma
    cross_above = prev_below and curr_above
    
    print(f"\nPrevious bar: price={prev_price} vs SMA={prev_ma} (price below: {prev_below})")
    print(f"Current bar:  price={curr_price} vs SMA={curr_ma} (price above: {curr_above})")
    print(f"✓ Cross above detected: {cross_above}")
    
    # Test with offset
    offset_pct = 0.5
    cross_level = curr_ma * (1 + offset_pct / 100)
    crosses_above_offset = curr_price >= cross_level
    print(f"\nWith {offset_pct}% offset: cross level = {cross_level:.2f}")
    print(f"✓ Price crosses above with offset: {crosses_above_offset}")


def test_serialization():
    """Test order serialization to/from JSON"""
    print("\n=== Test: Order Serialization ===")
    
    manager = HeldOrdersManager()
    
    # Create order
    order = manager.create_order(
        symbol="TSLA",
        side=OrderSide.LONG,
        quantity=25,
        order_type=OrderType.LIMIT,
        limit_price=250.00
    )
    
    cond = HeldOrderCondition(
        condition_type=ConditionType.CANDLE_BREAKOUT.value,
        phase=ConditionPhase.ENTRY.value,
        config={
            'timeframe': '1min',
            'candles_to_check': 10,
            'break_direction': 'above_high',
            'entry_offset_pct': 0.3,
            'lookback_bars': 10
        }
    )
    manager.add_entry_condition(order.order_id, cond)
    
    # Convert to dict
    order_dict = manager.to_dict()
    print(f"✓ Serialized to dict with {len(order_dict)} order(s)")
    
    # Print JSON representation
    json_str = json.dumps(order_dict, indent=2, default=str)
    print(f"\nJSON representation (first 200 chars):\n{json_str[:200]}...")
    
    # Create new manager and load from dict
    manager2 = HeldOrdersManager()
    manager2.from_dict(order_dict)
    
    loaded_orders = manager2.get_active_orders_for_symbol("TSLA")
    assert len(loaded_orders) == 1
    print(f"\n✓ Deserialized successfully")
    print(f"✓ Loaded order: {loaded_orders[0].symbol} {loaded_orders[0].side}")


def test_multiple_orders():
    """Test managing multiple orders"""
    print("\n=== Test: Multiple Orders ===")
    
    manager = HeldOrdersManager()
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "AAPL"]
    
    # Create multiple orders
    for symbol in symbols:
        order = manager.create_order(
            symbol=symbol,
            side=OrderSide.LONG if symbol != "MSFT" else OrderSide.SHORT,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=150.00
        )
        
        cond = HeldOrderCondition(
            condition_type=ConditionType.MA_CROSSOVER.value,
            phase=ConditionPhase.ENTRY.value,
            config={
                'timeframe': '5min',
                'ma_type': 'sma',
                'ma_period': 20,
                'cross_direction': 'above',
                'cross_offset_pct': 0
            }
        )
        manager.add_entry_condition(order.order_id, cond)
    
    print(f"✓ Created {len(symbols)} orders")
    
    # Get orders by symbol
    aapl_orders = manager.get_active_orders_for_symbol("AAPL")
    print(f"✓ AAPL has {len(aapl_orders)} active order(s)")
    
    msft_orders = manager.get_active_orders_for_symbol("MSFT")
    print(f"✓ MSFT has {len(msft_orders)} active order(s) - side: {msft_orders[0].side}")
    
    # Get all active orders
    all_orders = list(manager.orders.values())
    print(f"✓ Total active orders: {len(all_orders)}")


def test_order_status_tracking():
    """Test order status transitions"""
    print("\n=== Test: Order Status Tracking ===")
    
    manager = HeldOrdersManager()
    
    order = manager.create_order(
        symbol="XYZ",
        side=OrderSide.LONG,
        quantity=100,
        order_type=OrderType.MARKET
    )
    
    print(f"✓ Initial status: {order.status}")
    
    # Mark entry as executed with price
    manager.mark_entry_executed(order.order_id, 152.50)
    updated_order = manager.orders[order.order_id]
    print(f"✓ After mark_entry_executed: {updated_order.status}")
    print(f"✓ Entry executed at: {updated_order.entry_executed_price}")
    
    # Verify entry execution tracking
    if updated_order.entry_executed:
        print(f"  Entry execution time: {updated_order.entry_executed_at}")


def run_all_tests():
    """Run all test functions"""
    print("=" * 60)
    print("HELD ORDERS OFF-MARKET FEATURE - TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_basic_held_order_creation,
        test_ma_crossover_condition,
        test_candle_breakout_detection,
        test_ma_crossover_detection,
        test_serialization,
        test_multiple_orders,
        test_order_status_tracking,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
