# News Headline Settings Fix - Summary

## Problem Identified
News headlines were NOT being read aloud by default when the application started, even when users turned on the news settings. This was due to incorrect default values in the form configuration.

## Root Cause
In `forms.py`, the following fields had incorrect defaults:
- `NewsReadAloud`: default was "off" (should be "on")
- `NewsAutoReadAll`: default was "off" (should be "on")

## Solution Implemented
Modified `forms.py` to set the correct default values:

### Changes Made:
1. **NewsReadAloud field** (Line 1152-1159):
   - Changed: `default="off"` → `default="on"`
   - Effect: Headlines matching keywords are now read aloud by default

2. **NewsAutoReadAll field** (Line 1173-1182):
   - Changed: `default="off"` → `default="on"`
   - Effect: ALL news headlines are auto-read after results return by default

3. **ComparisonNews field** (Line 1129-1137):
   - Already set to: `default="enabled"`
   - No change needed

## How News Reading Works

### News Processing Flow:
```
ComparisonNews = "enabled" (REQUIRED - controls if news is fetched at all)
    ↓
NewsReadAloud = "on" (Reads keyword-matched headlines aloud)
    ├─ NewsReadAloudWithinValue = time window (0 = all headlines)
    └─ NewsReadAloudTimeUnit = minutes/hours/days
    
NewsAutoReadAll = "on" (Reads ALL headlines automatically)
    ├─ NewsReadAloudWithinValue = time window (0 = all headlines)  
    └─ NewsReadAloudTimeUnit = minutes/hours/days
```

### JavaScript Verification (morfeo.html):
- **Line 4044**: Checks if `ComparisonNews.value === 'enabled'`
- **Line 4050**: If news enabled, checks if `NewsReadAloud.value === 'on'`
- **Line 4122**: Checks if `NewsAutoReadAll.value === 'on' || NewsAutoReadAll.value === 'True'`
- **Line 4184-4186**: Queues headlines for TTS playback via `readHeadlineAloud()`

### Backend Logic (ibkr_signal_engine.py):
- **Line 6851**: Gets `ComparisonNews` setting, defaults to "enabled"
- **Line 6853**: Calculates `is_news_enabled` from the form value
- **Line 6854**: Checks if keywords are configured
- **Line 6855**: Decides whether to fetch news headlines

## Testing the Fix

1. Clear browser cache (localStorage might have old settings)
2. Refresh the application
3. Go to News Configuration section
4. Verify these are NOW enabled by default:
   - "Enable News" = "Used" ✓
   - "Read Headlines Aloud" = "On" ✓
   - "Auto-Read All News" = "On" ✓

5. Submit a scan
6. Headlines should now play automatically via text-to-speech

## Volume & Mute Controls
- **TTS Volume Slider**: Control volume (0-100%)
- **Mute Button**: Toggle mute on/off (💻 localStorage persisted)
- **Stop Button**: Stop current playback immediately

## Related Configuration Options
- `NewsMaxHeadlines`: Maximum headlines to fetch (default: 20)
- `NewsWithinValue` + `NewsTimeUnit`: Time window for headlines (0 = all)
- `NewsKeywords`: Comma-separated keywords to highlight (plays alert sound)
- `NewsExcludePublishers`: Publishers to exclude (e.g., "BZ, MT")
- `NewsProviders`: Preferred news providers (blank = all)

## Files Modified
- ✅ `forms.py` (Lines 1152-1159, 1173-1182)

## Files NOT Modified (Already Working Correctly)
- `templates/morfeo.html` - JavaScript logic ✓
- `ibkr_signal_engine.py` - Backend logic ✓
- `config.py` - Configuration ✓
