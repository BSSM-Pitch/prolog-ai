# 인수인계

백엔드(FastAPI) 팀이 이 패키지를 붙일 때 알아야 할 것만 모았다. 함수 입출력과 에러 코드는 `README.md`를 본다.

## 지금 상태

- 공개 함수(`run_nlcd`, `run_rex`, `run_aiq`, `run_scds`, `run_scds_rules`, `run_scds_analysis`, `run_ssm`)의 인터페이스와 응답 형식은 고정됐다.
- 어떤 입력·AI 오류에도 예외를 던지지 않고 `{"data", "meta"}` 또는 `{"error": {"code", "message", "details"}}`로 반환한다. 공개 함수 × 예외 케이스를 `tests/test_guardrails_modules.py`에서 확인한다.
- 실제 LLM 호출 경로(OpenRouter → DeepSeek)는 가짜 클라이언트 테스트(`tests/test_llm_real_path.py`)와 실제 API 호출(2026-09-29, 8번)로 확인했다. 다섯 모듈 모두 정해진 형식으로 응답한다. 결과는 `WARN.md` "실제 호출 결과".
- 프롬프트는 한두 줄짜리 자리표시 수준이라 결과 품질이 명세 예시에 못 미친다(`WARN.md` T21).

## 연동 체크리스트

1. 설치: `pip install git+https://github.com/BSSM-Pitch/prolog-ai.git` (버전 태그는 아직 없음)
2. 환경변수 `OPENROUTER_API_KEY`(필수), `PROLOG_AI_MODEL`(선택, 기본 `deepseek/deepseek-v4-flash`)을 서버 환경에 넣는다. 운영 환경에는 `USE_FAKE_LLM`을 넣지 않는다. 서버에서 `openrouter.ai`로 나가는 외부 연결이 필요하다. 패키지는 `.env`를 읽지 않는다.
3. 개발·테스트 환경에서는 `USE_FAKE_LLM=1`로 API 없이 돌릴 수 있다.
4. 함수는 동기이고 한 번에 수십 초 걸릴 수 있다. 호출 한 번의 제한은 30초(AIQ·SCDS AI 분석은 90초)이고 재시도까지 합치면 AIQ·SCDS는 최악 약 4분 40초다. 비동기 작업(워커)에서 호출하고, 결과로 작업 상태를 정한다(README "백엔드 작업 상태와 연결"). FastAPI `async def` 안에서 그대로 부르면 그동안 서버 전체가 멈추므로 워커나 `run_in_threadpool`로 부르고, 작업 시간 제한·큐 가시성 타임아웃은 5분 이상으로 둔다(`WARN.md` D8).
5. SCDS는 사건 저장 시 `run_scds_rules`(동기, LLM 없음)로 후보를 먼저 응답하고, `status`가 `queued`면 워커에서 `run_scds_analysis(event, rule_result, characters)`로 AI 분석을 한다. 재시도도 `run_scds_analysis`를 다시 부른다. 확정 캐릭터(ASS ConfirmedCharacter)도 넘겨야 캐릭터 설정이 룰 검출·AI 분석에 들어간다.
6. `SCHEMA_VALIDATION_FAILED`는 HTTP 상태가 미정이라 `HTTP_STATUS.get(code, 502)`처럼 기본값을 둔다.

## 알려진 한계 (자세한 내용은 `docs/specs/claude/WARN.md`)

| 영역 | 한계 | WARN |
| --- | --- | --- |
| SCDS | 룰 검출은 WorldRule `violation_keywords` 매칭(RULE-02)만 된다. 캐릭터 가치관 기반 판정(RULE-01/03/04)은 없어서, 세계관 규칙이 없으면 캐릭터 설정이 있어도 후보가 생기지 않는다 | A2, T14 |
| SSM | 챕터는 "제N장/N장" 줄로만 나눈다. "1화" 형식은 원고 전체가 한 번에 분석되고, 본문 속 "3장의 …"를 경계로 오인할 수 있다 | T5, A10 |
| SSM | 챕터별 결과를 이어붙이므로 노드의 `chapter` 번호와 `acts`가 전체 원고 기준이 아니다 | T6 |
| REX·SSM | 입력 길이 상한이 없다. 긴 원고는 출력 한도(4096 토큰)에 걸려 `AI_*_FAILED`가 날 수 있다 | T9 |
| 공통 | 프롬프트 인젝션 방어(시스템 프롬프트, 입력 구분자)가 없다 | T16 |
| 공통 | `OPENROUTER_API_KEY`가 비어 있으면 서버의 `OPENAI_API_KEY`가 대신 openrouter.ai로 전송된다. 운영 환경에 키를 반드시 넣는다 | T24 |

## 백엔드 팀에 확인이 필요한 것

`WARN.md`의 D(실제 백엔드 코드와 대조한 결과), B(명세끼리 안 맞는 부분), C(db.md와 API 명세 불일치)를 본다. 특히 A14·D1(LLM 호출·룰 엔진을 누가 맡는지)과 D2~D5(NLCD 근거·감정 키워드, SCDS `conflict_target` 저장 칸, AIQ `scope` 값, SSM `character_ids` 타입)는 연동 전에 정해야 한다.
