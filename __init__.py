import re
import os
import gc
import sys
import csv
import time
import json
import socket
import random
import logging
import threading
import traceback
import urllib.parse
from pathlib import Path
from config import Config
from waitress import serve
from io import TextIOWrapper
from datetime import datetime, UTC
from forms import Parameters, SecondSubmit
from flask import Flask, render_template, request, jsonify

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

cfg = Config()
cfg.setups_dir.mkdir(exist_ok=True)
cfg.watchlists_dir.mkdir(exist_ok=True)
cfg.order_presets_dir.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# IBKR port auto-detection (live / paper) using config values + preference
# -----------------------------------------------------------------------------

def detect_ibkr_port_from_config(host="127.0.0.1", timeout=1.0):
    """
    Try preferred IBKR environment first (from config).
    If it is not reachable, automatically try the other one and warn.
    Returns selected port or None.
    """

    preferred = (cfg.ibkr_preferred_env or "").upper()

    ports_map = {
        "LIVE": cfg.ibkr_live_port,
        "PAPER": cfg.ibkr_paper_port,
    }

    if preferred not in ports_map:
        logger.error(
            "Invalid ibkr_preferred_env value: %s (must be 'LIVE' or 'PAPER')",
            preferred,
        )
        return None

    # build ordered list: preferred first, then the other
    ordered = [preferred] + [k for k in ports_map.keys() if k != preferred]

    for idx, env in enumerate(ordered):
        port = ports_map.get(env)
        if not port:
            continue

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)

        try:
            s.connect((host, int(port)))
            s.close()

            if idx == 0:
                logger.info(
                    "IBKR %s environment detected on port %s (preferred)",
                    env,
                    port,
                )
            else:
                logger.warning(
                    "Preferred IBKR environment '%s' is not available. "
                    "Falling back to '%s' on port %s.",
                    preferred,
                    env,
                    port,
                )

            return int(port)

        except Exception:
            try:
                s.close()
            except Exception:
                pass

    return None


# Perform initial port check at startup
_detected_port = detect_ibkr_port_from_config()

if _detected_port is None:
    logger.error(
        "IBKR API is not reachable on either configured environment "
        "(preferred=%s). Exiting.",
        cfg.ibkr_preferred_env,
    )
    sys.exit(1)

# Override configured runtime port with detected one
cfg.ibkr_api_port = _detected_port
logger.info("Using IBKR API port: %s", cfg.ibkr_api_port)


# -----------------------------------------------------------------------------
# App factory + module-level app
# -----------------------------------------------------------------------------
def create_app(config_object=Config) -> Flask:
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_object)
    flask_app.config["SECRET_KEY"] = cfg.flask_secret_key
    return flask_app


app = create_app()

# Register held orders API routes
try:
    from held_orders_api import register_held_orders_routes
    register_held_orders_routes(app)
    logger.info("Held orders API routes registered")
except Exception as e:
    logger.warning(f"Failed to register held orders routes: {e}")


# -----------------------------------------------------------------------------
def safe_last_two_dates(folder: str):
    """
    Return the last two entries from the folder sorted by name.
    If the folder doesn't exist or has fewer entries, return what's available (or []).
    """
    try:
        p = Path(folder)
        if not p.exists() or not p.is_dir():
            return []
        items = sorted([x.name for x in p.iterdir() if x.is_file() or x.is_dir()])
        return items[-2:]
    except Exception:
        logger.exception("Failed to list folder %s", folder)
        return []


def apply_result_filters(results_list: list, form: dict) -> list:
    """
    Filter scan results based on enabled filter checkboxes.
    
    Only returns stocks that meet ALL checked filter criteria.
    If no filters are enabled, returns all results unchanged.
    
    Args:
        results_list: List of stock result dicts from sendToFlaskIB
        form: Form data dict with filter checkbox states
    
    Returns:
        Filtered list of stock results
    """
    from ibkr_signal_engine import apply_result_filters as backend_filter
    
    # If no results, return empty
    if not results_list:
        return []
    
    # Check if any filter is enabled
    filter_keys = [
        'filterVWAP', 'filterFastSMA', 'filterMediumSMA', 'filterSlowSMA',
        'filterRSI', 'filterFastEMA', 'filterSlowEMA', 'filterOBV', 'filterFastOBV', 'filterMediumOBV', 'filterSlowOBV', 'filterATR',
        'filterAverageVolume', 'filterRelativeVolume', 'filterPrevClose',
        'filterLowOfDay', 'filterHighOfDay', 'filterCross50SMA', 'filterCross200SMA',
        'filterBreakHigh', 'filterPullbackPct', 'filterPullbackPct2',
        'filterFibPullback', 'filterGapPullback', 'filterPivotPoint',
        'filterUpGap', 'filterDownGap', 'filterNewsKeyword', 'filterMarketCap',
        'filterVolume'
    ]
    
    any_enabled = any(form.get(k, False) for k in filter_keys)
    
    # If no filters enabled, return all results
    if not any_enabled:
        return results_list
    
    # Filter results: keep only stocks that pass all enabled filters
    filtered = []
    for stock_data in results_list:
        if backend_filter(stock_data, form):
            filtered.append(stock_data)
    
    return filtered


def run_gc():
    if cfg.cache_garbage_collection:
        gc.collect()
    else:
        pass


# -----------------------------------------------------------------------------
# Routes & helpers
# -----------------------------------------------------------------------------
@app.route("/")
@app.route("/morfeo", methods=["GET", "POST"])
def morfeo():
    last_updated_pdf = safe_last_two_dates("dates")
    param = Parameters()

    cfg_dict = {
        "bg_results_poll_ms": cfg.scanner_poll_interval
    }

    return render_template("morfeo.html", Param=param, pdffolder=last_updated_pdf, cfg_dict=cfg_dict)


@app.route("/micelania", methods=["GET", "POST"])
def micelania():
    ssubmit = SecondSubmit()
    return render_template("micelanias.html", ssubimit=ssubmit)


@app.route("/exclude-stocks", methods=["GET"])
def exclude_stocks_page():
    """Render the exclude stocks management page."""
    return render_template("exclude_stocks.html")

@app.route("/updatepdf", methods=["GET", "POST"])
def updatepdf():
    # import when used
    from micelanias import getPdf

    tio = getPdf()
    tio.chekAllFiles()

    logger.info("updatepdf called: %s", request.form)
    return {"result": "Updated PDF"}


def convertCSV(csv_file):
    # Symbol, Name, Last Sale, Net Change, % Change, Market Cap, Country, IPO Year, Volume, Sector, Industry
    mdta = []
    mcusip = []
    mticker = []
    indextouse = None
    for h, i in enumerate(csv_file):
        if h == 0:
            for hh, jj in enumerate(i):
                if jj == "Symbol":
                    indextouse = hh
            continue
        if indextouse is not None:
            dta = {"cusip": "custom" + str(h), "ticker": str(i[indextouse]).upper(), "change": 0}
            mcusip.append("custom" + str(h))
            mticker.append(i[indextouse])
        else:
            dta = {"cusip": i[1], "ticker": i[0], "change": 0}
            mcusip.append(i[1])
            mticker.append(i[0])
        mdta.append(dta)
    logger.debug("Parsed CSV -> %s", mdta)
    myresult = {"CSV": mdta, "cusip": mcusip, "ticker": mticker}
    return myresult


def convertDict(myfile):
    """
    Convert form-data (URL-encoded string inside 'data') into a dict.
    Use urllib.parse.unquote_plus to decode percent-encodings.
    """
    try:
        raw = myfile.to_dict().get("data", "")
        theform = raw.split("&") if raw else []
    except Exception:
        logger.exception("convertDict: invalid form input")
        return {}

    thedict = {}
    for i in theform:
        elements = i.split("=", 1)
        if len(elements) < 2:
            continue
        key = elements[0]
        # decode percent-encoding (spaces + pluses handled)
        value = urllib.parse.unquote_plus(elements[1])
        thedict[key] = value
    return thedict


def convertCustomForm(myfile):
    """
    Convert posted JSON custom form structure into the expected dict shape.
    Now also supports optional conId.
    """
    myform = {}

    for i in myfile.get("forms", []):
        myform[i["name"]] = i["value"]

    ticker = []
    cusip = []
    conIds = []   # NEW
    mdta = []

    for h, i in enumerate(myfile.get("tickers", {}).get("securities", [])):
        thecus = i["cusip"] if i.get("cusip") else "custom" + str(h)
        theConId = i.get("conId") if i.get("conId") not in (None, "", "None") else None

        mdta.append({

            "cusip": thecus,
            "ticker": i["ticker"],
            "conId": theConId,   # NEW
            "change": 0

        })

        ticker.append(str(i["ticker"]).upper())
        cusip.append(thecus)
        conIds.append(theConId)   # NEW

    mydict = {
        "CUSTOM": mdta,
        "cusip": cusip,
        "ticker": ticker,
        "conId": conIds   # NEW
    }

    getReturn = {
        "form": myform,
        "securities": mydict
    }

    return getReturn


def _sanitize_name(name: str) -> str:
    """Return safe filename-friendly name (limit length)."""
    if not name:
        name = "untitled"
    # keep only safe chars, replace spaces with underscores
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
    safe = re.sub(r"\s+", "_", safe)
    return safe[:64]


def _setup_path(name: str) -> Path:
    return cfg.setups_dir / (name + ".json")


