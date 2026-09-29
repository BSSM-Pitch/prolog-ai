"""공통 에러 형식과 에러 코드.

응답 형식은 API 명세 공통 규격을 그대로 따른다.
    성공: {"data": ..., "meta": {}}
    실패: {"error": {"code": ..., "message": ..., "details": {}}}
"""

from enum import StrEnum
from typing import Any, NamedTuple


class ErrorCode(StrEnum):
    # 명세(NLCD/REX/AIQ/SCDS/SSM) 공통
    INVALID_INPUT = "INVALID_INPUT"

    # AIQ
    INVALID_SELECTION_RANGE = "INVALID_SELECTION_RANGE"
    AI_RESPONSE_FAILED = "AI_RESPONSE_FAILED"
    AI_RESPONSE_TIMEOUT = "AI_RESPONSE_TIMEOUT"

    # NLCD, REX
    AI_EXTRACTION_FAILED = "AI_EXTRACTION_FAILED"
    AI_EXTRACTION_TIMEOUT = "AI_EXTRACTION_TIMEOUT"

    # SCDS, SSM
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    AI_ANALYSIS_TIMEOUT = "AI_ANALYSIS_TIMEOUT"

    # SCDS
    RULE_ENGINE_ERROR = "RULE_ENGINE_ERROR"

    # SSM
    MANUSCRIPT_TOO_SHORT = "MANUSCRIPT_TOO_SHORT"

    # 모듈 내부용: 명세에 없는 코드. error.code로 내보내지 않는다(WARN.md A4 ①).
    # SCHEMA_VALIDATION_FAILED는 모듈의 AI_*_FAILED로 바꿔 보내고 details.internal_code에만 남긴다.
    AI_TIMEOUT = "AI_TIMEOUT"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"


# 명세에 적힌 HTTP 상태. 내부용 코드는 error.code로 나가지 않으므로 넣지 않는다.
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.INVALID_SELECTION_RANGE: 400,
    ErrorCode.AI_RESPONSE_FAILED: 502,
    ErrorCode.AI_RESPONSE_TIMEOUT: 503,
    ErrorCode.AI_EXTRACTION_FAILED: 502,
    ErrorCode.AI_EXTRACTION_TIMEOUT: 503,
    ErrorCode.AI_ANALYSIS_FAILED: 502,
    ErrorCode.AI_ANALYSIS_TIMEOUT: 503,
    ErrorCode.RULE_ENGINE_ERROR: 500,
    ErrorCode.MANUSCRIPT_TOO_SHORT: 422,
}


class AIErrorCodes(NamedTuple):
    failed: ErrorCode
    timeout: ErrorCode


# 모듈마다 명세의 AI 실패/지연 코드 이름이 다르다.
MODULE_AI_ERRORS: dict[str, AIErrorCodes] = {
    "nlcd": AIErrorCodes(ErrorCode.AI_EXTRACTION_FAILED, ErrorCode.AI_EXTRACTION_TIMEOUT),
    "rex": AIErrorCodes(ErrorCode.AI_EXTRACTION_FAILED, ErrorCode.AI_EXTRACTION_TIMEOUT),
    "aiq": AIErrorCodes(ErrorCode.AI_RESPONSE_FAILED, ErrorCode.AI_RESPONSE_TIMEOUT),
    "scds": AIErrorCodes(ErrorCode.AI_ANALYSIS_FAILED, ErrorCode.AI_ANALYSIS_TIMEOUT),
    "ssm": AIErrorCodes(ErrorCode.AI_ANALYSIS_FAILED, ErrorCode.AI_ANALYSIS_TIMEOUT),
}


def make_error(
    code: ErrorCode | str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": ErrorCode(code).value,
            "message": message,
            "details": dict(details) if details else {},
        }
    }


def make_success(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "meta": dict(meta) if meta else {}}
