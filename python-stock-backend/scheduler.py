import logging
import os

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from db import session_scope
from market_bots import run_bot_trading_round
from models import CryptoRank, UpbitMarket
from ohlcv_aggregate import bootstrap_ohlcv_aggregates
from ohlcv_sync import run_incremental_sync, sync_enabled

log = logging.getLogger(__name__)

CMC_API_KEY = os.environ.get("CMC_API_KEY", "")


def sync_coinmarketcap_rankings():
    """코인마켓캡 API - 시가총액 top 100 동기화 (1시간 마다 실행)"""
    log.info("saveCoinMarketCapCryptoRank() -> 코인마켓캡 시가총액 Top100 스케쥴러 실행")
    if not CMC_API_KEY:
        log.warning("CMC_API_KEY가 설정되지 않아 동기화를 건너뜁니다.")
        return

    url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?CMC_PRO_API_KEY={CMC_API_KEY}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    items = resp.json().get("data", [])

    with session_scope() as db:
        db.execute(text("TRUNCATE TABLE crypto_rank"))
        for item in items:
            quote = (item.get("quote") or {}).get("USD") or {}
            db.add(CryptoRank(
                name=item.get("name"),
                symbol=item.get("symbol"),
                api_crypto_id=item.get("id"),
                price=quote.get("price"),
                market_cap=quote.get("market_cap"),
                percent_change24h=quote.get("percent_change_24h"),
                percent_change7d=quote.get("percent_change_7d"),
            ))


def sync_upbit_markets():
    """업비트 API - 거래가능 market 목록 DB 동기화 (오후 6시 1일 1회)"""
    log.info("saveUpbitMarketDatabase() -> 업비트 거래가능 목록 DB 저장 스케쥴러 실행")
    resp = requests.get("https://api.upbit.com/v1/market/all", timeout=10)
    resp.raise_for_status()
    items = resp.json()

    with session_scope() as db:
        existing = {m.market_code for m in db.query(UpbitMarket).all()}
        for item in items:
            code = item.get("market")
            if not code or "KRW" not in code or code in existing:
                continue
            db.add(UpbitMarket(
                market_code=code,
                korean_name=item.get("korean_name"),
                english_name=item.get("english_name"),
            ))


def _ohlcv_schedule_hours() -> str:
    """Return deterministic Asia/Seoul cron hours for the configured interval."""
    base_hour = int(os.environ.get("OHLCV_SYNC_HOUR", "18"))
    interval_hours = int(os.environ.get("OHLCV_SYNC_INTERVAL_HOURS", "12"))
    if not 0 <= base_hour <= 23:
        raise ValueError("OHLCV_SYNC_HOUR must be between 0 and 23")
    if interval_hours < 1 or 24 % interval_hours:
        raise ValueError("OHLCV_SYNC_INTERVAL_HOURS must be a positive divisor of 24")
    hours = sorted({(base_hour + offset) % 24 for offset in range(0, 24, interval_hours)})
    return ",".join(str(hour) for hour in hours)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(sync_coinmarketcap_rankings, CronTrigger(minute=0, timezone="Asia/Seoul"))
    scheduler.add_job(sync_upbit_markets, CronTrigger(hour=18, minute=0, timezone="Asia/Seoul"))
    scheduler.add_job(run_bot_trading_round, IntervalTrigger(minutes=10))
    try:
        result = bootstrap_ohlcv_aggregates()
        log.info("OHLCV aggregate bootstrap: %s", result)
    except Exception:
        log.exception("OHLCV aggregate bootstrap failed; scheduled batch will retry aggregation")
    if sync_enabled():
        scheduler.add_job(
            run_incremental_sync,
            CronTrigger(
                hour=_ohlcv_schedule_hours(),
                minute=int(os.environ.get("OHLCV_SYNC_MINUTE", "20")),
                timezone="Asia/Seoul",
            ),
            id="ohlcv-incremental-batch",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    scheduler.start()
    return scheduler