def list_setups():
    out = []
    for p in sorted(cfg.setups_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix == ".json":
            try:
                with p.open("r", encoding="utf-8") as fh:
                    meta = json.load(fh).get("meta", {})
            except Exception:
                meta = {}
            out.append({
                "name": p.stem,
                "filename": p.name,
                "created": meta.get("created_at") or datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "title": meta.get("title") or p.stem
            })
    return out


@app.route("/something", methods=["GET", "POST"])
def something():
    """
    Main screening endpoint.
    Behaviour preserved:
    - builds IBapi instance
    - connects and starts IBAPI.run() in a thread
    - depending on POST data or uploaded CSV, runs the screening and returns results
    """
    starttime = time.time()
    from micelanias import ComparePdf, dataProcessing
    from ibkr_signal_engine import IBapi

    IBAPI = IBapi()
    IBAPI.connect("127.0.0.1", cfg.ibkr_api_port, random.randint(1, 99))
    # compatibility with earlier code:
    try:
        IBAPI.nextOrderId = None
    except Exception:
        pass

    def run_loop():
        IBAPI.run()

    api_thread = threading.Thread(target=run_loop, daemon=True)
    api_thread.start()

    sendToHtml = {}

    # Branch A: form (no file / no JSON)
    if len(request.files.to_dict()) == 0 and request.json is None:
        myform = request.form.to_dict()
        if myform.get("Procesetf") == "processonebyone":
            rootdir = "dates"
            if not os.path.exists(rootdir):
                sendToHtml["CSV"] = {"Custom Tickers": list()}
                return
            casa = ComparePdf(rootdir)
            casa.getFolders()
            testing = list(casa.fileDirectory.keys())
            IBAPI.addFrequency = myform.get("addFrequency")
            for etfDict in testing:
                IBAPI.sendToFlaskIB = {}
                try:
                    myresult = casa.IntersectionDifferece(etfDict)
                    etf__ = etfDict.split(".")[0]
                    IBAPI.getFinalResult(myresult, myform)
                    # Apply filters to results
                    filtered_results = apply_result_filters(list(IBAPI.sendToFlaskIB.copy().values()), myform)
                    sendToHtml[etf__] = {etfDict: filtered_results}
                    time.sleep(5)
                except Exception as e:
                    logger.exception(f"Error processing ETF {etfDict}: {e}")
        else:
            IBAPI.addFrequency = myform.get("addFrequency")
            myresult = dataProcessing()
            IBAPI.getFinalResult(myresult, myform)
            # Apply filters to results
            filtered_results = apply_result_filters(list(IBAPI.sendToFlaskIB.copy().values()), myform)
            sendToHtml["All ETF tickers"] = {"All ETF tickers": filtered_results}

    # Branch B: CSV file posted
    elif len(request.files) == 1:
        myform = convertDict(request.form)
        IBAPI.addFrequency = myform.get("addFrequency")

        uploaded_file = request.files.get("csvfile")

        if not uploaded_file or uploaded_file.filename == "":
            return "", 400

        text_stream = TextIOWrapper(uploaded_file.stream, encoding="utf-8")

        reader = csv.reader(text_stream, delimiter=",")

        myresult = convertCSV(reader)

        IBAPI.getFinalResult(myresult, myform)
        # Apply filters to results
        filtered_results = apply_result_filters(list(IBAPI.sendToFlaskIB.copy().values()), myform)
        sendToHtml["CSV"] = {"Custom Tickers": filtered_results}

    # Branch C: JSON posted with custom instruments
    elif request.json is not None:
        processingData = convertCustomForm(request.json)
        myform = processingData["form"]
        IBAPI.addFrequency = myform.get("addFrequency")
        myresult = processingData["securities"]
        IBAPI.getFinalResult(myresult, myform)
        # Apply filters to results
        filtered_results = apply_result_filters(list(IBAPI.sendToFlaskIB.copy().values()), myform)
        sendToHtml["CSV"] = {"Custom Tickers": filtered_results}
        time.sleep(5)

    try:
        IBAPI.disconnect()
    except Exception:
        logger.exception("Error during IBAPI.disconnect()")

    run_gc()
    logger.info(f"Response: {sendToHtml}")

    logger.info("Total time to do all operations (Seconds): %s", time.time() - starttime)
    return {"result": sendToHtml, "warning": getattr(IBAPI, "warningTicker", {})}


@app.route("/sendorders", methods=["POST", "GET"])
def sendorders():
    from ibkr_signal_engine import IBapi
    import json

    IBAPI = None

    response = {
        "status": "error",
        "ordersId": None,
        "sentOrders": [],
        "message": None,
        "Connection": None,
    }

    try:
        asset = request.form.to_dict()

        logger.info(
            "sendorders payload: %s  data: %s",
            asset,
            request.data,
        )

        orders_id = int(time.time())
        response["ordersId"] = orders_id

        # Check if this is a multi-level order request
        is_multi_level = asset.get("isMultiLevel", "false") == "true"
        
        # ===== STEP 1: Connect to IBKR =====
        client_id = random.randint(300, 399)
        IBAPI = IBapi()
        IBAPI.connect("127.0.0.1", cfg.ibkr_api_port, client_id)

        # Start event loop IMMEDIATELY so callbacks can fire
        api_thread = threading.Thread(target=IBAPI.run, daemon=True)
        api_thread.start()

        # Wait for IB to confirm the connection (nextValidId callback)
        IBAPI.checkForConnection()

        if getattr(IBAPI, "indicateNotCondition", False):
            response["Connection"] = "There was not connection with Interactive Brokers. Please try again"
            response["message"] = response["Connection"]
            return response

        # Get ticker and common parameters
        ticker_order = asset["tickerOrder"]
        longshort = asset["longshort"]
        action = "BUY" if longshort == "long" else "SELL"
        tif = asset.get("tif", "DAY")
        outside_rth = asset.get("outsideRth", "regular")
        allow_outside_rth = outside_rth in ("extended", "overnight")

        # ------------------------------------------------------------
        # Resolve contract via symbol lookup
        # ------------------------------------------------------------
        req_id = IBAPI.initialSec
        IBAPI.data[req_id] = []
        IBAPI.requestInformation[req_id] = False

        IBAPI.findContractDetails(
            req_id,
            "nan",
            "CUSIP",
            ticker_order,
        )

        # Poll for contract details with timeout instead of blind sleep
        waited = 0.0
        timeout = cfg.contract_lookup_timeout_sec
        poll_interval = cfg.contract_lookup_poll_sec
        while not IBAPI.requestInformation.get(req_id, False):
            time.sleep(poll_interval)
            waited += poll_interval
            if waited >= timeout:
                break

        if not IBAPI.data.get(req_id):
            raise RuntimeError(
                f"No contract details returned from IB for '{ticker_order}'. "
                "Check that the symbol is valid and TWS/Gateway is running."
            )

        # Pick the best contract (prefer SMART exchange)
        best = IBAPI._select_best_contract(IBAPI.data[req_id], ticker_order)
        if best is None:
            best = IBAPI.data[req_id][0]

        contract = IBAPI.marketContract(
            best["symbol"],
            "STK",
            "SMART",
            best.get("primaryExchange") or "",
            best["currency"],
        )

        IBAPI.reqMarketDataType(4)

        # ===== MULTI-LEVEL ORDER HANDLING =====
        if is_multi_level:
            try:
                from order_manager import PriceReferenceResolver, PriceReference
                
                # Parse multi-level order configuration
                multi_level_json = asset.get("multiLevelConfig", "{}")
                multi_level_config = json.loads(multi_level_json)
                
                # Build price indicator values from available data
                # These would normally come from real-time market data
                indicator_values = {
                    'vwap': getattr(IBAPI, 'vwap', 0) or 0,
                    'sma_fast': getattr(IBAPI, 'fast_sma', 0) or 0,
                    'sma_medium': getattr(IBAPI, 'medium_sma', 0) or 0,
                    'sma_slow': getattr(IBAPI, 'slow_sma', 0) or 0,
                    'ema_fast': getattr(IBAPI, 'fast_ema', 0) or 0,
                    'ema_slow': getattr(IBAPI, 'slow_ema', 0) or 0,
                    'rsi': getattr(IBAPI, 'rsi', 50) or 50,
                    'atr': getattr(IBAPI, 'atr', 0) or 0,
                    'prev_close': getattr(IBAPI, 'lastPrice', 0) or 0,
                    'current_price': getattr(IBAPI, 'lastPrice', 0) or 0,
                    'day_high': getattr(IBAPI, 'day_high', 0) or 0,
                    'day_low': getattr(IBAPI, 'day_low', 0) or 0,
                }
                
                # Get current price as backup for missing indicators
                current_price = getattr(IBAPI, 'lastPrice', None)
                if current_price and current_price > 0:
                    # Fill in missing indicators with current price as default
                    for key in indicator_values:
                        if indicator_values[key] <= 0:
                            indicator_values[key] = current_price
                
                resolver = PriceReferenceResolver(indicator_values)
                
                # Process levels and resolve price references
                # Important: Each level in the config becomes ONE entry order with MULTIPLE exit orders
                levels_for_ib = []
                
                for level_idx, level_config in enumerate(multi_level_config.get('levels', [])):
                    level_qty = level_config.get('quantity', 100)
                    
                    # Resolve entry price
                    entry_ref = level_config.get('entry', {})
                    entry_price_ref = PriceReference(**entry_ref)
                    entry_price = resolver.resolve(entry_price_ref)
                    
                    if entry_price is None or entry_price <= 0:
                        raise ValueError(f"Level {level_idx+1}: Could not resolve entry price for {entry_ref.get('type', 'unknown')}")
                    
                    entry_type = entry_ref.get('order_type', 'limit').upper()
                    if entry_type == 'LIMIT':
                        entry_type = 'LMT'
                    elif entry_type == 'MARKET':
                        entry_type = 'MKT'
                    
                    # Resolve stop loss price
                    stop_price = None
                    stop_loss_ref = level_config.get('stop_loss')
                    if stop_loss_ref:
                        stop_loss_price_ref = PriceReference(**stop_loss_ref)
                        stop_price = resolver.resolve(stop_loss_price_ref)
                        
                        if stop_price is None or stop_price <= 0:
                            logger.warning(f"Level {level_idx+1}: Could not resolve stop price, ignoring")
                            stop_price = None
                    
                    # Collect ALL sell targets for this level
                    sell_targets_data = level_config.get('sell_targets', [])
                    if not sell_targets_data:
                        # If no sell targets, create a default one at +1%
                        sell_targets_data = [{
                            'type': 'percent_target',
                            'offset_pct': 1.0,
                            'order_type': 'limit',
                            'percent_of_position': 100.0,
                        }]
                    
                    # Resolve all target prices
                    resolved_targets = []
                    total_position_pct = 0
                    
                    for target_config in sell_targets_data:
                        # Resolve sell target price
                        target_price_ref = PriceReference(**target_config)
                        target_price = resolver.resolve(target_price_ref)
                        
                        if target_price is None or target_price <= 0:
                            logger.warning(f"Level {level_idx+1}: Could not resolve target price for {target_config.get('type')}, skipping")
                            continue
                        
                        pct_of_position = target_config.get('percent_of_position', 100.0)
                        total_position_pct += pct_of_position
                        
                        resolved_targets.append({
                            'price': target_price,
                            'percent_of_position': pct_of_position,
                            'order_type': target_config.get('order_type', 'limit'),
                            'trailing_amount': target_config.get('trailing_amount'),
                            'trailing_type': target_config.get('trailing_type', 'amount'),
                        })
                    
                    if not resolved_targets:
                        raise ValueError(f"Level {level_idx+1}: No valid sell targets could be resolved")
                    
                    # Normalize position percentages if they don't add up to 100%
                    if total_position_pct != 100.0 and total_position_pct > 0:
                        for target in resolved_targets:
                            target['percent_of_position'] = (target['percent_of_position'] / total_position_pct) * 100.0
                    
                    # Create ONE level entry with ALL the exit targets attached
                    level_for_ib = {
                        'quantity': level_qty,
                        'entry_price': round(entry_price, 2),
                        'entry_type': entry_type,
                        'exit_prices': resolved_targets,  # NEW: List of exit targets
                        'stop_price': round(stop_price, 2) if stop_price else None,
                    }
                    
                    levels_for_ib.append(level_for_ib)
                    
                    logger.info(f"Level {level_idx+1}: Entry @{level_for_ib['entry_price']} ({level_qty} shares) → "
                              f"{len(resolved_targets)} exit targets, Stop @{level_for_ib['stop_price']}")
                
                # Build order specification
                order_spec = {
                    'action': action,
                    'tif': tif,
                    'outside_rth': allow_outside_rth,
                    'start_order_id': orders_id,
                    'levels': levels_for_ib
                }
                
                logger.info(f"Multi-level order spec prepared: {len(levels_for_ib)} levels")
                
                # Create multi-level orders
                orders = IBAPI.multiLevelOrderAdvanced(order_spec)
                
            except Exception as e:
                logger.exception("Error processing multi-level orders")
                raise RuntimeError(f"Invalid multi-level order configuration: {str(e)}")
        
        # ===== STANDARD SINGLE-LEVEL ORDER HANDLING =====
        else:
            limit_price = asset["limitPrice"]
            bracket_limit = asset["bracketlimit"]
            high_bracket = asset["highBraket"]
            low_bracket = asset["lowBraket"]
            quantity = int(asset["quantity"])
            use_trailing_stop = asset.get("useTrailingStop", "off") == "on"
            trailing_amount = asset.get("trailingAmount", "")
            trailing_type = asset.get("trailingType", "amount")  # "amount" or "percent"
            entry_type = asset.get("entryType", "limit")  # "limit" or "market"
            hold_off_market = asset.get("holdOffMarket", "off") == "on"

            if hold_off_market and entry_type == "market":
                entry_type = "limit"

            # Build orders
            trailing_amt = None
            if use_trailing_stop and trailing_amount:
                trailing_amt = round(float(trailing_amount), 2)

            if entry_type == "market":
                # Market order — no limit price, optional bracket legs
                from ibapi.order import Order as IBOrder
                orders = []
                parent = IBOrder()
                parent.eTradeOnly = False
                parent.firmQuoteOnly = False
                parent.orderId = orders_id
                parent.action = action
                parent.orderType = "MKT"
                parent.totalQuantity = quantity
                parent.tif = tif
                parent.outsideRth = allow_outside_rth
                parent.transmit = True
                orders.append(parent)

            elif bracket_limit == "bracket":

                price_to_use = round(float(limit_price), 2) if limit_price != "" else None
                bracket_high = round(float(high_bracket), 2) if high_bracket != "" else None
                bracket_low = round(float(low_bracket), 2) if low_bracket != "" else None

                orders = IBAPI.bracketOrder(
                    orders_id,
                    action,
                    quantity,
                    price_to_use,
                    bracket_high,
                    bracket_low,
                    tif=tif,
                    outside_rth=allow_outside_rth,
                    use_trailing_stop=use_trailing_stop,
                    trailing_amount=trailing_amt,
                    trailing_percent=(trailing_type == "percent"),
                )

            else:
                price_to_use = round(float(limit_price), 2)

                orders = IBAPI.bracketOrder(
                    orders_id,
                    action,
                    quantity,
                    price_to_use,
                    None,
                    None,
                    tif=tif,
                    outside_rth=allow_outside_rth,
                )

        # ------------------------------------------------------------
        # Send orders
        # ------------------------------------------------------------
        for o in orders:
            IBAPI.placeOrder(o.orderId, contract, o)

            response["sentOrders"].append(
                {
                    "orderId": o.orderId,
                    "action": o.action,
                    "orderType": o.orderType,
                    "quantity": o.totalQuantity,
                    "limitPrice": getattr(o, "lmtPrice", None),
                    "auxPrice": getattr(o, "auxPrice", None),
                }
            )

        time.sleep(5)

        IBAPI.initialSec += 1

        response["status"] = "ok"
        response["message"] = "Orders submitted to IBKR"

    except Exception as e:
        logger.exception("Error in sendorders")

        response["status"] = "error"
        response["message"] = str(e)
        response["Connection"] = str(e)

    finally:
        if IBAPI is not None:
            try:
                IBAPI.disconnect()
            except Exception:
                pass

    run_gc()
    return response


# =============================================================================
# Order Preset Management Routes
# =============================================================================

@app.route("/order-presets/save", methods=["POST"])
def save_order_preset():
    """Save a multi-level order preset."""
    from order_manager import MultiLevelOrder, OrderPresetManager
    
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'symbol' not in data or 'levels' not in data:
            return {"status": "error", "message": "Missing required fields"}, 400
        
        # Create MultiLevelOrder from request data
        order = MultiLevelOrder(
            name=data['name'],
            symbol=data['symbol'],
            levels=data['levels'],  # This should be pre-serialized as dicts
            strategy_notes=data.get('strategy_notes', '')
        )
        
        # Save the preset
        manager = OrderPresetManager(cfg.order_presets_dir)
        filepath = manager.save_preset(order)
        
        return {
            "status": "ok",
            "message": f"Preset saved: {filepath.name}",
            "filename": filepath.name
        }
    
    except Exception as e:
        logger.exception("Error saving order preset")
        return {"status": "error", "message": str(e)}, 500


@app.route("/order-presets/list", methods=["GET"])
def list_order_presets():
    """List all available order presets, optionally filtered by symbol."""
    from order_manager import OrderPresetManager
    
    try:
        symbol = request.args.get('symbol', None)
        manager = OrderPresetManager(cfg.order_presets_dir)
        presets = manager.list_presets(symbol=symbol)
        
        return {
            "status": "ok",
            "presets": presets,
            "count": len(presets)
        }
    
    except Exception as e:
        logger.exception("Error listing order presets")
        return {"status": "error", "message": str(e)}, 500


@app.route("/order-presets/load/<filename>", methods=["GET"])
def load_order_preset(filename):
    """Load a specific order preset."""
    from order_manager import OrderPresetManager
    
    try:
        filepath = cfg.order_presets_dir / filename
        
        if not filepath.exists():
            return {"status": "error", "message": "Preset not found"}, 404
        
        manager = OrderPresetManager(cfg.order_presets_dir)
        order = manager.load_preset(filepath)
        
        return {
            "status": "ok",
            "preset": order.to_dict()
        }
    
    except Exception as e:
        logger.exception("Error loading order preset")
        return {"status": "error", "message": str(e)}, 500


@app.route("/order-presets/delete/<filename>", methods=["DELETE"])
def delete_order_preset(filename):
    """Delete an order preset."""
    from order_manager import OrderPresetManager
    
    try:
        manager = OrderPresetManager(cfg.order_presets_dir)
        
        if manager.delete_preset(filename):
            return {"status": "ok", "message": f"Preset deleted: {filename}"}
        else:
            return {"status": "error", "message": "Preset not found"}, 404
    
    except Exception as e:
        logger.exception("Error deleting order preset")
        return {"status": "error", "message": str(e)}, 500


# =============================================================================
# Auto-Order Preset Management Routes
# =============================================================================

@app.route("/auto-order-presets/save", methods=["POST"])
def save_auto_order_preset():
    """Save an auto-order preset with its settings."""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'settings' not in data:
            return {"ok": False, "message": "Missing required fields (name, settings)"}, 400
        
        name = data['name']
        settings = data['settings']
        is_default = data.get('isDefault', False)
        overwrite = data.get('overwrite', False)
        
        # Ensure 'ao_' prefix for namespace
        if not name.startswith('ao_'):
            name = 'ao_' + name
        
        # Create presets directory if needed
        cfg.order_presets_dir.mkdir(exist_ok=True)
        
        preset_file = cfg.order_presets_dir / (name + '.json')
        
        # Check if file exists and overwrite not allowed
        if preset_file.exists() and not overwrite:
            return {"ok": False, "message": "Preset already exists"}, 409
        
        # Prepare the full preset document
        preset_doc = {
            "meta": {
                "name": name,
                "isDefault": is_default,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            },
            "settings": settings
        }
        
        # Write to file
        with open(preset_file, 'w', encoding='utf-8') as f:
            json.dump(preset_doc, f, indent=2)
        
        logger.info(f"Auto-order preset saved: {preset_file}")
        
        return {"ok": True, "message": f"Preset saved: {name}", "name": name}
    
    except Exception as e:
        logger.exception("Error saving auto-order preset")
        return {"ok": False, "message": str(e)}, 500


@app.route("/auto-order-presets/load", methods=["POST"])
def load_auto_order_preset():
    """Load an auto-order preset by name."""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return {"ok": False, "message": "Missing preset name"}, 400
        
        name = data['name']
        
        # Ensure 'ao_' prefix
        if not name.startswith('ao_'):
            name = 'ao_' + name
        
        preset_file = cfg.order_presets_dir / (name + '.json')
        
        if not preset_file.exists():
            return {"ok": False, "message": "Preset not found"}, 404
        
        # Read the file
        with open(preset_file, 'r', encoding='utf-8') as f:
            preset_doc = json.load(f)
        
        logger.info(f"Auto-order preset loaded: {preset_file}")
        
        return preset_doc
    
    except Exception as e:
        logger.exception("Error loading auto-order preset")
        return {"ok": False, "message": str(e)}, 500


@app.route("/auto-order-presets/delete", methods=["POST"])
def delete_auto_order_preset():
    """Delete an auto-order preset by name."""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return {"ok": False, "message": "Missing preset name"}, 400
        
        name = data['name']
        
        # Ensure 'ao_' prefix
        if not name.startswith('ao_'):
            name = 'ao_' + name
        
        preset_file = cfg.order_presets_dir / (name + '.json')
        
        if not preset_file.exists():
            return {"ok": False, "message": "Preset not found"}, 404
        
        # Delete the file
        preset_file.unlink()
        
        logger.info(f"Auto-order preset deleted: {preset_file}")
        
        return {"ok": True, "message": f"Preset deleted: {name}"}
    
    except Exception as e:
        logger.exception("Error deleting auto-order preset")
        return {"ok": False, "message": str(e)}, 500


@app.route("/auto-order-presets/list", methods=["GET"])
def list_auto_order_presets():
    """List all available auto-order presets."""
    try:
        cfg.order_presets_dir.mkdir(exist_ok=True)
        
        presets = []
        for preset_file in cfg.order_presets_dir.glob('ao_*.json'):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    preset_doc = json.load(f)
                
                meta = preset_doc.get('meta', {})
                presets.append({
                    'name': meta.get('name', preset_file.stem),
                    'filename': preset_file.name,
                    'isDefault': meta.get('isDefault', False),
                    'created_at': meta.get('created_at'),
                    'updated_at': meta.get('updated_at'),
                })
            except Exception as e:
                logger.warning(f"Error reading preset file {preset_file}: {e}")
                continue
        
        logger.info(f"Listed {len(presets)} auto-order presets")
        
        return {"ok": True, "presets": presets, "count": len(presets)}
    
    except Exception as e:
        logger.exception("Error listing auto-order presets")
        return {"ok": False, "message": str(e)}, 500


@app.route("/upload-csv", methods=["POST"])
def upload_csv():
    logger.info("upload_csv files count: %s", len(request.files))

    if "csvfile" not in request.files:
        return "", 400

    uploaded_file = request.files["csvfile"]

    if uploaded_file.filename == "":
        return "", 400

    # wrap the binary stream
    text_stream = TextIOWrapper(uploaded_file.stream, encoding="utf-8")

    reader = csv.reader(text_stream, delimiter=";")

    convertCSV(reader)

    return "", 201


# -----------------------
# Routes: list, save, load
# -----------------------
@app.route("/setups/list", methods=["GET"])
def setups_list():
    try:
        return jsonify({"setups": list_setups()}), 200
    except Exception as e:
        logger.exception("Failed to list setups: %s", e)
        return jsonify({"error": "failed to list setups"}), 500


@app.route("/setups/save", methods=["POST"])
def setups_save():
    """
    Expects JSON:
    {
      "name": "My Setup",
      "overwrite": true|false,  # optional
      "form": { ... },          # same shape used by getFinalResult()
      "securities": { ... }     # optional, can be built from DOM on the client
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400

        name = payload.get("name", "").strip()
        overwrite = bool(payload.get("overwrite", False))
        form = payload.get("form")
        securities = payload.get("securities")

        if not name:
            return jsonify({"error": "name is required"}), 400
        if not isinstance(form, dict):
            return jsonify({"error": "form object required"}), 400

        safe = _sanitize_name(name)
        p = _setup_path(safe)
        if p.exists() and not overwrite:
            return jsonify({"error": "setup already exists", "exists": True}), 409

        doc = {
            "meta": {
                "title": name,
                "created_at": datetime.now(UTC).isoformat(),
            },
            "form": form,
            "securities": securities or {}
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

        logger.info("Saved setup: %s -> %s", name, p)
        return jsonify({"ok": True, "name": safe}), 200

    except Exception as e:
        logger.exception("Failed to save setup: %s", e)
        return jsonify({"error": "failed to save setup"}), 500


@app.route("/setups/load", methods=["POST"])
def setups_load():
    """
    Expects JSON:
    { "name": "<sanitized-name-or-filename>" }
    Returns:
    { "meta": {...}, "form": {...}, "securities": {...} }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        name = payload.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400

        safe = _sanitize_name(name)
        p = _setup_path(safe)
        if not p.exists():
            # allow passing filename with .json
            alt = cfg.setups_dir / name
            if alt.exists():
                p = alt
            else:
                return jsonify({"error": "not found"}), 404

        with p.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)

        return jsonify(doc), 200

    except Exception as e:
        logger.exception("Failed to load setup: %s", e)
        return jsonify({"error": "failed to load setup"}), 500


