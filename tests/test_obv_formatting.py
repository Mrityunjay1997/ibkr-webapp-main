from ibkr_signal_engine import _round_obv_value


def test_round_obv_value_returns_integer_for_smoothed_obv():
    assert _round_obv_value(1234.56) == 1235
    assert _round_obv_value(-1234.56) == -1235


def test_round_obv_value_handles_missing_values():
    assert _round_obv_value(None) is None
