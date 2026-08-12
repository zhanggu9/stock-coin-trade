"""Read-only broker OpenAPI quote checks used by the local test web page.

Credentials stay on the Flask server. Values from key files are never returned
or logged; the browser only receives a small normalized quote or a safe error.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
SECRETS_DIR = Path(os.environ.get("BROKER_KEYS_DIR", "/run/secrets"))
KB_API_BASE_URL = "https://developer.kbsec.com:32484"
KIS_TESTBED_URL = "https://openapivts.koreainvestment.com:29443"
_kis_token_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}
_kis_token_lock = threading.Lock()
_kis_quote_cache: dict[str, dict[str, Any]] = {}
_kis_quote_lock = threading.Lock()


class BrokerApiError(RuntimeError):
    """A user-safe error that never includes credentials or access tokens."""


def _read_key_file(filename: str, key_names: tuple[str, ...], secret_names: tuple[str, ...]) -> tuple[str, str]:
    path = next((candidate for candidate in (SECRETS_DIR / filename, ROOT_DIR / filename) if candidate.is_file()), None)
    if path is None:
        raise BrokerApiError(f"{filename} 파일을 찾을 수 없습니다.")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line:
            continue
        name, value = raw_line.split("=", 1)
        values[name.strip().lower().replace("-", "_")] = value.strip()
    app_key = next((values.get(name) for name in key_names if values.get(name)), None)
    app_secret = next((values.get(name) for name in secret_names if values.get(name)), None)
    if not app_key or not app_secret:
        raise BrokerApiError(f"{filename}에 App Key와 Secret을 설정하세요.")
    return app_key, app_secret


def _credentials(prefix: str, filename: str, key_names: tuple[str, ...], secret_names: tuple[str, ...]) -> tuple[str, str]:
    app_key = os.environ.get(f"{prefix}_APP_KEY")
    app_secret = os.environ.get(f"{prefix}_APP_SECRET")
    if app_key and app_secret:
        return app_key, app_secret
    return _read_key_file(filename, key_names, secret_names)


def _json(response: requests.Response, broker: str) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as exc:
        raise BrokerApiError(f"{broker} 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc


def _kb_token() -> str:
    app_key, app_secret = _credentials("KB", "kb.key", ("appkey", "app_key"), ("secret", "appsecret", "app_secret"))
    response = requests.post(
        f"{KB_API_BASE_URL}/oauth2/token",
        headers={"Content-Type": "application/json"},
        json={"grant_type": "client_credentials", "appKey": app_key, "appSecret": app_secret},
        timeout=20,
    )
    body = _json(response, "KB증권")
    token = body.get("access_token") or body.get("dataBody", {}).get("access_token")
    if token:
        return token
    header = body.get("dataHeader", {})
    code = header.get("processCode") or body.get("error") or body.get("code") or "unknown"
    message = header.get("processMessage") or body.get("error_description") or body.get("message") or "토큰 발급 실패"
    raise BrokerApiError(f"KB증권 인증 실패 (HTTP {response.status_code}, {code}): {message}")


def get_kb_quote(symbol: str) -> dict[str, Any]:
    """Validate the KB key before using its quote API.

    KB's quote URI and required API group are issued per approved service. The
    current project key is rejected by KB at OAuth, so no unverified quote URI is
    guessed or called. When approved, the route reports the missing configuration
    rather than risking a call to an unrelated endpoint.
    """
    _kb_token()
    raise BrokerApiError(
        "KB증권 인증은 성공했지만 이 프로젝트에는 포털에서 승인된 시세 API 경로/API 그룹 설정이 없습니다. "
        "최신 KB Open API 문서의 현재가 조회 API를 설정한 뒤 연결하세요."
    )


def get_kis_quote(symbol: str) -> dict[str, Any]:
    with _kis_quote_lock:
        cached_quote = _kis_quote_cache.get(symbol)
        if cached_quote and cached_quote["expires_at"] > time.time():
            return cached_quote["quote"]

    app_key, app_secret = _credentials("KIS", "kis.key", ("app_key",), ("secret", "app_secret"))
    with _kis_token_lock:
        access_token = _kis_token_cache["value"] if _kis_token_cache["expires_at"] > time.time() else None
        if not access_token:
            token_response = requests.post(
                f"{KIS_TESTBED_URL}/oauth2/tokenP",
                headers={"content-type": "application/json; charset=utf-8"},
                json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
                timeout=15,
            )
            token_body = _json(token_response, "한국투자증권")
            access_token = token_body.get("access_token")
            if not access_token:
                message = token_body.get("error_description") or token_body.get("msg1") or "토큰 발급 실패"
                raise BrokerApiError(f"한국투자증권 인증 실패 (HTTP {token_response.status_code}): {message}")
            # KIS tokens are normally valid for a day. Keep a conservative
            # expiry margin and avoid the Testbed's one-token-per-minute limit.
            expires_in = int(token_body.get("expires_in", 86400))
            _kis_token_cache.update(value=access_token, expires_at=time.time() + max(60, expires_in - 60))

    quote_response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": "FHKST01010100",
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        timeout=15,
    )
    body = _json(quote_response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 시세 조회 실패 (HTTP {quote_response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    output = body.get("output", {})
    quote = {
        "broker": "한국투자증권 Testbed", "symbol": symbol,
        "price": output.get("stck_prpr"), "change": output.get("prdy_vrss"),
        "changeRate": output.get("prdy_ctrt"), "volume": output.get("acml_vol"),
        "tradeTime": output.get("stck_cntg_hour"),
    }
    # Testbed rejects bursts at the per-second limit. A short cache makes a
    # double click safe without presenting stale data as a long-lived quote.
    with _kis_quote_lock:
        _kis_quote_cache[symbol] = {"quote": quote, "expires_at": time.time() + 3}
    return quote
