"""JSON 오류 응답.

프런트엔드는 ``data.error || data.message``를 표시하므로 기존 Flask 응답 본문 형식을 그대로 유지한다.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """상태 코드와 JSON 본문을 그대로 지정하는 애플리케이션 오류."""

    def __init__(self, status_code: int, **body: Any):
        """HTTP 상태 코드와 JSON 응답 본문을 보관한다."""
        super().__init__(body.get("message") or body.get("error") or str(status_code))
        self.status_code = status_code
        self.body = body


def unauthorized(message: str = "로그인이 필요합니다.", **extra: Any) -> ApiError:
    """인증 실패 응답을 일관된 형식으로 생성한다."""
    return ApiError(401, error="UNAUTHORIZED", message=message, **extra)


def json_error(status_code: int, **body: Any) -> JSONResponse:
    """예외 처리기에서 사용할 JSON 응답을 간단히 만든다."""
    return JSONResponse(body, status_code=status_code)


def _validation_message(exc: RequestValidationError) -> str:
    """FastAPI 검증 오류를 외부 API의 짧은 한국어 메시지로 변환한다."""
    parts = []
    for item in exc.errors()[:3]:
        if item.get("type") == "json_invalid":
            return "JSON 본문 형식이 올바르지 않습니다."
        location = ".".join(str(piece) for piece in item.get("loc", ()) if piece not in ("body", "query", "path"))
        parts.append(f"{location} 값이 올바르지 않습니다." if location else "요청 값이 올바르지 않습니다.")
    return " ".join(dict.fromkeys(parts)) or "요청 형식이 올바르지 않습니다."


def install_exception_handlers(app: FastAPI) -> None:
    """애플리케이션 전역에 오류 종류별 JSON 응답 처리기를 등록한다."""
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        """도메인 오류에 담긴 상태 코드와 본문을 그대로 반환한다."""
        return JSONResponse(exc.body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """FastAPI 기본 422 대신 기존 클라이언트 호환용 400을 반환한다."""
        # Flask 시절과 같이 잘못된 요청은 400으로 응답한다(FastAPI 기본 422 대신).
        return JSONResponse({"error": "INVALID_REQUEST", "message": _validation_message(exc)}, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """404·405 등 Starlette HTTP 오류도 동일한 JSON 모양으로 통일한다."""
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse(detail, status_code=exc.status_code, headers=getattr(exc, "headers", None))
