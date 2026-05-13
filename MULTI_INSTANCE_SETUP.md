# Multi-Instance & Multi-Tab Setup Guide

## Overview

The IBKR WebApp has been restored to support **running multiple independent instances simultaneously** with different trading setups and configurations. This document explains how the feature works and how to use it effectively.

### What Changed

The application now tracks background scanners and Top 50 scanners on a **per-tab basis** instead of globally. This means:

- ✅ **Multiple browser tabs can run different scanners concurrently**
- ✅ **Each tab maintains its own configuration independently**
- ✅ **No conflicts between different setup instances**
- ✅ **Each tab gets isolated results and status tracking**

---

## How It Works

### Tab Unique Identification

Each browser tab gets its own **unique tab ID** automatically when the page loads:

```javascript
const _bg_unique_id = Date.now() + "_" + Math.floor(Math.random() * 1000000);
const _sl_unique_id = Date.now() + "_sl_" + Math.floor(Math.random() * 1000000);
```

This ID is included in all requests to the background scanner and Top 50 scanner endpoints:

- **Background Scanner**: Uses `_bg_unique_id` (e.g., `1620000000000_123456`)
- **Top 50 Scanner**: Uses `_sl_unique_id` (e.g., `1620000000000_sl_123456`)

### Server-Side Management

On the server (Python/Flask), scanners are now stored in per-tab dictionaries:

```python
_background_scanners = {}           # dict[tab_unique_id] = BackgroundScanner()
_bg_top50_scanners = {}             # dict[tab_unique_id] = BackgroundTop50Scanner()
```

When a tab requests to start a scanner:
1. Server checks if a scanner exists for that tab ID
2. If not, creates a new scanner instance
3. Each tab's scanner runs independently
4. Results are isolated per tab

---

## Using Multiple Instances

### Scenario 1: Two Different Trading Strategies

**Tab 1: Growth Stocks Scanner**
1. Open the app in Tab 1
2. Configure your growth stock indicators in the form
3. Run the screening once to populate results
4. Click "Start" on the Background Scanner
5. Set interval (e.g., every 5 minutes)

**Tab 2: Value Stocks Scanner**
1. Open the app in Tab 2 (new tab, same URL)
2. Configure different value stock indicators
3. Run the screening once
4. Click "Start" on the Background Scanner
5. Set different interval (e.g., every 10 minutes)

**Result**: Both tabs run their scanners simultaneously with different configurations and results.

### Scenario 2: Using Top 50 Scanner with Custom Stock List

**Tab 1: Top 50 Gainers (Automated)**
1. Open app in Tab 1
2. Configure your indicators
3. Set up Top 50 Scanner Loop with scan code = "TOP_PERC_GAIN"
4. Click "Start Scanner Loop"

**Tab 2: Custom Watchlist (Manual)**
1. Open app in Tab 2
2. Use Stock List Management to add your custom tickers
3. Configure indicators
4. Set up Top 50 Scanner Loop (will use custom list instead of Top 50)
5. Click "Start Scanner Loop"

**Result**: One tab automatically screens Top 50, the other screens your custom list.

### Scenario 3: Different Order Presets

**Tab 1: Aggressive Trading**
1. Open app in Tab 1
2. Load aggressive order preset
3. Configure fast indicators (short timeframes)
4. Run scanner, start monitoring

**Tab 2: Conservative Trading**
1. Open app in Tab 2
2. Load conservative order preset
3. Configure slow indicators (long timeframes)
4. Run scanner, start monitoring

---

## Technical Details

### Modified Routes

All scanner endpoints now support per-tab operations:

#### Background Scanner Endpoints

```
POST /background/start
  Payload: {
    "tab_unique_id": "string",      # REQUIRED - tab identifier
    "value": number,
    "unit": "seconds|minutes|hours",
    "form": {...},                  # your indicator settings
    "securities": {...}             # tickers/cusips to scan
  }

POST /background/stop
  Payload: {
    "tab_unique_id": "string"       # REQUIRED - identifies which tab's scanner to stop
  }

GET /background/status?tab_unique_id=...
  Returns: status of scanner for that specific tab

GET /background/results?tab_unique_id=...
  Returns: latest results for that tab's scanner only
```

#### Top 50 Scanner Endpoints

```
POST /scanner-loop/start
  Payload: {
    "tab_unique_id": "string",      # REQUIRED
    "value": number,
    "unit": "seconds|minutes|hours",
    "form": {...},
    "scanner_params": {...}         # scan_code, min_price, min_volume
  }

POST /scanner-loop/stop
  Payload: {
    "tab_unique_id": "string"       # REQUIRED
  }

GET /scanner-loop/status?tab_unique_id=...
  Returns: status for that tab's Top 50 scanner

GET /scanner-loop/results?tab_unique_id=...
  Returns: results for that tab's Top 50 scanner only
```

### JavaScript Integration

The HTML template includes automatic tab ID generation and passes it to all endpoints:

