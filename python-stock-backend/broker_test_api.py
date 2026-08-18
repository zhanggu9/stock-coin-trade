import requests

from flask import Blueprint, jsonify, request

from broker_test import BrokerApiError, check_kb_token, get_kis_quote


broker_test_bp = Blueprint("broker_test", __name__, url_prefix="/api/broker-test")


def _symbol() -> str:
    symbol = request.args.get("symbol", "005930").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.")
    return symbol


@broker_test_bp.get("/kis/quote")
def kis_quote():
    try:
        return jsonify({"ok": True, "quote": get_kis_quote(_symbol())})
    except BrokerApiError as exc:
        # A broker-side rejection is an expected test result, not a browser
        # transport failure. Returning 200 prevents an unnecessary console 502.
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@broker_test_bp.get("/kb/token")
def kb_token():
    try:
        return jsonify({"ok": True, "check": check_kb_token()})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "KB증권", "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "KB증권", "message": "KB증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503
