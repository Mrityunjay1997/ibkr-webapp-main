# IBKR Signal & Scanner Engine

A lightweight screening and signal engine built on top of the Interactive Brokers API. It retrieves ranked movers from IBKR scanners, enriches results with market data when available, and computes technical indicators for signal generation.

It exposes a simple web interface and API for querying scanner results and running indicator-based screening workflows.

---

# Features

* Retrieve top gainers, losers, and other IBKR scanner results
* Return symbols in IBKR rank order with optional percent change
* Compute technical indicators (VWAP, SMA, RSI, EMA, OBV, ATR, pivot points)
* Run configurable screening and signal logic
* Background scanner support with live updates
* REST API and web UI

---

# Requirements

* Python 3.12+
* Interactive Brokers TWS
* IBKR account with API access enabled

---

# Running

Start the server:

```bash
python __init__.py
```

Then open:

```
http://localhost:5000
```