# -----------------------
# Routes: watchlists (stock lists)
# -----------------------
def _watchlist_path(name: str) -> Path:
    return cfg.watchlists_dir / (_sanitize_name(name) + ".json")


def list_watchlists():
    out = []
    for p in sorted(cfg.watchlists_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix == ".json":
            try:
                with p.open("r", encoding="utf-8") as fh:
                    doc = json.load(fh)
                    meta = doc.get("meta", {})
                    count = len(doc.get("tickers", []))
            except Exception:
                meta = {}
                count = 0
            out.append({
                "name": p.stem,
                "filename": p.name,
                "created": meta.get("created_at") or datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "title": meta.get("title") or p.stem,
                "count": count
            })
    return out


@app.route("/watchlists/list", methods=["GET"])
def watchlists_list():
    try:
        return jsonify({"watchlists": list_watchlists()}), 200
    except Exception as e:
        logger.exception("Failed to list watchlists: %s", e)
        return jsonify({"error": "failed to list watchlists"}), 500


@app.route("/watchlists/save", methods=["POST"])
def watchlists_save():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400

        name = payload.get("name", "").strip()
        overwrite = bool(payload.get("overwrite", False))
        tickers = payload.get("tickers", [])

        if not name:
            return jsonify({"error": "name is required"}), 400
        if not isinstance(tickers, list) or len(tickers) == 0:
            return jsonify({"error": "tickers list is required"}), 400

        safe = _sanitize_name(name)
        p = _watchlist_path(safe)
        if p.exists() and not overwrite:
            return jsonify({"error": "watchlist already exists", "exists": True}), 409

        doc = {
            "meta": {
                "title": name,
                "created_at": datetime.now(UTC).isoformat(),
            },
            "tickers": tickers
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

        logger.info("Saved watchlist: %s -> %s (%d tickers)", name, p, len(tickers))
        return jsonify({"ok": True, "name": safe}), 200

    except Exception as e:
        logger.exception("Failed to save watchlist: %s", e)
        return jsonify({"error": "failed to save watchlist"}), 500


@app.route("/watchlists/load", methods=["POST"])
def watchlists_load():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        name = payload.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400

        safe = _sanitize_name(name)
        p = _watchlist_path(safe)
        if not p.exists():
            alt = cfg.watchlists_dir / name
            if alt.exists():
                p = alt
            else:
                return jsonify({"error": "not found"}), 404

        with p.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)

        return jsonify(doc), 200

    except Exception as e:
        logger.exception("Failed to load watchlist: %s", e)
        return jsonify({"error": "failed to load watchlist"}), 500


@app.route("/watchlists/delete", methods=["POST"])
def watchlists_delete():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        name = payload.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400

        safe = _sanitize_name(name)
        p = _watchlist_path(safe)
        if not p.exists():
            return jsonify({"error": "not found"}), 404

        p.unlink()
        logger.info("Deleted watchlist: %s", safe)
        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.exception("Failed to delete watchlist: %s", e)
        return jsonify({"error": "failed to delete watchlist"}), 500


# -------------------------------------------------------------------------
# Stock Exclusion List Management
# -------------------------------------------------------------------------

def _get_excluded_api():
    try:
        from ibkr_signal_engine import IBapi
        return IBapi()
    except Exception:
        logger.exception("Failed to import IBapi for exclusion list")
        raise


@app.route("/exclude/list", methods=["GET"])
def exclude_list():
    """Get the list of excluded stocks."""
    try:
        IBAPI = _get_excluded_api()
        excluded = IBAPI.get_excluded_stocks()
        return jsonify({
            "ok": True,
            "excluded": sorted(list(excluded)),
            "count": len(excluded)
        }), 200
    except Exception as e:
        logger.exception("Failed to get excluded stocks list: %s", e)
        return jsonify({"error": "failed to get list"}), 500


@app.route("/exclude/add", methods=["POST"])
def exclude_add():
    """Add one or more stock symbols to the exclusion list."""
    try:
        IBAPI = _get_excluded_api()
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400

        symbols = []
        if "symbols" in payload:
            raw = payload.get("symbols")
            if isinstance(raw, str):
                symbols = [s.strip().upper() for s in re.split(r"[\s,]+", raw) if s.strip()]
            elif isinstance(raw, (list, tuple, set)):
                symbols = [str(s).strip().upper() for s in raw if str(s).strip()]
            else:
                return jsonify({"error": "invalid symbols format"}), 400
        elif "symbol" in payload:
            raw = payload.get("symbol", "")
            symbols = [s.strip().upper() for s in re.split(r"[\s,]+", str(raw)) if s.strip()]
        else:
            return jsonify({"error": "symbol required"}), 400

        if not symbols:
            return jsonify({"error": "symbol required"}), 400

        failed = []
        for symbol in symbols:
            if not IBAPI.add_excluded_stock(symbol):
                failed.append(symbol)

        excluded = IBAPI.get_excluded_stocks()
        if failed:
            return jsonify({
                "ok": False,
                "error": f"failed to save: {', '.join(failed)}",
                "excluded": sorted(list(excluded)),
                "count": len(excluded)
            }), 500

        return jsonify({
            "ok": True,
            "message": f"Added {len(symbols)} symbol(s) to exclusion list",
            "excluded": sorted(list(excluded)),
            "count": len(excluded)
        }), 200
    except Exception as e:
        logger.exception("Failed to add excluded stock: %s", e)
        return jsonify({"error": "failed to add stock"}), 500


@app.route("/exclude/remove", methods=["POST"])
def exclude_remove():
    """Remove a stock symbol from the exclusion list."""
    try:
        IBAPI = _get_excluded_api()
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        
        symbol = payload.get("symbol", "").strip().upper()
        if not symbol:
            return jsonify({"error": "symbol required"}), 400
        
        success = IBAPI.remove_excluded_stock(symbol)
        if success:
            excluded = IBAPI.get_excluded_stocks()
            return jsonify({
                "ok": True,
                "message": f"Removed {symbol} from exclusion list",
                "excluded": sorted(list(excluded)),
                "count": len(excluded)
            }), 200
        else:
            return jsonify({"error": "failed to save"}), 500
    except Exception as e:
        logger.exception("Failed to remove excluded stock: %s", e)
        return jsonify({"error": "failed to remove stock"}), 500


@app.route("/exclude/import-csv", methods=["POST"])
def exclude_import_csv():
    """Import excluded stocks from a CSV file."""
    try:
        IBAPI = _get_excluded_api()
        if "csvfile" not in request.files:
            return jsonify({"error": "csvfile required"}), 400
        
        file = request.files["csvfile"]
        if file.filename == "":
            return jsonify({"error": "empty file"}), 400
        
        # Read CSV and extract symbols
        from io import TextIOWrapper
        text_stream = TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.reader(text_stream, delimiter=",")
        
        symbols = []
        for i, row in enumerate(reader):
            if i == 0:  # Skip header if present
                if row and row[0].lower() in ["symbol", "ticker", "stock"]:
                    continue
            if row and row[0].strip():
                symbols.append(row[0].strip().upper())
        
        if not symbols:
            return jsonify({"error": "no symbols found in CSV"}), 400
        
        # Save to exclusion list
        success = IBAPI.save_excluded_stocks(symbols)
        if success:
            excluded = IBAPI.get_excluded_stocks()
            return jsonify({
                "ok": True,
                "message": f"Imported {len(symbols)} stocks to exclusion list",
                "excluded": sorted(list(excluded)),
                "count": len(excluded)
            }), 200
        else:
            return jsonify({"error": "failed to save"}), 500
    except Exception as e:
        logger.exception("Failed to import excluded stocks: %s", e)
        return jsonify({"error": "failed to import"}), 500


@app.route("/exclude/export-csv", methods=["GET"])
def exclude_export_csv():
    """Export excluded stocks as a CSV file."""
    try:
        IBAPI = _get_excluded_api()
        from io import StringIO
        from flask import send_file
        
        excluded = sorted(list(IBAPI.get_excluded_stocks()))
        
        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Symbol"])
        for symbol in excluded:
            writer.writerow([symbol])
        
        # Send as download
        output.seek(0)
        return send_file(
            StringIO(output.getvalue()),
            mimetype="text/csv",
            as_attachment=True,
            download_name="excluded_stocks.csv"
        )
    except Exception as e:
        logger.exception("Failed to export excluded stocks: %s", e)
        return jsonify({"error": "failed to export"}), 500


@app.route("/exclude/clear", methods=["POST"])
def exclude_clear():
    """Clear the entire exclusion list."""
    try:
        IBAPI = _get_excluded_api()
        success = IBAPI.save_excluded_stocks([])
        if success:
            return jsonify({
                "ok": True,
                "message": "Cleared exclusion list",
                "excluded": [],
                "count": 0
            }), 200
        else:
            return jsonify({"error": "failed to clear"}), 500
    except Exception as e:
        logger.exception("Failed to clear excluded stocks: %s", e)
        return jsonify({"error": "failed to clear"}), 500


# -------------------------------------------------------------------------
# Exclusion Lists - Named Presets (Save/Load/List)
# -------------------------------------------------------------------------

def _exclusion_list_path(name: str) -> Path:
    """Get path for a named exclusion list."""
    return cfg.watchlists_dir / ("exclude_" + _sanitize_name(name) + ".json")


def list_exclusion_lists():
    """List all saved exclusion lists."""
    out = []
    try:
        for p in sorted(cfg.watchlists_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file() and p.suffix == ".json" and p.stem.startswith("exclude_"):
                try:
                    with p.open("r", encoding="utf-8") as fh:
                        doc = json.load(fh)
                        meta = doc.get("meta", {})
                        count = len(doc.get("symbols", []))
                except Exception:
                    meta = {}
                    count = 0
                
                # Remove "exclude_" prefix for display
                display_name = p.stem[8:] if p.stem.startswith("exclude_") else p.stem
                out.append({
                    "name": display_name,
                    "filename": p.name,
                    "created": meta.get("created_at") or datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "title": meta.get("title") or display_name,
                    "count": count
                })
    except Exception:
        pass
    return out


@app.route("/exclude/lists", methods=["GET"])
def exclude_lists():
    """Get list of all saved exclusion lists."""
    try:
        lists = list_exclusion_lists()
        return jsonify({"ok": True, "lists": lists}), 200
    except Exception as e:
        logger.exception("Failed to list exclusion lists: %s", e)
        return jsonify({"error": "failed to list exclusion lists"}), 500


@app.route("/exclude/save", methods=["POST"])
def exclude_save():
    """
    Save the current exclusion list with a name.
    
    Expects JSON:
    {
        "name": "My Exclusion List",
        "symbols": ["AAPL", "MSFT"],
        "overwrite": true|false
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400

        name = payload.get("name", "").strip()
        overwrite = bool(payload.get("overwrite", False))
        symbols = payload.get("symbols", [])

        if not name:
            return jsonify({"error": "name is required"}), 400

        # If no symbols provided, get from current exclusion list
        if not symbols:
            IBAPI = _get_excluded_api()
            symbols = sorted(list(IBAPI.get_excluded_stocks()))
        
        if not isinstance(symbols, (list, tuple, set)):
            return jsonify({"error": "symbols must be a list"}), 400

        safe = _sanitize_name(name)
        p = _exclusion_list_path(safe)
        
        if p.exists() and not overwrite:
            return jsonify({"error": "exclusion list already exists", "exists": True}), 409

        doc = {
            "meta": {
                "title": name,
                "created_at": datetime.now(UTC).isoformat(),
            },
            "symbols": sorted([str(s).upper() for s in symbols if str(s).strip()])
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

        logger.info("Saved exclusion list: %s -> %s (%d symbols)", name, p, len(doc["symbols"]))
        return jsonify({
            "ok": True,
            "name": safe,
            "count": len(doc["symbols"])
        }), 200

    except Exception as e:
        logger.exception("Failed to save exclusion list: %s", e)
        return jsonify({"error": "failed to save exclusion list"}), 500


@app.route("/exclude/load/<list_name>", methods=["GET"])
def exclude_load(list_name: str):
    """Load a saved exclusion list by name."""
    try:
        safe = _sanitize_name(list_name.strip())
        p = _exclusion_list_path(safe)
        
        if not p.exists():
            # Try with the full filename
            alt = cfg.watchlists_dir / list_name
            if alt.exists() and alt.stem.startswith("exclude_"):
                p = alt
            else:
                return jsonify({"error": "exclusion list not found"}), 404

        with p.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)

        return jsonify({
            "ok": True,
            "name": p.stem[8:],  # Remove "exclude_" prefix
            "meta": doc.get("meta", {}),
            "symbols": doc.get("symbols", []),
            "count": len(doc.get("symbols", []))
        }), 200

    except Exception as e:
        logger.exception("Failed to load exclusion list: %s", e)
        return jsonify({"error": "failed to load exclusion list"}), 500


@app.route("/exclude/apply/<list_name>", methods=["POST"])
def exclude_apply(list_name: str):
    """Apply a saved exclusion list (load and set as current)."""
    try:
        IBAPI = _get_excluded_api()
        
        safe = _sanitize_name(list_name.strip())
        p = _exclusion_list_path(safe)
        
        if not p.exists():
            alt = cfg.watchlists_dir / list_name
            if alt.exists() and alt.stem.startswith("exclude_"):
                p = alt
            else:
                return jsonify({"error": "exclusion list not found"}), 404

        with p.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)
        
        symbols = doc.get("symbols", [])
        success = IBAPI.save_excluded_stocks(symbols)
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"Applied exclusion list: {list_name}",
                "excluded": sorted(list(IBAPI.get_excluded_stocks())),
                "count": len(symbols)
            }), 200
        else:
            return jsonify({"error": "failed to apply exclusion list"}), 500

    except Exception as e:
        logger.exception("Failed to apply exclusion list: %s", e)
        return jsonify({"error": "failed to apply exclusion list"}), 500


@app.route("/exclude/delete/<list_name>", methods=["DELETE", "POST"])
def exclude_delete(list_name: str):
    """Delete a saved exclusion list."""
    try:
        safe = _sanitize_name(list_name.strip())
        p = _exclusion_list_path(safe)
        
        if not p.exists():
            alt = cfg.watchlists_dir / list_name
            if alt.exists() and alt.stem.startswith("exclude_"):
                p = alt
            else:
                return jsonify({"error": "exclusion list not found"}), 404

        p.unlink()
        logger.info("Deleted exclusion list: %s", p)
        
        return jsonify({
            "ok": True,
            "message": f"Deleted exclusion list: {list_name}"
        }), 200

    except Exception as e:
        logger.exception("Failed to delete exclusion list: %s", e)
        return jsonify({"error": "failed to delete exclusion list"}), 500


# -------------------------------------------------------------------------
# Order Presets
# -------------------------------------------------------------------------

def _order_preset_path(name: str) -> Path:
    return cfg.order_presets_dir / (_sanitize_name(name) + ".json")


def list_order_presets():
    out = []
    if not cfg.order_presets_dir.exists():
        return out
    for p in sorted(cfg.order_presets_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix == ".json":
            try:
                with p.open("r", encoding="utf-8") as fh:
                    doc = json.load(fh)
                    meta = doc.get("meta", {})
            except Exception:
                meta = {}
            out.append({
                "name": p.stem,
                "title": meta.get("title") or p.stem,
                "isDefault": meta.get("isDefault", False),
            })
    return out


@app.route("/order-presets/list", methods=["GET"])
def order_presets_list():
    try:
        return jsonify({"presets": list_order_presets()}), 200
    except Exception as e:
        logger.exception("Failed to list order presets: %s", e)
        return jsonify({"error": "failed to list order presets"}), 500


@app.route("/order-presets/save", methods=["POST"])
def order_presets_save():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400

        name = payload.get("name", "").strip()
        overwrite = bool(payload.get("overwrite", False))
        settings = payload.get("settings", {})
        is_default = bool(payload.get("isDefault", False))

        if not name:
            return jsonify({"error": "name is required"}), 400

        safe = _sanitize_name(name)
        p = _order_preset_path(safe)
        if p.exists() and not overwrite:
            return jsonify({"error": "preset already exists", "exists": True}), 409

        # If setting as default, clear default flag from all others
        if is_default:
            for op in cfg.order_presets_dir.iterdir():
                if op.is_file() and op.suffix == ".json":
                    try:
                        with op.open("r", encoding="utf-8") as fh:
                            doc = json.load(fh)
                        if doc.get("meta", {}).get("isDefault"):
                            doc["meta"]["isDefault"] = False
                            with op.open("w", encoding="utf-8") as fh:
                                json.dump(doc, fh, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

        doc = {
            "meta": {
                "title": name,
                "created_at": datetime.now(UTC).isoformat(),
                "isDefault": is_default,
            },
            "settings": settings,
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

        logger.info("Saved order preset: %s -> %s", name, p)
        return jsonify({"ok": True, "name": safe}), 200

    except Exception as e:
        logger.exception("Failed to save order preset: %s", e)
        return jsonify({"error": "failed to save order preset"}), 500


@app.route("/order-presets/load", methods=["POST"])
def order_presets_load():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        name = payload.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400

        safe = _sanitize_name(name)
        p = _order_preset_path(safe)
        if not p.exists():
            return jsonify({"error": "not found"}), 404

        with p.open("r", encoding="utf-8") as fh:
            doc = json.load(fh)

        return jsonify(doc), 200

    except Exception as e:
        logger.exception("Failed to load order preset: %s", e)
        return jsonify({"error": "failed to load order preset"}), 500


@app.route("/order-presets/delete", methods=["POST"])
def order_presets_delete():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        name = payload.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400

        safe = _sanitize_name(name)
        p = _order_preset_path(safe)
        if not p.exists():
            return jsonify({"error": "not found"}), 404

        p.unlink()
        logger.info("Deleted order preset: %s", safe)
        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.exception("Failed to delete order preset: %s", e)
        return jsonify({"error": "failed to delete order preset"}), 500


# -------------------------------------------------------------------------
# Position Management - Track filled orders and manage exits
# -------------------------------------------------------------------------

@app.route("/positions/list", methods=["GET"])
def positions_list():
    """Get all open positions, summary, and account data"""
    try:
        from ibkr_signal_engine import IBapi
        # Create temporary IBAPI instance to access position manager and account data
        api = IBapi()
        summary = api.position_manager.get_all_positions()
        account_data = api.get_account_data()
        return jsonify({
            "positions": [p.to_dict() for p in summary],
            "summary": api.position_manager.get_positions_summary(),
            "account": account_data
        }), 200
    except Exception as e:
        logger.exception("Failed to list positions: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/account/summary", methods=["GET"])
def account_summary():
    """Get current account summary data"""
    try:
        from ibkr_signal_engine import IBapi
        api = IBapi()
        account_data = api.get_account_data()
        return jsonify(account_data), 200
    except Exception as e:
        logger.exception("Failed to get account summary: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/positions/add", methods=["POST"])
def positions_add():
    """Add a filled position to tracking (called when order fills)"""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        
        from position_manager import Position
        from ibkr_signal_engine import IBapi
        
        api = IBapi()
        pos = Position(
            symbol=payload['symbol'],
            entry_price=float(payload['entry_price']),
            quantity=int(payload['quantity']),
            entry_time=datetime.now(),
            order_id=int(payload['order_id']),
            side=payload.get('side', 'long')
        )
        
        api.position_manager.add_position(pos)
        return jsonify({"ok": True, "position": pos.to_dict()}), 200
    
    except Exception as e:
        logger.exception("Failed to add position: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/positions/update-price", methods=["POST"])
def positions_update_price():
    """Update current market price for a symbol"""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        
        from ibkr_signal_engine import IBapi
        api = IBapi()
        
        symbol = payload.get('symbol')
        current_price = float(payload.get('current_price'))
        
        api.position_manager.update_position_prices(symbol, current_price)
        return jsonify({"ok": True}), 200
    
    except Exception as e:
        logger.exception("Failed to update position price: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/positions/evaluate-exits", methods=["POST"])
def positions_evaluate_exits():
    """Evaluate exit conditions for a symbol"""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        
        from ibkr_signal_engine import IBapi
        api = IBapi()
        
        symbol = payload.get('symbol')
        market_data = payload.get('market_data', {})
        
        recommendations = api.position_manager.evaluate_exits(symbol, market_data)
        return jsonify({"exit_recommendations": recommendations}), 200
    
    except Exception as e:
        logger.exception("Failed to evaluate exits: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/positions/exit", methods=["POST"])
def positions_exit():
    """Execute partial or full position exit"""
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "JSON payload required"}), 400
        
        from ibkr_signal_engine import IBapi
        api = IBapi()
        
        symbol = payload['symbol']
        order_id = int(payload['order_id'])
        quantity = int(payload.get('quantity', 0))
        exit_price = float(payload['exit_price'])
        trigger = payload.get('trigger', 'manual')
        
        # If quantity is 0 or matches position size, do full exit
        if quantity == 0:
            success = api.position_manager.execute_full_exit(symbol, order_id, exit_price, trigger)
        else:
            success = api.position_manager.execute_partial_exit(symbol, order_id, quantity, exit_price, trigger)
        
        if success:
            return jsonify({"ok": True}), 200
        else:
            return jsonify({"error": "Failed to execute exit"}), 400
    
    except Exception as e:
        logger.exception("Failed to execute exit: %s", e)
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------------------------------
# News article detail endpoint
# -------------------------------------------------------------------------
@app.route("/news/article", methods=["GET"])
def news_article():
    """
    Fetch a full IBKR news article via the TWS API and return as JSON.

    Query params:
      provider  – IBKR provider code (e.g. "BZ", "DJ-N")
      articleId – IBKR article identifier (e.g. "BZ$12345")

    Returns JSON: {"articleType": 0|1, "articleText": "...", "provider": "...", "articleId": "..."}
    """
    from ibkr_signal_engine import IBapi
    import re as _re

    provider = request.args.get("provider", "").strip()
    article_id = request.args.get("articleId", "").strip()

    if not provider or not article_id:
        return jsonify({"error": "Missing provider or articleId parameter."}), 400

    # Basic input validation
    if len(provider) > 20 or len(article_id) > 200:
        return jsonify({"error": "Invalid parameters."}), 400

    ib = None
    try:
        ib = IBapi()
        ib.connect("127.0.0.1", cfg.ibkr_api_port, random.randint(100, 999))
        try:
            ib.nextOrderId = None
        except Exception:
            pass

        def run_loop():
            ib.run()

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()

        # Wait for connection
        waited = 0.0
        while not isinstance(ib.nextOrderId, int) and waited < 5.0:
            time.sleep(0.1)
            waited += 0.1

        result = ib.fetchNewsArticle(provider, article_id)

        if result and result.get("articleText"):
            article_type = result.get("articleType", 0)
            article_text = result["articleText"]

            if article_type == 1:
                # HTML article — sanitize script tags
                article_text = _re.sub(
                    r"<script[^>]*>.*?</script>",
                    "",
                    article_text,
                    flags=_re.IGNORECASE | _re.DOTALL,
                )

            return jsonify({
                "articleType": article_type,
                "articleText": article_text,
                "provider": provider,
                "articleId": article_id,
            })
        else:
            return jsonify({"error": "Article not available. This may be due to your news subscription level."}), 404

    except Exception as e:
        logger.exception("news_article endpoint error: %s", e)
        return jsonify({"error": "Error fetching article."}), 500
    finally:
        if ib:
            try:
                ib.disconnect()
            except Exception:
                pass


# -------------------------------------------------------------------------
# Bring IBKR TWS window to foreground
# -------------------------------------------------------------------------
@app.route("/focus-ibkr", methods=["POST"])
def focus_ibkr():
    """
    Bring the running IBKR Trader Workstation window to the foreground.
    Uses the Windows API to find and activate the TWS window.
    """
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32

    # Callback to enumerate windows and find TWS
    found_hwnd = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_callback(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            title_lower = title.lower()
            # Exclude editors/browsers that may contain "ibkr" in their title bar
            exclude_keywords = ("visual studio code", "vscode", "vs code", "code - ")
            if any(ex in title_lower for ex in exclude_keywords):
                return True
            # Match various IBKR window titles:
            # "Interactive Brokers", "Trader Workstation", "TWS", "IB Gateway"
            ib_keywords = ("interactive brokers", "trader workstation", "tws", "ib gateway", "ibkr")
            if any(kw in title_lower for kw in ib_keywords) and user32.IsWindowVisible(hwnd):
                found_hwnd.append(hwnd)
        return True

    user32.EnumWindows(enum_callback, 0)

    if found_hwnd:
        hwnd = found_hwnd[0]
        SW_RESTORE = 9
        SW_SHOW = 5
        # Restore if minimized
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        # Windows blocks SetForegroundWindow from background processes.
        # Workaround: simulate an Alt key press to satisfy the OS check,
        # then call SetForegroundWindow + BringWindowToTop.
        KEYEVENTF_EXTENDEDKEY = 0x0001
        KEYEVENTF_KEYUP = 0x0002
        VK_MENU = 0x12  # Alt key
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        user32.BringWindowToTop(hwnd)

        return jsonify({"status": "ok", "message": "IBKR TWS brought to foreground."})
    else:
        return jsonify({"status": "error", "message": "IBKR TWS window not found. Make sure TWS is running."}), 404


# -------------------------------------------------------------------------
# START OF ADDED BACKGROUND SCANNER CODE
#
# - BackgroundScanner class
# - /background/start  (POST)
# - /background/stop   (POST)
# - /background/status (GET)
# - /background/results (GET)
#
# This block only *adds* safe functionality and does not remove or alter
# any existing functions above. It was designed to be robust against bad
# input and concurrent start/stop attempts.
# -------------------------------------------------------------------------


class BackgroundScanner:
    """
    Manage a single background scanning loop.

    Usage:
      - call start(interval_seconds, form, securities) to start
      - call stop() to stop
      - status() / results() to inspect
    """

    def __init__(self):
        self.enabled = False
        self.interval_seconds = 60.0
        self.thread = None  # worker thread that runs _loop()
        self.lock = threading.Lock()
        self.is_running = False  # true while a single scan is in progress
        self.latest_results = {}  # latest sendToFlaskIB results
        self.previous_signals = {}  # previous signal states to detect new ones
        self.latest_warning = {}
        self._beep_pending = False  # set True each loop iteration when conditions met
        self.last_run_time = None
        self._stop_event = threading.Event()
        self._start_request_time = None

        # ---- lifecycle for a single persistent IB connection per scanner session ----
        self._ib = None  # IBapi instance (reused across iterations)
        self._ib_thread = None  # thread running self._ib.run()
        self._ib_client_id = None  # client id used for this _ib
        self._ib_lock = threading.Lock()  # protect _ib/_ib_thread lifecycle
        self._ib_connect_backoff = 0.0  # simple backoff counter for repeated connect failures

        # ---- client heartbeat / lease bookkeeping (new) ----
        # updated by results() when frontend polls /background/results
        self.last_client_seen = None

    @staticmethod
    def parse_interval(value, unit):
        """
        Convert value & unit to seconds.
        Accepts integer values. Returns None on invalid input.
        """
        try:
            v = int(value)
        except Exception:
            return None
        if v < 1:
            return None

        unit = (unit or "seconds").lower()
        if unit == "seconds":
            sec = v
        elif unit == "minutes":
            sec = v * 60
        elif unit == "hours":
            sec = v * 3600
        else:
            return None

        # enforce sensible caps to avoid too large intervals due to user error
        if sec < 1:
            sec = 1
        if sec > 7 * 24 * 3600:  # 1 week cap
            sec = 7 * 24 * 3600
        return sec

    # ---------------------------------------------------------------------
    # IB connection helpers: keep a single IB connection for the lifetime of
    # the background scanner session (start -> stop).  This prevents the
    # repeated connect/disconnect storms that cause "client id already in use".
    # ---------------------------------------------------------------------
    def _ensure_ib_connected(self):
        """
        Ensure self._ib is connected and running. If not, create and connect it.

        Returns True on success, False on failure. Sets self.latest_warning on error.
        """
        from ibkr_signal_engine import IBapi  # local import to avoid cycles
        # NOTE: cfg must be available globally in your app (as in your original code)
        global cfg

        with self._ib_lock:
            # If already connected and thread alive, assume it's usable
            if self._ib is not None and self._ib_thread is not None and self._ib_thread.is_alive():
                return True

            # Clean previous resources if any (disconnect, join thread)
            try:
                if self._ib is not None:
                    try:
                        # try a graceful disconnect
                        self._ib.disconnect()
                    except Exception:
                        logger.debug("ib.disconnect() raised during cleanup", exc_info=True)
                    self._ib = None
                if self._ib_thread is not None and self._ib_thread.is_alive():
                    # join but do not block long
                    self._ib_thread.join(timeout=1.5)
                    self._ib_thread = None
            except Exception:
                logger.exception("Error cleaning previous IB resources")

            # small pause to let TWS/Gateway clear connection state on its side
            if self._ib_connect_backoff < 1.5:
                # only short sleep if we're not in large backoff
                time.sleep(1.0)
            else:
                # if we've been failing repeatedly, apply slightly longer delay
                time.sleep(min(5.0, 1.0 + self._ib_connect_backoff))

            # create new IB instance and connect
            try:
                self._ib = IBapi()
                # pick a random-ish client id (large range to reduce collisions)
                self._ib_client_id = random.randint(2000, 99999)
                logger.debug("Connecting IB with client id %s", self._ib_client_id)
                self._ib.connect("127.0.0.1", cfg.ibkr_api_port, self._ib_client_id)

                # set non-daemon thread for cleaner shutdown / allow join()
                def run_loop():
                    try:
                        self._ib.run()
                    except Exception as err:
                        # record run-loop exceptions to warning
                        logger.exception("IB run loop exception: %s", err)

                self._ib_thread = threading.Thread(target=run_loop, daemon=False)
                self._ib_thread.start()

                # small wait for connection handshake to settle
                # If your IBapi has a connection flag you can wait on that instead.
                time.sleep(0.6)

                # reset connect backoff on success
                self._ib_connect_backoff = 0.0

                logger.info("IB connected (client id %s)", self._ib_client_id)
                return True

            except Exception as e:
                # on failure, cleanup and set warning
                logger.exception("Failed to create/connect IB instance: %s", e)
                with self.lock:
                    self.latest_warning = {"background_connect": str(e)}
                # increase backoff so repeated attempts are slower
                self._ib_connect_backoff = min(self._ib_connect_backoff + 0.75, 10.0)
                try:
                    if self._ib is not None:
                        self._ib.disconnect()
                except Exception:
                    pass
                self._ib = None
                self._ib_thread = None
                return False

    def _safe_run_scan_using_persistent_ib(self, form, securities):
        """
        Run a single scan using a persistent IB connection (preferred path).
        If the persistent IB connection is not available the method will raise.
        """
        # Ensure IB is connected (persistent)
        ok = self._ensure_ib_connected()
        if not ok:
            raise RuntimeError("IB not connected for background scan")

        # call getFinalResult on the single IB instance (same as /something handler, this blocks until done)
        try:
            # ---- normalize securities structure for getFinalResult ----
            normalized_securities = {
                "CSV": [],
                "cusip": [],
                "ticker": [],
            }

            try:
                if isinstance(securities, dict):
                    if isinstance(securities.get("CSV"), list):
                        normalized_securities["CSV"] = [
                            x for x in securities["CSV"]
                            if isinstance(x, dict)
                        ]

                    if isinstance(securities.get("cusip"), list):
                        normalized_securities["cusip"] = list(securities["cusip"])

                    if isinstance(securities.get("ticker"), list):
                        normalized_securities["ticker"] = list(securities["ticker"])
            except Exception as e:
                logger.exception("Failed to normalize background securities payload: %s", e)

            # propagate conId if present in securities
            try:
                if isinstance(securities.get("conId"), list):
                    normalized_securities["conId"] = list(securities["conId"])
            except Exception:
                pass

            # preserve backward compatibility flag
            try:
                self._ib.addFrequency = form.get("addFrequency")
            except Exception:
                pass

            # Reset screening state so each iteration fetches fresh data
            # (prices, indicators, signals).  Preserve the contract cache
            # because the background scanner re-uses the same tickers and
            # re-resolving them every iteration wastes time and API calls.
            saved_cache = dict(self._ib.contract_cache)
            self._ib._reset_screening_state()
            self._ib.contract_cache = saved_cache

            # IMPORTANT: call the IBapi scanning function (this blocks until done)
            self._ib.getFinalResult(normalized_securities, form)

            # copy results under lock
            with self.lock:
                raw_results = getattr(self._ib, "sendToFlaskIB", {}) or {}
                raw_warning = getattr(self._ib, "warningTicker", {}) or {}

                # Clean results
                clean_results = {}
                for k, v in raw_results.items():
                    if k is None:
                        fallback = f"custom{random.randint(51, 99)}"
                        clean_results[fallback] = v
                    clean_results[str(k)] = v

                # Clean warnings
                clean_warning = {}
                for k, v in raw_warning.items():
                    if k is None:
                        logger.error("warningTicker contains None key, skipping: %s", v)
                        continue
                    clean_warning[str(k)] = v

                self.latest_results = clean_results
                self.latest_warning = clean_warning

                # Beep every loop iteration when any stock meets conditions
                for v in clean_results.values():
                    if v.get("signal") == "yes":
                        self._beep_pending = True
                        break

        except Exception as e:
            # If the IB instance produced an error that may indicate a broken connection,
            # disconnect it so a fresh connection will be created on next iteration.
            logger.exception("Background scanner persistent IB getFinalResult exception: %s", e)
            with self.lock:
                self.latest_warning = {"background_scan": traceback.format_exc()}
            # attempt a safe disconnect - mark IB for recreation on next loop
            with self._ib_lock:
                try:
                    if self._ib is not None:
                        self._ib.disconnect()
                except Exception:
                    logger.debug("Exception during IB disconnect after scan failure", exc_info=True)
                self._ib = None
                # join thread if alive
                try:
                    if self._ib_thread is not None and self._ib_thread.is_alive():
                        self._ib_thread.join(timeout=1.0)
                except Exception:
                    logger.debug("Failed to join IB thread after scan failure", exc_info=True)
                self._ib_thread = None

            # re-raise so caller can handle backoff or continue loop
            raise

    def _loop(self, form, securities):
        """
        Background thread loop.
        It runs scans sequentially and waits interval_seconds after each run.
        It ensures that scans do not overlap.
        """
        logger.info("Background scanner loop started")
        # We'll attempt to keep one IB connection for the entire session to avoid client-id collisions.
        # If connecting fails we apply a lightweight backoff and keep trying until stopped.
        global cfg
        # Determine default idle timeout:
        # Prefer explicit cfg.bg_client_idle_timeout if present, else derive from cfg.scanner_poll_interval (ms) if available.
        try:
            if hasattr(cfg, "bg_client_idle_timeout") and cfg.bg_client_idle_timeout:
                idle_timeout = float(cfg.bg_client_idle_timeout)
            else:
                # cfg.scanner_poll_interval is JS poll in ms; allow 4x that as default lease window (seconds)
                idle_timeout = float(getattr(cfg, "scanner_poll_interval", 15000)) / 1000.0 * 4.0
                if idle_timeout < 30.0:
                    idle_timeout = 30.0
        except Exception:
            idle_timeout = 60.0

        _ = idle_timeout
        while not self._stop_event.is_set():
            # ---- client lease / heartbeat check ----
            try:
                heartbeat_time = self.last_client_seen or self._start_request_time
                if heartbeat_time is not None:
                    idle = time.time() - heartbeat_time
                    if idle > idle_timeout:
                        logger.info(
                            "Background scanner stopping due to client inactivity (idle %.1fs > timeout %.1fs)",
                            idle,
                            idle_timeout,
                        )
                        self._stop_event.set()
                        break
            except Exception:
                logger.exception("Error during client lease check")

            # do not start a new run if one is already in progress
            if self.is_running:
                # short sleep to avoid busy spin while a long scan is running
                if self._stop_event.wait(0.25):
                    break
                continue

            # mark running
            self.is_running = True
            try:
                # Try persistent IB path (preferred). If it fails we will catch and continue.
                try:
                    self._safe_run_scan_using_persistent_ib(form, securities)
                except Exception as e:
                    # If persistent IB path failed (e.g. connection dropped), we log & backoff a bit.
                    logger.warning("Persistent IB scan failed: %s", e)
                    # already set latest_warning inside called function
                    # small backoff to avoid immediate reconnect loops
                    if self._stop_event.wait(1.0):
                        break

                # move last_run_time AFTER successful scan (or even after attempted scan)
                self.last_run_time = time.time()

            except Exception as e:
                logger.exception("Unhandled exception inside background _loop: %s", e)
                with self.lock:
                    self.latest_warning = {"background_loop": str(e)}
            finally:
                # mark done
                self.is_running = False

            # After a run, wait interval_seconds unless stop requested
            # Use a chunked wait to respond quickly to stop events
            start_wait = time.time()
            while True:
                elapsed = time.time() - start_wait
                remaining = self.interval_seconds - elapsed
                if remaining <= 0 or self._stop_event.is_set():
                    break
                # wait in short chunks but no shorter than 0.5s (avoid very tight loops)
                wait_chunk = min(1.0, remaining)
                if self._stop_event.wait(wait_chunk):
                    break

        # Before exiting the loop, ensure IB resources are cleaned up
        with self._ib_lock:
            try:
                if self._ib is not None:
                    try:
                        self._ib.disconnect()
                    except Exception:
                        logger.debug("Error disconnecting IB on loop exit", exc_info=True)
                    self._ib = None
                if self._ib_thread is not None and self._ib_thread.is_alive():
                    try:
                        self._ib_thread.join(timeout=1.0)
                    except Exception:
                        logger.debug("Error joining IB thread on loop exit", exc_info=True)
                    self._ib_thread = None
            except Exception:
                logger.exception("Error cleaning IB resources during loop exit")

        with self.lock:
            self.enabled = False
        logger.info("Background scanner loop exiting")
        run_gc()

    # ---------------------------------------------------------------------
    # Public API (start / stop / status / results)
    # ---------------------------------------------------------------------
    def start(self, interval_seconds, form, securities):
        """
        Start the background scanner loop.
        `form` and `securities` must be provided (dicts) and should match the
        shape accepted by IBapi.getFinalResult().
        """
        if not isinstance(form, dict) or not isinstance(securities, dict):
            raise ValueError("form and securities must be dicts")

        with self.lock:
            if self.enabled:
                raise RuntimeError("Background scanner already started")

            # configure
            self.enabled = True
            self.interval_seconds = float(interval_seconds)
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._loop, args=(form, securities), daemon=False)
            # non-daemon so we can join it cleanly on stop
            self.thread.start()
            self._start_request_time = time.time()
            logger.info("Background scanner started: interval %s seconds", self.interval_seconds)

    def stop(self, wait_timeout=5.0):
        """
        Stop the background scanner gracefully.
        Wait up to wait_timeout seconds for the worker thread to finish.
        Also disconnect the persistent IB connection and join its thread.
        """
        with self.lock:
            if not self.enabled:
                return False
            self.enabled = False

            self.latest_results = {}
            self.previous_signals = {}
            self.latest_warning = {}
            self.last_run_time = None
            self._stop_event.set()

        # ask worker thread to stop and join it
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=wait_timeout)

        # ensure IB resources are torn down
        with self._ib_lock:
            try:
                if self._ib is not None:
                    try:
                        self._ib.disconnect()
                    except Exception:
                        logger.debug("ib.disconnect() raised during stop", exc_info=True)
                    self._ib = None
                if self._ib_thread is not None and self._ib_thread.is_alive():
                    try:
                        self._ib_thread.join(timeout=1.0)
                    except Exception:
                        logger.debug("joining IB thread failed in stop", exc_info=True)
                    self._ib_thread = None
            except Exception:
                logger.exception("Error cleaning IB resources during stop")

        logger.info("Background scanner stopped")
        run_gc()
        return True

    def status(self):
        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_time": self.last_run_time,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "ib_connected": (self._ib is not None and self._ib_thread is not None and self._ib_thread.is_alive()),
            "last_client_seen": self.last_client_seen,
        }

    def results(self):
        """
        Return latest results and a beep indicator.
        Beep is True whenever the most recent loop iteration found
        any stock meeting conditions.  The flag is cleared after reading
        so the frontend beeps once per loop iteration.
        """
        # Update client heartbeat (lease) whenever frontend polls results
        try:
            self.last_client_seen = time.time()
        except Exception:
            pass

        with self.lock:
            should_beep = self._beep_pending
            self._beep_pending = False

            return {
                "results": dict(self.latest_results),
                "beep": should_beep,
                "warning": dict(self.latest_warning),
                "last_run_time": self.last_run_time,
            }


# Per-tab scanner instances - supports multiple concurrent scanners
_background_scanners = {}  # dict mapping tab_unique_id -> BackgroundScanner instance
_background_scanners_lock = threading.Lock()  # Thread-safe access to _background_scanners


def _get_or_create_background_scanner(tab_unique_id):
    """
    Get or create a BackgroundScanner instance for the given tab.
    Returns the scanner instance for this tab.
    """
    if not tab_unique_id:
        raise ValueError("tab_unique_id is required")
    
    with _background_scanners_lock:
        if tab_unique_id not in _background_scanners:
            _background_scanners[tab_unique_id] = BackgroundScanner()
            logger.info("Created new background scanner for tab: %s", tab_unique_id)
        return _background_scanners[tab_unique_id]


def _get_background_scanner(tab_unique_id):
    """
    Get the BackgroundScanner instance for the given tab, or None if not found.
    """
    if not tab_unique_id:
        return None
    
    with _background_scanners_lock:
        return _background_scanners.get(tab_unique_id)


def _remove_background_scanner(tab_unique_id):
    """
    Remove the BackgroundScanner instance for the given tab after stopping it.
    """
    if not tab_unique_id:
        return False
    
    with _background_scanners_lock:
        if tab_unique_id in _background_scanners:
            del _background_scanners[tab_unique_id]
            logger.info("Removed background scanner for tab: %s", tab_unique_id)
            return True
    return False


@app.route("/background/start", methods=["POST"])
def background_start():
    """
    Start the background scanner for a specific tab.

    Expected JSON payload:
    {
        "tab_unique_id": "unique-tab-id",  # REQUIRED - identifies the tab
        "value": 5,
        "unit": "seconds" | "minutes" | "hours",
        "form": { ... },            # same shape used by getFinalResult
        "securities": { ... }       # same shape used by getFinalResult
    }

    Returns 200 on success or 4xx on bad input.
    Multiple tabs can run scanners concurrently with their own configurations.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "JSON payload required"}), 400

    tab_unique_id = payload.get("tab_unique_id")
    if not tab_unique_id:
        return jsonify({"error": "tab_unique_id is required"}), 400

    value = payload.get("value")
    unit = payload.get("unit", "seconds")
    form = payload.get("form")
    securities = payload.get("securities")

    # Get or create scanner for this tab
    try:
        scanner = _get_or_create_background_scanner(tab_unique_id)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to get/create background scanner: %s", e)
        return jsonify({"error": "failed to get/create scanner"}), 500

    # Parse interval
    seconds = scanner.parse_interval(value, unit)
    if seconds is None:
        return jsonify({"error": "Invalid interval value/unit"}), 400

    # validate form / securities presence
    if not isinstance(form, dict) or not isinstance(securities, dict):
        return jsonify({"error": "form and securities objects are required and must be JSON objects"}), 400

    # start scanner (guarded)
    try:
        scanner.start(seconds, form, securities)
    except RuntimeError as rte:
        # already running for this tab
        return jsonify({"error": str(rte)}), 409
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to start background scanner for tab %s: %s", tab_unique_id, e)
        return jsonify({"error": "failed to start scanner"}), 500

    return jsonify({"status": "started", "interval_seconds": seconds, "tab_id": tab_unique_id}), 200