```javascript
// Generated automatically on page load
const _bg_unique_id = Date.now() + "_" + Math.floor(Math.random() * 1000000);
const _sl_unique_id = Date.now() + "_sl_" + Math.floor(Math.random() * 1000000);

// Included in all AJAX requests
$.ajax({
  url: "/background/start",
  type: "POST",
  data: JSON.stringify({
    tab_unique_id: _bg_unique_id,  // ← automatically included
    value: 5,
    unit: "minutes",
    form: {...},
    securities: {...}
  })
});
```

---

## Limitations & Considerations

### 1. **Browser Tabs vs. Browser Windows**
- Each tab gets its own unique ID
- Different browser windows are also treated as separate tabs (they each get their own ID)
- This is by design - each tab has independent state

### 2. **Page Reloads**
- Reloading a tab **loses the current tab's scanner state**
- A new unique ID is generated on reload
- The server continues running the old scanner (if it's still running)
- You'll need to restart the scanner after a page reload

### 3. **Memory Usage**
- Each active tab's scanner creates its own IBAPI connection
- Running many concurrent scanners will use more memory and API connections
- Recommended: 2-3 concurrent scanners maximum (depending on system resources)

### 4. **IBKR API Connections**
- Each scanner uses a separate IBKR API connection
- Default client IDs: `100000-199999` (Top 50), `300-399` (background), `1-99` (manual requests)
- Make sure your IBKR TWS/Gateway can handle multiple concurrent connections

### 5. **Closing Tabs**
- Closing a tab **does NOT automatically stop** its scanner
- The scanner continues running on the server until:
  - Client heartbeat timeout (default: 1-4 minutes of inactivity)
  - Tab explicitly clicks "Stop"
- You can restart the tab and reconnect to the same running scanner

---

## Troubleshooting

### **Issue: Scanner won't start in a new tab**
- **Cause**: Previous tab's scanner already using that unique ID (very unlikely due to randomization)
- **Solution**: Refresh the page to generate a new tab ID

### **Issue: Changes in one tab affect another**
- **Cause**: This shouldn't happen with the new implementation
- **Solution**: Verify both tabs are sending different `tab_unique_id` values in their requests
  - Check browser DevTools → Network tab → look at request payloads

### **Issue: Scanner stops after a few minutes**
- **Cause**: Client heartbeat timeout triggered (no polling for results)
- **Solution**: Keep the browser tab in focus or polling results frequently
  - Background polling continues every 15 seconds by default

### **Issue: IBKR API connection errors**
- **Cause**: Too many concurrent connections or connection conflicts
- **Solution**: 
  - Reduce number of concurrent tabs
  - Check IBKR TWS/Gateway settings for connection limits
  - Ensure API port is set correctly (default: 7496 live, 7497 paper)

### **Issue: High memory usage**
- **Cause**: Multiple scanners creating persistent IBAPI connections
- **Solution**:
  - Stop scanners not in use
  - Reduce polling frequency (increase poll interval)
  - Monitor memory with Task Manager

---

## Best Practices

### 1. **Organization**
- Use a consistent naming convention for setups (e.g., "Strategy-1", "Strategy-2")
- Save your setups frequently for different strategies
- Use comments in indicator settings to describe the strategy

### 2. **Configuration Management**
- One browser window for each major strategy
- Each window has multiple tabs for variations
- Save different order presets for each strategy

### 3. **Monitoring**
- Keep status display visible (scroll to scanner section)
- Monitor the "Last Run" and "Results" sections
- Check for warnings/errors in the summary

### 4. **Resource Management**
- Limit to 2-3 concurrent scanners for optimal performance
- Close tabs when not actively trading that strategy
- Periodic server restart if running for extended periods (optional)

---

## API Reference

### Helper Functions (Server-side)

```python
# Get or create scanner for a tab
scanner = _get_or_create_background_scanner(tab_unique_id)

# Get existing scanner without creating
scanner = _get_background_scanner(tab_unique_id)

# Remove scanner after stopping
_remove_background_scanner(tab_unique_id)

# Same pattern for Top 50 scanner
_get_or_create_top50_scanner(tab_unique_id)
_get_top50_scanner(tab_unique_id)
_remove_top50_scanner(tab_unique_id)
```

### Response Format

All endpoints return JSON responses with `tab_id` field for tracking:

```json
{
  "status": "started|stopped|running",
  "interval_seconds": 300,
  "tab_id": "1620000000000_123456",
  "enabled": true,
  "results": {...},
  "warning": {...},
  "beep": false
}
```

---

## Version History

### Version 1.0 (Current)
- ✅ Per-tab background scanner instances
- ✅ Per-tab Top 50 scanner instances  
- ✅ Automatic tab ID generation
- ✅ Isolated results per tab
- ✅ Backward compatible client heartbeat

---

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review browser console for JavaScript errors (F12 → Console)
3. Check server logs for API errors
4. Verify IBKR API connection status
