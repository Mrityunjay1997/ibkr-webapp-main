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
logger = logging.getLogger("ibkr_app")

cfg = Config()
cfg.setups_dir.mkdir(exist_ok=True)


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


# -----------------------------------------------------------------------------
# Small helpers
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
                    sendToHtml[etf__] = {etfDict: list(IBAPI.sendToFlaskIB.copy().values())}
                    time.sleep(5)
                except Exception as e:
                    logger.exception(f"Error processing ETF {etfDict}: {e}")
        else:
            IBAPI.addFrequency = myform.get("addFrequency")
            myresult = dataProcessing()
            IBAPI.getFinalResult(myresult, myform)
            sendToHtml["All ETF tickers"] = {"All ETF tickers": list(IBAPI.sendToFlaskIB.copy().values())}

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
        sendToHtml["CSV"] = {"Custom Tickers": list(IBAPI.sendToFlaskIB.copy().values())}

    # Branch C: JSON posted with custom instruments
    elif request.json is not None:
        processingData = convertCustomForm(request.json)
        myform = processingData["form"]
        IBAPI.addFrequency = myform.get("addFrequency")
        myresult = processingData["securities"]
        IBAPI.getFinalResult(myresult, myform)
        sendToHtml["CSV"] = {"Custom Tickers": list(IBAPI.sendToFlaskIB.copy().values())}
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

    IBAPI = None  # <-- FIX: ensure it always exists

    response = {
        "status": "error",
        "ordersId": None,
        "sentOrders": [],
        "message": None,
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

        IBAPI = IBapi()
        IBAPI.connect("127.0.0.1", cfg.ibkr_api_port, 302)

        try:
            IBAPI.nextOrderId = None
        except Exception:
            pass

        time.sleep(2)

        def run_loop():
            IBAPI.run()

        api_thread = threading.Thread(target=run_loop, daemon=True)
        api_thread.start()

        time.sleep(1.5)

        # ------------------------------------------------------------
        # Read input
        # ------------------------------------------------------------
        ticker_order = asset["tickerOrder"]
        limit_price = asset["limitPrice"]
        bracket_limit = asset["bracketlimit"]
        longshort = asset["longshort"]
        high_bracket = asset["highBraket"]
        low_bracket = asset["lowBraket"]
        quantity = int(asset["quantity"])

        sec_id_type = "CUSIP"

        # ------------------------------------------------------------
        # Resolve contract
        # ------------------------------------------------------------
        IBAPI.data[IBAPI.initialSec] = []
        IBAPI.findContractDetails(
            IBAPI.initialSec,
            "nan",
            sec_id_type,
            ticker_order,
        )

        time.sleep(1.5)

        if not IBAPI.data.get(IBAPI.initialSec):
            raise RuntimeError("No contract details returned from IB")

        mydata_ = IBAPI.data[IBAPI.initialSec][0]

        contract = IBAPI.marketContract(
            mydata_["symbol"],
            "STK",
            mydata_["exchange"],
            mydata_["primaryExchange"],
            mydata_["currency"],
        )

        IBAPI.reqMarketDataType(4)

        action = "BUY" if longshort == "long" else "SELL"

        # ------------------------------------------------------------
        # Build orders
        # ------------------------------------------------------------
        if bracket_limit == "bracket":

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

    finally:
        # ------------------------------------------------------------
        # Always try to disconnect safely
        # ------------------------------------------------------------
        if IBAPI is not None:
            try:
                IBAPI.disconnect()
            except Exception:
                pass

    run_gc()
    return response


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

            # preserve backward compatibility flag
            try:
                self._ib.addFrequency = form.get("addFrequency")
            except Exception:
                pass

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
            # # ---- client lease / heartbeat check (new) ----
            # # If the frontend hasn't polled /background/results recently, assume the client has died and stop scanner.
            # try:
            #     if self.last_client_seen is not None:
            #         idle = time.time() - self.last_client_seen
            #         if idle > idle_timeout:
            #             logger.info("Background scanner stopping due to client inactivity (idle %.1fs > timeout %.1fs)",
            #                         idle, idle_timeout)
            #             # avoid clearing latest_results so frontend can still show last known table
            #             # perform graceful stop and exit loop
            #             self._stop_event.set()
            #             # ensure IB cleaned up below after loop exit
            #             break
            # except Exception:
            #     logger.exception("Error during client lease check")

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
        Return latest results and a simple beep indicator if new signals
        were found since last poll. This does not play sound itself.
        Frontend should poll and play beep when `beep` is True.
        """
        # Update client heartbeat (lease) whenever frontend polls results
        try:
            self.last_client_seen = time.time()
        except Exception:
            pass

        with self.lock:
            # detect new signals
            new_signal_found = False
            for cusip, data in self.latest_results.items():
                prev = self.previous_signals.get(cusip)
                if prev is None and data.get("signal") == "yes":
                    new_signal_found = True
                elif prev is not None and prev.get("signal") != "yes" and data.get("signal") == "yes":
                    new_signal_found = True

            # update previous_signals snapshot
            self.previous_signals = {k: dict(v) for k, v in self.latest_results.items()}

            return {
                "results": dict(self.latest_results),
                "beep": new_signal_found,
                "warning": dict(self.latest_warning),
                "last_run_time": self.last_run_time,
            }


# one global scanner instance
_background_scanner = BackgroundScanner()
_background_tab_unique_id = None


@app.route("/background/start", methods=["POST"])
def background_start():
    """
    Start the background scanner.

    Expected JSON payload:
    {
        "value": 5,
        "unit": "seconds" | "minutes" | "hours",
        "form": { ... },            # same shape used by getFinalResult
        "securities": { ... }       # same shape used by getFinalResult
    }

    Returns 200 on success or 4xx on bad input.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "JSON payload required"}), 400

    value = payload.get("value")
    unit = payload.get("unit", "seconds")
    form = payload.get("form")
    securities = payload.get("securities")
    global _background_tab_unique_id
    _background_tab_unique_id = payload.get("tab_unique_id")

    seconds = _background_scanner.parse_interval(value, unit)
    if seconds is None:
        return jsonify({"error": "Invalid interval value/unit"}), 400

    # validate form / securities presence
    if not isinstance(form, dict) or not isinstance(securities, dict):
        return jsonify({"error": "form and securities objects are required and must be JSON objects"}), 400

    # start scanner (guarded)
    try:
        _background_scanner.start(seconds, form, securities)
    except RuntimeError as rte:
        # already running
        return jsonify({"error": str(rte)}), 409
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Failed to start background scanner: %s", e)
        return jsonify({"error": "failed to start scanner"}), 500

    return jsonify({"status": "started", "interval_seconds": seconds}), 200


