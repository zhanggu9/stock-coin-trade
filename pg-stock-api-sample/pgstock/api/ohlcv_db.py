"""별도 OHLCV 저장소(pg-stock) 읽기 전용 집계 API."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy.exc import SQLAlchemyError

from pgstock.errors import ApiError
from pgstock.parsing import clamp
from pgstock.services import ohlcv_store

router = APIRouter(prefix="/api/ohlcv-db", tags=["ohlcv"])
logger = logging.getLogger(__name__)


def _optional_number(raw: str) -> Decimal | None:
    """빈 문자열은 필터 미사용으로, 값이 있으면 정확한 Decimal로 변환한다."""
    raw = raw.strip()
    return Decimal(raw) if raw else None


def _optional_date(raw: str) -> date | None:
    """빈 날짜 필터는 None으로 두고, 입력된 날짜는 ISO 형식으로 검증한다."""
    raw = raw.strip()
    return date.fromisoformat(raw) if raw else None


@router.get("/summary")
def summary() -> dict:
    """대시보드용 사전 계산 집계와 마지막 동기화 상태를 반환한다."""
    try:
        return ohlcv_store.summary()
    except (IndexError, SQLAlchemyError):
        logger.exception("Failed to query OHLCV summary")
        raise ApiError(503, message="OHLCV 일일 집계가 아직 준비되지 않았습니다.")


@router.get("/tickers")
def tickers(q: str = Query(""), limit: int = Query(100), offset: int = Query(0)) -> dict:
    """종목별 행 수·기간·연도별 적재량을 페이지 단위로 반환한다."""
    try:
        return ohlcv_store.ticker_summaries(q.strip().upper(), clamp(limit, 1, 200), max(0, offset))
    except (ValueError, SQLAlchemyError):
        logger.exception("Failed to query OHLCV ticker summary")
        raise ApiError(503, message="종목별 OHLCV 집계를 조회할 수 없습니다.")


@router.get("/rows")
def rows(q: str = Query(""), market: str = Query(""), date_from: str = Query(""), date_to: str = Query(""),
         min_close: str = Query(""), max_close: str = Query(""), min_volume: str = Query(""), max_volume: str = Query(""),
         limit: str = Query("100"), offset: str = Query("0"), sort: str = Query("trade_date"), order: str = Query("desc")) -> dict:
    """AG Grid infinite row model용 필터링된 일별 OHLCV 행."""
    try:
        filters = {
            "date_from": _optional_date(date_from), "date_to": _optional_date(date_to),
            "min_close": _optional_number(min_close), "max_close": _optional_number(max_close),
            "min_volume": _optional_number(min_volume), "max_volume": _optional_number(max_volume),
            "limit": clamp(int(limit), 1, 500), "offset": clamp(int(offset), 0, 10_000_000),
        }
    except (ValueError, ArithmeticError):
        raise ApiError(400, message="검색 조건의 숫자 또는 날짜 형식이 올바르지 않습니다.")
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise ApiError(400, message="시작일은 종료일보다 늦을 수 없습니다.")
    try:
        return ohlcv_store.filtered_rows(query=q.strip(), market=market.strip(), sort=sort.strip(),
                                         direction=order.strip().lower(), **filters)
    except SQLAlchemyError:
        logger.exception("Failed to query filtered OHLCV rows")
        raise ApiError(503, message="OHLCV 상세 데이터를 조회할 수 없습니다.")
