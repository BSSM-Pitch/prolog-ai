# WARN: 문제점·의문점 정리

명세를 근거로 구현하면서 확인된 문제점과, 팀이 결정해야 하지만 아직 결정되지 않은 항목을 모은 문서다.
(작성: 2026-09-28, 6단계 팀 결정 질문 결과 반영 / 같은 날 직접 테스트 결과 추가 / 2026-09-29 방침 반영)

**방침 (2026-09-29)**: 명세(API 명세, 기획.md, db.md)에 근거가 없는 작업은 하지 않는다. 그런 항목은 "하지 않음(명세 근거 없음)"으로 표시했다. 남은 작업의 담당·순서는 `CLAUDE.md` "후속 작업 계획"에 정리되어 있다.

- **T. 직접 테스트에서 발견한 문제**: 코드가 명세 의도대로 동작하지 않는 것 (20건: 해결 9, 일부 해결 4, 미해결 7). 미해결 중 실제로 기능이 안 되는 것은 "T. 발견한 문제" 절 상단 표(🔴🟠🟡⚪ 등급) 참고
- **A. 팀 결정 항목**: 이 저장소에서 정할 수 있지만 팀 결정이 필요한 것 (13개 중 결정 4, 보류 9)
- **B. 명세끼리 안 맞는 부분**: 명세 원문 수정이 필요한 것 (백엔드·기획 확인)
- **C. DB 설계와 API 명세 불일치**: 이 저장소가 정할 수 없는 것 (백엔드 확인)

담당: NLCD·REX·AIQ = Dev A, SCDS·SSM = Dev B, 공통 = 공동

---

## T. 직접 테스트에서 발견한 문제

### 테스트 방법

