"""APScheduler 배치: pg-stock OHLCV 증분 수집.

원본 ``app.jobs.scheduler`` 에서 코인마켓캡·업비트·봇 거래 작업을 제외하고 OHLCV 부분만 남겼다.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pgstock.config import get_settings
from pgstock.jobs.ohlcv_aggregate import bootstrap_ohlcv_aggregates
from pgstock.jobs.minute_kis import run_minute_sync
from pgstock.jobs.ohlcv_sync import run_incremental_sync, sync_enabled

log = logging.getLogger(__name__)


def _ohlcv_schedule_hours() -> str:
    """설정된 간격에 맞는 결정적인 Asia/Seoul cron 시(hour) 목록을 돌려준다."""
    settings = get_settings()
    if settings.ohlcv_sync_hours.strip():
        hours = sorted({int(value.strip()) for value in settings.ohlcv_sync_hours.split(",")})
        if any(hour < 0 or hour > 23 for hour in hours):
            raise ValueError("OHLCV_SYNC_HOURS must contain hours between 0 and 23")
        return ",".join(str(hour) for hour in hours)
    base_hour = settings.ohlcv_sync_hour
    interval_hours = settings.ohlcv_sync_interval_hours
    if not 0 <= base_hour <= 23:
        raise ValueError("OHLCV_SYNC_HOUR must be between 0 and 23")
    if interval_hours < 1 or 24 % interval_hours:
        raise ValueError("OHLCV_SYNC_INTERVAL_HOURS must be a positive divisor of 24")
    hours = sorted({(base_hour + offset) % 24 for offset in range(0, 24, interval_hours)})
    return ",".join(str(hour) for hour in hours)


def start_scheduler() -> BackgroundScheduler:
    """한국시간 cron에 증분 수집 작업을 등록하고 스케줄러를 시작한다.

    앱 기동 직후에는 집계 스냅샷을 준비하고, 이후 설정된 시각에만 수집 작업을
    실행한다. max_instances=1로 같은 작업이 겹치지 않게 한다.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    try:
        result = bootstrap_ohlcv_aggregates()
        log.info("OHLCV aggregate bootstrap: %s", result)
    except Exception:
        log.exception("OHLCV aggregate bootstrap failed; scheduled batch will retry aggregation")
    if sync_enabled():
        scheduler.add_job(
            run_incremental_sync,
            CronTrigger(hour=_ohlcv_schedule_hours(), minute=get_settings().ohlcv_sync_minute, timezone="Asia/Seoul"),
            id="ohlcv-incremental-batch",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
    settings = get_settings()
    if settings.minute_sync_enabled:
        if settings.kis_app_key and settings.kis_app_secret:
            scheduler.add_job(
                run_minute_sync,
                CronTrigger(day_of_week="mon-fri", hour=settings.minute_sync_hour,
                            minute=settings.minute_sync_minute, timezone="Asia/Seoul"),
                id="ohlcv-minute-batch",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
        else:
            log.warning("MINUTE_SYNC_ENABLED=true 이지만 KIS_APP_KEY/KIS_APP_SECRET 이 없어 1분봉 수집을 등록하지 않습니다.")
    scheduler.start()
    return scheduler
