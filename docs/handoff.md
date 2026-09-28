# 인수인계

백엔드(FastAPI) 팀이 이 패키지를 붙일 때 알아야 할 것만 모았다. 함수 입출력과 에러 코드는 `README.md`를 본다.

## 지금 상태

- 공개 함수(`run_nlcd`, `run_rex`, `run_aiq`, `run_scds`, `run_scds_rules`, `run_scds_analysis`, `run_ssm`)의 인터페이스와 응답 형식은 고정됐다.
- 어떤 입력·AI 오류에도 예외를 던지지 않고 `{"data", "meta"}` 또는 `{"error": {"code", "message", "details"}}`로 반환한다. 다섯 함수 × 예외 케이스를 `tests/test_guardrails_modules.py`에서 확인한다.
- 실제 LLM 호출 경로(OpenRouter → DeepSeek)는 가짜 클라이언트로만 검증했다(`tests/test_llm_real_path.py`). **실제 API로 돌려본 적은 없다.**
- 프롬프트는 한두 줄짜리 자리표시 수준이다. 결과 품질은 검증하지 않았다.

## 연동 체크리스트

1. 설치: `pip install git+https://github.com/BSSM-Pitch/prolog-ai.git` (버전 태그는 아직 없음)
2. 환경변수 `OPENROUTER_API_KEY`(필수), `PROLOG_AI_MODEL`(선택, 기본 `deepseek/deepseek-v4-flash`)을 서버 환경에 넣는다. 운영 환경에는 `USE_FAKE_LLM`을 넣지 않는다. 서버에서 `openrouter.ai`로 나가는 외부 연결이 필요하다. 패키지는 `.env`를 읽지 않는다.
3. 개발·테스트 환경에서는 `USE_FAKE_LLM=1`로 API 없이 돌릴 수 있다.
4. 함수는 동기이고 한 번에 수십 초 걸릴 수 있다. 호출 한 번의 제한은 30초(AIQ는 90초)이고 재시도까지 합치면 AIQ는 최악 약 4분 40초다. 비동기 작업(워커)에서 호출하고, 결과로 작업 상태를 정한다(README "백엔드 작업 상태와 연결").
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
| 공통 | 모델·키 환경변수가 비어 있어도 그대로 호출을 시도하고, 실패하면 `AI_*_FAILED`로 반환된다 | CLAUDE.md 8단계 |

## 백엔드 팀에 확인이 필요한 것

`WARN.md`의 B(명세끼리 안 맞는 부분)와 C(DB 설계와 API 명세 불일치)를 본다. 특히 C1·C2(근거·감정 키워드·작업 상태를 저장할 곳이 DB에 없음)는 연동 전에 정해야 한다.
