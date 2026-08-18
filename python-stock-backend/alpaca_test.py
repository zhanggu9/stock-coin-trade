"""Server-side, read-only Alpaca Paper Trading connection test."""

from __future__ import annotations

import os
from typing import Any

import requests

from broker_test import BrokerApiError, _read_key_file


ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_BASE = "https://data.alpaca.markets/v2"


def _credentials() -> tuple[str, str]:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if api_key and secret_key:
        return api_key, secret_key
    return _read_key_file(
        "al.key",
        ("key", "api_key", "alpaca_api_key", "apca_api_key_id"),
        ("secret", "secret_key", "alpaca_secret_key", "apca_api_secret_key"),
    )


def _headers() -> dict[str, str]:
    api_key, secret_key = _credentials()
    return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, headers=_headers(), params=params, timeout=15)
    try:
        body = response.json()
    except ValueError as exc:
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "요청이 거부되었습니다."
        raise BrokerApiError(f"Alpaca API 인증 실패 (HTTP {response.status_code}): {message}")
    return body


def test_paper_account() -> dict[str, Any]:
    """Call the read-only Paper account endpoint and return no account identifier."""
    body = _get(f"{ALPACA_PAPER_BASE}/account")
    return {
        "environment": "Paper Trading",
        "connection": "connected",
        "accountStatus": body.get("status"),
        "tradingBlocked": bool(body.get("trading_blocked")),
        "accountBlocked": bool(body.get("account_blocked")),
        "currency": body.get("currency"),
    }


def test_paper_positions() -> dict[str, Any]:
    """Read-only 보유 포지션 조회 (GET /v2/positions)."""
    body = _get(f"{ALPACA_PAPER_BASE}/positions")
    positions = [
        {
            "symbol": p.get("symbol"), "side": p.get("side"), "quantity": p.get("qty"),
            "avgEntryPrice": p.get("avg_entry_price"), "currentPrice": p.get("current_price"),
            "marketValue": p.get("market_value"), "unrealizedPl": p.get("unrealized_pl"),
            "unrealizedPlpc": p.get("unrealized_plpc"),
        }
        for p in body
    ]
    return {"environment": "Paper Trading", "positionCount": len(positions), "positions": positions}


def test_paper_orders(limit: int = 10) -> dict[str, Any]:
    """Read-only 최근 주문 내역 조회 (GET /v2/orders?status=all)."""
    body = _get(f"{ALPACA_PAPER_BASE}/orders", params={"status": "all", "limit": limit, "direction": "desc"})
    orders = [
        {
            "symbol": o.get("symbol"), "side": o.get("side"), "type": o.get("type"),
            "quantity": o.get("qty"), "status": o.get("status"),
            "filledAvgPrice": o.get("filled_avg_price"), "submittedAt": o.get("submitted_at"),
        }
        for o in body
    ]
    return {"environment": "Paper Trading", "orderCount": len(orders), "orders": orders}


def test_market_clock() -> dict[str, Any]:
    """Read-only 미국 증시 개장 여부 조회 (GET /v2/clock)."""
    body = _get(f"{ALPACA_PAPER_BASE}/clock")
    return {
        "isOpen": bool(body.get("is_open")), "timestamp": body.get("timestamp"),
        "nextOpen": body.get("next_open"), "nextClose": body.get("next_close"),
    }


def test_market_quote(symbol: str) -> dict[str, Any]:
    """Read-only 최근 호가·체결 조회 (Market Data API, /v2/stocks/{symbol}/quotes|trades/latest)."""
    symbol = symbol.upper()
    quote_body = _get(f"{ALPACA_DATA_BASE}/stocks/{symbol}/quotes/latest")
    trade_body = _get(f"{ALPACA_DATA_BASE}/stocks/{symbol}/trades/latest")
    quote = quote_body.get("quote", {})
    trade = trade_body.get("trade", {})
    return {
        "symbol": symbol,
        "bidPrice": quote.get("bp"), "bidSize": quote.get("bs"),
        "askPrice": quote.get("ap"), "askSize": quote.get("as"),
        "lastTradePrice": trade.get("p"), "lastTradeSize": trade.get("s"),
        "lastTradeTime": trade.get("t"),
    }
