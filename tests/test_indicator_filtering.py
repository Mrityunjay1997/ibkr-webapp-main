from ibkr_signal_engine import (
    _build_pivot_level_map,
    _compare_indicator_value,
    apply_result_filters,
)


def test_compare_indicator_value_supports_equal():
    assert _compare_indicator_value(10, "equal", 10) is True
    assert _compare_indicator_value(10, "equal", 11) is False


def test_result_filters_require_all_selected_variable_results():
    stock_data = {
        "symbol": "TEST",
        "variableResults": {
            "smaFast": True,
            "ema1": True,
            "Pivot": True,
        },
    }
    form = {
        "filterFastSMA": True,
        "filterEMA1": True,
        "filterPivotPoint": True,
    }

    assert apply_result_filters(stock_data, form) is True

    stock_data["variableResults"]["ema1"] = False
    assert apply_result_filters(stock_data, form) is False


def test_pivot_levels_are_normalized_for_results():
    levels = _build_pivot_level_map(prev_h=110.0, prev_l=100.0, prev_c=105.0)

    assert set(levels.keys()) == {
        "pivot_point",
        "resistance_1",
        "resistance_2",
        "support_1",
        "support_2",
    }
    assert levels["pivot_point"] == 105.0