@app.route("/background/stop", methods=["POST"])
def background_stop():
    """
    Stop the background scanner for a specific tab.
    
    Expected JSON payload:
    {
        "tab_unique_id": "unique-tab-id"  # REQUIRED
    }
    """
    try:
        data = request.get_json(silent=True)
        
        if not data or "tab_unique_id" not in data:
            return jsonify({"error": "tab_unique_id is required"}), 400

        tab_unique_id = data.get("tab_unique_id")
        scanner = _get_background_scanner(tab_unique_id)
        
        if scanner is None:
            return jsonify({"status": "not_running"}), 200

        stopped = scanner.stop()
        
        # Clean up the scanner instance after stopping
        _remove_background_scanner(tab_unique_id)

    except Exception as e:
        logger.exception("Failed to stop background scanner: %s", e)
        return jsonify({"error": "failed to stop scanner"}), 500

    if not stopped:
        return jsonify({"status": "not_running"}), 200
    return jsonify({"status": "stopped", "tab_id": tab_unique_id}), 200


@app.route("/background/status", methods=["GET"])
def background_status():
    """
    Return current status of the background scanner for a specific tab.
    Query parameter: tab_unique_id (required)
    """
    try:
        tab_unique_id = request.args.get("tab_unique_id")
        if not tab_unique_id:
            return jsonify({"error": "tab_unique_id query parameter is required"}), 400

        scanner = _get_background_scanner(tab_unique_id)
        if scanner is None:
            return jsonify({"enabled": False, "error": "no scanner for this tab"}), 200

        status = scanner.status()
        status["tab_id"] = tab_unique_id
        return jsonify(status), 200
    except Exception as e:
        logger.exception("Failed to get background status: %s", e)
        return jsonify({"error": "failed to get status"}), 500


