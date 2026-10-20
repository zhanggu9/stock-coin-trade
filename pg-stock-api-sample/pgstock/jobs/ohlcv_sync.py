"""종목·연도 단위로 묶은 예약·멱등 OHLCV 수집."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, text

from pgstock.config import get_settings
from pgstock.jobs.ohlcv_aggregate import (
    claim_daily_batch,
    create_ohlcv_engine,
    finish_daily_batch,
    refresh_ohlcv_aggregates,
)
from pgstock.jobs.krx_universe import fetch_listed_stocks
from pgstock.jobs.ohlcv_crawler import MAJOR_TICKERS, fetch_naver, fetch_yahoo, upsert_ticker

log = logging.getLogger(__name__)
_sync_lock = threading.Lock()


def sync_enabled() -> bool:
    """예약 증분 수집 기능이 환경설정상 활성화되어 있는지 반환한다."""
    return get_settings().ohlcv_sync_enabled


def _ensure_status_table(engine):
    """종목·연도별 수집 결과를 기록할 상태 테이블을 필요할 때 생성한다."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ohlcv_sync_status (
                ticker_code varchar(20) NOT NULL,
                data_year smallint NOT NULL,
                provider varchar(20) NOT NULL,
                status varchar(20) NOT NULL,
                requested_from date NOT NULL,
                requested_to date NOT NULL,
                fetched_rows integer NOT NULL DEFAULT 0,
                upserted_rows integer NOT NULL DEFAULT 0,
                last_error varchar(500),
                started_at timestamptz NOT NULL,
                completed_at timestamptz NOT NULL,
                PRIMARY KEY (ticker_code, data_year)
            )
        """))


def _save_status(engine, *, code, year, provider, status, start, end, fetched, upserted, error, started):
    """한 종목의 한 연도 수집 결과를 upsert한다."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ohlcv_sync_status
                (ticker_code,data_year,provider,status,requested_from,requested_to,
                 fetched_rows,upserted_rows,last_error,started_at,completed_at)
            VALUES
                (:code,:year,:provider,:status,:start,:end,:fetched,:upserted,
                 :error,:started,:completed)
            ON CONFLICT (ticker_code,data_year) DO UPDATE SET
                provider=EXCLUDED.provider, status=EXCLUDED.status,
                requested_from=EXCLUDED.requested_from, requested_to=EXCLUDED.requested_to,
                fetched_rows=EXCLUDED.fetched_rows, upserted_rows=EXCLUDED.upserted_rows,
                last_error=EXCLUDED.last_error, started_at=EXCLUDED.started_at,
                completed_at=EXCLUDED.completed_at
        """), {
            "code": code, "year": year, "provider": provider, "status": status,
            "start": start, "end": end - timedelta(days=1), "fetched": fetched,
            "upserted": upserted, "error": str(error)[:500] if error else None,
            "started": started, "completed": datetime.now(UTC),
        })


def _ticker_universe(engine):
    """설정값에 따라 수집 대상을 정한다.

    Returns:
        ({종목코드: (종목명, 시장)}, {종목코드: 상장일})  — 상장일은 listed 모드에서만 채운다.

    - listed: KOSPI·KOSDAQ 상장 주식 전체 (ETF·ETN·리츠·펀드 제외, KIS 종목 마스터 기준)
    - major : 내장 대표 24종목
    - all   : tickers 테이블의 모든 종목
    - 005930,000660 : 명시한 종목
    """
    settings = get_settings()
    selection = settings.ohlcv_sync_tickers.strip()
    limit = max(0, settings.ohlcv_sync_max_tickers)
    if selection.lower() == "listed":
        listed = fetch_listed_stocks()
        items = sorted(listed.items())
        if limit:
            items = items[:limit]
        return ({code: (stock.name, stock.market) for code, stock in items},
                {code: stock.listed_on for code, stock in items if stock.listed_on})
    if not selection or selection.lower() == "major":
        return dict(MAJOR_TICKERS), {}

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker_code,name,market FROM tickers ORDER BY ticker_code")).mappings()
        available = {row["ticker_code"]: (row["name"] or row["ticker_code"], row["market"] or "KOSPI") for row in rows}
    if selection.lower() == "all":
        items = list(available.items())
        return dict(items[:limit] if limit else items), {}

    requested = [value.strip().upper() for value in selection.split(",") if value.strip()]
    unknown = [code for code in requested if code not in available and code not in MAJOR_TICKERS]
    if unknown:
        raise ValueError(f"OHLCV_SYNC_TICKERS에 등록되지 않은 종목이 있습니다: {', '.join(unknown)}")
    return {code: available[code] if code in available else MAJOR_TICKERS[code] for code in requested}, {}


def _empty_years(engine):
    """이전 수집에서 공급자에 데이터가 없었던(status=empty) 종목·연도 집합."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker_code, data_year FROM ohlcv_sync_status WHERE status = 'empty'"))
        return {(row[0], int(row[1])) for row in rows}


