"""pg-stock 샘플 설정.

원본 ``app.core.config.Settings`` 에서 pg-stock 크롤링·API에 필요한 항목만 남겼다.
환경변수 또는 샘플 루트의 ``.env`` 로 읽는다(이미 설정된 환경변수가 우선).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

SAMPLE_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = SAMPLE_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    app_name: str = "pg-stock OHLCV API sample"
    debug: bool = False
    scheduler_enabled: bool = True

    # ── pg-stock(PostgreSQL) ────────────────────────────────────────────
    ohlcv_database_url: str = "postgresql+psycopg://admin:admin1234@localhost:55432/admin"

    # ── OHLCV 배치 ──────────────────────────────────────────────────────
    ohlcv_sync_enabled: bool = True
    # listed: KOSPI·KOSDAQ 상장 주식 전체(ETF·ETN·리츠·펀드 제외) | major: 대표 24종목 | all: tickers 테이블 | 005930,000660
    ohlcv_sync_tickers: str = "listed"
    ohlcv_sync_provider: str = "naver"         # naver | yahoo | auto
    ohlcv_sync_start_year: int = 2016          # 이 해 1월 1일부터 (약 10년치)
    ohlcv_sync_correction_days: int = 7
    ohlcv_sync_hours: str = "9,12,16"          # Asia/Seoul cron 시(hour) 목록
    ohlcv_sync_hour: int = 16                  # OHLCV_SYNC_HOURS 가 비었을 때만 사용
    ohlcv_sync_interval_hours: int = 24
    ohlcv_sync_minute: int = 50
    ohlcv_sync_max_tickers: int = 0
    ohlcv_sync_request_delay: float = 0.05     # 공급자 요청 사이 대기(초)

    # ── 1분봉 (KIS Open API 주식일별분봉조회, 과거 약 1년 보관) ──────────
    kis_app_key: str = ""                      # 실전 앱키 (모의투자 키는 초당 2건이라 전 종목 수집에 부족)
    kis_app_secret: str = ""
    kis_base_url: str = "https://openapi.koreainvestment.com:9443"
    minute_sync_enabled: bool = False          # 매일 장 마감 후 최근 거래일의 빠진 1분봉 채우기
    minute_sync_hour: int = 17                 # Asia/Seoul. 16:50 일봉 수집이 끝난 뒤
    minute_sync_minute: int = 30
    minute_catchup_days: int = 10              # 최근 몇 거래일까지 빠진 종목·일을 다시 확인할지
    minute_requests_per_second: float = 15.0   # KIS 실전 한도 초당 20건보다 낮게
    minute_workers: int = 2

    # ── Open API 쓰기 엔드포인트(/openapi/v1/ohlcv/ingest) 인증 ─────────
    # 원본은 MariaDB api_key 테이블을 조회하지만, 샘플은 쉼표로 나열한 고정 키를 쓴다.
    ohlcv_api_keys: str = ""


@lru_cache
def get_settings() -> Settings:
    """환경변수를 한 번만 읽어 애플리케이션 전체에서 동일한 설정을 공유한다."""
    return Settings()