@app.route("/background/results", methods=["GET"])
def background_results():
    """
    Return the last scan results for a specific tab.
    Query parameter: tab_unique_id (required)
    """
    try:
        tab_unique_id = request.args.get("tab_unique_id")
        if not tab_unique_id:
            return jsonify({"error": "tab_unique_id query parameter is required"}), 400

        scanner = _get_background_scanner(tab_unique_id)
        if scanner is None:
            return jsonify({"results": {}, "beep": False, "warning": {}, "error": "no scanner for this tab"}), 200

        res = scanner.results()
        res["tab_id"] = tab_unique_id
        return jsonify(res), 200
    except Exception as e:
        logger.exception("Failed to get background results: %s", e)
        return jsonify({"error": "failed to get results"}), 500


# -------------------------------------------------------------------------
# END OF ADDED BACKGROUND SCANNER CODE
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# START OF BACKGROUND TOP 50 SCANNER LOOP
#
# - BackgroundTop50Scanner class
# - /scanner-loop/start  (POST)
# - /scanner-loop/stop   (POST)
# - /scanner-loop/status (GET)
# - /scanner-loop/results (GET)
#
# This loop automatically fetches the IBKR Top 50 Movers on a timer,
# then screens them against the configured indicator variables (form),
# coordinating with the same signal-check pipeline as the background scanner.
# -------------------------------------------------------------------------


