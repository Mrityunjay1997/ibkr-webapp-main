import time
import json
import math
import random
import logging
import threading
import traceback
import numpy as np
import pandas as pd
from config import Config
from typing import Any, Dict, Optional
from datetime import time as datetime_time

import pytz

from ibapi.order import Order
from ibapi.common import OrderId, ListOfPriceIncrements
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract, ComboLeg
from ibapi.order_state import OrderState
from ibapi.scanner import ScannerSubscription

from indicators import (
    VolumeWeightedAveragePrice,
    SMAIndicator,
    RSIIndicator,
    EMAIndicator,
    OBVIndicator,
    FastOBVIndicator,
    MediumOBVIndicator,
    SlowOBVIndicator,
    ATRIndicator,
    GapAnalyzer,
    # pivot_points,
    last_value
)

# -----------------------------------------------------------------------------
# Logging - lightweight
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logging.getLogger("waitress").setLevel(logging.WARNING)
logging.getLogger("ibapi").setLevel(logging.WARNING)
logging.getLogger("ibapi.client").setLevel(logging.WARNING)
logger = logging.getLogger("ibkr_app")


def _safe_compare(value, op, threshold):
    """
    Compare value and threshold safely.
    If value is None -> return False.
    """

    if value is None:
        return False

    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold

    raise ValueError(f"Unsupported operator: {op}")


def _within_percent_check(indicator_value, close_value, mode, threshold):
    """Check if close is within threshold% of indicator_value.

    mode must be one of:
      'withinPercentAbove'  – close is between indicator and indicator*(1+threshold/100)
      'withinPercentBelow'  – close is between indicator*(1-threshold/100) and indicator
      'withinPercentEither' – close is within threshold% in either direction
    Returns True/False, or False if either value is None.
    """
    if indicator_value is None or close_value is None:
        return False
    try:
        pct_from = ((close_value - indicator_value) / abs(indicator_value)) * 100.0
    except ZeroDivisionError:
        return False
    if mode == "withinPercentAbove":
        return 0 <= pct_from <= threshold
    elif mode == "withinPercentBelow":
        return -threshold <= pct_from <= 0
    else:  # withinPercentEither
        return abs(pct_from) <= threshold


# Modes that are NOT simple > >= < <= comparisons
_NON_SIMPLE_MODES = frozenset(
    ("Not used", "between",
     "withinPercentAbove", "withinPercentBelow", "withinPercentEither")
)


def _normalize_market_cap(value):
    """
    Normalize market cap value to millions.
    
    Handles multiple formats:
    - Direct numeric values (assumed to be in millions from IBKR)
    - Values with suffixes like '1.15m' (millions), '1.92b' (billions)
    - Semicolon-delimited format from IBKR fundamental data
    - Very large numbers (> 1B) assumed to be in dollars
    
    Returns the value in millions as a float, or None if parsing fails.
    
    Examples:
      - 100 -> 100.0 (already in millions)
      - "100" -> 100.0 (string format, already in millions)
      - "1500m" or "1500M" -> 1500.0 (millions)
      - "2.5b" or "2.5B" -> 2500.0 (convert billions to millions)
      - "1.15m" -> 1.15 (already in millions)
      - 50000000 -> 50.0 (in dollars, convert to millions)
      - 2500000000 -> 2500.0 (in dollars, convert to millions)
    """
    if value is None:
        return None
    
    try:
        # Convert to string and strip whitespace
        val_str = str(value).strip().lower()
        
        # Handle empty string
        if not val_str or val_str == "":
            return None
        
        # Check for billion suffix
        if val_str.endswith('b'):
            # Extract number and convert billions to millions
            numeric = float(val_str[:-1])
            return numeric * 1000.0
        
        # Check for million suffix
        if val_str.endswith('m'):
            # Extract number (already in millions)
            return float(val_str[:-1])
        
        # Check for million as part of compound (e.g., "1500 m" or "1500m")
        if 'm' in val_str:
            # Extract the numeric part before 'm'
            numeric_str = val_str.split('m')[0].strip()
            try:
                numeric = float(numeric_str)
                # Check if it looks like millions (reasonable range for market cap values in millions)
                if numeric >= 0 and numeric < 1000000000:
                    return numeric
            except ValueError:
                pass
        
        # Pure numeric value
        numeric = float(val_str)
        
        # If the value is very large (likely in dollars), convert to millions
        # IBKR returns MKTCAP typically in millions already, but if it's returned
        # in dollars (very large number), divide by 1 million
        # Heuristic: if > 1 billion (1,000,000,000), it's likely in dollars
        if numeric > 1000000000:
            return numeric / 1000000.0  # Convert from dollars to millions
        
        # For values between 0 and 1,000,000,000, assume they're already in millions
        # This handles IBKR's native million format
        if numeric >= 0:
            return numeric
        
        # Negative values are invalid
        return None
    
    except (ValueError, TypeError, AttributeError):
        logger.debug("Failed to normalize market cap value: %s", value)
        return None


def _calculate_market_cap_from_price_and_shares(current_price, shares_outstanding):
    """
    Calculate market cap from current price and shares outstanding.
    
    Both parameters should be numeric values.
    Returns market cap in millions, or None if calculation fails.
    
    Formula: Market Cap (in millions) = (Current Price × Shares Outstanding) / 1,000,000
    
    Examples:
      - price=100, shares=50000000 -> 5000 million ($5B market cap)
      - price=25.50, shares=100000000 -> 2550 million
    """
    if current_price is None or shares_outstanding is None:
        return None
    
    try:
        price = float(current_price)
        shares = float(shares_outstanding)
        
        # Validate inputs
        if price <= 0 or shares <= 0:
            return None
        
        # Calculate market cap in dollars, then convert to millions
        market_cap_dollars = price * shares
        market_cap_millions = market_cap_dollars / 1_000_000.0
        
        return market_cap_millions
    
    except (ValueError, TypeError, AttributeError):
        logger.debug("Failed to calculate market cap from price=%s, shares=%s", current_price, shares_outstanding)
        return None


def average_volume(data: pd.DataFrame, lookback: int) -> float:
    """
    Calculate the average volume over the last `lookback` rows.
    """
    return float(np.mean(data["volume"][-lookback:]))


def relative_volume(data: pd.DataFrame, lookback: int) -> float:
    """
    Calculate relative volume:
        last bar volume / average volume over last `lookback` bars.
    """
    return float(data["volume"].values[-1]) / float(
        np.mean(data["volume"][-lookback:])
    )


def calculate_pct_change(data: pd.DataFrame, lookback_bars: int = 5) -> float:
    """
    Calculate % change over the last `lookback_bars` bars.
    Returns: (current_close - open_of_lookback) / open_of_lookback * 100
    """
    if data is None or len(data) < lookback_bars:
        return 0.0
    
    try:
        current_close = float(data["close"].iloc[-1])
        lookback_open = float(data["open"].iloc[-lookback_bars])
        if lookback_open <= 0:
            return 0.0
        pct_change = ((current_close - lookback_open) / lookback_open) * 100.0
        return float(pct_change)
    except (ValueError, KeyError, IndexError):
        return 0.0


def calculate_volume_sum(data: pd.DataFrame, lookback_bars: int = 5) -> float:
    """
    Calculate total volume over the last `lookback_bars` bars.
    """
    if data is None or len(data) < lookback_bars:
        return 0.0
    
    try:
        return float(np.sum(data["volume"].iloc[-lookback_bars:]))
    except (ValueError, KeyError, IndexError):
        return 0.0


def calculate_rvol(hist_data: pd.DataFrame, lookback_days: int = 5) -> float:
    """
    Calculate Relative Volume (RVOL) for the current bar.
    RVOL = Current Bar Volume / Average Volume
    
    Args:
        hist_data: DataFrame with historical OHLC and volume data
        lookback_days: Number of days to look back for average volume
    
    Returns:
        float: RVOL multiplier (e.g., 1.5 means 150% of average volume)
    """
    if hist_data is None or len(hist_data) == 0:
        return 0.0
    
    try:
        current_volume = float(hist_data["volume"].iloc[-1])
        
        # Get average volume from lookback period (excluding current bar)
        lookback_bars = max(1, min(lookback_days * 6, len(hist_data) - 1))  # ~6 bars per hour, 1 day = ~39 bars
        
        if lookback_bars > 0 and len(hist_data) > lookback_bars:
            avg_volume = float(hist_data["volume"].iloc[-lookback_bars-1:-1].mean())
        elif len(hist_data) > 1:
            avg_volume = float(hist_data["volume"].iloc[:-1].mean())
        else:
            avg_volume = current_volume
        
        if avg_volume <= 0:
            return 0.0
        
        rvol = current_volume / avg_volume
        return float(rvol)
    except Exception as e:
        logger.warning(f"Error calculating RVOL: {e}")
        return 0.0


def _safe_to_float(value) -> Optional[float]:
    """
    Safely convert any value to float, handling numpy types and None.
    
    Args:
        value: Value to convert (can be float, int, numpy type, string, None, etc.)
    
    Returns:
        float or None if conversion fails
    """
    if value is None:
        return None
    
    try:
        # Handle numpy types
        if hasattr(value, 'item'):
            # numpy scalar
            val = float(value.item())
        else:
            val = float(value)
        
        # Check for NaN
        if pd.isna(val):
            return None
        
        return val
    except (ValueError, TypeError, AttributeError):
        return None


def generate_tts_message(symbol: str, signal: str, description: str) -> str:
    """
    Generate a text-to-speech message for OBV analysis alerts.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        signal: Signal type (e.g., "strong_bullish", "strong_bearish")
        description: Natural language description from analyze_multi_obv
    
    Returns:
        str: Formatted message ready for TTS
    """
    if signal == "strong_bullish":
        return f"{symbol}. Strong bullish O B V signal detected. {description}"
    elif signal == "bullish":
        return f"{symbol}. Bullish O B V signal detected. {description}"
    elif signal == "strong_bearish":
        return f"{symbol}. Strong bearish O B V signal detected. {description}"
    elif signal == "bearish":
        return f"{symbol}. Bearish O B V signal detected. {description}"
    else:  # neutral or unknown
        return f"{symbol}. Neutral O B V signal. Monitor for clearer direction."


def prepare_obv_audio_alert(signal: str) -> dict:
    """
    Prepare audio alert configuration for Multi-OBV signals.
    
    Supports bullish (triumphant arpeggio) and bearish (descending) audio cues.
    
    Args:
        signal: Signal type from analyze_multi_obv result
    
    Returns:
        dict with audio configuration:
        {
            "type": "arpeggio" | "descending" | "neutral",
            "intensity": "high" | "medium" | "low",
            "notes": list of note frequencies or MIDI codes
        }
    """
    if signal in ["strong_bullish", "bullish"]:
        # Triumphant arpeggio: ascending notes
        return {
            "type": "arpeggio",
            "intensity": "high" if signal == "strong_bullish" else "medium",
            "direction": "ascending",
            "notes": [261.63, 329.63, 392.00, 523.25],  # C, E, G, C (arpeggio)
            "description": "Bullish momentum detected"
        }
    elif signal in ["strong_bearish", "bearish"]:
        # Descending notes: bearish indication
        return {
            "type": "descending",
            "intensity": "high" if signal == "strong_bearish" else "medium",
            "direction": "descending",
            "notes": [523.25, 392.00, 329.63, 261.63],  # C, G, E, C (descending)
            "description": "Bearish momentum detected"
        }
    else:
        # Neutral sound
        return {
            "type": "neutral",
            "intensity": "low",
            "notes": [349.23],  # F middle tone
            "description": "Neutral OBV signal"
        }


def format_obv_equation(fast_obv: float, medium_obv: float, slow_obv: float,
                        fast_pct_change: float, medium_pct_change: float, 
                        fast_slow_pct_change: float) -> str:
    """
    Format OBV comparison equation for display.
    
    Shows the visual relationship between three OBV values with direction indicators
    and percentage changes.
    
    Args:
        fast_obv: Fast OBV value (5-bar MA)
        medium_obv: Medium OBV value (10-bar MA)
        slow_obv: Slow OBV value (20-bar MA)
        fast_pct_change: % change from Fast to Medium OBV
        medium_pct_change: % change from Medium to Slow OBV
        fast_slow_pct_change: % change from Fast to Slow OBV
    
    Returns:
        str: Formatted equation string
    """
    fast_dir = '↑' if fast_obv > 0 else '↓'
    medium_dir = '↑' if medium_obv > 0 else '↓'
    slow_dir = '↑' if slow_obv > 0 else '↓'
    
    return (
        f"Fast OBV: {fast_obv:,.0f}{fast_dir} | "
        f"Medium OBV: {medium_obv:,.0f}{medium_dir} | "
        f"Slow OBV: {slow_obv:,.0f}{slow_dir} | "
        f"% Changes: F→M {fast_pct_change:+.1f}% | M→S {medium_pct_change:+.1f}% | F→S {fast_slow_pct_change:+.1f}%"
    )


def apply_result_filters(stock_data: dict, form: dict) -> bool:
    """
    Check if a stock result meets all enabled filter criteria.
    
    Args:
        stock_data: Dict containing stock indicator values and variableResults
        form: Form data dict with filter checkbox states (filterVWAP, filterRSI, etc.)
    
    Returns:
        True if stock meets ALL enabled filters, False otherwise.
        If no filters are enabled, returns True (include all).
    """
    
    # Track if any filters are enabled
    any_filter_enabled = False
    
    # Helper to evaluate if an indicator meets its configured condition
    def check_indicator_condition(indicator_value, indicator_key, comparison_key, value_key, value_key1=None):
        """Check if indicator meets the configured comparison condition."""
        # Safely convert indicator value to float
        indicator_value = _safe_to_float(indicator_value)
        if indicator_value is None:
            return False
        
        comparison = form.get(comparison_key, "Not used")
        if comparison == "Not used":
            return True  # If not configured, consider it "met"
        
        # Get comparison thresholds
        threshold = form.get(value_key)
        threshold1 = form.get(value_key1) if value_key1 else None
        
        if threshold in (None, ""):
            return True
        
        # Safely convert thresholds to float
        threshold = _safe_to_float(threshold)
        threshold1 = _safe_to_float(threshold1) if threshold1 else None
        
        if threshold is None:
            return True
        
        # If threshold1 was provided but conversion failed, use threshold as fallback
        if threshold1 is None and value_key1:
            threshold1 = threshold
        
        # Evaluate based on comparison operator
        try:
            if comparison == "greater":
                return indicator_value > threshold
            elif comparison == "greaterEqual":
                return indicator_value >= threshold
            elif comparison == "lower":
                return indicator_value < threshold
            elif comparison == "lowerEqual":
                return indicator_value <= threshold
            elif comparison == "between":
                # Both thresholds required for 'between'
                if threshold1 is None:
                    return True
                # Ensure threshold <= threshold1
                min_val, max_val = min(threshold, threshold1), max(threshold, threshold1)
                return min_val <= indicator_value <= max_val
            elif comparison == "withinPercentAbove":
                # Note: indicator_value is the current close, threshold is the reference level
                pct_diff = abs(threshold1 - threshold) if threshold1 else 0
                return _within_percent_check(threshold, indicator_value, "withinPercentAbove", pct_diff)
            elif comparison == "withinPercentBelow":
                pct_diff = abs(threshold1 - threshold) if threshold1 else 0
                return _within_percent_check(threshold, indicator_value, "withinPercentBelow", pct_diff)
            elif comparison == "withinPercentEither":
                pct_diff = abs(threshold1 - threshold) if threshold1 else 0
                return _within_percent_check(threshold, indicator_value, "withinPercentEither", pct_diff)
            else:
                return True
        except Exception as e:
            logger.debug("Error evaluating condition %s: %s", comparison_key, e)
            return False
    
    # Define all numeric filters as a list of tuples:
    # (filter_key, stock_data_key, comparison_key, value_key, value_key1)
    numeric_filters = [
        # Top group indicators (VWAP & SMAs)
        ("filterVWAP", "vwap", "ComparisonVWAP", "VWAP", "PercentageVWAP"),
        ("filterFastSMA", "smaFast", "ComparisonFastSMA", "FastSMA", "PercentageFastSMA"),
        ("filterMediumSMA", "smaMedium", "ComparisonMediumSMA", "MediumSMA", "PercentageMediumSMA"),
        ("filterSlowSMA", "smaSlow", "ComparisonSlowSMA", "SlowSMA", "PercentageSlowSMA"),
        
        # Momentum indicators
        ("filterRSI", "rsi", "ComparisonRSI", "RSI", "PercentageRSI"),
        ("filterFastEMA", "emaFast", "ComparisonFastEMA", "FastEMA", "PercentageFastEMA"),
        ("filterSlowEMA", "emaSlow", "ComparisonSlowEMA", "SlowEMA", "PercentageSlowEMA"),
        ("filterOBV", "obv", "ComparisonOBV", "OBV", "PercentageOBV"),
        ("filterFastOBV", "fast_obv", "ComparisonFastOBV", "FastOBV", "PercentageFastOBV"),
        ("filterMediumOBV", "medium_obv", "ComparisonMediumOBV", "MediumOBV", "PercentageMediumOBV"),
        ("filterSlowOBV", "slow_obv", "ComparisonSlowOBV", "SlowOBV", "PercentageSlowOBV"),
        ("filterATR", "atr", "ComparisonATR", "ATR", "PercentageATR"),
        
        # Volume indicators
        ("filterAverageVolume", "averageVolume", "ComparisonAverageVolume", "AverageVolume", None),
        ("filterRelativeVolume", "relativeVolume", "ComparisonRelativeVolume", "RelativeVolume", None),
        ("filterVolume", "volumeIndicator", "ComparisonVolume", "Volume", None),
        
        # Price-based indicators
        ("filterPrevClose", "prevClose", "ComparisonPrevClose", "PrevClose", "PercentagePrevClose"),
        ("filterPctChange", "pctChange", "ComparisonPctChange", "PctChange", "PercentagePctChange"),
        ("filterLowOfDay", "lowOfDay", "ComparisonLowOfDay", "LowOfDay", "PercentageLowOfDay"),
        ("filterHighOfDay", "highOfDay", "ComparisonHighOfDay", "HighOfDay", "PercentageHighOfDay"),
        ("filterBreakHigh", "breakHigh", "ComparisonBreakHigh", "BreakHigh", "PercentageBreakHigh"),
        
        # Pullback and Gap indicators
        ("filterPullbackPct", "pullbackPct", "ComparisonPullbackPct", "PullbackPct", "PercentagePullbackPct"),
        ("filterPullbackPct2", "pullbackPct2", "ComparisonPullbackPct2", "PullbackPct2", "PercentagePullbackPct2"),
        ("filterFibPullback", "fibPullback", "ComparisonFibPullback", "FibPullback", "PercentageFibPullback"),
        ("filterGapPullback", "gapPullback", "ComparisonGapPullback", "GapPullback", "PercentageGapPullback"),
        ("filterUpGap", "upGap", "ComparisonUpGap", "UpGap", "PercentageUpGap"),
        ("filterDownGap", "downGap", "ComparisonDownGap", "DownGap", "PercentageDownGap"),
        
        # Market indicators
        ("filterMarketCap", "marketCap", "ComparisonMarketCap", "MarketCap", "PercentageMarketCap"),
    ]
    
    # Check all numeric filters
    for filter_key, stock_key, comp_key, val_key, val_key1 in numeric_filters:
        if form.get(filter_key, False):
            any_filter_enabled = True
            if not check_indicator_condition(stock_data.get(stock_key), stock_key, comp_key, val_key, val_key1):
                return False
    
    # Cross SMA filters - check variableResults (boolean checks, not numeric comparisons)
    if form.get("filterCross50SMA", False):
        any_filter_enabled = True
        variable_results = stock_data.get("variableResults", {})
        if not (variable_results.get("cross50SMA_either") or stock_data.get("cross50SMA_either")):
            return False
    
    if form.get("filterCross200SMA", False):
        any_filter_enabled = True
        variable_results = stock_data.get("variableResults", {})
        if not (variable_results.get("cross200SMA_either") or stock_data.get("cross200SMA_either")):
            return False
    
    # Pivot Point filter (boolean check)
    if form.get("filterPivotPoint", False):
        any_filter_enabled = True
        variable_results = stock_data.get("variableResults", {})
        if not variable_results.get("Pivot", False):
            return False
    
    # News Keywords filter (boolean check)
    if form.get("filterNewsKeyword", False):
        any_filter_enabled = True
        variable_results = stock_data.get("variableResults", {})
        if not variable_results.get("newsKeyword", False):
            return False
    
    # If no filters were enabled, return True (include all results)
    if not any_filter_enabled:
        return True
    
    # Stock passed all enabled filters
    return True


def detect_nearby_key_levels(data: dict, proximity_pct: float = 1.0, level_type: str = "vwap") -> tuple:
    """
    Detect if current price is near a specific key level.
    
    Args:
        data: Dictionary with stock data (close, Pivot, VWAP, etc.)
        proximity_pct: How close (in %) to consider "near" a level
        level_type: Type of level to check: "vwap", "gapclose", "pivot1", "pivot2", "pivot3"
    
    Returns:
        tuple: (is_near_level: bool, level_name: str, level_value: float or None)
    """
    if not data or "close" not in data:
        return (False, "", None)
    
    try:
        current = float(data.get("close", 0))
        if current <= 0:
            return (False, "", None)
        
        target_level = None
        level_name = ""
        
        # Get the target level based on type
        if level_type == "vwap":
            level_name = "VWAP"
            if "vwap" in data:
                try:
                    target_level = float(data["vwap"])
                except (ValueError, TypeError):
                    pass
        
        elif level_type == "gapclose":
            level_name = "Gap Close"
            # Gap close is typically stored in gap data or calculated from previous close and current open
            if "gapCloseLevel" in data:
                try:
                    target_level = float(data["gapCloseLevel"])
                except (ValueError, TypeError):
                    pass
        
        elif level_type.startswith("pivot"):
            # Extract pivot level: pivot1, pivot2, pivot3
            pivot_num = level_type[-1]  # Get the last character (1, 2, or 3)
            pivot_source_key = f"Pivot{pivot_num}" if pivot_num != "1" else "Pivot"
            level_name = f"Pivot {pivot_num}"
            
            if pivot_source_key in data and isinstance(data[pivot_source_key], dict):
                pivot_dict = data[pivot_source_key]
                # Try to get the main pivot point value
                if "PP" in pivot_dict:
                    try:
                        target_level = float(pivot_dict["PP"])
                    except (ValueError, TypeError):
                        pass
        
        # Check if we found a valid level and if price is near it
        if target_level is not None and target_level > 0:
            proximity_threshold = current * (proximity_pct / 100.0)
            distance = abs(current - target_level)
            
            is_near = distance <= proximity_threshold
            return (is_near, level_name, target_level if is_near else None)
        
        return (False, level_name, None)
    except Exception as e:
        logger.warning(f"Error in detect_nearby_key_levels: {e}")
        return (False, "", None)


def detect_200sma_bullish_crossover(data: dict, form: dict = None, hist_data=None) -> bool:
    """
    Detect if stock crossed above 200 SMA from below (bullish crossover).
    Works with both regular hours and extended hours:
    - Regular hours: Compares yesterday's close to today's close
    - Extended hours: Compares previous bar's close to current bar's close
    
    This allows detection of crossovers in premarket and after-hours sessions.
    
    Args:
        data: Dictionary with current stock data (close, smaSlow, prevClose, prevBarClose, etc.)
        form: Optional form dict with EnableExtendedHours flag
        hist_data: Optional historical DataFrame with OHLC and SMA data (unused, kept for compatibility)
    
    Returns:
        True if bullish 200 SMA crossover detected, False otherwise
    """
    if not data:
        return False
    
    try:
        current_close = float(data.get("close", 0))
        sma_200 = float(data.get("smaSlow", 0))
        
        # Basic validation
        if current_close <= 0 or sma_200 <= 0:
            return False
        
        # Determine which "previous close" to use:
        # - If extended hours enabled: use prevBarClose (previous bar from extended hours data)
        # - Otherwise: use prevClose (previous trading day's close from regular hours)
        enable_extended = form.get("EnableExtendedHours", False) if form else False
        
        if enable_extended and "prevBarClose" in data:
            # Extended hours mode: use previous bar's close from the continuous extended hours data
            # This allows detection in premarket/after-hours
            prev_close = float(data.get("prevBarClose", 0))
            logger.debug("200 SMA crossover using extended hours mode (prevBarClose=%.2f)", prev_close)
        else:
            # Regular hours mode: use previous trading day's close
            prev_close = float(data.get("prevClose", 0))
        
        if prev_close <= 0:
            return False
        
        # Condition 1: Current close ABOVE 200 SMA
        is_above_today = current_close > sma_200
        
        # Condition 2: Previous close BELOW 200 SMA
        is_below_yesterday = prev_close < sma_200
        
        # Both conditions must be true for a bullish crossover
        crossover_detected = is_above_today and is_below_yesterday
        
        if crossover_detected:
            logger.info("200 SMA bullish crossover detected: prevClose=%.2f < sma200=%.2f, current=%.2f > sma200",
                       prev_close, sma_200, current_close)
        
        return crossover_detected
    except Exception as e:
        logger.warning(f"Error in detect_200sma_bullish_crossover: {e}")
        return False


def calculate_obv_momentum(data: pd.DataFrame, lookback: int = 20) -> tuple:
    """
    Calculate OBV momentum (trend direction and strength).
    
    Args:
        data: DataFrame with 'volume' and 'close' columns
        lookback: Number of bars to analyze for momentum
    
    Returns:
        Tuple of (trend, strength_pct, current_obv, obv_ma)
        trend: "rising", "declining", or "neutral"
        strength_pct: Absolute % change in OBV
        current_obv: Current OBV value
        obv_ma: OBV moving average
    """
    if data is None or len(data) < lookback:
        return ("neutral", 0.0, 0.0, 0.0)
    
    try:
        # Calculate OBV: cumulative sum of signed volume
        # +volume when close > prev close, -volume when close < prev close
        obv = np.zeros(len(data))
        obv[0] = data.iloc[0]['volume']
        
        for i in range(1, len(data)):
            close_diff = data.iloc[i]['close'] - data.iloc[i-1]['close']
            if close_diff > 0:
                obv[i] = obv[i-1] + data.iloc[i]['volume']
            elif close_diff < 0:
                obv[i] = obv[i-1] - data.iloc[i]['volume']
            else:
                obv[i] = obv[i-1]
        
        current_obv = float(obv[-1])
        lookback_obv = float(obv[-lookback])
        
        # Calculate momentum percentage
        if lookback_obv != 0:
            momentum_pct = ((current_obv - lookback_obv) / abs(lookback_obv)) * 100.0
        else:
            momentum_pct = 0.0
        
        # Determine trend direction
        if momentum_pct > 2.0:
            trend = "rising"
        elif momentum_pct < -2.0:
            trend = "declining"
        else:
            trend = "neutral"
        
        # Calculate simple moving average of OBV
        obv_ma = float(np.mean(obv[-lookback:]))
        
        return (trend, abs(momentum_pct), current_obv, obv_ma)
    except Exception as e:
        logger.warning(f"Error calculating OBV momentum: {e}")
        return ("neutral", 0.0, 0.0, 0.0)


def calculate_obv_vs_moving_average(data: pd.DataFrame, ma_period: int = 10) -> tuple:
    """
    Compare OBV to its moving average to determine strength relative to trend.
    
    Args:
        data: DataFrame with 'volume' and 'close' columns
        ma_period: Period for OBV moving average
    
    Returns:
        Tuple of (is_above_ma, distance_pct, obv_value, obv_ma_value)
        is_above_ma: True if OBV > its MA
        distance_pct: % distance between OBV and MA
        obv_value: Current OBV
        obv_ma_value: Current OBV MA
    """
    if data is None or len(data) < ma_period:
        return (False, 0.0, 0.0, 0.0)
    
    try:
        # Calculate OBV
        obv = np.zeros(len(data))
        obv[0] = data.iloc[0]['volume']
        
        for i in range(1, len(data)):
            close_diff = data.iloc[i]['close'] - data.iloc[i-1]['close']
            if close_diff > 0:
                obv[i] = obv[i-1] + data.iloc[i]['volume']
            elif close_diff < 0:
                obv[i] = obv[i-1] - data.iloc[i]['volume']
            else:
                obv[i] = obv[i-1]
        
        current_obv = float(obv[-1])
        
        # Calculate OBV moving average
        obv_ma = float(np.mean(obv[-ma_period:]))
        
        # Determine if above or below MA
        is_above = current_obv > obv_ma
        
        # Calculate distance as percentage
        if obv_ma != 0:
            distance_pct = abs((current_obv - obv_ma) / abs(obv_ma)) * 100.0
        else:
            distance_pct = 0.0
        
        return (is_above, distance_pct, current_obv, obv_ma)
    except Exception as e:
        logger.warning(f"Error calculating OBV vs MA: {e}")
        return (False, 0.0, 0.0, 0.0)


def detect_obv_strength(data: dict, hist_data=None, trend_period: int = 20, 
                       ma_period: int = 10, strength_threshold: float = 15.0) -> dict:
    """
    Comprehensive OBV strength analysis combining trend and MA comparison.
    
    Args:
        data: Stock data dictionary
        hist_data: Historical DataFrame with OHLC data
        trend_period: Lookback for trend analysis
        ma_period: Period for OBV MA
        strength_threshold: Minimum % change to consider "strong" (default 15%)
    
    Returns:
        Dictionary with OBV analysis:
        {
            'trend': 'rising'|'declining'|'neutral',
            'strength': 'strong'|'moderate'|'weak',
            'momentum_pct': float,
            'above_ma': bool,
            'ma_distance_pct': float,
            'is_strong_volume': bool,
            'signal': 'strong_bullish'|'bullish'|'neutral'|'bearish'|'strong_bearish'
        }
    """
    if hist_data is None or not isinstance(hist_data, pd.DataFrame) or hist_data.empty or len(hist_data) < max(trend_period, ma_period):
        return {
            'trend': 'neutral',
            'strength': 'weak',
            'momentum_pct': 0.0,
            'above_ma': False,
            'ma_distance_pct': 0.0,
            'is_strong_volume': False,
            'signal': 'neutral'
        }
    
    try:
        # Get momentum analysis
        trend, momentum_pct, obv_val, obv_ma = calculate_obv_momentum(hist_data, trend_period)
        
        # Get MA comparison
        is_above_ma, ma_distance_pct, current_obv, ma_val = calculate_obv_vs_moving_average(hist_data, ma_period)
        
        # Determine strength level
        if momentum_pct >= strength_threshold:
            strength = "strong"
        elif momentum_pct >= strength_threshold / 2:
            strength = "moderate"
        else:
            strength = "weak"
        
        # Determine if volume is strong (above MA and rising)
        is_strong_vol = is_above_ma and trend == "rising"
        
        # Create composite signal
        if trend == "rising" and is_above_ma and strength == "strong":
            signal = "strong_bullish"
        elif trend == "rising" and is_above_ma:
            signal = "bullish"
        elif trend == "declining" and not is_above_ma and strength == "strong":
            signal = "strong_bearish"
        elif trend == "declining" and not is_above_ma:
            signal = "bearish"
        else:
            signal = "neutral"
        
        return {
            'trend': trend,
            'strength': strength,
            'momentum_pct': momentum_pct,
            'above_ma': is_above_ma,
            'ma_distance_pct': ma_distance_pct,
            'is_strong_volume': is_strong_vol,
            'signal': signal
        }
    except Exception as e:
        logger.warning(f"Error in detect_obv_strength: {e}")
        return {
            'trend': 'neutral',
            'strength': 'weak',
            'momentum_pct': 0.0,
            'above_ma': False,
            'ma_distance_pct': 0.0,
            'is_strong_volume': False,
            'signal': 'neutral'
        }


def print_instance(instance: object) -> Dict[str, Any]:
    """
    Extract attributes of the first attribute found inside `instance`.

    This function behavior:
    - It takes only the *first* attribute of the object.
    - It assumes that the attribute itself has a __dict__.
    """

    attributes = vars(instance)

    # Original behavior:
    # result = [item for item in attrs.items()][0]
    # information = {str(i): vars(result[1])[i] for i in vars(result[1])}

    first_item = next(iter(attributes.items()))

    inner_object = first_item[1]

    return {key: vars(inner_object)[key] for key in vars(inner_object)}


