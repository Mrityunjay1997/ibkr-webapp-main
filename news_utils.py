from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence


def parse_news_datetime(value: Any) -> Optional[datetime]:
    """Parse common IBKR/news timestamp formats as timezone-aware UTC."""
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit():
        try:
            stamp = int(text)
            if stamp > 10_000_000_000:
                stamp = stamp / 1000
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    base = text.split(".")[0].strip()
    formats: Sequence[str] = (
        "%Y%m%d %H:%M:%S",
        "%Y%m%d-%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d-%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(base, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def time_window_minutes(value: Any, unit: Any) -> int:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        return 0

    if amount <= 0:
        return 0

    unit_text = str(unit or "minutes").strip().lower()
    
    if unit_text in ("", "m", "min", "mins", "minute", "minutes"):
        # Default to minutes when the unit is explicitly minutes or missing.
        if not unit_text and amount > 24:
            # If the unit is completely missing and the amount is large, assume days.
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Empty unit with amount={amount}, assuming user meant 'days' instead of 'minutes'"
            )
            return amount * 1440
        return amount
    if unit_text in ("h", "hr", "hrs", "hour", "hours"):
        return amount * 60
    if unit_text in ("d", "day", "days"):
        return amount * 1440

    # Debug: Log unexpected unit values
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Unexpected time unit: '{unit}' (normalized to '{unit_text}')")

    # Fall back to minutes for any unknown unit.
    return amount


def news_within_minutes(form: Mapping[str, Any]) -> int:
    """
    Calculate the news window in minutes from form data.
    Supports both new (NewsWithinValue + NewsTimeUnit) and legacy (NewsWithinHours) fields.
    
    Returns minutes, or 0 if no time window is specified (show all headlines).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Try new format first: NewsWithinValue + NewsTimeUnit
    news_within_value = form.get("NewsWithinValue", 0)
    news_time_unit = form.get("NewsTimeUnit", "")
    
    # If we have a value, calculate minutes
    if news_within_value and int(news_within_value or 0) > 0:
        # DON'T default to "minutes" - pass the actual unit value (even if empty)
        # so time_window_minutes can detect and handle the missing unit
        minutes = time_window_minutes(news_within_value, news_time_unit)
        if minutes > 0:
            logger.debug(f"news_within_minutes: Using new format - value={news_within_value}, unit={news_time_unit or 'empty'}, calculated={minutes} minutes")
            return minutes
        else:
            logger.warning(f"news_within_minutes: Failed to calculate minutes from NewsWithinValue={news_within_value}, NewsTimeUnit={news_time_unit or 'empty'} (got {minutes})")
    
    # Fall back to legacy NewsWithinHours field
    news_within_hours = form.get("NewsWithinHours", 0)
    if news_within_hours and int(news_within_hours or 0) > 0:
        minutes = time_window_minutes(news_within_hours, "hours")
        logger.debug(f"news_within_minutes: Using legacy format - NewsWithinHours={news_within_hours}, calculated={minutes} minutes")
        return minutes
    
    # No time filter specified
    logger.debug("news_within_minutes: No time filter specified (will show all headlines)")
    return 0


def read_aloud_within_minutes(form: Mapping[str, Any]) -> int:
    return time_window_minutes(
        form.get("NewsReadAloudWithinValue", 0),
        form.get("NewsReadAloudTimeUnit", "minutes"),
    )


def is_within_news_window(value: Any, minutes: int, now: Optional[datetime] = None) -> bool:
    if minutes <= 0:
        return True

    parsed = parse_news_datetime(value)
    if parsed is None:
        return False

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    return parsed >= current - timedelta(minutes=minutes)
