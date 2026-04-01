import time
import json
import math
import random
import logging
import threading
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
        # News related containers
        # ---------------------------
        # reqId -> list of headline dicts
        self._news_data = {}
        # reqId -> bool (historicalNewsEnd received)
        self._news_done = {}
        self._news_lock = threading.Lock()

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

    # ------------------------------------------------------------------
    # News callbacks
    # ------------------------------------------------------------------

    def historicalNews(self, request_id, time_str, provider_code, article_id, headline):
        """
        Callback for each historical news headline received from IBKR.
        """
        with self._news_lock:
            if request_id not in self._news_data:
                self._news_data[request_id] = []
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
        self._news_done[request_id] = True

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

        # Unblock the contract-details waiting loop in getDataResult().
        # When IB rejects a contract lookup (e.g. error 200 "No security
        # definition") the contractDetailsEnd callback never fires, so
        # requestInformation stays False and the thread idles for the full
        # timeout.  Signal completion here so it can proceed immediately.
        if req_id in self.requestInformation and not self.requestInformation[req_id]:
            self.requestInformation[req_id] = True

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

    @staticmethod
    def getIndicators(data, cusip, contract, form, net_position, symbol):
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
            result_full["ts"] = result_full["ts"].fillna(method="ffill").fillna(method="bfill")

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
            # use last `_lookback` days available (exclude current incomplete session if it is partial)
            days = daily_volume.copy()
            # if latest_date is today and session may be partial, exclude it for 'average daily volume'
            if len(days) > 1:
                days_to_use = days.iloc[-(min(len(days) - 1, _lookback)): -0] if len(days) > 1 else days
                # but above slicing can be empty; fallback:
                if days_to_use.empty:
                    days_to_use = days.iloc[-_lookback:]
            else:
                days_to_use = days.iloc[-_lookback:]
            if days_to_use.empty:
                return float(np.nan)
            return float(days_to_use.mean())

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

            indicators["averageVolume"] = avg_vol

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
                indicators["averageVolume1"] = avg_vol1

        # --- Relative volume ---
        if form.get("ComparisonRelativeVolume") != "Not used":
            try:
                rv_lookback = int(form.get("RelativeVolume", 5))
            except Exception:
                rv_lookback = 5

            # Definition: relativeVolume = today's cumulative volume / average daily volume (last N days)
            avg_daily = _avg_daily_volume(rv_lookback)
            if avg_daily and not np.isnan(avg_daily) and avg_daily > 0:
                rel_vol = today_cum_volume / avg_daily if not np.isnan(today_cum_volume) else float(np.nan)
            else:
                # fallback: last bar vs average bar volume
                avg_bar = float(result_full["volume"].iloc[-rv_lookback:].mean()) if result_full.shape[
                                                                                         0] >= 1 else float(np.nan)
                rel_vol = last_bar_volume / avg_bar if avg_bar and avg_bar > 0 else float(np.nan)

            indicators["relativeVolume"] = rel_vol

            if form.get("ComparisonRelativeVolume") == "between":
                try:
                    rv_lookback1 = int(form.get("RelativeVolume1", rv_lookback))
                except Exception:
                    rv_lookback1 = rv_lookback
                avg_daily1 = _avg_daily_volume(rv_lookback1)
                if avg_daily1 and not np.isnan(avg_daily1) and avg_daily1 > 0:
                    # we compare today's cum volume to avg_daily1
                    rel_vol1 = today_cum_volume / avg_daily1 if not np.isnan(today_cum_volume) else float(np.nan)
                else:
                    avg_bar1 = float(result_full["volume"].iloc[-rv_lookback1:].mean()) if result_full.shape[
                                                                                               0] >= 1 else float(
                        np.nan)
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

        # --- Previous Close (explicit) ---
        if form.get("ComparisonPrevClose", "Not used") != "Not used":
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

                if form.get("ComparisonPivotPoint") == "between":
                    pp_name1 = form.get("PivotPoint1", pp_name)
                    val1 = pivots.get(pp_name1, P)
                    indicators["Pivot1"] = {pp_name1: val1}
            except Exception:
                indicators["Pivot"] = {}
                indicators["Pivot1"] = {}

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
                    if curr_sma50 != 0:
                        indicators["cross50SMA_pctFromSMA"] = ((curr_close - curr_sma50) / curr_sma50) * 100.0
                    else:
                        indicators["cross50SMA_pctFromSMA"] = None
                else:
                    indicators["cross50SMA_above"] = False
                    indicators["cross50SMA_below"] = False
                    indicators["cross50SMA_either"] = False
                    indicators["cross50SMA_value"] = None
                    indicators["cross50SMA_pctFromSMA"] = None
            except Exception:
                indicators["cross50SMA_above"] = False
                indicators["cross50SMA_below"] = False
                indicators["cross50SMA_either"] = False
                indicators["cross50SMA_value"] = None
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
                    if curr_sma != 0:
                        indicators["cross200SMA_pctFromSMA"] = ((curr_close - curr_sma) / curr_sma) * 100.0
                    else:
                        indicators["cross200SMA_pctFromSMA"] = None
                else:
                    indicators["cross200SMA_above"] = False
                    indicators["cross200SMA_below"] = False
                    indicators["cross200SMA_either"] = False
                    indicators["cross200SMA_value"] = None
                    indicators["cross200SMA_pctFromSMA"] = None
            except Exception:
                indicators["cross200SMA_above"] = False
                indicators["cross200SMA_below"] = False
                indicators["cross200SMA_either"] = False
                indicators["cross200SMA_value"] = None
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

        # --- final housekeeping ---
        # ensure volume metadata
        try:
            indicators["volume"] = float(result_session["volume"].iloc[-1]) if not result_session.empty else float(
                result_full["volume"].iloc[-1])
        except Exception:
            indicators["volume"] = None

        return indicators

    def buySellSignalCheck(self, data, form):
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

        if cross_50_condition is not None:
            condition = condition and cross_50_condition
            counting_ += 1
            variable_results["cross50SMA"] = bool(cross_50_condition)

        # -------------------------
        # CROSS 200 SMA
        # -------------------------
        cross_200_condition = None

        cross200_mode = form.get("ComparisonCross200SMA", "Not used")
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
        # NEWS (within X minutes/hours)
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
        # FINAL
        # -------------------------
        if counting_ == 0:
            condition = False

        data["signal"] = "yes" if condition else "no"
        data["variableResults"] = variable_results
        data["passCount"] = sum(1 for v in variable_results.values() if v)
        data["totalCount"] = counting_

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

        max_headlines = 5
        try:
            max_headlines = int(form.get("NewsMaxHeadlines", 5))
        except Exception:
            pass
        if max_headlines < 1:
            max_headlines = 5

        # Parse excluded publishers from comma-separated string
        exclude_raw = form.get("NewsExcludePublishers", "")
        excluded_publishers = set()
        if exclude_raw:
            excluded_publishers = {
                p.strip().lower() for p in str(exclude_raw).split(",") if p.strip()
            }

        # Prepare the news request
        self._news_data[news_req_id] = []
        self._news_done[news_req_id] = False

        # IBKR reqHistoricalNews:
        #   reqId, conId, providerCodes, startDateTime, endDateTime, totalResults, historicalNewsOptions
        # providerCodes: "BZ+FLY+DJ+MT+GS" (or empty for all)
        # Date format: "YYYYMMDD-HH:MM:SS" or "" for open-ended
        end_dt = ""  # now
        start_dt = ""  # open-ended (let maxResults limit it)

        try:
            self.reqHistoricalNews(
                news_req_id,
                con_id,
                "",  # all providers
                start_dt,
                end_dt,
                max_headlines + 20,  # over-request to allow for filtering
                [],
            )
        except Exception as e:
            logger.warning("reqHistoricalNews failed for conId %s: %s", con_id, e)
            return []

        # Wait for news (bounded)
        waited = 0.0
        timeout = 10.0  # seconds
        while not self._news_done.get(news_req_id, False):
            time.sleep(0.1)
            waited += 0.1
            if waited >= timeout:
                break

        raw_headlines = self._news_data.get(news_req_id, [])

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

        # Limit to max requested
        deduped = deduped[:max_headlines]

        # Parse times and build clean output
        result = []
        for h in deduped:
            time_str = h.get("time", "")
            article_id = h.get("articleId", "")
            provider = h.get("provider", "")
            headline = h.get("headline", "")

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

            result.append({
                "time": time_str,
                "parsedTime": parsed_time.isoformat() if parsed_time else time_str,
                "provider": provider,
                "articleId": article_id,
                "headline": headline,
            })

        # Cleanup
        self._news_data.pop(news_req_id, None)
        self._news_done.pop(news_req_id, None)

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

                # request details from IB
                self.findContractDetails(theid, i, "CUSIP", m, contract_id=contract_id)

                waited = 0.0
                while self.requestInformation.get(theid) is False:
                    time.sleep(self.config.contract_lookup_poll_sec)
                    waited += self.config.contract_lookup_poll_sec

                    if waited >= self.config.contract_lookup_timeout_sec:
                        break

                contracts_list = self.data.get(theid, []) or []

                selected = self._select_best_contract(
                    contracts_list,
                    requested_symbol=m
                )

                if selected is not None:
                    resolved_cusip = selected.get("cusip")
                    break

            # --------------------------------------------------
            # Fallback: if CUSIP-based lookup failed and we have
            # a valid symbol, try a plain symbol-only lookup.
            # This covers cases where the CUSIP is stale/wrong
            # but the ticker symbol itself resolves fine.
            # --------------------------------------------------
            if selected is None and m and m != "nan" and not str(m).lower().startswith("custom"):
                logger.info(
                    "CUSIP lookup failed for %s (cusip=%s). Trying symbol-only fallback.",
                    m, i,
                )
                # one extra attempt with symbol only (no CUSIP, no conId)
                self.data[theid] = []
                self.requestInformation[theid] = False

                self.findContractDetails(theid, None, None, m, contract_id=None)

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
            # Use the cusip passed into getDataResult as fallback when cache hit
            # skips contract resolution (which is where resolved_cusip is normally set)
            resolved_cusip = i

        # small delay for safety (preserve original timing behavior)
        time.sleep(0.1)

        # -------------------------
        # Request historical data
        # -------------------------
        try:
            self.getData(contract, form, theid)
        except Exception:
            # If requesting historical data fails, warn and exit gracefully
            self.warningTicker[theid] = [m, i, "Failed to request historical data"]
            try:
                self.numberOfTicker -= 1
            except Exception:
                pass
            # cleanup
            self.data.pop(theid, None)
            self.HistoricalDt.pop(theid, None)
            return

        # -------------------------
        # Wait for historical data to finish (bounded)
        # -------------------------
        self.initial += 1
        waited = 0.0

        while not self.hisdtId.get(theid, False):
            time.sleep(self.config.history_lookup_poll_sec)
            waited += self.config.history_lookup_poll_sec
            if waited >= self.config.history_lookup_timeout_sec:
                # timeout: warn and continue to attempt processing with whatever we have
                self.warningTicker[theid] = [
                    m,
                    i,
                    "Historical data download timeout",
                ]
                break

        # Ensure historical data exists
        history = self.HistoricalDt.get(theid, []) or []

        # Process any symbol that returned at least 1 bar of data.
        # Individual indicators handle insufficient lookback gracefully
        # (return None), and buySellSignalCheck treats None as False via
        # _safe_compare.  The old rigid gate (len >= maxlength) rejected
        # many valid symbols whose IB history was simply shorter than the
        # longest configured lookback window.
        if len(history) >= 1:
            try:
                indic = self.getIndicators(
                    history,
                    i,
                    contract,
                    form,
                    net_position.get(i, 0),
                    m,
                )
                indic["cusip"] = resolved_cusip

                # -------------------------
                # Fetch news headlines if enabled
                # -------------------------
                if form.get("ComparisonNews", "Not used") != "Not used":
                    con_id = getattr(contract, "conId", None)
                    if con_id:
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
                if self.hisdtId.get(theid, False):
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
