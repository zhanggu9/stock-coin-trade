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


def _kb_token_response() -> dict[str, Any]:
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
        return body
    header = body.get("dataHeader", {})
    code = header.get("processCode") or body.get("error") or body.get("code") or "unknown"
    message = header.get("processMessage") or body.get("error_description") or body.get("message") or "토큰 발급 실패"
    raise BrokerApiError(f"KB증권 인증 실패 (HTTP {response.status_code}, {code}): {message}")


def check_kb_token() -> dict[str, Any]:
    """Verify KB Open API OAuth token issuance only.

    KB's quote API requires a portal-approved API group that this project does
    not currently have, so the connection test is limited to confirming that
    AppKey/AppSecret correctly issue an access token — mirroring kb_token_test.py.
    """
    body = _kb_token_response()
    token_type = body.get("token_type") or body.get("dataBody", {}).get("token_type") or "Bearer"
    expires_in = body.get("expires_in") or body.get("dataBody", {}).get("expires_in") or 0
    return {"broker": "KB증권 Open API", "tokenType": token_type, "expiresIn": int(expires_in)}


def get_kb_domestic_quote(symbol: str) -> dict[str, Any]:
    """Call KB's domestic-stock quote API once the portal-approved path is known.

    KB only documents OAuth (/oauth2/token) in the crawlable guide; the quote
    endpoint path/tr_id are issued per approved service and are not guessed
    here (an unverified URL could hit an unrelated, unintended endpoint). Once
    approved, set KB_QUOTE_PATH (e.g. "/uapi/domestic-stock/v1/quotations/...")
    and KB_QUOTE_TR_ID from the portal's API spec to activate this check.
    """
    quote_path = os.environ.get("KB_QUOTE_PATH")
    tr_id = os.environ.get("KB_QUOTE_TR_ID")
    if not quote_path or not tr_id:
        raise BrokerApiError(
            "KB증권 현재가 API 경로가 아직 설정되지 않았습니다. 포털에서 승인된 API 스펙을 확인한 뒤 "
            "KB_QUOTE_PATH, KB_QUOTE_TR_ID 환경변수를 설정하세요."
        )
    app_key, app_secret = _credentials("KB", "kb.key", ("appkey", "app_key"), ("secret", "appsecret", "app_secret"))
    token_body = _kb_token_response()
    access_token = token_body.get("access_token") or token_body.get("dataBody", {}).get("access_token")
    response = requests.get(
        f"{KB_API_BASE_URL}{quote_path}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": tr_id,
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        timeout=20,
    )
    body = _json(response, "KB증권")
    output = body.get("output", body.get("dataBody", {}))
    return {"broker": "KB증권 Open API", "symbol": symbol, "raw": output}


def _kis_credentials() -> tuple[str, str]:
    return _credentials("KIS", "kis.key", ("app_key",), ("secret", "app_secret"))


def _kis_account() -> tuple[str, str]:
    account_no = os.environ.get("KIS_ACCOUNT_NO")
    if not account_no:
        values: dict[str, str] = {}
        path = next((c for c in (SECRETS_DIR / "kis.key", ROOT_DIR / "kis.key") if c.is_file()), None)
        if path is not None:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                if "=" not in raw_line:
                    continue
                name, value = raw_line.split("=", 1)
                values[name.strip().lower().replace("-", "_")] = value.strip()
            account_no = values.get("account") or values.get("account_no") or values.get("cano")
    if not account_no or "-" not in account_no:
        raise BrokerApiError(
            "모의투자 계좌번호가 설정되지 않았습니다. KIS_ACCOUNT_NO 환경변수 또는 kis.key의 account 항목에 "
            "'CANO-계좌상품코드'(예: 12345678-01) 형식으로 설정하세요."
        )
    cano, _, acnt_prdt_cd = account_no.partition("-")
    return cano, acnt_prdt_cd


def _kis_access_token() -> str:
    app_key, app_secret = _kis_credentials()
    with _kis_token_lock:
        access_token = _kis_token_cache["value"] if _kis_token_cache["expires_at"] > time.time() else None
        if access_token:
            return access_token
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
        return access_token


def _kis_headers(tr_id: str) -> dict[str, str]:
    app_key, app_secret = _kis_credentials()
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {_kis_access_token()}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }


