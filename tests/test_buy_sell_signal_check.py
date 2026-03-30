# test_buy_sell_signal_check.py
from ibkr_signal_engine import IBapi


def _safe_compare(a, op, b):
    if a is None or b is None:
        return False
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    raise ValueError(op)


class Dummy(IBapi):
    def __init__(self):
        super().__init__()
        if not hasattr(self, "sendToFlaskIB"):
            self.sendToFlaskIB = {}


# ---- helpers ----

def minimal_form():
    return {
        "ComparisonAverageVolume": "Not used",
        "averageVolumeBool": "value",
        "ComparisonPrice": "Not used",
        "ComparisonVWAP": "Not used",
        "VWAPBool": "value",
        "ComparisonFastSMA": "Not used",
        "SMAFastBool": "value",
        "ComparisonMediumSMA": "Not used",
        "SMAMediumBool": "value",
        "ComparisonSlowSMA": "Not used",
        "smaslowyesno": "value",
        "ComparisonRSI": "Not used",
        "ComparisonFastEMA": "Not used",
        "FastEMABool": "value",
        "ComparisonSlowEMA": "Not used",
        "SlowEMABool": "value",
        "ComparisonOBV": "Not used",
        "OBVBool": "value",
        "ComparisonATR": "Not used",
        "ATRBool": "value",
        "PrevCloseBool": "value",
        "LowOfDayBool": "value",
        "HighOfDayBool": "value",
        "PullbackBool": "value",
        "ComparisonPivotPoint": "Not used",
        "pivotPointBool": "value",
        "ComparisonRelativeVolume": "Not used",
        "SMACrossoverPeriod": "50",
        "ComparisonSMACrossover": "Not used",
        "SMACrossoverBool": "value",
        "ComparisonSMA200Crossover": "Not used",
        "NewsEnabled": "disabled",
    }


def minimal_data():
    return {
        "cusip": "X",
    }


# ------------------------------------------------------------------
# 1) no conditions used -> counting_ == 0 -> signal must be "no"
# ------------------------------------------------------------------
def test_no_conditions_used_returns_no():
    d = Dummy()
    data = minimal_data()
    form = minimal_form()

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 2) missing value in percentage branch must NOT crash
#    and must force the condition to False
#    (average volume, percentage path)
# ------------------------------------------------------------------
def test_average_volume_percentage_missing_base_forces_false():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        # averageVolume is intentionally missing
        "volume": 100
    })

    form = minimal_form()
    form.update({
        "ComparisonAverageVolume": "greater",
        "averageVolumeBool": "percentage",
        "PercentageAverageVolume": "10",
    })

    out = d.buySellSignalCheck(data, form)

    # one condition is used and must fail
    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 3) percentage branch with valid base still works
# ------------------------------------------------------------------
def test_average_volume_percentage_happy_path():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "averageVolume": 100,
        "volume": 120,
    })

    form = minimal_form()
    form.update({
        "ComparisonAverageVolume": "greater",
        "averageVolumeBool": "percentage",
        "PercentageAverageVolume": "10",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "yes"


# ------------------------------------------------------------------
# 4) between percentage path: missing one bound must fail, not crash
# ------------------------------------------------------------------
def test_between_percentage_missing_upper_bound_fails():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "averageVolume": 100,
        # averageVolume1 missing
        "volume": 110,
    })

    form = minimal_form()
    form.update({
        "ComparisonAverageVolume": "between",
        "averageVolumeBool": "percentage",
        "PercentageAverageVolume": "5",
        "PercentageAverageVolume1": "20",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 5) price "between" must preserve strict inequality
#    old:  a < close < b
# ------------------------------------------------------------------
def test_price_between_strict():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 10.0
    })

    form = minimal_form()
    form.update({
        "ComparisonPrice": "between",
        "PercentagePrice": "10",
        "PercentagePrice1": "20",
    })

    out = d.buySellSignalCheck(data, form)

    # 10 < 10 < 20  -> False
    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 6) vwap percentage: vwap missing must fail, not crash