def skip_known_empty_years(ranges, code, as_of, empty_years, listed_on=None):
    """상장 전 연도처럼 받아도 비어 있는 과거 연도를 계획에서 뺀다.

    전 종목을 START_YEAR부터 수집하면 그 뒤에 상장한 종목은 상장 전 연도가 매번 '누락'으로
    잡혀 하루 세 번 빈 요청을 보낸다. 상장일 이전 연도와 이미 empty로 확인된 과거 연도는 건너뛴다.
    올해는 항상 남긴다.
    """
    kept = []
    for year, start, end in ranges:
        if year < as_of.year and (
            (code, year) in empty_years or (listed_on is not None and year < listed_on.year)
        ):
            continue
        kept.append((year, start, end))
    return kept


def _existing_years(engine, code):
    """특정 종목의 연도별 마지막 거래일과 행 수를 조회한다."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT extract(year FROM trade_date)::int AS data_year,
                   max(trade_date) AS last_date, count(*) AS row_count
            FROM ohlcv WHERE ticker_code=:code GROUP BY 1
        """), {"code": code}).mappings()
        return {row["data_year"]: {"last_date": row["last_date"], "row_count": row["row_count"]} for row in rows}


def plan_year_ranges(existing, start_year, as_of, reconcile=False, correction_days=7):
    """수집이 필요한 [시작, 끝) 구간을 돌려준다."""
    ranges = []
    end_exclusive = as_of + timedelta(days=1)
    for year in range(start_year, as_of.year + 1):
        year_start = date(year, 1, 1)
        year_end = min(date(year + 1, 1, 1), end_exclusive)
        state = existing.get(year)
        if reconcile or not state:
            ranges.append((year, year_start, year_end))
        elif year == as_of.year:
            refresh_start = max(year_start, state["last_date"] - timedelta(days=max(0, correction_days)))
            ranges.append((year, refresh_start, year_end))
    return ranges


def _download(provider, code, market, start, end):
    """선택된 공급자를 호출하고 auto 모드에서는 Yahoo 실패 시 네이버로 전환한다."""
    if provider == "naver":
        return fetch_naver(code, start, end)
    if provider == "yahoo":
        return fetch_yahoo(code, market, start, end)
    try:
        rows = fetch_yahoo(code, market, start, end)
    except Exception:
        log.warning("Yahoo OHLCV failed for %s; falling back to Naver", code, exc_info=True)
        rows = []
    return rows or fetch_naver(code, start, end)


