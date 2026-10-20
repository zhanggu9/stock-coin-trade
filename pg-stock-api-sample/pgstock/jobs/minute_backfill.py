"""KIS에 남아 있는 과거 1분봉(약 1년)을 전 종목 받아 ohlcv_minute에 저장한다 (처음 한 번, 이어받기 가능).

    python -m pgstock.jobs.minute_backfill --dry-run          # 대상 종목·일 수와 예상 호출 수만
    python -m pgstock.jobs.minute_backfill                    # 보관된 가장 오래된 날부터 수집
    python -m pgstock.jobs.minute_backfill --ticker 005930 --start 2026-10-01

- 날짜 오름차순으로 받는다. KIS 보관 기간이 하루씩 밀려나므로 가장 오래된 날을 먼저 받아야 놓치지 않는다.
- 이미 저장된 종목·일은 건너뛰므로 중간에 멈춰도 다시 실행하면 이어서 받는다.
- 정기 1분봉 수집(run_minute_sync)과 같은 KIS 키를 나눠 쓰지 않도록 DB 잠금을 잡는다.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta

from sqlalchemy import create_engine

from pgstock.config import get_settings
from pgstock.jobs.krx_universe import fetch_listed_stocks
from pgstock.jobs.minute_kis import (KisMinuteClient, collect_days, ensure_minute_table, last_complete_day,
                                     minute_lock, stored_codes, traded_codes, trading_days)

log = logging.getLogger("minute_backfill")


def parse_args():
    parser = argparse.ArgumentParser(description="KIS 1분봉 과거 수집")
    parser.add_argument("--start", default=None, help="시작일 YYYY-MM-DD (기본: 400일 전, 보관 기간 밖 날짜는 자동으로 건너뜀)")
    parser.add_argument("--end", default=None, help="종료일 YYYY-MM-DD (기본: 분봉이 확정된 마지막 날)")
    parser.add_argument("--ticker", action="append", dest="tickers", help="이 종목만 (여러 번 지정 가능)")
    parser.add_argument("--rps", type=float, default=None, help="초당 호출 수 (기본 MINUTE_REQUESTS_PER_SECOND)")
    parser.add_argument("--workers", type=int, default=None, help="동시 요청 스레드 수 (기본 MINUTE_WORKERS)")
    parser.add_argument("--recheck-empty", action="store_true", help="분봉 0개로 저장된 종목·일도 다시 받기")
    parser.add_argument("--dry-run", action="store_true", help="대상과 예상 호출 수만 출력")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    settings = get_settings()
    end = date.fromisoformat(args.end) if args.end else last_complete_day()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=400)
    engine = create_engine(settings.ohlcv_database_url, pool_pre_ping=True, pool_size=4, max_overflow=4)

    universe = set(fetch_listed_stocks())
    if args.tickers:
        universe &= set(args.tickers)
    days = trading_days(engine, start, end)
    log.info("대상 주식 %d종목, 거래일 %d일 (%s ~ %s)", len(universe), len(days), days[0] if days else "-", end)

    if args.dry_run:
        ensure_minute_table(engine)
        pending = sum(len((traded_codes(engine, d) & universe) - stored_codes(engine, d)) for d in days)
        print(json.dumps({"days": len(days), "pending_stock_days": pending,
                          "estimated_calls": round(pending * 2.2),
                          "estimated_hours": round(pending * 2.2 / (args.rps or settings.minute_requests_per_second) / 3600, 1)},
                         ensure_ascii=False))
        return 0

    client = KisMinuteClient(settings.kis_app_key, settings.kis_app_secret, settings.kis_base_url,
                             args.rps or settings.minute_requests_per_second)
    with minute_lock(engine) as acquired:
        if not acquired:
            log.error("다른 1분봉 수집이 실행 중입니다. 끝난 뒤 다시 실행하세요.")
            return 2
        ensure_minute_table(engine)
        result = collect_days(engine, client, days, universe, workers=args.workers or settings.minute_workers,
                              recheck_empty=args.recheck_empty)
        # 오래 도는 동안 새로 확정된 날짜까지 이어서 채운다.
        newest = last_complete_day()
        if newest > end:
            later = collect_days(engine, client, trading_days(engine, end + timedelta(days=1), newest), universe,
                                 workers=args.workers or settings.minute_workers)
            result = {key: result.get(key, 0) + later.get(key, 0) for key in set(result) | set(later)}
            result["calls"], result["throttled"] = later.get("calls", 0), later.get("throttled", 0)  # 누적값
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
