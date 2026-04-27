# Multi-Level Order System - Implementation Guide

## Overview

The multi-level order system provides advanced order entry capabilities for IBKR trading, enabling traders to:

- **Execute multi-level entries**: Place different quantities at different price levels
- **Flexible price references**: Use technical indicators (VWAP, SMAs, EMAs, Fibonacci) as price anchors
- **Customized exits**: Different exit strategies per level (limit orders, trailing stops, etc.)
- **Preset management**: Save and load complete order strategies for quick deployment
- **Independent legs**: All levels are placed simultaneously as independent orders (not dependent on fills)

## Key Features

### 1. Price Reference Options

All entry, exit, and stop-loss levels can reference:

**Technical Indicators:**
- VWAP (Volume Weighted Average Price)
- SMA Fast (typically 5-period)
- SMA Medium (typically 10-period)
- SMA Slow (typically 20-period)
- EMA Fast (typically 5-period)
- EMA Slow (typically 10-period)
- Previous Close

**Fibonacci Levels:**
- 23.6% retracement
- 38.2% retracement
- 50.0% retracement
- 61.8% retracement
- 78.6% retracement

**Support/Resistance:**
- Support Level 1 (day low)
- Resistance Level 1 (day high)
- Day High
- Day Low

**Specialized:**
- Trailing Stop (dollar amount or %)
- Custom Price (exact price)

### 2. Order Type Options per Level

Each entry/exit/stop can be configured as:
- **Limit**: Traditional limit order
- **Market**: Market order (best execution)
- **Stop**: Stop order (triggered at price)
- **Trailing**: Trailing stop order

### 3. Offset Percentages

Apply percentage offsets to price references:
- Positive % = higher price (e.g., VWAP + 2%)
- Negative % = lower price (e.g., VWAP - 2%)

**Example configurations:**
```
Entry 1: VWAP - 2.0%      (buy on weakness)
Entry 2: Fibonacci 50% - 1.0%  (scale into pullback)

Exit 1: Fibonacci 61.8% + 1.0%  (natural resistance)
Exit 2: Trailing Stop at 0.50$  (capture larger moves)

Stop: Support Level 1 - 0.5%   (tight risk)
```

## Architecture

### Backend Components

#### `order_manager.py` (NEW)
- **`PriceReference`** dataclass: Represents a price reference with offset
- **`OrderLevel`** dataclass: Single level with entry/exit/stop configuration
- **`MultiLevelOrder`** dataclass: Complete multi-level order strategy
- **`PriceReferenceResolver`** class: Converts price references to actual prices using indicators
- **`OrderPresetManager`** class: Save/load/delete preset files

#### `ibkr_signal_engine.py` (UPDATED)
- **`multiLevelOrder()`** method: Creates multiple independent bracket orders from level configuration
  - Iterates through each level
  - Creates parent entry order + exit + stop for each
  - Sets transmit flag on last order only

#### `__init__.py` (UPDATED)
- **`/sendorders`** endpoint: Enhanced to detect and handle multi-level order requests
  - Checks `isMultiLevel=true` flag
  - Parses `multiLevelConfig` JSON
  - Routes to `IBAPI.multiLevelOrder()` method
  
- **New preset management routes:**
  - `POST /order-presets/save` - Save a preset
  - `GET /order-presets/list` - List all presets (optionally filtered by symbol)
  - `GET /order-presets/load/<filename>` - Load a specific preset
  - `DELETE /order-presets/delete/<filename>` - Delete a preset

### Frontend Components

#### `multi_level_order_modal.html` (NEW)
- Complete UI for building multi-level orders
- Dynamic level management (add/remove)
- Price reference selector with offset
- Preset manager with load/save/delete
- Summary view of configuration

#### JavaScript Functions
- **`mloAddLevel()`** - Add a new order level
- **`mloDeleteLevel(levelId)`** - Remove a level
- **`mloRenderLevelUI(level)`** - Render UI for a level
- **`mloUpdateLevel(levelId, field, value)`** - Update level configuration
- **`mloSavePreset()`** - Save current configuration as preset
- **`mloLoadPreset()`** - Load saved preset
- **`mloDeletePreset()`** - Delete a preset
- **`mloSubmitOrders()`** - Send orders to backend

## Usage Examples

### Example 1: Fibonacci Pullback Strategy

**Strategy**: Enter at two Fibonacci levels with different exits

