"""
Resilience & Retry Module

Provides:
- Exponential backoff retry mechanism
- Partial failure handling (skip + log)
- % change data normalization with fallbacks
- Symbol-level error tracking
"""

import time
import math
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
import logging

logger = logging.getLogger("ibkr_app")


class ExponentialBackoffRetry:
    """
    Manages exponential backoff retry logic for transient failures.
    
    Usage:
        retry = ExponentialBackoffRetry(max_attempts=3, base_delay=0.5)
        result = retry.execute(callable_func, *args, **kwargs)
    """
    
    def __init__(self, max_attempts=3, base_delay=0.5, max_delay=30.0, jitter=True):
        """
        Args:
            max_attempts: Maximum number of attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay cap in seconds
            jitter: Add randomness to prevent thundering herd
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.attempt_count = 0
    
    def calculate_delay(self, attempt):
        """
        Calculate delay for attempt using exponential backoff:
        delay = min(base_delay * (2 ** attempt), max_delay)
        """
        delay = self.base_delay * (2 ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add up to 25% jitter
            jitter_amount = delay * 0.25
            delay = delay + (np.random.random() - 0.5) * jitter_amount * 2
        
        return max(0.1, delay)  # Minimum 100ms
    
    def execute(self, func: callable, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic.
        
        Args:
            func: Callable to execute
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Result from func or raises exception after max_attempts
        
        Raises:
            Exception: If all retries exhausted
        """
        self.attempt_count = 0
        last_exception = None
        
        for attempt in range(self.max_attempts):
            self.attempt_count = attempt + 1
            
            try:
                logger.debug(f"[RETRY] Attempt {self.attempt_count}/{self.max_attempts}")
                return func(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"[RETRY] Attempt {self.attempt_count} failed: {e}. "
                        f"Retrying in {delay:.2f}s ({attempt + 1}/{self.max_attempts - 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[RETRY] All {self.max_attempts} attempts exhausted. Final error: {e}"
                    )
        
        raise last_exception


class PartialFailureHandler:
    """
    Tracks and manages partial failures at symbol level.
    
    Allows continuing with successful symbols while logging failures.
    """
    
    def __init__(self, log_failures=True):
        """
        Args:
            log_failures: Whether to log individual failures
        """
        self.failed_symbols = {}  # symbol -> error reason
        self.succeeded_symbols = set()
        self.log_failures = log_failures
    
    def mark_failed(self, symbol: str, reason: str, cusip: str = None):
        """Mark symbol as failed with reason."""
        self.failed_symbols[symbol] = {
            'reason': reason,
            'timestamp': time.time(),
            'cusip': cusip,
        }
        if self.log_failures:
            logger.warning(f"[PARTIAL FAILURE] Symbol {symbol} ({cusip}): {reason}")
    
    def mark_succeeded(self, symbol: str):
        """Mark symbol as succeeded."""
        self.succeeded_symbols.add(symbol)
        # Remove from failures if it was retried and succeeded
        self.failed_symbols.pop(symbol, None)
    
    def get_summary(self):
        """Get summary of failures and successes."""
        return {
            'succeeded_count': len(self.succeeded_symbols),
            'failed_count': len(self.failed_symbols),
            'failed_symbols': dict(self.failed_symbols),
            'success_rate': len(self.succeeded_symbols) / (len(self.succeeded_symbols) + len(self.failed_symbols))
            if (len(self.succeeded_symbols) + len(self.failed_symbols)) > 0 else 0,
        }
    
    def log_summary(self):
        """Log summary of partial failures."""
        summary = self.get_summary()
        logger.info(
            f"[PARTIAL RESULTS] Success: {summary['succeeded_count']}, "
            f"Failed: {summary['failed_count']}, "
            f"Rate: {summary['success_rate']:.1%}"
        )
        
        if summary['failed_symbols']:
            logger.warning(f"[FAILED SYMBOLS] {list(summary['failed_symbols'].keys())}")