@app.route("/background/stop", methods=["POST"])
def background_stop():
    """
    Stop the background scanner.
    """
    try:
        # ONLY apply check if beacon sent data
        data = request.get_json(silent=True)

        global _background_tab_unique_id
        if data and "tab_unique_id" in data:
            if data["tab_unique_id"] != _background_tab_unique_id:
                return jsonify({"status": "ignored"}), 200
        _background_tab_unique_id = None
        stopped = _background_scanner.stop()

    except Exception as e:
        logger.exception("Failed to stop background scanner: %s", e)
        return jsonify({"error": "failed to stop scanner"}), 500

    if not stopped:
        return jsonify({"status": "not_running"}), 200
    return jsonify({"status": "stopped"}), 200


@app.route("/background/status", methods=["GET"])
def background_status():
    """
    Return current status of the background scanner.
    """
    try:
        status = _background_scanner.status()
        return jsonify(status), 200
    except Exception as e:
        logger.exception("Failed to get background status: %s", e)
        return jsonify({"error": "failed to get status"}), 500


@app.route("/background/results", methods=["GET"])
def background_results():
    """
    Return the last scan results and a 'beep' boolean the frontend can use to trigger sound.
    """
    try:
        res = _background_scanner.results()
        return jsonify(res), 200
    except Exception as e:
        logger.exception("Failed to get background results: %s", e)
        return jsonify({"error": "failed to get results"}), 500


# -------------------------------------------------------------------------
# END OF ADDED BACKGROUND SCANNER CODE
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
