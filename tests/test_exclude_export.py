import __init__ as appmod


def test_exclude_export_csv_returns_download():
    client = appmod.app.test_client()

    response = client.get("/exclude/export-csv")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "excluded_stocks.csv" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"\xef\xbb\xbfSymbol")
