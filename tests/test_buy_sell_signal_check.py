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
# 12) highest high breakout + near-high behavior
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

    data["close"] = 99.5
    form["HighestHighBool"] = "percentage"
    form["ComparisonHighestHigh"] = "near"
    form["PercentageHighestHigh"] = "1.0"  # within 1% of 100 => 99.0..100

    out2 = d.buySellSignalCheck(data, form)
    assert out2["signal"] == "yes"


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