# ------------------------------------------------------------------
def test_vwap_percentage_missing_vwap():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 10.0
    })

    form = minimal_form()
    form.update({
        "ComparisonVWAP": "greater",
        "VWAPBool": "percentage",
        "PercentageVWAP": "5",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 7) fast SMA percentage happy path
# ------------------------------------------------------------------
def test_fast_sma_percentage_ok():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "smaFast": 100,
        "close": 120,
    })

    form = minimal_form()
    form.update({
        "ComparisonFastSMA": "greater",
        "SMAFastBool": "percentage",
        "PercentageFastSMA": "10",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "yes"


# ------------------------------------------------------------------
# 8) pivot percentage: pivot missing must fail, not crash
# ------------------------------------------------------------------
def test_pivot_percentage_missing_pivot_value():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 10.0,
        "Pivot": {"P": None}
    })

    form = minimal_form()
    form.update({
        "ComparisonPivotPoint": "greater",
        "pivotPointBool": "percentage",
        "PercentagePivotPoint": "5",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 9) relative volume between preserves strict comparisons
#    old: rv > a and rv1 < b
# ------------------------------------------------------------------
def test_relative_volume_between_strict():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "relativeVolume": 5.0,
        "relativeVolume1": 10.0,
    })

    form = minimal_form()
    form.update({
        "ComparisonRelativeVolume": "between",
        "PercentageRelativeVolume": "5.0",
        "PercentageRelativeVolume1": "10.0",
    })

    out = d.buySellSignalCheck(data, form)

    # 5.0 > 5.0 is False
    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 10) multiple conditions: one false must flip whole signal to no
# ------------------------------------------------------------------
def test_mixed_conditions_one_false():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 50,
        "rsi": 30,
    })

    form = minimal_form()
    form.update({
        "ComparisonPrice": "greater",
        "PercentagePrice": "10",
        "ComparisonRSI": "greater",
        "PercentageRSI": "40",
    })

    out = d.buySellSignalCheck(data, form)

    # price ok, rsi fails
    assert out["signal"] == "no"


# ------------------------------------------------------------------
# 11) pullback percentage/value behavior
# ------------------------------------------------------------------
def test_pullback_value_condition_ok():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 90.0,
        "high": 120.0,
        "prevClose": 100.0,
        "pullback": (120.0 - 90.0) / (120.0 - 100.0),  # 1.5
    })

    form = minimal_form()
    form.update({
        "ComparisonPullback": "greater",
        "PullbackBool": "value",
        "PercentagePullback": "1.0",
    })

    out = d.buySellSignalCheck(data, form)

    assert out["signal"] == "yes"


# ------------------------------------------------------------------
# 11b) pullback percentage between mode
#   prevClose=1, high=2, move=$1
#   45% retracement -> close=1.55, pullback ratio=0.45
#   between 40% and 50% -> 0.4 < 0.45 < 0.5 => True
# ------------------------------------------------------------------
def test_pullback_percentage_between():
    d = Dummy()
    data = minimal_data()
    # Stock moved from 1 to 2, currently at 1.55 (45% retracement)
    data.update({
        "cusip": "X",
        "close": 1.55,
        "high": 2.0,
        "prevClose": 1.0,
        "pullback": (2.0 - 1.55) / (2.0 - 1.0),  # 0.45
    })

    form = minimal_form()
    form.update({
        "ComparisonPullback": "between",
        "PullbackBool": "percentage",
        "PercentagePullback": "40",
        "PercentagePullback1": "50",
    })

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # Exactly at 50% boundary (strict inequality => excluded)
    data["close"] = 1.5
    data["pullback"] = (2.0 - 1.5) / (2.0 - 1.0)  # 0.5
    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "no"

    # 30% retracement — outside range
    data["close"] = 1.7
    data["pullback"] = (2.0 - 1.7) / (2.0 - 1.0)  # 0.3
    out3 = d.buySellSignalCheck(data, form)
    assert out3["signal"] == "no"


# ------------------------------------------------------------------
# 12) break high breakout + near-high behavior
# ------------------------------------------------------------------
def test_highest_high_breakout_and_near():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 101.0,
        "highestHigh": 100.0,
    })

    form = minimal_form()
    form.update({
        "HighestHighBool": "value",
        "ComparisonHighestHigh": "greater",
    })

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # near: price just below the high (within 1%)
    data["close"] = 99.5
    form["HighestHighBool"] = "percentage"
    form["ComparisonHighestHigh"] = "near"
    form["PercentageHighestHigh"] = "1.0"  # within 1% of 100 => 99.0..

    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "yes"

    # near: price above the high also passes (break of high)
    data["close"] = 102.0
    out3 = d.buySellSignalCheck(data, form)
    assert out3["signal"] == "yes"

    # near: price too far below the high (outside 1%)
    data["close"] = 98.0
    out4 = d.buySellSignalCheck(data, form)
    assert out4["signal"] == "no"


