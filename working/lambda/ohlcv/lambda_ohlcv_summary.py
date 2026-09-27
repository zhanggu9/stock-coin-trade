"""HTTP API 경로별로 pg-stock 집계를 돌려주는 Lambda.

Flask 블루프린트 /api/ohlcv-db/* 와 같은 기능을 /ohlcv/* 경로로 제공한다.
"""
import json
import logging
from urllib.parse import unquote_plus

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

import ohlcv_service as svc
from secret_config import environment_values

logger = logging.getLogger()
config = environment_values(("OHLCV_DATABASE_URL",))
# connect_timeout: DB 에 못 닿으면 Lambda 타임아웃(15s) 대신 5초 안에 503 으로 응답
engine = create_engine(config["OHLCV_DATABASE_URL"], pool_pre_ping=True,
                       connect_args={"connect_timeout": 5})

ROUTES = {
    # DB 없이 200: 배포·ALB 연결 확인용
    "/ohlcv/health": lambda args: {"ok": True, "service": "ohlcv",
                                   "routes": sorted(p for p in ROUTES if p != "/ohlcv/health")},
    "/ohlcv/summary": lambda args: svc.load_summary(engine),
    "/ohlcv/yearly": lambda args: svc.load_yearly(engine),
    "/ohlcv/markets": lambda args: svc.load_markets(engine),
    "/ohlcv/quality": lambda args: svc.load_quality(engine),
    "/ohlcv/tickers": lambda args: svc.load_tickers(engine, args),
    "/ohlcv/rows": lambda args: svc.load_rows(engine, args),
}


def _response(status, payload):
    return {"statusCode": status, "headers": {"content-type": "application/json"},
            "isBase64Encoded": False,           # ALB 타깃 응답 형식에도 맞춤
            "body": json.dumps(payload, ensure_ascii=False, default=str)}


def lambda_handler(event, context):
    # HTTP API v2: rawPath / ALB: path (쿼리값이 URL 인코딩된 채로 옴)
    path = event.get("rawPath") or event.get("path") \
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    args = event.get("queryStringParameters") or {}
    if "elb" in event.get("requestContext", {}):
        args = {k: unquote_plus(v) for k, v in args.items()}
    handler = ROUTES.get(path)
    if handler is None:
        return _response(404, {"message": f"지원하지 않는 경로: {path}"})
    try:
        return _response(200, handler(args))
    except svc.BadRequest as exc:
        return _response(400, {"message": str(exc)})
    except (ValueError, ArithmeticError):
        return _response(400, {"message": "검색 조건의 숫자 또는 날짜 형식이 올바르지 않습니다."})
    except (IndexError, SQLAlchemyError):
        logger.exception("pg-stock 조회 실패: %s", path)
        return _response(503, {"message": "OHLCV 집계를 조회할 수 없습니다."})
