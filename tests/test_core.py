import enum
import json
from typing import Literal

import pytest
from pydantic import BaseModel

from prolog_ai.core.errors import (
    HTTP_STATUS,
    MODULE_AI_ERRORS,
    ErrorCode,
    make_error,
    make_success,
)
from prolog_ai.core.evidence import filter_unverified, is_present, normalize
from prolog_ai.core.llm import _build_fake_instance
from prolog_ai.core.runner import make_status_response
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


# --- evidence.py ---


def test_normalize_ignores_whitespace_and_quote_style():
    assert normalize("책임감이  강하지만\n") == normalize("책임감이 강하지만")
    assert normalize("“고인”") == normalize('"고인"')


def test_is_present_true_when_evidence_in_source():
    assert is_present("책임감이 강하지만", "그는 책임감이\n강하지만 자신감이 부족했다.")


def test_is_present_false_when_evidence_missing():
    assert not is_present("전혀 다른 문장", "그는 책임감이 강하지만 자신감이 부족했다.")


def test_is_present_false_for_empty_evidence():
    assert not is_present("", "아무 원문")


@pytest.mark.parametrize("evidence", ["   ", "\n\t", None])
def test_is_present_false_for_blank_evidence(evidence):
    assert not is_present(evidence, "아무 원문")


@pytest.mark.parametrize("evidence", ["「계약」", "『계약』", '"계약"', "“계약”"])
def test_korean_quote_brackets_are_normalized(evidence):
    assert is_present(evidence, "그는 『계약』을 맺었다.")


def test_filter_unverified_removes_only_unverified_items():
    data = {
        "personality_tags": [
            {"value": "책임감 강함", "evidence": "책임감이 강하지만"},
            {"value": "지어낸 항목", "evidence": "원문에 없는 문장"},
        ]
    }
    filtered, removed = filter_unverified(
        data, "그는 책임감이 강하지만 자신감이 부족했다.", ["personality_tags"]
    )
    assert filtered["personality_tags"] == [{"value": "책임감 강함", "evidence": "책임감이 강하지만"}]
    assert removed == 1


def test_filter_unverified_does_not_mutate_input():
    data = {"items": [{"value": "a", "evidence": "없는 근거"}]}
    filter_unverified(data, "전혀 다른 원문", ["items"])
    assert data["items"] == [{"value": "a", "evidence": "없는 근거"}]


# --- llm.py ---


class _NestedFake(BaseModel):
    label: str


class _FakeSchema(BaseModel):
    required_text: str
    required_count: int
    required_flag: bool
    required_list: list[str]
    required_nested: _NestedFake
    optional_text: str | None = None


def test_build_fake_instance_fills_only_required_fields_with_typed_defaults():
    fake = _build_fake_instance(_FakeSchema)
    assert fake == {
        "required_text": "",
        "required_count": 0,
        "required_flag": False,
        "required_list": [],
        "required_nested": {"label": ""},
    }
    _FakeSchema.model_validate(fake)  # 스키마 자체를 통과해야 한다


class _Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class _ChoiceSchema(BaseModel):
    kind: Literal["event", "turning_point"]
    color: _Color
    maybe_kind: Literal["a", "b"] | None


def test_build_fake_instance_supports_literal_and_enum():
    fake = _build_fake_instance(_ChoiceSchema)
    parsed = _ChoiceSchema.model_validate(fake)
    assert parsed.kind == "event"
    assert parsed.color is _Color.RED
    assert parsed.maybe_kind == "a"


# --- runner.py ---


def test_make_status_response_shape():
    result = make_status_response(
        RunStatus.SKIPPED,
        {"check_id": "chk_1"},
        {"skipped_reason": SkippedReason.NO_REFERENCE_DATA.value},
    )
    assert result == {
        "data": {"check_id": "chk_1", "status": "skipped"},
        "meta": {"skipped_reason": "NO_REFERENCE_DATA"},
    }


# --- error.details는 항상 JSON(jsonb)으로 저장할 수 있어야 한다 ---


def test_error_details_are_json_safe():
    import json

    from prolog_ai.core.errors import ErrorCode, make_error

    cyclic: dict = {}
    cyclic["self"] = cyclic

    class BadRepr:
        def __repr__(self):
            raise RuntimeError("bad repr")

    details = {
        "bytes": b"x",
        "obj": BadRepr(),
        "nan": float("nan"),
        "enum": ErrorCode.INVALID_INPUT,
        "cyclic": cyclic,
        1: "non-str key",
    }
    error = make_error(ErrorCode.INVALID_INPUT, "m", details)["error"]
    json.dumps(error, allow_nan=False)
    assert error["details"]["bytes"] == "b'x'"
    assert error["details"]["obj"] == "<BadRepr>"
    assert error["details"]["nan"] == "nan"
    assert error["details"]["enum"] == "INVALID_INPUT"
    assert error["details"]["1"] == "non-str key"


def test_cyclic_selection_range_is_still_invalid_selection_range():
    from prolog_ai import run_aiq

    cyclic: dict = {}
    cyclic["self"] = cyclic
    result = run_aiq("q", "원고 본문", "selection", cyclic)
    assert result["error"]["code"] == "INVALID_SELECTION_RANGE"
