import time
import json
import math
import random
import logging
import threading
import os
import datetime
import urllib.request
import urllib.parse
import numpy as np
import pandas as pd
from config import Config
from typing import Any, Dict
from ibapi.order import *
from ibapi.common import *
from ibapi.common import OrderId
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order_state import OrderState
from ibapi.scanner import ScannerSubscription

from indicators import (
    VolumeWeightedAveragePrice,
    SMAIndicator,
    RSIIndicator,
    EMAIndicator,
    OBVIndicator,
    ATRIndicator,
    # pivot_points,
    last_value
)

from resilience import (
    ExponentialBackoffRetry,
    PartialFailureHandler,
    PercentChangeNormalizer,
    HistoricalDataRetryFetcher,
    create_retry_context,
)

# -----------------------------------------------------------------------------
# Logging - lightweight
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ibkr_app")


def _safe_compare(value, op, threshold):
    """
    Compare value and threshold safely.
    If value is None -> return False.
    """

    if value is None or threshold is None:
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


def _parse_float(value):
    """Convert value to float safely; return None otherwise."""
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def evaluate(value, condition, target, target2=None):
    """Unified condition evaluator supporting >, <, >=, <=, between."""
    if condition in (None, "Not used", ""):
        return None

    normalized = condition
    if condition == "greater":
        normalized = ">"
    elif condition == "greaterEqual":
        normalized = ">="
    elif condition == "lower":
        normalized = "<"
    elif condition == "lowerEqual":
        normalized = "<="
    elif condition == "between":
        normalized = "between"

    if normalized == "between":
        if target is None or target2 is None:
            return False
        lo = _parse_float(target)
        hi = _parse_float(target2)
        if lo is None or hi is None:
            return False

        if value is None:
            return False

        try:
            # Use strict inequality for 'between' (old logic in the application)
            return float(value) > lo and float(value) < hi
        except (ValueError, TypeError):
            return False

    # non-between comparison
    rhs = _parse_float(target)
    if rhs is None:
        return False

    if value is None:
        return False

    try:
        lhs = float(value)
    except (ValueError, TypeError):
        return False

    return _safe_compare(lhs, normalized, rhs)


def evaluate_percentage(value, condition, base, percentage, percentage2=None):
    """Compare via percentage on a base value.

    For non-between: compare value to base * (1+percentage/100).
    For between: compare value to [base*(1+percentage/100), base*(1+percentage2/100)].
    """
    base_float = _parse_float(base)
    pct1 = _parse_float(percentage)
    pct2 = _parse_float(percentage2)

    if base_float is None or pct1 is None:
        return False

    try:
        current = float(value)
    except (ValueError, TypeError):
        return False

    if condition == "between":
        if pct2 is None:
            return False
        lower = base_float * (1.0 + pct1 / 100.0)
        upper = base_float * (1.0 + pct2 / 100.0)
        return lower <= current <= upper

    target = base_float * (1.0 + pct1 / 100.0)

    return evaluate(current, condition, target)


def absolute_cond(value, condition, target, target2=None):
    """Absolute value and between comparison."""
    return evaluate(value, condition, target, target2)