main(PR #7 병합 시점) 코드를 대상으로 아래를 확인했다. 실제 Claude API는 호출하지 않았다.

1. 기존 자동 테스트: `pytest` 194개 통과, `ruff check .` 통과, GitHub CI는 PR #2~#7과 main push 전부 성공
2. 탐색 테스트: 다섯 공개 함수를 실제 사용 흐름대로 호출하고, LLM 응답 자리에 원하는 값을 심어 결과와 프롬프트를 관찰
3. 실제 LLM 경로: `anthropic.Anthropic`을 가짜 클라이언트로 바꿔 네트워크 없이 `_call_real_llm`의 재시도·오류 분류·응답 파싱 확인
4. 배포 형태: wheel을 빌드해 따로 설치한 뒤 import·호출 확인

### 이상 없음으로 확인된 것

- wheel에 core와 다섯 모듈이 모두 들어가고, 설치한 패키지에서 `run_*` 다섯 개만 공개되며 호출이 동작함
- 5단계에서 고친 크래시(`run_scds(None, ...)`, `run_ssm(123)`, 인자 누락)는 모두 `INVALID_INPUT`으로 반환됨
- 실제 경로에서 정상 tool_use 응답은 스키마 검증과 근거 대조를 거쳐 정상 반환되고, 타임아웃은 `AI_*_TIMEOUT`, 그 밖의 실패는 `AI_*_FAILED`로 분류됨

### 발견한 문제

해결 이력: 2026-09-28 `fix/test-findings` 브랜치에서 명세·기존 지시만으로 답이 정해지는 항목을 고쳤다(✅ 해결, 🟡 일부 해결). 나머지는 결정이 필요해 남겨 두었다.

심각도 기준: **높음** = 명세의 핵심 기능이 동작하지 않거나 데이터가 사라짐 / **중간** = 운영 중 오류·비용·오판 위험 / **낮음** = 정리 필요

**미해결 7건 중 "안 고치면 실제로 작동 자체가 안 되는 것"만 추려내면 (2026-09-28 재검토):**

패키지 자체는 죽지 않는다. 다섯 함수 모두 어떤 입력에도 정해진 형식으로 응답한다(238개 테스트, main 기준). 아래는 "크래시"가 아니라 "그 기능을 쓰려고 하면 사실상 안 되거나, 특정 조건에서 백엔드가 죽을 수 있는" 것만 골랐다.

| 등급 | 항목 | 안 고치면 실제로 벌어지는 일 |
| --- | --- | --- |
| 🔴 기능이 사실상 없음 | **T14 / A2** (SCDS 가치관 기반 충돌 감지) | RULE-01(캐릭터 가치관 ↔ 위반 키워드 연결)이 없어서, 기획서·SCDS 예시의 핵심 시나리오("폭력 회피" 가치관 캐릭터가 "잔혹하게 살해"라는 사건을 냈을 때 감지)가 **world_rules에 정확히 같은 키워드가 없으면 절대 감지되지 않는다.** 지금은 RULE-02(WorldRule.violation_keywords 매칭)만 되므로, 세계관 규칙을 안 만든 프로젝트는 SCDS가 사실상 아무것도 잡지 못한다 |
| 🔴 기능이 사실상 없음 | **T17** (AIQ 후속 질문) | `run_aiq`에 이전 대화를 넘길 인자가 없어서, 스레드에 몇 번째 질문을 하든 매번 원고만 보고 새로 답한다. AIQ 4.4가 정의하는 "후속 질문" 기능은 호출만 되고 실질적으로 작동하지 않는다 |
| 🟠 조건부로 백엔드가 죽을 수 있음 | **T18 / A4** (`SCHEMA_VALIDATION_FAILED`가 HTTP_STATUS에 없음) | 백엔드가 `HTTP_STATUS[code]`처럼 딕셔너리를 그대로 쓰면, LLM 응답이 스키마와 안 맞는 순간(드물지 않음) `KeyError`로 백엔드가 죽는다. 패키지 자체는 정상 응답을 반환하므로, `HTTP_STATUS.get(code, 502)`처럼 기본값을 넣어 방어하면 지금 당장은 안전하다(README에 이미 안내함) |
| 🟡 정확도만 떨어짐 (기능은 됨) | **T5 / A10** (SSM "1화" 챕터 인식) | 챕터 제목이 "N장" 형식이 아니면 원고 전체가 청크 하나로 처리된다. 결과는 나오지만 챕터별로 사건 위치가 구분되지 않는다 |
| ⚪ 하지 않음 (명세 근거 없음) | T8(.env 미읽음), T9(입력 크기 상한 없음), T16(인젝션 방어 없음) | .env는 백엔드가 환경변수로 넘기면 되고, 나머지 둘은 특정 입력에서만 발생하며 실패해도 정해진 에러 형식으로 응답한다. 명세에 근거가 없어 방침상 하지 않는다 |

정리하면 **SCDS의 가치관 기반 충돌 감지(T14/A2)** 와 **AIQ의 후속 질문(T17)** 두 가지가 "고치지 않으면 그 기능을 쓸 수 없다"에 해당한다. T17(AIQ 후속 질문)과 T2 남은 부분(SCDS 룰 검출/AI 분석 분리)은 오류라기보다 **명세에 있는데 아직 없는 기능**이라 기능 구현 담당(사용자)이 바로 착수할 수 있다. T14/A2는 기획이 RULE-01/03/04 판정 기준을 줘야 풀린다.

| # | 심각도 | 모듈 | 문제 | 확인 방법·결과 | 대응 |
| --- | --- | --- | --- | --- | --- |
| T1 | 높음 | SCDS | **AI 분석에 캐릭터 설정이 전달되지 않는다.** `run_scds`는 `event`, `world_rules`만 받고, 프롬프트에는 사건과 룰 후보만 들어간다. 명세·기획서의 핵심("기존 캐릭터 설정(가치관)과 충돌하는지")을 AI가 판단할 재료가 없다. 2단계에서 만든 `core/mapping.py`도 어디에서도 호출되지 않는다 | 캐릭터 가치관을 넘길 인자가 없음. 생성된 프롬프트에 가치관 없음 | ✅ 해결: `run_scds(..., characters=)`로 ASS 확정 캐릭터를 받아 mapping으로 변환 후 프롬프트에 전달. 캐릭터 설정도 참조 데이터로 인정(둘 다 없을 때만 skipped). RULE-01 판정은 A2 결정 전까지 없음 |
| T2 | 높음 | SCDS | **AI 분석이 실패하면 룰 후보가 사라진다.** 실패 응답은 `{"error": ...}`뿐이라 `rule_result`가 없다. 명세 4.7은 "failed 상태에서는 후보만 표시"하라고 한다. 성공 응답에도 `rule_result`가 없다. 또 명세는 룰 검출(사건 저장 시 동기)과 AI 분석(비동기)을 나누는데, `run_scds` 하나가 둘을 한 번에 해서 백엔드가 나눠 쓸 수 없다 | LLM 실패를 심으면 `{'error': {'code': 'AI_ANALYSIS_FAILED', ...}}`만 반환 | 🟡 일부 해결: AI 실패 시 `error.details.rule_result`, 성공 시 `data.rule_result`로 후보를 남김. **남음 (기능 누락, 사용자 담당)**: SCDS 4.6·4.7·5항 흐름대로 룰 검출(동기)·AI 분석(비동기)을 공개 함수 두 개로 나누기 |
| T3 | 높음 | SCDS | **AI가 지어낸 충돌도 통과한다.** 입력에 없는 `character_id`(char_999)와 후보에 없는 `conflict_target`으로 만든 충돌이 그대로 반환된다. NLCD·REX의 근거 대조 같은 검증이 SCDS에는 없다 | 가짜 응답을 심어 확인 | ✅ 해결: 룰 후보의 (character_id, conflict_target) 조합만 남기고 `meta.removed_conflict_count`에 기록 |
| T4 | 높음 | SSM | **첫 챕터 제목 앞의 글이 버려진다.** "프롤로그: 중요한 복선\n1장 ..."을 나누면 프롤로그가 어느 청크에도 없다 | `split_into_chapters` 결과에 "프롤로그" 없음 | ✅ 해결: 첫 제목 앞 텍스트를 첫 청크로 보존 |
| T5 | 높음 | SSM | **챕터 인식이 흔한 형식에서 틀린다.** MSU 명세 예시 형식인 "1화"는 인식하지 못해 원고 전체가 청크 하나가 된다. 반대로 본문의 "3장의 편지를 썼다"는 챕터 경계로 오인한다 | "1화/2화" 원고 → 청크 1개, "1장…3장의 편지" → 청크 2개 | 미해결: A10 결정(MSU 챕터 목록을 입력으로 받기)이 근본 해결 |
| T6 | 높음 | SSM | **청크를 합친 구조 지도가 깨진다.** 청크마다 LLM이 따로 만든 값을 그대로 이어붙인다. `node_id`가 겹치고(`node_1`, `node_1`), 2장 노드의 `chapter`가 1로 나오며(LLM이 몇 번째 챕터인지 모름), 챕터마다 "발단" act가 새로 생긴다. `edges`가 어느 노드를 가리키는지도 모호해진다 | 두 챕터 원고 병합 결과 확인 | 🟡 일부 해결: 병합 시 node_id를 전체에서 새로 매기고 edges도 바꿈. 없는 노드를 가리키는 edge는 제거(`meta.removed_edge_count`). **남음**: chapter 번호·acts를 전체 원고 기준으로 맞추는 방식 결정(A10과 함께) |
| T7 | 높음 | AIQ | **선택 구간 질문에 원고 전체를 보낸다.** `scope="selection"`이어도 프롬프트에는 `selection_range`로 자른 부분이 아니라 원고 전체가 들어간다. 범위 검증만 하고 실제로는 쓰지 않는다 | 프롬프트에 선택 구간 앞·뒤 텍스트가 모두 있음 | ✅ 해결: 원고 전체(앞부분 문맥용)와 함께 `선택 구간(start~end)` 블록을 프롬프트에 넣음. 문맥 범위 조정은 프롬프트 튜닝 때 |
| T8 | 높음 | 공통 | **`.env`를 읽지 않는다.** `python-dotenv`가 의존성에 있지만 `load_dotenv` 호출이 없다. README 안내대로 `cp .env.example .env`를 해도 `USE_FAKE_LLM`, 키, 모델 설정이 무시된다 | `src/`에 dotenv 사용처 없음 | ⚪ 하지 않음(명세 근거 없음): 라이브러리는 환경변수만 본다. README에 현재 동작(패키지는 `.env`를 읽지 않음, 셸에 불러오는 방법)을 적어 둠 |
| T9 | 중간 | REX·SSM | **입력 크기 상한이 없다.** REX는 30만 자 원고를 LLM 호출 한 번에 넣는다(프롬프트 300,036자). SSM은 제목 없는 30만 자 원고를 청크 하나로 보낸다. 반대로 300장 원고는 LLM을 300번 순차 호출한다. `max_tokens=4096`이라 큰 출력은 잘린다 | 호출 횟수·프롬프트 길이 관찰 | ⚪ 하지 않음(명세 근거 없음): 명세에 크기 기준이 없다. 큰 입력은 실패해도 `AI_*_FAILED`로 정상 반환된다 |
| T10 | 중간 | 공통 | **실제 호출 재시도가 과하다.** 인증 오류나 tool_use 없는 응답처럼 다시 해도 소용없는 경우도 3번 시도한다. anthropic SDK 자체 재시도(기본 `max_retries=2`)와 겹쳐 실제 HTTP 요청은 최대 9번(3×3), 타임아웃 30초면 최악 4분 넘게 기다린다. 모델 환경변수가 없어도 `model=None`으로 호출한다 | 가짜 클라이언트로 시도 횟수·인자 확인 | 🟡 일부 해결: SDK 자체 재시도 끔(`max_retries=0`), 408·409·429·5xx·연결 오류만 재시도, 그 밖의 4xx는 즉시 실패. `tests/test_llm_real_path.py` 추가. **남은 부분(모델·키 설정 누락 시 처리)은 하지 않음(명세 근거 없음)**: 지금도 죽지 않고 `AI_*_FAILED`로 반환된다 |
| T11 | 중간 | 공통 | **출력이 잘린 것을 스키마 불일치로 보고한다.** `stop_reason="max_tokens"`로 잘린 응답이 `SCHEMA_VALIDATION_FAILED`로 나가 원인을 구분할 수 없다 | 가짜 클라이언트로 확인 | ✅ 해결: `stop_reason=max_tokens`면 재시도 없이 `LLMFailedError`(→ 모듈별 `AI_*_FAILED`), 메시지에 잘림 명시 |
| T12 | 중간 | NLCD·REX | **근거 대조에 허점이 있다.** 공백만 있는 근거가 통과한다(정규화하면 빈 문자열이 되어 모든 원문에 포함됨). `value`가 빈 문자열인 항목도 통과한다. 한국어 원고에 흔한 「」『』, 말줄임표 `…`와 `...`는 정규화하지 않아 정상 근거가 지워질 수 있다 | `is_present("   ", ...)` → True, 「」/『』 → False | 🟡 일부 해결: 공백만 있는 근거 거부, 「」『』를 따옴표로 정규화. **남음 (오류 수정, 다른 개발자)**: 빈 `value` 항목 처리. 말줄임표 `…`/`...` 정규화는 하지 않음(명세 근거 없음) |
| T13 | 중간 | 공통 | **가짜 LLM 설정이 불안정하다.** 최상위에 `Literal` 필드가 있는 스키마는 가짜 응답이 스키마를 통과하지 못한다. 지금은 `Literal`이 리스트 안에만 있어 증상이 없지만 스키마를 바꾸면 테스트가 깨진다. 또 `USE_FAKE_LLM`은 `"1"`만 인식해서 `"true"`로 쓰면 실제 API 호출로 넘어간다 | `Literal` 스키마 가짜 응답 검증 실패 확인 | ✅ 해결: 가짜 응답이 `Literal`·`Enum`을 채움. `USE_FAKE_LLM`은 `1`만 인정한다고 README에 명시 |
| T14 | 중간 | SCDS | **룰 검출이 쉽게 빗나간다.** `character_ids`가 빈 배열이면 세계관 규칙 위반도 `no_candidate`가 된다. 키워드 사이 공백 한 칸 차이("잔혹하게  살해")로 검출되지 않는다. 후보의 `rule_id`에 WorldRule id(`wr_001`)를 넣는데, 명세 예시는 룰 종류(`RULE-01`)를 넣는다 | 각 입력으로 status 확인 | 미해결: A2(기획) 결정과 함께 정리. 공백 차이·빈 `character_ids` 처리는 오류 수정(다른 개발자). rule_id 의미는 B13으로 백엔드 확인 |
| T15 | 중간 | SCDS | **응답 모양이 경우마다 다르다.** 성공은 `{"conflicts": [...]}`(status 없음), 건너뜀은 `{"rule_result": ..., "status": ...}`다. 백엔드가 키가 있는지로 분기해야 한다 | 두 응답의 data 키 비교 | ✅ 해결: skipped·no_candidate·completed 모두 `data.status`와 `data.rule_result`를 가짐 |
| T16 | 중간 | 공통 | **프롬프트 인젝션 방어가 없다.** 시스템 프롬프트 없이 사용자 입력을 구분자 없이 지시문 뒤에 이어붙인다. 가드레일 테스트는 가짜 LLM이라 "죽지 않는지"만 확인했지, 인젝션이 막히는지는 확인하지 못했다 | 생성된 프롬프트·요청 인자 확인 | ⚪ 하지 않음(명세 근거 없음): 프롬프트 튜닝이라 CLAUDE.md 절대 규칙상 범위 밖 |
| T17 | 중간 | AIQ | **후속 질문의 이전 대화를 받을 수 없다.** AIQ 4.4는 스레드에 후속 질문을 이어가지만 `run_aiq`에는 이전 메시지를 넘길 인자가 없어 매번 첫 질문처럼 답한다 | 시그니처 확인 | 미해결 (기능 누락, 사용자 담당): AIQ 4.4·2.2 근거로 이전 메시지(`role`, `content`) 목록 인자 추가 |
| T18 | 중간 | 공통 | **내부용 코드는 HTTP 상태 표에 없다.** 백엔드가 `HTTP_STATUS[code]`로 변환하면 `SCHEMA_VALIDATION_FAILED`에서 KeyError가 난다 | `core/errors.py` 확인 | 미해결 (오류 수정, 다른 개발자): A4와 함께 처리. 방침상 명세 코드(`AI_*_FAILED`)로 바꿔 보내는 쪽이 맞다 |
| T19 | 낮음 | 공통 | `core/mapping.py`가 어디에서도 쓰이지 않는다 (T1의 원인) | grep | ✅ 해결: SCDS에서 사용(T1) |
| T20 | 낮음 | 공통 | 버전이 `pyproject.toml`과 `__init__.py` 두 곳에 따로 적혀 있어 어긋날 수 있다 | 파일 확인 | ✅ 해결: 버전은 `__init__.py`의 `__version__` 한 곳, `pyproject.toml`은 hatch가 여기서 읽음 |

---

## A. 팀 결정 항목

### 결정됨

| # | 항목 | 결정 | 다음 할 일 | 담당 |
| --- | --- | --- | --- | --- |
| A1 | NLCD가 캐릭터 이름도 추출하는가 | **추출한다** (2026-09-28) | NLCD API 명세에 `character_name` 필드 추가를 백엔드와 합의한 뒤, `nlcd/schema.py`에 필드 추가. 합의 전에는 구현하지 않음 | Dev A |
| A7 | SCDS `related_chapter_ref` | **만들지 않는다** (2026-09-29, 방침) | 없음. 채우려면 명세에 없는 입력이 필요하다 | — |
| A8 | AIQ 답변 근거 대조 | **적용하지 않는다** (2026-09-29, 방침) | 없음. 적용하려면 AIQ 명세 변경이 필요하다 | — |
| A11 | SSM 청크 하나가 실패할 때 | **전체 실패로 반환한다** (현재 동작, 2026-09-29, 방침) | 없음. 부분 성공은 명세에 없는 상태다 | — |

A1 근거: ASS 확정 시 `character_name`이 비어 있으면 400 `MISSING_REQUIRED_FIELD`(ASS 1.4, 4.9)인데, NLCD 출력(NLCD 2.1)에는 이름 필드가 없다. 현재 코드: `modules/nlcd/schema.py` TODO.

### 보류 (결정 필요)

| # | 항목 | 문제 (명세 근거) | 현재 코드 동작 | 선택지 | 담당 | 코드 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | SCDS RULE-01/03/04 판정 방식 | 예시(SCDS 4.6)는 가치관 "폭력 회피"와 문구 "잔혹하게 살해"를 연결하지만, 그 연결 사전이 명세에 없다. 원본 기능 명세서(SCDS v0.1)도 없음 | `WorldRule.violation_keywords` 매칭(RULE-02)만 동작. 캐릭터 가치관 충돌은 감지 못 함 | ① 가치관별 위반 키워드 사전(팀 제공) ② RULE-02만 유지 ③ 캐릭터에 values가 있으면 항상 AI 분석(기획서 11-2 "선택적 AI 호출" 원칙과 충돌) | Dev B | `modules/scds/rules.py` |
| A3 | SCDS severity 판정 기준 | SCDS 2.7은 `low/medium/high` 값만 있고 기준이 없다 | LLM이 고르도록 스키마만 있음 (기준 없음) | ① AI가 판단(프롬프트에 기준 명시) ② 룰별 고정값 | Dev B | `modules/scds/schema.py` |
| A4 | 내부용 에러 코드 노출 방식 | `AI_TIMEOUT`, `SCHEMA_VALIDATION_FAILED`는 명세에 없다 | LLM 응답이 스키마와 안 맞으면 `SCHEMA_VALIDATION_FAILED`가 그대로 나감. HTTP 상태 미정 | ① 모듈별 `AI_*_FAILED`(502)로 바꿔 보내고 원래 코드는 details에 남김 ② 그대로 노출하고 명세에 코드·HTTP 상태 추가. **방침상 ① 권장** | 공동 | `core/errors.py`, `core/runner.py` |
| A5 | NLCD `duplicate_of` 판정 주체 | NLCD 2.1/4.1. 이전 추출 이력은 백엔드 DB에만 있다 | 패키지는 관여하지 않음 | ① 백엔드 ② 패키지(이전 추출 목록을 입력으로 받아 유사도 판정, 시그니처 변경) | Dev A | — |
| A6 | REX `source_chapter`를 채우는 주체 | REX 2.1에 필드는 있지만 `run_rex`는 원고 텍스트만 받아 챕터 번호를 모른다 | 항상 `null` | ① 챕터 목록(MSU Chapter)을 입력으로 받아 패키지가 채움(시그니처 변경) ② 백엔드가 챕터별로 호출하고 번호를 붙임 | Dev A | `modules/rex/schema.py` |
| A9 | SSM 분량 부족 기준 | SSM 1.4/4.1에 `MANUSCRIPT_TOO_SHORT`(422)는 있지만 기준값이 없다 | 완전히 비어 있을 때만 반환 | ① 현재 유지 ② 최소 글자 수 ③ 최소 챕터 수 | Dev B | `modules/ssm/module.py` |
| A10 | SSM 챕터 경계 기준 | MSU 2.2에 `Chapter(chapter_no, title, content)`가 이미 있다 | "제N장/N장" 제목 패턴으로 자름. 패턴이 없으면 원고 전체가 청크 하나 | ① MSU 챕터 목록을 입력으로 받음(정확, 시그니처 변경) ② 제목 패턴 유지 | Dev B | `modules/ssm/chunking.py` |
| A12 | SSM 노드 `character_ids` | SSM 2.3은 ASS/SCDS 캐릭터 ID를 참조하라고만 한다. 입력에 캐릭터 목록이 없다 | 항상 빈 배열 | ① 확정 캐릭터(id, name) 목록을 입력으로 받아 AI가 ID 선택, 목록에 없는 ID는 제거 ② 빈 배열 유지(백엔드도 채울 정보가 없음) | Dev B | `modules/ssm/schema.py` |
| A13 | ASS AI 재추천을 이 저장소에서 만드는가 | ASS 4.8(선택 기능, 기본 비활성화, `AI_SUGGESTION_DISABLED`)은 AI 호출 기능인데 이 패키지의 모듈 5개(nlcd/rex/aiq/scds/ssm)에 없다 | 없음 | ① 이 저장소에서 만든다(새 모듈) ② 이 저장소 범위가 아니다 | 공동 | — |

보류 항목이 많은 영역: SSM(3개), SCDS(2개). A6·A10·A12는 모두 "MSU 챕터 목록이나 확정 캐릭터 목록을 입력으로 받을지"라는 같은 질문이므로, 백엔드와 입력 형식을 한 번에 정하면 함께 풀린다.

---

## B. 명세끼리 안 맞는 부분 (명세 원문 수정 필요)

| # | 위치 | 문제 |
| --- | --- | --- |
| B1 | NLCD 4.2, SCDS 4.7 실패 응답 예시 | `data`와 `error`를 한 응답에 같이 담고 있다. 공통 응답 형식(성공 `{data, meta}` / 실패 `{error}`)과 맞지 않는다 |
| B2 | SCDS 4.7 실패 예시 | 코드는 `AI_ANALYSIS_FAILED`인데 메시지는 "AI 응답 시간이 초과되었습니다"다. `AI_ANALYSIS_TIMEOUT`이 맞는지 확인 필요 |
| B3 | AIQ 4.6 재시도 | 409 `INVALID_STATUS_TRANSITION`을 쓰지만 AIQ 1.4 에러 코드 표에 없다 |
| B4 | NLCD 4.3 재시도 | `completed` 상태 재시도를 `EXTRACTION_NOT_READY`로 거부한다. 코드 이름("아직 준비 안 됨")과 상황("이미 완료됨")이 반대다 |
| B5 | REX 4.3 재시도 | 409 설명이 "`EXTRACTION_NOT_READY`는 해당 없음"이라고 되어 있어 어떤 코드를 쓰는지 알 수 없다 |
| B6 | NLCD 머리말 ↔ ASS 2.3, 4.1 | NLCD는 "ASS와 필드명이 이미 같다"고 하지만, 영향 관계 항목의 대상 필드가 NLCD는 `value`, ASS는 `target`이다. ASS 입력(4.1)은 evidence 없는 문자열 배열이라 근거가 전달되지 않는다 |
| B7 | ASS 2.4 ↔ SCDS 2.1 | 같은 캐릭터를 `personality_tags/core_values/influence_relations`와 `traits/values/influences`로 다르게 부른다. 이 저장소는 `core/mapping.py` 변환 레이어로 해결(2단계). `emotion_keywords`는 SCDS에 대응 필드가 없어 버려진다 |
| B8 | SCDS 2.1 `Character.status` | `alive/deceased/removed`(RULE-04 판정 기준)가 ASS `ConfirmedCharacter`(`status`는 `confirmed` 고정)와 DB 어디에도 없다 |
| B9 | REX 2.2 ↔ SCDS 2.2 `WorldRule` | REX는 `origin`, `extraction_id`, `evidence`, `updated_at`을 추가했지만 SCDS 정의에는 없다. REX 문서 스스로 통일이 필요하다고 적고 있다 |
| B10 | SCDS 2.6 `skipped_reason` | "`NO_REFERENCE_DATA` 등"으로만 적혀 있어 다른 사유가 있는지 알 수 없다 (`core/status.py` TODO) |
| B11 | REX·AIQ·SSM 머리말 | 세 문서 모두 원본 기능 명세서 없이 "합리적으로 가정"했다고 밝히고 있다. 상태값·오류 처리 전체가 가정이다 |
| B12 | SCDS.md 끝부분 | 파일이 596행 `##`에서 끊겨 있다. 뒤에 내용이 더 있었는지 확인 필요 |
| B13 | SCDS 2.6 ↔ 4.6 | `RuleResult.candidates[].rule_id`가 WorldRule의 id(`wr_001`)인지 룰 종류(`RULE-01`)인지 알 수 없다. 4.6 예시는 룰 종류를 넣지만 world_rules의 id는 `wr_001` 형식이다 (T14) |

---

## C. DB 설계와 API 명세 불일치 (백엔드 확인 필요)

| # | 대상 | API 명세 | DB 설계(db.md) | 영향 |
| --- | --- | --- | --- | --- |
| C1 | NLCD 결과 저장 | 항목마다 `evidence`, `emotion_keywords`, `influence_relations`, 추출 작업(NLExtraction) | `CharacterPersonalityTags`·`CharacterCoreValues`에 `value`만. 근거 컬럼, 감정 키워드·영향 관계 테이블, 작업 테이블 없음 | AI가 돌려준 근거·감정 키워드를 저장할 곳이 없다 |
| C2 | 작업(job) 테이블 | NLCD `NLExtraction`, REX `RuleExtraction`, SCDS `ConflictCheck`, SSM `StructureAnalysis`의 상태값 | 해당 테이블 없음 | 비동기 폴링 상태를 저장할 곳이 없다 |
| C3 | 세계관 규칙 | `description`, `violation_keywords`, `origin`, `evidence` | `WorldRules(content)`만 | 필드 이름이 다르고, SCDS 룰 검출에 필요한 `violation_keywords`가 없다 |
| C4 | AIQ | 스레드·메시지(`role`, `content`, `status`), `selection_range{start,end}` 오프셋 | `ManuscriptQuestions(question, target_text)` | 답변을 저장할 컬럼이 없다. 범위를 오프셋이 아니라 텍스트로 저장한다 |
| C5 | 충돌(Conflict) | `conflict_target`, `input_event`(문자열), `chapter`(정수), 상태 `pending/accepted/ignored/modified` | `description`, `input_event`(Events FK uuid로 변경), `chapter_id`(uuid), 샘플 상태 `open/resolved` | 필드·타입·상태값이 모두 다르다 |
| C6 | 스토리 구조 분석 | `acts[{act_name, chapter_from, chapter_to, summary}]`, `nodes`, `edges` | `result jsonb`. 샘플은 `structure_type`, `acts[{act, title, chapters, tension_level}]`, `turning_points`, `issues` | JSON 구조가 완전히 다르다. 이 패키지는 API 명세 구조로 출력한다 |
| C7 | 챕터 참조 | 챕터 번호(정수) | `chapter_id`(uuid) | 백엔드가 번호와 id를 변환해야 한다 |
| C8 | 상태값 샘플 | 복선 `resolved/unresolved`, ASS `pending_review/confirmed/discarded` | 복선 샘플 `planted`, 캐릭터 샘플 `draft/confirmed` | 상태값 목록이 다르다 |
