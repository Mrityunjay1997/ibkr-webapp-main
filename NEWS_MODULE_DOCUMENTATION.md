# News Module Documentation

## Overview

The News Module is an integrated component of the IBKR Trading Webapp that fetches, filters, and processes financial news headlines based on scanner results and user-defined keywords. It supports text-to-speech (TTS) functionality to read headlines aloud and provides a dedicated interface for monitoring news feeds.

---

## Architecture & Components

### 1. **File Structure**

```
news/
├── __init__.py          # Package initialization
├── routes.py            # News utility functions and Flask route registration
├── utils.py             # Date/time parsing and filtering logic
└── fix_article.py       # Article text cleaning utilities
```

### 2. **Key Components**

| Component | Location | Purpose |
|-----------|----------|---------|
| **Routes & Filters** | [news/routes.py](news/routes.py) | Keyword filtering, news signal evaluation, Flask route registration |
| **Date/Time Utils** | [news/utils.py](news/utils.py) | Parse timestamps, calculate time windows, filter headlines by date range |
| **Form Configuration** | [forms.py](forms.py#L922-L970) | News-related form fields and settings |
| **Signal Engine** | [scanner/ibkr_signal_engine.py](scanner/ibkr_signal_engine.py) | Integration with scanner logic, news evaluation |
| **Templates** | [templates/news_reader.html](templates/news_reader.html) | Dedicated news reader UI |

---

## How the News Module Works

### Data Flow

```
Scanner Results
    ↓
Check if news is needed (news_enabled or has_keywords)
    ↓
Fetch headlines from IBKR API (if enabled)
    ↓
Filter by keywords (if specified)
    ↓
Filter by time window (if specified)
    ↓
Return filtered headlines to frontend
    ↓
Browser: Display, read aloud (TTS), queue for audio
```

### Key Functions

#### 1. **News Enable/Disable Logic** ([news/routes.py](news/routes.py#L15-L25))

```python
def news_enabled(form: Mapping[str, Any]) -> bool:
    """Return whether news should participate in fetching/timing logic."""
    setting = form.get("ComparisonNews", "enabled").lower()
    return setting not in {"disabled", "false", "0", "off", "no"}

def news_signal_enabled(form: Mapping[str, Any]) -> bool:
    """Return whether the news indicator itself should be evaluated as a signal."""
    return form.get("ComparisonNews", "").lower() == "enabled"
```

#### 2. **Keyword Filtering** ([news/routes.py](news/routes.py#L42-L62))

- Parses comma-separated keywords from form
- Performs whole-word matching (case-insensitive)
- Returns filtered headlines and matched text
- Uses regex for pattern matching: `\b<keyword>\b`

#### 3. **Time Window Filtering** ([news/utils.py](news/utils.py#L80-L140))

Two configuration options:
- **New Format**: `NewsWithinValue` + `NewsTimeUnit` (minutes, hours, days)
- **Legacy Format**: `NewsWithinHours`

Returns headlines published within the specified time window. Setting value to 0 shows all headlines.

#### 4. **Date/Time Parsing** ([news/utils.py](news/utils.py#L1-L75))

Supports multiple timestamp formats:
- ISO 8601 (`2026-05-29T14:30:00Z`)
- IBKR format (`20260529-14:30:00`)
- Unix timestamps (seconds or milliseconds)
- Multiple date/time separators (-, /, spaces)

All timestamps normalized to UTC timezone.

---

## Form Configuration Options

### Core News Settings

| Form Field | Type | Default | Description |
|-----------|------|---------|-------------|
| **ComparisonNews** | Select | `enabled` | Enable/disable news as a signal indicator |
| **NewsKeywords** | String | (empty) | Comma-separated keywords to match in headlines |
| **NewsWithinValue** | Integer | 0 | Time window value |
| **NewsTimeUnit** | Select | `minutes` | Time unit: minutes, hours, or days |
| **NewsWithinHours** | Integer | (legacy) | Deprecated - use NewsWithinValue instead |

### Read Aloud Settings

| Form Field | Type | Default | Description |
|-----------|------|---------|-------------|
| **NewsReadAloud** | Select | `on` | Read keyword-matched headlines aloud |
| **NewsAutoReadAll** | Select | `on` | Read ALL headlines automatically |
| **NewsReadAloudWithinValue** | Integer | 0 | Time window for read-aloud |
| **NewsReadAloudTimeUnit** | Select | `minutes` | Time unit for read-aloud window |

### Configuration Logic

```
1. ComparisonNews = "enabled"  → News is processed as a signal
2. ComparisonNews = "disabled" → News is not processed
3. NewsKeywords populated     → Only matching headlines are shown
4. NewsReadAloud = "on"       → Read matched headlines aloud
5. NewsAutoReadAll = "on"     → Read ALL headlines aloud
6. TimeWindow > 0             → Filter by recent headlines only
```

---

## Setup & Installation

### Prerequisites

1. **Python 3.8+**
2. **Flask** (for routing)
3. **IBKR TWS/IB Gateway** running with API enabled
4. **Modern web browser** (Chrome, Firefox, Safari, Edge)

### Installation Steps

#### 1. Install Requirements
```bash
# Navigate to project root
cd c:\Users\krmri\Music\ibkr-webapp-main 3-25-26

# Run the install script (Windows)
install_requirements.bat

# Or manually install
pip install -r requirements.txt
```

#### 2. Configure Flask App
Edit [config.ini](config.ini) to set:
```ini
[Flask]
flask_run_port = 5000
flask_secret_key = your-secret-key-here
scanner_interval_seconds = 60
```

#### 3. Configure IBKR Connection
```ini
[IBKR]
api_mode = PAPER           # or LIVE
api_live_port = 7496
api_paper_port = 7497
```

#### 4. Verify Setup
```bash
# Check if all files exist
ls news/
ls scanner/
ls templates/news_reader.html

# Verify Python packages
python -c "import flask; import pandas; import ibapi; print('All dependencies OK')"
```

---

## Running the News Module

### 1. Start the Flask Application

**Windows (Batch File)**
```bash
runthis.bat
```

**Manual Start**
```bash
cd c:\Users\krmri\Music\ibkr-webapp-main 3-25-26
python -m flask run --port 5000
```

### 2. Start IBKR TWS or IB Gateway

- Open TWS/Gateway
- Enable API (Edit → Settings → API)
- Use Paper Trading or Live Trading
- Confirm port matches config.ini (7496 for live, 7497 for paper)

### 3. Verify Connection

Once Flask is running:
```
✓ Check: http://localhost:5000 (main scanner page)
✓ Check: http://localhost:5000/news-reader (dedicated news page)
✓ Check: Flask console shows "Running on http://127.0.0.1:5000"
```

### 4. Run Tests (Optional)

```bash
# Test news utilities
python -m pytest tests/test_news_utils.py -v

# Test news filtering
python -m pytest tests/test_news_filtering_debug.py -v

# All tests
python -m pytest tests/ -v
```

---

## Validation & Testing on Browser

### 1. **Access the Scanner Page**

1. Open browser: `http://localhost:5000/morfeo`
2. Configure scanner settings
3. **Enable news feature**:
   - Set `Comparison News` → `enabled`
   - Add keywords (e.g., "earnings, dividend, acquisition")
   - Set time window (e.g., 60 minutes)

### 2. **Configure News Settings in Scanner**

| Setting | Action | Expected |
|---------|--------|----------|
| **Comparison News** | Select "enabled" | News headlines appear in scanner results |
| **News Keywords** | Enter "earnings,split" | Only headlines matching keywords shown |
| **News Read Aloud** | Select "on" | Matched headlines read via TTS |
| **News Auto Read All** | Select "on" | All headlines read automatically |
| **Within Value** | Set "60" | Only headlines from last 60 minutes shown |

### 3. **Dedicated News Reader Page**

1. Navigate to: `http://localhost:5000/news-reader`
2. This page displays:
   - Symbol filter
   - Source selector (Scanner Loop / Background Scan)
   - Time window filter
   - Live feed of headlines
   - Read aloud controls

### 4. **Validation Checklist**

#### ✓ News Fetching
- [ ] Scanner loads without errors
- [ ] Headlines appear in scanner results when "ComparisonNews" = "enabled"
- [ ] News count increases as scanner runs
- [ ] Timestamps are visible and reasonable

#### ✓ Keyword Filtering
- [ ] Set keywords to "tesla"
- [ ] Only headlines containing "tesla" appear
- [ ] Case-insensitive matching works
- [ ] Whole-word matching only (e.g., "tesla" doesn't match "teslatech")

#### ✓ Time Window Filtering
- [ ] Set "Within Value" to "0" → shows all headlines
- [ ] Set "Within Value" to "30" (minutes) → shows only recent headlines
- [ ] Changing time unit (hours/days) works correctly
- [ ] Old headlines disappear when time window filter applied

#### ✓ Text-to-Speech (TTS)
- [ ] Browser audio is enabled
- [ ] Set "News Read Aloud" = "on"
- [ ] Matched headlines are read aloud
- [ ] Set "News Auto Read All" = "on"
- [ ] All headlines are read aloud
- [ ] Volume/speed controls work in browser
- [ ] Queue shows pending headlines

#### ✓ News Reader Dedicated Page
- [ ] Page loads at `http://localhost:5000/news-reader`
- [ ] Headlines display in clean list format
- [ ] Filter controls work
- [ ] Back to Scanner link works

### 5. **Browser Developer Tools Testing**

**Open DevTools (F12) → Console Tab**

#### Test 1: Verify API Endpoints
```javascript
// Fetch news configuration
fetch('/api/scan-status').then(r => r.json()).then(console.log)

// Check if news data is present
console.log('Check for headlines:', !!document.querySelector('.news-headline'))
```

#### Test 2: Monitor Network Traffic
1. Open DevTools → Network tab
2. Set keywords and apply filter
3. Watch for API calls:
   - News fetch requests
   - Headline updates
   - TTS audio requests

#### Test 3: Check Console for Errors
1. Open DevTools → Console tab
2. Run scanner with news enabled
3. Verify no errors related to:
   - `news_enabled()`
   - `filter_headlines_by_keywords()`
   - News datetime parsing

### 6. **Manual Testing Scenarios**

#### Scenario 1: Basic News Fetch
```
Setup:
  - ComparisonNews: enabled
  - NewsKeywords: (empty)
  - NewsWithinValue: 0

Expected:
  - All headlines appear
  - Headlines include dates, symbols, text
  - New headlines added as scanner runs
```

#### Scenario 2: Keyword Filtering
```
Setup:
  - ComparisonNews: enabled
  - NewsKeywords: earnings, earnings call
  - NewsWithinValue: 120 (minutes)

Expected:
  - Only headlines containing "earnings" or "earnings call" appear
  - Case-insensitive matching
  - Only last 2 hours of headlines shown
```

#### Scenario 3: Read Aloud
```
Setup:
  - NewsReadAloud: on
  - NewsAutoReadAll: off
  - NewsReadAloudWithinValue: 30
  - Browser audio enabled

Expected:
  - Matched headlines are read aloud
  - Audio plays for headlines < 30 minutes old
  - Can hear TTS voice in browser
  - Playback queue visible
```

#### Scenario 4: Multiple Keywords
```
Setup:
  - NewsKeywords: "apple, microsoft, google, nvidia"
  - NewsWithinValue: 60

Expected:
  - Headlines for any of these 4 companies shown
  - From last 60 minutes only
  - All symbols in sidebar
```

---

## Troubleshooting

### Issue: No headlines appearing

**Checklist:**
- [ ] `ComparisonNews` is set to "enabled" (not "disabled")
- [ ] IBKR TWS/Gateway is running and connected
- [ ] Scanner has found stocks to analyze
- [ ] IBKR API port (7496/7497) is correct in config.ini
- [ ] Check browser console (F12) for JavaScript errors

**Debug:**
```python
# In Python console
from news.routes import news_enabled
from forms import Parameters
form = Parameters().validate()  # Get current form data
print(news_enabled(form.data))  # Should print True
```

### Issue: Keywords not filtering

**Checklist:**
- [ ] Keywords are comma-separated (e.g., "tesla, apple")
- [ ] At least one headline contains the keyword
- [ ] Check browser network tab for API response
- [ ] Verify keyword matching in console

**Debug:**
```python
from news.routes import filter_headlines_by_keywords
headlines = [
    {"headline": "Tesla Reports Earnings"},
    {"headline": "Apple Splits Stock"}
]
filtered, matched, found = filter_headlines_by_keywords(headlines, "tesla")
print(filtered)  # Should show Tesla headline
print(matched)   # Should show matched text
```

### Issue: TTS not working

**Checklist:**
- [ ] Browser audio is not muted
- [ ] Volume is set above 0%
- [ ] `NewsReadAloud` or `NewsAutoReadAll` is set to "on"
- [ ] Speech synthesis supported in your browser (check F12 console)

**Test TTS in Browser Console:**
```javascript
const utterance = new SpeechSynthesisUtterance("Test audio. This is a news headline.");
window.speechSynthesis.speak(utterance);
// Should hear "Test audio..." in browser
```

### Issue: Time window filtering not working

**Checklist:**
- [ ] `NewsWithinValue` is greater than 0
- [ ] `NewsTimeUnit` is set to minutes/hours/days
- [ ] Headlines are actually within the time window
- [ ] Check date parsing by looking at headline timestamps

**Debug:**
```python
from news.utils import news_within_minutes, parse_news_datetime
from datetime import datetime, timezone

# Test time window calculation
minutes = news_within_minutes({"NewsWithinValue": 60, "NewsTimeUnit": "minutes"})
print(f"Time window: {minutes} minutes")  # Should print 60

# Test date parsing
dt = parse_news_datetime("2026-05-29T14:30:00Z")
print(f"Parsed date: {dt}")  # Should show UTC datetime
```

---

## Common Use Cases

### Use Case 1: Monitor Specific Stocks
```
1. Scanner Results → Filter by symbols (AAPL, MSFT, GOOGL)
2. ComparisonNews: enabled
3. NewsWithinValue: 30 minutes
4. Result: Only recent news for these stocks shown
```

### Use Case 2: Track Earnings Season
```
1. NewsKeywords: "earnings, earnings call, earnings report"
2. NewsWithinValue: 1440 (24 hours)
3. NewsReadAloud: on
4. Result: All earnings headlines read aloud automatically
```

### Use Case 3: Monitor M&A Activity
```
1. NewsKeywords: "acquisition, merger, takeover, buyout"
2. NewsWithinValue: 60 (minutes)
3. Result: Real-time M&A news feed
```

### Use Case 4: Event-Based Trading
```
1. ComparisonNews: enabled (as signal indicator)
2. Scanner evaluates news as part of signal strength
3. High news activity can trigger alerts
4. Result: News integrated into trading signals
```

---

## Performance Considerations

### News Fetching Impact
- **IBKR API calls**: One call per symbol per scan
- **Cached results**: Headlines cached in memory
- **Time window**: Filtering by time reduces memory usage

### Browser Performance
- **TTS Queue**: Limited to ~10-20 headlines
- **DOM Updates**: News rows appended incrementally
- **Audio Files**: Generated on-the-fly (no storage)

### Optimization Tips
1. Use tight keyword filters to reduce headlines
2. Set reasonable time windows (30-120 minutes)
3. Disable "Auto Read All" to reduce TTS processing
4. Refresh browser if UI becomes sluggish

---

## Code Examples

### Example 1: Check if News is Enabled
```python
from news.routes import news_enabled
from forms import Parameters

form_data = Parameters().data
if news_enabled(form_data):
    print("News is enabled for this scan")
else:
    print("News is disabled")
```

### Example 2: Filter Headlines by Keywords
```python
from news.routes import filter_headlines_by_keywords

headlines = [
    {"headline": "Apple Reports Record Earnings", "timestamp": "2026-05-29T14:00:00Z"},
    {"headline": "Microsoft Announces Partnership", "timestamp": "2026-05-29T13:30:00Z"},
    {"headline": "Tesla Stock Rises", "timestamp": "2026-05-29T13:00:00Z"},
]

keywords = "apple, microsoft"
filtered, matched_text, found = filter_headlines_by_keywords(headlines, keywords)

print(f"Found {len(filtered)} matching headlines:")
for h in filtered:
    print(f"  - {h['headline']}")
# Output:
#   Found 2 matching headlines:
#   - Apple Reports Record Earnings
#   - Microsoft Announces Partnership
```

### Example 3: Calculate News Time Window
```python
from news.utils import news_within_minutes

form_data = {
    "NewsWithinValue": 60,
    "NewsTimeUnit": "minutes"
}

minutes = news_within_minutes(form_data)
print(f"News window: {minutes} minutes")  # Output: 60 minutes
```

### Example 4: Parse News Timestamp
```python
from news.utils import parse_news_datetime
from datetime import datetime, timezone

# Parse various timestamp formats
timestamps = [
    "2026-05-29T14:30:00Z",
    "20260529-14:30:00",
    1717008600,  # Unix timestamp
    "2026-05-29 14:30:00"
]

for ts in timestamps:
    dt = parse_news_datetime(ts)
    print(f"{ts} → {dt} (UTC)")
```

---

## Related Documentation

- **Forms Configuration**: [forms.py](forms.py#L922-L970)
- **Scanner Signal Engine**: [scanner/ibkr_signal_engine.py](scanner/ibkr_signal_engine.py)
- **Main App Setup**: [__init__.py](__init__.py)
- **Test Suite**: [tests/test_news_utils.py](tests/test_news_utils.py)

---

## Support & Debugging

### Enable Debug Logging
```python
# In your script or __init__.py
import logging
logging.basicConfig(level=logging.DEBUG)

# Now you'll see detailed news processing logs
```

### Run Tests
```bash
# All news-related tests
pytest tests/test_news*.py -v

# Specific test file
pytest tests/test_news_utils.py -v

# Run with output
pytest tests/test_news_filtering_debug.py -v -s
```

### Check Integration
```bash
# Verify news route is registered
python -c "from __init__ import app; print('/news-reader' in [r.rule for r in app.url_map.iter_rules()])"
# Should output: True
```

---

## Summary

The News Module provides a complete news monitoring and filtering system for the IBKR Trading Webapp:

✓ **Fetches** headlines from IBKR API based on scanner results  
✓ **Filters** by keywords, time windows, and signal indicators  
✓ **Displays** in dedicated UI with real-time updates  
✓ **Reads aloud** using browser text-to-speech  
✓ **Integrates** with scanner signal evaluation  

For questions or issues, check logs, run tests, and refer to the troubleshooting section above.
