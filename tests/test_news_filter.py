"""
Unit tests for news filtering module.
"""

import datetime
from news_filter import (
    remove_duplicates,
    exclude_sources,
    filter_by_time_window,
    limit_headlines,
    filter_news
)


def test_remove_duplicates():
    """Test duplicate removal by title."""
    articles = [
        {"title": "Apple Stock Up", "source": "Bloomberg", "url": "http://1"},
        {"title": "Apple Stock Up", "source": "Reuters", "url": "http://2"},  # Duplicate
        {"title": "Tesla Rally", "source": "CNBC", "url": "http://3"},
    ]
    
    result = remove_duplicates(articles)
    assert len(result) == 2
    assert result[0]["title"] == "Apple Stock Up"
    assert result[1]["title"] == "Tesla Rally"


def test_remove_duplicates_case_insensitive():
    """Test that duplicate removal is case-insensitive."""
    articles = [
        {"title": "Apple Stock Up", "source": "Bloomberg"},
        {"title": "apple stock up", "source": "Reuters"},  # Same title, different case
    ]
    
    result = remove_duplicates(articles)
    assert len(result) == 1


def test_exclude_sources():
    """Test source exclusion."""
    articles = [
        {"title": "News 1", "source": "Bloomberg"},
        {"title": "News 2", "source": "Reuters"},
        {"title": "News 3", "source": "CNBC"},
    ]
    
    result = exclude_sources(articles, ["Bloomberg", "CNBC"])
    assert len(result) == 1
    assert result[0]["source"] == "Reuters"


def test_exclude_sources_case_insensitive():
    """Test that source exclusion is case-insensitive."""
    articles = [
        {"title": "News 1", "source": "Bloomberg"},
        {"title": "News 2", "source": "REUTERS"},
    ]
    
    result = exclude_sources(articles, ["bloomberg"])
    assert len(result) == 1
    assert result[0]["source"] == "REUTERS"


def test_filter_by_time_window_days():
    """Test filtering by days back."""
    now = datetime.datetime.utcnow()
    articles = [
        {"title": "Old News", "publishedAt": (now - datetime.timedelta(days=5)).isoformat()},
        {"title": "Recent News", "publishedAt": (now - datetime.timedelta(days=1)).isoformat()},
        {"title": "Very Recent News", "publishedAt": now.isoformat()},
    ]
    
    result = filter_by_time_window(articles, days_back=2)
    assert len(result) == 2
    assert result[0]["title"] == "Recent News"
    assert result[1]["title"] == "Very Recent News"


def test_filter_by_time_window_hours():
    """Test filtering by hours back."""
    now = datetime.datetime.utcnow()
    articles = [
        {"title": "Old News", "publishedAt": (now - datetime.timedelta(hours=5)).isoformat()},
        {"title": "Recent News", "publishedAt": (now - datetime.timedelta(hours=1)).isoformat()},
    ]
    
    result = filter_by_time_window(articles, hours_back=2)
    assert len(result) == 1
    assert result[0]["title"] == "Recent News"


def test_limit_headlines():
    """Test limiting headlines count."""
    articles = [
        {"title": f"News {i}", "source": "Source"} for i in range(10)
    ]
    
    result = limit_headlines(articles, max_count=5)
    assert len(result) == 5


def test_filter_news_combined():
    """Test filtering with all filters combined."""
    now = datetime.datetime.utcnow()
    articles = [
        {"title": "Duplicate", "source": "Bloomberg", "publishedAt": now.isoformat(), "url": "http://1"},
        {"title": "Duplicate", "source": "Reuters", "publishedAt": now.isoformat(), "url": "http://2"},  # Duplicate
        {"title": "Old News", "source": "CNBC", "publishedAt": (now - datetime.timedelta(days=10)).isoformat(), "url": "http://3"},
        {"title": "Recent 1", "source": "Bloomberg", "publishedAt": now.isoformat(), "url": "http://4"},
        {"title": "Recent 2", "source": "Excluded", "publishedAt": now.isoformat(), "url": "http://5"},
        {"title": "Recent 3", "source": "CNBC", "publishedAt": (now - datetime.timedelta(hours=1)).isoformat(), "url": "http://6"},
    ]
    
    result = filter_news(
        articles,
        max_headlines=2,
        excluded_sources=["Excluded"],
        days_back=1,
        remove_dups=True
    )
    
    # Should have: Duplicate (1), Recent 1, Recent 3 after filtering - but max 2
    assert len(result) == 2
    assert result[0]["title"] == "Duplicate"
    assert result[1]["title"] == "Recent 1"


def test_filter_news_no_filters():
    """Test that filter_news returns all articles when no filters are applied."""
    articles = [
        {"title": "News 1", "source": "Source"},
        {"title": "News 2", "source": "Source"},
    ]
    
    result = filter_news(articles, remove_dups=False)
    assert len(result) == 2


if __name__ == "__main__":
    test_remove_duplicates()
    test_remove_duplicates_case_insensitive()
    test_exclude_sources()
    test_exclude_sources_case_insensitive()
    test_filter_by_time_window_days()
    test_filter_by_time_window_hours()
    test_limit_headlines()
    test_filter_news_combined()
    test_filter_news_no_filters()
    
    print("✓ All tests passed!")
