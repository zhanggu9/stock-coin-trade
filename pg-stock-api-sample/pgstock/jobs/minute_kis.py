"""KIS Open API 1분봉 수집 (국내주식 주식일별분봉조회, TR FHKST03010230).

KIS 서버는 과거 1분봉을 약 1년(거래일 약 250일)만 보관한다. 그래서
- 처음 한 번: 보관된 가장 오래된 날부터 전 종목을 받아 둔다 (python -m pgstock.jobs.minute_backfill)
- 매일 장 마감 후: 최근 거래일 중 빠진 종목·일을 채운다 (run_minute_sync, 스케줄러)
로 보관 기간 이상을 쌓아 간다.

저장: ohlcv_minute_day 한 행 = 한 종목의 하루치 정규장(09:00~15:30) 1분봉. 분봉 값은 배열 열에 담고 lz4로
압축한다. 분봉 하나를 한 행으로 두면 전 종목 1년치가 약 1억 4천만 행이라 작은 서버 디스크에 맞지 않는다.
거래가 없던 분은 KIS가 주지 않으므로 배열에서도 빠진다 (bar_count = 0 이면 그날 분봉이 없었다는 기록).

수집 대상은 일봉(ohlcv) 테이블에서 그날 거래량이 있던 KOSPI·KOSDAQ 주식(krx_universe)이다.
상장 전·거래정지일은 자연히 빠진다.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import text

from pgstock.config import get_settings

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
TOKEN_PATH = "/oauth2/tokenP"
MINUTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
TR_ID = "FHKST03010230"
ROWS_PER_CALL = 120
MARKET_CLOSE = "153000"
PROBE_TICKER = "005930"   # 보관 기간 확인용 (거래정지가 없는 대형주)
LOCK_KEY = 73_020_171     # pg_advisory_lock: 분봉 수집은 서버 전체에서 한 번에 하나만
ARRAY_COLUMNS = ("hhmm", "open", "high", "low", "close", "volume")


class KisError(RuntimeError):
    """KIS가 오류를 돌려줬거나 재시도 끝에 실패했다."""


class RateLimiter:
    """여러 스레드가 함께 쓰는 초당 호출 수 제한 (KIS 실전 REST 한도는 초당 20건)."""

    def __init__(self, per_second: float):
        self.interval = 1.0 / per_second if per_second > 0 else 0.0
        self._next = time.monotonic()
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = self._next
            self._next = now + self.interval


class KisMinuteClient:
    """KIS 1분봉 조회 클라이언트. 토큰은 메모리에만 두고 만료 1시간 전에 다시 발급한다."""

    def __init__(self, app_key: str, app_secret: str, base_url: str, per_second: float = 15.0):
        if not app_key or not app_secret:
            raise KisError("KIS_APP_KEY / KIS_APP_SECRET 이 설정되지 않았습니다.")
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.limiter = RateLimiter(per_second)
        self._local = threading.local()
        self._token_lock = threading.Lock()
        self._token: str | None = None
        self._token_expires = datetime.min
        self._calls = Counter()

    @classmethod
    def from_settings(cls) -> "KisMinuteClient":
        settings = get_settings()
        return cls(settings.kis_app_key, settings.kis_app_secret, settings.kis_base_url,
                   settings.minute_requests_per_second)

    @property
    def calls(self) -> int:
        return self._calls["calls"]

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session()
        return self._local.session

    def _ensure_token(self, force: bool = False) -> str:
        with self._token_lock:
            if self._token and not force and datetime.now() < self._token_expires:
                return self._token
            for _ in range(5):
                body = self._session().post(self.base_url + TOKEN_PATH, timeout=15, json={
                    "grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret,
                }).json()
                if body.get("access_token"):
                    self._token = body["access_token"]
                    lifetime = int(body.get("expires_in") or 86400)
                    self._token_expires = datetime.now() + timedelta(seconds=max(60, lifetime - 3600))
                    return self._token
                if body.get("error_code") == "EGW00133":  # 토큰 발급은 1분에 1회
                    time.sleep(61)
                    continue
                raise KisError(f"KIS 토큰 발급 실패: {body.get('error_code')} {body.get('error_description')}")
            raise KisError("KIS 토큰 발급 재시도 초과")

    def _page(self, code: str, ymd: str, hour: str) -> list[dict]:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hour,
            "FID_INPUT_DATE_1": ymd, "FID_PW_DATA_INCU_YN": "N", "FID_FAKE_TICK_INCU_YN": "",
        }
        last_error = ""
        for attempt in range(6):
            token = self._ensure_token()
            self.limiter.wait()
            with self._token_lock:
                self._calls["calls"] += 1
            try:
                body = self._session().get(self.base_url + MINUTE_PATH, params=params, timeout=20, headers={
                    "content-type": "application/json; charset=utf-8", "authorization": f"Bearer {token}",
                    "appkey": self.app_key, "appsecret": self.app_secret, "tr_id": TR_ID, "custtype": "P",
                }).json()
            except (requests.RequestException, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(min(30, 2 ** attempt))
                continue
            if body.get("rt_cd") == "0":
                return [row for row in (body.get("output2") or []) if row.get("stck_bsop_date") == ymd]
            msg_cd = body.get("msg_cd", "")
            last_error = f"{msg_cd} {(body.get('msg1') or '').strip()}"
            if msg_cd == "EGW00201":             # 초당 거래건수 초과
                with self._token_lock:
                    self._calls["throttled"] += 1
                time.sleep(1 + attempt)
                continue
            if msg_cd in ("EGW00121", "EGW00123"):  # 유효하지 않은/만료된 토큰
                self._ensure_token(force=True)
                continue
            raise KisError(f"{code} {ymd} {hour}: {last_error}")
        raise KisError(f"{code} {ymd} {hour}: 재시도 초과 ({last_error})")

    def has_data(self, code: str, day: date) -> bool:
        """그날 분봉이 KIS에 남아 있는지 (호출 1번)."""
        return bool(self._page(code, day.strftime("%Y%m%d"), MARKET_CLOSE))

    def fetch_day(self, code: str, day: date) -> list[tuple[int, int, int, int, int, int]]:
        """한 종목 하루치 정규장 1분봉 [(HHMM, 시가, 고가, 저가, 종가, 거래량)] 시간 오름차순."""
        ymd = day.strftime("%Y%m%d")
        rows_by_time: dict[str, dict] = {}
        hour = MARKET_CLOSE
        while True:
            rows = self._page(code, ymd, hour)
            fresh = [row for row in rows if row["stck_cntg_hour"] not in rows_by_time]
            for row in fresh:
                rows_by_time[row["stck_cntg_hour"]] = row
            if len(rows) < ROWS_PER_CALL or not fresh:
                break
            earliest = min(row["stck_cntg_hour"] for row in rows)
            if earliest <= "090000":
                break
            hour = earliest  # 다음 페이지: 이 시각 이전 120개 (경계 1개는 겹친다)
        return parse_minute_rows(rows_by_time.values())


def parse_minute_rows(rows) -> list[tuple[int, int, int, int, int, int]]:
    """KIS output2 행들을 (HHMM, O, H, L, C, V)로 바꾼다. 가격이 0 이하인 행은 버린다."""
    bars = []
    for row in rows:
        try:
            hhmmss = row["stck_cntg_hour"]
            open_, high, low, close = (int(row[key]) for key in ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_prpr"))
            volume = int(row["cntg_vol"])
        except (KeyError, TypeError, ValueError):
            continue
        if min(open_, high, low, close) <= 0 or volume < 0:
            continue
        bars.append((int(hhmmss[:4]), open_, max(high, open_, close), min(low, open_, close), close, volume))
    bars.sort()
    return bars


# ── 저장 ────────────────────────────────────────────────────────────────────

def ensure_minute_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_minute_day (
                ticker_code varchar(20) NOT NULL,
                trade_date date NOT NULL,
                bar_count smallint NOT NULL,
                hhmm smallint[] NOT NULL,
                open integer[] NOT NULL,
                high integer[] NOT NULL,
                low integer[] NOT NULL,
                close integer[] NOT NULL,
                volume bigint[] NOT NULL,
                source varchar(20) NOT NULL DEFAULT 'kis',
                collected_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (ticker_code, trade_date)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ohlcv_minute_day_trade_date ON ohlcv_minute_day (trade_date)"))
        # 분봉 한 개 = 한 행으로 펼쳐 보는 뷰 (trade_time 은 한국시간 봉 시작 시각).
        # 사용자의 StrategyAutomation 프로젝트가 행 단위 ohlcv_minute 테이블을 쓰므로 이름을 겹치지 않게 한다.
        conn.execute(text("""
            CREATE OR REPLACE VIEW ohlcv_minute_bar AS
            SELECT d.ticker_code,
                   d.trade_date + make_interval(hours => b.hhmm / 100, mins => b.hhmm % 100) AS trade_time,
                   b.open, b.high, b.low, b.close, b.volume
            FROM ohlcv_minute_day d
            CROSS JOIN LATERAL unnest(d.hhmm, d.open, d.high, d.low, d.close, d.volume)
                 AS b(hhmm, open, high, low, close, volume)
        """))
    # lz4가 없는 서버면 기본(pglz) 압축을 쓴다.
    try:
        with engine.begin() as conn:
            for column in ARRAY_COLUMNS:
                conn.execute(text(f"ALTER TABLE ohlcv_minute_day ALTER COLUMN {column} SET COMPRESSION lz4"))
    except Exception:  # noqa: BLE001 - 압축 방식은 최적화일 뿐이다
        log.warning("ohlcv_minute_day lz4 압축 설정 실패 — 기본 압축 사용", exc_info=True)


def upsert_minute_day(engine, code: str, day: date, bars) -> None:
    columns = list(zip(*bars)) if bars else [[] for _ in ARRAY_COLUMNS]
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ohlcv_minute_day (ticker_code, trade_date, bar_count, hhmm, open, high, low, close, volume)
            VALUES (:code, :day, :count, :hhmm, :open, :high, :low, :close, :volume)
            ON CONFLICT (ticker_code, trade_date) DO UPDATE SET
                bar_count = EXCLUDED.bar_count, hhmm = EXCLUDED.hhmm, open = EXCLUDED.open,
                high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
                volume = EXCLUDED.volume, collected_at = now()
        """), {"code": code, "day": day, "count": len(bars),
               **{name: list(values) for name, values in zip(ARRAY_COLUMNS, columns)}})