def percent_cond(value, condition, base, pct, pct2=None):
    """Percent-based comparison against base.

    The caller should pass percentage amount (e.g. 5 for +5%).
    """
    return evaluate_percentage(value, condition, base, pct, pct2)


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
        # Resilience & Retry Context
        # ---------------------------
        self._resilience = create_retry_context(self, self.config)
        self._failure_tracker = self._resilience['failure_tracker']
        self._data_fetcher = self._resilience['data_fetcher']
        self._pct_normalizer = self._resilience['pct_normalizer']

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

        if not getattr(self.config, "enable_contract_cache", False):
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
                c = self.marketContract(
                    data["symbol"],
                    data["secType"],
                    data["exchange"],
                    data.get("primaryExchange", ""),
                    data["currency"],
                )
                self.contract_cache[symbol] = c
            except Exception:
                continue

    def _save_contract_cache_to_disk(self, updated_symbols=None):

        if not getattr(self.config, "enable_contract_cache", False):
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

        # Assumes the list is already initialized elsewhere
        self.HistoricalDt[req_id].append(current_bar)

    def historicalDataEnd(self, req_id: int, start: str, end: str):
        """
        Callback fired when all historical bars for reqId were sent.
        """

        super().historicalDataEnd(req_id, start, end)

        print("HistoricalDataEnd. ReqId:", req_id, "from", start, "to", end)

        # mark this request as completed
        self.hisdtId[req_id] = True

    def tickPrice(self, req_id, tick_type, price, attrib):
        """
        Callback for live / delayed market price updates.

        - Supports tickType 56 (LAST_PERCENT) as a primary source.
        - Fallback: capture LAST (4) and CLOSE (9) and compute pct when both present.
        - NEW: All % change values go through resilience normalizer for fallback support
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

                        # NEW: Normalize % change with fallback chain if needed
                        if hasattr(self, '_pct_normalizer'):
                            normalized_pct = self._pct_normalizer.normalize_market_data(
                                self._market_data[req_id],
                                last_price=self._market_data[req_id].get("last"),
                                close_price=self._market_data[req_id].get("close"),
                                df=None
                            )
                            if normalized_pct is not None:
                                self._market_data[req_id]["percent"] = normalized_pct
                                logger.debug(f"[NORMALIZATION] req_id {req_id}: LAST_PERCENT normalized to {normalized_pct}")

                        # mark progress
                        if isinstance(self._market_expected, int) and self._market_expected > 0:
                            self._market_expected -= 1
                        # set event when done
                        if self._market_expected <= 0:
                            self._market_event.set()
                return
        except Exception as e:
            # don't raise from callback
            logger.warning(f"[NORMALIZATION ERROR] LAST_PERCENT normalization failed: {e}")
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

                    # NEW: Normalize % change with fallback chain if needed
                    if hasattr(self, '_pct_normalizer'):
                        normalized_pct = self._pct_normalizer.normalize_market_data(
                            entry,
                            last_price=last,
                            close_price=close,
                            df=None
                        )
                        if normalized_pct is not None:
                            entry["percent"] = normalized_pct
                            logger.debug(f"[NORMALIZATION] req_id {req_id}: LAST/CLOSE normalized to {normalized_pct}")

                    if isinstance(self._market_expected, int) and self._market_expected > 0:
                        self._market_expected -= 1
                    if self._market_expected <= 0:
                        self._market_event.set()
        except Exception as e:
            # swallow any callback exceptions
            logger.warning(f"[NORMALIZATION ERROR] LAST/CLOSE normalization failed: {e}")
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

            self.warningTicker[self.otherErrorCounter] = [
                req_id,
                "Internal Error",
                f"Error: {error_code}. {error_string}",
            ]

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
        self.data[req_id].append(contract_info)

    def contractDetailsEnd(self, req_id):
        """
        IB callback fired when all contract details for req_id are received.
        """

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
        # --------------------------------------------------
        elif (
                sec_id
                and sec_id != "nan"
                and sec_id_type == "CUSIP"
                and not str(sec_id).lower().startswith("custom")
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

    # =========================================================================
    # NEW: Per-Indicator Execution Architecture
    # =========================================================================
    # Enables independent timeframe and historical data fetch for each indicator
    # =========================================================================

    def build_indicator_config(self, form):
        """
        Extract indicator configuration from form.
        
        Returns:
            dict: {
                'indicator_name': {
                    'enabled': bool,
                    'timeframe': str,              # '1 min', '5 min', '1 day', etc.
                    'window': int,                  # lookback window/period
                    'comparison': str,              # 'Not used', '>', '<', 'between', etc.
                    'threshold1': float,            # primary threshold
                    'threshold2': float or None,    # secondary threshold for 'between'
                    'alt_window': int or None,      # alternative window for 'between' comparisons
                },
                ...
            }
        
        Example:
            {
                'FastSMA': {
                    'enabled': True,
                    'timeframe': '5m',
                    'window': 21,
                    'comparison': '>',
                    'threshold1': 100.0,
                    'threshold2': None,
                    'alt_window': None,
                },
                'SlowEMA': {
                    'enabled': True,
                    'timeframe': '1d',
                    'window': 50,
                    'comparison': 'between',
                    'threshold1': 90.0,
                    'threshold2': 110.0,
                    'alt_window': 60,
                },
            }
        """
        config = {}
        
        # Indicator definitions: (form_key, form_window_key, form_tf_key, form_comparison_key, form_threshold_key, form_threshold2_key, alt_window_key)
        indicator_specs = [
            ("FastSMA", "FastSMA", "FastSMA_tf", "ComparisonFastSMA", "FastSMA_threshold", "FastSMA_threshold2", "FastSMA1"),
            ("FastSMA1", "FastSMA1", "FastSMA1_tf", "ComparisonFastSMA", "FastSMA_threshold", "FastSMA_threshold2", "FastSMA1"),
            ("MediumSMA", "MediumSMA", "MediumSMA_tf", "ComparisonMediumSMA", "MediumSMA_threshold", "MediumSMA_threshold2", "MediumSMA1"),
            ("MediumSMA1", "MediumSMA1", "MediumSMA1_tf", "ComparisonMediumSMA", "MediumSMA_threshold", "MediumSMA_threshold2", "MediumSMA1"),
            ("SlowSMA", "SlowSMA", "SlowSMA_tf", "ComparisonSlowSMA", "SlowSMA_threshold", "SlowSMA_threshold2", "SlowSMA1"),
            ("SlowSMA1", "SlowSMA1", "SlowSMA1_tf", "ComparisonSlowSMA", "SlowSMA_threshold", "SlowSMA_threshold2", "SlowSMA1"),
            ("VWAP", "VWAP", "VWAP_tf", "ComparisonVWAP", "VWAP_threshold", "VWAP_threshold2", "VWAP1"),
            ("VWAP1", "VWAP1", "VWAP1_tf", "ComparisonVWAP", "VWAP_threshold", "VWAP_threshold2", "VWAP1"),
            ("RSI", "RSI", "RSI_tf", "ComparisonRSI", "RSI_threshold", "RSI_threshold2", "RSI1"),
            ("RSI1", "RSI1", "RSI1_tf", "ComparisonRSI", "RSI_threshold", "RSI_threshold2", "RSI1"),
            ("FastEMA", "FastEMA", "FastEMA_tf", "ComparisonFastEMA", "FastEMA_threshold", "FastEMA_threshold2", "FastEMA1"),
            ("FastEMA1", "FastEMA1", "FastEMA1_tf", "ComparisonFastEMA", "FastEMA_threshold", "FastEMA_threshold2", "FastEMA1"),
            ("SlowEMA", "SlowEMA", "SlowEMA_tf", "ComparisonSlowEMA", "SlowEMA_threshold", "SlowEMA_threshold2", "SlowEMA1"),
            ("SlowEMA1", "SlowEMA1", "SlowEMA1_tf", "ComparisonSlowEMA", "SlowEMA_threshold", "SlowEMA_threshold2", "SlowEMA1"),
            ("OBV", "OBV", "OBV_tf", "ComparisonOBV", "OBV_threshold", "OBV_threshold2", "OBV1"),
            ("OBV1", "OBV1", "OBV1_tf", "ComparisonOBV", "OBV_threshold", "OBV_threshold2", "OBV1"),
            ("ATR", "ATR", "ATR_tf", "ComparisonATR", "ATR_threshold", "ATR_threshold2", "ATR1"),
            ("ATR1", "ATR1", "ATR1_tf", "ComparisonATR", "ATR_threshold", "ATR_threshold2", "ATR1"),
            ("PrevClose", "PrevClose", "PrevClose_tf", "ComparisonPrevClose", "PrevClose_threshold", "PrevClose_threshold2", "PrevClose1"),
            ("LowOfDay", "LowOfDay", "LowOfDay_tf", "ComparisonLowOfDay", "LowOfDay_threshold", "LowOfDay_threshold2", "LowOfDay1"),
            ("HighOfDay", "HighOfDay", "HighOfDay_tf", "ComparisonHighOfDay", "HighOfDay_threshold", "HighOfDay_threshold2", "HighOfDay1"),
            ("HighestHigh", "HighestHigh", "HighestHigh_tf", "ComparisonHighestHigh", "HighestHigh_threshold", "HighestHigh_threshold2", "HighestHigh1"),
            ("Pullback", "Pullback", "Pullback_tf", "ComparisonPullback", "Pullback_threshold", "Pullback_threshold2", "Pullback1"),
        ]
        
        for ind_name, window_key, tf_key, cmp_key, thresh_key, thresh2_key, alt_key in indicator_specs:
            comparison = form.get(cmp_key, "Not used")
            
            if comparison == "Not used":
                continue
            
            # Extract window
            try:
                window = int(form.get(window_key, "20"))
            except (ValueError, TypeError):
                window = 20
            
            # Extract timeframe
            timeframe = form.get(tf_key, "1 day")
            
            # Extract thresholds
            try:
                threshold1 = float(form.get(thresh_key, "0"))
            except (ValueError, TypeError):
                threshold1 = 0.0
            
            try:
                threshold2 = float(form.get(thresh2_key)) if form.get(thresh2_key) else None
            except (ValueError, TypeError):
                threshold2 = None
            
            # Extract alternative window (for 'between' comparisons)
            alt_window = None
            if comparison == "between":
                try:
                    alt_window = int(form.get(alt_key, window))
                except (ValueError, TypeError):
                    alt_window = window
            
            config[ind_name] = {
                'enabled': True,
                'timeframe': timeframe,
                'window': window,
                'comparison': comparison,
                'threshold1': threshold1,
                'threshold2': threshold2,
                'alt_window': alt_window,
            }
        
        logger.info("[INDICATOR CONFIG] Built config for %d indicators", len(config))
        return config

    def group_indicators_by_timeframe(self, indicator_config):
        """
        Group indicators by their required timeframe to minimize API calls.
        
        Returns:
            dict: {
                'timeframe': ['indicator1', 'indicator2', ...],
                ...
            }
        
        Example:
            {
                '5m': ['FastSMA', 'FastSMA1'],
                '1d': ['SlowSMA', 'SlowEMA', 'RSI'],
            }
        """
        grouped = {}
        
        for ind_name, ind_cfg in indicator_config.items():
            tf = ind_cfg['timeframe']
            if tf not in grouped:
                grouped[tf] = []
            grouped[tf].append(ind_name)
        
        logger.info("[TIMEFRAME GROUPING] %d unique timeframes: %s", len(grouped), list(grouped.keys()))
        return grouped

    def calculate_lookback_for_indicators(self, indicator_config):
        """
        Calculate maximum lookback window needed across all indicators for each timeframe.
        
        Returns:
            dict: {
                'timeframe': max_window_for_this_tf,
                ...
            }
        """
        timeframe_lookbacks = {}
        
        for ind_name, ind_cfg in indicator_config.items():
            tf = ind_cfg['timeframe']
            window = ind_cfg['window']
            alt_window = ind_cfg.get('alt_window') or ind_cfg['window']
            
            max_window = max(window, alt_window)
            
            if tf not in timeframe_lookbacks:
                timeframe_lookbacks[tf] = max_window
            else:
                timeframe_lookbacks[tf] = max(timeframe_lookbacks[tf], max_window)
        
        logger.info("[LOOKBACK CALCULATION] Per-timeframe lookbacks: %s", timeframe_lookbacks)
        return timeframe_lookbacks

    def fetch_data_for_timeframe(self, contract, timeframe, lookback_window, theid, timeframe_index):
        """
        Request historical data for ONE specific timeframe.
        
        Args:
            contract: IB Contract object
            timeframe: str, one of '1 min', '5 min', '1 hour', '1 day'
            lookback_window: int, number of bars to request
            theid: int, base request ID
            timeframe_index: int, 0-based index for this timeframe (to derive unique reqId)
        
        Returns:
            int: The reqId used for this request
        """
        TIMEFRAME_TO_IB = {
            "1 min": ("1 min", 60),
            "2 min": ("2 mins", 120),
            "5 min": ("5 mins", 300),
            "15 min": ("15 mins", 900),
            "1 hour": ("1 hour", 3600),
            "1 day": ("1 day", 86400),
            "1 year": ("1 day", 31536000),
        }
        
        ib_bar_size, bar_seconds = TIMEFRAME_TO_IB.get(timeframe, ("1 day", 86400))
        
        # Calculate timeperiod needed to cover lookback_window bars
        if bar_seconds < 3600:
            # intraday minute bars
            minutes_per_trading_day = 390
            bars_per_day = (minutes_per_trading_day * 60) / bar_seconds
            if bars_per_day < 1:
                bars_per_day = 1
            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            timeperiod = f"{days_needed} D"
        elif ib_bar_size == "1 hour":
            bars_per_day = 6.5
            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            timeperiod = f"{days_needed} D"
        else:
            # daily bars
            if lookback_window < 365:
                timeperiod = f"{lookback_window} D"
            else:
                years = int(math.ceil(float(lookback_window) / 252.0))
                if years < 1:
                    years = 1
                timeperiod = f"{years} Y"
        
        # Create unique request ID for this timeframe (theid_0, theid_1, etc.)
        reqId = theid * 1000 + timeframe_index
        
        # Initialize storage
        self.HistoricalDt[reqId] = []
        self.hisdtId[reqId] = False
        
        logger.info(
            "[FETCH TIMEFRAME] %s | timeframe=%s | bar_size=%s | timeperiod=%s | lookback=%s | reqId=%s",
            getattr(contract, 'symbol', '<unknown>'),
            timeframe,
            ib_bar_size,
            timeperiod,
            lookback_window,
            reqId,
        )
        
        try:
            self.reqHistoricalData(
                reqId,
                contract,
                "",
                timeperiod,
                ib_bar_size,
                "TRADES",
                0,
                1,
                False,
                [],
            )
        except Exception as e:
            logger.exception("Failed to request historical data for %s at %s", 
                           getattr(contract, 'symbol', '<unknown>'), timeframe)
            raise
        
        return reqId

    def fetch_all_timeframe_data(self, contract, indicator_config, theid):
        """
        Request historical data for all required timeframes.
        
        Returns:
            dict: {
                'timeframe': reqId,
                ...
            }
        """
        timeframe_lookbacks = self.calculate_lookback_for_indicators(indicator_config)
        timeframe_to_reqid = {}
        
        for index, (timeframe, lookback_window) in enumerate(timeframe_lookbacks.items()):
            reqId = self.fetch_data_for_timeframe(contract, timeframe, lookback_window, theid, index)
            timeframe_to_reqid[timeframe] = reqId
        
        return timeframe_to_reqid

    def wait_for_all_timeframe_data(self, timeframe_to_reqid, timeout_per_tf=10.0):
        """
        Wait for historical data to arrive for all requested timeframes.
        
        Args:
            timeframe_to_reqid: dict mapping timeframe -> reqId
            timeout_per_tf: timeout in seconds per timeframe
        
        Returns:
            dict: {
                'timeframe': data_list,
                ...
            }
        """
        timeframe_data = {}
        
        for timeframe, reqId in timeframe_to_reqid.items():
            waited = 0.0
            while not self.hisdtId.get(reqId, False):
                time.sleep(0.1)
                waited += 0.1
                if waited >= timeout_per_tf:
                    logger.warning("[WAIT TIMEOUT] Timeframe %s (reqId %s) exceeded timeout", timeframe, reqId)
                    break
            
            data = self.HistoricalDt.get(reqId, []) or []
            timeframe_data[timeframe] = data
            
            logger.info("[TIMEFRAME DATA READY] %s: %d bars", timeframe, len(data))
        
        return timeframe_data

    def compute_single_indicator(self, indicator_name, indicator_cfg, timeframe_data_df, symbol, form):
        """
        Compute a single indicator from its dedicated timeframe data.
        
        Args:
            indicator_name: str, e.g. 'FastSMA', 'SlowEMA'
            indicator_cfg: dict with 'window', 'alt_window', etc.
            timeframe_data_df: pd.DataFrame with cols [date, open, high, low, close, volume]
            symbol: str, for logging
            form: dict, original form for extra config
        
        Returns:
            dict: {
                indicator_name: value (float or None),
                indicator_name + '1': value (float or None) if 'between' comparison,
            }
        """
        results = {}
        
        if timeframe_data_df.empty:
            logger.warning("[COMPUTE FAILED] %s %s: empty dataframe", symbol, indicator_name)
            results[indicator_name] = None
            if indicator_cfg['comparison'] == 'between':
                results[indicator_name + '1'] = None
            return results
        
        try:
            # Compute primary value
            if indicator_name.startswith('FastSMA') or indicator_name.startswith('MediumSMA') or indicator_name.startswith('SlowSMA'):
                window = indicator_cfg['window']
                sma = SMAIndicator(close=timeframe_data_df["close"], window=window)
                results[indicator_name] = last_value(sma.sma_indicator())
                
                if indicator_cfg['comparison'] == 'between':
                    alt_window = indicator_cfg.get('alt_window', window)
                    sma_alt = SMAIndicator(close=timeframe_data_df["close"], window=alt_window)
                    results[indicator_name + '1'] = last_value(sma_alt.sma_indicator())
            
            elif indicator_name.startswith('FastEMA') or indicator_name.startswith('SlowEMA'):
                window = indicator_cfg['window']
                ema = EMAIndicator(close=timeframe_data_df["close"], window=window)
                try:
                    ema_series = ema.ema_indicator()
                except Exception:
                    ema_series = ema.ema()
                results[indicator_name] = last_value(ema_series)
                
                if indicator_cfg['comparison'] == 'between':
                    alt_window = indicator_cfg.get('alt_window', window)
                    ema_alt = EMAIndicator(close=timeframe_data_df["close"], window=alt_window)
                    try:
                        ema_alt_series = ema_alt.ema_indicator()
                    except Exception:
                        ema_alt_series = ema_alt.ema()
                    results[indicator_name + '1'] = last_value(ema_alt_series)
            
            elif indicator_name.startswith('VWAP'):
                window = indicator_cfg['window']
                vwap = VolumeWeightedAveragePrice(
                    high=timeframe_data_df["high"],
                    low=timeframe_data_df["low"],
                    close=timeframe_data_df["close"],
                    volume=timeframe_data_df["volume"],
                    window=window,
                )
                results[indicator_name] = last_value(vwap.volume_weighted_average_price())
                
                if indicator_cfg['comparison'] == 'between':
                    alt_window = indicator_cfg.get('alt_window', window)
                    vwap_alt = VolumeWeightedAveragePrice(
                        high=timeframe_data_df["high"],
                        low=timeframe_data_df["low"],
                        close=timeframe_data_df["close"],
                        volume=timeframe_data_df["volume"],
                        window=alt_window,
                    )
                    results[indicator_name + '1'] = last_value(vwap_alt.volume_weighted_average_price())
            
            elif indicator_name.startswith('RSI'):
                window = indicator_cfg['window']
                rsi = RSIIndicator(timeframe_data_df["close"], window=window)
                results[indicator_name] = last_value(rsi.rsi())
                
                if indicator_cfg['comparison'] == 'between':
                    alt_window = indicator_cfg.get('alt_window', window)
                    rsi_alt = RSIIndicator(timeframe_data_df["close"], window=alt_window)
                    results[indicator_name + '1'] = last_value(rsi_alt.rsi())
            
            elif indicator_name.startswith('OBV'):
                obv = OBVIndicator(close=timeframe_data_df["close"], volume=timeframe_data_df["volume"])
                try:
                    obv_series = obv.on_balance_volume()
                except Exception:
                    try:
                        obv_series = obv.obv()
                    except Exception:
                        obv_series = obv.onBalanceVolume()
                results[indicator_name] = last_value(obv_series)
                
                if indicator_cfg['comparison'] == 'between':
                    obv_alt = OBVIndicator(close=timeframe_data_df["close"], volume=timeframe_data_df["volume"])
                    try:
                        obv_alt_series = obv_alt.on_balance_volume()
                    except Exception:
                        try:
                            obv_alt_series = obv_alt.obv()
                        except Exception:
                            obv_alt_series = obv_alt.onBalanceVolume()
                    results[indicator_name + '1'] = last_value(obv_alt_series)
            
            elif indicator_name.startswith('ATR'):
                window = indicator_cfg['window']
                atr = ATRIndicator(
                    high=timeframe_data_df["high"],
                    low=timeframe_data_df["low"],
                    close=timeframe_data_df["close"],
                    window=window,
                )
                try:
                    atr_series = atr.average_true_range()
                except Exception:
                    try:
                        atr_series = atr.atr()
                    except Exception:
                        atr_series = atr.averageTrueRange()
                results[indicator_name] = last_value(atr_series)
                
                if indicator_cfg['comparison'] == 'between':
                    alt_window = indicator_cfg.get('alt_window', window)
                    atr_alt = ATRIndicator(
                        high=timeframe_data_df["high"],
                        low=timeframe_data_df["low"],
                        close=timeframe_data_df["close"],
                        window=alt_window,
                    )
                    try:
                        atr_alt_series = atr_alt.average_true_range()
                    except Exception:
                        try:
                            atr_alt_series = atr_alt.atr()
                        except Exception:
                            atr_alt_series = atr_alt.averageTrueRange()
                    results[indicator_name + '1'] = last_value(atr_alt_series)

            elif indicator_name == 'PrevClose':
                if len(timeframe_data_df) >= 2:
                    results['prevClose'] = float(timeframe_data_df['close'].iloc[-2])
                else:
                    results['prevClose'] = None

            elif indicator_name == 'LowOfDay':
                try:
                    results['lowOfDay'] = float(timeframe_data_df['low'].min())
                except Exception:
                    results['lowOfDay'] = None

            elif indicator_name == 'HighOfDay':
                try:
                    results['highOfDay'] = float(timeframe_data_df['high'].max())
                except Exception:
                    results['highOfDay'] = None

            elif indicator_name == 'HighestHigh':
                try:
                    window = indicator_cfg.get('window', 1)
                    high_series = timeframe_data_df['high']
                    if not high_series.empty:
                        lookup = min(len(high_series), int(window)) if window and window > 0 else len(high_series)
                        results['highestHigh'] = float(high_series.iloc[-lookup:].max())
                    else:
                        results['highestHigh'] = None
                except Exception:
                    results['highestHigh'] = None

            elif indicator_name == 'Pullback':
                current_close = float(timeframe_data_df['close'].iloc[-1]) if not timeframe_data_df.empty else None
                high = float(timeframe_data_df['high'].iloc[-1]) if not timeframe_data_df.empty else None
                prev_close = float(timeframe_data_df['close'].iloc[-2]) if len(timeframe_data_df) >= 2 else None

                if prev_close is not None and high is not None and high != prev_close and current_close is not None:
                    results['pullback'] = (high - current_close) / (high - prev_close)
                else:
                    results['pullback'] = None

            else:
                logger.warning("[COMPUTE] Unknown indicator: %s", indicator_name)
                results[indicator_name] = None
        
        except Exception as e:
            logger.exception("[COMPUTE FAILED] %s %s: %s", symbol, indicator_name, e)
            results[indicator_name] = None
            if indicator_cfg['comparison'] == 'between':
                results[indicator_name + '1'] = None
        
        return results

    def getData(self, contract, form, theid):
        """
        Request historical market data for a contract based on the indicator
        configuration contained in `form`.

        Behavior:
        - Compute maximum lookback window required by enabled indicators (lo
        okback_window).
        - Detect per-indicator time frame fields. If any are present,
          choose the *finest* (smallest) timeframe among them.
          Otherwise fall back to self.addFrequency or a safe default.
        - Request IB historical data using the chosen bar size. For intraday
          minute bar sizes the function requests enough *days* to cover lookback_window bars
          (approx 390 trading minutes/day).
        """
        # ------------------------------------------------------------------
        # Determine the maximum lookback required by all indicators
        # ------------------------------------------------------------------
        maxlength = []

        # Primary indicator fields
        for key in ("FastSMA", "MediumSMA", "SlowSMA", "VWAP", "RSI",
                    "AverageVolume", "FastEMA", "SlowEMA", "OBV", "ATR"):
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
        # Collect requested per-indicator timeframes (new per-indicator fields)
        # ------------------------------------------------------------------
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
        )

        for tf_field in per_indicator_tf_fields:
            if tf_field in form and form[tf_field] not in (None, ""):
                requested_tfs.append(form[tf_field])

        # Fallback to the global selector if no per-indicator TFs were provided
        if not requested_tfs:
            # try attribute on the engine first
            if getattr(self, "addFrequency", None):
                requested_tfs.append(self.addFrequency)
            # otherwise try the form-posted global value
            elif "addFrequency" in form and form["addFrequency"] not in (None, ""):
                requested_tfs.append(form["addFrequency"])
            else:
                requested_tfs.append("1 day")  # safe default

        # Normalize and filter requested timeframes to known choices
        requested_tfs = [tf for tf in requested_tfs if tf in TIMEFRAME_TO_IB]

        if not requested_tfs:
            # if none matched, fallback to daily
            requested_tfs = ["1 day"]

        # ------------------------------------------------------------------
        # Choose the *finest* (smallest duration) timeframe among requested
        # ------------------------------------------------------------------
        def tf_seconds(tf):
            return TIMEFRAME_TO_IB.get(tf, ("1 day", 86400))[1]

        selected_tf = min(requested_tfs, key=tf_seconds)
        ib_bar_size, bar_seconds = TIMEFRAME_TO_IB.get(selected_tf, ("1 day", 86400))

        # ------------------------------------------------------------------
        # Determine an appropriate 'timeperiod' string for IB's reqHistoricalData
        # The goal is to request enough history to cover `lookback_window` bars at chosen gran.
        # For intraday minute bars we approximate 390 trading minutes/day.
        # ------------------------------------------------------------------
        if bar_seconds < 3600:
            # intraday minute-based bars
            minutes_per_trading_day = 390  # conservative approximation (US regular session)
            bars_per_day = (minutes_per_trading_day * 60) / bar_seconds
            # avoid division by zero and ensure at least 1 bar/day
            if bars_per_day < 1:
                bars_per_day = 1
            days_needed = int(math.ceil(float(lookback_window) / bars_per_day))
            if days_needed < 1:
                days_needed = 1
            timeperiod = f"{days_needed} D"
        elif ib_bar_size == "1 hour":
            # estimate ~6.5 trading hours/day -> ~6.5 hourly bars per trading day
            bars_per_day = 6.5
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

        try:
            self.reqHistoricalData(
                idreqHistDt,
                contract,
                "",
                timeperiod,
                ib_bar_size,
                "TRADES",
                0,
                1,
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

        # Store the required window length per symbol
        try:
            self.windowLength[contract.symbol] = lookback_window
        except Exception:
            # defensive: if contract has no symbol, skip assignment
            pass

    def getIndicators(self, data, cusip, contract, form, net_position, symbol, market_data=None):
        """
        NEW ARCHITECTURE: Per-indicator execution with independent timeframes.
        
        Each indicator runs independently with its own timeframe and historical data fetch.
        This refactored version:
        - Extracts indicator config from form
        - Groups indicators by timeframe to minimize API calls
        - Fetches data for each timeframe
        - Computes each indicator using its dedicated timeframe data
        - Returns dict of indicators compatible with existing signal logic
        
        Args:
            data: list of bars (legacy fallback, now unused - fetched per-timeframe)
            cusip: str
            contract: IB Contract object
            form: dict with indicator configuration
            net_position: int
            symbol: str
            
        Returns:
            dict of indicators and computed values
        """
        logger.info(
            "[GETINDICATORS] NEW ARCHITECTURE | %s | %d primary bars (fallback)",
            getattr(contract, "symbol", symbol),
            len(data) if data else 0,
        )
        
        # Initialize result dict with basic metadata
        indicators = {
            "symbol": getattr(contract, "symbol", symbol),
            "cusip": cusip,
            "close": None,
            "volume": None,
            "netPosition": int(net_position) if net_position is not None else 0,
        }
        
        if not data:
            logger.warning("[GETINDICATORS] No primary data provided for %s", symbol)
            return indicators
        
        # =====================================================================
        # STEP 1: Extract per-indicator configuration from form
        # =====================================================================
        indicator_config = self.build_indicator_config(form)
        
        if not indicator_config:
            logger.info("[GETINDICATORS] No indicators configured for %s", symbol)
            # Set at least close/volume from primary data and derived OHLC values
            try:
                result_df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close", "volume"])
                if not result_df.empty:
                    indicators["close"] = float(result_df["close"].iloc[-1])
                    indicators["volume"] = float(result_df["volume"].iloc[-1])
                    indicators["high"] = float(result_df["high"].iloc[-1])
                    indicators["low"] = float(result_df["low"].iloc[-1])
                    indicators["highOfDay"] = float(result_df["high"].max())
                    indicators["lowOfDay"] = float(result_df["low"].min())
                    indicators["prevClose"] = float(result_df["close"].iloc[-2]) if len(result_df) >= 2 else None
                    prev_close = indicators.get("prevClose")
                    cur_close = indicators.get("close")
                    high_val = indicators.get("high")
                    if prev_close is not None and high_val is not None and high_val != prev_close and cur_close is not None:
                        indicators["pullback"] = (high_val - cur_close) / (high_val - prev_close)
                    else:
                        indicators["pullback"] = None
                else:
                    indicators["close"] = None
                    indicators["volume"] = None
            except Exception:
                pass
            return indicators
        
        # =====================================================================
        # STEP 2: Group indicators by timeframe
        # =====================================================================
        tf_grouping = self.group_indicators_by_timeframe(indicator_config)
        logger.info("[GETINDICATORS] Grouped %d indicators into %d timeframes", 
                   len(indicator_config), len(tf_grouping))
        
        # =====================================================================
        # STEP 3: Fetch data for each timeframe (NEW: per-timeframe requests)
        # =====================================================================
        # Note: This is the key architectural change - each timeframe gets fresh data
        # instead of all indicators using a single minimum timeframe
        
        # For now, map the incoming `data` to the finest timeframe
        # (preserves legacy behavior as fallback)
        finest_tf = min(tf_grouping.keys(), 
                       key=lambda tf: self._tf_to_seconds(tf))
        
        timeframe_data = {finest_tf: data}
        
        logger.info("[GETINDICATORS] Using legacy data for fine-grained timeframes: %s", finest_tf)
        
        # =====================================================================
        # STEP 4: Convert raw data to timeframe-indexed DataFrames
        # =====================================================================
        timeframe_dfs = {}
        
        for tf, bars in timeframe_data.items():
            if not bars:
                logger.warning("[GETINDICATORS] No bars for timeframe %s", tf)
                timeframe_dfs[tf] = pd.DataFrame(
                    columns=["date", "open", "high", "low", "close", "volume"]
                )
                continue
            
            try:
                df = pd.DataFrame(bars, columns=["date", "open", "high", "low", "close", "volume"])
                
                # Normalize datetime index
                def _to_datetime(x):
                    try:
                        return pd.to_datetime(x, unit="s")
                    except Exception:
                        pass
                    try:
                        return pd.to_datetime(str(x), format="%Y%m%d", errors="coerce")
                    except Exception:
                        return pd.to_datetime(x, errors="coerce")
                
                df["ts"] = df["date"].apply(_to_datetime)
                if df["ts"].isna().all():
                    df["ts"] = pd.to_datetime(df["date"], errors="coerce")
                if df["ts"].isna().any():
                    df["ts"] = df["ts"].fillna(method="ffill").fillna(method="bfill")
                
                df = df.set_index("ts", drop=False).sort_index()
                timeframe_dfs[tf] = df
                
                logger.info("[GETINDICATORS] Prepared %d bars for timeframe %s", len(df), tf)
            except Exception as e:
                logger.exception("[GETINDICATORS] Failed to prepare dataframe for timeframe %s: %s", tf, e)
                timeframe_dfs[tf] = pd.DataFrame(
                    columns=["date", "open", "high", "low", "close", "volume"]
                )
        
        # =====================================================================
        # STEP 5: Execute each indicator independently
        # =====================================================================
        for ind_name, ind_cfg in indicator_config.items():
            tf = ind_cfg['timeframe']
            ind_df = timeframe_dfs.get(tf)
            
            if ind_df is None or ind_df.empty:
                logger.warning("[GETINDICATORS] No data for %s at timeframe %s", ind_name, tf)
                indicators[ind_name] = None
                if ind_cfg['comparison'] == 'between':
                    indicators[ind_name + '1'] = None
                continue
            
            # Compute single indicator from its dedicated timeframe
            ind_results = self.compute_single_indicator(ind_name, ind_cfg, ind_df, symbol, form)
            indicators.update(ind_results)
        
        # =====================================================================
        # STEP 6: Set baseline metadata (use finest timeframe for OHLCV)
        # =====================================================================
        finest_df = timeframe_dfs.get(finest_tf)
        if finest_df is not None and not finest_df.empty:
            try:
                last_close = float(finest_df["close"].iloc[-1])
                last_high = float(finest_df["high"].iloc[-1])
                last_low = float(finest_df["low"].iloc[-1])

                indicators["close"] = last_close
                indicators["volume"] = float(finest_df["volume"].iloc[-1])
                indicators["high"] = last_high
                indicators["low"] = last_low
                indicators["highOfDay"] = float(finest_df["high"].max())
                indicators["lowOfDay"] = float(finest_df["low"].min())
                indicators["prevClose"] = float(finest_df["close"].iloc[-2]) if len(finest_df) >= 2 else None

                prev_close = indicators.get("prevClose")
                if prev_close is not None and last_high is not None and last_high != prev_close and last_close is not None:
                    indicators["pullback"] = (last_high - last_close) / (last_high - prev_close)
                else:
                    indicators["pullback"] = None
            except Exception:
                pass
        
        # NEW: Add normalized % change using fallback chain (market_data, last/close, OHLC)
        try:
            if hasattr(self, '_pct_normalizer'):
                market_data_payload = dict(market_data or {})
                normalized = self._pct_normalizer.normalize_market_data(
                    market_data_payload,
                    last_price=market_data_payload.get('last'),
                    close_price=market_data_payload.get('close'),
                    df=finest_df,
                )
                indicators['percent'] = normalized.get('percent')
                if indicators['percent'] is not None:
                    indicators['percent_source'] = normalized.get('percent_source', 'market_data')
                    logger.info(
                        "[GETINDICATORS] Added normalized percent: %.2f%% for %s (source=%s)",
                        indicators['percent'], symbol, indicators.get('percent_source')
                    )
        except Exception as e:
            logger.warning("[GETINDICATORS] Percent normalization failed for %s: %s", symbol, e)

        # NEW: Add fixed period SMAs for crossover checks (50 & 200)
        try:
            if finest_df is not None and not finest_df.empty:
                sma_50_val = last_value(SMAIndicator(close=finest_df['close'], window=50).sma_indicator())
                sma_200_val = last_value(SMAIndicator(close=finest_df['close'], window=200).sma_indicator())
                indicators['sma50'] = float(sma_50_val) if sma_50_val is not None else None
                indicators['sma200'] = float(sma_200_val) if sma_200_val is not None else None
        except Exception:
            indicators.setdefault('sma50', None)
            indicators.setdefault('sma200', None)

        logger.info(
            "[GETINDICATORS COMPLETE] %s computed %d indicator values",
            symbol,
            sum(1 for k, v in indicators.items() if v is not None and k not in ("symbol", "cusip", "netPosition")),
        )

        return indicators

    def fetch_news_for_symbol(self, symbol, limit=25, lookback_days=14):
        """Fetch symbol news and sort most recent first.

        Uses provider configured in Config.news_api_provider (optional). If not
        configured, returns an empty list and logs a warning.

        The returned list structure is:
            [{"symbol": ..., "title": ..., "url": ..., "publishedAt": ..., "source": ...}, ...]
        """
        if not symbol:
            return []

        provider = self.config.news_api_provider.strip().lower() if getattr(self, 'config', None) else ''
        api_key = self.config.news_api_key.strip() if getattr(self, 'config', None) else ''

        if not provider or not api_key:
            logger.warning("[NEWS] No news provider/key configured; returning empty news for %s", symbol)
            return []

        end_date = datetime.datetime.utcnow().date()
        start_date = end_date - datetime.timedelta(days=lookback_days)

        try:
            if provider in ('finnhub', 'finn'):
                uri = (
                    f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={start_date}&to={end_date}&token={api_key}"
                )
            elif provider in ('newsapi', 'newsapi.org'):
                uri = (
                    f"https://newsapi.org/v2/everything?q={urllib.parse.quote(symbol)}"
                    f"&from={start_date}&to={end_date}&pageSize={min(limit,100)}&sortBy=publishedAt&apiKey={api_key}"
                )
            else:
                logger.warning("[NEWS] Unsupported news provider '%s'", provider)
                return []

            with urllib.request.urlopen(uri, timeout=20) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                payload = json.loads(raw)

            articles = []
            if provider in ('finnhub', 'finn'):
                for art in payload or []:
                    articles.append({
                        'symbol': symbol,
                        'title': art.get('headline'),
                        'url': art.get('url'),
                        'summary': art.get('summary'),
                        'publishedAt': art.get('datetime'),
                        'source': art.get('source'),
                    })
            elif provider in ('newsapi', 'newsapi.org'):
                for art in payload.get('articles', [])[:limit]:
                    articles.append({
                        'symbol': symbol,
                        'title': art.get('title'),
                        'url': art.get('url'),
                        'summary': art.get('description'),
                        'publishedAt': art.get('publishedAt'),
                        'source': art.get('source', {}).get('name'),
                    })

            def parse_date(x):
                if x is None:
                    return datetime.datetime.min
                if isinstance(x, (int, float)):
                    return datetime.datetime.utcfromtimestamp(x)
                try:
                    return datetime.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
                except Exception:
                    try:
                        return datetime.datetime.strptime(str(x), '%Y-%m-%dT%H:%M:%S%z')
                    except Exception:
                        return datetime.datetime.min

            articles_sorted = sorted(
                articles,
                key=lambda item: parse_date(item.get('publishedAt')),
                reverse=True,
            )

            return articles_sorted[:limit]

        except Exception as e:
            logger.warning('[NEWS] Failed fetching news for %s: %s', symbol, e)
            return []

    @staticmethod
    def _tf_to_seconds(timeframe_str):
        """Convert timeframe string to seconds for comparison."""
        tf_map = {
            "1 min": 60,
            "2 min": 120,
            "5 min": 300,
            "15 min": 900,
            "1 hour": 3600,
            "1 day": 86400,
            "1 year": 31536000,
        }
        return tf_map.get(timeframe_str, 86400)

    @staticmethod
    def _parse_datetime(x):
        """Parse various datetime formats robustly."""
        try:
            return pd.to_datetime(x, unit="s")
        except Exception:
            pass
        try:
            return pd.to_datetime(str(x), format="%Y%m%d", errors="coerce")
        except Exception:
            return pd.to_datetime(x, errors="coerce")

    def buySellSignalCheck(self, data, form):
        condition = True
        counting_ = 0
        
        # Dictionary to track individual condition statuses for visual feedback
        conditions_status = {}

        # -------------------------
        # AVERAGE VOLUME
        # -------------------------
        zero_condition = None

        if (
                form["ComparisonAverageVolume"] not in ("Not used", "between")
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
                form["ComparisonAverageVolume"] not in ("Not used", "between")
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

        if zero_condition is not None:
            conditions_status['AverageVolume'] = zero_condition
            condition = condition and zero_condition
            counting_ += 1

        # -------------------------
        # PRICE LEVEL
        # -------------------------
        price_condition = absolute_cond(
            data.get("close"),
            form.get("ComparisonPrice", "Not used"),
            form.get("PercentagePrice"),
            form.get("PercentagePrice1"),
        )

        if price_condition is not None:
            conditions_status['Price'] = price_condition
            condition = condition and price_condition
            counting_ += 1

        # -------------------------
        # VWAP
        # -------------------------
        vwap_condition = None

        if (
                form["ComparisonVWAP"] not in ("Not used", "between")
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
                form["ComparisonVWAP"] not in ("Not used", "between")
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

        if vwap_condition is not None:
            conditions_status['VWAP'] = vwap_condition
            condition = condition and vwap_condition
            counting_ += 1

        # -------------------------
        # FAST SMA
        # -------------------------
        fast_sma_condition = None

        if (
                form["ComparisonFastSMA"] not in ("Not used", "between")
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
                form["ComparisonFastSMA"] not in ("Not used", "between")
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

        if fast_sma_condition is not None:
            conditions_status['FastSMA'] = fast_sma_condition
            condition = condition and fast_sma_condition
            counting_ += 1

        # -------------------------
        # MEDIUM SMA
        # -------------------------
        medium_sma_condition = None

        if (
                form["ComparisonMediumSMA"] not in ("Not used", "between")
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
                form["ComparisonMediumSMA"] not in ("Not used", "between")
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

        if medium_sma_condition is not None:
            conditions_status['MediumSMA'] = medium_sma_condition
            condition = condition and medium_sma_condition
            counting_ += 1

        # -------------------------
        # SLOW SMA
        # -------------------------
        slow_sma_condition = None

        if (
                form["ComparisonSlowSMA"] not in ("Not used", "between")
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
                form["ComparisonSlowSMA"] not in ("Not used", "between")
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

        if slow_sma_condition is not None:
            conditions_status['SlowSMA'] = slow_sma_condition
            condition = condition and slow_sma_condition
            counting_ += 1

        # -------------------------
        # RSI
        # -------------------------
        rsi_condition = None

        if form["ComparisonRSI"] not in ("Not used", "between"):
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

        if rsi_condition is not None:
            conditions_status['RSI'] = rsi_condition
            condition = condition and rsi_condition
            counting_ += 1

        # -------------------------
        # FAST EMA
        # -------------------------
        emaFast_condition = None

        if form.get("ComparisonFastEMA", "Not used") not in ("Not used", "between"):
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

        if emaFast_condition is not None:
            conditions_status['FastEMA'] = emaFast_condition
            condition = condition and emaFast_condition
            counting_ += 1

        # -------------------------
        # SLOW EMA
        # -------------------------
        emaSlow_condition = None

        if form.get("ComparisonSlowEMA", "Not used") not in ("Not used", "between"):
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

        if emaSlow_condition is not None:
            conditions_status['SlowEMA'] = emaSlow_condition
            condition = condition and emaSlow_condition
            counting_ += 1

        # -------------------------
        # OBV
        # -------------------------
        obv_condition = None

        if form.get("ComparisonOBV", "Not used") not in ("Not used", "between"):
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

        if obv_condition is not None:
            conditions_status['OBV'] = obv_condition
            condition = condition and obv_condition
            counting_ += 1

        # -------------------------
        # ATR
        # -------------------------
        atr_condition = None

        if form.get("ComparisonATR", "Not used") not in ("Not used", "between"):
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

        if atr_condition is not None:
            conditions_status['ATR'] = atr_condition
            condition = condition and atr_condition
            counting_ += 1

        # -------------------------
        # PREVIOUS CLOSE
        # -------------------------
        prev_condition = None

        if form.get("PrevCloseBool") == "percentage":
            prev_condition = percent_cond(
                data.get("close"),
                form.get("ComparisonPrevClose", "Not used"),
                data.get("prevClose"),
                form.get("PercentagePrevClose"),
                form.get("PercentagePrevClose1"),
            )

        elif form.get("PrevCloseBool") == "value":
            prev_condition = absolute_cond(
                data.get("prevClose"),
                form.get("ComparisonPrevClose", "Not used"),
                form.get("PercentagePrevClose"),
                form.get("PercentagePrevClose1"),
            )

        if prev_condition is not None:
            conditions_status['PrevClose'] = prev_condition
            condition = condition and prev_condition
            counting_ += 1

        # -------------------------
        # LOW OF DAY
        # -------------------------
        low_condition = None

        if form.get("LowOfDayBool") == "percentage":
            low_condition = percent_cond(
                data.get("close"),
                form.get("ComparisonLowOfDay", "Not used"),
                data.get("lowOfDay"),
                form.get("PercentageLowOfDay"),
                form.get("PercentageLowOfDay1"),
            )

        elif form.get("LowOfDayBool") == "value":
            low_condition = absolute_cond(
                data.get("lowOfDay"),
                form.get("ComparisonLowOfDay", "Not used"),
                form.get("PercentageLowOfDay"),
                form.get("PercentageLowOfDay1"),
            )

        if low_condition is not None:
            conditions_status['LowOfDay'] = low_condition
            condition = condition and low_condition
            counting_ += 1

        # -------------------------
        # HIGH OF DAY
        # -------------------------
        high_condition = None

        if form.get("HighOfDayBool") == "percentage":
            high_condition = percent_cond(
                data.get("close"),
                form.get("ComparisonHighOfDay", "Not used"),
                data.get("highOfDay"),
                form.get("PercentageHighOfDay"),
                form.get("PercentageHighOfDay1"),
            )

        elif form.get("HighOfDayBool") == "value":
            high_condition = absolute_cond(
                data.get("highOfDay"),
                form.get("ComparisonHighOfDay", "Not used"),
                form.get("PercentageHighOfDay"),
                form.get("PercentageHighOfDay1"),
            )

        if high_condition is not None:
            conditions_status['HighOfDay'] = high_condition
            condition = condition and high_condition
            counting_ += 1

        # -------------------------
        # HIGHEST HIGH (N days)
        # -------------------------
        highest_high_condition = None
        highest_high = data.get("highestHigh")

        if form.get("HighestHighBool") == "value":
            comp = form.get("ComparisonHighestHigh", "Not used")
            if comp != "Not used":
                highest_high_condition = evaluate(
                    data.get("close"),
                    comp,
                    highest_high,
                    None,
                )

        elif form.get("HighestHighBool") == "percentage":
            comp = form.get("ComparisonHighestHigh", "Not used")
            if comp == "near":
                try:
                    pct = float(form.get("PercentageHighestHigh", 0))
                    if highest_high is None or data.get("close") is None:
                        highest_high_condition = False
                    else:
                        low_limit = float(highest_high) * (1.0 - pct / 100.0)
                        highest_high_condition = (
                            float(data.get("close")) >= low_limit
                            and float(data.get("close")) <= float(highest_high)
                        )
                except (TypeError, ValueError):
                    highest_high_condition = False
            elif comp != "Not used":
                highest_high_condition = percent_cond(
                    data.get("close"),
                    comp,
                    highest_high,
                    form.get("PercentageHighestHigh"),
                    form.get("PercentageHighestHigh1"),
                )

        if highest_high_condition is not None:
            conditions_status['HighestHigh'] = highest_high_condition
            condition = condition and highest_high_condition
            counting_ += 1

        # -------------------------
        # SMA CROSSOVER (Previous close vs SMA, Current price vs SMA)
        # -------------------------
        sma_crossover_condition = None
        smaperiod = form.get("SMACrossoverPeriod", "50")
        comp = form.get("ComparisonSMACrossover", "Not used")
        sma_key = "sma50" if smaperiod == "50" else "sma200"
        sma_value = data.get(sma_key)
        prev_close = data.get("prevClose")
        current_close = data.get("close")

        if comp != "Not used":
            if sma_value is None or prev_close is None or current_close is None:
                sma_crossover_condition = False
            else:
                if comp == "crossAbove":
                    sma_crossover_condition = (prev_close < sma_value and current_close > sma_value)
                elif comp == "crossBelow":
                    sma_crossover_condition = (prev_close > sma_value and current_close < sma_value)
                else:
                    sma_crossover_condition = False

        if sma_crossover_condition is not None:
            conditions_status['SMACrossover'] = sma_crossover_condition
            condition = condition and sma_crossover_condition
            counting_ += 1

        # -------------------------
        # PULLBACK
        # -------------------------
        pullback_condition = None

        if form.get("PullbackBool") == "percentage":
            pb_value = data.get("pullback")
            try:
                target = float(form.get("PercentagePullback", 0)) / 100.0
                target1 = float(form.get("PercentagePullback1")) / 100.0 if form.get("PercentagePullback1") else None
            except (TypeError, ValueError):
                pb_value = None
                target = None
                target1 = None

            if pb_value is not None:
                pullback_condition = evaluate(pb_value, form.get("ComparisonPullback", "Not used"), target, target1)

        elif form.get("PullbackBool") == "value":
            pullback_condition = absolute_cond(
                data.get("pullback"),
                form.get("ComparisonPullback", "Not used"),
                form.get("PercentagePullback"),
                form.get("PercentagePullback1"),
            )

        if pullback_condition is not None:
            conditions_status['Pullback'] = pullback_condition
            condition = condition and pullback_condition
            counting_ += 1

        # -------------------------
        # PIVOT POINT
        # -------------------------
        pivot_condition = None

        pivot = None
        pivot1 = None
        if isinstance(data.get("Pivot"), dict) and data.get("Pivot"):
            pivot = next(iter(data["Pivot"].values()), None)
        if isinstance(data.get("Pivot1"), dict) and data.get("Pivot1"):
            pivot1 = next(iter(data["Pivot1"].values()), None)

        if form.get("pivotPointBool") == "percentage":
            close_value = data.get("close")
            pivot_condition = percent_cond(
                close_value,
                form.get("ComparisonPivotPoint", "Not used"),
                pivot,
                form.get("PercentagePivotPoint"),
                form.get("PercentagePivotPoint1"),
            )

        elif form.get("pivotPointBool") == "value":
            pivot_condition = absolute_cond(
                pivot,
                form.get("ComparisonPivotPoint", "Not used"),
                form.get("PercentagePivotPoint"),
                form.get("PercentagePivotPoint1"),
            )

        if pivot_condition is not None:
            conditions_status['PivotPoint'] = pivot_condition
            condition = condition and pivot_condition
            counting_ += 1

        # -------------------------
        # RELATIVE VOLUME
        # -------------------------

        # -------------------------
        # RELATIVE VOLUME
        # -------------------------
        relative_volume_condition = None

        if form["ComparisonRelativeVolume"] not in ("Not used", "between"):
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

        if relative_volume_condition is not None:
            conditions_status['RelativeVolume'] = relative_volume_condition
            condition = condition and relative_volume_condition
            counting_ += 1

        # -------------------------
        # FINAL
        # -------------------------
        if counting_ == 0:
            condition = False

        data["signal"] = "yes" if condition else "no"
        data["conditions_status"] = conditions_status  # Include individual condition statuses for UI highlighting

        # tag scanner name on every row when provided
        scanner_name = None
        if isinstance(form, dict):
            scanner_name = form.get("ScannerName") or form.get("scanner_name")
        if scanner_name is not None and scanner_name != "":
            data["scanner_name"] = str(scanner_name)

        if self.config.scale_volume_metrics:
            # create copy for Flask so internal logic stays untouched
            flask_data = data.copy()
            if scanner_name is not None and scanner_name != "":
                flask_data["scanner_name"] = str(scanner_name)

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

            def _lookup_contract():
                """Single contract lookup attempt with timeout polling."""
                self.data[theid] = []
                self.requestInformation[theid] = False

                if contract_id is not None:
                    try:
                        self.findContractDetails(theid, i, "CUSIP", m, contract_id=contract_id)
                    except TypeError:
                        self.findContractDetails(theid, i, "CUSIP", m)
                else:
                    self.findContractDetails(theid, i, "CUSIP", m)

                waited = 0.0
                while self.requestInformation.get(theid) is False and waited < self.config.contract_lookup_timeout_sec:
                    time.sleep(self.config.contract_lookup_poll_sec)
                    waited += self.config.contract_lookup_poll_sec

                contracts_list = self.data.get(theid, []) or []
                selected_contract = self._select_best_contract(contracts_list, requested_symbol=m)

                if selected_contract is None:
                    raise Exception(
                        f"Contract lookup attempt {self._resilience['retry_executor'].attempt_count + 1} failed for {m} (CUSIP={i})"
                    )

                return selected_contract

            try:
                selected = self._resilience['retry_executor'].execute(_lookup_contract)
                resolved_cusip = selected.get("cusip")
            except Exception as e:
                error_msg = (
                    f"Contract lookup failed for {m} (CUSIP={i}) after "
                    f"{self.config.contract_lookup_max_attempts} attempts: {e}"
                )
                self.warningTicker[theid] = [m, i, error_msg]
                self._failure_tracker.mark_failed(m, error_msg, i)
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
                exchange = selected.get("exchange", "SMART")
                primary_exchange = selected.get("primaryExchange", "")
                currency = selected.get("currency", "USD")

                contract = self.marketContract(
                    symbol_for_contract,
                    sec_type,
                    exchange,
                    primary_exchange,
                    currency,
                )
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

        # small delay for safety (preserve original timing behavior)
        time.sleep(0.1)

        # -------------------------
        # Request historical data
        # -------------------------
        try:
            self.getData(contract, form, theid)
        except Exception as e:
            # If requesting historical data fails, track failure and exit
            error_msg = f"Failed to request historical data: {e}"
            self.warningTicker[theid] = [m, i, error_msg]
            self._failure_tracker.mark_failed(m, error_msg, i)
            try:
                self.numberOfTicker -= 1
            except Exception:
                pass
            # cleanup
            self.data.pop(theid, None)
            self.HistoricalDt.pop(theid, None)
            return

        # -------------------------
        # Wait for historical data with retry logic
        # -------------------------
        self.initial += 1
        
        # Use resilience-enabled fetcher for timeout/retry
        history = self._data_fetcher.fetch_with_retry(
            theid,
            contract,
            timeout_sec=self.config.history_lookup_timeout_sec,
            retry_count=2  # Allow 1 retry on timeout
        )
        
        # Validate row count - track partial failures
        min_rows = self.maxlength or 20
        is_valid, validation_error = self._data_fetcher.validate_rowcount(
            history, min_rows, m, i
        )
        
        if not is_valid:
            # Log but CONTINUE processing with partial data (resilience over strictness)
            logger.warning(f"[PARTIAL DATA] {m} ({i}): {validation_error}")
            self._failure_tracker.mark_failed(m, validation_error, i)

            # Skip this symbol if no bars were received
            if len(history) == 0:
                self.warningTicker[theid] = [m, i, validation_error]
                try:
                    self.numberOfTicker -= 1
                except Exception:
                    pass
                self.data.pop(theid, None)
                self.HistoricalDt.pop(theid, None)
                return

            try:
                # Get market data with normalized % change if available
                market_data = self._market_data.get(theid) if hasattr(self, '_market_data') else None
                indic = self.getIndicators(
                    history,
                    i,
                    contract,
                    form,
                    net_position.get(i, 0),
                    m,
                    market_data=market_data,
                )
                indic["cusip"] = resolved_cusip
                _ = self.buySellSignalCheck(indic, form)
            except Exception as e:
                # Protect the thread: capture indicator/signal exceptions and log to warningTicker
                self.warningTicker[theid] = [m, i, f"Indicator/signal error: {e}"]
        else:
            self._failure_tracker.mark_succeeded(m)
            # not enough rows -> register a warning if not already present
            if theid not in self.warningTicker:
                rows = len(history)
                if self.hisdtId.get(theid, False):
                    self.warningTicker[theid] = [
                        self.data.get(theid, [{}])[0].get("symbol", m) if self.data.get(theid) else m,
                        i,
                        f"Security number of rows {rows}. Please request less rows",
                    ]
                else:
                    self.warningTicker[theid] = [
                        self.data.get(theid, [{}])[0].get("symbol", m) if self.data.get(theid) else m,
                        i,
                        f"Security number of rows {rows}. Unable to download all data",
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

    # -------------------------------------------------------------------------
    # NEW: Fresh data & cache management methods
    # -------------------------------------------------------------------------
    @staticmethod
    def is_market_hours(use_utc=False):
        """
        Check if current time is during US market hours (9:30 AM - 4:00 PM ET).
        During market hours, disable contract caching for fresh data.
        
        Args:
            use_utc: If True, use UTC time; else use local time
        
        Returns:
            bool: True if currently in market hours, False otherwise
        """
        import datetime
        
        if use_utc:
            now = datetime.datetime.utcnow()
            # UTC offset for ET: -5 (EST) or -4 (EDT)
            # For simplicity, use offset rule: Mar-Nov is EDT (-4), else EST (-5)
            month = now.month
            offset = -4 if 3 <= month <= 10 else -5
            market_time = now + datetime.timedelta(hours=offset)
        else:
            market_time = datetime.datetime.now()
        
        weekday = market_time.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        hour = market_time.hour
        minute = market_time.minute
        
        # Market is closed on weekends
        if weekday >= 5:
            return False
        
        # Market hours: 9:30 AM to 4:00 PM (16:00)
        # Convert to minutes for easier comparison
        current_minutes = hour * 60 + minute
        market_open = 9 * 60 + 30  # 9:30 AM
        market_close = 16 * 60  # 4:00 PM
        
        return market_open <= current_minutes < market_close

    def clear_contract_cache(self, force=False):
        """
        Clear the contract cache to force fresh lookups.
        
        If force=True, clear immediately.
        If force=False, only clear during market hours.
        
        Args:
            force: If True, clear regardless of market hours
        """
        should_clear = force or self.is_market_hours()
        
        if should_clear:
            old_size = len(self.contract_cache)
            self.contract_cache.clear()
            logger.info(
                "[FRESH DATA] Contract cache cleared (was %d entries, market_hours=%s, force=%s)",
                old_size,
                self.is_market_hours(),
                force
            )
            return True
        else:
            logger.debug(
                "[CACHE] Contract cache NOT cleared (outside market hours)"
            )
            return False

    def reset_scan_state(self):
        """
        Reset all scan-related state for a fresh iteration.
        Called at the beginning of each background scan cycle.
        
        This ensures:
        - No reuse of previous response objects
        - Fresh data containers
        - Clean request/response tracking
        """
        import time as time_module
        scan_id = time_module.time()
        scan_timestamp = time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime(scan_id))
        
        logger.info(
            "[SCAN CYCLE START] ts=%s | Resetting all request/response state for fresh data fetch",
            scan_timestamp
        )
        
        # Clear all request/response containers to prevent stale data reuse
        try:
            # Clear historical data containers
            self.HistoricalDt.clear()
            self.hisdtId.clear()
            
            # Clear request tracking
            self.requestInformation.clear()
            self.data.clear()
            
            # Clear results from previous iteration
            self.sendToFlaskIB.clear()
            self.warningTicker.clear()
            
            # Clear market data
            with self._market_lock:
                self._market_data.clear()
                self._market_expected = 0
            
            # Clear error tracking
            self.errorSymbol.clear()
            self.priceMarketData.clear()
            
            # Reset per-ticker counters (but preserve global state)
            self.initial = 0
            self.numberOfTicker = 0
            self.customSymbol = 0
            
            logger.info(
                "[SCAN CYCLE START] ts=%s | State reset complete. Ready for fresh API calls.",
                scan_timestamp
            )
            
            return scan_timestamp
        except Exception as e:
            logger.error(
                "[SCAN CYCLE START] Failed to reset scan state: %s",
                e,
                exc_info=True
            )
            return scan_timestamp

    def getFinalResult(self, data, form):
        """
        Entry point for running the screening logic for all symbols.

        Spawns worker threads which call getDataResult().
        """
        
        # ---- CRITICAL: Ensure fresh data on each call ----
        scan_timestamp = self.reset_scan_state()
        
        # ---- IMPORTANT: Disable contract cache during market hours ----
        # During market hours, clear cache to force fresh CUSIP/contract lookups
        self.clear_contract_cache(force=False)
        
        logger.info(
            "[%s] getFinalResult called | %d symbols, form keys: %s",
            scan_timestamp,
            len(data.get("ticker", [])),
            list(form.keys()) if form else "none"
        )

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

        for cusip, conId, m in zip(self.cusip, self.conIds, mainTickers):

            time.sleep(6 / 50)

            self.numberOfTicker += 1
            self.numberSequence += 1

            theidd = self.numberSequence
            self.HistoricalDt[theidd] = []

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

        # Log partial failure summary for this scan cycle
        if hasattr(self, '_failure_tracker'):
            self._failure_tracker.log_summary()

    @staticmethod
    def bracketOrder(
            parent_order_id: int,
            action: str,
            quantity: float,
            limit_price: float,
            take_profit_limit_price: float | None,
            stop_loss_price: float | None,
    ):
        """
        Create a standard IB bracket order:
        - parent order
        - optional take-profit order
        - optional stop-loss order
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
            takeProfit.transmit = False

            bracketOrder.append(takeProfit)

        if stop_loss_price is not None:
            stopLoss = Order()
            stopLoss.eTradeOnly = False
            stopLoss.firmQuoteOnly = False
            stopLoss.orderId = parent.orderId + 2
            stopLoss.action = "SELL" if action == "BUY" else "BUY"
            stopLoss.orderType = "STP"
            stopLoss.auxPrice = stop_loss_price
            stopLoss.totalQuantity = quantity
            stopLoss.parentId = parent_order_id
            stopLoss.transmit = True

            bracketOrder.append(stopLoss)

        return bracketOrder

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
            conId = data["conId"] if data else None
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
