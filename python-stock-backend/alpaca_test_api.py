import requests

from flask import Blueprint, jsonify

from alpaca_test import test_paper_account
from broker_test import BrokerApiError


alpaca_test_bp = Blueprint("alpaca_test", __name__, url_prefix="/api/alpaca-test")


@alpaca_test_bp.get("/paper/account")
def paper_account():
    try:
        return jsonify({"ok": True, "result": test_paper_account()})
    except BrokerApiError as exc:
        # Credential rejection is an expected test outcome, not a browser error.
        return jsonify({"ok": False, "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "message": "Alpaca Paper 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503