```
Level 1: 
  - Quantity: 100 shares
  - Entry: VWAP - 2%
  - Exit: Fibonacci 61.8% + 1%
  - Stop: Support 1 - 0.5%

Level 2:
  - Quantity: 50 shares
  - Entry: Fibonacci 50% - 1%
  - Exit: Trailing Stop $0.50
  - Stop: Support 1 - 0.5%

Total Risk: ~$1.00 on 150 shares
```

### Example 2: VWAP Bounce Strategy

```
Level 1 (Primary):
  - Quantity: 200 shares
  - Entry: VWAP - 1%
  - Exit: SMA Slow + 0.5%
  - Stop: VWAP - 3%

Level 2 (Scale):
  - Quantity: 100 shares
  - Entry: VWAP - 4%
  - Exit: SMA Slow + 1%
  - Stop: VWAP - 5%
```

### Example 3: SMA Crossover with Trailing Exit

```
Level 1:
  - Quantity: 150 shares
  - Entry: SMA Fast > SMA Medium (trigger)
  - Entry Price: SMA Fast + 0.5%
  - Exit: Trailing Stop $1.00
  - Stop: SMA Slow - 0.5%
```

## How to Access

### Opening the Multi-Level Order Builder

1. In the modal dialog, click the **Multi-Level Order Builder** button (or use keyboard shortcut)
2. Or press `Ctrl+Alt+M` (configurable)
3. Or click from the order entry toolbar

### Building an Order

1. **Set basics**: Symbol, Action (BUY/SELL), TIF (DAY/GTC), Extended Hours
2. **Add levels**: Click "Add Level" button (starts with one)
3. **Configure each level**:
   - Set quantity
   - Choose entry price reference and offset %
   - Choose exit price reference and offset %
   - Choose stop-loss reference and offset %
   - Select order types (limit/market/stop/trailing)
4. **Save as preset** (optional):
   - Enter preset name
   - Click "Save" to save for future use
5. **Submit**: Click "Place Multi-Level Orders"

### Working with Presets

**Save a preset:**
1. Configure your order levels
2. Enter a name in "Preset name" field
3. Click "Save"
4. Preset is saved to `order_presets/` directory

**Load a preset:**
1. Click "Load Preset" dropdown
2. Select a saved preset
3. Click "Load"
4. Configuration is populated into the builder

**Delete a preset:**
1. Select preset from dropdown
2. Click "Delete"
3. Confirm deletion

## Data Flow

```
1. User builds order in Multi-Level Order Builder UI
   ↓
2. JavaScript collects level configurations
   ↓
3. POST /sendorders with:
   - tickerOrder: "AAPL"
   - isMultiLevel: "true"
   - multiLevelConfig: JSON string with levels
   ↓
4. Backend /sendorders route:
   - Detects isMultiLevel flag
   - Parses multiLevelConfig
   - Connects to IBKR
   ↓
5. Calls IBAPI.multiLevelOrder(order_spec)
   ↓
6. multiLevelOrder() iterates levels:
   - Creates entry order
   - Creates exit order (if price set)
   - Creates stop-loss order (if price/trailing set)
   ↓
7. All orders placed via IBAPI.placeOrder()
   ↓
8. Response sent back to frontend with order IDs
```

## JSON Structure for API

### Preset File Format
```json
{
  "name": "Fibonacci Reversal 2-Level",
  "symbol": "AAPL",
  "strategy_notes": "Two-level entry using Fibonacci pullback levels",
  "created_at": "2026-04-22T15:30:00.000000",
  "last_used": "2026-04-22T16:45:00.000000",
  "total_quantity": 150,
  "levels": [
    {
      "level_num": 1,
      "quantity": 100,
      "entry": {
        "type": "vwap",
        "offset_pct": -2.0,
        "order_type": "limit",
        "custom_price": null,
        "trailing_amount": null,
        "trailing_type": "amount"
      },
      "exit": {
        "type": "fibonacci_61.8",
        "offset_pct": 1.0,
        "order_type": "limit"
      },
      "stop_loss": {
        "type": "support_1",
        "offset_pct": -0.5,
        "order_type": "stop"
      },
      "notes": "Initial entry at VWAP support"
    }
  ]
}
```

### /sendorders Multi-Level Request
```json
{
  "tickerOrder": "AAPL",
  "longshort": "long",
  "tif": "DAY",
  "outsideRth": "regular",
  "isMultiLevel": "true",
  "multiLevelConfig": {
    "levels": [
      {
        "quantity": 100,
        "entry_price": null,
        "entry_type": "LMT",
        "exit_price": null,
        "stop_price": null,
        "use_trailing_stop": false,
        "trailing_amount": null,
        "trailing_type": "amount"
      }
    ]
  }
}
```

