# 인수인계

백엔드(FastAPI) 팀이 이 패키지를 붙일 때 알아야 할 것만 모았다. 함수 입출력과 에러 코드는 `README.md`를 본다.

## 지금 상태

- 0.1.0에 선택적 인물 기억 계층이 추가됐다. 원문 장면 전체 목록과 확정 인물 목록을
  `run_character_memory`에 넘겨 구축하고 AIQ/SCDS의 `memory=`에 연결한다.
  기존 기억 없는 호출은 유지된다. 워커 재개/저장/시점 제한/품질 평가의 계약은
  [character-memory.md](character-memory.md)를 따른다.
  기억 검토를 쓸 때는 SCDS rules가 skipped여도 워커를 실행해야 한다.

- 2026-10-26 전체 18장 기억 구축과 동일 14문항 재시험을 완료했다. 최종 답변은 14/14개
  완료했으며 엄격한 의미 채점은 완전 통과 4개·부분 통과 5개·오답 5개다. 원문 근거 회수와
  구조적 완결성의 개선을 의미 정확도와 구분해야 한다. 최신 수치와 평가 한계는
  [전체 기억 재시험](character-memory.md#전체-기억-구축과-동일-14문항-재시험-2026-10-26)에 있다.

- NVIDIA Step 5 선택 경로를 추가했다(`PROLOG_AI_PROVIDER=nvidia`). 2026-10-22 실제
  인물 기억 평가는 요청 9회 중 7회가 시간 초과였고 두 사례 모두 미완료다. 일부 원문
  디테일 회수는 확인했지만 장편/심리 해석 품질을 통과한 것으로 취급하지 않는다.
  상세 결과와 재개 checkpoint는 [character-memory.md](character-memory.md)에 연결돼 있다.

- 공개 함수(`run_nlcd`, `run_rex`, `run_aiq`, `run_scds`, `run_scds_rules`, `run_scds_analysis`, `run_ssm`)의 인터페이스와 응답 형식은 고정됐다.
- 어떤 입력·AI 오류에도 예외를 던지지 않고 `{"data", "meta"}` 또는 `{"error": {"code", "message", "details"}}`로 반환한다. 공개 함수 × 예외 케이스를 `tests/test_guardrails_modules.py`에서 확인한다.
- 실제 LLM 호출 경로(OpenRouter → DeepSeek)는 가짜 클라이언트 테스트(`tests/test_llm_real_path.py`)와 실제 API 호출(2026-09-29, 8번)로 확인했다. 다섯 모듈 모두 정해진 형식으로 응답한다. 결과는 `WARN.md` "실제 호출 결과".
- 다섯 모듈 프롬프트는 명세 기준을 옮겨 결과가 명세 예시에 가까워졌다. 남은 한계(REX 위반 키워드 검출률 등)는 `WARN.md` "실제 호출 결과 3".

## 연동 체크리스트

1. 설치: `pip install git+https://github.com/BSSM-Pitch/prolog-ai.git` (버전 태그는 아직 없음)
2. 기본 제공사/모델은 NVIDIA `z-ai/glm-5.3-flash`다. `NVIDIA_API_KEY`를 서버 환경에 넣는다.
   `PROLOG_AI_REASONING_EFFORT`는 기본 `low`이며 `high`·`max`도 가능하다.
   기존 OpenRouter는 `PROLOG_AI_PROVIDER=openrouter`와 `OPENROUTER_API_KEY`로 선택한다.
   OpenRouter의 기본 모델은 `deepseek/deepseek-v4-flash`다. 기존 `.env`에 명시한 제공사/모델은
   기본값보다 우선하므로 전환 시 함께 수정한다. 키는 해당 제공사의 API에만 전송한다.
   운영 환경에는 `USE_FAKE_LLM`을 넣지 않는다. 패키지는 `.env`를 읽지 않는다.
3. 개발·테스트 환경에서는 `USE_FAKE_LLM=1`로 API 없이 돌릴 수 있다.
4. 함수는 동기이고 한 번에 수십 초 걸릴 수 있다. 호출 한 번의 제한은 NLCD 30초, REX·AIQ·SCDS·SSM 90초(SSM은 챕터마다)이고 재시도까지 합치면 한 번 호출에 최악 약 4분 40초다. 비동기 작업(워커)에서 호출하고, 결과로 작업 상태를 정한다(README "백엔드 작업 상태와 연결"). FastAPI `async def` 안에서 그대로 부르면 그동안 서버 전체가 멈추므로 워커나 `run_in_threadpool`로 부르고, 작업 시간 제한·큐 가시성 타임아웃은 5분 이상으로 둔다(`WARN.md` D8).
5. SCDS는 사건 저장 시 `run_scds_rules`(동기, LLM 없음)로 후보를 먼저 응답하고, `status`가 `queued`일 때만 AI 작업(`conflict_check`)을 만들어 워커에서 `run_scds_analysis(event, rule_result, characters)`로 AI 분석을 한다. 재시도도 `run_scds_analysis`를 다시 부른다. 확정 캐릭터(ASS ConfirmedCharacter)도 넘겨야 캐릭터 설정이 룰 검출·AI 분석에 들어간다.
6. 백엔드 값에 맞춘 것: AIQ `scope`는 `project`/`chapter`/`selection`(`qa_threads_scope_chk`), SSM 노드 `character_ids`는 `run_ssm(..., characters=)`로 넘긴 확정 캐릭터의 `character_id`만(`structure_node_characters` 외래키), NLCD 중복 값은 `character_attributes` 유니크 인덱스 기준으로 합친다. SCDS 상태값은 `jobs.status`와 같아 그대로 저장한다(후보 없음도 `skipped`, `rule_result`로 구분). 무시한 충돌 억제는 백엔드 `conflict_suppressions`로 거른다.
7. 반환되는 `error.code`는 모두 `HTTP_STATUS`에 있다. AI 응답이 스키마와 안 맞으면 `AI_*_FAILED`(502)로 오고, `details.internal_code`가 `SCHEMA_VALIDATION_FAILED`다.

## 알려진 한계 (자세한 내용은 `docs/specs/claude/WARN.md`)

기억을 사용하는 `run_aiq`는 이제 원문 정독과 재검토 두 단계를 기본 실행한다.
`content`는 최종 답변이고 `moments`·`review_notes`·`draft`는 추가 정보다.
기존 단일 호출은 `review_character_details=False`로 선택한다. 오류 코드는 기존 AIQ 코드를
유지한다. 별도 `run_character_reading(question, scenes, characters)`도 공개한다.
정독 호출은 단계당 180초, 자동 재시도 없이 실패한 검토 단계부터 재개할 수 있다.
긴 원고에는 검색 계획 호출을 추가하므로 기본 호출 수는 짧은 원고 2회, 긴 원고 3회다.
원문 32,000자 예산으로 빠진 검색 장면은 `coverage.omitted_scene_ids`에 표시된다.
정독 결과의 잠정 해석은 인물 기억에 자동 병합하지 않는다.

| 영역 | 한계 | WARN |
| --- | --- | --- |
| SCDS | 룰 검출은 WorldRule `violation_keywords` 매칭(RULE-02)만 된다. 캐릭터 가치관 기반 판정(RULE-01/03/04)은 없어서, 세계관 규칙이 없으면 캐릭터 설정이 있어도 후보가 생기지 않는다 | A2, T14 |
| SSM | 챕터는 "제N장/N장" 줄로만 나눈다. "1화" 형식은 원고 전체가 한 번에 분석되고, 본문 속 "3장의 …"를 경계로 오인할 수 있다 | T5, A10 |
| SSM | 챕터별 결과를 이어붙이므로 노드의 `chapter` 번호와 `acts`가 전체 원고 기준이 아니다 | T6 |
| REX·SSM | 입력 길이 상한이 없다. 아주 긴 원고는 출력 한도(16384 토큰, 추론 토큰 포함)에 걸려 `AI_*_FAILED`가 날 수 있다 | T9 |
| SCDS | 룰 검출은 위반 키워드 문자열 일치라, 표현이 다른 위반은 놓치고 규칙을 지키는 장면도 일부 후보가 된다(후보는 AI 분석이 다시 거른다) | T21, A2 |

## 백엔드 팀에 확인이 필요한 것

`WARN.md`의 D(실제 백엔드 코드와 대조한 결과), B(명세끼리 안 맞는 부분), C(db.md와 API 명세 불일치)를 본다. 특히 A14·D1(LLM 호출·룰 엔진을 누가 맡는지)과 D2~D5(NLCD 근거·감정 키워드, SCDS `conflict_target` 저장 칸, AIQ `scope` 값, SSM `character_ids` 타입)는 연동 전에 정해야 한다.