class IBapi(EWrapper, EClient):
    """
    Main Interactive Brokers API wrapper.

    This class is responsible for:
    - handling IB callbacks
    - collecting historical data
    - collecting live prices
    - coordinating requests and responses for the screener
    """

    def __init__(self):
        EClient.__init__(self, self)
        self.config = Config()

        # ---- request / response state ----

        self.data = {}
        self.idInc = 100000

        # reqId -> list of bars
        self.HistoricalDt = {}

        # reqId -> bool (historicalDataEnd received)
        self.hisdtId = {}

        # symbol / ticker -> ContractDetails
        self.AllContract = {}

        self.cusip = None
        self.ticker_ = None
        self.conIds = []

        # final results returned to Flask
        self.sendToFlaskIB = {}

        self.requestInformation = {}
        self.contract = None

        # symbol -> last market price
        self.priceMarketData = {}

        # general error / state flags
        self.indicateNotCondition = False

        self.errorCodeToShow = {}
        self.warningTicker = {}

        # global frequency (used later by historical requests)
        self.addFrequency = None

        # per symbol / request window length
        self.windowLength = {}

        self.initial = 0
        self.numberOfTicker = 0

        self.Locking = threading.Lock()

        # Semaphore to limit concurrent reqHistoricalData calls
        # IB allows ~6 concurrent historical data requests; we use 10
        # to allow some headroom while preventing silent drops.
        self._hist_semaphore = threading.Semaphore(10)

        self.errorSymbol = {}
        self.otherErrorCounter = 0

        # Request delayed-frozen market data
        # (4 = delayed-frozen)
        self.reqMarketDataType(4)

        self.numberSequence = 0
        self.maxlength = None
        self.initialSec = 0
        self.customSymbol = 0
        self.nextOrderId = None

        self.contract_cache = {}  # symbol -> Contract
        self._load_contract_cache_from_disk()

        # Position management
        from position_manager import PositionManager
        self.position_manager = PositionManager()

        # ---------------------------
        # Scanner related containers
        # ---------------------------
        # reqId -> list of dict rows reported by scannerData
        self.scannerResults = {}
        # reqId -> threading.Event set by scannerDataEnd
        self.scannerEvents = {}
        # protect scanner state
        self.scannerLock = threading.Lock()

        self._scanner_results_raw = []
        self._scanner_results = []
        self._scanner_event = threading.Event()
        self._scanner_lock = threading.Lock()

        self._market_data = {}
        self._market_lock = threading.Lock()
        self._market_event = threading.Event()
        self._market_expected = 0

        # ---------------------------
        # News related containers
        # ---------------------------
        # reqId -> list of headline dicts
        self._news_data = {}
        # reqId -> bool (historicalNewsEnd received)
        self._news_done = {}
        self._news_lock = threading.Lock()
        # Subscribed provider codes discovered via reqNewsProviders()
        self._subscribed_news_providers = None  # None = not yet queried

        # reqId -> {"articleType": int, "articleText": str}
        self._article_data = {}
        # reqId -> bool (newsArticle callback received)
        self._article_done = {}

        # ---------------------------
        # Fundamental data (market cap via tick type 258)
        # ---------------------------
        self._fundamental_data = {}   # reqId -> {"MKTCAP": float, ...}
        self._fundamental_done = {}   # reqId -> bool
        self._fundamental_lock = threading.Lock()

    # =========================================================================
    # Stock Exclusion List Management
    # =========================================================================
    
    def get_excluded_stocks(self) -> set:
        """
        Load excluded stocks from JSON file.
        Returns: set of uppercase stock symbols to exclude
        """
        try:
            exclude_path = self.config.watchlists_dir / "excluded_stocks.json"
            if exclude_path.exists():
                with exclude_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(s.upper() for s in data.get("excluded", []))
        except Exception as e:
            logger.warning(f"Failed to load excluded stocks: {e}")
        return set()
    
    def save_excluded_stocks(self, symbols: list) -> bool:
        """
        Save excluded stocks to JSON file.
        Args: symbols - list of stock symbols
        Returns: True if successful, False otherwise
        """
        try:
            exclude_path = self.config.watchlists_dir / "excluded_stocks.json"
            exclude_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "excluded": [s.upper() for s in symbols],
                "last_updated": str(time.time())
            }
            
            with exclude_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(symbols)} excluded stocks")
            return True
        except Exception as e:
            logger.error(f"Failed to save excluded stocks: {e}")
            return False
    
    def add_excluded_stock(self, symbol: str) -> bool:
        """
        Add a stock symbol to the exclusion list.
        Returns: True if successful
        """
        excluded = self.get_excluded_stocks()
        if symbol.upper() not in excluded:
            excluded.add(symbol.upper())
            return self.save_excluded_stocks(list(excluded))
        return True
    
    def remove_excluded_stock(self, symbol: str) -> bool:
        """
        Remove a stock symbol from the exclusion list.
        Returns: True if successful
        """
        excluded = self.get_excluded_stocks()
        if symbol.upper() in excluded:
            excluded.discard(symbol.upper())
            return self.save_excluded_stocks(list(excluded))
        return True
    
    def is_stock_excluded(self, symbol: str) -> bool:
        """
        Check if a stock symbol is in the exclusion list.
        Returns: True if excluded, False otherwise
        """
        return symbol.upper() in self.get_excluded_stocks()

    def _to_dict(self, obj):
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, (list, tuple)):
            return [self._to_dict(x) for x in obj]

        if hasattr(obj, "__dict__"):
            return {
                k: self._to_dict(v)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }

        return str(obj)

    def _load_contract_cache_from_disk(self):

        if not self.config.enable_contract_cache:
            logger.info("Contract cache disabled by config")
            return

        cache_path = self.config.cache_path

        if not cache_path.exists():
            return

        try:
            with cache_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return

        now = time.time()

        for symbol, entry in raw.items():
            ts = entry.get("ts")
            data = entry.get("contract")

            if not ts or not data:
                continue

            # TTL check
            if now - ts > self.config.contract_cache_ttl_sec:
                logger.info(
                    "Contract cache expired for %s (age=%.1fs, ttl=%ss)",
                    symbol,
                    now - ts,
                    self.config.contract_cache_ttl_sec,
                )
                continue

            try:
                cached_exchange = data["exchange"]
                cached_primary = data.get("primaryExchange", "")
                # Always route through SMART; preserve specific exchange
                # as primaryExchange for listing venue identification.
                if cached_exchange != "SMART" and not cached_primary:
                    cached_primary = cached_exchange
                c = self.marketContract(
                    data["symbol"],
                    data["secType"],
                    "SMART",
                    cached_primary,
                    data["currency"],
                )
                # Restore conId so news fetch works from cached contracts
                if data.get("conId"):
                    c.conId = int(data["conId"])
                self.contract_cache[symbol] = c
            except Exception:
                continue

    def _save_contract_cache_to_disk(self, updated_symbols=None):

        if not self.config.enable_contract_cache:
            return

        updated_symbols = set(updated_symbols or [])

        cache_path = self.config.cache_path

        # load existing file so we can preserve old timestamps
        try:
            if cache_path.exists():
                with cache_path.open("r", encoding="utf-8") as f:
                    existing = json.load(f)
            else:
                existing = {}
        except Exception:
            existing = {}

        out = {}

        now = time.time()

        for symbol, contract in self.contract_cache.items():

            entry = existing.get(symbol, {})

            # keep old ts by default
            ts = entry.get("ts")

            # only refresh when this symbol was really updated
            if symbol in updated_symbols or ts is None:
                ts = now

            try:
                out[symbol] = {
                    "ts": ts,
                    "contract": {
                        "symbol": contract.symbol,
                        "secType": contract.secType,
                        "exchange": contract.exchange,
                        "primaryExchange": getattr(contract, "primaryExchange", ""),
                        "currency": contract.currency,
                        "conId": getattr(contract, "conId", None),
                    }
                }
            except Exception:
                pass

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _select_best_contract(contracts, requested_symbol=None):
        """
        Pick the most suitable contract from IB contractDetails results.

        Priority:
        1) restrict to requested_symbol (if provided)
        2) primaryExchange present
        3) exchange == SMART
        4) fallback: first entry
        """

        if not contracts:
            return None

        candidates = contracts

        # 1) restrict to symbol matches first (if provided)
        if requested_symbol:
            symbol_matches = [
                c for c in contracts
                if c.get("symbol") == requested_symbol
            ]
            if symbol_matches:
                candidates = symbol_matches

        # 2) has primaryExchange
        for c in candidates:
            if c.get("primaryExchange"):
                return c

        # 3) SMART exchange
        for c in candidates:
            if c.get("exchange") == "SMART":
                return c

        # 4) fallback
        return candidates[0]

    def nextValidId(self, order_id):
        """
        Callback fired by IB once the connection is established
        and the first valid order id is received.
        """
        self.nextOrderId = order_id
        # Discover subscribed news providers as soon as connected
        try:
            self.reqNewsProviders()
        except Exception:
            pass

    def checkForConnection(self):
        """
        Busy-wait loop until the IB connection is considered ready.

        This method logic:
        - waits until a valid order id is present
        - stops after ~15 seconds
        """

        time_to_wait = 0

        while True:
            if isinstance(self.nextOrderId, int):
                print("connected")
                break

            print("waiting for connection")
            time.sleep(1)

            time_to_wait += 1

            if time_to_wait > 15:
                self.indicateNotCondition = True
                break

    def tickString(self, req_id, tick_type, value):
        """
        Callback for string-based tick data.

        tickType 47 = FUNDAMENTAL_RATIOS (generic ticks like 258) — semicolon-delimited key=value pairs
        containing MKTCAP (market cap in millions), among other fields.
        
        Format from IB: "key1=value1;key2=value2;..." (e.g., "MKTCAP=1234.5;PER=15.2")
        """
        # Handle FUNDAMENTAL_RATIOS (tick type 47, used for generic ticks like 258)
        if tick_type == 47 and value:
            try:
                ratios = {}
                # Split by semicolon to get key=value pairs
                for pair in value.split(";"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        k_clean = k.strip()
                        v_clean = v.strip()
                        ratios[k_clean] = v_clean
                        
                        # Log extraction of MKTCAP specifically for debugging
                        if k_clean == "MKTCAP":
                            logger.debug("Received MKTCAP tick: %s -> %s", k_clean, v_clean)
                
                with self._fundamental_lock:
                    self._fundamental_data[req_id] = ratios
                    self._fundamental_done[req_id] = True
                    
                # Log all keys for debugging
                if ratios:
                    logger.debug("Fundamental data received (reqId=%s): keys=%s", req_id, list(ratios.keys()))
            except Exception as e:
                logger.debug("Error parsing fundamental data (reqId=%s): %s", req_id, e)
                with self._fundamental_lock:
                    self._fundamental_done[req_id] = True

    def tickSize(self, req_id, tick_type, size):

        # tickType 8 = VOLUME
        if tick_type == 8:

            with self._market_lock:

                if req_id in self._market_data:
                    self._market_data[req_id]["volume"] = size

    def historicalData(self, req_id, bar):
        """
        Callback for every historical bar received.
        Appends one bar to self.HistoricalDt[reqId].
        """

        current_bar = [
            bar.date,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            float(bar.volume),
        ]

        # Guard against late callbacks for already-cleaned-up request IDs
        if req_id not in self.HistoricalDt:
            return

        # Assumes the list is already initialized elsewhere
        self.HistoricalDt[req_id].append(current_bar)

    def historicalDataEnd(self, req_id: int, start: str, end: str):
        """
        Callback fired when all historical bars for reqId were sent.
        """

        super().historicalDataEnd(req_id, start, end)

        print("HistoricalDataEnd. ReqId:", req_id, "from", start, "to", end)

        # mark this request as completed (guard against stale req_ids)
        if req_id in self.hisdtId:
            self.hisdtId[req_id] = True

    # ------------------------------------------------------------------
    # News callbacks
    # ------------------------------------------------------------------

    def historicalNews(self, request_id, time_str, provider_code, article_id, headline):
        """
        Callback for each historical news headline received from IBKR.
        """
        logger.debug("historicalNews reqId=%s provider=%s headline=%.80s", request_id, provider_code, headline)
        with self._news_lock:
            # Ensure the request ID has been initialized by fetchNews
            # If not, this might be a stale callback, so silently ignore it
            if request_id not in self._news_data:
                logger.debug("historicalNews for unknown reqId=%s (may be stale callback), ignoring", request_id)
                return
            self._news_data[request_id].append({
                "time": time_str,
                "provider": provider_code,
                "articleId": article_id,
                "headline": headline,
            })

    def historicalNewsEnd(self, request_id, has_more):
        """
        Callback fired when all historical news for request_id were sent.
        """
        with self._news_lock:
            count = len(self._news_data.get(request_id, []))
            logger.info("historicalNewsEnd reqId=%s headlines=%d hasMore=%s", request_id, count, has_more)
            if request_id in self._news_done:
                self._news_done[request_id] = True
            else:
                logger.debug("historicalNewsEnd for unknown reqId=%s (may be stale callback), ignoring", request_id)

    def newsProviders(self, news_providers):
        """
        Callback fired when reqNewsProviders() returns the list of
        subscribed news providers.  We log the result and store the
        provider codes so fetchNews() only requests subscribed ones.
        """
        if news_providers:
            codes = [np.code for np in news_providers]
            display = [f"{np.code} ({np.name})" for np in news_providers]
            logger.info("Subscribed news providers: %s", ", ".join(display))
            self._subscribed_news_providers = "+".join(codes)
        else:
            logger.warning(
                "No news providers subscribed.  "
                "Enable at least 'Benzinga General News (BZ:BZ_FREE)' in "
                "IBKR Account Management → Settings → Market Data Subscriptions "
                "to see news headlines. Will use fallback provider list."
            )
            # Don't set to empty string - use fallback in fetchNews
            self._subscribed_news_providers = None

    def newsArticle(self, request_id, article_type, article_text):
        """
        Callback fired when reqNewsArticle() returns the article body.
        articleType: 0 = plain text, 1 = HTML.
        """
        logger.info("newsArticle reqId=%s type=%s len=%d", request_id, article_type,
                    len(article_text) if article_text else 0)
        self._article_data[request_id] = {
            "articleType": article_type,
            "articleText": article_text,
        }
        self._article_done[request_id] = True

    def tickPrice(self, req_id, tick_type, price, attrib):
        """
        Callback for live / delayed market price updates.

        - Supports tickType 56 (LAST_PERCENT) as a primary source.
        - Fallback: capture LAST (4) and CLOSE (9) and compute pct when both present.
        The current implementation stores the last price
        using self.symbolData as a key.
        """

        key = getattr(self, "symbolData", None)
        if key is not None:
            try:
                self.priceMarketData[key] = price
            except Exception:
                # defensive: don't crash on write errors
                pass

        # ------------------ primary: LAST_PERCENT ------------------
        # IB tickType 56 = LAST_PERCENT (percentage change)
        try:
            if tick_type == 56:
                with self._market_lock:
                    if req_id in self._market_data:
                        self._market_data[req_id].setdefault("symbol", None)
                        # store percent directly
                        self._market_data[req_id]["percent"] = float(price) if price is not None else None

                        # mark progress
                        if isinstance(self._market_expected, int) and self._market_expected > 0:
                            self._market_expected -= 1
                        # set event when done
                        if self._market_expected <= 0:
                            self._market_event.set()
                return
        except Exception:
            # don't raise from callback
            pass

        # ------------------ fallback: LAST (4) and CLOSE (9) to compute percent ------------------
        try:
            with self._market_lock:
                if req_id not in self._market_data:
                    # We only bother storing fallback data for requests we created.
                    return

                entry = self._market_data[req_id]
                # capture last / close if tick types arrive
                if tick_type == 4:  # LAST
                    entry["last"] = float(price) if price is not None else None
                elif tick_type == 9:  # CLOSE
                    entry["close"] = float(price) if price is not None else None

                # if both present, compute percent once
                last = entry.get("last")
                close = entry.get("close")
                if last is not None and close not in (None, 0):
                    entry["percent"] = ((last - close) / close) * 100.0

                    if isinstance(self._market_expected, int) and self._market_expected > 0:
                        self._market_expected -= 1
                    if self._market_expected <= 0:
                        self._market_event.set()
        except Exception:
            # swallow any callback exceptions
            pass

    def error(self, req_id, error_code, error_string):

        # IB error codes to completely ignore
        SILENT_CODES = {
            504,  # Not connected
            2104,  # Market data farm connection OK
            2106,  # HMDS connection OK
            2158,  # Sec-def data farm connection OK
            2108,  # Market data farm inactive
            2119,  # Market data farm connection inactive
            10167,  # Requested market data is not subscribed
        }

        # completely ignore
        if error_code in SILENT_CODES:
            return

        # optional: mute based on text config
        msg = error_string.lower()
        if any(m.lower() in msg for m in self.config.muted_ibapi_errors):
            return

        # Silently handle fundamental-data errors (e.g. 10358 "Fundamentals
        # data is not allowed" when the account lacks a subscription).
        # Unblock the wait loop but do NOT store in warningTicker.
        if req_id in self._fundamental_done and not self._fundamental_done[req_id]:
            logger.info("Fundamental request %s got error %s: %s — unblocking (suppressed)", req_id, error_code, error_string)
            with self._fundamental_lock:
                self._fundamental_done[req_id] = True
            return

        # Handle news-request errors (e.g. "Rejected - Invalid value in field # 48" when provider not subscribed).
        # Valid headlines from other providers may still arrive via historicalNews / historicalNewsEnd.
        with self._news_lock:
            is_news_request = req_id in self._news_done
        
        if is_news_request:
            logger.warning("News request %s got error %s: %s — suppressed, will continue waiting for headlines", 
                          req_id, error_code, error_string)
            # Mark as done to unblock wait loop - timeout will handle cases where no data arrives
            with self._news_lock:
                if req_id in self._news_done and not self._news_done[req_id]:
                    self._news_done[req_id] = True
            return

        # store but don't print
        self.errorCodeToShow[error_code] = error_string

        # map to ticker if possible
        if req_id in self.errorSymbol and error_code != 300:

            my_symbol = self.errorSymbol[req_id]["ticker"]
            my_cusip = self.errorSymbol[req_id]["cusip"]

            self.warningTicker[req_id] = [
                my_symbol,
                my_cusip,
                f"Error: {error_code}. {error_string}",
            ]

        elif req_id not in self.errorSymbol and error_code != 300:

            self.otherErrorCounter += 1
            # Use a large offset to avoid colliding with screening theid values
            other_key = 900000 + self.otherErrorCounter

            self.warningTicker[other_key] = [
                req_id,
                "Internal Error",
                f"Error: {error_code}. {error_string}",
            ]

        # Unblock the contract-details waiting loop in getDataResult().
        # When IB rejects a contract lookup (e.g. error 200 "No security
        # definition") the contractDetailsEnd callback never fires, so
        # requestInformation stays False and the thread idles for the full
        # timeout.  Signal completion here so it can proceed immediately.
        if req_id in self.requestInformation and not self.requestInformation[req_id]:
            self.requestInformation[req_id] = True

        # Unblock the article-body waiting loop in fetchNewsArticle().
        if req_id in self._article_done and not self._article_done[req_id]:
            self._article_done[req_id] = True

        # Unblock the historical-data waiting loop in getDataResult().
        # When IB rejects a request (pacing violation, no data, etc.) the
        # historicalDataEnd callback never fires, so hisdtId stays False and
        # the thread sleeps for the full timeout (30 s).  Signal completion
        # here so the thread can proceed immediately with whatever bars
        # (if any) were already received.
        if req_id in self.hisdtId and not self.hisdtId[req_id]:
            self.hisdtId[req_id] = True

    def contractDetails(self, req_id, contract_details):
        """
        IB callback for each contract detail received.

        Extracts:
        - symbol
        - conId (primary IB identifier)
        - cusip (direct or derived from ISIN)
        - isin
        - exchange info

        and stores it in self.data[req_id]
        """

        super().contractDetails(req_id, contract_details)
        c = contract_details.contract

        cusip = None
        isin = None

        # ----------------------------
        # Extract identifiers
        # ----------------------------
        try:
            if contract_details.secIdList:
                for sec in contract_details.secIdList:
                    if sec.tag == "CUSIP":
                        cusip = sec.value
                    elif sec.tag == "ISIN":
                        isin = sec.value
        except Exception:
            pass

        # ----------------------------
        # Derive CUSIP from ISIN if needed
        # ----------------------------
        if cusip is None and isin:

            try:
                cusip = isin[2:-1]
            except Exception:
                cusip = None

        # ----------------------------
        # Build contract info
        # ----------------------------
        contract_info = {
            "symbol": c.symbol,
            "conId": c.conId,
            "cusip": cusip,
            "isin": isin,
            "secType": c.secType,
            "exchange": c.exchange,
            "primaryExchange": c.primaryExchange,
            "currency": c.currency,
            "longName": getattr(contract_details, "longName", None)
        }

        # store result
        if req_id in self.data:
            self.data[req_id].append(contract_info)

    def contractDetailsEnd(self, req_id):
        """
        IB callback fired when all contract details for req_id are received.
        """

        if req_id in self.requestInformation:
            self.requestInformation[req_id] = True

        print("\ncontractDetails End\n")

    def findContractDetails(self, id_sec, sec_id, sec_id_type, symbol, contract_id=None):
        """
        Request contract details for a stock.

        Priority:
        1) Use conId when provided
        2) Use CUSIP when provided
        3) Fallback to symbol
        """

        self.requestInformation[id_sec] = False

        contract = Contract()

        # --------------------------------------------------
        # NEW: Use conId FIRST if available
        # --------------------------------------------------
        if contract_id not in (None, "", "None"):

            contract.conId = int(contract_id)
            contract.exchange = "SMART"

        # --------------------------------------------------
        # Existing CUSIP logic
        # Skip CINS codes (international CUSIPs starting with
        # a letter like G/Y) — IB doesn't resolve them via
        # secIdType="CUSIP"; fall through to symbol lookup.
        # --------------------------------------------------
        elif (
                sec_id
                and sec_id != "nan"
                and sec_id_type == "CUSIP"
                and not str(sec_id).lower().startswith("custom")
                and str(sec_id)[0:1].isdigit()
        ):

            contract.secIdType = "CUSIP"
            contract.secId = sec_id

            if symbol and symbol != "nan":
                contract.symbol = symbol

        # --------------------------------------------------
        # Existing symbol fallback
        # --------------------------------------------------
        else:
            if symbol and symbol != "nan":
                contract.symbol = symbol
            elif sec_id and sec_id != "nan":
                contract.symbol = sec_id

        contract.currency = "USD"
        contract.secType = "STK"

        logger.debug(
            "reqContractDetails id=%s symbol=%s conId=%s secIdType=%s secId=%s exchange=%s",
            id_sec,
            getattr(contract, "symbol", None),
            getattr(contract, "conId", None),
            getattr(contract, "secIdType", None),
            getattr(contract, "secId", None),
            getattr(contract, "exchange", None),
        )

        self.reqContractDetails(id_sec, contract)

    @staticmethod
    def marketContract(symbol, sec_type, exchange, primary_exchange, currency):
        """
        Build and return an IB Contract object for market data / orders.
        """

        contract = Contract()

        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.primaryExchange = primary_exchange
        contract.currency = currency

        return contract

    def getData(self, contract, form, theid, override_tf=None, override_lookback=None):
        """
        Request historical market data for a contract.

        When override_tf and override_lookback are provided they are used
        directly instead of being derived from the form.  This enables
        per-indicator timeframe support where each unique timeframe gets
        its own historical data request.
        """
        # ------------------------------------------------------------------
        # Determine the maximum lookback required by all indicators
        # ------------------------------------------------------------------
        if override_lookback is not None:
            lookback_window = override_lookback
            if self.maxlength is None:
                self.maxlength = lookback_window
        else:
            maxlength = []

            # Primary indicator fields
            for key in ("FastSMA", "MediumSMA", "SlowSMA", "VWAP", "RSI",
                        "AverageVolume", "FastEMA", "SlowEMA", "OBV", "ATR",
                        "Cross50SMA", "Cross200SMA"):
                if key in form and form[key] != "":
                    try:
                        maxlength.append(int(form[key]))
                    except Exception:
                        # ignore non-integer entries
                        pass

            # Secondary indicator fields (a duplicated set)
            for key in ("FastSMA1", "MediumSMA1", "SlowSMA1", "VWAP1", "RSI1",
                        "AverageVolume1", "FastEMA1", "SlowEMA1", "OBV1", "ATR1"):
                if key in form and form[key] != "":
                    try:
                        maxlength.append(int(form[key]))
                    except Exception:
                        pass

            if len(maxlength) > 0:
                max_required = max(maxlength) + 1
                if self.maxlength is None:
                    self.maxlength = max_required
                lookback_window = max_required
            else:
                # Default lookback when no indicator requires a window
                lookback_window = 252

        # ------------------------------------------------------------------
        # Map friendly timeframes to IB barSize strings and approximate seconds
        # ------------------------------------------------------------------
        # seconds are approximate bar duration in seconds
        TIMEFRAME_TO_IB = {
            "1 min": ("1 min", 60),
            "2 min": ("2 mins", 120),
            "5 min": ("5 mins", 300),
            "15 min": ("15 mins", 900),
            "1 hour": ("1 hour", 3600),
            "1 day": ("1 day", 86400),
            "1 year": ("1 day", 31536000),  # keep 1 year as daily bars but larger timeperiod was updated to differnt then  daily x 365 for days 3/21/26
        }

        # ------------------------------------------------------------------
        # Determine the selected timeframe
        # ------------------------------------------------------------------
        if override_tf is not None:
            # Caller supplied the exact timeframe – skip detection
            selected_tf = override_tf
            ib_bar_size, bar_seconds = TIMEFRAME_TO_IB.get(selected_tf, ("1 day", 86400))
            requested_tfs = [selected_tf]
        else:
            # Collect requested per-indicator timeframes
            requested_tfs = []
            per_indicator_tf_fields = (
                "FastSMA_tf",
                "FastSMA1_tf",
                "MediumSMA_tf",
                "MediumSMA1_tf",
                "SlowSMA_tf",
                "SlowSMA1_tf",
                "VWAP_tf",
                "VWAP1_tf",
                "RSI_tf",
                "RSI1_tf",
                "FastEMA_tf",
                "FastEMA1_tf",
                "SlowEMA_tf",
                "SlowEMA1_tf",
                "OBV_tf",
                "OBV1_tf",
                "ATR_tf",
                "ATR1_tf",
                "PrevClose_tf",
                "PrevClose1_tf",
                "LowOfDay_tf",
                "LowOfDay1_tf",
                "HighOfDay_tf",
                "HighOfDay1_tf",
                "averageVolume_tf",
                "averageVolume1_tf",
                "relativeVolume_tf",
                "relativeVolume1_tf",
                "Cross50SMA_tf",
                "Cross200SMA_tf",
            )

            for tf_field in per_indicator_tf_fields:
                if tf_field in form and form[tf_field] not in (None, ""):
                    requested_tfs.append(form[tf_field])

            # Fallback to the global selector if no per-indicator TFs were provided
            if not requested_tfs:
                if getattr(self, "addFrequency", None):
                    requested_tfs.append(self.addFrequency)
                elif "addFrequency" in form and form["addFrequency"] not in (None, ""):
                    requested_tfs.append(form["addFrequency"])
                else:
                    requested_tfs.append("1 day")

            requested_tfs = [tf for tf in requested_tfs if tf in TIMEFRAME_TO_IB]
            if not requested_tfs:
                requested_tfs = ["1 day"]

            def tf_seconds(tf):
                return TIMEFRAME_TO_IB.get(tf, ("1 day", 86400))[1]

            selected_tf = min(requested_tfs, key=tf_seconds)
            ib_bar_size, bar_seconds = TIMEFRAME_TO_IB.get(selected_tf, ("1 day", 86400))

        # ------------------------------------------------------------------
        # Determine an appropriate 'timeperiod' string for IB's reqHistoricalData
        # The goal is to request enough history to cover `lookback_window` bars at chosen gran.
        # For intraday minute bars we approximate 390 trading minutes/day (regular hours).
        # With extended hours enabled, add ~2 hours pre-market + ~4 hours after-hours = +360 minutes
        # ------------------------------------------------------------------
        
        # Check if extended hours are enabled (affects bar count per day)
        enable_extended = form.get("EnableExtendedHours", False)
        include_overnight = form.get("IncludeOvernightData", False)
        
        if bar_seconds < 3600:
            # intraday minute-based bars
            minutes_per_trading_day = 390  # US regular session (9:30 AM - 4 PM ET)
            
            # Add extra minutes for extended hours if enabled
            if enable_extended:
                # Pre-market: 4 AM - 9:30 AM = 5.5 hours = 330 minutes
                # After-hours: 4 PM - 8 PM = 4 hours = 240 minutes
                # Total extra: 570 minutes
                minutes_per_trading_day += 570
            
            if include_overnight:
                # Overnight: 8 PM - 4 AM next day = 8 hours = 480 minutes
                # (Note: this is typically very low volume but still calculated)
                minutes_per_trading_day += 480
            
            bars_per_day = (minutes_per_trading_day * 60) / bar_seconds
            # avoid division by zero and ensure at least 1 bar/day
            if bars_per_day < 1:
                bars_per_day = 1
            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            # Account for weekends/holidays: request ~1.4x more calendar days to ensure we get enough trading days
            # For RVOL calculations on intraday bars, we need complete days of history
            calendar_days_needed = int(math.ceil(days_needed * 1.4))
            timeperiod = f"{calendar_days_needed} D"
        elif ib_bar_size == "1 hour":
            # estimate ~6.5 trading hours/day for regular hours
            bars_per_day = 6.5

            # Add extra hours for extended hours if enabled
            if enable_extended:
                # Pre-market: ~5.5 hours, After-hours: ~4 hours
                bars_per_day += 9.5

            if include_overnight:
                # Overnight: ~8 hours
                bars_per_day += 8

            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            timeperiod = f"{days_needed} D"
            
            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            timeperiod = f"{days_needed} D"
        else:
            # daily bars
            if lookback_window < 365:
                timeperiod = f"{lookback_window} D"
            else:
                # convert to years (approx 252 trading days/year)
                years = int(math.ceil(float(lookback_window) / 252.0))
                if years < 1:
                    years = 1
                timeperiod = f"{years} Y"

        # ------------------------------------------------------------------
        # Make the historical data request using the selected bar size
        # Acquire semaphore to limit concurrent IB historical requests
        # ------------------------------------------------------------------
        idreqHistDt = theid

        try:
            logger.info(
                "[TF-DEBUG] %s | requested_tfs=%s | selected_tf=%s | ib_bar_size=%s | timeperiod=%s | lookback_window=%s",
                getattr(contract, "symbol", "<no-symbol>"),
                requested_tfs,
                selected_tf,
                ib_bar_size,
                timeperiod,
                lookback_window,
            )
        except Exception:
            pass

        self._hist_semaphore.acquire()
        try:
            try:
                # Determine if extended hours should be included
                # useRTH = 1 means Regular Trading Hours only (9:30 AM - 4 PM EST)
                # useRTH = 0 means include pre-market (4 AM - 9:30 AM) and after-hours (4 PM - 8 PM) and overnight
                enable_extended = form.get("EnableExtendedHours", False)
                include_overnight = form.get("IncludeOvernightData", False)
                
                # If extended hours or overnight data is requested, include all hours (useRTH=0)
                useRTH = 0 if (enable_extended or include_overnight) else 1
                
                self.reqHistoricalData(
                    idreqHistDt,
                    contract,
                    "",
                    timeperiod,
                    ib_bar_size,
                    "TRADES",
                    0,
                    useRTH,
                    False,
                    [],
                )
            except Exception:
                # keep behavior safe: log but don't crash
                try:
                    logger.exception(
                        "reqHistoricalData failed for %s with bar size %s; falling back to 1 day",
                        getattr(contract, "symbol", "<unknown>"),
                        ib_bar_size,
                    )
                except Exception:
                    pass
                # fallback to a safe daily request
                try:
                    self.reqHistoricalData(
                        idreqHistDt,
                        contract,
                        "",
                        timeperiod,
                        "1 day",
                        "TRADES",
                        0,
                        1,
                        False,
                        [],
                    )
                except Exception:
                    # if fallback also fails, raise so caller can notice
                    raise
        finally:
            self._hist_semaphore.release()

        # Store the required window length per symbol
        try:
            self.windowLength[contract.symbol] = lookback_window
        except Exception:
            # defensive: if contract has no symbol, skip assignment
            pass

    # ------------------------------------------------------------------
    # Multi-timeframe helpers
    # ------------------------------------------------------------------

    _KNOWN_TFS = {"1 min", "2 min", "5 min", "15 min", "1 hour", "1 day", "1 year"}

    # Maps indicator result key -> form field that holds its per-indicator TF
    _INDICATOR_TF_FIELD = {
        "smaFast": "FastSMA_tf",
        "smaFast1": "FastSMA1_tf",
        "smaMedium": "MediumSMA_tf",
        "smaMedium1": "MediumSMA1_tf",
        "smaSlow": "SlowSMA_tf",
        "smaSlow1": "SlowSMA1_tf",
        "vwap": "VWAP_tf",
        "vwap1": "VWAP1_tf",
        "rsi": "RSI_tf",
        "rsi1": "RSI1_tf",
        "emaFast": "FastEMA_tf",
        "emaFast1": "FastEMA1_tf",
        "emaSlow": "SlowEMA_tf",
        "emaSlow1": "SlowEMA1_tf",
        "obv": "OBV_tf",
        "obv1": "OBV1_tf",
        "atr": "ATR_tf",
        "atr1": "ATR1_tf",
        "averageVolume": "averageVolume_tf",
        "averageVolume1": "averageVolume1_tf",
        "volumeIndicator": "Volume_tf",
        "volumeIndicator1": "Volume1_tf",
        "relativeVolume": "relativeVolume_tf",
        "relativeVolume1": "relativeVolume1_tf",
        "prevClose": "PrevClose_tf",
        "prevClose1": "PrevClose1_tf",
        "lowOfDay": "LowOfDay_tf",
        "lowOfDay1": "LowOfDay1_tf",
        "highOfDay": "HighOfDay_tf",
        "highOfDay1": "HighOfDay1_tf",
        "cross50SMA": "Cross50SMA_tf",
        "cross50SMA_above": "Cross50SMA_tf",
        "cross50SMA_below": "Cross50SMA_tf",
        "cross50SMA_either": "Cross50SMA_tf",
        "cross50SMA_value": "Cross50SMA_tf",
        "cross50SMA_pctFromSMA": "Cross50SMA_tf",
        "cross50SMA_isAbove": "Cross50SMA_tf",
        "cross200SMA": "Cross200SMA_tf",
        "cross200SMA_above": "Cross200SMA_tf",
        "cross200SMA_below": "Cross200SMA_tf",
        "cross200SMA_either": "Cross200SMA_tf",
        "cross200SMA_value": "Cross200SMA_tf",
        "cross200SMA_pctFromSMA": "Cross200SMA_tf",
        "cross200SMA_isAbove": "Cross200SMA_tf",
        "breakHigh": "BreakHigh_tf",
        "pullbackPct": "PullbackPct_tf",
        "pullbackPct1": "PullbackPct_tf",
        "pullbackPct2": "PullbackPct2_tf",
        "pullbackPct2_1": "PullbackPct2_tf",
        "fibPullback": "FibPullback_tf",
        "fibPullback1": "FibPullback_tf",
        "gapPullback": "GapPullback_tf",
        "gapPullback1": "GapPullback_tf",
        "upGap": "UpGap_tf",
        "upGap1": "UpGap_tf",
        "downGap": "DownGap_tf",
        "downGap1": "DownGap_tf",
        "fibGap": "FibGap_tf",
        "Pivot": "Pivot_tf",
        "Pivot1": "Pivot_tf",
    }

    @staticmethod
    def _build_tf_plan(form):
        """
        Determine which unique timeframes are needed and the max lookback
        window for each.

        Returns (default_tf, tf_plan) where tf_plan is {tf_str: max_lookback}.
        """
        KNOWN = IBapi._KNOWN_TFS

        # Global / default timeframe
        default_tf = form.get("addFrequency") or "1 day"
        if default_tf not in KNOWN:
            default_tf = "1 day"

        # (value_key, tf_form_key, default_lookback)
        LOOKBACK_INDICATORS = [
            ("FastSMA", "FastSMA_tf", 10),
            ("FastSMA1", "FastSMA1_tf", 10),
            ("MediumSMA", "MediumSMA_tf", 10),
            ("MediumSMA1", "MediumSMA1_tf", 10),
            ("SlowSMA", "SlowSMA_tf", 50),
            ("SlowSMA1", "SlowSMA1_tf", 50),
            ("VWAP", "VWAP_tf", 20),
            ("VWAP1", "VWAP1_tf", 20),
            ("RSI", "RSI_tf", 14),
            ("RSI1", "RSI1_tf", 14),
            ("FastEMA", "FastEMA_tf", 21),
            ("FastEMA1", "FastEMA1_tf", 21),
            ("SlowEMA", "SlowEMA_tf", 21),
            ("SlowEMA1", "SlowEMA1_tf", 21),
            ("OBV", "OBV_tf", 14),
            ("OBV1", "OBV1_tf", 14),
            ("ATR", "ATR_tf", 14),
            ("ATR1", "ATR1_tf", 14),
            ("AverageVolume", "averageVolume_tf", 14),
            ("AverageVolume1", "averageVolume1_tf", 14),
            ("Volume", "Volume_tf", 1),
            ("Volume1", "Volume1_tf", 1),
            ("RelativeVolume", "relativeVolume_tf", 5),
            ("RelativeVolume1", "relativeVolume1_tf", 5),
            ("Cross50SMA", "Cross50SMA_tf", 50),
            ("Cross200SMA", "Cross200SMA_tf", 200),
        ]

        tf_plan = {}  # {tf_str: max_lookback}

        for val_key, tf_key, default_lb in LOOKBACK_INDICATORS:
            if val_key in form and form[val_key] not in (None, ""):
                try:
                    lookback = int(form[val_key]) + 1
                except Exception:
                    lookback = default_lb + 1
            else:
                continue
            tf = form.get(tf_key)
            if not tf or tf not in KNOWN:
                tf = default_tf
            tf_plan[tf] = max(tf_plan.get(tf, 0), lookback)

        # Indicators that always use the default TF (no per-indicator TF field)
        for val_key, default_lb in [("BreakHigh", 5)]:
            if val_key in form and form[val_key] not in (None, ""):
                try:
                    lookback = int(form[val_key]) + 1
                except Exception:
                    lookback = default_lb + 1
                tf_plan[default_tf] = max(tf_plan.get(default_tf, 0), lookback)

        # Indicators with TF fields but small fixed lookback
        for comp_key, tf_key, lb in [
            ("ComparisonPrevClose", "PrevClose_tf", 5),
            ("ComparisonLowOfDay", "LowOfDay_tf", 2),
            ("ComparisonHighOfDay", "HighOfDay_tf", 2),
        ]:
            if form.get(comp_key, "Not used") != "Not used":
                tf = form.get(tf_key)
                if not tf or tf not in KNOWN:
                    tf = default_tf
                tf_plan[tf] = max(tf_plan.get(tf, 0), lb)

        if not tf_plan:
            tf_plan[default_tf] = 252

        return default_tf, tf_plan

    @staticmethod
    def getIndicators(data, cusip, contract, form, net_position, symbol, market_cap=None):
        """
        Build and compute all configured indicators for one symbol.

        Requirements fixed:
        - separates full historical data (result_full) from the current session bars (result_session)
          so session-only indicators (HighOfDay/LowOfDay/RelativeVolume/Pivot) use the correct data.
        - pivot points are computed from the previous trading day's H/L/C.
        - averageVolume uses daily aggregation when intraday bars are present.
        - relativeVolume is calculated as (today cumulative volume) / (avg daily volume over lookback days)
          which is the common market definition and matches TWS-like behaviour.
        - defensive: attempts to parse date column into pd.Timestamp; falls back to string heuristics.

        Returns dict of indicators (same keys as before).
        """
        # --- build dataframe and normalize the datetime index ---
        result_full = pd.DataFrame(data, columns=["date", "open", "high", "low", "close", "volume"])

        # try to coerce 'date' into pandas datetime (handles ints, strings)
        # many IB historical bars come as 'YYYYMMDD' or epoch-like ints; try both
        def _to_datetime(x):
            try:
                return pd.to_datetime(x, unit="s")
            except Exception:
                pass
            try:
                # If it's integer like 20260217 or string '20260217'
                return pd.to_datetime(str(x), format="%Y%m%d", errors="coerce")
            except Exception:
                return pd.to_datetime(x, errors="coerce")

        result_full["ts"] = result_full["date"].apply(_to_datetime)
        # if parsing failed entirely, try a looser parse
        if result_full["ts"].isna().all():
            result_full["ts"] = pd.to_datetime(result_full["date"], errors="coerce")

        # If still NaT, keep original 'date' as string index to preserve previous logic
        if result_full["ts"].isna().any():
            # best-effort: fill NaT with forward fill of last valid
            result_full["ts"] = result_full["ts"].ffill().bfill()

        # set a proper datetime index
        result_full = result_full.set_index("ts", drop=False).sort_index()

        # determine unique trading dates in the dataset (as date objects)
        unique_dates = result_full.index.normalize().unique()
        unique_dates = sorted([d for d in unique_dates if pd.notna(d)])

        # latest trading date (session we consider 'today' in this run)
        if len(unique_dates) == 0:
            # no usable timestamps: fallback to original behaviour using raw array
            result = result_full.set_index("date")
            indicators = {"volume": last_value(result.volume), "symbol": getattr(contract, "symbol", symbol),
                          "cusip": cusip, "close": last_value(result.close) if not result.close.empty else None,
                          "netPosition": int(net_position) if net_position is not None else 0}
            return indicators

        latest_date = unique_dates[-1]
        # construct session dataframe: all rows whose normalized date == latest_date
        mask_session = result_full.index.normalize() == latest_date
        result_session = result_full.loc[mask_session].copy()

        # full history excluding incomplete current session if the user wants previous-close logic
        result_history = result_full.copy()

        # --- helper: daily aggregated volumes (for averageVolume / relativeVolume) ---
        # if data has multiple bars per date -> intraday, else daily bars
        grouped = result_history.groupby(result_history.index.normalize())
        daily_volume = grouped["volume"].sum()

        def _avg_daily_volume(_lookback):
            # use last `_lookback` complete days (exclude current incomplete session)
            days = daily_volume.copy()
            if len(days) > 1:
                # Exclude the last entry (today's partial session) and take
                # up to _lookback previous complete days.
                complete_days = days.iloc[:-1]
                days_to_use = complete_days.iloc[-_lookback:]
            else:
                days_to_use = days.iloc[-_lookback:]
            if days_to_use.empty:
                return float(np.nan)
            return float(days_to_use.mean())
        
        def _avg_volume_by_time_of_day(_lookback_days):
            """
            Calculate average volume for each time-of-day slot across historical days.
            
            Returns dict: {time_str: avg_volume}
            This is used for proper RVOL calculation on intraday bars.
            
            Formula from IBKR documentation:
            RVOL_intraday = (Current Bar Volume) / (Average Volume for this time slot across past N complete days)
            
            Example: {'09:30': 50000, '09:35': 45000, ...}
            """
            try:
                if result_full.empty or len(result_full) < 2:
                    return {}
                
                # Create a copy to add temporary columns
                temp_df = result_full.copy()
                
                # Extract time component (HH:MM) from index
                temp_df["time_slot"] = temp_df.index.strftime("%H:%M")
                
                # Track which day each bar belongs to
                temp_df["trading_day"] = temp_df.index.normalize()
                
                # Get all unique trading days
                unique_trading_days = sorted(temp_df["trading_day"].unique())
                
                # CRITICAL: Only use PREVIOUS COMPLETE days (exclude today's incomplete data)
                # If we only have today's data, we can't calculate proper TOD averages
                if len(unique_trading_days) <= 1:
                    logger.debug("Not enough complete days for TOD averages (only %d day(s))", len(unique_trading_days))
                    return {}  # Not enough previous days
                
                # Exclude the last (current/incomplete) day
                previous_days = unique_trading_days[:-1]
                
                # Limit to _lookback_days of previous data
                previous_days = previous_days[-_lookback_days:]
                
                if len(previous_days) == 0:
                    logger.debug("No previous complete days available after filtering")
                    return {}
                
                # Filter to only previous complete days
                hist_data = temp_df[temp_df["trading_day"].isin(previous_days)].copy()
                
                if hist_data.empty:
                    logger.debug("No historical data found for previous days")
                    return {}
                
                # Group by time slot and calculate mean volume
                time_of_day_avg = hist_data.groupby("time_slot")["volume"].mean().to_dict()
                
                logger.debug("Computed TOD averages for %d time slots from %d complete days: %s", 
                           len(time_of_day_avg), len(previous_days), list(sorted(time_of_day_avg.keys()))[:5])
                return time_of_day_avg
            except Exception as e:
                logger.debug("Error computing time-of-day averages: %s", e)
                logger.debug(traceback.format_exc())
                return {}

        # cumulative today volume up to the last available bar in session
        today_cum_volume = float(result_session["volume"].sum()) if not result_session.empty else float(np.nan)

        # last available bar volume (including incomplete bar if present in result_session)
        last_bar_volume = float(result_session["volume"].iloc[-1]) if not result_session.empty else float(np.nan)

        # --- build indicators dict (start with some safe defaults) ---
        indicators: Dict[str, Any] = {"symbol": getattr(contract, "symbol", symbol), "cusip": cusip,
                                      "netPosition": int(net_position) if net_position is not None else 0}

        # store last close reference (if form asks for previous bar or last closed bar)
        try:
            if form.get("CloseBool") == "Close":
                # reference the last available bar in the index
                indicators["close"] = float(result_full["close"].iloc[-1])
            else:
                # previous close (exclude current last incomplete bar)
                if len(result_full) >= 2:
                    indicators["close"] = float(result_full["close"].iloc[-2])
                else:
                    indicators["close"] = float(result_full["close"].iloc[-1])
        except Exception:
            indicators["close"] = None

        # --- Average volume ---
        if form.get("ComparisonAverageVolume") != "Not used":
            try:
                lookback = int(form.get("AverageVolume", 14))
            except Exception:
                lookback = 14

            # If intraday bars (more than 1 bar per day) -> compute average daily volume
            if result_full.shape[0] > 1 and len(unique_dates) > 1 and result_full.shape[0] / max(1,
                                                                                                 len(unique_dates)) > 1.5:
                avg_vol = _avg_daily_volume(lookback)
            else:
                # data looks like daily bars: average of last `lookback` bars' volume
                avg_vol = float(result_full["volume"].iloc[-lookback:].mean()) if result_full.shape[0] >= 1 else float(
                    np.nan)

            indicators["averageVolume"] = int(round(avg_vol)) if not np.isnan(avg_vol) else None

            if form.get("ComparisonAverageVolume") == "between":
                try:
                    lookback1 = int(form.get("AverageVolume1", lookback))
                except Exception:
                    lookback1 = lookback
                if result_full.shape[0] > 1 and len(unique_dates) > 1 and result_full.shape[0] / max(1,
                                                                                                     len(unique_dates)) > 1.5:
                    avg_vol1 = _avg_daily_volume(lookback1)
                else:
                    avg_vol1 = float(result_full["volume"].iloc[-lookback1:].mean()) if result_full.shape[
                                                                                            0] >= 1 else float(np.nan)
                indicators["averageVolume1"] = int(round(avg_vol1)) if not np.isnan(avg_vol1) else None

        # --- Relative volume ---
        if form.get("ComparisonRelativeVolume") != "Not used":
            try:
                rv_lookback = int(form.get("RelativeVolume", 5))
            except Exception:
                rv_lookback = 5

            # Detect if we're using intraday bars (multiple bars per day) or daily bars
            is_intraday_data = result_full.shape[0] > 1 and len(unique_dates) > 1 and result_full.shape[0] / max(1,
                                                                                                 len(unique_dates)) > 1.5

            if is_intraday_data:
                # Time-of-day adjusted RVOL for intraday bars (e.g., 5-min, 15-min)
                # This matches the IBKR formula for proper RVOL calculation
                # 1. Get current bar's time and volume
                current_bar_time_str = result_full.index[-1].strftime("%H:%M")
                current_bar_volume = float(result_full["volume"].iloc[-1])
                
                # 2. Calculate average volume at this time of day across past N days
                tod_averages = _avg_volume_by_time_of_day(rv_lookback)
                
                # 3. Get the average volume for this specific time slot
                if current_bar_time_str in tod_averages and tod_averages[current_bar_time_str] > 0:
                    avg_volume_at_time = float(tod_averages[current_bar_time_str])
                    rel_vol = current_bar_volume / avg_volume_at_time
                    logger.debug("RVOL for %s: %.2f (current=%d, avg_at_time=%.0f) [TOD method]", 
                               current_bar_time_str, rel_vol, current_bar_volume, avg_volume_at_time)
                else:
                    # Fallback: TOD data not available, calculate average from recent complete days
                    logger.debug("TOD data not available for %s, using fallback method", current_bar_time_str)
                    
                    # Method 1: Use average daily volume across previous complete days
                    avg_daily = _avg_daily_volume(rv_lookback)
                    if avg_daily and not np.isnan(avg_daily) and avg_daily > 0:
                        # Estimate bars per day and get the expected bar average
                        bars_per_day = result_full.shape[0] / max(1, len(unique_dates) - 1)
                        if bars_per_day > 1:
                            # If intraday bars, divide daily average by approximate bars per day
                            avg_bar_volume = avg_daily / bars_per_day
                        else:
                            avg_bar_volume = avg_daily
                        rel_vol = current_bar_volume / avg_bar_volume if avg_bar_volume > 0 else float(np.nan)
                        logger.debug("RVOL fallback (daily avg): %.2f (current=%d, daily_avg=%.0f, bars_per_day=%.1f)", 
                                   rel_vol if not np.isnan(rel_vol) else 0, current_bar_volume, avg_daily, bars_per_day)
                    else:
                        # Method 2: Use recent bar average (excluding current bar)
                        if result_full.shape[0] > rv_lookback:
                            avg_bar = float(result_full["volume"].iloc[-(rv_lookback+1):-1].mean())
                        else:
                            avg_bar = float(result_full["volume"].iloc[:-1].mean()) if result_full.shape[0] > 1 else float(np.nan)
                        rel_vol = current_bar_volume / avg_bar if avg_bar and avg_bar > 0 else float(np.nan)
                        logger.debug("RVOL fallback (recent bars): %.2f (current=%d, recent_avg=%.0f)", 
                                   rel_vol if not np.isnan(rel_vol) else 0, current_bar_volume, avg_bar if avg_bar else 0)
            else:
                # Daily or longer timeframe: use today's cumulative volume / avg daily volume
                avg_daily = _avg_daily_volume(rv_lookback)
                if avg_daily and not np.isnan(avg_daily) and avg_daily > 0:
                    rel_vol = today_cum_volume / avg_daily if not np.isnan(today_cum_volume) else float(np.nan)
                else:
                    # fallback: last bar vs average of PREVIOUS bars
                    if result_full.shape[0] > rv_lookback:
                        avg_bar = float(result_full["volume"].iloc[-(rv_lookback+1):-1].mean()) if result_full.shape[0] > rv_lookback else float(np.nan)
                    else:
                        avg_bar = float(result_full["volume"].iloc[:-1].mean()) if result_full.shape[0] > 1 else float(np.nan)
                    rel_vol = last_bar_volume / avg_bar if avg_bar and avg_bar > 0 else float(np.nan)
                    
            indicators["relativeVolume"] = rel_vol

            if form.get("ComparisonRelativeVolume") == "between":
                try:
                    rv_lookback1 = int(form.get("RelativeVolume1", rv_lookback))
                except Exception:
                    rv_lookback1 = rv_lookback
                
                if is_intraday_data:
                    # Time-of-day adjusted RVOL for "between" comparison
                    current_bar_time_str = result_full.index[-1].strftime("%H:%M")
                    current_bar_volume = float(result_full["volume"].iloc[-1])
                    
                    tod_averages1 = _avg_volume_by_time_of_day(rv_lookback1)
                    
                    if current_bar_time_str in tod_averages1 and tod_averages1[current_bar_time_str] > 0:
                        avg_volume_at_time1 = float(tod_averages1[current_bar_time_str])
                        rel_vol1 = current_bar_volume / avg_volume_at_time1
                    else:
                        # Fallback
                        if result_full.shape[0] > rv_lookback1:
                            avg_bar1 = float(result_full["volume"].iloc[-(rv_lookback1+1):-1].mean()) if result_full.shape[0] > rv_lookback1 else float(np.nan)
                        else:
                            avg_bar1 = float(result_full["volume"].iloc[:-1].mean()) if result_full.shape[0] > 1 else float(np.nan)
                        rel_vol1 = current_bar_volume / avg_bar1 if avg_bar1 and avg_bar1 > 0 else float(np.nan)
                else:
                    # Daily or longer timeframe: use today's cumulative volume / avg daily volume
                    avg_daily1 = _avg_daily_volume(rv_lookback1)
                    if avg_daily1 and not np.isnan(avg_daily1) and avg_daily1 > 0:
                        rel_vol1 = today_cum_volume / avg_daily1 if not np.isnan(today_cum_volume) else float(np.nan)
                    else:
                        if result_full.shape[0] > rv_lookback1:
                            avg_bar1 = float(result_full["volume"].iloc[-(rv_lookback1+1):-1].mean()) if result_full.shape[0] > rv_lookback1 else float(np.nan)
                        else:
                            avg_bar1 = float(result_full["volume"].iloc[:-1].mean()) if result_full.shape[0] > 1 else float(np.nan)
                        rel_vol1 = last_bar_volume / avg_bar1 if avg_bar1 and avg_bar1 > 0 else float(np.nan)
                indicators["relativeVolume1"] = rel_vol1

        # --- Price level (last close) ---
        if form.get("ComparisonPrice") != "Not used":
            # prefer last closed bar (if session incomplete and user requested previous close logic this was handled above)
            indicators["priceLevel"] = indicators.get("close")

        # --- VWAP ---
        if form.get("ComparisonVWAP") != "Not used":
            try:
                w = int(form.get("VWAP", 20))
            except Exception:
                w = 20
            try:
                vwap = VolumeWeightedAveragePrice(
                    high=result_full["high"],
                    low=result_full["low"],
                    close=result_full["close"],
                    volume=result_full["volume"],
                    window=w,
                )
                indicators["vwap"] = last_value(vwap.volume_weighted_average_price())
            except Exception:
                indicators["vwap"] = None

            if form.get("ComparisonVWAP") == "between":
                try:
                    w1 = int(form.get("VWAP1", w))
                except Exception:
                    w1 = w
                try:
                    vwap1 = VolumeWeightedAveragePrice(
                        high=result_full["high"],
                        low=result_full["low"],
                        close=result_full["close"],
                        volume=result_full["volume"],
                        window=w1,
                    )
                    indicators["vwap1"] = last_value(vwap1.volume_weighted_average_price())
                except Exception:
                    indicators["vwap1"] = None

        # --- Fast SMA ---
        if form.get("ComparisonFastSMA") != "Not used":
            try:
                w = int(form.get("FastSMA", 10))
            except Exception:
                w = 10
            try:
                sma_fast = SMAIndicator(close=result_full["close"], window=w)
                indicators["smaFast"] = last_value(sma_fast.sma_indicator())
            except Exception:
                indicators["smaFast"] = None

            if form.get("ComparisonFastSMA") == "between":
                try:
                    w1 = int(form.get("FastSMA1", w))
                except Exception:
                    w1 = w
                try:
                    sma_fast1 = SMAIndicator(close=result_full["close"], window=w1)
                    indicators["smaFast1"] = last_value(sma_fast1.sma_indicator())
                except Exception:
                    indicators["smaFast1"] = None

        # --- Medium SMA ---
        if form.get("ComparisonMediumSMA") != "Not used":
            try:
                w = int(form.get("MediumSMA", 10))
            except Exception:
                w = 10
            try:
                sma_medium = SMAIndicator(close=result_full["close"], window=w)
                indicators["smaMedium"] = last_value(sma_medium.sma_indicator())
            except Exception:
                indicators["smaMedium"] = None

            if form.get("ComparisonMediumSMA") == "between":
                try:
                    w1 = int(form.get("MediumSMA1", w))
                except Exception:
                    w1 = w
                try:
                    sma_medium1 = SMAIndicator(close=result_full["close"], window=w1)
                    indicators["smaMedium1"] = last_value(sma_medium1.sma_indicator())
                except Exception:
                    indicators["smaMedium1"] = None

        # --- Slow SMA ---
        if form.get("ComparisonSlowSMA") != "Not used":
            try:
                w = int(form.get("SlowSMA", 50))
            except Exception:
                w = 50
            try:
                sma_slow = SMAIndicator(close=result_full["close"], window=w)
                indicators["smaSlow"] = last_value(sma_slow.sma_indicator())
            except Exception:
                indicators["smaSlow"] = None

            if form.get("ComparisonSlowSMA") == "between":
                try:
                    w1 = int(form.get("SlowSMA1", w))
                except Exception:
                    w1 = w
                try:
                    sma_slow1 = SMAIndicator(close=result_full["close"], window=w1)
                    indicators["smaSlow1"] = last_value(sma_slow1.sma_indicator())
                except Exception:
                    indicators["smaSlow1"] = None

        # --- RSI ---
        if form.get("ComparisonRSI") != "Not used":
            try:
                w = int(form.get("RSI", 14))
            except Exception:
                w = 14
            try:
                rsi = RSIIndicator(result_full["close"], window=w)
                indicators["rsi"] = last_value(rsi.rsi())
            except Exception:
                indicators["rsi"] = None

            if form.get("ComparisonRSI") == "between":
                try:
                    w1 = int(form.get("RSI1", w))
                except Exception:
                    w1 = w
                try:
                    rsi1 = RSIIndicator(result_full["close"], window=w1)
                    indicators["rsi1"] = last_value(rsi1.rsi())
                except Exception:
                    indicators["rsi1"] = None

        # --- Fast EMA ---
        if form.get("ComparisonFastEMA", "Not used") != "Not used":
            try:
                w = int(form.get("FastEMA", 21))
            except Exception:
                w = 21
            try:
                emaFast = EMAIndicator(close=result_full["close"], window=w)
                try:
                    emaFast_series = emaFast.ema_indicator()
                except Exception:
                    emaFast_series = emaFast.ema()
                indicators["emaFast"] = last_value(emaFast_series)
            except Exception:
                indicators["emaFast"] = None

            if form.get("ComparisonFastEMA") == "between":
                try:
                    w1 = int(form.get("FastEMA1", w))
                except Exception:
                    w1 = w
                try:
                    emaFast1 = EMAIndicator(close=result_full["close"], window=w1)
                    try:
                        emaFast1_series = emaFast1.ema_indicator()
                    except Exception:
                        emaFast1_series = emaFast1.ema()
                    indicators["emaFast1"] = last_value(emaFast1_series)
                except Exception:
                    indicators["emaFast1"] = None

        # --- Slow EMA ---
        if form.get("ComparisonSlowEMA", "Not used") != "Not used":
            try:
                w = int(form.get("SlowEMA", 21))
            except Exception:
                w = 21
            try:
                emaSlow = EMAIndicator(close=result_full["close"], window=w)
                try:
                    emaSlow_series = emaSlow.ema_indicator()
                except Exception:
                    emaSlow_series = emaSlow.ema()
                indicators["emaSlow"] = last_value(emaSlow_series)
            except Exception:
                indicators["emaSlow"] = None

            if form.get("ComparisonSlowEMA") == "between":
                try:
                    w1 = int(form.get("SlowEMA1", w))
                except Exception:
                    w1 = w
                try:
                    emaSlow1 = EMAIndicator(close=result_full["close"], window=w1)
                    try:
                        emaSlow1_series = emaSlow1.ema_indicator()
                    except Exception:
                        emaSlow1_series = emaSlow1.ema()
                    indicators["emaSlow1"] = last_value(emaSlow1_series)
                except Exception:
                    indicators["emaSlow1"] = None

        # --- OBV ---
        if form.get("ComparisonOBV", "Not used") != "Not used":
            try:
                obv = OBVIndicator(close=result_full["close"], volume=result_full["volume"])
                try:
                    obv_series = obv.on_balance_volume()
                except Exception:
                    try:
                        obv_series = obv.obv()
                    except Exception:
                        obv_series = obv.onBalanceVolume()
                indicators["obv"] = last_value(obv_series)
            except Exception:
                indicators["obv"] = None

            if form.get("ComparisonOBV") == "between":
                try:
                    obv1 = OBVIndicator(close=result_full["close"], volume=result_full["volume"])
                    try:
                        obv1_series = obv1.on_balance_volume()
                    except Exception:
                        try:
                            obv1_series = obv1.obv()
                        except Exception:
                            obv1_series = obv1.onBalanceVolume()
                    indicators["obv1"] = last_value(obv1_series)
                except Exception:
                    indicators["obv1"] = None

        # --- Fast OBV (5-bar MA) ---
        if form.get("ComparisonFastOBV", "Not used") != "Not used":
            try:
                fast_obv = FastOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=5)
                try:
                    fast_obv_series = fast_obv.fast_obv()
                except Exception:
                    fast_obv_series = fast_obv.obv()
                indicators["fast_obv"] = last_value(fast_obv_series)
            except Exception:
                indicators["fast_obv"] = None

            if form.get("ComparisonFastOBV") == "between":
                try:
                    fast_obv1 = FastOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=5)
                    try:
                        fast_obv1_series = fast_obv1.fast_obv()
                    except Exception:
                        fast_obv1_series = fast_obv1.obv()
                    indicators["fast_obv1"] = last_value(fast_obv1_series)
                except Exception:
                    indicators["fast_obv1"] = None

        # --- Medium OBV (10-bar MA) ---
        if form.get("ComparisonMediumOBV", "Not used") != "Not used":
            try:
                medium_obv = MediumOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=10)
                try:
                    medium_obv_series = medium_obv.medium_obv()
                except Exception:
                    medium_obv_series = medium_obv.obv()
                indicators["medium_obv"] = last_value(medium_obv_series)
            except Exception:
                indicators["medium_obv"] = None

            if form.get("ComparisonMediumOBV") == "between":
                try:
                    medium_obv1 = MediumOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=10)
                    try:
                        medium_obv1_series = medium_obv1.medium_obv()
                    except Exception:
                        medium_obv1_series = medium_obv1.obv()
                    indicators["medium_obv1"] = last_value(medium_obv1_series)
                except Exception:
                    indicators["medium_obv1"] = None

        # --- Slow OBV (20-bar MA) ---
        if form.get("ComparisonSlowOBV", "Not used") != "Not used":
            try:
                slow_obv = SlowOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=20)
                try:
                    slow_obv_series = slow_obv.slow_obv()
                except Exception:
                    slow_obv_series = slow_obv.obv()
                indicators["slow_obv"] = last_value(slow_obv_series)
            except Exception:
                indicators["slow_obv"] = None

            if form.get("ComparisonSlowOBV") == "between":
                try:
                    slow_obv1 = SlowOBVIndicator(close=result_full["close"], volume=result_full["volume"], window=20)
                    try:
                        slow_obv1_series = slow_obv1.slow_obv()
                    except Exception:
                        slow_obv1_series = slow_obv1.obv()
                    indicators["slow_obv1"] = last_value(slow_obv1_series)
                except Exception:
                    indicators["slow_obv1"] = None

        # --- ATR ---
        if form.get("ComparisonATR", "Not used") != "Not used":
            try:
                w = int(form.get("ATR", 14))
            except Exception:
                w = 14
            try:
                atr = ATRIndicator(high=result_full["high"], low=result_full["low"], close=result_full["close"],
                                   window=w)
                try:
                    atr_series = atr.average_true_range()
                except Exception:
                    try:
                        atr_series = atr.atr()
                    except Exception:
                        atr_series = atr.averageTrueRange()
                indicators["atr"] = last_value(atr_series)
            except Exception:
                indicators["atr"] = None

            if form.get("ComparisonATR") == "between":
                try:
                    w1 = int(form.get("ATR1", w))
                except Exception:
                    w1 = w
                try:
                    atr1 = ATRIndicator(high=result_full["high"], low=result_full["low"], close=result_full["close"],
                                        window=w1)
                    try:
                        atr1_series = atr1.average_true_range()
                    except Exception:
                        try:
                            atr1_series = atr1.atr()
                        except Exception:
                            atr1_series = atr1.averageTrueRange()
                    indicators["atr1"] = last_value(atr1_series)
                except Exception:
                    indicators["atr1"] = None

        # --- Previous Close (always calculated for 200 SMA crossover detection) ---
        try:
            # previous session close = last bar close from previous date (not the current session)
            if len(unique_dates) >= 2:
                prev_date = unique_dates[-2]
                prev_mask = result_full.index.normalize() == prev_date
                prev_close = float(result_full.loc[prev_mask]["close"].iloc[-1])
            else:
                prev_close = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else float(
                    result_full["close"].iloc[-1])
            indicators["prevClose"] = prev_close
            if form.get("ComparisonPrevClose") == "between":
                indicators["prevClose1"] = prev_close
        except Exception:
            indicators["prevClose"] = None

        # --- Percentage Change from Previous Close (% CHG) ---
        try:
            current_close = indicators.get("close")
            prev_close = indicators.get("prevClose")
            
            if current_close is not None and prev_close is not None and prev_close != 0:
                pct_change = ((current_close - prev_close) / prev_close) * 100.0
                indicators["pctChange"] = float(pct_change)
            else:
                indicators["pctChange"] = None
        except Exception:
            indicators["pctChange"] = None

        # --- LowOfDay / HighOfDay (session-only) ---
        if form.get("ComparisonLowOfDay", "Not used") != "Not used":
            try:
                if not result_session.empty:
                    low_of_day = float(result_session["low"].min())
                else:
                    # fallback to last available low
                    low_of_day = float(result_full["low"].iloc[-1])
                indicators["lowOfDay"] = low_of_day
                if form.get("ComparisonLowOfDay") == "between":
                    indicators["lowOfDay1"] = low_of_day
            except Exception:
                indicators["lowOfDay"] = None

        if form.get("ComparisonHighOfDay", "Not used") != "Not used":
            try:
                if not result_session.empty:
                    high_of_day = float(result_session["high"].max())
                else:
                    high_of_day = float(result_full["high"].iloc[-1])
                indicators["highOfDay"] = high_of_day
                if form.get("ComparisonHighOfDay") == "between":
                    indicators["highOfDay1"] = high_of_day
            except Exception:
                indicators["highOfDay"] = None

        # --- Pivot points: compute from previous trading day H/L/C (classical pivots) ---
        # Classic pivot formulas:
        # P  = (H + L + C) / 3
        # R1 = (2 * P) - L
        # S1 = (2 * P) - H
        # R2 = P + (H - L)
        # S2 = P - (H - L)
        if form.get("ComparisonPivotPoint") != "Not used":
            try:
                if len(unique_dates) >= 2:
                    prev_date = unique_dates[-2]
                    prev_mask = result_full.index.normalize() == prev_date
                    prev_df = result_full.loc[prev_mask]
                    prev_h = float(prev_df["high"].max())
                    prev_l = float(prev_df["low"].min())
                    prev_c = float(prev_df["close"].iloc[-1])
                else:
                    # fallback to last full bar as previous day
                    prev_h = float(result_full["high"].iloc[-2]) if len(result_full) >= 2 else float(
                        result_full["high"].iloc[-1])
                    prev_l = float(result_full["low"].iloc[-2]) if len(result_full) >= 2 else float(
                        result_full["low"].iloc[-1])
                    prev_c = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else float(
                        result_full["close"].iloc[-1])

                P = (prev_h + prev_l + prev_c) / 3.0
                R1 = (2 * P) - prev_l
                S1 = (2 * P) - prev_h
                R2 = P + (prev_h - prev_l)
                S2 = P - (prev_h - prev_l)

                pivots = {
                    "Pivot": P,
                    "R1": R1,
                    "S1": S1,
                    "R2": R2,
                    "S2": S2,
                }

                # user selects which pivot to use via form["PivotPoint"]; map common names
                pp_name = form.get("PivotPoint", "Pivot")
                # try to return requested pivot value, otherwise return the main pivot
                val = pivots.get(pp_name, P)
                indicators["Pivot"] = {pp_name: val}

                # Store full pivot dictionary so other features can inspect all levels
                indicators["PivotLevels"] = pivots.copy()

                if form.get("ComparisonPivotPoint") == "between":
                    pp_name1 = form.get("PivotPoint1", pp_name)
                    val1 = pivots.get(pp_name1, P)
                    indicators["Pivot1"] = {pp_name1: val1}
                
                # Store second pivot point
                if form.get("PivotPoint2") and form.get("PivotPoint2") != "Not used":
                    pp_name2 = form.get("PivotPoint2", pp_name)
                    val2 = pivots.get(pp_name2, P)
                    indicators["Pivot2"] = {pp_name2: val2}
                
                # Store third pivot point
                if form.get("PivotPoint3") and form.get("PivotPoint3") != "Not used":
                    pp_name3 = form.get("PivotPoint3", pp_name)
                    val3 = pivots.get(pp_name3, P)
                    indicators["Pivot3"] = {pp_name3: val3}
            except Exception:
                indicators["Pivot"] = {}
                indicators["Pivot1"] = {}
                indicators["Pivot2"] = {}
                indicators["Pivot3"] = {}

        # --- Cross 50 SMA (daily) ---
        if form.get("ComparisonCross50SMA", "Not used") != "Not used":
            try:
                sma_window_50 = int(form.get("Cross50SMA", 50))
            except Exception:
                sma_window_50 = 50
            try:
                sma_50 = SMAIndicator(close=result_full["close"], window=sma_window_50)
                sma_50_series = sma_50.sma_indicator()
                if len(sma_50_series) >= 2 and len(result_full["close"]) >= 2:
                    prev_close = float(result_full["close"].iloc[-2])
                    curr_close = float(result_full["close"].iloc[-1])
                    prev_sma50 = float(sma_50_series.iloc[-2])
                    curr_sma50 = float(sma_50_series.iloc[-1])
                    crossed_above = (prev_close < prev_sma50) and (curr_close > curr_sma50)
                    crossed_below = (prev_close > prev_sma50) and (curr_close < curr_sma50)
                    indicators["cross50SMA_above"] = crossed_above
                    indicators["cross50SMA_below"] = crossed_below
                    indicators["cross50SMA_either"] = crossed_above or crossed_below
                    indicators["cross50SMA_value"] = curr_sma50
                    indicators["cross50SMA_isAbove"] = curr_close >= curr_sma50
                    if curr_sma50 != 0:
                        indicators["cross50SMA_pctFromSMA"] = ((curr_close - curr_sma50) / curr_sma50) * 100.0
                    else:
                        indicators["cross50SMA_pctFromSMA"] = None
                else:
                    indicators["cross50SMA_above"] = False
                    indicators["cross50SMA_below"] = False
                    indicators["cross50SMA_either"] = False
                    indicators["cross50SMA_value"] = None
                    indicators["cross50SMA_isAbove"] = None
                    indicators["cross50SMA_pctFromSMA"] = None
            except Exception:
                indicators["cross50SMA_above"] = False
                indicators["cross50SMA_below"] = False
                indicators["cross50SMA_either"] = False
                indicators["cross50SMA_value"] = None
                indicators["cross50SMA_isAbove"] = None
                indicators["cross50SMA_pctFromSMA"] = None

        # --- Cross 200 SMA (daily) ---
        if form.get("ComparisonCross200SMA", "Not used") != "Not used":
            try:
                sma_window_200 = int(form.get("Cross200SMA", 200))
            except Exception:
                sma_window_200 = 200
            try:
                sma_200 = SMAIndicator(close=result_full["close"], window=sma_window_200)
                sma_200_series = sma_200.sma_indicator()
                if len(sma_200_series) >= 2 and len(result_full["close"]) >= 2:
                    prev_close = float(result_full["close"].iloc[-2])
                    curr_close = float(result_full["close"].iloc[-1])
                    prev_sma = float(sma_200_series.iloc[-2])
                    curr_sma = float(sma_200_series.iloc[-1])
                    crossed_above = (prev_close < prev_sma) and (curr_close > curr_sma)
                    crossed_below = (prev_close > prev_sma) and (curr_close < curr_sma)
                    indicators["cross200SMA_above"] = crossed_above
                    indicators["cross200SMA_below"] = crossed_below
                    indicators["cross200SMA_either"] = crossed_above or crossed_below
                    indicators["cross200SMA_value"] = curr_sma
                    indicators["cross200SMA_isAbove"] = curr_close >= curr_sma
                    if curr_sma != 0:
                        indicators["cross200SMA_pctFromSMA"] = ((curr_close - curr_sma) / curr_sma) * 100.0
                    else:
                        indicators["cross200SMA_pctFromSMA"] = None
                else:
                    indicators["cross200SMA_above"] = False
                    indicators["cross200SMA_below"] = False
                    indicators["cross200SMA_either"] = False
                    indicators["cross200SMA_value"] = None
                    indicators["cross200SMA_isAbove"] = None
                    indicators["cross200SMA_pctFromSMA"] = None
            except Exception:
                indicators["cross200SMA_above"] = False
                indicators["cross200SMA_below"] = False
                indicators["cross200SMA_either"] = False
                indicators["cross200SMA_value"] = None
                indicators["cross200SMA_isAbove"] = None
                indicators["cross200SMA_pctFromSMA"] = None

        # --- Break High (recent X-day high) ---
        if form.get("ComparisonBreakHigh", "Not used") != "Not used":
            try:
                lookback_days = int(form.get("BreakHigh", 5))
            except Exception:
                lookback_days = 5
            try:
                # use daily highs: group by date, take max high per day
                daily_highs = result_full.groupby(result_full.index.normalize())["high"].max()
                # exclude today (last date) to get the *previous* X days' high
                if len(daily_highs) > 1:
                    past_highs = daily_highs.iloc[-(lookback_days + 1):-1]
                else:
                    past_highs = daily_highs.iloc[-lookback_days:]
                if not past_highs.empty:
                    indicators["breakHigh"] = float(past_highs.max())
                else:
                    indicators["breakHigh"] = None
            except Exception:
                indicators["breakHigh"] = None

            if form.get("ComparisonBreakHigh") == "between":
                indicators["breakHigh1"] = indicators.get("breakHigh")

        # --- Pullback Retracement (% retracement of day's move) ---
        if form.get("ComparisonPullbackPct", "Not used") != "Not used":
            try:
                # high of day (session)
                if not result_session.empty:
                    hod = float(result_session["high"].max())
                else:
                    hod = float(result_full["high"].iloc[-1])

                # previous close
                if len(unique_dates) >= 2:
                    prev_date = unique_dates[-2]
                    prev_mask = result_full.index.normalize() == prev_date
                    pc = float(result_full.loc[prev_mask]["close"].iloc[-1])
                else:
                    pc = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else float(
                        result_full["close"].iloc[-1])

                close_price = float(result_full["close"].iloc[-1])
                move = hod - pc

                if move > 0:
                    pullback_pct = ((hod - close_price) / move) * 100.0
                    indicators["pullbackPct"] = pullback_pct
                else:
                    indicators["pullbackPct"] = None

                if form.get("ComparisonPullbackPct") == "between":
                    indicators["pullbackPct1"] = indicators.get("pullbackPct")
            except Exception:
                indicators["pullbackPct"] = None

        # --- 2nd Pullback Retracement (same logic, independent threshold) ---
        if form.get("ComparisonPullbackPct2", "Not used") != "Not used":
            try:
                if not result_session.empty:
                    hod2 = float(result_session["high"].max())
                else:
                    hod2 = float(result_full["high"].iloc[-1])

                if len(unique_dates) >= 2:
                    prev_date2 = unique_dates[-2]
                    prev_mask2 = result_full.index.normalize() == prev_date2
                    pc2 = float(result_full.loc[prev_mask2]["close"].iloc[-1])
                else:
                    pc2 = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else float(
                        result_full["close"].iloc[-1])

                close_price2 = float(result_full["close"].iloc[-1])
                move2 = hod2 - pc2

                if move2 > 0:
                    pullback_pct2 = ((hod2 - close_price2) / move2) * 100.0
                    indicators["pullbackPct2"] = pullback_pct2
                else:
                    indicators["pullbackPct2"] = None

                if form.get("ComparisonPullbackPct2") == "between":
                    indicators["pullbackPct2_1"] = indicators.get("pullbackPct2")
            except Exception:
                indicators["pullbackPct2"] = None

        # --- Fibonacci Pullback (price pullback to Fib retracement levels) ---
        # Calculates Fib retracement levels of the move from previous close to session high
        # Checks if current price is within a tolerance of the selected Fib level
        if form.get("ComparisonFibPullback", "Not used") != "Not used":
            try:
                close_price_fpb = float(result_full["close"].iloc[-1])
                
                # Get high of the session
                if not result_session.empty:
                    hod_fpb = float(result_session["high"].max())
                else:
                    hod_fpb = float(result_full["high"].iloc[-1])

                # Get previous close based on selected timeframe
                if len(unique_dates) >= 2:
                    prev_date_fpb = unique_dates[-2]
                    prev_mask_fpb = result_full.index.normalize() == prev_date_fpb
                    pc_fpb = float(result_full.loc[prev_mask_fpb]["close"].iloc[-1])
                else:
                    pc_fpb = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else close_price_fpb

                move_fpb = hod_fpb - pc_fpb

                if move_fpb > 0:
                    # Get selected Fib level
                    fib_level_str = form.get("FibPullbackLevel", "61.8")
                    fib_level_ratio = float(fib_level_str) / 100.0
                    
                    # Calculate Fib retracement level
                    fib_pb_level = hod_fpb - (move_fpb * fib_level_ratio)
                    
                    # Distance from current price to fib level as % of move
                    distance_from_fib = abs(close_price_fpb - fib_pb_level)
                    fib_pb_pct = (distance_from_fib / move_fpb) * 100.0 if move_fpb != 0 else None
                    
                    indicators["fibPullback"] = fib_pb_pct
                    indicators["fibPullbackLevel"] = round(fib_pb_level, 2)
                    indicators["fibPullbackMoveSize"] = round(move_fpb, 2)
                else:
                    indicators["fibPullback"] = None
                    indicators["fibPullbackLevel"] = None
                    indicators["fibPullbackMoveSize"] = None

                if form.get("ComparisonFibPullback") == "between":
                    indicators["fibPullback1"] = indicators.get("fibPullback")
            except Exception as e:
                logger.debug("Fib pullback calculation error: %s", e)
                indicators["fibPullback"] = None
                indicators["fibPullbackLevel"] = None
                indicators["fibPullbackMoveSize"] = None

        # --- Gap Pullback (price pullback to gap Fib retracement levels) ---
        # Calculates Fib retracement levels of the overnight gap (open - previous close)
        # Checks if current price is within tolerance of the selected Fib level
        if form.get("ComparisonGapPullback", "Not used") != "Not used":
            try:
                close_price_gpb = float(result_full["close"].iloc[-1])
                open_price_gpb = float(result_full["open"].iloc[-1])
                
                # Get previous close (always previous trading day close for gap)
                if len(unique_dates) >= 2:
                    prev_date_gpb = unique_dates[-2]
                    prev_mask_gpb = result_full.index.normalize() == prev_date_gpb
                    pc_gpb = float(result_full.loc[prev_mask_gpb]["close"].iloc[-1])
                else:
                    pc_gpb = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else close_price_gpb

                gap_gpb = open_price_gpb - pc_gpb

                if gap_gpb != 0:
                    # Get selected Fib level
                    fib_level_str_gpb = form.get("GapPullbackLevel", "61.8")
                    fib_level_ratio_gpb = float(fib_level_str_gpb) / 100.0
                    
                    # Calculate Fib retracement level of the gap
                    # If gap is positive (up): pc + (gap * fib_ratio)
                    # If gap is negative (down): pc + (gap * fib_ratio) 
                    fib_gpb_level = pc_gpb + (gap_gpb * fib_level_ratio_gpb)
                    
                    # Distance from current price to fib level as % of gap
                    distance_from_fib_gpb = abs(close_price_gpb - fib_gpb_level)
                    gap_pb_pct = (distance_from_fib_gpb / abs(gap_gpb)) * 100.0 if gap_gpb != 0 else None
                    
                    indicators["gapPullback"] = gap_pb_pct
                    indicators["gapPullbackLevel"] = round(fib_gpb_level, 2)
                    indicators["gapPullbackSize"] = round(gap_gpb, 2)
                else:
                    indicators["gapPullback"] = None
                    indicators["gapPullbackLevel"] = None
                    indicators["gapPullbackSize"] = None

                if form.get("ComparisonGapPullback") == "between":
                    indicators["gapPullback1"] = indicators.get("gapPullback")
            except Exception as e:
                logger.debug("Gap pullback calculation error: %s", e)
                indicators["gapPullback"] = None
                indicators["gapPullbackLevel"] = None
                indicators["gapPullbackSize"] = None

        # --- Fibonacci Pullback Levels (for entry/exit orders) ---
        # Calculate Fibonacci retracement levels of the gap regardless of comparison mode
        # These are useful for order entry/exit strategies
        try:
            close_price_fib = float(result_full["close"].iloc[-1])
            open_price_fib = float(result_full["open"].iloc[-1])

            if len(unique_dates) >= 2:
                prev_date_fib = unique_dates[-2]
                prev_mask_fib = result_full.index.normalize() == prev_date_fib
                prev_close_fib = float(result_full.loc[prev_mask_fib]["close"].iloc[-1])
            else:
                prev_close_fib = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else close_price_fib

            gap = open_price_fib - prev_close_fib

            # Fib retracement levels of the gap (available for order entry)
            fib38 = prev_close_fib + gap * 0.382
            fib50 = prev_close_fib + gap * 0.500
            fib618 = prev_close_fib + gap * 0.618

            indicators["fib38"] = round(fib38, 2) if fib38 else None
            indicators["fib50"] = round(fib50, 2) if fib50 else None
            indicators["fib618"] = round(fib618, 2) if fib618 else None
            indicators["fibGapLevel"] = None  # Default; overwritten below if comparing
        except Exception:
            indicators["fib38"] = None
            indicators["fib50"] = None
            indicators["fib618"] = None

        # --- Up Gap & Down Gap (daily gap from 9:30 AM - 4 PM EST) ---
        # 
        # WHAT IS A GAP?
        # A gap occurs when a stock opens significantly away from where it closed.
        # This is calculated as: (Today's RTH Open - Yesterday's Close) / Yesterday's Close * 100%
        #
        # GAP UP (Positive gap):
        #   - Today's opening price > Yesterday's closing price
        #   - Indicates overnight bullish sentiment/news
        #   - Gap is "filled/closed" when price returns to yesterday's close level
        #   - Common setup: Gap up then pullback intraday (buyers vs sellers)
        #
        # GAP DOWN (Negative gap):
        #   - Today's opening price < Yesterday's closing price
        #   - Indicates overnight bearish sentiment/news
        #   - Gap is "filled/closed" when price returns to yesterday's close level
        #   - Common setup: Gap down then bounce intraday (oversold bounce)
        #
        # Calculations use only Regular Trading Hours (9:30 AM - 4 PM EST)
        # to exclude pre/post-market gaps
        
        if form.get("ComparisonUpGap", "Not used") != "Not used" or form.get("ComparisonDownGap", "Not used") != "Not used":
            try:
                # Filter to 9:30 AM - 4 PM EST only (Regular Trading Hours)
                eastern = pytz.timezone('US/Eastern')
                result_rth = result_full.copy()
                
                # Filter by time of day (9:30 AM - 4 PM)
                if hasattr(result_rth.index, 'tz_localize'):
                    # Make timezone-aware if needed
                    if result_rth.index.tz is None:
                        result_rth.index = result_rth.index.tz_localize('UTC').tz_convert(eastern)
                    else:
                        result_rth.index = result_rth.index.tz_convert(eastern)
                
                # Extract trading hours (9:30 AM - 4 PM)
                result_rth = result_rth.between_time('09:30', '16:00')
                
                # Get opening price during RTH (first bar after 9:30)
                if len(result_rth) > 0:
                    open_rth = float(result_rth["open"].iloc[0])
                else:
                    open_rth = float(result_full["open"].iloc[-1])
                
                # Get previous day's closing price
                if len(unique_dates) >= 2:
                    prev_date = unique_dates[-2]
                    prev_mask = result_full.index.normalize() == prev_date
                    prev_close = float(result_full.loc[prev_mask]["close"].iloc[-1])
                else:
                    prev_close = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else float(result_full["close"].iloc[-1])
                
                # Calculate the gap: (Today's Open - Yesterday's Close)
                gap = open_rth - prev_close
                
                # UP GAP: positive gap (today opened higher than yesterday's close)
                if gap > 0 and prev_close > 0:
                    up_gap_pct = (gap / prev_close) * 100.0
                    # Example: Open $103, Previous Close $100, Gap = $3, Gap% = 3%
                    indicators["upGap"] = up_gap_pct
                    if form.get("ComparisonUpGap") == "between":
                        indicators["upGap1"] = up_gap_pct
                else:
                    indicators["upGap"] = 0
                    if form.get("ComparisonUpGap") == "between":
                        indicators["upGap1"] = 0
                
                # DOWN GAP: negative gap (today opened lower than yesterday's close)
                if gap < 0 and prev_close > 0:
                    down_gap_pct = (abs(gap) / prev_close) * 100.0
                    # Example: Open $97, Previous Close $100, Gap = -$3, Gap% = 3%
                    indicators["downGap"] = down_gap_pct
                    if form.get("ComparisonDownGap") == "between":
                        indicators["downGap1"] = down_gap_pct
                else:
                    indicators["downGap"] = 0
                    if form.get("ComparisonDownGap") == "between":
                        indicators["downGap1"] = 0
                        
            except Exception as e:
                logger.debug("Gap calculation error: %s", e)
                indicators["upGap"] = None
                indicators["upGap1"] = None
                indicators["downGap"] = None
                indicators["downGap1"] = None

        # --- Fibonacci Gap (daily gap vs Fib retracement levels) ---
        # Uses RTH (9:30 AM - 4 PM EST) data only, excluding pre/post-market
        if form.get("ComparisonFibGap", "Not used") != "Not used":
            try:
                close_price_fg = float(result_full["close"].iloc[-1])
                
                # Filter to 9:30 AM - 4 PM EST only (Regular Trading Hours) for gap calculation
                eastern = pytz.timezone('US/Eastern')
                result_rth_fg = result_full.copy()
                
                if hasattr(result_rth_fg.index, 'tz_localize'):
                    # Make timezone-aware if needed
                    if result_rth_fg.index.tz is None:
                        result_rth_fg.index = result_rth_fg.index.tz_localize('UTC').tz_convert(eastern)
                    else:
                        result_rth_fg.index = result_rth_fg.index.tz_convert(eastern)
                
                # Extract trading hours (9:30 AM - 4 PM)
                result_rth_fg = result_rth_fg.between_time('09:30', '16:00')
                
                # Get RTH open price (first bar after 9:30 AM)
                if len(result_rth_fg) > 0:
                    open_price_fg = float(result_rth_fg["open"].iloc[0])
                else:
                    open_price_fg = float(result_full["open"].iloc[-1])

                if len(unique_dates) >= 2:
                    prev_date_fg = unique_dates[-2]
                    prev_mask_fg = result_full.index.normalize() == prev_date_fg
                    prev_close_fg = float(result_full.loc[prev_mask_fg]["close"].iloc[-1])
                    prev_high_fg = float(result_full.loc[prev_mask_fg]["high"].max())
                    prev_low_fg = float(result_full.loc[prev_mask_fg]["low"].min())
                else:
                    prev_close_fg = float(result_full["close"].iloc[-2]) if len(result_full) >= 2 else close_price_fg
                    prev_high_fg = float(result_full["high"].iloc[-2]) if len(result_full) >= 2 else float(result_full["high"].iloc[-1])
                    prev_low_fg = float(result_full["low"].iloc[-2]) if len(result_full) >= 2 else float(result_full["low"].iloc[-1])

                gap = open_price_fg - prev_close_fg

                # Fib retracement levels of the gap
                fib_levels = {
                    "38.2": prev_close_fg + gap * 0.382,
                    "50.0": prev_close_fg + gap * 0.500,
                    "61.8": prev_close_fg + gap * 0.618,
                }

                # Find nearest fib level and compute distance as % of gap size
                best_dist = None
                best_level = None
                for lbl, lvl in fib_levels.items():
                    dist = abs(close_price_fg - lvl)
                    if best_dist is None or dist < best_dist:
                        best_dist = dist
                        best_level = lbl

                # fibGap = distance from nearest fib level as % of the gap size
                # If gap is $10 and current price is $0.50 away from the 50% level, 
                # then fibGap = 5% (0.50 / 10.0 * 100)
                fib_gap_pct = (best_dist / abs(gap)) * 100.0 if gap != 0 else None
                indicators["fibGap"] = fib_gap_pct
                indicators["fibGapLevel"] = best_level
                indicators["fibGapDir"] = "up" if gap > 0 else ("down" if gap < 0 else "flat")

                if form.get("ComparisonFibGap") == "between":
                    indicators["fibGap1"] = indicators.get("fibGap")
            except Exception:
                indicators["fibGap"] = None

        # --- final housekeeping ---
        # ensure volume metadata (integer — no decimals)
        try:
            raw_vol = result_session["volume"].iloc[-1] if not result_session.empty else result_full["volume"].iloc[-1]
            indicators["volume"] = int(round(float(raw_vol)))
        except Exception:
            indicators["volume"] = None

        # --- Volume indicator (cumulative session volume over lookback bars) ---
        if form.get("ComparisonVolume") != "Not used":
            try:
                vol_lookback = int(form.get("Volume", 1))
            except Exception:
                vol_lookback = 1

            # Use intraday session volume if multiple bars per day, else use bar volume
            if result_full.shape[0] > 1 and len(unique_dates) > 1 and result_full.shape[0] / max(1, len(unique_dates)) > 1.5:
                # intraday: sum the last vol_lookback bars' volume
                vol_val = float(result_full["volume"].iloc[-vol_lookback:].sum()) if result_full.shape[0] >= 1 else float(np.nan)
            else:
                # daily bars: sum the last vol_lookback bars' volume
                vol_val = float(result_full["volume"].iloc[-vol_lookback:].sum()) if result_full.shape[0] >= 1 else float(np.nan)

            indicators["volumeIndicator"] = int(round(vol_val)) if not np.isnan(vol_val) else None

            if form.get("ComparisonVolume") == "between":
                try:
                    vol_lookback1 = int(form.get("Volume1", vol_lookback))
                except Exception:
                    vol_lookback1 = vol_lookback
                if result_full.shape[0] > 1 and len(unique_dates) > 1 and result_full.shape[0] / max(1, len(unique_dates)) > 1.5:
                    vol_val1 = float(result_full["volume"].iloc[-vol_lookback1:].sum()) if result_full.shape[0] >= 1 else float(np.nan)
                else:
                    vol_val1 = float(result_full["volume"].iloc[-vol_lookback1:].sum()) if result_full.shape[0] >= 1 else float(np.nan)
                indicators["volumeIndicator1"] = int(round(vol_val1)) if not np.isnan(vol_val1) else None

        # --- Market Cap (normalized to millions) ---
        # Source: reqMktData tick 258 (fundamental ratios via IBKR QuoteData subscription)
        # Normalized by _normalize_market_cap() to handle m/M (millions) and b/B (billions) suffixes
        if market_cap is not None:
            indicators["marketCap"] = market_cap
            if form.get("ComparisonMarketCap") == "between":
                indicators["marketCap1"] = market_cap

        # --- Previous Bar Close (for extended hours crossover detection) ---
        # When extended hours are enabled, we need the previous bar's close (not previous day's close)
        # to detect crossovers in premarket and after-hours sessions
        if form.get("Enable200SMABullishCrossover") or form.get("EnableExtendedHours"):
            try:
                if len(result_full) >= 2:
                    # Use the second-to-last close for continuous extended hours data
                    indicators["prevBarClose"] = float(result_full["close"].iloc[-2])
                    logger.debug("Computed prevBarClose=%.2f for extended hours crossover detection", 
                                indicators["prevBarClose"])
                else:
                    # Not enough bars
                    indicators["prevBarClose"] = None
            except Exception as e:
                logger.debug("Failed to compute prevBarClose: %s", e)
                indicators["prevBarClose"] = None

        return indicators

    def buySellSignalCheck(self, data, form):
        """
        Evaluate all configured signal conditions against the current indicators.
        
        Note: If EnableExtendedHours is checked, the indicators and moving averages are 
        calculated using pre-market and after-hours data (4 AM - 8 PM ET).
        If IncludeOvernightData is checked, overnight data (8 PM - 4 AM ET) is also included.
        This affects all technical indicators, volume calculations, and price levels.
        
        Args:
            data: Indicators dictionary with computed values (see getIndicators)
            form: Form data with all configured conditions and parameters
            
        Returns:
            Tuple[bool, dict]: (overall_condition, variable_results)
        """
        condition = True
        counting_ = 0
        variable_results = {}  # track pass/fail per variable

        # -------------------------
        # AVERAGE VOLUME
        # -------------------------
        zero_condition = None

        if (
                form["ComparisonAverageVolume"] not in _NON_SIMPLE_MODES
                and form["averageVolumeBool"] == "value"
        ):
            if form["ComparisonAverageVolume"] == "greater":
                zero_condition = _safe_compare(data.get("averageVolume"), ">", float(
                    form["PercentageAverageVolume"]
                ))
            elif form["ComparisonAverageVolume"] == "greaterEqual":
                zero_condition = _safe_compare(data.get("averageVolume"), ">=", float(
                    form["PercentageAverageVolume"]
                ))
            elif form["ComparisonAverageVolume"] == "lower":
                zero_condition = _safe_compare(data.get("averageVolume"), "<", float(
                    form["PercentageAverageVolume"]
                ))
            elif form["ComparisonAverageVolume"] == "lowerEqual":
                zero_condition = _safe_compare(data.get("averageVolume"), "<=", float(
                    form["PercentageAverageVolume"]
                ))

        elif (
                form["ComparisonAverageVolume"] == "between"
                and form["averageVolumeBool"] == "value"
        ):
            zero_condition = (
                    _safe_compare(data.get("averageVolume"), ">=", float(form["PercentageAverageVolume"]))
                    and _safe_compare(data.get("averageVolume1"), "<=", float(form["PercentageAverageVolume1"]))
            )

        elif (
                form["ComparisonAverageVolume"] not in _NON_SIMPLE_MODES
                and form["averageVolumeBool"] == "percentage"
        ):
            avg = data.get("averageVolume")
            if avg is None:
                zero_condition = False
            else:
                base = avg * (1.0 + float(form["PercentageAverageVolume"]) / 100.0)

                if form["ComparisonAverageVolume"] == "greater":
                    zero_condition = _safe_compare(data.get("volume"), ">", base)
                elif form["ComparisonAverageVolume"] == "greaterEqual":
                    zero_condition = _safe_compare(data.get("volume"), ">=", base)
                elif form["ComparisonAverageVolume"] == "lower":
                    zero_condition = _safe_compare(data.get("volume"), "<", base)
                elif form["ComparisonAverageVolume"] == "lowerEqual":
                    zero_condition = _safe_compare(data.get("volume"), "<=", base)

        elif (
                form["ComparisonAverageVolume"] == "between"
                and form["averageVolumeBool"] == "percentage"
        ):
            avg = data.get("averageVolume")
            avg1 = data.get("averageVolume1")
            if avg is None or avg1 is None:
                zero_condition = False
            else:
                base = avg * (1.0 + float(form["PercentageAverageVolume"]) / 100.0)
                base1 = avg1 * (1.0 + float(form["PercentageAverageVolume1"]) / 100.0)
                zero_condition = (
                        _safe_compare(data.get("volume"), ">=", base)
                        and _safe_compare(data.get("volume"), "<=", base1)
                )

        elif form["ComparisonAverageVolume"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageAverageVolume"])
            except Exception:
                threshold = 5.0
            zero_condition = _within_percent_check(
                data.get("averageVolume"), data.get("volume"),
                form["ComparisonAverageVolume"], threshold
            )

        if zero_condition is not None:
            condition = condition and zero_condition
            counting_ += 1
            variable_results["averageVolume"] = bool(zero_condition)

        # -------------------------
        # VOLUME
        # -------------------------
        volume_condition = None

        if (
                form.get("ComparisonVolume", "Not used") not in _NON_SIMPLE_MODES
                and form.get("VolumeBool", "value") == "value"
        ):
            if form["ComparisonVolume"] == "greater":
                volume_condition = _safe_compare(data.get("volumeIndicator"), ">", float(
                    form["PercentageVolume"]
                ))
            elif form["ComparisonVolume"] == "greaterEqual":
                volume_condition = _safe_compare(data.get("volumeIndicator"), ">=", float(
                    form["PercentageVolume"]
                ))
            elif form["ComparisonVolume"] == "lower":
                volume_condition = _safe_compare(data.get("volumeIndicator"), "<", float(
                    form["PercentageVolume"]
                ))
            elif form["ComparisonVolume"] == "lowerEqual":
                volume_condition = _safe_compare(data.get("volumeIndicator"), "<=", float(
                    form["PercentageVolume"]
                ))

        elif (
                form.get("ComparisonVolume", "Not used") == "between"
                and form.get("VolumeBool", "value") == "value"
        ):
            volume_condition = (
                    _safe_compare(data.get("volumeIndicator"), ">=", float(form["PercentageVolume"]))
                    and _safe_compare(data.get("volumeIndicator1"), "<=", float(form.get("PercentageVolume1", "0")))
            )

        elif (
                form.get("ComparisonVolume", "Not used") not in _NON_SIMPLE_MODES
                and form.get("VolumeBool", "value") == "percentage"
        ):
            vol = data.get("volumeIndicator")
            if vol is None:
                volume_condition = False
            else:
                base = vol * (1.0 + float(form["PercentageVolume"]) / 100.0)

                if form["ComparisonVolume"] == "greater":
                    volume_condition = _safe_compare(data.get("volume"), ">", base)
                elif form["ComparisonVolume"] == "greaterEqual":
                    volume_condition = _safe_compare(data.get("volume"), ">=", base)
                elif form["ComparisonVolume"] == "lower":
                    volume_condition = _safe_compare(data.get("volume"), "<", base)
                elif form["ComparisonVolume"] == "lowerEqual":
                    volume_condition = _safe_compare(data.get("volume"), "<=", base)

        elif (
                form.get("ComparisonVolume", "Not used") == "between"
                and form.get("VolumeBool", "value") == "percentage"
        ):
            vol = data.get("volumeIndicator")
            vol1 = data.get("volumeIndicator1")
            if vol is None or vol1 is None:
                volume_condition = False
            else:
                base = vol * (1.0 + float(form["PercentageVolume"]) / 100.0)
                base1 = vol1 * (1.0 + float(form.get("PercentageVolume1", "0")) / 100.0)
                volume_condition = (
                        _safe_compare(data.get("volume"), ">=", base)
                        and _safe_compare(data.get("volume"), "<=", base1)
                )

        elif form.get("ComparisonVolume", "Not used") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageVolume"])
            except Exception:
                threshold = 5.0
            volume_condition = _within_percent_check(
                data.get("volumeIndicator"), data.get("volume"),
                form["ComparisonVolume"], threshold
            )

        if volume_condition is not None:
            condition = condition and volume_condition
            counting_ += 1
            variable_results["volumeIndicator"] = bool(volume_condition)

        # -------------------------
        # MARKET CAP (in millions)
        # -------------------------
        mktcap_condition = None
        mktcap_comp_mode = form.get("ComparisonMarketCap", "Not used")
        mktcap_value = data.get("marketCap")
        
        try:
            mktcap_threshold = float(form.get("PercentageMarketCap", 0))
        except (ValueError, TypeError):
            mktcap_threshold = 0

        if mktcap_comp_mode not in _NON_SIMPLE_MODES:
            if mktcap_comp_mode == "greater":
                mktcap_condition = _safe_compare(mktcap_value, ">", mktcap_threshold)
            elif mktcap_comp_mode == "greaterEqual":
                mktcap_condition = _safe_compare(mktcap_value, ">=", mktcap_threshold)
            elif mktcap_comp_mode == "lower":
                mktcap_condition = _safe_compare(mktcap_value, "<", mktcap_threshold)
            elif mktcap_comp_mode == "lowerEqual":
                mktcap_condition = _safe_compare(mktcap_value, "<=", mktcap_threshold)

        elif form.get("ComparisonMarketCap") == "between":
            mktcap_condition = (
                    _safe_compare(data.get("marketCap"), ">=", float(form.get("PercentageMarketCap", 0)))
                    and _safe_compare(data.get("marketCap1"), "<=", float(form.get("PercentageMarketCap1", 0)))
            )

        elif form.get("ComparisonMarketCap") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageMarketCap", 5))
            except Exception:
                threshold = 5.0
            mktcap_condition = _within_percent_check(
                data.get("marketCap"), data.get("close"),
                form.get("ComparisonMarketCap"), threshold
            )

        if mktcap_condition is not None:
            condition = condition and mktcap_condition
            counting_ += 1
            variable_results["marketCap"] = bool(mktcap_condition)

        # -------------------------
        # PRICE LEVEL
        # -------------------------
        price_condition = None

        if form["ComparisonPrice"] not in _NON_SIMPLE_MODES:
            if form["ComparisonPrice"] == "greater":
                price_condition = _safe_compare(data.get("close"), ">", float(form["PercentagePrice"]))
            elif form["ComparisonPrice"] == "greaterEqual":
                price_condition = _safe_compare(data.get("close"), ">=", float(form["PercentagePrice"]))
            elif form["ComparisonPrice"] == "lower":
                price_condition = _safe_compare(data.get("close"), "<", float(form["PercentagePrice"]))
            elif form["ComparisonPrice"] == "lowerEqual":
                price_condition = _safe_compare(data.get("close"), "<=", float(form["PercentagePrice"]))

        elif form["ComparisonPrice"] == "between":
            price_condition = (
                    _safe_compare(data.get("close"), ">", float(form["PercentagePrice"]))
                    and _safe_compare(data.get("close"), "<", float(form["PercentagePrice1"]))
            )

        elif form["ComparisonPrice"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentagePrice"])
            except Exception:
                threshold = 5.0
            price_condition = _within_percent_check(
                float(form["PercentagePrice"]), data.get("close"),
                form["ComparisonPrice"], threshold
            )

        if price_condition is not None:
            condition = condition and price_condition
            counting_ += 1
            variable_results["close"] = bool(price_condition)

        # -------------------------
        # VWAP
        # -------------------------
        vwap_condition = None

        if (
                form["ComparisonVWAP"] not in _NON_SIMPLE_MODES
                and form["VWAPBool"] == "percentage"
        ):
            v = data.get("vwap")
            if v is None:
                vwap_condition = False
            else:
                base = v * (
                        1.0 + float(form["PercentageVWAP"]) / 100.0
                )

                if form["ComparisonVWAP"] == "greater":
                    vwap_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonVWAP"] == "greaterEqual":
                    vwap_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonVWAP"] == "lower":
                    vwap_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonVWAP"] == "lowerEqual":
                    vwap_condition = _safe_compare(data.get("close"), "<=", base)

        elif (
                form["ComparisonVWAP"] == "between"
                and form["VWAPBool"] == "percentage"
        ):
            v = data.get("vwap")
            v1 = data.get("vwap1")
            if v is None or v1 is None:
                vwap_condition = False
            else:
                base = v * (1.0 + float(form["PercentageVWAP"]) / 100.0)
                base1 = v1 * (1.0 + float(form["PercentageVWAP1"]) / 100.0)
                vwap_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (
                form["ComparisonVWAP"] not in _NON_SIMPLE_MODES
                and form["VWAPBool"] == "value"
        ):
            if form["ComparisonVWAP"] == "greater":
                vwap_condition = _safe_compare(data.get("vwap"), ">", float(form["PercentageVWAP"]))
            elif form["ComparisonVWAP"] == "greaterEqual":
                vwap_condition = _safe_compare(data.get("vwap"), ">=", float(form["PercentageVWAP"]))
            elif form["ComparisonVWAP"] == "lower":
                vwap_condition = _safe_compare(data.get("vwap"), "<", float(form["PercentageVWAP"]))
            elif form["ComparisonVWAP"] == "lowerEqual":
                vwap_condition = _safe_compare(data.get("vwap"), "<=", float(form["PercentageVWAP"]))

        elif (
                form["ComparisonVWAP"] == "between"
                and form["VWAPBool"] == "value"
        ):
            vwap_condition = (
                    _safe_compare(data.get("vwap"), ">=", float(form["PercentageVWAP"]))
                    and _safe_compare(data.get("vwap1"), "<=", float(form["PercentageVWAP1"]))
            )

        elif form["ComparisonVWAP"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageVWAP"])
            except Exception:
                threshold = 5.0
            vwap_condition = _within_percent_check(
                data.get("vwap"), data.get("close"),
                form["ComparisonVWAP"], threshold
            )

        if vwap_condition is not None:
            condition = condition and vwap_condition
            counting_ += 1
            variable_results["vwap"] = bool(vwap_condition)

        # -------------------------
        # FAST SMA
        # -------------------------
        fast_sma_condition = None

        if (
                form["ComparisonFastSMA"] not in _NON_SIMPLE_MODES
                and form["SMAFastBool"] == "percentage"
        ):
            sf = data.get("smaFast")
            if sf is None:
                fast_sma_condition = False
            else:
                base = sf * (
                        1.0 + float(form["PercentageFastSMA"]) / 100.0
                )

                if form["ComparisonFastSMA"] == "greater":
                    fast_sma_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonFastSMA"] == "greaterEqual":
                    fast_sma_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonFastSMA"] == "lower":
                    fast_sma_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonFastSMA"] == "lowerEqual":
                    fast_sma_condition = _safe_compare(data.get("close"), "<=", base)

        elif (
                form["ComparisonFastSMA"] == "between"
                and form["SMAFastBool"] == "percentage"
        ):
            sf = data.get("smaFast")
            sf1 = data.get("smaFast1")
            if sf is None or sf1 is None:
                fast_sma_condition = False
            else:
                base = sf * (1.0 + float(form["PercentageFastSMA"]) / 100.0)
                base1 = sf1 * (1.0 + float(form["PercentageFastSMA1"]) / 100.0)
                fast_sma_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (
                form["ComparisonFastSMA"] not in _NON_SIMPLE_MODES
                and form["SMAFastBool"] == "value"
        ):
            if form["ComparisonFastSMA"] == "greater":
                fast_sma_condition = (
                    _safe_compare(data.get("smaFast"), ">", float(form["PercentageFastSMA"]))
                )
            elif form["ComparisonFastSMA"] == "greaterEqual":
                fast_sma_condition = (
                    _safe_compare(data.get("smaFast"), ">=", float(form["PercentageFastSMA"]))
                )
            elif form["ComparisonFastSMA"] == "lower":
                fast_sma_condition = (
                    _safe_compare(data.get("smaFast"), "<", float(form["PercentageFastSMA"]))
                )
            elif form["ComparisonFastSMA"] == "lowerEqual":
                fast_sma_condition = (
                    _safe_compare(data.get("smaFast"), "<=", float(form["PercentageFastSMA"]))
                )

        elif (
                form["ComparisonFastSMA"] == "between"
                and form["SMAFastBool"] == "value"
        ):
            fast_sma_condition = (
                    _safe_compare(data.get("smaFast"), ">=", float(form["PercentageFastSMA"]))
                    and _safe_compare(data.get("smaFast1"), "<=", float(form["PercentageFastSMA1"]))
            )

        elif form["ComparisonFastSMA"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageFastSMA"])
            except Exception:
                threshold = 5.0
            fast_sma_condition = _within_percent_check(
                data.get("smaFast"), data.get("close"),
                form["ComparisonFastSMA"], threshold
            )

        if fast_sma_condition is not None:
            condition = condition and fast_sma_condition
            counting_ += 1
            variable_results["smaFast"] = bool(fast_sma_condition)

        # -------------------------
        # MEDIUM SMA
        # -------------------------
        medium_sma_condition = None

        if (
                form["ComparisonMediumSMA"] not in _NON_SIMPLE_MODES
                and form["SMAMediumBool"] == "percentage"
        ):
            sf = data.get("smaMedium")
            if sf is None:
                medium_sma_condition = False
            else:
                base = sf * (
                        1.0 + float(form["PercentageMediumSMA"]) / 100.0
                )

                if form["ComparisonMediumSMA"] == "greater":
                    medium_sma_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonMediumSMA"] == "greaterEqual":
                    medium_sma_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonMediumSMA"] == "lower":
                    medium_sma_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonMediumSMA"] == "lowerEqual":
                    medium_sma_condition = _safe_compare(data.get("close"), "<=", base)

        elif (
                form["ComparisonMediumSMA"] == "between"
                and form["SMAMediumBool"] == "percentage"
        ):
            sf = data.get("smaMedium")
            sf1 = data.get("smaMedium1")
            if sf is None or sf1 is None:
                medium_sma_condition = False
            else:
                base = sf * (1.0 + float(form["PercentageMediumSMA"]) / 100.0)
                base1 = sf1 * (1.0 + float(form["PercentageMediumSMA1"]) / 100.0)
                medium_sma_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (
                form["ComparisonMediumSMA"] not in _NON_SIMPLE_MODES
                and form["SMAMediumBool"] == "value"
        ):
            if form["ComparisonMediumSMA"] == "greater":
                medium_sma_condition = (
                    _safe_compare(data.get("smaMedium"), ">", float(form["PercentageMediumSMA"]))
                )
            elif form["ComparisonMediumSMA"] == "greaterEqual":
                medium_sma_condition = (
                    _safe_compare(data.get("smaMedium"), ">=", float(form["PercentageMediumSMA"]))
                )
            elif form["ComparisonMediumSMA"] == "lower":
                medium_sma_condition = (
                    _safe_compare(data.get("smaMedium"), "<", float(form["PercentageMediumSMA"]))
                )
            elif form["ComparisonMediumSMA"] == "lowerEqual":
                medium_sma_condition = (
                    _safe_compare(data.get("smaMedium"), "<=", float(form["PercentageMediumSMA"]))
                )

        elif (
                form["ComparisonMediumSMA"] == "between"
                and form["SMAMediumBool"] == "value"
        ):
            medium_sma_condition = (
                    _safe_compare(data.get("smaMedium"), ">=", float(form["PercentageMediumSMA"]))
                    and _safe_compare(data.get("smaMedium1"), "<=", float(form["PercentageMediumSMA1"]))
            )

        elif form["ComparisonMediumSMA"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageMediumSMA"])
            except Exception:
                threshold = 5.0
            medium_sma_condition = _within_percent_check(
                data.get("smaMedium"), data.get("close"),
                form["ComparisonMediumSMA"], threshold
            )

        if medium_sma_condition is not None:
            condition = condition and medium_sma_condition
            counting_ += 1
            variable_results["smaMedium"] = bool(medium_sma_condition)

        # -------------------------
        # SLOW SMA
        # -------------------------
        slow_sma_condition = None

        if (
                form["ComparisonSlowSMA"] not in _NON_SIMPLE_MODES
                and form["smaslowyesno"] == "percentage"
        ):
            sh = data.get("smaSlow")
            if sh is None:
                slow_sma_condition = False
            else:
                base = sh * (
                        1.0 + float(form["PercentageSlowSMA"]) / 100.0
                )

                if form["ComparisonSlowSMA"] == "greater":
                    slow_sma_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonSlowSMA"] == "greaterEqual":
                    slow_sma_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonSlowSMA"] == "lower":
                    slow_sma_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonSlowSMA"] == "lowerEqual":
                    slow_sma_condition = _safe_compare(data.get("close"), "<=", base)

        elif (
                form["ComparisonSlowSMA"] == "between"
                and form["smaslowyesno"] == "percentage"
        ):
            sh = data.get("smaSlow")
            sh1 = data.get("smaSlow1")
            if sh is None or sh1 is None:
                slow_sma_condition = False
            else:
                base = sh * (1.0 + float(form["PercentageSlowSMA"]) / 100.0)
                base1 = sh1 * (1.0 + float(form["PercentageSlowSMA1"]) / 100.0)
                slow_sma_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (
                form["ComparisonSlowSMA"] not in _NON_SIMPLE_MODES
                and form["smaslowyesno"] == "value"
        ):
            if form["ComparisonSlowSMA"] == "greater":
                slow_sma_condition = (
                    _safe_compare(data.get("smaSlow"), ">", float(form["PercentageSlowSMA"]))
                )
            elif form["ComparisonSlowSMA"] == "greaterEqual":
                slow_sma_condition = (
                    _safe_compare(data.get("smaSlow"), ">=", float(form["PercentageSlowSMA"]))
                )
            elif form["ComparisonSlowSMA"] == "lower":
                slow_sma_condition = (
                    _safe_compare(data.get("smaSlow"), "<", float(form["PercentageSlowSMA"]))
                )
            elif form["ComparisonSlowSMA"] == "lowerEqual":
                slow_sma_condition = (
                    _safe_compare(data.get("smaSlow"), "<=", float(form["PercentageSlowSMA"]))
                )

        elif (
                form["ComparisonSlowSMA"] == "between"
                and form["smaslowyesno"] == "value"
        ):
            slow_sma_condition = (
                    _safe_compare(data.get("smaSlow"), ">=", float(form["PercentageSlowSMA"]))
                    and _safe_compare(data.get("smaSlow1"), "<=", float(form["PercentageSlowSMA1"]))
            )

        elif form["ComparisonSlowSMA"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageSlowSMA"])
            except Exception:
                threshold = 5.0
            slow_sma_condition = _within_percent_check(
                data.get("smaSlow"), data.get("close"),
                form["ComparisonSlowSMA"], threshold
            )

        if slow_sma_condition is not None:
            condition = condition and slow_sma_condition
            counting_ += 1
            variable_results["smaSlow"] = bool(slow_sma_condition)

        # -------------------------
        # RSI
        # -------------------------
        rsi_condition = None

        if form["ComparisonRSI"] not in _NON_SIMPLE_MODES:
            if form["ComparisonRSI"] == "greater":
                rsi_condition = _safe_compare(data.get("rsi"), ">", float(form["PercentageRSI"]))
            elif form["ComparisonRSI"] == "greaterEqual":
                rsi_condition = _safe_compare(data.get("rsi"), ">=", float(form["PercentageRSI"]))
            elif form["ComparisonRSI"] == "lower":
                rsi_condition = _safe_compare(data.get("rsi"), "<", float(form["PercentageRSI"]))
            elif form["ComparisonRSI"] == "lowerEqual":
                rsi_condition = _safe_compare(data.get("rsi"), "<=", float(form["PercentageRSI"]))

        elif form["ComparisonRSI"] == "between":
            rsi_condition = (
                    _safe_compare(data.get("rsi"), ">=", float(form["PercentageRSI"]))
                    and _safe_compare(data.get("rsi1"), "<=", float(form["PercentageRSI1"]))
            )

        elif form["ComparisonRSI"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageRSI"])
            except Exception:
                threshold = 5.0
            rsi_condition = _within_percent_check(
                data.get("rsi"), data.get("close"),
                form["ComparisonRSI"], threshold
            )

        if rsi_condition is not None:
            condition = condition and rsi_condition
            counting_ += 1
            variable_results["rsi"] = bool(rsi_condition)

        # -------------------------
        # FAST EMA
        # -------------------------
        emaFast_condition = None

        if form.get("ComparisonFastEMA", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonFastEMA") == "greater":
                emaFast_condition = _safe_compare(data.get("emaFast"), ">", float(form.get("PercentageFastEMA")))
            elif form.get("ComparisonFastEMA") == "greaterEqual":
                emaFast_condition = _safe_compare(data.get("emaFast"), ">=", float(form.get("PercentageFastEMA")))
            elif form.get("ComparisonFastEMA") == "lower":
                emaFast_condition = _safe_compare(data.get("emaFast"), "<", float(form.get("PercentageFastEMA")))
            elif form.get("ComparisonFastEMA") == "lowerEqual":
                emaFast_condition = _safe_compare(data.get("emaFast"), "<=", float(form.get("PercentageFastEMA")))
        elif form.get("ComparisonFastEMA") == "between":
            emaFast_condition = (
                    _safe_compare(data.get("emaFast"), ">=", float(form.get("PercentageFastEMA")))
                    and _safe_compare(data.get("emaFast1"), "<=", float(form.get("PercentageFastEMA1")))
            )

        elif form.get("ComparisonFastEMA") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageFastEMA", 5))
            except Exception:
                threshold = 5.0
            emaFast_condition = _within_percent_check(
                data.get("emaFast"), data.get("close"),
                form.get("ComparisonFastEMA"), threshold
            )

        if emaFast_condition is not None:
            condition = condition and emaFast_condition
            counting_ += 1
            variable_results["emaFast"] = bool(emaFast_condition)

        # -------------------------
        # SLOW EMA
        # -------------------------
        emaSlow_condition = None

        if form.get("ComparisonSlowEMA", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonSlowEMA") == "greater":
                emaSlow_condition = _safe_compare(data.get("emaSlow"), ">", float(form.get("PercentageSlowEMA")))
            elif form.get("ComparisonSlowEMA") == "greaterEqual":
                emaSlow_condition = _safe_compare(data.get("emaSlow"), ">=", float(form.get("PercentageSlowEMA")))
            elif form.get("ComparisonSlowEMA") == "lower":
                emaSlow_condition = _safe_compare(data.get("emaSlow"), "<", float(form.get("PercentageSlowEMA")))
            elif form.get("ComparisonSlowEMA") == "lowerEqual":
                emaSlow_condition = _safe_compare(data.get("emaSlow"), "<=", float(form.get("PercentageSlowEMA")))
        elif form.get("ComparisonSlowEMA") == "between":
            emaSlow_condition = (
                    _safe_compare(data.get("emaSlow"), ">=", float(form.get("PercentageSlowEMA")))
                    and _safe_compare(data.get("emaSlow1"), "<=", float(form.get("PercentageSlowEMA1")))
            )

        elif form.get("ComparisonSlowEMA") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageSlowEMA", 5))
            except Exception:
                threshold = 5.0
            emaSlow_condition = _within_percent_check(
                data.get("emaSlow"), data.get("close"),
                form.get("ComparisonSlowEMA"), threshold
            )

        if emaSlow_condition is not None:
            condition = condition and emaSlow_condition
            counting_ += 1
            variable_results["emaSlow"] = bool(emaSlow_condition)

        # -------------------------
        # OBV
        # -------------------------
        obv_condition = None

        if form.get("ComparisonOBV", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonOBV") == "greater":
                obv_condition = _safe_compare(data.get("obv"), ">", float(form.get("PercentageOBV")))
            elif form.get("ComparisonOBV") == "greaterEqual":
                obv_condition = _safe_compare(data.get("obv"), ">=", float(form.get("PercentageOBV")))
            elif form.get("ComparisonOBV") == "lower":
                obv_condition = _safe_compare(data.get("obv"), "<", float(form.get("PercentageOBV")))
            elif form.get("ComparisonOBV") == "lowerEqual":
                obv_condition = _safe_compare(data.get("obv"), "<=", float(form.get("PercentageOBV")))
        elif form.get("ComparisonOBV") == "between":
            obv_condition = (
                    _safe_compare(data.get("obv"), ">=", float(form.get("PercentageOBV")))
                    and _safe_compare(data.get("obv1"), "<=", float(form.get("PercentageOBV1")))
            )

        elif form.get("ComparisonOBV") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageOBV", 5))
            except Exception:
                threshold = 5.0
            obv_condition = _within_percent_check(
                data.get("obv"), data.get("close"),
                form.get("ComparisonOBV"), threshold
            )

        if obv_condition is not None:
            condition = condition and obv_condition
            counting_ += 1
            variable_results["obv"] = bool(obv_condition)

        # -------------------------
        # ATR
        # -------------------------
        atr_condition = None

        if form.get("ComparisonATR", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonATR") == "greater":
                atr_condition = _safe_compare(data.get("atr"), ">", float(form.get("PercentageATR")))
            elif form.get("ComparisonATR") == "greaterEqual":
                atr_condition = _safe_compare(data.get("atr"), ">=", float(form.get("PercentageATR")))
            elif form.get("ComparisonATR") == "lower":
                atr_condition = _safe_compare(data.get("atr"), "<", float(form.get("PercentageATR")))
            elif form.get("ComparisonATR") == "lowerEqual":
                atr_condition = _safe_compare(data.get("atr"), "<=", float(form.get("PercentageATR")))
        elif form.get("ComparisonATR") == "between":
            atr_condition = (
                    _safe_compare(data.get("atr"), ">=", float(form.get("PercentageATR")))
                    and _safe_compare(data.get("atr1"), "<=", float(form.get("PercentageATR1")))
            )

        elif form.get("ComparisonATR") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageATR", 5))
            except Exception:
                threshold = 5.0
            atr_condition = _within_percent_check(
                data.get("atr"), data.get("close"),
                form.get("ComparisonATR"), threshold
            )

        if atr_condition is not None:
            condition = condition and atr_condition
            counting_ += 1
            variable_results["atr"] = bool(atr_condition)

        # -------------------------
        # PREVIOUS CLOSE
        # -------------------------
        prev_condition = None

        if (form.get("ComparisonPrevClose", "Not used") not in _NON_SIMPLE_MODES and
                form["PrevCloseBool"] == "percentage"):
            v = data.get("prevClose")
            if v is None:
                prev_condition = False
            else:
                base = v * (1.0 + float(form["PercentagePrevClose"]) / 100.0)
                if form["ComparisonPrevClose"] == "greater":
                    prev_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonPrevClose"] == "greaterEqual":
                    prev_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonPrevClose"] == "lower":
                    prev_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonPrevClose"] == "lowerEqual":
                    prev_condition = _safe_compare(data.get("close"), "<=", base)

        elif form.get("ComparisonPrevClose", "") == "between" and form["PrevCloseBool"] == "percentage":
            v = data.get("prevClose")
            v1 = data.get("prevClose1")
            if v is None or v1 is None:
                prev_condition = False
            else:
                base = v * (1.0 + float(form["PercentagePrevClose"]) / 100.0)
                base1 = v1 * (1.0 + float(form["PercentagePrevClose1"]) / 100.0)
                prev_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (form.get("ComparisonPrevClose", "Not used") not in _NON_SIMPLE_MODES and
              form["PrevCloseBool"] == "value"):
            if form["ComparisonPrevClose"] == "greater":
                prev_condition = _safe_compare(data.get("prevClose"), ">", float(form["PercentagePrevClose"]))
            elif form["ComparisonPrevClose"] == "greaterEqual":
                prev_condition = _safe_compare(data.get("prevClose"), ">=", float(form["PercentagePrevClose"]))
            elif form["ComparisonPrevClose"] == "lower":
                prev_condition = _safe_compare(data.get("prevClose"), "<", float(form["PercentagePrevClose"]))
            elif form["ComparisonPrevClose"] == "lowerEqual":
                prev_condition = _safe_compare(data.get("prevClose"), "<=", float(form["PercentagePrevClose"]))
        elif form.get("ComparisonPrevClose", "") == "between" and form["PrevCloseBool"] == "value":
            prev_condition = (
                    _safe_compare(data.get("prevClose"), ">=", float(form["PercentagePrevClose"]))
                    and _safe_compare(data.get("prevClose1"), "<=", float(form["PercentagePrevClose1"]))
            )

        elif form.get("ComparisonPrevClose") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentagePrevClose"])
            except Exception:
                threshold = 5.0
            prev_condition = _within_percent_check(
                data.get("prevClose"), data.get("close"),
                form["ComparisonPrevClose"], threshold
            )

        if prev_condition is not None:
            condition = condition and prev_condition
            counting_ += 1
            variable_results["prevClose"] = bool(prev_condition)

        # -------------------------
        # LOW OF DAY
        # -------------------------
        low_condition = None

        if (form.get("ComparisonLowOfDay", "Not used") not in _NON_SIMPLE_MODES and
                form["LowOfDayBool"] == "percentage"):
            v = data.get("lowOfDay")
            if v is None:
                low_condition = False
            else:
                base = v * (1.0 + float(form["PercentageLowOfDay"]) / 100.0)
                if form["ComparisonLowOfDay"] == "greater":
                    low_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonLowOfDay"] == "greaterEqual":
                    low_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonLowOfDay"] == "lower":
                    low_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonLowOfDay"] == "lowerEqual":
                    low_condition = _safe_compare(data.get("close"), "<=", base)

        elif form.get("ComparisonLowOfDay", "") == "between" and form["LowOfDayBool"] == "percentage":
            v = data.get("lowOfDay")
            v1 = data.get("lowOfDay1")
            if v is None or v1 is None:
                low_condition = False
            else:
                base = v * (1.0 + float(form["PercentageLowOfDay"]) / 100.0)
                base1 = v1 * (1.0 + float(form["PercentageLowOfDay1"]) / 100.0)
                low_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (form.get("ComparisonLowOfDay", "Not used") not in _NON_SIMPLE_MODES and
              form["LowOfDayBool"] == "value"):
            if form["ComparisonLowOfDay"] == "greater":
                low_condition = _safe_compare(data.get("lowOfDay"), ">", float(form["PercentageLowOfDay"]))
            elif form["ComparisonLowOfDay"] == "greaterEqual":
                low_condition = _safe_compare(data.get("lowOfDay"), ">=", float(form["PercentageLowOfDay"]))
            elif form["ComparisonLowOfDay"] == "lower":
                low_condition = _safe_compare(data.get("lowOfDay"), "<", float(form["PercentageLowOfDay"]))
            elif form["ComparisonLowOfDay"] == "lowerEqual":
                low_condition = _safe_compare(data.get("lowOfDay"), "<=", float(form["PercentageLowOfDay"]))
        elif form.get("ComparisonLowOfDay", "") == "between" and form["LowOfDayBool"] == "value":
            low_condition = (
                    _safe_compare(data.get("lowOfDay"), ">=", float(form["PercentageLowOfDay"]))
                    and _safe_compare(data.get("lowOfDay1"), "<=", float(form["PercentageLowOfDay1"]))
            )

        elif form.get("ComparisonLowOfDay") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageLowOfDay"])
            except Exception:
                threshold = 5.0
            low_condition = _within_percent_check(
                data.get("lowOfDay"), data.get("close"),
                form["ComparisonLowOfDay"], threshold
            )

        if low_condition is not None:
            condition = condition and low_condition
            counting_ += 1
            variable_results["lowOfDay"] = bool(low_condition)

        # -------------------------
        # HIGH OF DAY
        # -------------------------
        high_condition = None

        if (form.get("ComparisonHighOfDay", "Not used") not in _NON_SIMPLE_MODES and
                form["HighOfDayBool"] == "percentage"):
            v = data.get("highOfDay")
            if v is None:
                high_condition = False
            else:
                base = v * (1.0 + float(form["PercentageHighOfDay"]) / 100.0)
                if form["ComparisonHighOfDay"] == "greater":
                    high_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonHighOfDay"] == "greaterEqual":
                    high_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonHighOfDay"] == "lower":
                    high_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonHighOfDay"] == "lowerEqual":
                    high_condition = _safe_compare(data.get("close"), "<=", base)

        elif form.get("ComparisonHighOfDay", "") == "between" and form["HighOfDayBool"] == "percentage":
            v = data.get("highOfDay")
            v1 = data.get("highOfDay1")
            if v is None or v1 is None:
                high_condition = False
            else:
                base = v * (1.0 + float(form["PercentageHighOfDay"]) / 100.0)
                base1 = v1 * (1.0 + float(form["PercentageHighOfDay1"]) / 100.0)
                high_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (form.get("ComparisonHighOfDay", "Not used") not in _NON_SIMPLE_MODES and
              form["HighOfDayBool"] == "value"):
            if form["ComparisonHighOfDay"] == "greater":
                high_condition = _safe_compare(data.get("highOfDay"), ">", float(form["PercentageHighOfDay"]))
            elif form["ComparisonHighOfDay"] == "greaterEqual":
                high_condition = _safe_compare(data.get("highOfDay"), ">=", float(form["PercentageHighOfDay"]))
            elif form["ComparisonHighOfDay"] == "lower":
                high_condition = _safe_compare(data.get("highOfDay"), "<", float(form["PercentageHighOfDay"]))
            elif form["ComparisonHighOfDay"] == "lowerEqual":
                high_condition = _safe_compare(data.get("highOfDay"), "<=", float(form["PercentageHighOfDay"]))
        elif form.get("ComparisonHighOfDay", "") == "between" and form["HighOfDayBool"] == "value":
            high_condition = (
                    _safe_compare(data.get("highOfDay"), ">=", float(form["PercentageHighOfDay"]))
                    and _safe_compare(data.get("highOfDay1"), "<=", float(form["PercentageHighOfDay1"]))
            )

        elif form.get("ComparisonHighOfDay") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageHighOfDay"])
            except Exception:
                threshold = 5.0
            high_condition = _within_percent_check(
                data.get("highOfDay"), data.get("close"),
                form["ComparisonHighOfDay"], threshold
            )

        if high_condition is not None:
            condition = condition and high_condition
            counting_ += 1
            variable_results["highOfDay"] = bool(high_condition)

        # -------------------------
        # PIVOT POINT
        # -------------------------
        pivot_condition = None

        if (
                form["ComparisonPivotPoint"] not in _NON_SIMPLE_MODES
                and form["pivotPointBool"] == "percentage"
        ):
            pp_name = list(data["Pivot"].keys())[0]
            pivot = data["Pivot"][pp_name]

            if pivot is None:
                pivot_condition = False
            else:
                base = pivot * (
                        1.0 + float(form["PercentagePivotPoint"]) / 100.0
                )

                if form["ComparisonPivotPoint"] == "greater":
                    pivot_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonPivotPoint"] == "greaterEqual":
                    pivot_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonPivotPoint"] == "lower":
                    pivot_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonPivotPoint"] == "lowerEqual":
                    pivot_condition = _safe_compare(data.get("close"), "<=", base)

        elif (
                form["ComparisonPivotPoint"] == "between"
                and form["pivotPointBool"] == "percentage"
        ):
            pp_name = list(data["Pivot"].keys())[0]
            pp_name1 = list(data["Pivot1"].keys())[0]
            pivot = data["Pivot"][pp_name]
            pivot1 = data["Pivot1"][pp_name1]

            close_val = data.get("close")

            if close_val is None or pivot is None or pivot1 is None:
                pivot_condition = False
            else:
                base_close = close_val * (1.0 + float(form["PercentagePivotPoint"]) / 100.0)
                base_pivot1 = pivot1 * (1.0 + float(form["PercentagePivotPoint1"]) / 100.0)

                pivot_condition = (
                        _safe_compare(base_close, ">=", pivot)
                        and _safe_compare(base_close, "<=", base_pivot1)
                )

        elif (
                form["ComparisonPivotPoint"] not in _NON_SIMPLE_MODES
                and form["pivotPointBool"] == "value"
        ):
            pp_name = list(data["Pivot"].keys())[0]
            pivot = data["Pivot"][pp_name]

            if pivot is None:
                pivot_condition = False
            else:
                if form["ComparisonPivotPoint"] == "greater":
                    pivot_condition = _safe_compare(pivot, ">", float(form["PercentagePivotPoint"]))
                elif form["ComparisonPivotPoint"] == "greaterEqual":
                    pivot_condition = _safe_compare(pivot, ">=", float(form["PercentagePivotPoint"]))
                elif form["ComparisonPivotPoint"] == "lower":
                    pivot_condition = _safe_compare(float(form["PercentagePivotPoint"]), "<", pivot)
                elif form["ComparisonPivotPoint"] == "lowerEqual":
                    pivot_condition = _safe_compare(float(form["PercentagePivotPoint"]), "<=", pivot)

        elif (
                form["ComparisonPivotPoint"] == "between"
                and form["pivotPointBool"] == "value"
        ):
            pp_name = list(data["Pivot"].keys())[0]
            pp_name1 = list(data["Pivot1"].keys())[0]
            pivot = data["Pivot"][pp_name]
            pivot1 = data["Pivot1"][pp_name1]

            pivot_condition = (
                    _safe_compare(pivot, ">=", float(form["PercentagePivotPoint"]))
                    and _safe_compare(float(form["PercentagePivotPoint1"]), ">=", pivot1)
            )

        elif form["ComparisonPivotPoint"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                pp_name = list(data["Pivot"].keys())[0]
                pivot = data["Pivot"][pp_name]
            except Exception:
                pivot = None
            try:
                threshold = float(form["PercentagePivotPoint"])
            except Exception:
                threshold = 5.0
            pivot_condition = _within_percent_check(
                pivot, data.get("close"),
                form["ComparisonPivotPoint"], threshold
            )

        if pivot_condition is not None:
            condition = condition and pivot_condition
            counting_ += 1
            variable_results["Pivot"] = bool(pivot_condition)

        # -------------------------
        # PIVOT POINT 2 (Second Pivot)
        # -------------------------
        pivot2_condition = None
        
        if form.get("ComparisonPivotPoint2") and form.get("ComparisonPivotPoint2") != "Not used" and "Pivot2" in data:
            pp_name2 = list(data.get("Pivot2", {}).keys())[0] if data.get("Pivot2") else None
            pivot2 = data.get("Pivot2", {}).get(pp_name2) if pp_name2 else None
            
            if pivot2 is not None:
                if (
                    form.get("ComparisonPivotPoint2") not in _NON_SIMPLE_MODES
                    and form.get("pivotPointBool", "value") == "percentage"
                ):
                    base2 = pivot2 * (1.0 + float(form.get("PercentagePivotPoint2", 0)) / 100.0)
                    if form["ComparisonPivotPoint2"] == "greater":
                        pivot2_condition = _safe_compare(data.get("close"), ">", base2)
                    elif form["ComparisonPivotPoint2"] == "greaterEqual":
                        pivot2_condition = _safe_compare(data.get("close"), ">=", base2)
                    elif form["ComparisonPivotPoint2"] == "lower":
                        pivot2_condition = _safe_compare(data.get("close"), "<", base2)
                    elif form["ComparisonPivotPoint2"] == "lowerEqual":
                        pivot2_condition = _safe_compare(data.get("close"), "<=", base2)
                
                elif (
                    form.get("ComparisonPivotPoint2") not in _NON_SIMPLE_MODES
                    and form.get("pivotPointBool", "value") == "value"
                ):
                    if form["ComparisonPivotPoint2"] == "greater":
                        pivot2_condition = _safe_compare(pivot2, ">", float(form.get("PercentagePivotPoint2", 0)))
                    elif form["ComparisonPivotPoint2"] == "greaterEqual":
                        pivot2_condition = _safe_compare(pivot2, ">=", float(form.get("PercentagePivotPoint2", 0)))
                    elif form["ComparisonPivotPoint2"] == "lower":
                        pivot2_condition = _safe_compare(float(form.get("PercentagePivotPoint2", 0)), "<", pivot2)
                    elif form["ComparisonPivotPoint2"] == "lowerEqual":
                        pivot2_condition = _safe_compare(float(form.get("PercentagePivotPoint2", 0)), "<=", pivot2)
                
                elif form.get("ComparisonPivotPoint2") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
                    threshold = float(form.get("PercentagePivotPoint2", 5.0))
                    pivot2_condition = _within_percent_check(
                        pivot2, data.get("close"),
                        form["ComparisonPivotPoint2"], threshold
                    )
            
            if pivot2_condition is not None:
                condition = condition and pivot2_condition
                counting_ += 1
                variable_results["Pivot2"] = bool(pivot2_condition)

        # -------------------------
        # PIVOT POINT 3 (Third Pivot)
        # -------------------------
        pivot3_condition = None
        
        if form.get("ComparisonPivotPoint3") and form.get("ComparisonPivotPoint3") != "Not used" and "Pivot3" in data:
            pp_name3 = list(data.get("Pivot3", {}).keys())[0] if data.get("Pivot3") else None
            pivot3 = data.get("Pivot3", {}).get(pp_name3) if pp_name3 else None
            
            if pivot3 is not None:
                if (
                    form.get("ComparisonPivotPoint3") not in _NON_SIMPLE_MODES
                    and form.get("pivotPointBool", "value") == "percentage"
                ):
                    base3 = pivot3 * (1.0 + float(form.get("PercentagePivotPoint3", 0)) / 100.0)
                    if form["ComparisonPivotPoint3"] == "greater":
                        pivot3_condition = _safe_compare(data.get("close"), ">", base3)
                    elif form["ComparisonPivotPoint3"] == "greaterEqual":
                        pivot3_condition = _safe_compare(data.get("close"), ">=", base3)
                    elif form["ComparisonPivotPoint3"] == "lower":
                        pivot3_condition = _safe_compare(data.get("close"), "<", base3)
                    elif form["ComparisonPivotPoint3"] == "lowerEqual":
                        pivot3_condition = _safe_compare(data.get("close"), "<=", base3)
                
                elif (
                    form.get("ComparisonPivotPoint3") not in _NON_SIMPLE_MODES
                    and form.get("pivotPointBool", "value") == "value"
                ):
                    if form["ComparisonPivotPoint3"] == "greater":
                        pivot3_condition = _safe_compare(pivot3, ">", float(form.get("PercentagePivotPoint3", 0)))
                    elif form["ComparisonPivotPoint3"] == "greaterEqual":
                        pivot3_condition = _safe_compare(pivot3, ">=", float(form.get("PercentagePivotPoint3", 0)))
                    elif form["ComparisonPivotPoint3"] == "lower":
                        pivot3_condition = _safe_compare(float(form.get("PercentagePivotPoint3", 0)), "<", pivot3)
                    elif form["ComparisonPivotPoint3"] == "lowerEqual":
                        pivot3_condition = _safe_compare(float(form.get("PercentagePivotPoint3", 0)), "<=", pivot3)
                
                elif form.get("ComparisonPivotPoint3") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
                    threshold = float(form.get("PercentagePivotPoint3", 5.0))
                    pivot3_condition = _within_percent_check(
                        pivot3, data.get("close"),
                        form["ComparisonPivotPoint3"], threshold
                    )
            
            if pivot3_condition is not None:
                condition = condition and pivot3_condition
                counting_ += 1
                variable_results["Pivot3"] = bool(pivot3_condition)

        # -------------------------
        # RELATIVE VOLUME
        # -------------------------
        relative_volume_condition = None

        if form["ComparisonRelativeVolume"] not in _NON_SIMPLE_MODES:
            if form["ComparisonRelativeVolume"] == "greater":
                relative_volume_condition = (
                    _safe_compare(data.get("relativeVolume"), ">", float(form["PercentageRelativeVolume"]))
                )
            elif form["ComparisonRelativeVolume"] == "greaterEqual":
                relative_volume_condition = (
                    _safe_compare(data.get("relativeVolume"), ">=", float(form["PercentageRelativeVolume"]))
                )
            elif form["ComparisonRelativeVolume"] == "lower":
                relative_volume_condition = (
                    _safe_compare(data.get("relativeVolume"), "<", float(form["PercentageRelativeVolume"]))
                )
            elif form["ComparisonRelativeVolume"] == "lowerEqual":
                relative_volume_condition = (
                    _safe_compare(data.get("relativeVolume"), "<=", float(form["PercentageRelativeVolume"]))
                )

        elif form["ComparisonRelativeVolume"] == "between":
            relative_volume_condition = (
                    _safe_compare(data.get("relativeVolume"), ">", float(form["PercentageRelativeVolume"]))
                    and _safe_compare(data.get("relativeVolume1"), "<", float(form["PercentageRelativeVolume1"]))
            )

        elif form["ComparisonRelativeVolume"] in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form["PercentageRelativeVolume"])
            except Exception:
                threshold = 5.0
            relative_volume_condition = _within_percent_check(
                data.get("relativeVolume"), data.get("volume"),
                form["ComparisonRelativeVolume"], threshold
            )

        if relative_volume_condition is not None:
            condition = condition and relative_volume_condition
            counting_ += 1
            variable_results["relativeVolume"] = bool(relative_volume_condition)

        # -------------------------
        # CROSS 50 SMA
        # -------------------------
        cross_50_condition = None
        cross50_mode = form.get("ComparisonCross50SMA", "Not used")

        # Always set the SMA-value column color (green = above, red = below)
        is_above_50 = data.get("cross50SMA_isAbove")
        if is_above_50 is not None:
            variable_results["cross50SMA_val"] = bool(is_above_50)

        if cross50_mode == "crossAbove":
            cross_50_condition = data.get("cross50SMA_above", False)
        elif cross50_mode == "crossBelow":
            cross_50_condition = data.get("cross50SMA_below", False)
        elif cross50_mode in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            pct_from = data.get("cross50SMA_pctFromSMA")
            try:
                threshold = float(form.get("PercentageCross50SMA", 5))
            except Exception:
                threshold = 5.0
            if pct_from is not None:
                if cross50_mode == "withinPercentAbove":
                    cross_50_condition = 0 <= pct_from <= threshold
                elif cross50_mode == "withinPercentBelow":
                    cross_50_condition = -threshold <= pct_from <= 0
                else:  # withinPercentEither
                    cross_50_condition = abs(pct_from) <= threshold
            else:
                cross_50_condition = False
        elif (
            cross50_mode not in _NON_SIMPLE_MODES
            and form.get("Cross50SMABool", "percentage") == "percentage"
        ):
            sf = data.get("cross50SMA_value")
            if sf is None:
                cross_50_condition = False
            else:
                base = sf * (1.0 + float(form.get("PercentageCross50SMA", 0)) / 100.0)
                if cross50_mode == "greater":
                    cross_50_condition = _safe_compare(data.get("close"), ">", base)
                elif cross50_mode == "greaterEqual":
                    cross_50_condition = _safe_compare(data.get("close"), ">=", base)
                elif cross50_mode == "lower":
                    cross_50_condition = _safe_compare(data.get("close"), "<", base)
                elif cross50_mode == "lowerEqual":
                    cross_50_condition = _safe_compare(data.get("close"), "<=", base)
        elif cross50_mode == "between" and form.get("Cross50SMABool", "percentage") == "percentage":
            sf = data.get("cross50SMA_value")
            if sf is None:
                cross_50_condition = False
            else:
                base = sf * (1.0 + float(form.get("PercentageCross50SMA", 0)) / 100.0)
                cross_50_condition = (
                    _safe_compare(data.get("close"), ">=", base)
                )
        elif (
            cross50_mode not in _NON_SIMPLE_MODES
            and form.get("Cross50SMABool", "percentage") == "value"
        ):
            try:
                threshold = float(form.get("PercentageCross50SMA", 0))
            except Exception:
                threshold = 0
            sf = data.get("cross50SMA_value")
            if cross50_mode == "greater":
                cross_50_condition = _safe_compare(sf, ">", threshold)
            elif cross50_mode == "greaterEqual":
                cross_50_condition = _safe_compare(sf, ">=", threshold)
            elif cross50_mode == "lower":
                cross_50_condition = _safe_compare(sf, "<", threshold)
            elif cross50_mode == "lowerEqual":
                cross_50_condition = _safe_compare(sf, "<=", threshold)
        elif cross50_mode == "between" and form.get("Cross50SMABool", "percentage") == "value":
            try:
                threshold = float(form.get("PercentageCross50SMA", 0))
            except Exception:
                threshold = 0
            cross_50_condition = _safe_compare(data.get("cross50SMA_value"), ">=", threshold)

        if cross_50_condition is not None:
            condition = condition and cross_50_condition
            counting_ += 1
            variable_results["cross50SMA"] = bool(cross_50_condition)

        # -------------------------
        # CROSS 200 SMA
        # -------------------------
        cross_200_condition = None
        cross200_mode = form.get("ComparisonCross200SMA", "Not used")

        # Always set the SMA-value column color (green = above, red = below)
        is_above_200 = data.get("cross200SMA_isAbove")
        if is_above_200 is not None:
            variable_results["cross200SMA_val"] = bool(is_above_200)

        if cross200_mode == "crossAbove":
            cross_200_condition = data.get("cross200SMA_above", False)
        elif cross200_mode == "crossBelow":
            cross_200_condition = data.get("cross200SMA_below", False)
        elif cross200_mode in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            pct_from = data.get("cross200SMA_pctFromSMA")
            try:
                threshold = float(form.get("PercentageCross200SMA", 5))
            except Exception:
                threshold = 5.0
            if pct_from is not None:
                if cross200_mode == "withinPercentAbove":
                    cross_200_condition = 0 <= pct_from <= threshold
                elif cross200_mode == "withinPercentBelow":
                    cross_200_condition = -threshold <= pct_from <= 0
                else:  # withinPercentEither
                    cross_200_condition = abs(pct_from) <= threshold
            else:
                cross_200_condition = False
        elif (
            cross200_mode not in _NON_SIMPLE_MODES
            and form.get("Cross200SMABool", "percentage") == "percentage"
        ):
            sf = data.get("cross200SMA_value")
            if sf is None:
                cross_200_condition = False
            else:
                base = sf * (1.0 + float(form.get("PercentageCross200SMA", 0)) / 100.0)
                if cross200_mode == "greater":
                    cross_200_condition = _safe_compare(data.get("close"), ">", base)
                elif cross200_mode == "greaterEqual":
                    cross_200_condition = _safe_compare(data.get("close"), ">=", base)
                elif cross200_mode == "lower":
                    cross_200_condition = _safe_compare(data.get("close"), "<", base)
                elif cross200_mode == "lowerEqual":
                    cross_200_condition = _safe_compare(data.get("close"), "<=", base)
        elif cross200_mode == "between" and form.get("Cross200SMABool", "percentage") == "percentage":
            sf = data.get("cross200SMA_value")
            if sf is None:
                cross_200_condition = False
            else:
                base = sf * (1.0 + float(form.get("PercentageCross200SMA", 0)) / 100.0)
                cross_200_condition = (
                    _safe_compare(data.get("close"), ">=", base)
                )
        elif (
            cross200_mode not in _NON_SIMPLE_MODES
            and form.get("Cross200SMABool", "percentage") == "value"
        ):
            try:
                threshold = float(form.get("PercentageCross200SMA", 0))
            except Exception:
                threshold = 0
            sf = data.get("cross200SMA_value")
            if cross200_mode == "greater":
                cross_200_condition = _safe_compare(sf, ">", threshold)
            elif cross200_mode == "greaterEqual":
                cross_200_condition = _safe_compare(sf, ">=", threshold)
            elif cross200_mode == "lower":
                cross_200_condition = _safe_compare(sf, "<", threshold)
            elif cross200_mode == "lowerEqual":
                cross_200_condition = _safe_compare(sf, "<=", threshold)
        elif cross200_mode == "between" and form.get("Cross200SMABool", "percentage") == "value":
            try:
                threshold = float(form.get("PercentageCross200SMA", 0))
            except Exception:
                threshold = 0
            cross_200_condition = _safe_compare(data.get("cross200SMA_value"), ">=", threshold)

        if cross_200_condition is not None:
            condition = condition and cross_200_condition
            counting_ += 1
            variable_results["cross200SMA"] = bool(cross_200_condition)

        # -------------------------
        # BREAK HIGH
        # -------------------------
        break_high_condition = None

        if (form.get("ComparisonBreakHigh", "Not used") not in _NON_SIMPLE_MODES and
                form.get("BreakHighBool", "percentage") == "percentage"):
            v = data.get("breakHigh")
            if v is None:
                break_high_condition = False
            else:
                base = v * (1.0 + float(form.get("PercentageBreakHigh", 0)) / 100.0)
                if form["ComparisonBreakHigh"] == "greater":
                    break_high_condition = _safe_compare(data.get("close"), ">", base)
                elif form["ComparisonBreakHigh"] == "greaterEqual":
                    break_high_condition = _safe_compare(data.get("close"), ">=", base)
                elif form["ComparisonBreakHigh"] == "lower":
                    break_high_condition = _safe_compare(data.get("close"), "<", base)
                elif form["ComparisonBreakHigh"] == "lowerEqual":
                    break_high_condition = _safe_compare(data.get("close"), "<=", base)

        elif (form.get("ComparisonBreakHigh", "") == "between" and
              form.get("BreakHighBool", "percentage") == "percentage"):
            v = data.get("breakHigh")
            v1 = data.get("breakHigh1")
            if v is None or v1 is None:
                break_high_condition = False
            else:
                base = v * (1.0 + float(form.get("PercentageBreakHigh", 0)) / 100.0)
                base1 = v1 * (1.0 + float(form.get("PercentageBreakHigh1", 0)) / 100.0)
                break_high_condition = (
                        _safe_compare(data.get("close"), ">=", base)
                        and _safe_compare(data.get("close"), "<=", base1)
                )

        elif (form.get("ComparisonBreakHigh", "Not used") not in _NON_SIMPLE_MODES and
              form.get("BreakHighBool", "percentage") == "value"):
            if form["ComparisonBreakHigh"] == "greater":
                break_high_condition = _safe_compare(data.get("breakHigh"), ">", float(form.get("PercentageBreakHigh", 0)))
            elif form["ComparisonBreakHigh"] == "greaterEqual":
                break_high_condition = _safe_compare(data.get("breakHigh"), ">=", float(form.get("PercentageBreakHigh", 0)))
            elif form["ComparisonBreakHigh"] == "lower":
                break_high_condition = _safe_compare(data.get("breakHigh"), "<", float(form.get("PercentageBreakHigh", 0)))
            elif form["ComparisonBreakHigh"] == "lowerEqual":
                break_high_condition = _safe_compare(data.get("breakHigh"), "<=", float(form.get("PercentageBreakHigh", 0)))

        elif (form.get("ComparisonBreakHigh", "") == "between" and
              form.get("BreakHighBool", "percentage") == "value"):
            break_high_condition = (
                    _safe_compare(data.get("breakHigh"), ">=", float(form.get("PercentageBreakHigh", 0)))
                    and _safe_compare(data.get("breakHigh1"), "<=", float(form.get("PercentageBreakHigh1", 0)))
            )

        elif form.get("ComparisonBreakHigh") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageBreakHigh", 5))
            except Exception:
                threshold = 5.0
            break_high_condition = _within_percent_check(
                data.get("breakHigh"), data.get("close"),
                form.get("ComparisonBreakHigh"), threshold
            )

        if break_high_condition is not None:
            condition = condition and break_high_condition
            counting_ += 1
            variable_results["breakHigh"] = bool(break_high_condition)

        # -------------------------
        # PULLBACK RETRACEMENT
        # -------------------------
        pullback_condition = None

        if form.get("ComparisonPullbackPct", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonPullbackPct") == "greater":
                pullback_condition = _safe_compare(data.get("pullbackPct"), ">", float(form.get("PercentagePullbackPct", 0)))
            elif form.get("ComparisonPullbackPct") == "greaterEqual":
                pullback_condition = _safe_compare(data.get("pullbackPct"), ">=", float(form.get("PercentagePullbackPct", 0)))
            elif form.get("ComparisonPullbackPct") == "lower":
                pullback_condition = _safe_compare(data.get("pullbackPct"), "<", float(form.get("PercentagePullbackPct", 0)))
            elif form.get("ComparisonPullbackPct") == "lowerEqual":
                pullback_condition = _safe_compare(data.get("pullbackPct"), "<=", float(form.get("PercentagePullbackPct", 0)))

        elif form.get("ComparisonPullbackPct") == "between":
            pullback_condition = (
                    _safe_compare(data.get("pullbackPct"), ">=", float(form.get("PercentagePullbackPct", 0)))
                    and _safe_compare(data.get("pullbackPct1"), "<=", float(form.get("PercentagePullbackPct1", 0)))
            )

        elif form.get("ComparisonPullbackPct") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentagePullbackPct", 5))
            except Exception:
                threshold = 5.0
            pullback_condition = _within_percent_check(
                data.get("pullbackPct"), data.get("close"),
                form.get("ComparisonPullbackPct"), threshold
            )

        if pullback_condition is not None:
            condition = condition and pullback_condition
            counting_ += 1
            variable_results["pullbackPct"] = bool(pullback_condition)

        # -------------------------
        # 2ND PULLBACK RETRACEMENT
        # -------------------------
        pullback2_condition = None

        if form.get("ComparisonPullbackPct2", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonPullbackPct2") == "greater":
                pullback2_condition = _safe_compare(data.get("pullbackPct2"), ">", float(form.get("PercentagePullbackPct2", 0)))
            elif form.get("ComparisonPullbackPct2") == "greaterEqual":
                pullback2_condition = _safe_compare(data.get("pullbackPct2"), ">=", float(form.get("PercentagePullbackPct2", 0)))
            elif form.get("ComparisonPullbackPct2") == "lower":
                pullback2_condition = _safe_compare(data.get("pullbackPct2"), "<", float(form.get("PercentagePullbackPct2", 0)))
            elif form.get("ComparisonPullbackPct2") == "lowerEqual":
                pullback2_condition = _safe_compare(data.get("pullbackPct2"), "<=", float(form.get("PercentagePullbackPct2", 0)))

        elif form.get("ComparisonPullbackPct2") == "between":
            pullback2_condition = (
                    _safe_compare(data.get("pullbackPct2"), ">=", float(form.get("PercentagePullbackPct2", 0)))
                    and _safe_compare(data.get("pullbackPct2_1"), "<=", float(form.get("PercentagePullbackPct2_1", 0)))
            )

        elif form.get("ComparisonPullbackPct2") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentagePullbackPct2", 5))
            except Exception:
                threshold = 5.0
            pullback2_condition = _within_percent_check(
                data.get("pullbackPct2"), data.get("close"),
                form.get("ComparisonPullbackPct2"), threshold
            )

        if pullback2_condition is not None:
            condition = condition and pullback2_condition
            counting_ += 1
            variable_results["pullbackPct2"] = bool(pullback2_condition)

        # -------------------------
        # FIBONACCI PULLBACK
        # -------------------------
        fib_pb_condition = None

        if form.get("ComparisonFibPullback", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonFibPullback") == "greater":
                fib_pb_condition = _safe_compare(data.get("fibPullback"), ">", float(form.get("PercentageFibPullback", 0)))
            elif form.get("ComparisonFibPullback") == "greaterEqual":
                fib_pb_condition = _safe_compare(data.get("fibPullback"), ">=", float(form.get("PercentageFibPullback", 0)))
            elif form.get("ComparisonFibPullback") == "lower":
                fib_pb_condition = _safe_compare(data.get("fibPullback"), "<", float(form.get("PercentageFibPullback", 0)))
            elif form.get("ComparisonFibPullback") == "lowerEqual":
                fib_pb_condition = _safe_compare(data.get("fibPullback"), "<=", float(form.get("PercentageFibPullback", 0)))

        elif form.get("ComparisonFibPullback") == "between":
            fib_pb_condition = (
                    _safe_compare(data.get("fibPullback"), ">=", float(form.get("PercentageFibPullback", 0)))
                    and _safe_compare(data.get("fibPullback1"), "<=", float(form.get("PercentageFibPullback1", 0)))
            )

        elif form.get("ComparisonFibPullback") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageFibPullback", 5))
            except Exception:
                threshold = 5.0
            fib_pb_condition = _within_percent_check(
                data.get("fibPullback"), data.get("close"),
                form.get("ComparisonFibPullback"), threshold
            )

        if fib_pb_condition is not None:
            condition = condition and fib_pb_condition
            counting_ += 1
            variable_results["fibPullback"] = bool(fib_pb_condition)

        # -------------------------
        # GAP PULLBACK
        # -------------------------
        gap_pb_condition = None

        if form.get("ComparisonGapPullback", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonGapPullback") == "greater":
                gap_pb_condition = _safe_compare(data.get("gapPullback"), ">", float(form.get("PercentageGapPullback", 0)))
            elif form.get("ComparisonGapPullback") == "greaterEqual":
                gap_pb_condition = _safe_compare(data.get("gapPullback"), ">=", float(form.get("PercentageGapPullback", 0)))
            elif form.get("ComparisonGapPullback") == "lower":
                gap_pb_condition = _safe_compare(data.get("gapPullback"), "<", float(form.get("PercentageGapPullback", 0)))
            elif form.get("ComparisonGapPullback") == "lowerEqual":
                gap_pb_condition = _safe_compare(data.get("gapPullback"), "<=", float(form.get("PercentageGapPullback", 0)))

        elif form.get("ComparisonGapPullback") == "between":
            gap_pb_condition = (
                    _safe_compare(data.get("gapPullback"), ">=", float(form.get("PercentageGapPullback", 0)))
                    and _safe_compare(data.get("gapPullback1"), "<=", float(form.get("PercentageGapPullback1", 0)))
            )

        elif form.get("ComparisonGapPullback") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageGapPullback", 5))
            except Exception:
                threshold = 5.0
            gap_pb_condition = _within_percent_check(
                data.get("gapPullback"), data.get("close"),
                form.get("ComparisonGapPullback"), threshold
            )

        if gap_pb_condition is not None:
            condition = condition and gap_pb_condition
            counting_ += 1
            variable_results["gapPullback"] = bool(gap_pb_condition)

        # -------------------------
        # UP GAP (gap up from previous close, 9:30 AM - 4 PM EST)
        # -------------------------
        up_gap_condition = None

        if form.get("ComparisonUpGap", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonUpGap") == "greater":
                up_gap_condition = _safe_compare(data.get("upGap"), ">", float(form.get("PercentageUpGap", 0)))
            elif form.get("ComparisonUpGap") == "greaterEqual":
                up_gap_condition = _safe_compare(data.get("upGap"), ">=", float(form.get("PercentageUpGap", 0)))
            elif form.get("ComparisonUpGap") == "lower":
                up_gap_condition = _safe_compare(data.get("upGap"), "<", float(form.get("PercentageUpGap", 0)))
            elif form.get("ComparisonUpGap") == "lowerEqual":
                up_gap_condition = _safe_compare(data.get("upGap"), "<=", float(form.get("PercentageUpGap", 0)))

        elif form.get("ComparisonUpGap") == "between":
            up_gap_condition = (
                    _safe_compare(data.get("upGap"), ">=", float(form.get("PercentageUpGap", 0)))
                    and _safe_compare(data.get("upGap1"), "<=", float(form.get("PercentageUpGap1", 0)))
            )

        elif form.get("ComparisonUpGap") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageUpGap", 5))
            except Exception:
                threshold = 5.0
            up_gap_condition = _within_percent_check(
                data.get("upGap"), data.get("close"),
                form.get("ComparisonUpGap"), threshold
            )

        if up_gap_condition is not None:
            condition = condition and up_gap_condition
            counting_ += 1
            variable_results["upGap"] = bool(up_gap_condition)

        # -------------------------
        # DOWN GAP (gap down from previous close, 9:30 AM - 4 PM EST)
        # -------------------------
        down_gap_condition = None

        if form.get("ComparisonDownGap", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonDownGap") == "greater":
                down_gap_condition = _safe_compare(data.get("downGap"), ">", float(form.get("PercentageDownGap", 0)))
            elif form.get("ComparisonDownGap") == "greaterEqual":
                down_gap_condition = _safe_compare(data.get("downGap"), ">=", float(form.get("PercentageDownGap", 0)))
            elif form.get("ComparisonDownGap") == "lower":
                down_gap_condition = _safe_compare(data.get("downGap"), "<", float(form.get("PercentageDownGap", 0)))
            elif form.get("ComparisonDownGap") == "lowerEqual":
                down_gap_condition = _safe_compare(data.get("downGap"), "<=", float(form.get("PercentageDownGap", 0)))

        elif form.get("ComparisonDownGap") == "between":
            down_gap_condition = (
                    _safe_compare(data.get("downGap"), ">=", float(form.get("PercentageDownGap", 0)))
                    and _safe_compare(data.get("downGap1"), "<=", float(form.get("PercentageDownGap1", 0)))
            )

        elif form.get("ComparisonDownGap") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageDownGap", 5))
            except Exception:
                threshold = 5.0
            down_gap_condition = _within_percent_check(
                data.get("downGap"), data.get("close"),
                form.get("ComparisonDownGap"), threshold
            )

        if down_gap_condition is not None:
            condition = condition and down_gap_condition
            counting_ += 1
            variable_results["downGap"] = bool(down_gap_condition)

        # -------------------------
        # FIBONACCI GAP
        # -------------------------
        fib_gap_condition = None

        if form.get("ComparisonFibGap", "Not used") not in _NON_SIMPLE_MODES:
            if form.get("ComparisonFibGap") == "greater":
                fib_gap_condition = _safe_compare(data.get("fibGap"), ">", float(form.get("PercentageFibGap", 0)))
            elif form.get("ComparisonFibGap") == "greaterEqual":
                fib_gap_condition = _safe_compare(data.get("fibGap"), ">=", float(form.get("PercentageFibGap", 0)))
            elif form.get("ComparisonFibGap") == "lower":
                fib_gap_condition = _safe_compare(data.get("fibGap"), "<", float(form.get("PercentageFibGap", 0)))
            elif form.get("ComparisonFibGap") == "lowerEqual":
                fib_gap_condition = _safe_compare(data.get("fibGap"), "<=", float(form.get("PercentageFibGap", 0)))

        elif form.get("ComparisonFibGap") == "between":
            fib_gap_condition = (
                    _safe_compare(data.get("fibGap"), ">=", float(form.get("PercentageFibGap", 0)))
                    and _safe_compare(data.get("fibGap1"), "<=", float(form.get("PercentageFibGap1", 0)))
            )

        elif form.get("ComparisonFibGap") in ("withinPercentAbove", "withinPercentBelow", "withinPercentEither"):
            try:
                threshold = float(form.get("PercentageFibGap", 5))
            except Exception:
                threshold = 5.0
            fib_gap_condition = _within_percent_check(
                data.get("fibGap"), data.get("close"),
                form.get("ComparisonFibGap"), threshold
            )

        if fib_gap_condition is not None:
            condition = condition and fib_gap_condition
            counting_ += 1
            variable_results["fibGap"] = bool(fib_gap_condition)

        # -------------------------
        # NEWS (within X minutes/hours/days)
        # -------------------------
        news_condition = None

        if form.get("ComparisonNews", "Not used") != "Not used":
            # Support both the new NewsWithinValue+NewsTimeUnit fields
            # and the legacy NewsWithinHours field for backward compat.
            news_within_minutes = 0
            try:
                time_unit = form.get("NewsTimeUnit", "minutes").lower()
                within_value = int(form.get("NewsWithinValue", 0))
                if within_value > 0:
                    if time_unit == "hours":
                        news_within_minutes = within_value * 60
                    elif time_unit == "days":
                        news_within_minutes = within_value * 1440
                    else:  # minutes
                        news_within_minutes = within_value
                else:
                    # fallback to legacy field
                    legacy_hours = int(form.get("NewsWithinHours", 0))
                    news_within_minutes = legacy_hours * 60
            except Exception:
                pass

            if news_within_minutes > 0:
                # Check if any headline falls within the time window
                from datetime import datetime, timezone, timedelta
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=news_within_minutes)
                headlines = data.get("newsHeadlines", [])
                has_recent = False
                for h in headlines:
                    parsed = h.get("parsedTime", "")
                    if parsed:
                        try:
                            dt = datetime.fromisoformat(parsed)
                            if dt >= cutoff:
                                has_recent = True
                                break
                        except Exception:
                            pass
                news_condition = has_recent
            else:
                # No time filter — just check if any headlines exist
                news_condition = len(data.get("newsHeadlines", [])) > 0

        if news_condition is not None:
            condition = condition and news_condition
            counting_ += 1
            variable_results["news"] = bool(news_condition)

        # -------------------------
        # NEWS KEYWORD SCAN (filter headlines by keywords independently, regardless of signal)
        # -------------------------
        news_keyword_match = None
        matched_keyword_headlines = []

        # Apply keyword filtering REGARDLESS of whether News signal is enabled
        keywords_raw = form.get("NewsKeywords", "").strip()
        logger.debug(f"[KEYWORDS DEBUG] form keys: {list(form.keys()) if isinstance(form, dict) else 'not dict'}")
        logger.debug(f"[KEYWORDS DEBUG] NewsKeywords value: '{keywords_raw}'")
        logger.debug(f"[KEYWORDS DEBUG] Available headlines: {len(data.get('newsHeadlines', []) or [])} headlines")
        if keywords_raw:
            keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
            logger.debug(f"[KEYWORDS DEBUG] Parsed keywords: {keywords}")
            if keywords:
                headlines = data.get("newsHeadlines", [])
                # Handle case where headlines might be None instead of list
                if headlines is None:
                    headlines = []
                    logger.debug("[KEYWORDS DEBUG] newsHeadlines was None, using empty list")
                    
                # Use whole-word matching to avoid unintended partial matches
                import re as _re_kw
                filtered_headlines = []
                # compile patterns once for performance
                patterns = [_re_kw.compile(r"\b" + _re_kw.escape(k) + r"\b", _re_kw.IGNORECASE) for k in keywords]
                for h in headlines:
                    headline_text = (h.get("headline") or "")
                    for pat in patterns:
                        if pat.search(headline_text):
                            filtered_headlines.append(h)
                            matched_keyword_headlines.append(h.get("headline", ""))
                            break

                # Replace newsHeadlines with only those containing keywords
                data["newsHeadlines"] = filtered_headlines
                news_keyword_match = len(filtered_headlines) > 0
                logger.debug(f"[KEYWORDS DEBUG] Matched {len(filtered_headlines)} out of {len(headlines)} headlines")
        else:
            logger.debug("[KEYWORDS DEBUG] No keywords entered")

        if news_keyword_match is not None:
            variable_results["newsKeyword"] = bool(news_keyword_match)

        data["newsKeywordMatch"] = bool(news_keyword_match) if news_keyword_match else False
        data["matchedKeywordHeadlines"] = matched_keyword_headlines
        logger.debug(f"[KEYWORDS DEBUG] Final result: news_keyword_match={news_keyword_match}")

        # -------------------------
        # FINAL
        # -------------------------
        if counting_ == 0:
            condition = False

        data["signal"] = "yes" if condition else "no"
        data["variableResults"] = variable_results
        data["passCount"] = sum(1 for v in variable_results.values() if v)
        data["totalCount"] = counting_

        # -------------------------
        # FIBONACCI PULLBACK CALCULATIONS
        # -------------------------
        # Calculate Fibonacci pullback levels if we have prevClose and highOfDay
        try:
            prev_close = data.get("prevClose")
            high_of_day = data.get("highOfDay")
            
            if prev_close is not None and high_of_day is not None:
                prev_close = float(prev_close)
                high_of_day = float(high_of_day)
                
                if high_of_day > prev_close:  # Only calculate if there's an uptrend
                    from indicators import FibonacciCalculator
                    
                    fib_calc = FibonacciCalculator(prev_close, high_of_day)
                    fib_levels = fib_calc.calculate_levels()
                    
                    # Store Fibonacci data in the result
                    data["fibonacciLevels"] = fib_levels
                    data["fibonacciMove"] = round(high_of_day - prev_close, 4)
                else:
                    # No uptrend to calculate pullback
                    data["fibonacciLevels"] = {}
                    data["fibonacciMove"] = 0.0
        except Exception as e:
            logger.warning(f"Fibonacci calculation failed: {e}")
            data["fibonacciLevels"] = {}
            data["fibonacciMove"] = 0.0
        
        # -------- Gap Detection --------
        try:
            if form.get("GapDetectionEnabled", False):
                current_price = data.get("close")
                try:
                    lookback_days = int(form.get("GapLookbackDays", 60))
                except Exception:
                    lookback_days = 60
                try:
                    min_gap_percent = float(form.get("GapMinimumPercent", 2.0))
                except Exception:
                    min_gap_percent = 2.0
                try:
                    proximity_percent = float(form.get("GapProximityPercent", 50.0))
                except Exception:
                    proximity_percent = 50.0
                
                # Get historical data for gap analysis
                symbol = data.get("symbol")
                historical_data = []
                
                # Try to get historical data from internal data structure
                if symbol in self.HistoricalDt:
                    hist_bars = self.HistoricalDt[symbol]
                    for bar in hist_bars:
                        if hasattr(bar, 'open') and hasattr(bar, 'close'):
                            historical_data.append({
                                'date': str(bar.date) if hasattr(bar, 'date') else '',
                                'open': float(bar.open),
                                'close': float(bar.close),
                                'high': float(bar.high) if hasattr(bar, 'high') else float(bar.close),
                                'low': float(bar.low) if hasattr(bar, 'low') else float(bar.close),
                            })
                
                if historical_data and current_price:
                    current_price = float(current_price)
                    
                    # Analyze gaps
                    gap_analyzer = GapAnalyzer(lookback_days=lookback_days, min_gap_percent=min_gap_percent)
                    all_gaps = gap_analyzer.detect_gaps(historical_data)
                    
                    # Identify which gaps are still open
                    gaps_status = gap_analyzer.identify_open_gaps(all_gaps['all_gaps'], current_price)
                    
                    # Find gaps being filled
                    approaching = gap_analyzer.find_approaching_gaps(
                        gaps_status['open_gaps'],
                        current_price,
                        proximity_percent=proximity_percent
                    )
                    
                    # Store gap data in results
                    data["gaps"] = {
                        "all_detected": [g for g in all_gaps['all_gaps']],
                        "open_gaps": gaps_status['open_gaps'],
                        "upside_gaps": gaps_status['upside_gaps'],
                        "downside_gaps": gaps_status['downside_gaps'],
                        "approaching_gaps": approaching['approaching'],
                        "closest_gap": approaching['closest_gap'],
                        "approaching_downside": approaching['approaching_downside'],
                        "approaching_upside": approaching['approaching_upside'],
                    }
                else:
                    data["gaps"] = {
                        "all_detected": [],
                        "open_gaps": [],
                        "upside_gaps": [],
                        "downside_gaps": [],
                        "approaching_gaps": [],
                        "closest_gap": None,
                        "approaching_downside": [],
                        "approaching_upside": [],
                    }
            else:
                data["gaps"] = {
                    "all_detected": [],
                    "open_gaps": [],
                    "upside_gaps": [],
                    "downside_gaps": [],
                    "approaching_gaps": [],
                    "closest_gap": None,
                    "approaching_downside": [],
                    "approaching_upside": [],
                }
        except Exception as e:
            logger.warning(f"Gap detection failed: {e}")
            data["gaps"] = {
                "all_detected": [],
                "open_gaps": [],
                "upside_gaps": [],
                "downside_gaps": [],
                "approaching_gaps": [],
                "closest_gap": None,
                "approaching_downside": [],
                "approaching_upside": [],
            }

        # -------------------------
        # % CHANGE MONITORING
        # -------------------------
        pct_change_condition = None
        if form.get("EnablePctChangeMonitor"):
            try:
                lookback_minutes = int(form.get("PctChangeLookbackMinutes", 5))
                threshold_pct = float(form.get("PctChangeThreshold", 3.0))
                
                # Convert minutes to bars (assuming 1-minute bars)
                lookback_bars = max(1, lookback_minutes)
                
                # Get historical data from HistoricalDt
                symbol = data.get("symbol")
                if symbol and symbol in self.HistoricalDt:
                    hist_data = self.HistoricalDt[symbol]
                    if isinstance(hist_data, pd.DataFrame) and len(hist_data) >= lookback_bars:
                        pct_change = calculate_pct_change(hist_data, lookback_bars)
                        pct_change_condition = abs(pct_change) >= threshold_pct
                        data["pctChange"] = pct_change
                        data["pctChangeThreshold"] = threshold_pct
                    else:
                        pct_change_condition = False
                        data["pctChange"] = 0.0
                else:
                    pct_change_condition = False
                    data["pctChange"] = 0.0
            except Exception as e:
                logger.warning(f"% Change monitoring failed: {e}")
                pct_change_condition = False
        
        if pct_change_condition is not None:
            variable_results["pctChange"] = bool(pct_change_condition)

        # -------------------------
        # RVOL MONITORING
        # -------------------------
        rvol_monitor_condition = None
        if form.get("EnableRVOLMonitor"):
            try:
                lookback_days = int(form.get("RVOLLookbackDays", 5))
                rvol_threshold = float(form.get("RVOLThreshold", 1.5))
                
                # Get historical data
                symbol = data.get("symbol")
                if symbol and symbol in self.HistoricalDt:
                    hist_data = self.HistoricalDt[symbol]
                    if isinstance(hist_data, pd.DataFrame) and len(hist_data) >= 1:
                        rvol_value = calculate_rvol(hist_data, lookback_days)
                        rvol_monitor_condition = rvol_value >= rvol_threshold
                        data["rvol"] = rvol_value
                        data["rvolThreshold"] = rvol_threshold
                    else:
                        rvol_monitor_condition = False
                        data["rvol"] = 0.0
                else:
                    rvol_monitor_condition = False
                    data["rvol"] = 0.0
            except Exception as e:
                logger.warning(f"RVOL monitoring failed: {e}")
                rvol_monitor_condition = False
        
        if rvol_monitor_condition is not None:
            variable_results["rvol"] = bool(rvol_monitor_condition)

        # -------------------------
        # KEY LEVEL DETECTION
        # -------------------------
        key_level_condition = None
        key_level_details = {}
        if form.get("EnableKeyLevelDetection"):
            try:
                proximity_pct = float(form.get("KeyLevelProximityPercent", 1.0))
                level_type = form.get("KeyLevelType", "vwap")
                
                is_near, level_name, level_value = detect_nearby_key_levels(data, proximity_pct, level_type)
                key_level_condition = is_near
                data["nearKeyLevel"] = key_level_condition
                data["keyLevelProximity"] = proximity_pct
                data["keyLevelType"] = level_type
                key_level_details = {
                    "name": level_name,
                    "value": level_value,
                    "type": level_type
                }
            except Exception as e:
                logger.warning(f"Key level detection failed: {e}")
                key_level_condition = False
        
        if key_level_condition is not None:
            variable_results["keyLevel"] = bool(key_level_condition)
            if key_level_condition:
                variable_results["keyLevelDetails"] = key_level_details

        # -------------------------
        # 200 SMA BULLISH CROSSOVER DETECTION
        # -------------------------
        sma_200_crossover_condition = None
        if form.get("Enable200SMABullishCrossover"):
            try:
                # Pass form dict so the function can check EnableExtendedHours flag
                sma_200_crossover_condition = detect_200sma_bullish_crossover(data, form=form)
                data["sma200BullishCrossover"] = sma_200_crossover_condition
                
                # Add description for the crossover
                if sma_200_crossover_condition:
                    current_price = data.get("close")
                    sma_200_value = data.get("smaSlow")  # Use smaSlow (the actual 200 SMA)
                    if sma_200_value:
                        description = f"200 SMA Bullish Crossover: Price ${current_price:.2f} crossed above 200 SMA ${sma_200_value:.2f}"
                    else:
                        description = "200 SMA Bullish Crossover Detected"
                    data["sma200BullishCrossoverDescription"] = description
                else:
                    data["sma200BullishCrossoverDescription"] = None
                    
            except Exception as e:
                logger.warning(f"200 SMA bullish crossover detection failed: {e}")
                sma_200_crossover_condition = False
                data["sma200BullishCrossoverDescription"] = None
        
        if sma_200_crossover_condition is not None:
            variable_results["sma200Crossover"] = bool(sma_200_crossover_condition)

        # -------------------------
        # ON BALANCE VOLUME (OBV) ANALYSIS
        # -------------------------
        obv_analysis = None
        if form.get("EnableOBVAnalysis"):
            try:
                # Get historical data for OBV calculation
                symbol = data.get("symbol")
                hist_data = None
                
                if symbol and symbol in self.HistoricalDt:
                    hist_df = self.HistoricalDt[symbol]
                    if isinstance(hist_df, pd.DataFrame) and len(hist_df) >= 20:
                        hist_data = hist_df
                
                if hist_data is not None:
                    trend_period = int(form.get("OBVTrendPeriod", 20))
                    ma_period = int(form.get("OBVMovingAveragePeriod", 10))
                    strength_threshold = float(form.get("OBVStrengthThreshold", 15.0))
                    
                    obv_analysis = detect_obv_strength(
                        data, 
                        hist_data,
                        trend_period=trend_period,
                        ma_period=ma_period,
                        strength_threshold=strength_threshold
                    )
                    
                    # Store OBV analysis results
                    data["obvAnalysis"] = obv_analysis
                    data["obvTrend"] = obv_analysis["trend"]
                    data["obvStrength"] = obv_analysis["strength"]
                    data["obvMomentum"] = obv_analysis["momentum_pct"]
                    data["obvAboveMA"] = obv_analysis["above_ma"]
                    data["obvSignal"] = obv_analysis["signal"]
                else:
                    # Not enough data for OBV analysis
                    obv_analysis = None
            except Exception as e:
                logger.warning(f"OBV analysis failed: {e}")
                obv_analysis = None
        
        # Store OBV conditions in variable results
        if obv_analysis is not None:
            # Variable 1: OBV Trend & Strength
            is_bullish_obv = obv_analysis["signal"] in ["strong_bullish", "bullish"]
            variable_results["obvTrendStrength"] = is_bullish_obv
            
            # Variable 2: OBV Above MA (strong relative volume)
            variable_results["obvAboveMovingAverage"] = obv_analysis["above_ma"]

        # -------------------------
        # MULTI-OBV ANALYSIS (Fast, Medium, Slow comparison)
        # -------------------------
        multi_obv_analysis = None
        obv_tts_alert = None
        if form.get("EnableMultiOBVAnalysis"):
            try:
                # Get current OBV values from indicators
                fast_obv = indicators.get("fast_obv")
                medium_obv = indicators.get("medium_obv")
                slow_obv = indicators.get("slow_obv")
                
                # Get previous OBV values from historical data
                prev_fast = None
                prev_medium = None
                prev_slow = None
                
                symbol = data.get("symbol")
                if symbol and symbol in self.HistoricalDt:
                    hist_df = self.HistoricalDt[symbol]
                    if isinstance(hist_df, pd.DataFrame) and len(hist_df) >= 2:
                        try:
                            # Get previous bar's OBV values
                            prev_close = hist_df.iloc[-2]['close'] if len(hist_df) >= 2 else hist_df.iloc[-1]['close']
                            prev_volume = hist_df.iloc[-2]['volume'] if len(hist_df) >= 2 else hist_df.iloc[-1]['volume']
                            
                            # Calculate previous OBV values using the indicator classes
                            if len(hist_df) >= 6:  # Fast OBV needs 5-bar window
                                fast_obv_ind = FastOBVIndicator(close=hist_df['close'], volume=hist_df['volume'], window=5)
                                prev_fast = last_value(fast_obv_ind.fast_obv().iloc[:-1])
                            
                            if len(hist_df) >= 11:  # Medium OBV needs 10-bar window
                                medium_obv_ind = MediumOBVIndicator(close=hist_df['close'], volume=hist_df['volume'], window=10)
                                prev_medium = last_value(medium_obv_ind.medium_obv().iloc[:-1])
                            
                            if len(hist_df) >= 21:  # Slow OBV needs 20-bar window
                                slow_obv_ind = SlowOBVIndicator(close=hist_df['close'], volume=hist_df['volume'], window=20)
                                prev_slow = last_value(slow_obv_ind.slow_obv().iloc[:-1])
                        except Exception as e:
                            logger.debug(f"Could not calculate previous OBV values: {e}")
                            prev_fast = fast_obv
                            prev_medium = medium_obv
                            prev_slow = slow_obv
                
                # Perform multi-OBV analysis
                change_threshold = float(form.get("MultiOBVChangeThreshold", 5.0))
                multi_obv_analysis = analyze_multi_obv(
                    fast_obv=fast_obv,
                    medium_obv=medium_obv,
                    slow_obv=slow_obv,
                    prev_fast=prev_fast if prev_fast is not None else fast_obv,
                    prev_medium=prev_medium if prev_medium is not None else medium_obv,
                    prev_slow=prev_slow if prev_slow is not None else slow_obv,
                    change_threshold=change_threshold
                )
                
                # Store Multi-OBV analysis results
                data["multiOBVAnalysis"] = multi_obv_analysis
                data["multiOBVSignal"] = multi_obv_analysis["signal"]
                data["multiOBVAlignment"] = multi_obv_analysis["alignment"]
                data["multiOBVStrength"] = multi_obv_analysis["strength"]
                data["multiOBVDivergence"] = multi_obv_analysis["divergence"]
                data["multiOBVEquation"] = multi_obv_analysis["equation"]
                
                # Store individual OBV values and changes for display
                data["fastOBVValue"] = fast_obv
                data["mediumOBVValue"] = medium_obv
                data["slowOBVValue"] = slow_obv
                data["fastMediumPctChange"] = multi_obv_analysis["fast_medium_pct_change"]
                data["mediumSlowPctChange"] = multi_obv_analysis["medium_slow_pct_change"]
                data["fastSlowPctChange"] = multi_obv_analysis["fast_slow_pct_change"]
                
                # Add to variable results for conditional filtering
                is_strong_bullish = multi_obv_analysis["signal"] in ["strong_bullish", "bullish"]
                variable_results["multiOBVBullish"] = is_strong_bullish
                variable_results["multiOBVAlignment"] = multi_obv_analysis["alignment"] != "misaligned"
                
                # Text-to-Speech alert if enabled
                if form.get("EnableMultiOBVTTS"):
                    symbol = data.get("symbol", "unknown")
                    # Create TTS alert message
                    if multi_obv_analysis["signal"] in ["strong_bullish", "strong_bearish"]:
                        obv_tts_alert = {
                            "symbol": symbol,
                            "signal": multi_obv_analysis["signal"],
                            "description": multi_obv_analysis["description"],
                            "equation": multi_obv_analysis["equation"]
                        }
                        data["obvTTSAlert"] = obv_tts_alert
                        
                        # Log for debugging
                        logger.info(f"Multi-OBV TTS Alert for {symbol}: {multi_obv_analysis['signal']}")
                
            except Exception as e:
                logger.warning(f"Multi-OBV analysis failed: {e}")
                logger.debug(f"Multi-OBV error traceback: {traceback.format_exc()}")
                multi_obv_analysis = None

        if self.config.scale_volume_metrics:
            # create copy for Flask so internal logic stays untouched
            flask_data = data.copy()

            # scale volume metrics x100 for UI
            if flask_data.get("volume") is not None:
                flask_data["volume"] *= 100.0

            # if flask_data.get("averageVolume") is not None:
            #     flask_data["averageVolume"] *= 100.0
            #
            # if flask_data.get("averageVolume1") is not None:
            #     flask_data["averageVolume1"] *= 100.0
            #
            # if flask_data.get("relativeVolume") is not None:
            #     flask_data["relativeVolume"] *= 100.0
            #
            # if flask_data.get("relativeVolume1") is not None:
            #     flask_data["relativeVolume1"] *= 100.0

            self.sendToFlaskIB[data["cusip"]] = flask_data
        else:
            self.sendToFlaskIB[data["cusip"]] = data

        return data

    def fetchNews(self, con_id, form, news_req_id):
        """
        Fetch historical news headlines for a contract from IBKR.

        Uses reqHistoricalNews which requires conId.
        Returns list of headline dicts, filtered by exclude list and deduped.
        """
        from datetime import datetime, timezone, timedelta

        max_headlines = 20
        try:
            max_headlines = int(form.get("NewsMaxHeadlines", 20))
        except Exception:
            pass
        if max_headlines < 1:
            max_headlines = 20

        # Parse excluded publishers from comma-separated string
        exclude_raw = form.get("NewsExcludePublishers", "")
        excluded_publishers = set()
        if exclude_raw:
            excluded_publishers = {
                p.strip().lower() for p in str(exclude_raw).split(",") if p.strip()
            }

        # Prepare the news request with thread-safe initialization
        with self._news_lock:
            self._news_data[news_req_id] = []
            self._news_done[news_req_id] = False

        # IBKR reqHistoricalNews:
        #   reqId, conId, providerCodes, startDateTime, endDateTime, totalResults, historicalNewsOptions
        # providerCodes: "BZ+FLY+DJ+MT+GS" etc. separated by "+"
        # Date format: "YYYYMMDD-HH:MM:SS" or "" for open-ended
        #
        # Wait briefly for the newsProviders callback if it hasn't fired yet
        # But don't wait too long to avoid blocking the entire screening
        if self._subscribed_news_providers is None:
            logger.debug("Waiting for news provider discovery...")
            _pw = 0.0
            while self._subscribed_news_providers is None and _pw < 2.0:
                time.sleep(0.05)
                _pw += 0.05
            if self._subscribed_news_providers is None:
                logger.warning("News provider discovery did not complete, will use fallback providers")

        # -------------------------
        # Determine which news providers to request
        # -------------------------
        # Priority:
        # 1. User-specified providers in NewsProviders field
        # 2. Discovered subscribed providers from IBKR
        # 3. Fallback list with diverse providers
        
        user_providers = form.get("NewsProviders", "").strip()
        if user_providers:
            # User specified preferred providers
            provider_list = [p.strip().upper() for p in user_providers.split(",") if p.strip()]
            provider_codes = "+".join(provider_list)
            logger.info("Using user-specified news providers: %s", provider_codes)
        elif self._subscribed_news_providers:
            # Use discovered subscribed providers
            provider_codes = self._subscribed_news_providers
            logger.info("Using discovered news providers: %s", provider_codes)
        else:
            # Fall back to comprehensive provider list
            # Ordered to prioritize non-Dow Jones sources first to improve diversity:
            # BZ (Benzinga), FLY (Fly), MT (Morningstar), GS, CZ, BSW, BRFG, then DJNL + DJ-N (Dow Jones)
            # This ensures better provider diversity and avoids DJ-N dominance
            provider_codes = "BZ+FLY+MT+GS+CZ+BSW+BRFG+DJNL+DJ-N+DJ-RT"
            logger.info("Using fallback news providers (diversity-first): %s", provider_codes)

        end_dt = ""  # now
        start_dt = ""  # open-ended (let maxResults limit it)

        # Over-request articles to improve availability and provider diversity
        # Request significantly more headlines than needed to ensure we can filter by diversity
        # while still returning the requested max_headlines to the user
        total_to_request = max(150, max_headlines * 8)  # request significantly more for diversity and availability

        logger.info(
            "reqHistoricalNews reqId=%s conId=%s providers=%s totalResults=%s",
            news_req_id, con_id, provider_codes, total_to_request,
        )

        try:
            logger.debug("Requesting historical news for conId %s with providers: %s", con_id, provider_codes)
            self.reqHistoricalNews(
                news_req_id,
                con_id,
                provider_codes,
                start_dt,
                end_dt,
                total_to_request,
                [],
            )
            logger.debug("reqHistoricalNews submitted successfully for reqId=%s", news_req_id)
        except Exception as e:
            logger.error("reqHistoricalNews failed for conId %s: %s", con_id, e)
            with self._news_lock:
                self._news_data.pop(news_req_id, None)
                self._news_done.pop(news_req_id, None)
            return []

        # Wait for news (bounded) - increased timeout to 15 seconds for slower connections
        waited = 0.0
        timeout = 15.0  # seconds (increased to handle slower IBKR API responses)
        poll_interval = 0.2  # increased poll interval to reduce contention
        while True:
            with self._news_lock:
                if self._news_done.get(news_req_id, False):
                    logger.debug("fetchNews reqId=%s: historicalNewsEnd received", news_req_id)
                    break
            
            time.sleep(poll_interval)
            waited += poll_interval
            if waited >= timeout:
                with self._news_lock:
                    headline_count = len(self._news_data.get(news_req_id, []))
                logger.warning("fetchNews timeout for conId %s after %.1fs, received %d headlines so far. "
                              "This may indicate slow API response or no news available.",
                              con_id, waited, headline_count)
                break

        # Retrieve headlines with lock protection
        with self._news_lock:
            raw_headlines = self._news_data.get(news_req_id, [])[:]  # make a copy
            is_done = self._news_done.get(news_req_id, False)
        
        logger.info(
            "fetchNews reqId=%s conId=%s returned %d raw headlines (done=%s, waited=%.1fs)",
            news_req_id, con_id, len(raw_headlines), is_done, waited,
        )

        # Filter excluded publishers
        filtered = []
        for h in raw_headlines:
            provider = (h.get("provider") or "").strip().lower()
            if provider in excluded_publishers:
                continue
            filtered.append(h)

        # Deduplicate by headline text (keep first occurrence)
        seen_headlines = set()
        deduped = []
        for h in filtered:
            hl_text = (h.get("headline") or "").strip()
            if hl_text in seen_headlines:
                continue
            seen_headlines.add(hl_text)
            deduped.append(h)

        # -------------------------
        # Provider diversity filter: maintain variety while respecting max_headlines
        # -------------------------
        # Only apply diversity filtering if we have significantly more headlines than requested
        # This prevents accidentally truncating results when user wants many headlines
        if len(deduped) > max_headlines * 1.5:  # Only if we have excess
            dj_providers = {"dj-n", "dj-rt", "djnl"}  # Dow Jones variants
            dj_items = []
            non_dj_items = []
            
            for h in deduped:
                provider = (h.get("provider") or "").strip().lower()
                if provider in dj_providers:
                    dj_items.append(h)
                else:
                    non_dj_items.append(h)
            
            # Strategy: Mix DJ and non-DJ for diversity when we have excess
            # Prioritize non-DJ, but include DJ headlines to reach max_headlines target
            if non_dj_items and dj_items:
                # Balance providers: allow up to 60% DJ if that's what we have
                max_dj_allowed = max(int(max_headlines * 0.60), 1)
                max_non_dj_allowed = max_headlines - max_dj_allowed
                mixed = []
                mixed.extend(non_dj_items[:max_non_dj_allowed])
                mixed.extend(dj_items[:max_dj_allowed])
                deduped = mixed
        
        # Limit to max requested (show all if fewer available)
        deduped = deduped[:max_headlines]

        # -------------------------
        # Filter by timeframe if specified
        # -------------------------
        # Extract time window configuration for "Read Headlines Aloud" feature
        news_within_minutes = 0
        try:
            time_unit = form.get("NewsTimeUnit", "minutes").lower()
            within_value = int(form.get("NewsWithinValue", 0))
            if within_value > 0:
                if time_unit == "hours":
                    news_within_minutes = within_value * 60
                elif time_unit == "days":
                    news_within_minutes = within_value * 1440
                else:  # minutes (default)
                    news_within_minutes = within_value
        except Exception:
            pass

        # Apply timeframe filter if configured
        if news_within_minutes > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=news_within_minutes)
            filtered_by_time = []
            for h in deduped:
                time_str = h.get("time", "")
                parsed_time = None
                try:
                    # Try standard IBKR format
                    if " " in time_str:
                        parsed_time = datetime.strptime(
                            time_str.split(".")[0], "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=timezone.utc)
                    elif time_str.isdigit():
                        parsed_time = datetime.fromtimestamp(
                            int(time_str) / 1000, tz=timezone.utc
                        )
                except Exception:
                    pass

                # Include headline if it's within the timeframe, or if time couldn't be parsed
                # (to be conservative and not drop headlines with parsing issues)
                if parsed_time is None or parsed_time >= cutoff:
                    filtered_by_time.append(h)
            
            deduped = filtered_by_time
            logger.info(
                "fetchNews timeframe filter: requested last %d minutes, returned %d / %d headlines",
                news_within_minutes, len(deduped), len(filtered_by_time) if 'filtered_by_time' in locals() else 0
            )

        # Parse times and build clean output
        import re as _re
        import urllib.parse as _urlparse

        result = []
        for h in deduped:
            time_str = h.get("time", "")
            article_id = h.get("articleId", "")
            provider = h.get("provider", "")
            raw_headline = h.get("headline", "")

            # Strip {PROVIDER} tags and stray punctuation that IBKR embeds
            headline = _re.sub(r"\{[^}]*\}", "", raw_headline)
            headline = headline.replace("!", "").strip()

            # IBKR time format: "2024-03-25 14:30:00.0" or epoch
            parsed_time = None
            try:
                # Try standard IBKR format
                if " " in time_str:
                    parsed_time = datetime.strptime(
                        time_str.split(".")[0], "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                elif time_str.isdigit():
                    parsed_time = datetime.fromtimestamp(
                        int(time_str) / 1000, tz=timezone.utc
                    )
            except Exception:
                pass

            # Build the article URL pointing to IBKR article detail endpoint
            url = ""
            try:
                if provider and article_id:
                    url = "/news/article?" + _urlparse.urlencode({
                        "provider": provider,
                        "articleId": article_id,
                    })
            except Exception:
                pass

            result.append({
                "time": time_str,
                "parsedTime": parsed_time.isoformat() if parsed_time else time_str,
                "provider": provider,
                "articleId": article_id,
                "headline": headline,
                "url": url,
            })

        # Cleanup with thread-safe removal
        # Note: we keep these in the dict for a short time to allow any stray callbacks
        # to detect the request is no longer active and log appropriately
        with self._news_lock:
            self._news_data.pop(news_req_id, None)
            self._news_done.pop(news_req_id, None)
        
        logger.debug("fetchNews reqId=%s cleanup complete, returning %d final headlines", 
                    news_req_id, len(result))
        return result

    def fetchNewsArticle(self, provider_code, article_id):
        """
        Fetch the full body of a news article from IBKR using reqNewsArticle.

        Returns dict: {"articleType": int, "articleText": str}
          articleType: 0 = plain text, 1 = HTML
        Returns None on timeout or error.
        """
        with self.Locking:
            self.idInc += 1
            req_id = self.idInc

        self._article_data.pop(req_id, None)
        self._article_done[req_id] = False

        try:
            self.reqNewsArticle(req_id, provider_code, article_id, [])
        except Exception as e:
            logger.warning("reqNewsArticle failed provider=%s articleId=%s: %s",
                           provider_code, article_id, e)
            self._article_done.pop(req_id, None)
            return None

        # Wait for callback (bounded)
        waited = 0.0
        timeout = 10.0
        while not self._article_done.get(req_id, False):
            time.sleep(0.1)
            waited += 0.1
            if waited >= timeout:
                logger.warning("fetchNewsArticle timeout provider=%s articleId=%s",
                               provider_code, article_id)
                break

        result = self._article_data.pop(req_id, None)
        self._article_done.pop(req_id, None)
        return result

    def getDataResult(self, i, m, net_position, form, theid, contract_id=None):
        """
        Worker method executed in a separate thread.

        For one (cusip, symbol) pair:
        - resolve contract details (uses cache if available)
        - request historical data
        - compute indicators
        - evaluate Buy/Sell signal
        """

        # init per-request structures under lock
        self.Locking.acquire()
        try:
            self.data[theid] = []
            self.hisdtId[theid] = False
            self.errorSymbol[theid] = {"ticker": m, "cusip": i}
        finally:
            self.Locking.release()

        # -------------------------
        # Try contract cache first
        # -------------------------
        contract = self.contract_cache.get(m)

        resolved_cusip = None
        if contract is None:

            selected = None

            for attempt in range(self.config.contract_lookup_max_attempts):

                # reset state for this attempt
                self.data[theid] = []
                self.requestInformation[theid] = False

                # request details from IB (protected against socket errors)
                try:
                    self.findContractDetails(theid, i, "CUSIP", m, contract_id=contract_id)
                except Exception as e:
                    logger.warning("findContractDetails raised for %s: %s", m, e)
                    self.requestInformation[theid] = True  # unblock

                waited = 0.0
                while self.requestInformation.get(theid) is False:
                    time.sleep(self.config.contract_lookup_poll_sec)
                    waited += self.config.contract_lookup_poll_sec

                    if waited >= self.config.contract_lookup_timeout_sec:
                        logger.warning("Contract lookup timeout for %s (attempt %d)", m, attempt + 1)
                        break

                contracts_list = self.data.get(theid, []) or []

                selected = self._select_best_contract(
                    contracts_list,
                    requested_symbol=m
                )

                if selected is not None:
                    resolved_cusip = selected.get("cusip")
                    break

                # small delay between retry attempts to avoid IB pacing
                if attempt < self.config.contract_lookup_max_attempts - 1:
                    time.sleep(0.25)

            # --------------------------------------------------
            # Fallback: if CUSIP-based lookup failed and we have
            # a valid symbol, try a plain symbol-only lookup.
            # This covers cases where the CUSIP is stale/wrong
            # but the ticker symbol itself resolves fine.
            # --------------------------------------------------
            if selected is None and m and m != "nan" and not str(m).lower().startswith("custom"):
                logger.info(
                    "CUSIP lookup failed for %s (cusip=%s, conId=%s). Trying symbol-only fallback.",
                    m, i, contract_id,
                )
                # one extra attempt with symbol only (no CUSIP, no conId)
                self.data[theid] = []
                self.requestInformation[theid] = False

                try:
                    self.findContractDetails(theid, None, None, m, contract_id=None)
                except Exception as e:
                    logger.warning("findContractDetails fallback raised for %s: %s", m, e)
                    self.requestInformation[theid] = True  # unblock

                waited = 0.0
                while self.requestInformation.get(theid) is False:
                    time.sleep(self.config.contract_lookup_poll_sec)
                    waited += self.config.contract_lookup_poll_sec
                    if waited >= self.config.contract_lookup_timeout_sec:
                        break

                contracts_list = self.data.get(theid, []) or []
                selected = self._select_best_contract(
                    contracts_list,
                    requested_symbol=m,
                )
                if selected is not None:
                    resolved_cusip = selected.get("cusip") or i

            if selected is None:
                # Preserve the actual IB error detail if the error callback already
                # stored a more specific message for this request id.
                existing = self.warningTicker.get(theid)
                if existing and len(existing) >= 3 and "Error:" in str(existing[2]):
                    # Keep the IB error message — don't overwrite with generic text
                    pass
                else:
                    self.warningTicker[theid] = [
                        m,
                        i,
                        "Contract lookup failed (CUSIP + symbol) after "
                        f"{self.config.contract_lookup_max_attempts} attempts due to IBKR TWS API error",
                    ]
                try:
                    self.numberOfTicker -= 1
                except Exception:
                    pass

                self.data.pop(theid, None)
                self.HistoricalDt.pop(theid, None)
                return

            # Try to build an IB Contract object from the selected result; fallback if keys missing
            symbol_for_contract = m
            try:
                symbol_for_contract = selected.get("symbol", m)
                sec_type = selected.get("secType", "STK")
                raw_exchange = selected.get("exchange", "SMART")
                primary_exchange = selected.get("primaryExchange", "")
                currency = selected.get("currency", "USD")

                # Always route through SMART for market data; use the
                # specific exchange as primaryExchange so IB can still
                # identify the correct listing venue.
                if raw_exchange and raw_exchange != "SMART" and not primary_exchange:
                    primary_exchange = raw_exchange
                exchange = "SMART"

                contract = self.marketContract(
                    symbol_for_contract,
                    sec_type,
                    exchange,
                    primary_exchange,
                    currency,
                )
                # Preserve conId from IB contractDetails so news fetch and
                # other conId-dependent calls work correctly.
                resolved_conId = selected.get("conId")
                if resolved_conId:
                    contract.conId = int(resolved_conId)
            except Exception:
                contract = self.marketContract(m, "STK", "SMART", "", "USD")

            # Cache the Contract object under both the resolved symbol and the original key 'm'
            # try block out section to see if where repeated posting same results
            try:
                self.Locking.acquire()
                if symbol_for_contract:
                    self.contract_cache[symbol_for_contract] = contract
                self.contract_cache[m] = contract
            finally:
                self._save_contract_cache_to_disk(
                    updated_symbols={m, symbol_for_contract}
                )
                self.Locking.release()
        else:
            # cached contract found: ensure `m` variable aligns with contract.symbol (for later messages)
            try:
                m = getattr(contract, "symbol", m) or m
            except Exception:
                pass
            # Use the cusip passed into getDataResult as fallback when cache hit
            # skips contract resolution (which is where resolved_cusip is normally set)
            resolved_cusip = i

        # small delay for safety (preserve original timing behavior)
        time.sleep(0.1)

        # -------------------------
        # Fetch market cap via fundamental ratios (tick type 258)
        # -------------------------
        # Market cap is requested via reqMktData with "258" tag to get fundamental ratios.
        # This provides near-real-time market cap data (not historical/lag).
        # Request market cap if:
        # 1. ComparisonMarketCap is configured, OR
        # 2. filterMarketCap checkbox is enabled, OR
        # 3. Always fetch for display in results (now default behavior)
        # 
        # Approach (in priority order):
        # 1. Try to calculate from current_price × shares_outstanding (most real-time)
        # 2. Fall back to IBKR MKTCAP fundamental data (may be delayed 1+ day)
        # 
        # The normalization function _normalize_market_cap() handles various formats
        _mktcap_value = None
        should_fetch_mktcap = True  # Always fetch market cap for results display
        
        if should_fetch_mktcap:
            with self.Locking:
                self.idInc += 1
                mktcap_req_id = self.idInc

            with self._fundamental_lock:
                self._fundamental_data[mktcap_req_id] = {}
                self._fundamental_done[mktcap_req_id] = False

            try:
                # Request generic tick 258 (FUNDAMENTAL_RATIOS) which includes MKTCAP and SHARES
                self.reqMktData(mktcap_req_id, contract, "258", False, False, [])
                logger.debug("Requested market cap data (tick 258) for %s (reqId=%s)", m, mktcap_req_id)
            except Exception as e:
                logger.debug("reqMktData(258) failed for %s: %s", m, e)

            # wait for tickString callback (up to 5 seconds for reliable data)
            _waited = 0.0
            while _waited < 5.0:
                with self._fundamental_lock:
                    if self._fundamental_done.get(mktcap_req_id, False):
                        break
                time.sleep(0.15)
                _waited += 0.15

            try:
                self.cancelMktData(mktcap_req_id)
            except Exception:
                pass

            with self._fundamental_lock:
                ratios = self._fundamental_data.pop(mktcap_req_id, {})
                self._fundamental_done.pop(mktcap_req_id, None)

            # First, try to calculate market cap from price × shares_outstanding (most real-time)
            shares_outstanding = None
            current_price = None
            
            # Try to get shares outstanding from fundamental data
            if "SHARES" in ratios and ratios["SHARES"]:
                try:
                    shares_outstanding = float(ratios["SHARES"])
                    logger.debug("Got shares outstanding for %s: %s", m, shares_outstanding)
                except (ValueError, TypeError):
                    logger.debug("Failed to parse SHARES for %s: %s", m, ratios.get("SHARES"))
            
            # Try to get current price from latest market data or use the last available close
            # We'll get it from the history data after it's loaded
            # For now, we'll try LASTPRICE from fundamental data or use the close from history
            if "LASTPRICE" in ratios and ratios["LASTPRICE"]:
                try:
                    current_price = float(ratios["LASTPRICE"])
                    logger.debug("Got last price for %s: %s", m, current_price)
                except (ValueError, TypeError):
                    logger.debug("Failed to parse LASTPRICE for %s: %s", m, ratios.get("LASTPRICE"))
            
            # If we have both price and shares, calculate market cap
            if shares_outstanding and current_price and shares_outstanding > 0 and current_price > 0:
                _mktcap_value = _calculate_market_cap_from_price_and_shares(current_price, shares_outstanding)
                if _mktcap_value is not None and _mktcap_value > 0:
                    logger.info("Market cap for %s calculated from price(%.2f) × shares(%.0f) = %.2f million", 
                               m, current_price, shares_outstanding, _mktcap_value)
            
            # Fall back to IBKR's MKTCAP fundamental data if calculation wasn't possible
            if _mktcap_value is None and "MKTCAP" in ratios and ratios["MKTCAP"]:
                try:
                    # Normalize market cap to millions (handles m/M and b/B suffixes)
                    _mktcap_value = _normalize_market_cap(ratios["MKTCAP"])
                    if _mktcap_value is not None and _mktcap_value > 0:
                        logger.info("Market cap for %s from IBKR fundamental data: %s -> %.2f million", 
                                   m, ratios["MKTCAP"], _mktcap_value)
                    else:
                        logger.debug("Market cap normalization failed for %s: %s", m, ratios["MKTCAP"])
                except (ValueError, TypeError) as e:
                    logger.debug("Market cap parsing error for %s: %s", m, e)
            
            # Log available ratios if we couldn't find MKTCAP
            if _mktcap_value is None:
                logger.debug("No valid market cap for %s. Shares: %s, Price: %s, Ratios keys: %s", 
                           m, shares_outstanding, current_price, list(ratios.keys()))


        # -------------------------
        # Determine the per-indicator timeframe plan
        # -------------------------
        default_tf, tf_plan = self._build_tf_plan(form)

        # -------------------------
        # Request historical data for each unique timeframe (with retry)
        # -------------------------
        max_hist_attempts = 2
        tf_history = {}  # {tf_str: [bar_list]}

        for tf_str, tf_lookback in tf_plan.items():
            # Allocate a request ID for this timeframe
            with self.Locking:
                self.idInc += 1
                tf_req_id = self.idInc
            hist_req_id = tf_req_id
            tf_bars = []

            for hist_attempt in range(max_hist_attempts):
                self.HistoricalDt[hist_req_id] = []
                self.hisdtId[hist_req_id] = False

                try:
                    self.getData(contract, form, hist_req_id,
                                 override_tf=tf_str, override_lookback=tf_lookback)
                except Exception:
                    if not tf_history:
                        # First TF failed: treat as fatal
                        self.warningTicker[theid] = [m, i, "Failed to request historical data"]
                        try:
                            self.numberOfTicker -= 1
                        except Exception:
                            pass
                        self.data.pop(theid, None)
                        self.HistoricalDt.pop(hist_req_id, None)
                        return
                    break  # skip this TF, continue with what we have

                self.initial += 1
                waited = 0.0
                while not self.hisdtId.get(hist_req_id, False):
                    time.sleep(self.config.history_lookup_poll_sec)
                    waited += self.config.history_lookup_poll_sec
                    if waited >= self.config.history_lookup_timeout_sec:
                        break

                tf_bars = self.HistoricalDt.get(hist_req_id, []) or []

                if len(tf_bars) >= 1 or self.hisdtId.get(hist_req_id, False):
                    break

                if hist_attempt < max_hist_attempts - 1:
                    logger.warning(
                        "Historical data timeout for %s tf=%s (attempt %d/%d), retrying...",
                        m, tf_str, hist_attempt + 1, max_hist_attempts,
                    )
                    try:
                        self.cancelHistoricalData(hist_req_id)
                    except Exception:
                        pass
                    self.HistoricalDt.pop(hist_req_id, None)
                    self.hisdtId.pop(hist_req_id, None)
                    with self.Locking:
                        self.idInc += 1
                        hist_req_id = self.idInc
                    time.sleep(1.0)

            # Store bars for this timeframe
            if tf_bars:
                tf_history[tf_str] = tf_bars

            # Cleanup request state
            self.HistoricalDt.pop(hist_req_id, None)
            self.hisdtId.pop(hist_req_id, None)
            if hist_req_id != tf_req_id:
                self.HistoricalDt.pop(tf_req_id, None)
                self.hisdtId.pop(tf_req_id, None)

        # Determine primary history (the default TF, or first available)
        history = tf_history.get(default_tf) or next(iter(tf_history.values()), [])

        if not tf_history:
            # No data at all for any TF — warn
            self.warningTicker[theid] = [
                m, i, "Historical data download timeout",
            ]

        # -------------------------
        # Compute indicators, merging across timeframes
        # -------------------------
        if len(history) >= 1:
            try:
                if len(tf_history) <= 1:
                    # Single timeframe: use the standard path (no merge needed)
                    indic = self.getIndicators(
                        history, i, contract, form,
                        net_position.get(i, 0), m,
                        market_cap=_mktcap_value,
                    )
                else:
                    # Multiple timeframes: compute indicators per TF, then merge
                    tf_indicators = {}
                    for tf_str, tf_bars in tf_history.items():
                        if tf_bars:
                            try:
                                tf_indicators[tf_str] = self.getIndicators(
                                    tf_bars, i, contract, form,
                                    net_position.get(i, 0), m,
                                    market_cap=_mktcap_value,
                                )
                            except Exception:
                                pass

                    # Start with default TF indicators as the base
                    if default_tf in tf_indicators:
                        indic = tf_indicators[default_tf].copy()
                    else:
                        # Fall back to the first available TF
                        indic = next(iter(tf_indicators.values()), {}).copy()

                    # Override each indicator value from its assigned TF
                    for indic_key, tf_field in self._INDICATOR_TF_FIELD.items():
                        assigned_tf = form.get(tf_field) or default_tf
                        if assigned_tf not in self._KNOWN_TFS:
                            assigned_tf = default_tf
                        if assigned_tf in tf_indicators and indic_key in tf_indicators[assigned_tf]:
                            indic[indic_key] = tf_indicators[assigned_tf][indic_key]

                    logger.info(
                        "[MULTI-TF] %s merged indicators from TFs: %s",
                        m, list(tf_history.keys()),
                    )
                indic["cusip"] = resolved_cusip

                # -------------------------
                # Fetch news headlines only if news is ENABLED or keyword filtering is enabled
                # -------------------------
                should_fetch_news = (
                    form.get("ComparisonNews", "Not used") != "Not used" or 
                    bool(form.get("NewsKeywords", "").strip())
                )
                
                con_id = getattr(contract, "conId", None)
                if con_id and should_fetch_news:
                    try:
                        with self.Locking:
                            self.idInc += 1
                            news_req_id = self.idInc
                        news_headlines = self.fetchNews(con_id, form, news_req_id)
                        indic["newsHeadlines"] = news_headlines

                        # Compute latest news timestamp for sorting & signal check
                        if news_headlines:
                            indic["latestNewsTime"] = news_headlines[0].get("parsedTime", "")
                            indic["newsCount"] = len(news_headlines)
                        else:
                            indic["latestNewsTime"] = ""
                            indic["newsCount"] = 0
                    except Exception as e:
                        logger.warning("News fetch error for %s: %s", m, e)
                        indic["newsHeadlines"] = []
                        indic["latestNewsTime"] = ""
                        indic["newsCount"] = 0
                else:
                    indic["newsHeadlines"] = []
                    indic["latestNewsTime"] = ""
                    indic["newsCount"] = 0

                _ = self.buySellSignalCheck(indic, form)
            except Exception as e:
                # Protect the thread: capture indicator/signal exceptions and log to warningTicker
                self.warningTicker[theid] = [m, i, f"Indicator/signal error: {e}"]
        else:
            # zero rows -> register a warning
            if theid not in self.warningTicker:
                if tf_history:
                    self.warningTicker[theid] = [
                        self.data.get(theid, [{}])[0].get("symbol", m) if self.data.get(theid) else m,
                        i,
                        "No historical data returned by IBKR for this security",
                    ]
                else:
                    self.warningTicker[theid] = [
                        self.data.get(theid, [{}])[0].get("symbol", m) if self.data.get(theid) else m,
                        i,
                        "Historical data download timeout - no bars received",
                    ]

        # -------------------------
        # cleanup & bookkeeping
        # -------------------------
        try:
            self.cancelMktData(theid)
        except Exception:
            pass

        try:
            self.numberOfTicker -= 1
        except Exception:
            pass

        # remove per-request containers
        self.data.pop(theid, None)
        self.HistoricalDt.pop(theid, None)

    def getFinalResult(self, data, form):
        """
        Entry point for running the screening logic for all symbols.

        Spawns worker threads which call getDataResult().
        """
        # Wait for IB connection to be ready before starting threads
        waited = 0.0
        while not isinstance(self.nextOrderId, int):
            time.sleep(0.2)
            waited += 0.2
            if waited >= 10.0:
                logger.warning("getFinalResult: timed out waiting for IB connection")
                break

        self.cusip = data["cusip"][0:50]

        headers = list(data.keys())

        mainTickers = data["ticker"][0:50]
        self.ticker_ = mainTickers

        netPosition = {
            i: j["change"]
            for i, j in zip(data[headers[1]], data[headers[0]])
        }

        threads = []

        self.conIds = data.get("conId", [None] * len(self.cusip))[0:50]

        # Load form-based exclusion list (if enabled)
        form_excluded = set()
        if form.get("EnableStockExclusion"):
            exclude_str = form.get("ExcludeStocksList", "")
            if exclude_str:
                form_excluded = {s.upper().strip() for s in exclude_str.split(",") if s.strip()}
        
        # Load file-based exclusion list
        file_excluded = self.get_excluded_stocks()
        
        # Combine both lists
        all_excluded = form_excluded | file_excluded

        for cusip, conId, m in zip(self.cusip, self.conIds, mainTickers):
            
            # Check if stock is excluded
            symbol_to_check = str(m).upper() if m else ""
            if symbol_to_check in all_excluded:
                logger.info(f"Skipping excluded stock: {m}")
                continue

            time.sleep(11 / 50)

            self.Locking.acquire()
            try:
                self.numberOfTicker += 1
                self.numberSequence += 1
                theidd = self.numberSequence
                self.HistoricalDt[theidd] = []
            finally:
                self.Locking.release()

            # Keep IB 30 concurrent limit protection
            while self.numberOfTicker >= 30:
                print("Rate limit hit, waiting..", self.numberOfTicker)
                time.sleep(1)

            # AVOID ticker as nan float
            if isinstance(m, float):
                self.customSymbol += 1
                m = "custom" + str(self.customSymbol)

            t = threading.Thread(
                target=self.getDataResult,
                args=(cusip, m, netPosition, form, theidd),
                kwargs={"contract_id": conId},
            )

            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    @staticmethod
    def bracketOrder(
            parent_order_id: int,
            action: str,
            quantity: float,
            limit_price: float,
            take_profit_limit_price: float | None,
            stop_loss_price: float | None,
            tif: str = "DAY",
            outside_rth: bool = False,
            use_trailing_stop: bool = False,
            trailing_amount: float | None = None,
            trailing_percent: bool = False,
    ):
        """
        Create a standard IB bracket order:
        - parent order (limit order)
        - optional take-profit order (opposite action, limit)
        - optional stop-loss order (opposite action, stop or trailing stop)

        tif: "DAY" or "GTC"
        outside_rth: allow execution outside regular trading hours
        use_trailing_stop: use TRAIL instead of STP for the stop-loss leg
        trailing_amount: trailing amount (absolute or percent)
        trailing_percent: if True, trailing_amount is treated as a percentage
        """

        bracketOrder = []

        parent = Order()
        parent.eTradeOnly = False
        parent.firmQuoteOnly = False
        parent.orderId = parent_order_id
        parent.action = action
        parent.orderType = "LMT"
        parent.totalQuantity = quantity
        parent.lmtPrice = limit_price
        parent.tif = tif
        parent.outsideRth = outside_rth
        parent.transmit = False

        bracketOrder.append(parent)

        if take_profit_limit_price is not None:
            takeProfit = Order()
            takeProfit.eTradeOnly = False
            takeProfit.firmQuoteOnly = False
            takeProfit.orderId = parent.orderId + 1
            takeProfit.action = "SELL" if action == "BUY" else "BUY"
            takeProfit.orderType = "LMT"
            takeProfit.totalQuantity = quantity
            takeProfit.lmtPrice = take_profit_limit_price
            takeProfit.parentId = parent_order_id
            takeProfit.tif = tif
            takeProfit.outsideRth = outside_rth
            takeProfit.transmit = False

            bracketOrder.append(takeProfit)

        if stop_loss_price is not None or (use_trailing_stop and trailing_amount is not None):
            stopLoss = Order()
            stopLoss.eTradeOnly = False
            stopLoss.firmQuoteOnly = False
            stopLoss.orderId = parent.orderId + 2
            stopLoss.action = "SELL" if action == "BUY" else "BUY"
            stopLoss.totalQuantity = quantity
            stopLoss.parentId = parent_order_id
            stopLoss.tif = tif
            stopLoss.outsideRth = outside_rth
            stopLoss.transmit = False

            if use_trailing_stop and trailing_amount is not None:
                stopLoss.orderType = "TRAIL"
                if trailing_percent:
                    stopLoss.trailingPercent = trailing_amount
                else:
                    stopLoss.auxPrice = trailing_amount
            else:
                stopLoss.orderType = "STP"
                stopLoss.auxPrice = stop_loss_price

            bracketOrder.append(stopLoss)

        # The LAST order must have transmit=True to trigger IB to submit
        # the entire group.  Without this the orders sit in "held" state
        # and never reach the exchange.
        bracketOrder[-1].transmit = True

        return bracketOrder

    def multiLevelOrder(self, multi_level_order_dict: dict) -> list:
        """
        Create multiple independent bracket orders for a multi-level trading strategy.
        
        Args:
            multi_level_order_dict: Dictionary containing levels configuration
                {
                    'action': 'BUY' | 'SELL',
                    'tif': 'DAY' | 'GTC',
                    'outside_rth': bool,
                    'start_order_id': int,
                    'levels': [
                        {
                            'quantity': int,
                            'entry_price': float,
                            'entry_type': 'LMT' | 'MKT',
                            'exit_price': float | None,
                            'stop_price': float | None,
                            'use_trailing_stop': bool,
                            'trailing_amount': float | None,
                            'trailing_type': 'amount' | 'percent',
                        },
                        ...
                    ]
                }
        
        Returns:
            List of all Order objects for all levels (entry + exit + stop for each)
        """
        all_orders = []
        action = multi_level_order_dict.get('action', 'BUY')
        tif = multi_level_order_dict.get('tif', 'DAY')
        outside_rth = multi_level_order_dict.get('outside_rth', False)
        start_order_id = multi_level_order_dict.get('start_order_id', int(time.time()))
        levels = multi_level_order_dict.get('levels', [])
        
        current_order_id = start_order_id
        
        for level in levels:
            quantity = level.get('quantity')
            entry_price = level.get('entry_price')
            entry_type = level.get('entry_type', 'LMT')
            exit_price = level.get('exit_price')
            stop_price = level.get('stop_price')
            use_trailing_stop = level.get('use_trailing_stop', False)
            trailing_amount = level.get('trailing_amount')
            trailing_type = level.get('trailing_type', 'amount')
            
            # Create parent entry order
            parent = Order()
            parent.eTradeOnly = False
            parent.firmQuoteOnly = False
            parent.orderId = current_order_id
            parent.action = action
            parent.orderType = entry_type
            parent.totalQuantity = quantity
            parent.tif = tif
            parent.outsideRth = outside_rth
            parent.transmit = False
            
            if entry_type == "LMT" and entry_price:
                parent.lmtPrice = round(entry_price, 2)
            
            all_orders.append(parent)
            current_order_id += 1
            
            # Create exit order if exit price is specified
            if exit_price is not None:
                exit_order = Order()
                exit_order.eTradeOnly = False
                exit_order.firmQuoteOnly = False
                exit_order.orderId = current_order_id
                exit_order.action = "SELL" if action == "BUY" else "BUY"
                exit_order.orderType = "LMT"
                exit_order.totalQuantity = quantity
                exit_order.lmtPrice = round(exit_price, 2)
                exit_order.parentId = parent.orderId
                exit_order.tif = tif
                exit_order.outsideRth = outside_rth
                exit_order.transmit = False
                
                all_orders.append(exit_order)
                current_order_id += 1
            
            # Create stop-loss order if stop price is specified or trailing stop
            if stop_price is not None or (use_trailing_stop and trailing_amount is not None):
                stop_order = Order()
                stop_order.eTradeOnly = False
                stop_order.firmQuoteOnly = False
                stop_order.orderId = current_order_id
                stop_order.action = "SELL" if action == "BUY" else "BUY"
                stop_order.totalQuantity = quantity
                stop_order.parentId = parent.orderId
                stop_order.tif = tif
                stop_order.outsideRth = outside_rth
                stop_order.transmit = False
                
                if use_trailing_stop and trailing_amount is not None:
                    stop_order.orderType = "TRAIL"
                    if trailing_type == "percent":
                        stop_order.trailingPercent = trailing_amount
                    else:
                        stop_order.auxPrice = round(trailing_amount, 2)
                else:
                    stop_order.orderType = "STP"
                    stop_order.auxPrice = round(stop_price, 2)
                
                all_orders.append(stop_order)
                current_order_id += 1
        
        # Set the last order to transmit=True to trigger batch submission
        if all_orders:
            all_orders[-1].transmit = True
        
        return all_orders

    def multiLevelOrderAdvanced(self, multi_level_order_dict: dict) -> list:
        """
        Create multiple bracket orders with ADVANCED FEATURES:
        - Multiple exit targets per entry level (not just one)
        - Flexible stop loss configuration per level
        - Percentage allocation for partial exits
        
        Args:
            multi_level_order_dict: Dictionary containing levels configuration
                {
                    'action': 'BUY' | 'SELL',
                    'tif': 'DAY' | 'GTC',
                    'outside_rth': bool,
                    'start_order_id': int,
                    'levels': [
                        {
                            'quantity': int,
                            'entry_price': float,
                            'entry_type': 'LMT' | 'MKT',
                            'exit_prices': [
                                {
                                    'price': float,
                                    'percent_of_position': float,  # 100 = full qty
                                    'order_type': 'limit' | 'market' | 'trail',
                                    'trailing_amount': float | None,
                                    'trailing_type': 'amount' | 'percent',
                                },
                                ...
                            ],
                            'stop_price': float | None,
                        },
                        ...
                    ]
                }
        
        Returns:
            List of all Order objects for all levels
        """
        all_orders = []
        action = multi_level_order_dict.get('action', 'BUY')
        tif = multi_level_order_dict.get('tif', 'DAY')
        outside_rth = multi_level_order_dict.get('outside_rth', False)
        start_order_id = multi_level_order_dict.get('start_order_id', int(time.time()))
        levels = multi_level_order_dict.get('levels', [])
        
        current_order_id = start_order_id
        
        for level_idx, level in enumerate(levels):
            quantity = level.get('quantity')
            entry_price = level.get('entry_price')
            entry_type = level.get('entry_type', 'LMT')
            stop_price = level.get('stop_price')
            exit_prices_config = level.get('exit_prices', [])
            
            logger.info(f"Processing level {level_idx + 1}: "
                       f"Entry {quantity} @ {entry_price} ({entry_type}), "
                       f"{len(exit_prices_config)} exit targets")
            
            # Create parent entry order
            parent = Order()
            parent.eTradeOnly = False
            parent.firmQuoteOnly = False
            parent.orderId = current_order_id
            parent.action = action
            parent.orderType = entry_type
            parent.totalQuantity = quantity
            parent.tif = tif
            parent.outsideRth = outside_rth
            parent.transmit = False
            
            if entry_type == "LMT" and entry_price:
                parent.lmtPrice = round(entry_price, 2)
            
            all_orders.append(parent)
            logger.debug(f"Created parent entry order {current_order_id}: {action} {quantity} @ {entry_price}")
            current_order_id += 1
            
            # Create exit orders for each target
            for exit_idx, exit_config in enumerate(exit_prices_config):
                exit_price = exit_config.get('price')
                percent_of_position = exit_config.get('percent_of_position', 100.0)
                exit_order_type = exit_config.get('order_type', 'limit').upper()
                
                # Calculate quantity for this exit
                exit_quantity = max(1, int(quantity * (percent_of_position / 100.0)))
                
                # Normalize order type
                if exit_order_type in ('LIMIT', 'LMT'):
                    exit_order_type = 'LMT'
                elif exit_order_type in ('MARKET', 'MKT'):
                    exit_order_type = 'MKT'
                elif exit_order_type in ('TRAIL', 'TRAIL_PERCENT', 'TRAIL_CANDLE'):
                    exit_order_type = 'TRAIL'
                elif exit_order_type in ('STOP', 'STP'):
                    exit_order_type = 'STP'
                else:
                    exit_order_type = 'LMT'  # Default to limit
                
                # Create exit order
                exit_order = Order()
                exit_order.eTradeOnly = False
                exit_order.firmQuoteOnly = False
                exit_order.orderId = current_order_id
                exit_order.action = "SELL" if action == "BUY" else "BUY"
                exit_order.totalQuantity = exit_quantity
                exit_order.parentId = parent.orderId
                exit_order.tif = tif
                exit_order.outsideRth = outside_rth
                exit_order.transmit = False
                
                if exit_order_type == "LMT" and exit_price:
                    exit_order.orderType = "LMT"
                    exit_order.lmtPrice = round(exit_price, 2)
                elif exit_order_type == "MKT":
                    exit_order.orderType = "MKT"
                elif exit_order_type == "TRAIL":
                    exit_order.orderType = "TRAIL"
                    trailing_amount = exit_config.get('trailing_amount')
                    trailing_type = exit_config.get('trailing_type', 'amount')
                    if trailing_type == 'percent':
                        exit_order.trailingPercent = trailing_amount
                    else:
                        exit_order.auxPrice = round(trailing_amount, 2)
                else:
                    exit_order.orderType = "LMT"
                    exit_order.lmtPrice = round(exit_price, 2)
                
                all_orders.append(exit_order)
                logger.debug(f"Created exit order {current_order_id}: "
                            f"{exit_order.action} {exit_quantity} @ {exit_price} "
                            f"({percent_of_position:.1f}% of position)")
                current_order_id += 1
            
            # Create stop-loss order if specified
            if stop_price is not None and stop_price > 0:
                stop_order = Order()
                stop_order.eTradeOnly = False
                stop_order.firmQuoteOnly = False
                stop_order.orderId = current_order_id
                stop_order.action = "SELL" if action == "BUY" else "BUY"
                stop_order.orderType = "STP"
                stop_order.totalQuantity = quantity
                stop_order.auxPrice = round(stop_price, 2)
                stop_order.parentId = parent.orderId
                stop_order.tif = tif
                stop_order.outsideRth = outside_rth
                stop_order.transmit = False
                
                all_orders.append(stop_order)
                logger.debug(f"Created stop-loss order {current_order_id}: "
                            f"{stop_order.action} {quantity} @ {stop_price}")
                current_order_id += 1
        
        # Set the last order to transmit=True to trigger batch submission
        if all_orders:
            all_orders[-1].transmit = True
            logger.info(f"Multi-level order ready: {len(all_orders)} total orders "
                       f"({len(levels)} levels with multiple exits)")
        
        return all_orders

    def marketRule(self, market_rule_id: int, price_increments: ListOfPriceIncrements):
        """
        Callback providing market rule price increments.
        """

        super().marketRule(market_rule_id, price_increments)

        print("Market Rule ID: ", market_rule_id)

        for priceIncrement in price_increments:
            print("Price Increment.", priceIncrement)

    def openOrder(
            self,
            order_id: OrderId,
            contract: Contract,
            order: Order,
            order_state: OrderState,
    ):
        """
        Callback when an order is opened or updated.
        """

        super().openOrder(order_id, contract, order, order_state)

        print(
            "OpenOrder. PermId: ",
            order.permId,
            "ClientId:",
            order.clientId,
            " OrderId:",
            order_id,
            "Account:",
            order.account,
            "Symbol:",
            contract.symbol,
            "SecType:",
            contract.secType,
            "Exchange:",
            contract.exchange,
            "Action:",
            order.action,
            "OrderType:",
            order.orderType,
            "TotalQty:",
            order.totalQuantity,
            "CashQty:",
            order.cashQty,
            "LmtPrice:",
            order.lmtPrice,
            "AuxPrice:",
            order.auxPrice,
            "Status:",
            order_state.status,
        )

    # ---------------------------
    # IBKR Scanner callbacks & helper
    # ---------------------------
    def scannerData(self, req_id, rank, contract_details,
                    distance, benchmark, projection, legs_str):

        symbol = contract_details.contract.symbol
        conId = contract_details.contract.conId

        with self._scanner_lock:
            self._scanner_results_raw.append({
                "rank": rank,
                "contractDetails": self._to_dict(contract_details),
                "distance": distance,
                "benchmark": benchmark,
                "projection": projection,
                "legsStr": legs_str,
            })
            self._scanner_results.append({
                "rank": rank,
                "symbol": symbol,
                "conId": conId
            })

    def scannerDataEnd(self, req_id):
        self._scanner_event.set()

    def request_price_movers(
            self,
            timeout_sec: int = 30,
            num_rows: int = 50,
            scan_code: str = "TOP_PERC_GAIN",
            instrument: str = "STK",
            location_code: str = "STK.US",
            above_price: float = 0.05,
            above_volume: int = 75000,
            min_percent: float | None = None,
            batch_size: int | None = None
    ):
        """
        Request IBKR scanner (TOP % movers) and return list of dicts:
          [{'symbol': str, 'rank': int, 'percent': float}, ...]

        Notes:
        - Uses tickType 56 when available; falls back to LAST+CLOSE if not.
        """
        sub = ScannerSubscription()
        sub.instrument = instrument
        sub.locationCode = location_code
        sub.scanCode = scan_code
        sub.numberOfRows = num_rows
        sub.abovePrice = float(above_price)
        sub.aboveVolume = int(above_volume)

        # build a unique request id
        # reuse idInc counter already present in the class
        try:
            reqId = int(self.idInc) + 1
            self.idInc = reqId
        except Exception:
            reqId = random.randint(100000, 999999)
            self.idInc = reqId

        # send subscription
        try:
            # NB: this is the actual IB API call that starts the scanner
            self.reqScannerSubscription(reqId, sub, [], [])
        except Exception as e:
            logger.exception("reqScannerSubscription failed: %s", e)
            raise

        finished = self._scanner_event.wait(timeout=timeout_sec)

        try:
            self.cancelScannerSubscription(reqId)
        except Exception:
            # ignore cancel errors but log debug
            logger.debug("cancelScannerSubscription raised for reqId %s", reqId, exc_info=True)

        if not finished:
            # timed out - raise so callers can handle (Flask layer will return 503)
            raise RuntimeError(
                f"IB scanner timed out after {timeout_sec} seconds (reqId={reqId}).")

        # sort scanner results by rank
        with self._scanner_lock:
            scanner_rows = sorted(self._scanner_results, key=lambda x: x["rank"])

        # the contracts' list
        contracts = scanner_rows

        # base req id for market requests
        market_req_id = reqId * 1000

        # ---------- batching optional ----------

        # if batch_size is None or <=0 → request all at once
        if not batch_size or batch_size <= 0:
            batches = [contracts]
        else:
            batches = [
                contracts[i:i + batch_size]
                for i in range(0, len(contracts), batch_size)
            ]

        for batch in batches:

            # clear event and set expected counter
            self._market_event.clear()

            with self._market_lock:

                self._market_expected = len(batch)

                for each_contract in batch:

                    symbol = each_contract["symbol"]
                    self._market_data[market_req_id] = {
                        "symbol": symbol,
                        "conId": each_contract["conId"],
                        "last": None,
                        "close": None,
                        "percent": None,
                        "volume": None
                    }

                    try:
                        contract = Contract()
                        contract.symbol = symbol
                        contract.secType = "STK"
                        contract.exchange = "SMART"
                        contract.currency = "USD"

                        self.reqMktData(
                            market_req_id,
                            contract,
                            "233",
                            False,
                            False,
                            []
                        )
                    except Exception:
                        logger.debug(
                            "reqMktData failed for %s (req %s)",
                            each_contract,
                            market_req_id,
                            exc_info=True
                        )

                    market_req_id += 1

            # wait for responses
            self._market_event.wait(timeout=timeout_sec)

            # cancel subscriptions for this batch
            cancel_start = market_req_id - len(batch)
            cancel_end = market_req_id

            for cancel_id in range(cancel_start, cancel_end):

                try:
                    self.cancelMktData(cancel_id)
                except Exception:
                    pass

            time.sleep(0.2)

        # ---------- merge/compute final percent map ----------
        with self._market_lock:
            percent_map = {
                v["symbol"]: {
                    "percent": v.get("percent"),
                    "conId": v.get("conId"),
                    "volume": v.get("volume")
                }
                for v in self._market_data.values()
                if v.get("percent") is not None
            }

        # ---------- build results and apply min_percent filter ----------
        raw_results = []

        for row in scanner_rows:

            data = percent_map.get(row["symbol"])

            pct = data["percent"] if data else None
            # Preserve conId from scanner results; fall back to percent_map only if available
            conId = (data["conId"] if data else None) or row.get("conId")
            volume = data["volume"] if data else None

            if min_percent is not None and pct is not None and pct < min_percent:
                continue

            raw_results.append({
                "symbol": row["symbol"],
                "conId": conId,
                "rank": row["rank"],
                "percent": pct,
                "volume": volume,
            })

        # -------------------------------------------------
        # Apply forced volume filter SAFELY
        # -------------------------------------------------

        if self.config.force_min_volume and above_volume is not None:

            filtered_results = [
                r for r in raw_results
                if r["volume"] is not None and r["volume"] >= above_volume
            ]

            # Only use filtered results if NOT EMPTY
            if filtered_results:
                results = filtered_results
            else:
                results = raw_results  # fallback
        else:

            results = raw_results

        # # sort safely (None last)
        # results.sort(
        #     key=lambda x: x["percent"] if x["percent"] is not None else -999999,
        #     reverse=True
        # )

        return results

    def _reset_scanner_state(self):
        """Clear scanner-related state for a fresh request_price_movers() call."""
        with self._scanner_lock:
            self._scanner_results_raw = []
            self._scanner_results = []
            self._scanner_event.clear()
        with self._market_lock:
            self._market_data = {}
            self._market_event.clear()
            self._market_expected = 0

    def _reset_screening_state(self):
        """Clear ALL screening-related state for a fresh getFinalResult() call."""
        self.sendToFlaskIB = {}
        self.warningTicker = {}
        self.errorSymbol = {}
        self.otherErrorCounter = 0
        self.numberOfTicker = 0
        self.initial = 0

        # Clear accumulated per-request dicts that leak across iterations
        self.data = {}
        self.hisdtId = {}
        self.requestInformation = {}
        self.HistoricalDt = {}
        self.windowLength = {}
        self.priceMarketData = {}

        # Reset maxlength so it is recomputed from the form each run
        self.maxlength = None

        # Clear contract cache so each iteration resolves contracts fresh
        # (prevents stale exchange routing and the resolved_cusip=None bug)
        self.contract_cache = {}

        # Reset custom symbol counter to avoid unbounded growth
        self.customSymbol = 0


# =============================================================================
# MULTI-OBV ANALYSIS FUNCTIONS
# =============================================================================

def analyze_multi_obv(
    fast_obv: float = None,
    medium_obv: float = None, 
    slow_obv: float = None,
    prev_fast: float = None,
    prev_medium: float = None,
    prev_slow: float = None,
    change_threshold: float = 5.0
) -> dict:
    """
    Analyze three OBV indicators (Fast, Medium, Slow) to generate trading signals.
    
    Detects:
    - Alignment: bullish (all positive), bearish (all negative), misaligned (mixed)
    - Divergence: when OBVs move in opposite directions
    - Transitions: when OBV changes sign (positive to negative or vice versa)
    - Strength: based on alignment and % changes
    - % changes: between pairs (Fast→Medium, Medium→Slow, Fast→Slow)
    
    Args:
        fast_obv: Current Fast OBV value
        medium_obv: Current Medium OBV value
        slow_obv: Current Slow OBV value
        prev_fast: Previous Fast OBV value
        prev_medium: Previous Medium OBV value
        prev_slow: Previous Slow OBV value
        change_threshold: Minimum % change to trigger "strong" signal (default 5.0%)
    
    Returns:
        dict with keys:
            - signal: strong_bullish/bullish/neutral/bearish/strong_bearish
            - alignment: aligned_bullish/aligned_bearish/misaligned/neutral
            - strength: very_strong/strong/moderate/weak
            - divergence: bool (True if OBVs diverge)
            - fast_transition: bool (True if Fast OBV changes sign)
            - medium_transition: bool (True if Medium OBV changes sign)
            - slow_transition: bool (True if Slow OBV changes sign)
            - fast_medium_pct_change: % change from Fast to Medium
            - medium_slow_pct_change: % change from Medium to Slow
            - fast_slow_pct_change: % change from Fast to Slow
            - equation: Formatted display equation
            - description: Natural language description for TTS
    """
    
    # Handle None values - return neutral
    if fast_obv is None or medium_obv is None or slow_obv is None:
        return {
            'signal': 'neutral',
            'alignment': 'neutral',
            'strength': 'weak',
            'divergence': False,
            'fast_transition': False,
            'medium_transition': False,
            'slow_transition': False,
            'fast_medium_pct_change': 0.0,
            'medium_slow_pct_change': 0.0,
            'fast_slow_pct_change': 0.0,
            'equation': 'Insufficient data for analysis',
            'description': 'Cannot analyze OBV with missing data'
        }
    
    # Calculate % changes with safe division
    def safe_pct_change(current: float, reference: float) -> float:
        """Calculate % change safely, handling zero/None values."""
        if reference is None or reference == 0:
            return 0.0
        try:
            return ((current - reference) / abs(reference)) * 100.0
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    # Calculate % changes
    fast_medium_pct = safe_pct_change(medium_obv, fast_obv)
    medium_slow_pct = safe_pct_change(slow_obv, medium_obv)
    fast_slow_pct = safe_pct_change(slow_obv, fast_obv)
    
    # Detect transitions (sign changes)
    fast_transition = (prev_fast is not None and 
                      ((prev_fast > 0 and fast_obv <= 0) or (prev_fast < 0 and fast_obv >= 0)))
    medium_transition = (prev_medium is not None and 
                        ((prev_medium > 0 and medium_obv <= 0) or (prev_medium < 0 and medium_obv >= 0)))
    slow_transition = (prev_slow is not None and 
                      ((prev_slow > 0 and slow_obv <= 0) or (prev_slow < 0 and slow_obv >= 0)))
    
    # Detect alignment
    all_positive = fast_obv > 0 and medium_obv > 0 and slow_obv > 0
    all_negative = fast_obv < 0 and medium_obv < 0 and slow_obv < 0
    
    if all_positive:
        alignment = 'aligned_bullish'
    elif all_negative:
        alignment = 'aligned_bearish'
    else:
        alignment = 'misaligned'
    
    # Detect divergence (mixed signs)
    divergence = not (all_positive or all_negative)
    
    # Determine signal based on alignment and transitions
    if all_positive:
        if fast_transition or medium_transition:
            # Was bearish, now turning bullish
            signal = 'strong_bullish'
            strength = 'very_strong'
        elif abs(fast_medium_pct) > change_threshold or abs(medium_slow_pct) > change_threshold:
            signal = 'strong_bullish'
            strength = 'strong'
        else:
            signal = 'bullish'
            strength = 'moderate'
    elif all_negative:
        if fast_transition or medium_transition:
            # Was bullish, now turning bearish
            signal = 'strong_bearish'
            strength = 'very_strong'
        elif abs(fast_medium_pct) > change_threshold or abs(medium_slow_pct) > change_threshold:
            signal = 'strong_bearish'
            strength = 'strong'
        else:
            signal = 'bearish'
            strength = 'moderate'
    else:
        # Misaligned
        if divergence and (fast_transition or medium_transition or slow_transition):
            signal = 'neutral'  # Conflicting signals
            strength = 'weak'
        else:
            signal = 'neutral'
            strength = 'weak'
    
    # Build equation display with direction indicators
    fast_dir = '↑' if fast_obv > 0 else '↓'
    medium_dir = '↑' if medium_obv > 0 else '↓'
    slow_dir = '↑' if slow_obv > 0 else '↓'
    
    equation = (
        f"Fast: {fast_obv:,.0f}{fast_dir} | "
        f"Medium: {medium_obv:,.0f}{medium_dir} | "
        f"Slow: {slow_obv:,.0f}{slow_dir} | "
        f"Changes: F-M:{fast_medium_pct:+.1f}%, M-S:{medium_slow_pct:+.1f}%, F-S:{fast_slow_pct:+.1f}%"
    )
    
    # Build natural language description
    if signal == 'strong_bullish':
        if fast_transition:
            description = f"Strong bullish momentum detected! Fast OBV transitioned from bearish to bullish with Medium OBV rising {fast_medium_pct:+.1f}%."
        else:
            description = f"Very strong bullish alignment detected. All OBV indicators positive with significant upward momentum. Fast to Medium change: {fast_medium_pct:+.1f}%."
    elif signal == 'bullish':
        description = f"Bullish OBV alignment detected. All indicators positive with moderate growth. Fast to Medium: {fast_medium_pct:+.1f}%, Medium to Slow: {medium_slow_pct:+.1f}%."
    elif signal == 'strong_bearish':
        if fast_transition:
            description = f"Strong bearish momentum detected! Fast OBV transitioned from bullish to bearish with Medium OBV falling {fast_medium_pct:+.1f}%."
        else:
            description = f"Very strong bearish alignment detected. All OBV indicators negative with significant downward momentum. Fast to Medium change: {fast_medium_pct:+.1f}%."
    elif signal == 'bearish':
        description = f"Bearish OBV alignment detected. All indicators negative with moderate decline. Fast to Medium: {fast_medium_pct:+.1f}%, Medium to Slow: {medium_slow_pct:+.1f}%."
    else:  # neutral
        if divergence:
            description = f"OBV divergence detected. Mixed signals between indicators - Fast OBV is {('bullish' if fast_obv > 0 else 'bearish')} while Slow OBV is {('bullish' if slow_obv > 0 else 'bearish')}. Exercise caution."
        else:
            description = f"Neutral OBV signal. Insufficient momentum or conflicting indicators. Monitor for clearer direction."
    
    return {
        'signal': signal,
        'alignment': alignment,
        'strength': strength,
        'divergence': divergence,
        'fast_transition': fast_transition,
        'medium_transition': medium_transition,
        'slow_transition': slow_transition,
        'fast_medium_pct_change': fast_medium_pct,
        'medium_slow_pct_change': medium_slow_pct,
        'fast_slow_pct_change': fast_slow_pct,
        'equation': equation,
        'description': description
    }
