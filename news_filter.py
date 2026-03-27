"""
News filtering module for duplicate removal, source exclusion, and temporal filtering.
"""

import datetime
from typing import List, Dict, Optional, Set


def parse_datetime_safe(dt_str):
    """Parse ISO datetime strings safely."""
    if not dt_str:
        return None
    try:
        # Handle ISO format with Z suffix
        if isinstance(dt_str, str):
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1] + '+00:00'
            return datetime.datetime.fromisoformat(dt_str)
        return dt_str
    except Exception:
        return None


def remove_duplicates(articles: List[Dict]) -> List[Dict]:
    """
    Remove duplicate articles based on title.
    
    Args:
        articles: List of article dictionaries
        
    Returns:
        List of articles with duplicates removed (by title)
    """
    seen_titles = set()
    unique_articles = []
    
    for article in articles:
        title = article.get('title', '').strip().lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)
    
    return unique_articles


def exclude_sources(articles: List[Dict], excluded_sources: Optional[List[str]]) -> List[Dict]:
    """
    Exclude articles from specified sources.
    
    Args:
        articles: List of article dictionaries
        excluded_sources: List of source names to exclude (case-insensitive)
        
    Returns:
        List of articles with excluded sources filtered out
    """
    if not excluded_sources:
        return articles
    
    # Normalize excluded sources to lowercase
    excluded_set = {src.strip().lower() for src in excluded_sources}
    
    filtered = []
    for article in articles:
        source = article.get('source', '').strip().lower()
        if source and source not in excluded_set:
            filtered.append(article)
    
    return filtered


def filter_by_time_window(
    articles: List[Dict],
    hours_back: Optional[int] = None,
    days_back: Optional[int] = None
) -> List[Dict]:
    """
    Filter articles by time window.
    
    Args:
        articles: List of article dictionaries
        hours_back: Filter articles from the last N hours (ignored if days_back is set)
        days_back: Filter articles from the last N days
        
    Returns:
        List of articles within the time window
    """
    if not days_back and not hours_back:
        return articles
    
    # Calculate cutoff time
    if days_back:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)
    else:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)
    
    filtered = []
    for article in articles:
        pub_date_str = article.get('publishedAt')
        pub_date = parse_datetime_safe(pub_date_str)
        
        # If we can't parse the date, include the article
        if pub_date is None:
            filtered.append(article)
            continue
        
        # Make both timezone-aware for comparison
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=datetime.timezone.utc)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=datetime.timezone.utc)
        
        if pub_date >= cutoff:
            filtered.append(article)
    
    return filtered


def limit_headlines(articles: List[Dict], max_count: Optional[int] = None) -> List[Dict]:
    """
    Limit the number of headlines returned.
    
    Args:
        articles: List of article dictionaries
        max_count: Maximum number of articles to return
        
    Returns:
        List of articles limited to max_count
    """
    if max_count is None or max_count <= 0:
        return articles
    
    return articles[:max_count]


def filter_news(
    articles: List[Dict],
    max_headlines: Optional[int] = None,
    excluded_sources: Optional[List[str]] = None,
    hours_back: Optional[int] = None,
    days_back: Optional[int] = None,
    remove_dups: bool = True
) -> List[Dict]:
    """
    Apply all news filters in order.
    
    Filters are applied in this order:
    1. Remove duplicates (by title)
    2. Exclude specified sources
    3. Filter by time window
    4. Limit headlines count
    
    Args:
        articles: List of article dictionaries
        max_headlines: Maximum number of articles to return
        excluded_sources: List of source names to exclude
        hours_back: Filter articles from the last N hours
        days_back: Filter articles from the last N days
        remove_dups: Whether to remove duplicates (default: True)
        
    Returns:
        Filtered list of articles
    """
    result = articles
    
    if remove_dups:
        result = remove_duplicates(result)
    
    result = exclude_sources(result, excluded_sources)
    result = filter_by_time_window(result, hours_back=hours_back, days_back=days_back)
    result = limit_headlines(result, max_count=max_headlines)
    
    return result