class _SkipIteration(Exception):
    """Sentinel exception to skip the current loop iteration without error."""
    pass


class BackgroundTop50Scanner:
    """
    Background loop that:
    1. Fetches top 50 movers from IBKR scanner (request_price_movers)
    2. Screens those symbols against configured indicator variables (getFinalResult)
    3. Repeats at a configurable interval
    """

    def __init__(self):
        self.enabled = False
        self.interval_seconds = 60.0
        self.thread = None
        self.lock = threading.Lock()
        self.is_running = False
        self.latest_results = {}
        self.latest_movers = []
        self.previous_signals = {}
        self.latest_warning = {}
        self._beep_pending = False  # set True each loop iteration when conditions met
        self.last_run_time = None
        self._stop_event = threading.Event()
        self._start_request_time = None
        self._run_count = 0
        self.scan_code = "TOP_PERC_GAIN"

        # IB connection management (same pattern as BackgroundScanner)
        self._ib = None
        self._ib_thread = None
        self._ib_client_id = None
        self._ib_lock = threading.Lock()
        self._ib_connect_backoff = 0.0

        # client heartbeat
        self.last_client_seen = None

    @staticmethod
    def parse_interval(value, unit):
        try:
            v = int(value)
        except Exception:
            return None
        if v < 1:
            return None
        unit = (unit or "seconds").lower()
        if unit == "seconds":
            sec = v
        elif unit == "minutes":
            sec = v * 60
        elif unit == "hours":
            sec = v * 3600
        else:
            return None
        if sec < 1:
            sec = 1
        if sec > 7 * 24 * 3600:
            sec = 7 * 24 * 3600
        return sec

    def _ensure_ib_connected(self):
        from ibkr_signal_engine import IBapi
        global cfg

        with self._ib_lock:
            if self._ib is not None and self._ib_thread is not None and self._ib_thread.is_alive():
                return True

            # clean previous resources
            try:
                if self._ib is not None:
                    try:
                        self._ib.disconnect()
                    except Exception:
                        pass
                    self._ib = None
                if self._ib_thread is not None and self._ib_thread.is_alive():
                    self._ib_thread.join(timeout=1.5)
                    self._ib_thread = None
            except Exception:
                logger.exception("Error cleaning previous IB resources (top50)")

            if self._ib_connect_backoff < 1.5:
                time.sleep(1.0)
            else:
                time.sleep(min(5.0, 1.0 + self._ib_connect_backoff))

            try:
                self._ib = IBapi()
                self._ib_client_id = random.randint(100000, 199999)
                logger.debug("Top50 scanner connecting IB with client id %s", self._ib_client_id)
                self._ib.connect("127.0.0.1", cfg.ibkr_api_port, self._ib_client_id)

                def run_loop():
                    try:
                        self._ib.run()
                    except Exception as err:
                        logger.exception("Top50 IB run loop exception: %s", err)

                self._ib_thread = threading.Thread(target=run_loop, daemon=False)
                self._ib_thread.start()
                time.sleep(0.6)
                self._ib_connect_backoff = 0.0
                logger.info("Top50 scanner IB connected (client id %s)", self._ib_client_id)
                return True

            except Exception as e:
                logger.exception("Failed to connect IB for top50 scanner: %s", e)
                with self.lock:
                    self.latest_warning = {"scanner_loop_connect": str(e)}
                self._ib_connect_backoff = min(self._ib_connect_backoff + 0.75, 10.0)
                try:
                    if self._ib is not None:
                        self._ib.disconnect()
                except Exception:
                    pass
                self._ib = None
                self._ib_thread = None
                return False

    def _disconnect_ib(self):
        with self._ib_lock:
            try:
                if self._ib is not None:
                    try:
                        self._ib.disconnect()
                    except Exception:
                        pass
                    self._ib = None
                if self._ib_thread is not None and self._ib_thread.is_alive():
                    self._ib_thread.join(timeout=1.0)
                    self._ib_thread = None
            except Exception:
                logger.exception("Error disconnecting IB (top50)")

    def _loop(self, form, scanner_params):
        logger.info("Top 50 scanner loop started (interval=%.1fs)", self.interval_seconds)

        global cfg
        try:
            if hasattr(cfg, "bg_client_idle_timeout") and cfg.bg_client_idle_timeout:
                idle_timeout = float(cfg.bg_client_idle_timeout)
            else:
                idle_timeout = float(getattr(cfg, "scanner_poll_interval", 15000)) / 1000.0 * 4.0
                if idle_timeout < 30.0:
                    idle_timeout = 30.0
        except Exception:
            idle_timeout = 60.0

        while not self._stop_event.is_set():
            try:
                heartbeat_time = self.last_client_seen or self._start_request_time
                if heartbeat_time is not None:
                    idle = time.time() - heartbeat_time
                    if idle > idle_timeout:
                        logger.info(
                            "Top 50 scanner stopping due to client inactivity (idle %.1fs > timeout %.1fs)",
                            idle,
                            idle_timeout,
                        )
                        self._stop_event.set()
                        break
            except Exception:
                logger.exception("Error during top50 client lease check")

            if self.is_running:
                if self._stop_event.wait(0.25):
                    break
                continue

            self.is_running = True
            try:
                ok = self._ensure_ib_connected()
                if not ok:
                    raise RuntimeError("IB not connected for top50 scanner")

                # ----------------------------------------------------------
                # Determine ticker source: custom stock list OR Top 50 scan
                # ----------------------------------------------------------
                custom_tickers = scanner_params.get("custom_tickers") or []

                if custom_tickers:
                    # ---- Custom stock list mode (from Stock List Management) ----
                    movers = None  # no scanner scan needed

                    securities = {
                        "CSV": [],
                        "cusip": [],
                        "ticker": [],
                        "conId": [],
                    }
                    for idx, sym in enumerate(custom_tickers):
                        cusip = f"custom{idx}"
                        securities["CSV"].append({
                            "cusip": cusip,
                            "ticker": sym,
                            "conId": None,
                            "change": 0,
                        })
                        securities["cusip"].append(cusip)
                        securities["ticker"].append(sym)
                        securities["conId"].append(None)

                    with self.lock:
                        self.latest_movers = [{"symbol": s, "rank": i} for i, s in enumerate(custom_tickers)]
                        self.scan_code = "CUSTOM_LIST"

                else:
                    # ---- Top 50 scanner mode (original behavior) ----
                    # Step 1: Reset scanner state and fetch top 50 movers
                    self._ib._reset_scanner_state()

                    current_scan_code = scanner_params.get("scan_code", "TOP_PERC_GAIN")
                    movers = self._ib.request_price_movers(
                        timeout_sec=cfg.movers_timeout_sec,
                        location_code=cfg.location_code,
                        scan_code=current_scan_code,
                        above_price=float(scanner_params.get("min_price", 0.05)),
                        above_volume=int(scanner_params.get("min_volume", 75000)),
                    )

                    with self.lock:
                        self.latest_movers = movers or []
                        self.scan_code = current_scan_code

                    if not movers:
                        with self.lock:
                            self.latest_warning = {"scanner_loop": "No movers returned from IBKR scanner"}
                        self.last_run_time = time.time()
                        self._run_count += 1
                        raise _SkipIteration()

                    # Build securities dict from movers
                    securities = {
                        "CSV": [],
                        "cusip": [],
                        "ticker": [],
                        "conId": [],
                    }
                    for idx, m in enumerate(movers):
                        cusip = f"custom{idx}"
                        securities["CSV"].append({
                            "cusip": cusip,
                            "ticker": m["symbol"],
                            "conId": m.get("conId"),
                            "change": 0,
                        })
                        securities["cusip"].append(cusip)
                        securities["ticker"].append(m["symbol"])
                        securities["conId"].append(m.get("conId"))

                # ----------------------------------------------------------
                # Common path: screen the securities against indicators
                # ----------------------------------------------------------
                # Preserve contract_cache across iterations to avoid
                # redundant reqContractDetails calls and IB pacing violations
                saved_cache = dict(self._ib.contract_cache)
                self._ib._reset_screening_state()
                self._ib.contract_cache = saved_cache
                self._ib._reset_scanner_state()
                self._ib.addFrequency = form.get("addFrequency")
                self._ib.getFinalResult(securities, form)

                # Collect results
                with self.lock:
                    raw_results = getattr(self._ib, "sendToFlaskIB", {}) or {}
                    raw_warning = getattr(self._ib, "warningTicker", {}) or {}

                    clean_results = {}
                    for k, v in raw_results.items():
                        key = str(k) if k is not None else f"custom{random.randint(51, 99)}"
                        clean_results[key] = v

                    clean_warning = {}
                    for k, v in raw_warning.items():
                        if k is None:
                            continue
                        clean_warning[str(k)] = v

                    self.latest_results = clean_results
                    self.latest_warning = clean_warning

                    # Beep every loop iteration when any stock meets conditions
                    for v in clean_results.values():
                        if v.get("signal") == "yes":
                            self._beep_pending = True
                            break

                self.last_run_time = time.time()
                self._run_count += 1

            except _SkipIteration:
                # No movers returned — skip screening, move to wait
                pass

            except Exception as e:
                logger.exception("Top 50 scanner loop error: %s", e)
                with self.lock:
                    self.latest_warning = {"scanner_loop": str(e)}
                # disconnect IB on error so it reconnects next iteration
                self._disconnect_ib()
                if self._stop_event.wait(1.0):
                    break

            finally:
                self.is_running = False

            # Wait for interval
            start_wait = time.time()
            while True:
                elapsed = time.time() - start_wait
                remaining = self.interval_seconds - elapsed
                if remaining <= 0 or self._stop_event.is_set():
                    break
                wait_chunk = min(1.0, remaining)
                if self._stop_event.wait(wait_chunk):
                    break

        # Cleanup on exit
        self._disconnect_ib()
        with self.lock:
            self.enabled = False
        logger.info("Top 50 scanner loop exiting")
        run_gc()

    def start(self, interval_seconds, form, scanner_params):
        if not isinstance(form, dict):
            raise ValueError("form must be a dict")

        with self.lock:
            # Auto-recover if enabled flag is stuck but the thread is dead
            if self.enabled:
                thread_alive = self.thread and self.thread.is_alive()
                if not thread_alive:
                    logger.warning("Top 50 scanner: enabled flag stuck but thread is dead — resetting")
                    self.enabled = False
                    self._stop_event.set()
                else:
                    raise RuntimeError("Top 50 scanner loop already started")
            self.enabled = True
            self.interval_seconds = float(interval_seconds)
            self._stop_event.clear()
            self._run_count = 0
            self.thread = threading.Thread(
                target=self._loop,
                args=(form, scanner_params),
                daemon=False,
            )
            self.thread.start()
            self._start_request_time = time.time()
            logger.info("Top 50 scanner loop started: interval %s seconds", self.interval_seconds)

    def stop(self, wait_timeout=5.0):
        with self.lock:
            if not self.enabled:
                return False
            self.enabled = False
            self.latest_results = {}
            self.previous_signals = {}
            self.latest_warning = {}
            self.last_run_time = None
            self._stop_event.set()
            self._run_count = 0

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=wait_timeout)

        self._disconnect_ib()
        logger.info("Top 50 scanner loop stopped")
        run_gc()
        return True

    def status(self):
        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run_time": self.last_run_time,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "ib_connected": (self._ib is not None and self._ib_thread is not None and self._ib_thread.is_alive()),
            "run_count": self._run_count,
            "movers_count": len(self.latest_movers),
        }

    def results(self):
        try:
            self.last_client_seen = time.time()
        except Exception:
            pass

        with self.lock:
            should_beep = self._beep_pending
            self._beep_pending = False

            return {
                "results": dict(self.latest_results),
                "movers": list(self.latest_movers),
                "beep": should_beep,
                "warning": dict(self.latest_warning),
                "last_run_time": self.last_run_time,
                "run_count": self._run_count,
                "scan_code": self.scan_code,
            }


