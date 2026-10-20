"""KOSPI·KOSDAQ 상장 주식의 과거 일봉 누락을 진단하고 다시 채운다 (일회성/수동 실행).

    python -m pgstock.jobs.ohlcv_backfill --dry-run          # 진단만
    python -m pgstock.jobs.ohlcv_backfill                    # 진단 → 누락 종목 재수집 → 재진단
    python -m pgstock.jobs.ohlcv_backfill --ticker 035720    # 특정 종목만

1. 대상: KIS 종목 마스터의 KOSPI·KOSDAQ 주식 (ETF·ETN·리츠·펀드 제외, krx_universe 참고)
2. 시장 거래일 달력: 대형주 몇 종목의 네이버 일봉 날짜를 합집합으로 만든다 (한 종목 거래정지에 영향받지 않게)
3. 종목별로 max(시작일, 상장일) 이후 달력 거래일 중 DB에 없는 날을 센다. 하나라도 없으면 재수집 대상
4. 재수집: 네이버에서 시작일~오늘을 한 번에 받아 upsert하고, 연도별 결과를 ohlcv_sync_status에 남긴다
   (상장 전 연도는 empty로 기록되어 이후 정기 수집이 빈 요청을 보내지 않는다)
5. 다시 진단해 남은 누락(거래정지 등 공급자에도 없는 날)을 보고하고 집계 스냅샷을 갱신한다
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine, text

from pgstock.config import get_settings
from pgstock.jobs.krx_universe import ListedStock, fetch_listed_stocks
from pgstock.jobs.ohlcv_aggregate import refresh_ohlcv_aggregates
from pgstock.jobs.ohlcv_crawler import fetch_naver, upsert_ticker
from pgstock.jobs.ohlcv_sync import _ensure_status_table, _save_status

log = logging.getLogger("ohlcv_backfill")

# 시장 달력용 대형주: 삼성전자, SK하이닉스, 현대차, NAVER, LG화학
CALENDAR_TICKERS = ("005930", "000660", "005380", "035420", "051910")


def build_calendar(start: date, end_exclusive: date) -> list[date]:
    days: set[date] = set()
    for code in CALENDAR_TICKERS:
        days.update(row["trade_date"] for row in fetch_naver(code, start, end_exclusive))
    if not days:
        raise RuntimeError("시장 거래일 달력을 만들지 못했습니다 (네이버 응답 없음).")
    return sorted(days)


def audit(engine, universe: dict[str, ListedStock], calendar: list[date], start: date) -> dict[str, dict]:
    """종목별 기대 거래일 수와 실제 보유 일수를 DB 안에서 계산한다."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE IF NOT EXISTS bf_calendar (d date PRIMARY KEY) ON COMMIT DROP"))
        conn.execute(text("CREATE TEMP TABLE IF NOT EXISTS bf_universe (code varchar(20) PRIMARY KEY, since date NOT NULL) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO bf_calendar (d) VALUES (:d)"), [{"d": d} for d in calendar])
        conn.execute(
            text("INSERT INTO bf_universe (code, since) VALUES (:code, :since)"),
            [{"code": code, "since": max(start, stock.listed_on or start)} for code, stock in universe.items()],
        )
        rows = conn.execute(text("""
            SELECT u.code,
                   count(c.d) AS expected,
                   count(o.trade_date) AS present,
                   min(c.d) FILTER (WHERE o.trade_date IS NULL) AS first_missing
            FROM bf_universe u
            LEFT JOIN bf_calendar c ON c.d >= u.since
            LEFT JOIN ohlcv o ON o.ticker_code = u.code AND o.trade_date = c.d
            GROUP BY u.code
        """)).mappings().all()
    return {
        row["code"]: {
            "expected": int(row["expected"]),
            "present": int(row["present"]),
            "missing": int(row["expected"]) - int(row["present"]),
            "first_missing": row["first_missing"].isoformat() if row["first_missing"] else None,
        }
        for row in rows
    }


def summarize(result: dict[str, dict]) -> dict:
    missing = {code: info for code, info in result.items() if info["missing"] > 0}
    return {
        "tickers": len(result),
        "complete": len(result) - len(missing),
        "with_missing": len(missing),
        "no_data": sum(1 for info in missing.values() if info["present"] == 0),
        "missing_days": sum(info["missing"] for info in missing.values()),
    }


def refetch(engine, stock: ListedStock, start: date, as_of: date, retries: int = 3) -> tuple[int, int]:
    """한 종목을 네이버에서 시작일~오늘까지 받아 upsert하고 연도별 상태를 기록한다."""
    end = as_of + timedelta(days=1)
    started = datetime.now(UTC)
    for attempt in range(1, retries + 1):
        try:
            rows = fetch_naver(stock.code, start, end)
            break
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    upserted = upsert_ticker(engine, stock.code, stock.name, stock.market, rows)
    per_year = Counter(row["trade_date"].year for row in rows)
    for year in range(start.year, as_of.year + 1):
        year_start = max(start, date(year, 1, 1))
        year_end = min(date(year + 1, 1, 1), end)
        count = per_year.get(year, 0)
        _save_status(engine, code=stock.code, year=year, provider="naver",
                     status="success" if count else "empty", start=year_start, end=year_end,
                     fetched=count, upserted=0, error=None, started=started)
    return len(rows), max(0, upserted or 0)


