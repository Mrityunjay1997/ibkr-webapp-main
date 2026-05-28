from scanner.ibkr_signal_engine import IBapi


def test_select_best_contract_symbol_match():
    contracts = [
        {"symbol": "AAPL", "exchange": "NYSE", "primaryExchange": ""},
        {"symbol": "MSFT", "exchange": "SMART", "primaryExchange": "NASDAQ"},
    ]

    selected = IBapi._select_best_contract(contracts, requested_symbol="MSFT")

    assert selected["symbol"] == "MSFT"


def test_select_best_contract_primary_exchange_preferred():
    contracts = [
        {"symbol": "AAPL", "exchange": "NYSE", "primaryExchange": ""},
        {"symbol": "AAPL", "exchange": "ARCA", "primaryExchange": "NASDAQ"},
    ]

    selected = IBapi._select_best_contract(contracts, requested_symbol="AAPL")

    assert selected["primaryExchange"] == "NASDAQ"


def test_select_best_contract_smart_fallback():
    contracts = [
        {"symbol": "AAPL", "exchange": "NYSE", "primaryExchange": ""},
        {"symbol": "AAPL", "exchange": "SMART", "primaryExchange": ""},
    ]

    selected = IBapi._select_best_contract(contracts, requested_symbol=None)

    assert selected["exchange"] == "SMART"


def test_select_best_contract_first_fallback():
    contracts = [
        {"symbol": "AAPL", "exchange": "NYSE", "primaryExchange": ""},
        {"symbol": "AAPL", "exchange": "ARCA", "primaryExchange": ""},
    ]

    selected = IBapi._select_best_contract(contracts, requested_symbol=None)

    assert selected is contracts[0]


def test_select_best_contract_empty():
    selected = IBapi._select_best_contract([], requested_symbol="AAPL")
    assert selected is None