def stored_codes(engine, day: date, *, include_empty: bool = True) -> set[str]:
    sql = "SELECT ticker_code FROM ohlcv_minute_day WHERE trade_date = :day"
    if not include_empty:
        sql += " AND bar_count > 0"
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(text(sql), {"day": day})}


def traded_codes(engine, day: date) -> set[str]:
    """일봉 테이블에서 그날 거래량이 있던 종목."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker_code FROM ohlcv WHERE trade_date = :day AND volume > 0"), {"day": day})
        return {row[0] for row in rows}


def trading_days(engine, start: date, end: date) -> list[date]:
    """일봉 테이블의 시장 거래일 (대형주 일봉 날짜 합집합)."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT trade_date FROM ohlcv
            WHERE ticker_code IN ('005930', '000660', '005380', '035420', '051910')
              AND trade_date BETWEEN :start AND :end
            ORDER BY trade_date
        """), {"start": start, "end": end})
        return [row[0] for row in rows]


def last_complete_day(now: datetime | None = None) -> date:
    """분봉이 확정된 마지막 날 (한국시간 16시 전이면 어제)."""
    now = now or datetime.now(KST)
    return now.date() if now.hour >= 16 else now.date() - timedelta(days=1)


@contextmanager
def minute_lock(engine):
    """백필과 정기 수집이 동시에 같은 KIS 키를 쓰지 않도록 서버 전체 잠금을 잡는다."""
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar())
        try:
            yield acquired
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    finally:
        conn.close()


# ── 수집 ────────────────────────────────────────────────────────────────────

def collect_days(engine, client: KisMinuteClient, days, universe: set[str], *,
                 workers: int = 2, recheck_empty: bool = False, deadline: float | None = None) -> dict:
    """날짜 오름차순으로 (그날 거래된 주식 - 이미 저장된 종목) 의 1분봉을 받아 저장한다.

    오래된 날부터 받는 이유: KIS 보관 기간이 하루씩 밀려나므로 가장 오래된 날이 먼저 사라진다.
    그날 대형주 분봉이 비어 있으면 보관 기간 밖으로 보고 그 날짜는 건너뛴다.
    """
    summary = Counter()
    started = time.monotonic()
    for day in days:
        if deadline and time.monotonic() > deadline:
            summary["stopped_at_deadline"] = 1
            break
        targets = (traded_codes(engine, day) & universe) - stored_codes(engine, day, include_empty=not recheck_empty)
        if not targets:
            continue
        if not client.has_data(PROBE_TICKER, day):
            summary["expired_days"] += 1
            log.info("%s: KIS 보관 기간 밖 (대형주 분봉 없음) — 건너뜀", day)
            continue
        day_started, day_calls = time.monotonic(), client.calls
        day_stats = Counter()
        stats_lock = threading.Lock()

        def work(code: str) -> None:
            try:
                bars = client.fetch_day(code, day)
                upsert_minute_day(engine, code, day, bars)
                update = {"stock_days": 1, "bars": len(bars), "empty": 0 if bars else 1}
            except Exception as exc:  # noqa: BLE001 - 한 종목 실패가 전체를 멈추지 않게 한다
                update = {"failed": 1}
                log.warning("분봉 실패 %s %s: %s", code, day, str(exc)[:200])
            with stats_lock:
                day_stats.update(update)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(work, sorted(targets)))
        summary.update(day_stats)
        summary["days"] += 1
        log.info("%s: %d종목 저장 (빈 날 %d, 실패 %d), 분봉 %d개, 호출 %d회, %.0f초 | 누적 %d일 %.1f시간",
                 day, day_stats["stock_days"], day_stats["empty"], day_stats["failed"], day_stats["bars"],
                 client.calls - day_calls, time.monotonic() - day_started, summary["days"],
                 (time.monotonic() - started) / 3600)
    summary["calls"] = client.calls
    summary["throttled"] = client._calls["throttled"]
    return dict(summary)


def run_minute_sync(as_of: date | None = None) -> dict:
    """스케줄러 진입점: 최근 거래일 중 빠진 종목·일의 1분봉을 채운다."""
    from pgstock.jobs.krx_universe import fetch_listed_stocks
    from pgstock.jobs.ohlcv_aggregate import create_ohlcv_engine

    settings = get_settings()
    if not settings.minute_sync_enabled:
        return {"status": "disabled"}
    engine = create_ohlcv_engine()
    with minute_lock(engine) as acquired:
        if not acquired:
            log.info("분봉 수집이 이미 실행 중이라 이번 정기 수집은 건너뜁니다.")
            return {"status": "busy"}
        ensure_minute_table(engine)
        end = as_of or last_complete_day()
        days = trading_days(engine, end - timedelta(days=settings.minute_catchup_days * 2 + 7), end)
        days = days[-settings.minute_catchup_days:]
        result = collect_days(engine, KisMinuteClient.from_settings(), days, set(fetch_listed_stocks()),
                              workers=settings.minute_workers)
        log.info("Minute sync finished: %s", result)
        return result
