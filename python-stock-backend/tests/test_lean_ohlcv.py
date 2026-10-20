from datetime import date

import pytest

from app.services import lean_ohlcv


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def make_row(trade_date, close):
    return {
        "trade_date": trade_date,
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "adj_close": close,
        "volume": 1000,
    }


def test_fetch_ohlcv_history_paginates_and_orders_rows(monkeypatch):
    monkeypatch.setenv("OHLCV_API_BASE_URL", "http://127.0.0.1:8010")
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, dict(params), dict(headers), timeout))
        if params["offset"] == 0:
            return FakeResponse({
                "ticker": {"ticker_code": "005930", "name": "삼성전자", "market": "KOSPI"},
                "rows": [make_row("2024-01-03", 103), make_row("2024-01-02", 102)],
                "total": 3,
                "limit": 1000,
                "offset": 0,
                "nextOffset": 2,
            })
        return FakeResponse({
            "ticker": {"ticker_code": "005930", "name": "삼성전자", "market": "KOSPI"},
            "rows": [make_row("2024-01-04", 104)],
            "total": 3,
            "limit": 1000,
            "offset": 2,
            "nextOffset": None,
        })

    monkeypatch.setattr(lean_ohlcv.requests, "get", fake_get)
    ticker, rows, pages = lean_ohlcv.fetch_ohlcv_history(
        "005930", date(2024, 1, 1), date(2024, 1, 31)
    )

    assert ticker["name"] == "삼성전자"
    assert [row["trade_date"] for row in rows] == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert len(calls) == 2
    assert [call[1]["offset"] for call in calls] == [0, 2]
    assert calls[0][1]["limit"] == 1000
    assert calls[0][1]["order"] == "asc"
    assert calls[0][1]["date_from"] == "2024-01-01"
    assert calls[0][1]["date_to"] == "2024-01-31"
    assert "Authorization" not in calls[0][2]
    assert pages == 2


def test_fetch_ohlcv_history_uses_optional_bearer_token(monkeypatch):
    monkeypatch.setenv("OHLCV_API_BASE_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("OHLCV_API_TOKEN", "test-token")
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(dict(headers))
        return FakeResponse({
            "ticker": {"ticker_code": "005930", "name": "삼성전자"},
            "rows": [make_row("2024-01-02", 102), make_row("2024-01-03", 103)],
            "total": 2,
            "nextOffset": None,
        })

    monkeypatch.setattr(lean_ohlcv.requests, "get", fake_get)
    _, rows, pages = lean_ohlcv.fetch_ohlcv_history("005930", "2024-01-01", "2024-01-31")

    assert len(rows) == 2
    assert pages == 1
    assert calls[0]["Authorization"] == "Bearer test-token"


def test_fetch_ohlcv_history_rejects_invalid_ohlcv(monkeypatch):
    monkeypatch.setenv("OHLCV_API_BASE_URL", "http://127.0.0.1:8010")
    row = make_row("2024-01-02", 102)
    row["high"] = 100
    monkeypatch.setattr(
        lean_ohlcv.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({
            "ticker": {"ticker_code": "005930", "name": "삼성전자"},
            "rows": [row, make_row("2024-01-03", 103)],
            "total": 2,
            "nextOffset": None,
        }),
    )

    with pytest.raises(lean_ohlcv.OHLCVBacktestError) as exc:
        lean_ohlcv.fetch_ohlcv_history("005930", "2024-01-01", "2024-01-31")

    assert exc.value.status_code == 422
