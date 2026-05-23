from datetime import datetime, timezone

from news_utils import (
    is_within_news_window,
    news_within_minutes,
    parse_news_datetime,
    read_aloud_within_minutes,
)


def test_parse_news_datetime_accepts_ibkr_compact_format():
    parsed = parse_news_datetime("20260521 13:45:00.0")

    assert parsed == datetime(2026, 5, 21, 13, 45, tzinfo=timezone.utc)


def test_parse_news_datetime_accepts_hyphenated_format():
    parsed = parse_news_datetime("2026-05-21 13:45:00.0")

    assert parsed == datetime(2026, 5, 21, 13, 45, tzinfo=timezone.utc)


def test_parse_news_datetime_accepts_epoch_milliseconds():
    parsed = parse_news_datetime("1779371100000")

    assert parsed == datetime(2026, 5, 21, 13, 45, tzinfo=timezone.utc)


def test_news_window_minutes_supports_minutes_hours_days_and_legacy_hours():
    assert news_within_minutes({"NewsWithinValue": "5", "NewsTimeUnit": "minutes"}) == 5
    assert news_within_minutes({"NewsWithinValue": "2", "NewsTimeUnit": "hours"}) == 120
    assert news_within_minutes({"NewsWithinValue": "1", "NewsTimeUnit": "days"}) == 1440
    assert news_within_minutes({"NewsWithinValue": "0", "NewsWithinHours": "3"}) == 180


def test_news_window_minutes_supports_day_variations():
    assert news_within_minutes({"NewsWithinValue": "10", "NewsTimeUnit": "days"}) == 14400
    assert news_within_minutes({"NewsWithinValue": "10", "NewsTimeUnit": "Days"}) == 14400
    assert news_within_minutes({"NewsWithinValue": "10", "NewsTimeUnit": "d"}) == 14400
    assert news_within_minutes({"NewsWithinValue": "10", "NewsTimeUnit": "DAY"}) == 14400


def test_read_aloud_window_is_separate_from_news_window():
    form = {
        "NewsWithinValue": "0",
        "NewsTimeUnit": "minutes",
        "NewsReadAloudWithinValue": "15",
        "NewsReadAloudTimeUnit": "minutes",
    }

    assert news_within_minutes(form) == 0
    assert read_aloud_within_minutes(form) == 15


def test_is_within_news_window_uses_compact_ibkr_time():
    now = datetime(2026, 5, 21, 13, 50, tzinfo=timezone.utc)

    assert is_within_news_window("20260521 13:45:00.0", 5, now=now)
    assert not is_within_news_window("20260521 13:44:59.0", 5, now=now)