def test_sma_crossover_50_cross_above_and_below():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "prevClose": 99.0,
        "close": 101.0,
        "sma50": 100.0,
        "sma200": 100.0,
    })

    form = minimal_form()
    form.update({
        "SMACrossoverPeriod": "50",
        "ComparisonSMACrossover": "crossAbove",
    })

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    data["prevClose"] = 101.0
    data["close"] = 99.0
    form["ComparisonSMACrossover"] = "crossBelow"

    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "yes"


def test_scanner_name_propagates_to_result():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 10.0,
    })

    form = minimal_form()
    form["ScannerName"] = "My Scanner"

    out = d.buySellSignalCheck(data, form)

    assert out["scanner_name"] == "My Scanner"
    assert d.sendToFlaskIB["X"]["scanner_name"] == "My Scanner"


def test_sma200_crossover_cross_above_and_below():
    d = Dummy()
    data = minimal_data()
    data.update({
        "cusip": "X",
        "prevClose": 195.0,
        "close": 205.0,
        "sma50": 100.0,
        "sma200": 200.0,
    })

    form = minimal_form()
    form["ComparisonSMA200Crossover"] = "crossAbove"

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # Cross below: was above 200 SMA, now below
    data["prevClose"] = 205.0
    data["close"] = 195.0
    form["ComparisonSMA200Crossover"] = "crossBelow"

    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "yes"

    # No cross: both sides above -> no signal
    data["prevClose"] = 205.0
    data["close"] = 210.0
    form["ComparisonSMA200Crossover"] = "crossAbove"

    out3 = d.buySellSignalCheck(data, form)
    assert out3["signal"] == "no"


# ------------------------------------------------------------------
# PrevClose / HighOfDay / LowOfDay / Pivot — percentage between mode
# ------------------------------------------------------------------
def test_prevclose_percentage_between():
    """Stock up between 1% and 20% from previous close."""
    d = Dummy()
    data = minimal_data()
    # prevClose=100, close=110 → up 10%
    data.update({"cusip": "X", "close": 110.0, "prevClose": 100.0})

    form = minimal_form()
    form.update({
        "ComparisonPrevClose": "between",
        "PrevCloseBool": "percentage",
        "PercentagePrevClose": "1",
        "PercentagePrevClose1": "20",
    })

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # close=125 → up 25% — outside 1-20% range
    data["close"] = 125.0
    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "no"

    # close=100.5 → up 0.5% — below 1% range
    data["close"] = 100.5
    out3 = d.buySellSignalCheck(data, form)
    assert out3["signal"] == "no"


def test_highofday_percentage_between():
    """Close within -5% to 0% of high of day (near the high)."""
    d = Dummy()
    data = minimal_data()
    # highOfDay=200, close=195 → 2.5% below high
    data.update({"cusip": "X", "close": 195.0, "highOfDay": 200.0})

    form = minimal_form()
    form.update({
        "ComparisonHighOfDay": "between",
        "HighOfDayBool": "percentage",
        "PercentageHighOfDay": "-5",
        "PercentageHighOfDay1": "0",
    })

    # -5% of 200 = 190, 0% of 200 = 200 → 190 <= 195 <= 200 → yes
    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # close=185 → below 190 → no
    data["close"] = 185.0
    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "no"


def test_lowofday_percentage_between():
    """Close within 0% to 5% of low of day (near the low)."""
    d = Dummy()
    data = minimal_data()
    # lowOfDay=50, close=51 → 2% above low
    data.update({"cusip": "X", "close": 51.0, "lowOfDay": 50.0})

    form = minimal_form()
    form.update({
        "ComparisonLowOfDay": "between",
        "LowOfDayBool": "percentage",
        "PercentageLowOfDay": "0",
        "PercentageLowOfDay1": "5",
    })

    # 0% of 50=50, 5% of 50=52.5 → 50 <= 51 <= 52.5 → yes
    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # close=55 → above 52.5 → no
    data["close"] = 55.0
    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "no"


