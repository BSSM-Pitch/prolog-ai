"""공개 함수 방어: 어떤 인자·예외가 와도 errors.py 형식으로 반환.

run_module은 자기 안에서 나는 예외만 막는다. SCDS 룰 검출, SSM 청킹·병합처럼
run_module 밖에서 도는 코드와, 호출 인자 자체가 틀린 경우는 @public_api가 막는다.
타입 검증 헬퍼(expect_*)는 틀린 입력을 AI 실패가 아니라 INVALID_INPUT으로 분류하기 위해 쓴다.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from prolog_ai.core.errors import MODULE_AI_ERRORS, ErrorCode, make_error
from prolog_ai.core.runner import InputValidationError


def public_api(module: str, unexpected_code: ErrorCode | None = None) -> Callable:
    """unexpected_code를 주지 않으면 예상 못 한 예외는 모듈의 AI_*_FAILED로 반환한다."""
    fallback_code = unexpected_code or MODULE_AI_ERRORS[module].failed

    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                signature.bind(*args, **kwargs)
            except TypeError as exc:
                return make_error(
                    ErrorCode.INVALID_INPUT, "함수 인자가 올바르지 않습니다.", {"reason": str(exc)}
                )

            try:
                return fn(*args, **kwargs)
            except InputValidationError as exc:
                return make_error(exc.code, exc.message, exc.details)
            except Exception as exc:  # noqa: BLE001 - 공개 함수는 절대 죽지 않는다
                return make_error(fallback_code, f"예상하지 못한 오류가 발생했습니다: {exc}")

        return wrapper

    return decorator


def expect_type(value: Any, expected: type, field: str) -> Any:
    # bool은 int의 하위 타입이라 정수 자리에 True/False가 들어오는 것을 따로 막는다.
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        raise InputValidationError(
            f"{field}는 {expected.__name__} 타입이어야 합니다.",
            {"field": field, "expected": expected.__name__, "received": type(value).__name__},
        )
    return value


def expect_text(value: Any, field: str) -> str:
    """문자열이면서 공백만 있지 않아야 한다."""
    expect_type(value, str, field)
    if not value.strip():
        raise InputValidationError(f"{field}가 비어 있습니다.", {"field": field})
    return value


def expect_list_of(value: Any, item_type: type, field: str) -> list:
    expect_type(value, list, field)
    for index, item in enumerate(value):
        expect_type(item, item_type, f"{field}[{index}]")
    return value