# Per-tab Top 50 scanner instances - supports multiple concurrent scanners
_bg_top50_scanners = {}  # dict mapping tab_unique_id -> BackgroundTop50Scanner instance
_bg_top50_scanners_lock = threading.Lock()  # Thread-safe access to _bg_top50_scanners


def _get_or_create_top50_scanner(tab_unique_id):
    """
    Get or create a BackgroundTop50Scanner instance for the given tab.
    Returns the scanner instance for this tab.
    """
    if not tab_unique_id:
        raise ValueError("tab_unique_id is required")
    
    with _bg_top50_scanners_lock:
        if tab_unique_id not in _bg_top50_scanners:
            _bg_top50_scanners[tab_unique_id] = BackgroundTop50Scanner()
            logger.info("Created new Top50 scanner for tab: %s", tab_unique_id)
        return _bg_top50_scanners[tab_unique_id]


def _get_top50_scanner(tab_unique_id):
    """
    Get the BackgroundTop50Scanner instance for the given tab, or None if not found.
    """
    if not tab_unique_id:
        return None
    
    with _bg_top50_scanners_lock:
        return _bg_top50_scanners.get(tab_unique_id)


def _remove_top50_scanner(tab_unique_id):
    """
    Remove the BackgroundTop50Scanner instance for the given tab after stopping it.
    """
    if not tab_unique_id:
        return False
    
    with _bg_top50_scanners_lock:
        if tab_unique_id in _bg_top50_scanners:
            del _bg_top50_scanners[tab_unique_id]
            logger.info("Removed Top50 scanner for tab: %s", tab_unique_id)
            return True
    return False