def test_pivot_percentage_between():
    """Close within 1% to 3% of pivot."""
    d = Dummy()
    data = minimal_data()
    # pivot=100, close=102 → 2% above pivot
    data.update({
        "cusip": "X",
        "close": 102.0,
        "Pivot": {"P": 100.0},
    })

    form = minimal_form()
    form.update({
        "ComparisonPivotPoint": "between",
        "pivotPointBool": "percentage",
        "PercentagePivotPoint": "1",
        "PercentagePivotPoint1": "3",
    })

    # 1% of 100=101, 3% of 100=103 → 101 <= 102 <= 103 → yes
    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"

    # close=105 → above 103 → no
    data["close"] = 105.0
    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "no"


# ------------------------------------------------------------------
# News integration tests
# ------------------------------------------------------------------
def test_news_disabled_no_headlines():
    """When NewsEnabled=disabled, no news fetching occurs."""
    d = Dummy()
    data = minimal_data()
    data.update({"cusip": "X", "close": 10.0})

    form = minimal_form()
    form["NewsEnabled"] = "disabled"

    out = d.buySellSignalCheck(data, form)
    assert out["news_headlines"] == []
    assert out["latest_news_ts"] == ""


def test_news_required_no_articles_forces_signal_no():
    """When NewsEnabled=required and no news returned, signal forced to no."""
    import types

    d = Dummy()
    # Stub fetch_news_for_symbol to return empty list
    d.fetch_news_for_symbol = types.MethodType(
        lambda self, symbol, limit=50, lookback_days=14: [], d
    )

    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 120.0,
        "smaFast": 100.0,
    })

    form = minimal_form()
    form["ComparisonFastSMA"] = "greater"
    form["SMAFastBool"] = "percentage"
    form["PercentageFastSMA"] = "10"
    form["NewsEnabled"] = "required"
    form["NewsLookbackHours"] = "24"

    out = d.buySellSignalCheck(data, form)
    # SMA condition passes but no news -> forced to no
    assert out["signal"] == "no"
    assert out["conditions_status"].get("NewsWithinWindow") is False


def test_news_required_with_articles_keeps_signal():
    """When NewsEnabled=required and news exists, signal stays yes."""
    import types

    d = Dummy()
    fake_articles = [
        {"symbol": "AAPL", "title": "Apple rises", "url": "https://example.com/1",
         "publishedAt": "2025-01-15T10:00:00", "source": "TestNews"},
    ]
    d.fetch_news_for_symbol = types.MethodType(
        lambda self, symbol, limit=50, lookback_days=14: list(fake_articles), d
    )

    data = minimal_data()
    data.update({
        "cusip": "X",
        "close": 120.0,
        "smaFast": 100.0,
    })

    form = minimal_form()
    form["ComparisonFastSMA"] = "greater"
    form["SMAFastBool"] = "percentage"
    form["PercentageFastSMA"] = "10"
    form["NewsEnabled"] = "required"
    form["NewsLookbackHours"] = "0"

    out = d.buySellSignalCheck(data, form)
    assert out["signal"] == "yes"
    assert len(out["news_headlines"]) == 1
    assert out["latest_news_ts"] == "2025-01-15T10:00:00"
    assert out["conditions_status"].get("NewsWithinWindow") is True


def test_news_enabled_attaches_headlines():
    """When NewsEnabled=enabled, news is fetched and attached but signal not forced."""
    import types

    d = Dummy()
    fake_articles = [
        {"symbol": "TSLA", "title": "Tesla news", "url": "https://example.com/2",
         "publishedAt": "2025-01-15T12:00:00", "source": "TestNews"},
        {"symbol": "TSLA", "title": "Tesla other", "url": "https://example.com/3",
         "publishedAt": "2025-01-15T11:00:00", "source": "TestNews"},
    ]
    d.fetch_news_for_symbol = types.MethodType(
        lambda self, symbol, limit=50, lookback_days=14: list(fake_articles), d
    )

    data = minimal_data()
    data.update({"cusip": "X", "close": 10.0})

    form = minimal_form()
    form["NewsEnabled"] = "enabled"
    form["NewsLookbackHours"] = "0"

    out = d.buySellSignalCheck(data, form)
    # No other conditions -> signal no, but news still attached
    assert out["signal"] == "no"
    assert len(out["news_headlines"]) == 2
    assert out["latest_news_ts"] == "2025-01-15T12:00:00"
