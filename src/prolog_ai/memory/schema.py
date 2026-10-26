"""인물 → 관찰 → 패턴 → 가설의 작은 온톨로지.

관찰의 인용 위치는 코드가 계산한다. 모델이 제안한 해석은 항상 tentative이며,
반복 횟수와 근거 범위는 모델의 자신감 점수 대신 원문 참조로 계산한다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[Text, Field(max_length=500)]
BehaviorRole = Literal["trigger", "awareness", "desire", "involuntary_reaction", "choice", "other"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Character(Model):
    # ASS ConfirmedCharacter도 받을 수 있다. 사용하지 않는 필드는 기억으로 승격하지 않는다.
    model_config = ConfigDict(extra="ignore", strict=True)
    character_id: Text
    name: Text
    aliases: list[Text] = Field(default_factory=list)


class Scene(Model):
    scene_id: Text
    revision: Text
    order: int = Field(ge=0, le=2147483647, description="독자가 읽는 순서. 작중 시간과 구분한다")
    chapter_id: Text | None = None
    story_time: Text | None = None
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonblank(self):
        if not self.text.strip():
            raise ValueError("scene.text는 공백만일 수 없습니다")
        return self


class Evidence(Model):
    scene_id: Text
    revision: Text
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=1200)


class ObservationDraft(Model):
    character_id: Text | None = Field(description="목록의 ID. 발화/행동 주체를 모르면 null")
    attribution: Literal["certain", "uncertain"]
    kind: Literal["speech", "action", "inner_thought", "narration"]
    presentation: Literal["depicted", "character_claim", "narrator_claim", "thought"]
    behavior_role: BehaviorRole = "other"
    summary: ShortText = Field(description="관찰되는 표현/행동만. 숨은 동기를 단정하지 않는다")
    context: ShortText = Field(description="상대·직전 상황·반응 조건. 원문에서 모르면 미상")
    interlocutor_ids: list[Text] = Field(default_factory=list)
    quote: str = Field(min_length=1, max_length=1200, description="입력의 연속 구절을 그대로 복사")
    occurrence: int = Field(
        default=0, ge=0, description="같은 구절이 입력에 여러 번 나오면 0부터 순번"
    )


class ExtractionOutput(Model):
    observations: list[ObservationDraft]


class Observation(Model):
    observation_id: Text
    character_id: Text | None
    attribution: Literal["certain", "uncertain"]
    kind: Literal["speech", "action", "inner_thought", "narration"]
    presentation: Literal["depicted", "character_claim", "narrator_claim", "thought"]
    behavior_role: BehaviorRole = "other"
    summary: ShortText
    context: ShortText
    interlocutor_ids: list[Text]
    evidence: Evidence


class SpeakerDecision(Model):
    observation_id: Text
    character_id: Text | None
    attribution: Literal["certain", "uncertain"]
    reason: ShortText
    quote: str = Field(min_length=1, max_length=1200)
    occurrence: int = Field(default=0, ge=0)


class SpeakerVerificationOutput(Model):
    decisions: list[SpeakerDecision]

    @classmethod
    def fake_response(cls):
        return {"decisions": []}


class SpeakerResolution(Model):
    observation_id: Text
    character_id: Text | None
    attribution: Literal["certain", "uncertain"]
    reason: ShortText
    evidence_id: Text


class SpeakerResolutionOutput(Model):
    decisions: list[SpeakerResolution]


class SpeakerVerification(Model):
    observation_id: Text
    original_observation_id: Text
    original_character_id: Text | None
    original_attribution: Literal["certain", "uncertain"]
    original_summary: ShortText | None = None
    original_context: ShortText | None = None
    proposed_character_id: Text | None = None
    proposed_attribution: Literal["certain", "uncertain"] | None = None
    adjudicated: bool = False
    reason: ShortText
    evidence: Evidence


class Proposal(Model):
    description: ShortText
    condition: ShortText
    seed_observation_ids: list[Text] = Field(min_length=1)
    hypothesis: ShortText | None = None
    alternatives: list[ShortText] = Field(default_factory=list)


class DiscoveryOutput(Model):
    proposals: list[Proposal]


class Assessment(Model):
    proposal_index: int = Field(ge=0)
    supporting_observation_ids: list[Text]
    counterexample_observation_ids: list[Text]


class AssessmentOutput(Model):
    assessments: list[Assessment]


class Pattern(Model):
    pattern_id: Text
    character_id: Text
    description: ShortText
    condition: ShortText
    supporting_observation_ids: list[Text] = Field(min_length=2)
    counterexample_observation_ids: list[Text]
    supporting_scene_count: int = Field(ge=2)
    counterexample_scene_count: int = Field(ge=0)
    evaluated_observation_count: int = Field(ge=2)
    analyzed_through_order: int = Field(ge=0)
    status: Literal["recurring", "contested"]


class Hypothesis(Model):
    hypothesis_id: Text
    character_id: Text
    pattern_id: Text
    statement: ShortText
    alternatives: list[ShortText]
    status: Literal["tentative"] = "tentative"


class Memory(Model):
    schema_version: Literal[1] = 1
    project_id: Text
    snapshot_id: Text
    analysis_key: Text
    model: Text
    mode: Literal["fake", "real"]
    characters: list[Character]
    scenes: list[Scene]
    observations: list[Observation] = Field(default_factory=list)
    speaker_verifications: list[SpeakerVerification] = Field(default_factory=list)
    speaker_verification_version: Literal["v1"] | None = None
    patterns: list[Pattern] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    processed_scene_ids: list[Text] = Field(default_factory=list)
    complete: bool = False
    # 워커 재개용 캐시. 모델 응답만 저장하며 API 키나 프롬프트는 저장하지 않는다.
    call_cache: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


class CharacterFinding(Model):
    character_id: Text
    kind: Literal["continuation", "development", "possible_inconsistency", "insufficient_evidence"]
    explanation: ShortText
    advice: ShortText
    event_quote: str = Field(min_length=1)
    observation_ids: list[Text]


class CharacterReviewOutput(Model):
    findings: list[CharacterFinding]
