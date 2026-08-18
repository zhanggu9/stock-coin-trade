import requests

from flask import Blueprint, jsonify, request

from alpaca_test import (
    test_market_clock,
    test_market_quote,
    test_paper_account,
    test_paper_orders,
    test_paper_positions,
)
from broker_test import BrokerApiError


alpaca_test_bp = Blueprint("alpaca_test", __name__, url_prefix="/api/alpaca-test")


def _run(build):
    try:
        return jsonify({"ok": True, "result": build()})
    except BrokerApiError as exc:
        # Credential rejection is an expected test outcome, not a browser error.
        return jsonify({"ok": False, "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "message": "Alpaca 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@alpaca_test_bp.get("/paper/account")
def paper_account():
    return _run(test_paper_account)


@alpaca_test_bp.get("/paper/positions")
def paper_positions():
    return _run(test_paper_positions)


@alpaca_test_bp.get("/paper/orders")
def paper_orders():
    return _run(test_paper_orders)


@alpaca_test_bp.get("/market/clock")
def market_clock():
    return _run(test_market_clock)


@alpaca_test_bp.get("/market/quote")
def market_quote():
    symbol = request.args.get("symbol", "AAPL").strip()
    if not symbol.isalpha() or not (1 <= len(symbol) <= 5):
        return jsonify({"ok": False, "message": "symbol은 1~5자리 영문 티커여야 합니다."})
    return _run(lambda: test_market_quote(symbol))
