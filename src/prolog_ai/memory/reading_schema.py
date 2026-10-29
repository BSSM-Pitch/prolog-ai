"""한 번뿐인 행동·인지의 어긋남도 출처와 함께 기록하는 정독 출력."""

from typing import Literal

from pydantic import Field, model_validator

from prolog_ai.memory.schema import BehaviorRole, Model, Scene, ShortText, Text


class ReadingSource(Scene):
    source_scene_id: Text | None = None
    source_start: int = Field(default=0, ge=0)
    source_order: int | None = Field(default=None, ge=0)


class ReadingPlan(Model):
    requirements: list[ShortText] = Field(min_length=1, max_length=4)
    search_queries: list[ShortText] = Field(min_length=1, max_length=8)

    @classmethod
    def fake_response(cls):
        return {"requirements": ["질문에 답할 근거가 있는가"], "search_queries": ["소설 인물"]}


class AnswerCoverage(Model):
    requirement_index: int = Field(ge=0)
    status: Literal["answered", "unknown"]
    answer_excerpt: str = Field(
        min_length=1,
        max_length=1500,
        description="최종 content에서 이 요구에 답한 연속 문장을 그대로 복사",
    )


class ReadingReference(Model):
    scene_id: Text
    quote: str = Field(min_length=1, max_length=1200)
    occurrence: int = Field(default=0, ge=0)


class BehaviorClaim(Model):
    role: BehaviorRole
    statement: ShortText
    evidence: list[ReadingReference] = Field(min_length=1, max_length=4)


class CharacterMoment(Model):
    character_id: Text
    observations: list[BehaviorClaim] = Field(min_length=1, max_length=10)
    interpretation: ShortText | None
    # 해석은 사실로 승격하지 않는다. 반복 패턴이나 두 장면을 필수로 요구하지 않는다.
    interpretation_status: Literal["tentative"] = "tentative"
    alternatives: list[ShortText] = Field(max_length=4)
    counterevidence: list[ReadingReference] = Field(max_length=4)


class ReadingDraft(Model):
    content: str = Field(
        min_length=1,
        max_length=6000,
        description="사용자 질문에 직접 답하는 최종 문장. 검토 과정/초안 평가/필드 설명은 넣지 않는다.",
    )
    certainty: Literal["supported", "tentative", "insufficient_evidence"]
    answer_evidence: list[ReadingReference] = Field(max_length=16)
    moments: list[CharacterMoment] = Field(max_length=8)

    @classmethod
    def fake_response(cls):
        result = {
            "content": "[FAKE] 실제 인물 분석을 수행하지 않은 형식 확인용 응답입니다.",
            "certainty": "insufficient_evidence",
            "answer_evidence": [],
            "moments": [],
        }
        if "verdict" in cls.model_fields:
            result.update(verdict="insufficient_evidence", review_notes=[])
            result["coverage_checks"] = [
                {"requirement_index": 0, "status": "unknown", "answer_excerpt": result["content"]}
            ]
        return result

    @model_validator(mode="after")
    def grounded_answer(self):
        if not self.content.strip():
            raise ValueError("답변이 비어 있습니다")
        if self.certainty != "insufficient_evidence" and not self.answer_evidence:
            raise ValueError("답변의 원문 근거가 필요합니다")
        return self


class ReadingNote(Model):
    kind: Literal[
        "missed_context",
        "unsupported_inference",
        "overgeneralization",
        "speaker_or_time",
        "alternative",
        "insufficient_evidence",
    ]
    explanation: ShortText
    evidence: list[ReadingReference] = Field(max_length=4)


class ReadingRevision(ReadingDraft):
    verdict: Literal["retained", "revised", "insufficient_evidence"]
    review_notes: list[ReadingNote] = Field(max_length=8)
    coverage_checks: list[AnswerCoverage] = Field(min_length=1, max_length=8)
