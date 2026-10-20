"""Fetch paginated OHLCV JSON from pg-stock and run a LEAN backtest without CSV."""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import tempfile
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

DEFAULT_OHLCV_API_BASE_URL = "http://43.202.161.134:8010"
OHLCV_PAGE_SIZE = 1000
MAX_OHLCV_ROWS = 20000
REQUEST_TIMEOUT = (4, 20)
LEAN_IMAGE_TAG = os.environ.get(
    "LEAN_DOCKER_IMAGE",
    "quantconnect/lean@sha256:70071d1bbb90385deb60c7d20bc3830c7f4c79f6c09c5d1ade9196c009f68861",
)
LEAN_RUNNER = os.environ.get("LEAN_RUNNER", "remote")
LEAN_BUILD_CONTEXT = "/lean-src"
LEAN_TIMEOUT_SECONDS = 180
_TICKER_RE = re.compile(r"^[0-9A-Za-z._-]{1,20}$")
_runner_lock = threading.Lock()


class OHLCVBacktestError(Exception):
    """HTTP-friendly failure raised by API loading or LEAN execution."""

    def __init__(self, status_code: int, message: str, **extra):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.extra = extra


def _as_date(value: str | date, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise OHLCVBacktestError(400, f"{field}는 YYYY-MM-DD 형식이어야 합니다.") from exc


def _api_base_url() -> str:
    raw = os.environ.get("OHLCV_API_BASE_URL", DEFAULT_OHLCV_API_BASE_URL).strip().rstrip("/")
    parsed = urlparse(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise OHLCVBacktestError(503, "OHLCV_API_BASE_URL 설정이 올바르지 않습니다.")
    return raw


def _normalize_row(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise OHLCVBacktestError(502, "OHLCV API rows 항목이 객체가 아닙니다.")
    try:
        trade_date = date.fromisoformat(str(raw["trade_date"])[:10]).isoformat()
        values = {key: float(raw[key]) for key in ("open", "high", "low", "close", "volume")}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise OHLCVBacktestError(502, "OHLCV API 응답에 날짜 또는 필수 가격 필드가 없습니다.") from exc

    if not all(math.isfinite(value) for value in values.values()):
        raise OHLCVBacktestError(422, f"{trade_date} 행에 유효하지 않은 숫자가 있습니다.")
    if min(values["open"], values["high"], values["low"], values["close"]) <= 0 or values["volume"] < 0:
        raise OHLCVBacktestError(422, f"{trade_date} 행의 OHLCV 값이 허용 범위를 벗어났습니다.")
    if (
        values["low"] > values["high"]
        or values["low"] > min(values["open"], values["close"])
        or values["high"] < max(values["open"], values["close"])
    ):
        raise OHLCVBacktestError(422, f"{trade_date} 행의 고가·저가와 시가·종가 관계가 올바르지 않습니다.")

    adjusted = raw.get("adj_close")
    try:
        adjusted = float(adjusted) if adjusted is not None else None
    except (TypeError, ValueError, OverflowError) as exc:
        raise OHLCVBacktestError(422, f"{trade_date} 행의 adj_close 값이 올바르지 않습니다.") from exc
    if adjusted is not None and (not math.isfinite(adjusted) or adjusted <= 0):
        adjusted = None

    return {
        "trade_date": trade_date,
        "open": values["open"],
        "high": values["high"],
        "low": values["low"],
        "close": values["close"],
        "adj_close": adjusted,
        "volume": values["volume"],
    }


def fetch_ohlcv_history(ticker_code: str, date_from: str | date, date_to: str | date) -> tuple[dict, list[dict], int]:
    """Read the API's ticker/rows/total/nextOffset response until every page is loaded."""
    code = str(ticker_code or "").strip().upper()
    if not _TICKER_RE.fullmatch(code):
        raise OHLCVBacktestError(400, "ticker_code 형식이 올바르지 않습니다.")

    start = _as_date(date_from, "date_from")
    end = _as_date(date_to, "date_to")
    if start > end:
        raise OHLCVBacktestError(400, "date_from은 date_to보다 늦을 수 없습니다.")

    base_url = _api_base_url()
    url = f"{base_url}/openapi/v1/ohlcv/{code}"
    headers = {"Accept": "application/json"}
    optional_token = os.environ.get("OHLCV_API_TOKEN", "").strip()
    if optional_token:
        headers["Authorization"] = f"Bearer {optional_token}"

    offset = 0
    pages = 0
    total: int | None = None
    ticker: dict = {"ticker_code": code, "name": code, "market": None}
    unique_rows: dict[str, dict] = {}

    while True:
        params = {
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "order": "asc",
            "limit": OHLCV_PAGE_SIZE,
            "offset": offset,
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise OHLCVBacktestError(502, f"OHLCV API에 연결하지 못했습니다: {exc}") from exc

        if response.status_code == 429:
            raise OHLCVBacktestError(429, "OHLCV API의 IP별 호출 제한에 도달했습니다. 잠시 후 다시 실행하세요.")
        if response.status_code in {401, 403}:
            raise OHLCVBacktestError(
                502,
                "OHLCV 조회 API가 인증 오류를 반환했습니다. 배포 설정이 바뀌었다면 OHLCV_API_TOKEN을 확인하세요.",
            )
        if response.status_code == 404:
            raise OHLCVBacktestError(404, f"OHLCV API에서 종목 {code}을(를) 찾지 못했습니다.")
        if response.status_code < 200 or response.status_code >= 300:
            raise OHLCVBacktestError(502, f"OHLCV API가 HTTP {response.status_code}를 반환했습니다.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise OHLCVBacktestError(502, "OHLCV API 응답이 유효한 JSON이 아닙니다.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
            raise OHLCVBacktestError(502, "OHLCV API 응답에 rows 배열이 없습니다.")

        if isinstance(payload.get("ticker"), dict):
            ticker = {**ticker, **payload["ticker"]}
        try:
            page_total = int(payload.get("total", len(payload["rows"])))
        except (TypeError, ValueError) as exc:
            raise OHLCVBacktestError(502, "OHLCV API의 total 값이 올바르지 않습니다.") from exc
        if page_total < 0 or page_total > MAX_OHLCV_ROWS:
            raise OHLCVBacktestError(
                413,
                f"요청 구간 데이터가 너무 많습니다(최대 {MAX_OHLCV_ROWS:,}개 행). 날짜 범위를 줄여주세요.",
            )
        if total is None:
            total = page_total
        elif page_total != total:
            raise OHLCVBacktestError(502, "페이지 조회 중 OHLCV API의 total 값이 변경되었습니다.")

        raw_rows = payload["rows"]
        pages += 1
        for raw in raw_rows:
            row = _normalize_row(raw)
            if start.isoformat() <= row["trade_date"] <= end.isoformat():
                unique_rows[row["trade_date"]] = row

        if not raw_rows:
            if total and offset < total:
                raise OHLCVBacktestError(502, "OHLCV API가 total보다 적은 행을 반환해 페이지 조회를 중단했습니다.")
            break

        next_offset = payload.get("nextOffset")
        if next_offset is None:
            expected_offset = offset + len(raw_rows)
            if expected_offset < total:
                next_offset = expected_offset
            else:
                break
        try:
            next_offset = int(next_offset)
        except (TypeError, ValueError) as exc:
            raise OHLCVBacktestError(502, "OHLCV API의 nextOffset 값이 올바르지 않습니다.") from exc
        if next_offset <= offset or next_offset > MAX_OHLCV_ROWS:
            raise OHLCVBacktestError(502, "OHLCV API의 nextOffset이 진행되지 않아 페이지 조회를 중단했습니다.")
        offset = next_offset

    rows = [unique_rows[key] for key in sorted(unique_rows)]
    if not rows:
        raise OHLCVBacktestError(422, f"{code} 종목의 지정한 기간에 백테스트할 OHLCV 데이터가 없습니다.")
    return ticker, rows, pages


def _run_remote_ohlcv(rows: list[dict], ticker_code: str, ticker_name: str, initial_cash: float) -> dict:
    key = os.environ.get("LEAN_SSH_KEY_PATH", "")
    host = os.environ.get("LEAN_SSH_HOST", "")
    user = os.environ.get("LEAN_SSH_USER", "lean-iv")
    if not host or not os.path.isfile(key):
        raise OHLCVBacktestError(503, "공통 LEAN 원격 러너 설정이 없습니다.")

    work_root = os.environ.get("LEAN_REMOTE_WORKDIR", "/home/lean-iv/workflows").rstrip("/")
    if not re.fullmatch(r"/[A-Za-z0-9_/-]+", work_root):
        raise OHLCVBacktestError(503, "LEAN 작업 경로 설정이 올바르지 않습니다.")

    work_id = "ohlcv-" + uuid.uuid4().hex
    remote = f"{work_root}/{work_id}"
    container = "lean-" + work_id
    options = [
        "-i", key, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "UserKnownHostsFile=/run/secrets/lean-known-hosts", "-o", "ConnectTimeout=15",
    ]
    target = f"{user}@{host}"

    def ssh(command: str, timeout: int = 30):
        return subprocess.run(["ssh", *options, target, command], capture_output=True, text=True, timeout=timeout)

    def copy(source: str, destination: str):
        result = subprocess.run(
            ["scp", *options, source, destination],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            raise OHLCVBacktestError(502, "LEAN 파일 전송에 실패했습니다.", log=result.stderr[-1500:])

    for filename in ("OHLCVJsonBacktest.py", "ohlcv_api_config.json", "ohlcv_api_entrypoint.sh"):
        if not Path(LEAN_BUILD_CONTEXT, filename).is_file():
            raise OHLCVBacktestError(503, f"LEAN 어댑터 파일이 없습니다: {filename}")

    try:
        check = ssh(
            f"docker image inspect {shlex.quote(LEAN_IMAGE_TAG)} >/dev/null "
            f"&& mkdir -p {shlex.quote(remote)}/module {shlex.quote(remote)}/data {shlex.quote(remote)}/results"
        )
        if check.returncode:
            raise OHLCVBacktestError(502, "공통 LEAN 엔진 연결에 실패했습니다.", log=check.stderr[-1500:])

        with tempfile.TemporaryDirectory(prefix="lean-ohlcv-") as temp_dir:
            data_path = Path(temp_dir, "ohlcv.jsonl")
            with data_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

            for filename in ("OHLCVJsonBacktest.py", "ohlcv_api_config.json", "ohlcv_api_entrypoint.sh"):
                copy(str(Path(LEAN_BUILD_CONTEXT, filename)), f"{target}:{remote}/module/{filename}")
            copy(str(data_path), f"{target}:{remote}/data/ohlcv.jsonl")

            env_values = {
                "TICKER_CODE": ticker_code,
                "TICKER_NAME": ticker_name[:80],
                "INITIAL_CASH": str(initial_cash),
            }
            env_flags = " ".join(
                f"-e {shlex.quote(f'{key}={value}')}" for key, value in env_values.items()
            )
            command = (
                f"docker run --rm --network none --cpus 2 --memory 2g --name {shlex.quote(container)} "
                f"{env_flags} "
                f"-v {shlex.quote(remote)}/module:/module:ro "
                f"-v {shlex.quote(remote)}/data:/custom-data:ro "
                f"-v {shlex.quote(remote)}/results:/results "
                f"--entrypoint sh {shlex.quote(LEAN_IMAGE_TAG)} /module/ohlcv_api_entrypoint.sh"
            )
            run = ssh(command, LEAN_TIMEOUT_SECONDS)
            if run.returncode:
                raise OHLCVBacktestError(
                    502,
                    "LEAN 백테스트 프로세스가 오류로 종료되었습니다.",
                    log=(run.stdout + "\n" + run.stderr)[-2500:],
                )

            local_summary = Path(temp_dir, "OHLCVJsonBacktest-summary.json")
            copy(f"{target}:{remote}/results/OHLCVJsonBacktest-summary.json", str(local_summary))
            try:
                with local_summary.open(encoding="utf-8") as handle:
                    statistics = (json.load(handle) or {}).get("statistics") or {}
            except (OSError, ValueError) as exc:
                raise OHLCVBacktestError(502, "LEAN 결과 JSON을 읽을 수 없습니다.") from exc
            if not statistics:
                raise OHLCVBacktestError(
                    502,
                    "LEAN 통계가 생성되지 않았습니다.",
                    log=(run.stdout + "\n" + run.stderr)[-2500:],
                )
            return statistics
    except subprocess.TimeoutExpired as exc:
        raise OHLCVBacktestError(
            504, f"LEAN 백테스트가 {LEAN_TIMEOUT_SECONDS}초 안에 끝나지 않았습니다."
        ) from exc
    finally:
        try:
            ssh(
                f"docker rm -f {shlex.quote(container)} >/dev/null 2>&1; "
                f"rm -rf {shlex.quote(remote)}",
                30,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass


def run_backtest(
    ticker_code: str,
    date_from: str | date,
    date_to: str | date,
    initial_cash: float | int = 1_000_000,
) -> dict:
    """Fetch API data, stage it as JSON Lines, and execute the isolated LEAN runner."""
    try:
        cash = float(initial_cash)
    except (TypeError, ValueError, OverflowError) as exc:
        raise OHLCVBacktestError(400, "initial_cash는 양수 숫자여야 합니다.") from exc
    if not math.isfinite(cash) or cash <= 0 or cash > 1_000_000_000_000:
        raise OHLCVBacktestError(400, "initial_cash는 0 초과, 1조 이하의 숫자여야 합니다.")

    start = _as_date(date_from, "date_from")
    end = _as_date(date_to, "date_to")
    if start > end:
        raise OHLCVBacktestError(400, "date_from은 date_to보다 늦을 수 없습니다.")

    ticker, rows, pages = fetch_ohlcv_history(ticker_code, start, end)
    code = str(ticker.get("ticker_code") or ticker_code).upper()
    name = str(ticker.get("name") or code).strip()[:80] or code
    if len(rows) < 2:
        raise OHLCVBacktestError(422, "LEAN 백테스트에는 유효한 일봉이 최소 2개 필요합니다.")
    if LEAN_RUNNER != "remote":
        raise OHLCVBacktestError(503, "현재 프로젝트는 LEAN_RUNNER=remote 방식으로 구성되어 있습니다.")

    with _runner_lock:
        statistics = _run_remote_ohlcv(rows, code, name, cash)

    stat_keys = (
        "Start Equity", "End Equity", "Net Profit", "Compounding Annual Return",
        "Sharpe Ratio", "Drawdown", "Total Orders",
    )
    return {
        "stock": name,
        "tickerCode": code,
        "engine": "QuantConnect LEAN",
        "runner": LEAN_RUNNER,
        "dataSource": "OHLCV Open API",
        "adapterFormat": "JSON Lines (no CSV)",
        "dateFrom": rows[0]["trade_date"],
        "dateTo": rows[-1]["trade_date"],
        "rowsLoaded": len(rows),
        "apiPages": pages,
        "initialCash": cash,
        "statistics": {key: statistics[key] for key in stat_keys if key in statistics},
        "notice": (
            f"{name}({code})의 OHLCV API 일봉 {len(rows):,}개로 QuantConnect LEAN 매수 후 보유 기준 백테스트를 "
            "실행했습니다. 수수료·슬리피지 및 배당/분할 적용 여부는 실제 운용과 다를 수 있으므로 투자 판단 전에 "
            "전략과 데이터 조정 정책을 확인하세요."
        ),
    }