class PercentChangeNormalizer:
    """
    Normalizes % change data with multiple fallback strategies.
    """
    
    @staticmethod
    def calculate_from_prices(last_price, close_price):
        """
        Calculate % change from last and close prices.
        
        Returns:
            float or None: (last - close) / close * 100, or None if calculation impossible
        """
        try:
            if last_price is None or close_price is None:
                return None
            if close_price == 0:
                return None
            
            pct_change = ((last_price - close_price) / close_price) * 100.0
            return float(pct_change)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    
    @staticmethod
    def calculate_from_ohlc(dataframe):
        """
        Calculate % change from OHLC data (highest priority: close bars).
        
        Tries:
        1. Previous bar close vs current bar close
        2. Day low vs day high
        3. Open vs close (intraday)
        
        Args:
            dataframe: pd.DataFrame with 'open', 'high', 'low', 'close', 'date' columns
        
        Returns:
            float or None: % change value
        """
        if dataframe is None or dataframe.empty:
            return None
        
        try:
            # Try previous close vs current close (most accurate)
            if len(dataframe) >= 2:
                prev_close = float(dataframe['close'].iloc[-2])
                curr_close = float(dataframe['close'].iloc[-1])
                
                if prev_close != 0 and not np.isnan(prev_close) and not np.isnan(curr_close):
                    return ((curr_close - prev_close) / prev_close) * 100.0
            
            # Fallback: current open vs current close (intraday)
            if len(dataframe) >= 1:
                open_price = float(dataframe['open'].iloc[-1])
                close_price = float(dataframe['close'].iloc[-1])
                
                if open_price != 0 and not np.isnan(open_price) and not np.isnan(close_price):
                    return ((close_price - open_price) / open_price) * 100.0
            
            return None
        except (TypeError, ValueError, KeyError, IndexError):
            return None
    
    @staticmethod
    def normalize_market_data(market_data, last_price=None, close_price=None, df=None):
        """
        Normalize % change with intelligent fallback chain.
        
        Priority:
        1. Already computed 'percent' in market_data
        2. LAST_PERCENT from ticker
        3. Calculate from LAST and CLOSE prices
        4. Calculate from OHLC data
        
        Args:
            market_data: dict with potential 'percent', 'last', 'close' keys
            last_price: Optional explicit last price
            close_price: Optional explicit close price
            df: Optional DataFrame for OHLC fallback
        
        Returns:
            dict: market_data dict with 'percent' key set (or None if unavailable)
        """
        market_data = market_data or {}
        
        # Already have percent from LAST_PERCENT tick
        if market_data.get('percent') is not None:
            return market_data
        
        # Try calculate from provided/stored prices
        calc_pct = PercentChangeNormalizer.calculate_from_prices(
            last_price or market_data.get('last'),
            close_price or market_data.get('close')
        )
        if calc_pct is not None:
            market_data['percent'] = calc_pct
            logger.debug(f"[PCT CALC] Calculated from prices: {calc_pct:.2f}%")
            return market_data
        
        # Final fallback: calculate from OHLC
        if df is not None:
            calc_pct = PercentChangeNormalizer.calculate_from_ohlc(df)
            if calc_pct is not None:
                market_data['percent'] = calc_pct
                market_data['percent_source'] = 'ohlc_fallback'
                logger.debug(f"[PCT CALC] Calculated from OHLC: {calc_pct:.2f}%")
                return market_data
        
        # No percent available
        market_data['percent'] = None
        logger.warning("[PCT CALC] Could not calculate percent change from any source")
        return market_data


class HistoricalDataRetryFetcher:
    """
    Wrapper for historical data fetching with retry and timeout handling.
    
    Handles:
    - Timeout with retry
    - Partial data (fewer rows than requested)
    - Connection errors
    """
    
    def __init__(self, ibapi, config):
        """
        Args:
            ibapi: IBapi instance
            config: Configuration object (has timeout/poll settings)
        """
        self.ibapi = ibapi
        self.config = config
    
    def fetch_with_retry(self, req_id, contract, timeout_sec=None, retry_count=1):
        """
        Fetch historical data with retry capability.
        
        Args:
            req_id: Request ID
            contract: IB Contract object
            timeout_sec: Timeout override (uses config default if None)
            retry_count: Number of retry attempts
        
        Returns:
            list: Historical bars, possibly empty
        """
        timeout = timeout_sec or self.config.history_lookup_timeout_sec
        
        retry = ExponentialBackoffRetry(
            max_attempts=retry_count,
            base_delay=0.5,
            max_delay=5.0
        )
        
        def attempt_fetch():
            """Nested function for retry.execute()"""
            return self._wait_for_data(req_id, timeout)
        
        try:
            return retry.execute(attempt_fetch)
        except Exception as e:
            logger.warning(f"[FETCH FAILED] ReqId {req_id}: {e} after {retry_count} attempts")
            # Return whatever partial data we have gathered
            return self.ibapi.HistoricalDt.get(req_id, [])
    
    def _wait_for_data(self, req_id, timeout_sec):
        """Wait for historical data with timeout."""
        waited = 0.0
        poll_sec = self.config.history_lookup_poll_sec
        timed_out = False

        while not self.ibapi.hisdtId.get(req_id, False):
            time.sleep(poll_sec)
            waited += poll_sec

            if waited >= timeout_sec:
                logger.warning(
                    f"[HIST TIMEOUT] ReqId {req_id} exceeded {timeout_sec}s timeout"
                )
                timed_out = True
                break

        data = self.ibapi.HistoricalDt.get(req_id, []) or []
        logger.info(f"[HIST DATA] ReqId {req_id}: {len(data)} bars (waited {waited:.1f}s)")

        if timed_out and not self.ibapi.hisdtId.get(req_id, False):
            raise TimeoutError(
                f"Historical data request {req_id} timed out after {timeout_sec} seconds"
            )

        return data
    
    def validate_rowcount(self, data, min_rows, symbol, cusip):
        """
        Validate sufficient rows returned.
        
        Args:
            data: List of bars
            min_rows: Minimum required rows
            symbol: Symbol being fetched
            cusip: CUSIP for error tracking
        
        Returns:
            tuple: (is_valid, error_message or None)
        """
        if not data:
            return False, f"No historical data received for {symbol} ({cusip})"
        
        rows = len(data)
        if rows < min_rows:
            pct_complete = (rows / min_rows) * 100.0
            return False, f"Insufficient data: {rows}/{min_rows} bars ({pct_complete:.0f}%)"
        
        return True, None


def create_retry_context(ibapi, config):
    """
    Factory to create retry/resilience objects.
    
    Returns:
        dict: Context with retry helpers
    """
    return {
        'retry_executor': ExponentialBackoffRetry(max_attempts=3, base_delay=0.5),
        'failure_tracker': PartialFailureHandler(log_failures=True),
        'pct_normalizer': PercentChangeNormalizer(),
        'data_fetcher': HistoricalDataRetryFetcher(ibapi, config),
    }
