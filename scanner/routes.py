from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Sequence

logger = logging.getLogger(__name__)

FILTER_KEYS: tuple[str, ...] = (
    "filterVWAP", "filterFastSMA", "filterMediumSMA", "filterSlowSMA",
    "filterSMA1", "filterSMA2", "filterSMA3",
    "filterRSI", "filterFastEMA", "filterSlowEMA", "filterEMA1", "filterEMA2",
    "filterOBV", "filterFastOBV", "filterMediumOBV", "filterSlowOBV", "filterATR",
    "filterAverageVolume", "filterRelativeVolume", "filterPrevClose",
    "filterLowOfDay", "filterHighOfDay", "filterCross50SMA", "filterCross200SMA",
    "filterBreakHigh", "filterPullbackPct", "filterPullbackPct2",
    "filterFibPullback", "filterGapPullback", "filterPivotPoint",
    "filterUpGap", "filterDownGap", "filterNewsKeyword", "filterMarketCap",
    "filterVolume",
)


def ibkr_port_ready(port: Any) -> bool:
    return port is not None and str(port).strip() != ""


def has_enabled_filters(form: Mapping[str, Any]) -> bool:
    return any(bool(form.get(key)) for key in FILTER_KEYS)


def filter_results(
    results_list: Sequence[dict[str, Any]] | None,
    form: Mapping[str, Any],
    evaluator: Callable[[dict[str, Any], Mapping[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Keep rows that satisfy every enabled scanner filter."""
    if not results_list:
        return []

    if not has_enabled_filters(form):
        return list(results_list)

    if evaluator is None:
        from scanner.ibkr_signal_engine import apply_result_filters as evaluator

    filtered: list[dict[str, Any]] = []
    for stock_data in results_list:
        try:
            if evaluator(stock_data, form):
                filtered.append(stock_data)
        except Exception as exc:
            logger.exception(
                "Scanner result rejected because filter evaluation failed for %s: %s",
                stock_data.get("ticker") or stock_data.get("symbol") or stock_data.get("cusip"),
                exc,
            )

    return filtered
