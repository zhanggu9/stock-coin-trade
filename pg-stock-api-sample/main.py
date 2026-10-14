"""pg-stock OHLCV 크롤링·조회 API 샘플 진입점.

    uvicorn main:app --reload --port 8010

기동 시 APScheduler 가 OHLCV 증분 수집을 등록한다(SCHEDULER_ENABLED=false 로 끌 수 있다).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pgstock.api import ohlcv_db, openapi_ohlcv
from pgstock.config import get_settings
from pgstock.errors import install_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션과 모든 라우터·수명주기 훅을 조립한다.

    애플리케이션 객체를 모듈 전역에서 바로 만들 수 있도록 팩토리로 분리했다.
    이 함수가 담당하는 일은 라우터 등록, 공통 오류 처리기 설치, 스케줄러의
    시작·종료 관리이며, 실제 OHLCV 조회·수집 로직은 각 하위 모듈에 위임한다.
    """
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """프로세스 시작 시 배치 스케줄러를 시작하고 종료 시 정리한다."""
        scheduler = None
        if settings.scheduler_enabled:
            from pgstock.jobs.scheduler import start_scheduler

            scheduler = start_scheduler()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan, debug=settings.debug,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    install_exception_handlers(app)
    app.include_router(ohlcv_db.router)
    app.include_router(openapi_ohlcv.router)

    @app.get("/")
    def root() -> dict:
        """서비스가 살아 있는지 브라우저에서 바로 확인할 수 있는 안내 응답."""
        return {"ok": True, "service": "pg-stock-api-sample", "docs": "/api/docs", "health": "/health"}

    @app.get("/health")
    def health() -> dict:
        """로드밸런서·모니터링이 사용하는 최소 상태 확인 엔드포인트."""
        return {"ok": True, "service": "pg-stock-api-sample"}

    return app


app = create_app()