def get_kis_quote(symbol: str) -> dict[str, Any]:
    with _kis_quote_lock:
        cached_quote = _kis_quote_cache.get(symbol)
        if cached_quote and cached_quote["expires_at"] > time.time():
            return cached_quote["quote"]

    quote_response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers=_kis_headers("FHKST01010100"),
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


def get_kis_balance() -> dict[str, Any]:
    """Read-only 모의투자 계좌 잔고/평가액 조회 (inquire-balance, VTTC8434R)."""
    cano, acnt_prdt_cd = _kis_account()
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=_kis_headers("VTTC8434R"),
        params={
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        },
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 잔고 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    summary = (body.get("output2") or [{}])[0]
    holdings = [
        {
            "symbol": item.get("pdno"), "name": item.get("prdt_name"),
            "quantity": item.get("hldg_qty"), "avgPrice": item.get("pchs_avg_pric"),
            "evalAmount": item.get("evlu_amt"), "profitLoss": item.get("evlu_pfls_amt"),
            "profitLossRate": item.get("evlu_pfls_rt"),
        }
        for item in (body.get("output1") or []) if item.get("pdno")
    ]
    return {
        "broker": "한국투자증권 Testbed",
        "cashBalance": summary.get("dnca_tot_amt"),
        "totalEvalAmount": summary.get("tot_evlu_amt"),
        "totalProfitLoss": summary.get("evlu_pfls_smtl_amt"),
        "holdingsCount": len(holdings),
        "holdings": holdings,
    }


def get_kis_daily_chart(symbol: str, days: int = 20) -> dict[str, Any]:
    """Read-only 일봉 캔들 조회 (inquire-daily-itemchartprice, FHKST03010100)."""
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.localtime(time.time() - days * 4 * 86400))
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        headers=_kis_headers("FHKST03010100"),
        params={
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start, "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1",
        },
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 일봉 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    candles = [
        {
            "date": row.get("stck_bsop_date"), "open": row.get("stck_oprc"),
            "high": row.get("stck_hgpr"), "low": row.get("stck_lwpr"),
            "close": row.get("stck_clpr"), "volume": row.get("acml_vol"),
        }
        for row in (body.get("output2") or [])[:days]
    ]
    return {"broker": "한국투자증권 Testbed", "symbol": symbol, "candles": candles}


def get_kis_orderbook(symbol: str) -> dict[str, Any]:
    """Read-only 매도/매수 10단계 호가 조회 (inquire-asking-price-exp-ccn, FHKST01010200)."""
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
        headers=_kis_headers("FHKST01010200"),
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 호가 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    output1 = body.get("output1") or {}
    levels = [
        {
            "level": n,
            "askPrice": output1.get(f"askp{n}"), "askQty": output1.get(f"askp_rsqn{n}"),
            "bidPrice": output1.get(f"bidp{n}"), "bidQty": output1.get(f"bidp_rsqn{n}"),
        }
        for n in range(1, 11)
    ]
    return {
        "broker": "한국투자증권 Testbed", "symbol": symbol, "levels": levels,
        "totalAskQty": output1.get("total_askp_rsqn"), "totalBidQty": output1.get("total_bidp_rsqn"),
    }


_KIS_INDEX_NAMES = {"0001": "코스피", "1001": "코스닥"}


def get_kis_index(index_code: str = "0001") -> dict[str, Any]:
    """Read-only 업종 현재지수 조회 (inquire-index-price, FHPUP02100000). 0001=코스피, 1001=코스닥."""
    response = requests.get(
        f"{KIS_TESTBED_URL}/uapi/domestic-stock/v1/quotations/inquire-index-price",
        headers=_kis_headers("FHPUP02100000"),
        params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code},
        timeout=15,
    )
    body = _json(response, "한국투자증권")
    if body.get("rt_cd") != "0":
        raise BrokerApiError(
            f"한국투자증권 지수 조회 실패 (HTTP {response.status_code}, {body.get('msg_cd')}): {body.get('msg1')}"
        )
    output = body.get("output", {})
    return {
        "broker": "한국투자증권 Testbed", "index": _KIS_INDEX_NAMES.get(index_code, index_code),
        "price": output.get("bstp_nmix_prpr"), "change": output.get("bstp_nmix_prdy_vrss"),
        "changeRate": output.get("bstp_nmix_prdy_ctrt"), "volume": output.get("acml_vol"),
    }