def collect_ohlcv(*, reconcile=False, as_of=None, engine=None, downloader=None):
    """설정된 종목마다 빠진 연도를 수집하고 올해 데이터를 보정한다.

    종목별로 과거 누락 연도는 전체 구간을 받고, 현재 연도는 correction_days만큼
    되감아 재수집한다. 프로세스 안의 lock으로 스케줄러 중복 실행도 방지한다.
    """
    if not _sync_lock.acquire(blocking=False):
        return {"status": "already_running", "tickers": 0, "ranges": 0, "failed": []}
    try:
        settings = get_settings()
        as_of = as_of or date.today()
        provider = settings.ohlcv_sync_provider.strip().lower()
        if provider not in {"naver", "yahoo", "auto"}:
            raise ValueError("OHLCV_SYNC_PROVIDER는 naver, yahoo, auto 중 하나여야 합니다.")
        start_year = settings.ohlcv_sync_start_year
        correction_days = settings.ohlcv_sync_correction_days
        engine = engine or create_engine(settings.ohlcv_database_url, pool_pre_ping=True, pool_size=2, max_overflow=1)
        _ensure_status_table(engine)
        universe, listed_on = _ticker_universe(engine)
        empty_years = set() if reconcile else _empty_years(engine)
        delay = max(0.0, settings.ohlcv_sync_request_delay)
        fetch = downloader or _download
        summary = {"status": "completed", "tickers": len(universe), "ranges": 0,
                   "fetchedRows": 0, "upsertedRows": 0, "failed": []}
        for code, (name, market) in universe.items():
            existing = _existing_years(engine, code)
            ranges = plan_year_ranges(existing, start_year, as_of, reconcile, correction_days)
            if not reconcile:
                ranges = skip_known_empty_years(ranges, code, as_of, empty_years, listed_on.get(code))
            for year, start, end in ranges:
                summary["ranges"] += 1
                started = datetime.now(UTC)
                try:
                    if delay:
                        time.sleep(delay)  # 공급자 부하·차단 방지
                    rows = fetch(provider, code, market, start, end)
                    upserted = upsert_ticker(engine, code, name, market, rows)
                    status = "success" if rows else "empty"
                    _save_status(engine, code=code, year=year, provider=provider, status=status,
                                 start=start, end=end, fetched=len(rows), upserted=upserted, error=None, started=started)
                    summary["fetchedRows"] += len(rows)
                    summary["upsertedRows"] += max(0, upserted or 0)
                    log.info("OHLCV %s %s: %s rows (%s..%s)", code, year, len(rows), start, end - timedelta(days=1))
                except Exception as exc:
                    summary["failed"].append({"ticker": code, "year": year, "error": str(exc)[:200]})
                    _save_status(engine, code=code, year=year, provider=provider, status="failed",
                                 start=start, end=end, fetched=0, upserted=0, error=exc, started=started)
                    log.exception("OHLCV collection failed for %s/%s", code, year)
        if summary["failed"]:
            summary["status"] = "partial_failure"
        return summary
    finally:
        _sync_lock.release()


def run_incremental_sync():
    """스케줄러가 호출하는 증분 수집 진입점과 집계 갱신을 연결한다."""
    if not sync_enabled():
        return {"status": "disabled"}
    engine = create_ohlcv_engine()
    result = collect_ohlcv(reconcile=False, engine=engine)
    result["aggregate"] = refresh_ohlcv_aggregates(engine)
    log.info("Incremental OHLCV sync finished: %s", result)
    return result


def run_daily_ohlcv_batch(as_of=None):
    """수집과 집계를 로컬 날짜당 최대 한 번 실행한다."""
    if not sync_enabled():
        return {"status": "disabled"}
    batch_date = as_of or date.today()
    engine = create_ohlcv_engine()
    if not claim_daily_batch(engine, batch_date):
        result = {"status": "already_executed", "batchDate": batch_date.isoformat()}
        log.info("Daily OHLCV batch skipped: %s", result)
        return result
    try:
        result = collect_ohlcv(reconcile=False, as_of=batch_date, engine=engine)
        aggregate = refresh_ohlcv_aggregates(engine)
        status = result.get("status", "completed")
        finish_daily_batch(
            engine, batch_date, status=status,
            fetched_rows=result.get("fetchedRows", 0),
            upserted_rows=result.get("upsertedRows", 0),
            refreshed_at=aggregate.get("refreshed_at"),
        )
        result.update({"batchDate": batch_date.isoformat(), "aggregate": aggregate})
        log.info("Daily OHLCV batch finished: %s", result)
        return result
    except Exception as exc:
        finish_daily_batch(engine, batch_date, status="failed", error=exc)
        log.exception("Daily OHLCV batch failed")
        raise
