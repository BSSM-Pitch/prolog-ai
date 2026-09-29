"""--real 채점용 의미 비교(LLM-as-a-judge).

expected_values는 명세 예시 문구라, 모델이 같은 뜻을 다른 말로 쓰면 글자 비교로는 항상 실패한다
("마법은 계약 없이 발현될 수 없다" ↔ "모든 주문은 정령과의 계약 없이 사용할 수 없다", WARN.md E9).
그래서 글자 비교(공백 무시)로 먼저 맞춰 보고, 남은 기대값만 LLM에 "같은 뜻인지" 묻는다.

채점 기준(루브릭)을 구체적으로 적고, 판단 이유를 함께 받아 사람이 채점 결과를 검토할 수 있게 한다.
판단 예시는 evals 케이스와 겹치지 않는 값으로 쓴다(겹치면 채점기가 정답을 외운다).
"""

from pydantic import BaseModel, Field

from prolog_ai.core.llm import call_llm

JUDGE_TIMEOUT_SECONDS = 60.0

JUDGE_INSTRUCTION = """\
당신은 정보 추출 결과를 채점하는 평가자다. <expected>의 각 기대값에 대해, <actual> 목록 안에 **같은 뜻**의 항목이 있는지 판단한다.

<rubric>
- 같은 뜻: 핵심 개념이 같고 표현만 다르다. 조사·어미·띄어쓰기·어순 차이, 동의어, 같은 대상을 부르는 다른 이름은 같은 뜻이다
- 같은 뜻: 규칙·문장이라면 금지하거나 요구하는 내용이 같다. 같은 대상을 더 좁게·넓게 부르는 차이는 괜찮다
- 다른 뜻: 핵심 개념이 다르다. 비슷한 분야여도 가리키는 특성이 다르면 다른 뜻이다(예: "성실" ↔ "책임감")
- 다른 뜻: 한쪽이 다른 쪽의 일부만 담아 핵심이 빠졌다
- 판단이 애매하면 다른 뜻으로 본다. 너그럽게 채점하면 품질 문제를 놓친다
</rubric>

<examples>
<example>기대값 "겁 많음", 실제 ["소심함", "고집 셈"] → matched "소심함" (같은 기질)</example>
<example>기대값 "가족 우선", 실제 ["가족을 소중히 여김"] → matched "가족을 소중히 여김" (표현만 다름)</example>
<example>기대값 "분노", 실제 ["슬픔", "외로움"] → matched null (다른 감정)</example>
<example>기대값 "흡혈귀는 초대 없이 집에 들어갈 수 없다", 실제 ["흡혈귀는 집주인의 허락을 받아야만 들어갈 수 있다"] → matched (같은 금지)</example>
</examples>

기대값마다 판단 결과 하나를 respond 도구로 답한다. matched에는 같은 뜻인 실제 항목을 글자 그대로 쓰고, 없으면 null로 둔다.
"""


class Verdict(BaseModel):
    expected: str = Field(description="판단한 기대값 (그대로)")
    matched: str | None = Field(description="같은 뜻인 실제 항목 (글자 그대로). 없으면 null")
    reason: str = Field(description="판단 이유 한 문장")


class JudgeOutput(BaseModel):
    verdicts: list[Verdict]


def _normalize(text: str) -> str:
    return "".join(text.split())


def judge_field(expected: list[str], actual: list[str]) -> tuple[list[str], list[dict]]:
    """(못 찾은 기대값 목록, 판단 기록)을 돌려준다. 글자 비교로 맞은 값은 LLM에 묻지 않는다."""
    normalized_actual = {_normalize(a) for a in actual}
    remaining = [e for e in expected if _normalize(e) not in normalized_actual]
    records = [{"expected": e, "matched": e, "reason": "글자 일치"} for e in expected if e not in remaining]
    if not remaining:
        return [], records
    if not actual:
        return remaining, records + [
            {"expected": e, "matched": None, "reason": "실제 항목 없음"} for e in remaining
        ]

    prompt = (
        f"{JUDGE_INSTRUCTION}\n<expected>\n"
        + "\n".join(f"- {e}" for e in remaining)
        + "\n</expected>\n<actual>\n"
        + "\n".join(f"- {a}" for a in actual)
        + "\n</actual>"
    )
    output = JudgeOutput.model_validate(
        call_llm(prompt, schema=JudgeOutput, timeout=JUDGE_TIMEOUT_SECONDS)
    )
    by_expected = {v.expected: v for v in output.verdicts}
    missing = []
    for e in remaining:
        verdict = by_expected.get(e)
        # 채점기가 지어낸 항목을 matched로 쓰면 인정하지 않는다.
        matched = verdict.matched if verdict and verdict.matched in actual else None
        records.append(
            {"expected": e, "matched": matched, "reason": verdict.reason if verdict else "판단 없음"}
        )
        if matched is None:
            missing.append(e)
    return missing, records
