import json
import os
import shutil
import pytest
from scanners import StockListManager


@pytest.fixture
def manager(tmp_path):
    return StockListManager(storage_dir=str(tmp_path / "stock_lists"))


def test_save_and_load(manager):
    result = manager.save("My Watchlist", ["AAPL", "MSFT", "TSLA"])
    assert result["success"] is True
    assert result["ticker_count"] == 3

    loaded = manager.load("My Watchlist")
    assert loaded["success"] is True
    assert loaded["tickers"] == ["AAPL", "MSFT", "TSLA"]
    assert loaded["list_name"] == "My Watchlist"


def test_save_deduplicates_and_uppercases(manager):
    result = manager.save("Dupes", ["aapl", "AAPL", "msft", "  msft  "])
    assert result["success"] is True
    assert result["ticker_count"] == 2

    loaded = manager.load("Dupes")
    assert loaded["tickers"] == ["AAPL", "MSFT"]


def test_save_empty_name_fails(manager):
    result = manager.save("", ["AAPL"])
    assert result["success"] is False


def test_save_empty_tickers_ok(manager):
    result = manager.save("Empty", [])
    assert result["success"] is True
    assert result["ticker_count"] == 0


def test_load_nonexistent_fails(manager):
    result = manager.load("DoesNotExist")
    assert result["success"] is False


def test_delete(manager):
    manager.save("ToDelete", ["GOOG"])
    result = manager.delete("ToDelete")
    assert result["success"] is True

    # Verify gone
    loaded = manager.load("ToDelete")
    assert loaded["success"] is False


def test_delete_nonexistent_fails(manager):
    result = manager.delete("Nope")
    assert result["success"] is False


def test_list_all(manager):
    manager.save("List A", ["AAPL", "MSFT"])
    manager.save("List B", ["TSLA"])

    result = manager.list_all()
    assert result["success"] is True
    assert len(result["lists"]) == 2

    names = [l["name"] for l in result["lists"]]
    assert "List A" in names
    assert "List B" in names

    for item in result["lists"]:
        if item["name"] == "List A":
            assert item["ticker_count"] == 2
        elif item["name"] == "List B":
            assert item["ticker_count"] == 1


def test_list_all_empty(manager):
    result = manager.list_all()
    assert result["success"] is True
    assert result["lists"] == []


def test_overwrite_existing_list(manager):
    manager.save("Evolving", ["AAPL"])
    manager.save("Evolving", ["AAPL", "GOOG", "META"])

    loaded = manager.load("Evolving")
    assert loaded["tickers"] == ["AAPL", "GOOG", "META"]
