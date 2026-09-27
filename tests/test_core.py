import json

import pytest

from prolog_ai.core.errors import (
    HTTP_STATUS,
    MODULE_AI_ERRORS,
    ErrorCode,
    make_error,
    make_success,
)
from prolog_ai.core.status import (
    AIQMessageStatus,
    NLCDStatus,
    REXStatus,
    RunStatus,
    SCDSCheckStatus,
    SkippedReason,
    SSMStatus,
)

MODULES = ["nlcd", "rex", "aiq", "scds", "ssm"]
INTERNAL_CODES = {ErrorCode.AI_TIMEOUT, ErrorCode.SCHEMA_VALIDATION_FAILED}


def test_make_error_shape():
    result = make_error(ErrorCode.INVALID_INPUT, "빈 입력입니다.", {"field": "source_text"})
    assert result == {
        "error": {
            "code": "INVALID_INPUT",
            "message": "빈 입력입니다.",
            "details": {"field": "source_text"},
        }
    }


def test_make_error_details_default_empty_dict():
    assert make_error(ErrorCode.AI_ANALYSIS_FAILED, "실패")["error"]["details"] == {}


def test_make_error_accepts_code_string():
    assert make_error("AI_RESPONSE_TIMEOUT", "지연")["error"]["code"] == "AI_RESPONSE_TIMEOUT"


def test_make_error_rejects_unknown_code():
    with pytest.raises(ValueError):
        make_error("MADE_UP_CODE", "x")


def test_make_error_does_not_share_details():
    details = {"a": 1}
    result = make_error(ErrorCode.INVALID_INPUT, "x", details)
    details["a"] = 2
    assert result["error"]["details"] == {"a": 1}


def test_make_success_shape():
    assert make_success({"items": []}) == {"data": {"items": []}, "meta": {}}
    assert make_success([], {"removed_count": 1}) == {"data": [], "meta": {"removed_count": 1}}


def test_responses_are_json_serializable():
    json.dumps(make_error(ErrorCode.INVALID_INPUT, "x", {"k": "v"}))
    json.dumps(make_success({"status": RunStatus.COMPLETED}))


def test_every_spec_code_has_http_status_and_internal_codes_do_not():
    for code in ErrorCode:
        if code in INTERNAL_CODES:
            assert code not in HTTP_STATUS
        else:
            assert code in HTTP_STATUS


def test_module_ai_errors_cover_all_modules():
    assert set(MODULE_AI_ERRORS) == set(MODULES)
    for codes in MODULE_AI_ERRORS.values():
        assert HTTP_STATUS[codes.failed] == 502
        assert HTTP_STATUS[codes.timeout] == 503


@pytest.mark.parametrize(
    "enum_cls, values",
    [
        (NLCDStatus, {"analyzing", "completed", "failed"}),
        (REXStatus, {"queued", "extracting", "completed", "failed"}),
        (AIQMessageStatus, {"pending", "completed", "failed"}),
        (
            SCDSCheckStatus,
            {"skipped", "no_candidate", "queued", "analyzing", "completed", "failed"},
        ),
        (SSMStatus, {"queued", "analyzing", "completed", "failed"}),
    ],
)
def test_module_status_values_match_spec(enum_cls, values):
    assert {s.value for s in enum_cls} == values


def test_run_status_values_exist_in_module_status():
    module_values = {"completed", "failed"}
    for enum_cls in (NLCDStatus, REXStatus, AIQMessageStatus, SSMStatus):
        assert module_values <= {s.value for s in enum_cls}
    assert {s.value for s in RunStatus} <= {s.value for s in SCDSCheckStatus}


def test_skipped_reason_value():
    assert SkippedReason.NO_REFERENCE_DATA == "NO_REFERENCE_DATA"
