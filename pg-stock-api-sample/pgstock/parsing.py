"""요청 값 파싱 헬퍼. 기존 API의 관대한 입력 처리(문자열 숫자 허용, 범위 클램프)를 유지한다."""

from __future__ import annotations

from typing import Any


def parse_int(value: Any, default: int | None = None) -> int | None:
    """정수로 바꿀 수 없으면 default를 돌려준다. bool은 정수로 취급하지 않는다."""
    if isinstance(value, bool):
        return default
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float | None = None) -> float | None:
    """임의 입력을 float로 변환하고 실패하면 기본값을 반환한다."""
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: int, minimum: int, maximum: int) -> int:
    """정수를 [minimum, maximum] 범위로 잘라 페이지 크기 등을 안전하게 제한한다."""
    return max(minimum, min(value, maximum))
