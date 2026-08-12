"""Server-side, read-only Alpaca Paper Trading connection test."""

from __future__ import annotations

import os
from typing import Any

import requests

from broker_test import BrokerApiError, _read_key_file


ALPACA_PAPER_URL = "https://paper-api.alpaca.markets/v2/account"


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


def test_paper_account() -> dict[str, Any]:
    """Call the read-only Paper account endpoint and return no account identifier."""
    api_key, secret_key = _credentials()
    response = requests.get(
        ALPACA_PAPER_URL,
        headers={"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key},
        timeout=15,
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise BrokerApiError(f"Alpaca 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
    if not response.ok:
        message = body.get("message") or body.get("code") or "계정 조회가 거부되었습니다."
        raise BrokerApiError(f"Alpaca Paper API 인증 실패 (HTTP {response.status_code}): {message}")
    return {
        "environment": "Paper Trading",
        "connection": "connected",
        "accountStatus": body.get("status"),
        "tradingBlocked": bool(body.get("trading_blocked")),
        "accountBlocked": bool(body.get("account_blocked")),
        "currency": body.get("currency"),
    }
