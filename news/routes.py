from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    return str(value or "").strip()


def news_enabled(form: Mapping[str, Any]) -> bool:
    """Return whether news should participate in fetching/timing logic."""
    setting = _text(form.get("ComparisonNews", "enabled")).lower()
    return setting not in {"disabled", "false", "0", "off", "no"}


def news_signal_enabled(form: Mapping[str, Any]) -> bool:
    """Return whether the news indicator itself should be evaluated as a signal."""
    return _text(form.get("ComparisonNews", "")).lower() == "enabled"


def parse_news_keywords(value: Any) -> list[str]:
    raw = _text(value)
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def has_news_keywords(form: Mapping[str, Any]) -> bool:
    return bool(parse_news_keywords(form.get("NewsKeywords", "")))


def should_fetch_news(form: Mapping[str, Any]) -> bool:
    """Fetch headlines only when news is enabled or keyword matching needs them."""
    return news_enabled(form) or has_news_keywords(form)


def filter_headlines_by_keywords(
    headlines: Iterable[Mapping[str, Any]] | None,
    keywords_raw: Any,
) -> tuple[list[Mapping[str, Any]], list[str], bool]:
    """Return headlines containing any whole-word keyword and the matched text."""
    keywords = parse_news_keywords(keywords_raw)
    safe_headlines = [h for h in (headlines or []) if isinstance(h, Mapping)]
    if not keywords:
        return safe_headlines, [], False

    patterns = [re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE) for keyword in keywords]
    filtered: list[Mapping[str, Any]] = []
    matched_text: list[str] = []

    for headline in safe_headlines:
        headline_text = _text(headline.get("headline", ""))
        if any(pattern.search(headline_text) for pattern in patterns):
            filtered.append(headline)
            matched_text.append(headline_text)

    return filtered, matched_text, bool(filtered)


def register_news_routes(app: Any) -> None:
    """Register News page routes independently from scanner/order routes."""
    if "news_reader_page" in app.view_functions:
        return

    from flask import render_template

    @app.route("/news-reader", methods=["GET"])
    def news_reader_page():
        """Render a dedicated page for monitoring and reading scan news aloud."""
        return render_template("news_reader.html")
