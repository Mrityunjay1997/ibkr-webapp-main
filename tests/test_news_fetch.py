import json
import datetime
import io
from ibkr_signal_engine import IBapi


def test_fetch_news_api_sort_desc(monkeypatch):
    api = IBapi()
    api.config.news_api_provider = 'newsapi'
    api.config.news_api_key = 'dummykey'

    sample_payload = {
        'status': 'ok',
        'totalResults': 3,
        'articles': [
            {
                'title': 'Old News',
                'url': 'http://old',
                'description': 'old',
                'publishedAt': '2026-03-20T09:00:00Z',
                'source': {'name': 'OldSource'}
            },
            {
                'title': 'New News',
                'url': 'http://new',
                'description': 'new',
                'publishedAt': '2026-03-27T09:05:00Z',
                'source': {'name': 'NewSource'}
            },
            {
                'title': 'Mid News',
                'url': 'http://mid',
                'description': 'mid',
                'publishedAt': '2026-03-27T09:03:00Z',
                'source': {'name': 'MidSource'}
            }
        ]
    }

    class DummyResp:
        def __enter__(self):
            self.buf = io.BytesIO(json.dumps(sample_payload).encode('utf-8'))
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            return self.buf.getvalue()

    def fake_urlopen(_url, timeout=20):
        return DummyResp()

    monkeypatch.setattr('urllib.request.urlopen', fake_urlopen)

    articles = api.fetch_news_for_symbol('AAPL', limit=3, lookback_days=7)

    assert len(articles) == 3
    assert articles[0]['title'] == 'New News'
    assert articles[1]['title'] == 'Mid News'
    assert articles[2]['title'] == 'Old News'