@app.route("/scanner-loop/start", methods=["POST"])
def scanner_loop_start():
    """
    Start the Top 50 scanner for a specific tab.
    
    Expected JSON payload:
    {
        "tab_unique_id": "unique-tab-id",  # REQUIRED - identifies the tab
        "value": 5,
        "unit": "seconds" | "minutes" | "hours",
        "form": { ... },            # same shape used by getFinalResult
        "scanner_params": { ... }   # optional scanner parameters
    }
    
    Multiple tabs can run Top 50 scanners concurrently with their own configurations.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "JSON payload required"}), 400

    tab_unique_id = payload.get("tab_unique_id")
    if not tab_unique_id:
        return jsonify({"error": "tab_unique_id is required"}), 400

    value = payload.get("value")
    unit = payload.get("unit", "seconds")
    form = payload.get("form")
    scanner_params = payload.get("scanner_params", {})

    # Get or create scanner for this tab
    try:
        scanner = _get_or_create_top50_scanner(tab_unique_id)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to get/create Top50 scanner: %s", e)
        return jsonify({"error": "failed to get/create scanner"}), 500

    seconds = BackgroundTop50Scanner.parse_interval(value, unit)
    if seconds is None:
        return jsonify({"error": "Invalid interval value/unit"}), 400

    if not isinstance(form, dict):
        return jsonify({"error": "form object is required"}), 400

    if not isinstance(scanner_params, dict):
        scanner_params = {}

    try:
        scanner.start(seconds, form, scanner_params)
    except RuntimeError as rte:
        return jsonify({"error": str(rte)}), 409
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to start top50 scanner loop for tab %s: %s", tab_unique_id, e)
        return jsonify({"error": "failed to start scanner loop"}), 500

    return jsonify({"status": "started", "interval_seconds": seconds, "tab_id": tab_unique_id}), 200


@app.route("/scanner-loop/stop", methods=["POST"])
def scanner_loop_stop():
    """
    Stop the Top 50 scanner for a specific tab.
    
    Expected JSON payload:
    {
        "tab_unique_id": "unique-tab-id"  # REQUIRED
    }
    """
    try:
        data = request.get_json(silent=True)
        
        if not data or "tab_unique_id" not in data:
            return jsonify({"error": "tab_unique_id is required"}), 400

        tab_unique_id = data.get("tab_unique_id")
        scanner = _get_top50_scanner(tab_unique_id)
        
        if scanner is None:
            return jsonify({"status": "not_running"}), 200

        stopped = scanner.stop()
        
        # Clean up the scanner instance after stopping
        _remove_top50_scanner(tab_unique_id)
        
    except Exception as e:
        logger.exception("Failed to stop top50 scanner loop: %s", e)
        return jsonify({"error": "failed to stop scanner loop"}), 500

    if not stopped:
        return jsonify({"status": "not_running"}), 200
    return jsonify({"status": "stopped", "tab_id": tab_unique_id}), 200


@app.route("/scanner-loop/status", methods=["GET"])
def scanner_loop_status():
    """
    Return current status of the Top 50 scanner for a specific tab.
    Query parameter: tab_unique_id (required)
    """
    try:
        tab_unique_id = request.args.get("tab_unique_id")
        if not tab_unique_id:
            return jsonify({"error": "tab_unique_id query parameter is required"}), 400

        scanner = _get_top50_scanner(tab_unique_id)
        if scanner is None:
            return jsonify({"enabled": False, "error": "no scanner for this tab"}), 200

        status = scanner.status()
        status["tab_id"] = tab_unique_id
        return jsonify(status), 200
    except Exception as e:
        logger.exception("Failed to get scanner loop status: %s", e)
        return jsonify({"error": "failed to get status"}), 500


@app.route("/scanner-loop/results", methods=["GET"])
def scanner_loop_results():
    """
    Return the last scan results for a specific tab.
    Query parameter: tab_unique_id (required)
    """
    try:
        tab_unique_id = request.args.get("tab_unique_id")
        if not tab_unique_id:
            return jsonify({"error": "tab_unique_id query parameter is required"}), 400

        scanner = _get_top50_scanner(tab_unique_id)
        if scanner is None:
            return jsonify({"results": {}, "beep": False, "warning": {}, "error": "no scanner for this tab"}), 200

        res = scanner.results()
        res["tab_id"] = tab_unique_id
        return jsonify(res), 200
    except Exception as e:
        logger.exception("Failed to get scanner loop results: %s", e)
        return jsonify({"error": "failed to get results"}), 500


# -------------------------------------------------------------------------
# END OF BACKGROUND TOP 50 SCANNER LOOP
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# POST /scanner/universe
#
# Accepts JSON:
# {
#   "scan_code": str,
#   "min_price": float,
#   "min_volume": int
# }
#
# Returns:
# {
#   "rows": [...]
# }
# -------------------------------------------------------------------------

@app.route("/scanner/universe", methods=["POST"])
def scanner_universe():

    # ---- read request payload ----
    payload = request.get_json(silent=True) or {}

    # ---- import IBapi ----
    try:
        from ibkr_signal_engine import IBapi
    except Exception:
        logger.exception("Failed to import IBapi")
        return jsonify({"error": "IBKR backend unavailable"}), 503

    IBAPI = IBapi()

    rows = []

    try:
        client_id = random.randint(1000, 9999)
        IBAPI.connect("127.0.0.1", cfg.ibkr_api_port, client_id)

        thread = threading.Thread(target=IBAPI.run, daemon=True)
        thread.start()

        IBAPI.checkForConnection()

        if getattr(IBAPI, "indicateNotCondition", False):
            IBAPI.disconnect()
            run_gc()
            return jsonify({"error": "IBKR not connected"}), 503

        kwargs = {
            "timeout_sec": cfg.movers_timeout_sec,
            "location_code": cfg.location_code
        }

        if "scan_code" in payload:
            kwargs["scan_code"] = str(payload["scan_code"])

        if "min_price" in payload:
            kwargs["above_price"] = float(payload["min_price"])

        if "min_volume" in payload:
            kwargs["above_volume"] = int(payload["min_volume"])

        rows = IBAPI.request_price_movers(**kwargs)

    except Exception:
        logger.exception("Scanner request failed")
        try:
            IBAPI.disconnect()
        except Exception:
            pass
        return jsonify({"error": "IBKR scanner failed"}), 503

    finally:
        try:
            IBAPI.disconnect()
        except Exception:
            pass
        run_gc()

    return jsonify({"rows": rows}), 200


# -------------------------------------------------------------------------
# END OF NEW /scanner/universe
# -------------------------------------------------------------------------


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # no real connection is made here
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# -----------------------------------------------------------------------------
# Run server
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    local_ip = get_local_ip()
    run_port = cfg.flask_run_port

    logger.info("Web app is running:")
    logger.info("  Local : http://localhost:%s", run_port)
    logger.info("  Local : http://127.0.0.1:%s", run_port)
    logger.info("  LAN   : http://%s:%s", local_ip, run_port)

    serve(app, host="0.0.0.0", port=run_port)