def sync_ticker_names(engine, universe: dict[str, ListedStock]) -> None:
    """tickers 테이블의 종목명·시장을 마스터 기준으로 맞춘다 (종목명이 코드로만 들어간 행 정리)."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO tickers (ticker_code, name, market) VALUES (:code, :name, :market)
            ON CONFLICT (ticker_code) DO UPDATE SET name = EXCLUDED.name, market = EXCLUDED.market
            WHERE (tickers.name, tickers.market) IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.market)
        """), [{"code": s.code, "name": s.name, "market": s.market} for s in universe.values()])


def parse_args():
    parser = argparse.ArgumentParser(description="KOSPI·KOSDAQ 주식 일봉 누락 진단/재수집")
    parser.add_argument("--start", default=None, help="시작일 YYYY-MM-DD (기본: OHLCV_SYNC_START_YEAR년 1월 1일)")
    parser.add_argument("--as-of", default=None, help="기준일 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--ticker", action="append", dest="tickers", help="이 종목만 (여러 번 지정 가능)")
    parser.add_argument("--limit", type=int, default=0, help="재수집 종목 수 상한 (시험용)")
    parser.add_argument("--delay", type=float, default=None, help="요청 사이 대기(초), 기본 OHLCV_SYNC_REQUEST_DELAY")
    parser.add_argument("--dry-run", action="store_true", help="진단만 하고 DB를 바꾸지 않음")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    settings = get_settings()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    start = date.fromisoformat(args.start) if args.start else date(settings.ohlcv_sync_start_year, 1, 1)
    delay = settings.ohlcv_sync_request_delay if args.delay is None else max(0.0, args.delay)
    engine = create_engine(settings.ohlcv_database_url, pool_pre_ping=True)

    universe = fetch_listed_stocks()
    markets = Counter(stock.market for stock in universe.values())
    if args.tickers:
        unknown = [code for code in args.tickers if code not in universe]
        if unknown:
            raise SystemExit(f"KOSPI·KOSDAQ 주식 목록에 없는 종목: {', '.join(unknown)}")
        universe = {code: universe[code] for code in args.tickers}
    log.info("대상 주식 %d종목 (전체 %s), 기간 %s ~ %s", len(universe), dict(markets), start, as_of)

    calendar = build_calendar(start, as_of + timedelta(days=1))
    log.info("시장 거래일 %d일 (%s ~ %s)", len(calendar), calendar[0], calendar[-1])

    before = audit(engine, universe, calendar, start)
    before_summary = summarize(before)
    log.info("진단(전): %s", before_summary)
    targets = sorted(code for code, info in before.items() if info["missing"] > 0)
    if args.limit:
        targets = targets[: args.limit]

    report = {"start": start.isoformat(), "as_of": as_of.isoformat(), "calendar_days": len(calendar),
              "before": before_summary, "targets": len(targets)}
    if args.dry_run:
        report["sample_missing"] = {code: before[code] for code in targets[:20]}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    _ensure_status_table(engine)
    sync_ticker_names(engine, universe)
    fetched = upserted = 0
    failed: dict[str, str] = {}
    started = time.monotonic()
    for index, code in enumerate(targets, 1):
        if delay:
            time.sleep(delay)
        try:
            got, changed = refetch(engine, universe[code], start, as_of)
            fetched += got
            upserted += changed
        except Exception as exc:  # 한 종목 실패가 전체를 멈추지 않게 한다
            failed[code] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.warning("재수집 실패 %s: %s", code, failed[code])
        if index % 100 == 0 or index == len(targets):
            log.info("재수집 %d/%d (받은 행 %d, 반영 %d, 실패 %d, %.0f초)",
                     index, len(targets), fetched, upserted, len(failed), time.monotonic() - started)

    after = audit(engine, universe, calendar, start)
    after_summary = summarize(after)
    still = sorted((info["missing"], code) for code, info in after.items() if info["missing"] > 0)
    report.update({
        "fetched_rows": fetched,
        "upserted_rows": upserted,
        "failed": failed,
        "after": after_summary,
        # 남은 누락은 대부분 거래정지 등으로 공급자에도 없는 날이다
        "still_missing_top": [
            {"code": code, "name": universe[code].name, **after[code]} for _, code in reversed(still[-30:])
        ],
        "aggregate": refresh_ohlcv_aggregates(engine),
    })
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