## Configuration

### order_presets Directory
- Location: `order_presets/` (relative to app root)
- Auto-created on first save
- Configurable via `config.ini`:
  ```ini
  [Flask]
  order_presets_dir = order_presets
  ```

### Indicator Parameters
- Uses existing indicator calculations from `ibkr_signal_engine.py`
- SMA periods: Fast (5), Medium (10), Slow (20)
- EMA periods: Fast (5), Slow (10)
- VWAP: Rolling calculation
- Fibonacci: Calculated from day high/previous close

## Limitations & Notes

### Current Limitations
1. **Price reference calculation**: Prices are calculated on order submission (not real-time tracking)
2. **Simultaneous placement**: All levels placed at once, not sequentially
3. **Static price references**: If market moves significantly before order placement, prices won't update
4. **No conditional orders**: Levels don't depend on previous level fills

### Future Enhancements
1. Real-time price calculation with market data updates
2. Sequential level placement (place level 2 only if level 1 fills)
3. Smart bracketing (share same stop-loss across levels)
4. Conditional order logic
5. Position sizing based on account equity
6. Risk/reward ratio visualization
7. Order modification after submission

## Troubleshooting

### Orders Not Placing
- Verify symbol is valid (check TWS/Gateway logs)
- Confirm IBKR connection is active
- Check order prices make sense (bid/ask spreads)

### Price References Not Calculating
- Ensure market data is flowing (check Data subscriptions in TWS)
- Fibonacci requires day high ≠ previous close
- Check logs for "Could not resolve price reference" messages

### Presets Not Loading
- Verify file exists in `order_presets/` directory
- Check file permissions
- Ensure JSON format is valid

## Integration with Auto-Orders

The multi-level order system can be integrated with the existing Auto-Order feature:
1. Create a multi-level preset
2. In Auto-Order settings, reference the preset name
3. When scan conditions trigger, apply preset configuration

(To be implemented in future enhancement)

## API Reference

### Frontend API

#### `mloInit()`
Initialize the multi-level order builder (called automatically when modal opens).

#### `mloAddLevel()`
Add a new order level with default configuration.

#### `mloDeleteLevel(levelId)`
Remove a level from the configuration.
- **levelId**: DOM element ID of level to delete

#### `mloUpdateLevel(levelId, field, value)`
Update a specific field in a level.
- **levelId**: Level DOM ID
- **field**: Field name ('quantity', 'entry_ref', 'entry_offset', etc.)
- **value**: New value

#### `mloSavePreset()`
Save current configuration as a named preset.

#### `mloLoadPreset()`
Load a selected preset from the dropdown.

#### `mloSubmitOrders()`
Validate and submit all configured levels to the backend.

### Backend API

#### POST `/order-presets/save`
```json
{
  "name": "Strategy Name",
  "symbol": "AAPL",
  "strategy_notes": "Optional notes",
  "levels": [...]
}
```

#### GET `/order-presets/list?symbol=AAPL`
Returns list of presets, optionally filtered by symbol.

#### GET `/order-presets/load/<filename>`
Returns full preset configuration.

#### DELETE `/order-presets/delete/<filename>`
Deletes a preset file.

## Files Modified/Created

### New Files
- `order_manager.py` - Order management classes and logic
- `templates/multi_level_order_modal.html` - UI modal and JavaScript

### Modified Files
- `ibkr_signal_engine.py` - Added `multiLevelOrder()` method
- `__init__.py` - Updated `/sendorders` endpoint + preset routes
- `templates/morfeo.html` - Included multi_level_order_modal.html

### Unchanged Files
- `indicators.py` - Used existing `FibonacciCalculator`
- `config.py` - Uses existing order_presets_dir config

## Performance Considerations

- Preset loading: O(1) to O(n) file operations
- Price calculation: O(1) for most indicators, O(n) for Fibonacci
- Order placement: Sequential (order by order to avoid rate limits)
- Typical placement time: 5-10 seconds for 6-9 orders

## Security Notes

1. Presets are stored as plain JSON files (no encryption)
2. File system permissions control access
3. Symbol and order types validated before submission
4. IBKR connection requires authentication

Consider restricting `order_presets/` directory permissions in production.
