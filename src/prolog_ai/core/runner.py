"""모든 모듈이 공유하는 실행 뼈대: 입력 검증 -> LLM 호출 -> 스키마 검증 -> 근거 대조 -> 반환.

책임 경계: run_module은 "입력 하나 -> LLM 호출 한 번 -> 검증된 출력 하나"만 처리한다.
청킹(SSM)과 룰 검출(SCDS)은 모듈마다 기준이 달라 뼈대 밖(각 모듈의 chunking.py/rules.py와
module.py)에서 수행하고, 그 결과(스킵 여부, 나뉜 입력)만 이 함수에 넘기거나 이 함수를
아예 호출하지 않는다. SCDS는 응답에 status를 붙이기 위해 make_status_response()를 쓰며,
skipped(참조 데이터 없음·후보 없음)일 때는 run_module을 호출하지 않는다.

어떤 예외가 나도 이 함수는 죽지 않고 errors.py 형식으로 반환한다. 빈 결과(추출된 항목이
없음)는 에러가 아니라 빈 배열을 담은 정상 응답이다.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from prolog_ai.core import evidence
from prolog_ai.core.errors import MODULE_AI_ERRORS, ErrorCode, make_error, make_success
from prolog_ai.core.llm import LLMFailedError, LLMTimeoutError, call_llm
from prolog_ai.core.status import RunStatus


class InputValidationError(Exception):
    """validate 콜백이 입력을 거부할 때 던진다.

    code는 기본 INVALID_INPUT이지만, AIQ의 INVALID_SELECTION_RANGE처럼
    모듈 명세가 더 구체적인 코드를 요구하는 경우 지정할 수 있다.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        code: ErrorCode = ErrorCode.INVALID_INPUT,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.code = code


def make_status_response(
    status: RunStatus, data: dict[str, Any], meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    """data에 status를 붙인 성공 응답. SCDS가 skipped/queued/completed를 같은 모양으로 반환할 때 쓴다."""
    return make_success({**data, "status": status.value}, meta)


def run_module(
    *,
    module: str,
    input_data: Any,
    validate: Callable[[Any], Any],
    build_prompt: Callable[[Any], str],
    output_schema: type[BaseModel],
    evidence_text: str | None = None,
    evidence_fields: list[str] = (),
    timeout: float | None = None,
) -> dict[str, Any]:
    ai_errors = MODULE_AI_ERRORS[module]

    try:
        validated = validate(input_data)

        try:
            prompt = build_prompt(validated)
            llm_options = {} if timeout is None else {"timeout": timeout}
            raw_output = call_llm(prompt, schema=output_schema, **llm_options)
        except LLMTimeoutError as exc:
            return make_error(ai_errors.timeout, str(exc))
        except LLMFailedError as exc:
            return make_error(ai_errors.failed, str(exc))

        try:
            parsed = output_schema.model_validate(raw_output)
        except ValidationError as exc:
            # 명세에 없는 내부 코드는 밖으로 내보내지 않고, 모듈의 AI_*_FAILED로 바꿔 details에 남긴다.
            return make_error(
                ai_errors.failed,
                "LLM 응답이 정해진 스키마를 따르지 않습니다.",
                {
                    "internal_code": ErrorCode.SCHEMA_VALIDATION_FAILED.value,
                    "errors": exc.errors(include_url=False),
                },
            )

        data = parsed.model_dump()
        meta: dict[str, Any] = {}

        if evidence_text is not None and evidence_fields:
            data, removed_count = evidence.filter_unverified(
                data, evidence_text, list(evidence_fields)
            )
            meta["removed_evidence_count"] = removed_count

        return make_success(data, meta)

    except InputValidationError as exc:
        return make_error(exc.code, exc.message, exc.details)
    except Exception as exc:  # noqa: BLE001 - 최후 방어선: 절대 죽지 않는다
        return make_error(ai_errors.failed, f"예상하지 못한 오류가 발생했습니다: {exc}")
