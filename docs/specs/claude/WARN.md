# WARN: 문제점·결정 항목 정리

명세를 근거로 구현하면서 확인된 문제점과, 팀이 결정해야 하지만 아직 결정되지 않은 항목을 모은 문서다.
(작성: 2026-09-28 / 2026-09-29 실제 API 호출 결과 반영 / 2026-09-29 전체 재검토 결과 반영, `WARN_2.md` 통합 / 2026-09-29 `fix/backend-alignment` 반영)

**방침 (2026-09-29)**

- 명세(API 명세, db.md)에 근거가 없는 작업은 하지 않는다. 그런 항목은 ⚪ "하지 않음(명세 근거 없음)"으로 표시했다.
- 기획.md에만 있고 API 명세에 없는 기능은 폐기된 아이디어로 보고 이 문서에서 다루지 않는다.
- 남은 작업의 담당·순서는 `CLAUDE.md` "후속 작업 계획"에 있다.

| 절 | 내용 | 현황 |
| --- | --- | --- |
| 0. 진행 현황 | 끝난 작업과 해결된 문제 | 완료 PR 18개 + 다른 개발자 수정 2건 병합 + `fix/backend-alignment`, 해결된 문제 32건 |
| 1. 한눈에 보기 | 남은 문제를 "안 고치면 무엇이 안 되는지" 기준으로 등급별 정리 | — |
| T. 발견한 문제 | 코드가 명세 의도대로 동작하지 않는 것 (해결된 것은 0절로 옮기고 지움) | 남은 10건: 🟡 일부 해결 4, ⚪ 하지 않음 3, 미해결 3 |
| A. 팀 결정 항목 | 이 저장소에서 정할 수 있지만 팀 결정이 필요한 것 | 13개: 결정 5, 보류 8 (A4는 해결되어 지움) |
| B. 명세끼리 안 맞는 부분 | 명세 원문 수정이 필요한 것 | 18건 |
| C. DB 설계와 API 명세 불일치 | db.md 기준 (백엔드 확인) | 8건 (실제 백엔드 스키마 기준 현황은 D절) |
| D. 실제 백엔드와 연동 확인 | `prolog-backend-master` 코드·마이그레이션을 직접 읽은 결과 | 남은 5건 (D2·D4·D5·D6·D10 해결) |
| E. 보완 권장 | 기능은 되지만 품질·비용·운영이 아쉬운 것 (명세 근거 없음) | 12건, 모두 ⚪ |
| F. 명세 ↔ 실제 백엔드 DB·코드 대조 | 2026-09-29 전 영역(명세 13종) 대조. 명세를 실제 DB에 맞춘 것과 남은 백엔드 작업 | 명세 수정 완료 + 남은 백엔드 작업 |

담당: NLCD·REX·AIQ = Dev A, SCDS·SSM = Dev B, 공통 = 공동

---

## 0. 진행 현황

### ✅ 완료 (main 병합됨)

| PR | 내용 | 관련 항목 |
| --- | --- | --- |
| #1 | 저장소 초기 설정(폴더 구조, CI, 템플릿) | — |
| #2 | 공통 에러 형식·에러 코드·상태값 | — |
| #3 | NLCD/ASS → SCDS 필드 매핑 레이어 (`core/mapping.py`) | B7 |
| #4 | 공통 실행 뼈대 (`core/llm.py`, `evidence.py`, `runner.py`) | — |
| #5 | 모듈 스키마와 공개 함수 `run_*` | — |
| #6 | 후속 작업 계획 (CLAUDE.md) | — |
| #7 | 공개 함수 입력 방어·크래시 방지 | — |
| #8 | 직접 테스트 발견 문제 수정, WARN.md·handoff·README 작성 | T1·T2·T3·T4·T7·T11·T13·T15·T19·T20 |
| #9 | WARN.md에 "안 고치면 작동 안 되는 것" 표시 | — |
| #10 | evals 케이스 형식과 `run_evals.py` | — |
| #11 | CLAUDE.md 9단계 완료 표시 | — |
| #12 | LLM을 Claude에서 OpenRouter 경유 DeepSeek(`deepseek/deepseek-v4-flash`)으로 교체 | — |
| #13 | AIQ AI 호출 시간 제한 30초 → 90초 | 실제 호출 결과 |
| #14 | 남은 작업 정리, 실제 호출 결과 반영 | T21 |
| #15 | AIQ 후속 질문 지원 (`run_aiq(..., messages=)`) | T17 |
| #16 | SCDS 룰 검출/AI 분석 공개 함수 분리 (`run_scds_rules`, `run_scds_analysis`) | T2 |
| #17 | SCDS AI 분석 시간 제한 30초 → 90초 | 실제 호출 결과 |

그 밖에 main에 PR 없이 들어간 커밋: README 브랜치 규칙·커밋 컨벤션 추가(`e7aac8a`, `e5a3231`).

| PR | 내용 | 관련 항목 |
| --- | --- | --- |
| #18 | 전체 재검토 결과 반영, `WARN_2.md` 통합 | — |
| `fix/merge-pending-fixes` 브랜치 | 다른 개발자의 수정 2건 병합: `fix/core-schema-error-code`(스키마 불일치를 모듈별 `AI_*_FAILED`로 반환, 원래 코드는 `details.internal_code`), `fix/scds-conflict-target-filter`(AI가 충돌 대상 문자열 대신 후보 번호 `candidate_index`를 고르고 패키지가 후보에서 필드를 채움). 병합 후 테스트 290개 통과 | T18·A4, T3 |

| `fix/backend-alignment` 브랜치 | 남은 오류 수정과 실제 백엔드(`prolog-backend-master`) 스키마에 맞춘 수정. 퍼징(공개 함수 7개 × 이상한 입력·AI 응답 수천 건)에서 찾은 `error.details` JSON 직렬화 실패(bytes·임의 객체·NaN·순환 참조 입력)도 수정. 테스트 309개 통과(Python 3.11, 3.12 wheel 설치) | T22·T24~T30·T32~T37, D2·D4·D5·D6·D10, A12, T12·T14·T31 일부 |

| `docs/spec-align-db` 브랜치 | 명세를 실제 백엔드 DB 값에 맞춤(F절), REX `title` 추가, SSM 노드 제목 200자, SCDS 후보 없음을 `skipped`로 | F절 |

`docs/add-project-docs` 브랜치(`WARN_2.md` 추가)는 내용을 이 문서에 합쳤으므로 병합하지 않는다. 두 fix 브랜치에 들어 있던 `WARN_2.md`도 병합할 때 뺐다.

### 해결되어 문제 목록에서 지운 것

| # | 문제 | 해결 |
| --- | --- | --- |
| T1 | SCDS AI 분석에 캐릭터 설정이 전달되지 않음 | PR #8 |
| T2 | SCDS AI 실패 시 룰 후보 소실, 룰 검출/AI 분석을 나눠 쓸 수 없음 | PR #8, #16 |
| T3 | SCDS 지어낸 충돌 통과 → 문자열 일치 필터가 정상 조언을 버림 | PR #8, `fix/scds-conflict-target-filter` |
| T4 | SSM 첫 챕터 제목 앞 글(프롤로그) 소실 | PR #8 |
| T7 | AIQ 선택 구간을 쓰지 않고 원고 전체만 보냄 | PR #8 |
| T10 | 실제 호출 재시도 과다(최대 9번) | PR #8, #12 (키 누락 처리는 하지 않기로 함, 키 누락 시 다른 키 전송은 T24) |
| T11 | 출력 잘림을 스키마 불일치로 보고 | PR #8 |
| T13 | 가짜 LLM이 `Literal`·`Enum` 스키마를 못 채움 | PR #8 |
| T15 | SCDS 응답 모양이 경우마다 다름 | PR #8 |
| T17 | AIQ 후속 질문의 이전 대화를 받을 수 없음 | PR #15 |
| T18 | 명세에 없는 `SCHEMA_VALIDATION_FAILED`가 밖으로 나가 `HTTP_STATUS[code]`에서 `KeyError` | `fix/core-schema-error-code` |
| T19 | `core/mapping.py` 미사용 | PR #8 |
| T20 | 버전이 두 곳에 따로 적힘 | PR #8 |
| A4 | 내부용 에러 코드 노출 방식 → ① 모듈별 `AI_*_FAILED`로 결정·구현 | `fix/core-schema-error-code` |
| T22 | REX `violation_keywords`가 비어도 통과 → AI 응답 필수 필드로 두고 필드 설명 추가, 빈·중복 키워드 제거 | `fix/backend-alignment` |
| T24 | `OPENROUTER_API_KEY`가 비면 `OPENAI_API_KEY`가 전송됨 → SDK를 만들기 전에 `AI_*_FAILED` | `fix/backend-alignment` |
| T25 | `.env.example`의 `USE_FAKE_LLM=1` → 값 비우고 주석 | `fix/backend-alignment` |
| T26 | 도구 호출 미지원 제공사 라우팅 → `provider.require_parameters=true` | `fix/backend-alignment` |
| T27 | 공백 키워드가 모든 사건을 후보로 만듦 → 무시 | `fix/backend-alignment` |
| T28 | 후보·충돌 중복 → (캐릭터, 규칙) 단위 후보, 같은 후보 번호 충돌은 하나만(`removed_conflict_count`에 포함) | `fix/backend-alignment` |
| T29 | `run_scds_analysis`가 사건↔`rule_result` 짝을 확인하지 않음 → 후보 캐릭터가 사건에 없으면 `INVALID_INPUT` | `fix/backend-alignment` |
| T30 | REX `source_chapter`를 LLM이 지어냄 → 항상 `null`로 덮어씀(A6 결정 전까지) | `fix/backend-alignment` |
| T32 | NLCD 중복 값이 백엔드 유니크 인덱스에 걸림 → 카테고리 안에서 `lower(strip(value))` 기준으로 합침 | `fix/backend-alignment` |
| T33 | 408이 `FAILED`로 분류 → `TIMEOUT` | `fix/backend-alignment` |
| T34 | AIQ 빈 원고 통과, 정수 아닌 오프셋을 `INVALID_SELECTION_RANGE`로 보냄 → 둘 다 `INVALID_INPUT`, README에 현재 질문 안내 | `fix/backend-alignment` |
| T35 | REX·SSM 시간 제한 30초 → 90초 | `fix/backend-alignment` |
| T36 | `candidate_index`가 `true`·`"0"`을 받음 → `StrictInt` | `fix/backend-alignment` |
| T37 | 무시한 충돌 억제 입력 없음 → 백엔드에 `insight.conflict_suppressions`(`suppression_key`)가 있어 백엔드가 거른다. 패키지는 받지 않음(README 안내) | `fix/backend-alignment` |
| A12 / D5 | SSM `character_ids`에 이름이 들어감 → ① 확정 캐릭터 목록 `run_ssm(..., characters=)`을 받아 그 id만 남김, 없으면 빈 배열(백엔드 uuid 외래키 기준) | `fix/backend-alignment` |

---

## 1. 한눈에 보기 (남은 문제)

패키지 자체는 어떤 입력에도 예외를 던지지 않고 정해진 형식으로 응답한다. 여기서 "불능"은 크래시가 아니라 **응답은 오지만 기능으로 쓸 수 없는 결과**를 뜻한다.

| 등급 | 뜻 |
| --- | --- |
| 🔴 **불능** | 정상적인 사용 흐름에서 그 기능을 서비스로 제공할 수 없다 |
| 🟠 **조건부 불능** | 흔한 조건(긴 원고, 특정 설정·연동 방식)에서 실패하거나, 보안·운영 사고가 난다 |
| 🟡 **품질 저하** | 기능은 돌아가지만 결과가 틀리거나 중복된다 |
| ⚪ **하지 않음** | 명세 근거가 없어 방침상 하지 않는다 |

| 등급 | 항목 | 안 고치면 벌어지는 일 | 누가 |
| --- | --- | --- | --- |
| 🔴 | **A14 / D1** LLM 호출·룰 엔진 담당 주체 | 백엔드 ROADMAP은 프롬프트·LLM 호출·룰 엔진을 백엔드가 맡는다고 적었고, 이 패키지는 셋 다 안에 갖고 있다. 한쪽 설계를 버려야 연동이 시작된다 | 팀 |
| 🔴 | **D3** 실제 백엔드 스키마 불일치 | SCDS `conflict_target`·`chapter`를 저장할 곳이 없다(D2·D4·D5는 해결) | 백엔드 |
| 🔴 | **T14 / A2** SCDS 가치관 기반 판정 없음 | 캐릭터 가치관만 있고 세계관 규칙이 없는 프로젝트는 항상 `no_candidate`다 | 기획 |
| 🔴 | **T6 / T23 / A10** SSM 구조 지도 | 챕터마다 따로 분석해 acts가 중복되고, 노드 chapter가 모두 1이며, 챕터를 넘는 연결을 만들 수 없다 | 백엔드와 입력 형식 합의 |
| 🔴 | **T21** 프롬프트·스키마 설명 부재 | 실제 호출에서 REX가 규칙 0개. 다른 모듈도 명세 예시와 다른 표현을 낸다 | 팀(담당 결정) |
| 🟠 | **T9** 긴 원고 | REX·AIQ는 원고 전체를 한 번에 보내고, SSM은 챕터 수만큼 순차 호출한다(시간 제한은 T35에서 90초로 늘림) | A6 |
| 🟠 | **D7~D8** 연동 준비 | 백엔드에 의존성·키·AI 워커가 없고, 동기 함수를 `async def`에서 부르면 서버 전체가 멈춘다 | 백엔드 |
| 🟠 | **B14** AIQ 선택 구간 오프셋 기준 | 오프셋이 챕터 기준인지 원고 전체 기준인지 명세에 없어, 틀리면 `INVALID_SELECTION_RANGE`나 엉뚱한 구간에 답한다 | 기획·백엔드 |
| 🟡 | T5, T6(남은 부분), T14(남은 부분), T31(남은 부분) | 챕터 오인, 빈 `character_ids` 사건, SSM 중복 node_id | 결정 |
| ⚪ | T8, T9(크기 상한), T16, E1~E12 | 명세 근거 없음 | — |

---

## T. 발견한 문제

### 검토 이력

| 날짜 | 대상 | 방법 |
| --- | --- | --- |
| 2026-09-28 | main(PR #7 시점) | `pytest` 194개·ruff 통과 확인, 공개 함수를 실제 사용 흐름대로 호출하고 LLM 응답 자리에 원하는 값을 심어 관찰, 가짜 클라이언트로 실제 호출 경로 확인, wheel 설치 확인 |
| 2026-09-29 | main(PR #12~#17) | 실제 API 호출 (아래 "실제 호출 결과") |
| 2026-09-29 | main(PR #17) + 다른 개발자 수정 브랜치 2개 | 코드·API 명세 13종·db.md 전체 대조, 실제 백엔드 저장소(`prolog-backend-master`) 대조, 의심 지점을 가짜 LLM으로 재현. `WARN_2.md`(다른 개발자 검토) 통합. 병합 대기 브랜치를 main에 합쳐 테스트 290개 통과 확인 |

이상 없음으로 확인된 것:

- 공개 함수 7개(`run_nlcd`, `run_rex`, `run_aiq`, `run_scds`, `run_scds_rules`, `run_scds_analysis`, `run_ssm`) 모두 어떤 입력·AI 오류에도 예외 없이 정해진 형식으로 응답한다.
- 인자 누락·타입 오류는 `INVALID_INPUT`, 시간 초과는 `AI_*_TIMEOUT`, 그 밖의 AI 실패는 `AI_*_FAILED`로 분류된다.
- 실제 API에서 다섯 모듈 모두 정해진 스키마로 응답을 받았다.

심각도: **높음** = 명세의 핵심 기능이 동작하지 않거나 데이터·보안 사고 / **중간** = 운영 중 오류·비용·오판 위험 / **낮음** = 정리 필요

### 발견한 문제

| # | 심각도 | 모듈 | 문제 | 확인 방법·결과 | 대응 |
| --- | --- | --- | --- | --- | --- |
| T5 | 높음 | SSM | **챕터 인식이 흔한 형식에서 틀린다.** MSU 예시 형식 "1화"는 인식하지 못해 원고 전체가 청크 하나가 된다. 반대로 본문 줄 첫머리의 "3장의 편지를 썼다", "10장면 전환"도 챕터 경계로 오인한다 | "1화/2화" → 청크 1개, "3장의…"·"10장면…" → 경계로 잘림 (재현) | 미해결: A10 결정(MSU 챕터 목록을 입력으로 받기)이 근본 해결 |
| T6 | 높음 | SSM | **청크를 합친 구조 지도가 명세 구조와 다르다.** 청크마다 LLM을 따로 불러 이어붙이므로, 챕터마다 "발단"부터 새로 생겨 acts가 챕터 수만큼 쌓이고(3장 원고 → 발단 3개), 노드 `chapter`는 LLM이 몇 번째 챕터인지 몰라 모두 1이다. 명세 4.4 예시의 acts는 원고 전체 기준(발단 1~8장, 전개 9~30장)이다 | 다챕터 원고 병합 결과 확인 | 🟡 일부 해결(PR #8): node_id를 전체에서 새로 매기고 edges도 바꿈, 없는 노드를 가리키는 edge는 제거. **남음**: chapter 번호·acts를 전체 원고 기준으로 맞추기(A10과 함께). 챕터 간 연결은 T23 |
| T8 | 높음 | 공통 | **`.env`를 읽지 않는다.** `python-dotenv`가 의존성에 있지만 쓰지 않는다 | `src/`에 dotenv 사용처 없음 | ⚪ 하지 않음(명세 근거 없음): 라이브러리는 환경변수만 본다. README에 셸에서 불러오는 방법을 적어 둠. 쓰지 않는 의존성은 E10 |
| T9 | 중간 | REX·AIQ·SSM | **입력 크기 상한이 없다.** REX는 원고 전체를 한 번에 넣는다(30만 자 → 프롬프트 300,036자). AIQ는 질문마다 원고 전체를 넣고, `selection`이면 선택 구간을 한 번 더 붙인다(10만 자 원고에 10자 선택 → 100,069자). SSM은 제목 패턴이 없으면 원고 전체가 청크 하나다. 출력은 `max_tokens=4096`이라 큰 출력은 잘려 재시도 없이 실패한다 | 호출 횟수·프롬프트 길이 관찰 | ⚪ 하지 않음(명세 근거 없음): 명세에 크기 기준이 없다. 실패해도 `AI_*_FAILED`로 정상 반환된다. REX 챕터 단위 호출은 A6, 시간 제한은 T35 |
| T12 | 중간 | NLCD·REX | **근거 대조에 허점이 있다.** 공백만 있는 근거가 통과했다. `value`가 빈 문자열인 항목도 통과한다. 「」『』, 말줄임표 `…`/`...`는 정규화하지 않아 정상 근거가 지워질 수 있다. "마법"처럼 아주 짧은 근거도 원문에 있으면 통과한다 | `is_present("   ", ...)` → True였음 | 🟡 일부 해결(PR #8, `fix/backend-alignment`): 공백만 있는 근거 거부, 「」『』 정규화, 빈 `value`(NLCD)·빈 `description`(REX) 항목 제거. 말줄임표 정규화·최소 근거 길이는 하지 않음(명세 근거 없음) |
| T14 | 중간 | SCDS | **룰 검출이 쉽게 빗나간다.** `character_ids`가 빈 배열이면 세계관 규칙 위반도 `no_candidate`가 된다. 키워드 사이 공백 한 칸 차이("잔혹하게  살해")로 검출되지 않는다. 후보의 `rule_id`에 WorldRule id(`wr_001`)를 넣는데 명세 예시는 룰 종류(`RULE-01`)를 넣는다. 가치관 기반 판정(RULE-01/03/04)은 없다 | 각 입력으로 status 확인 (재현) | 🟡 일부 해결(`fix/backend-alignment`): 공백 차이 무시, 공백 키워드 무시, (캐릭터, 규칙) 단위로 후보 합침. rule_id는 백엔드 `conflicts.rule_id`(world_rules 외래키)에 맞춰 WorldRule id 유지(B13). **남음**: 가치관 판정 기준은 A2(기획). 빈 `character_ids` 사건은 후보를 만들 캐릭터가 없어 그대로 `no_candidate`(백엔드 `conflicts.character_id`는 null 허용이지만 SCDS 2.6 후보는 `character_id` 필수라 명세 확인 필요) |
| T16 | 중간 | 공통 | **프롬프트 인젝션 방어가 없다.** 시스템 프롬프트 없이 사용자 입력을 구분자 없이 지시문 뒤에 이어붙인다 | 생성된 프롬프트 확인 | ⚪ 하지 않음(명세 근거 없음): 프롬프트 튜닝이라 범위 밖. 프롬프트 작성(T21) 때 원고를 태그로 감싸면 함께 해결된다 |
| T21 | 높음 | 공통 | **프롬프트와 스키마 설명이 자리표시 수준이다.** 다섯 모듈 `prompt.py`가 한두 줄짜리 지시문이고, LLM에 넘기는 도구 스키마(`model_json_schema()`)에도 필드 설명(`description`)이 하나도 없다. 모델은 무엇을 어떤 기준으로 뽑아야 하는지 모른다. SCDS 프롬프트는 사건·캐릭터 설정을 파이썬 dict 문자열(`{'key': ...}`)로 넣는다 | 실제 호출: REX 규칙 0개, NLCD 값 표현이 명세 예시와 다름, SCDS 조언에 원고에 없는 원작 지식("큰 힘에는 큰 책임")이 섞임 | 미해결: 절대 규칙상 프롬프트 튜닝은 범위 밖이라 담당·범위를 팀이 먼저 정한다. 스키마에 `Field(description=...)`로 명세 필드 정의를 옮기는 것만으로도 효과가 크다 |
| T23 | 높음 | SSM | **챕터를 넘는 연결(edges)을 만들 수 없다.** 청크마다 독립 호출이라 LLM은 다른 챕터의 노드를 모른다. 만들더라도 병합할 때 없는 노드로 보고 버린다. 결과적으로 edges는 한 챕터 안의 인과관계만 남고, 복선 → 회수 같은 장편의 핵심 연결이 빠진다 | 코드 흐름 확인 (`ssm/module.py`) | 미해결: A10(챕터 목록 입력)과 함께 "챕터별 요약 → 전체 기준 한 번 더 판단"하는 두 단계 구조가 필요하다 |
| T31 | 낮음 | SSM | **노드·연결 병합에 빈틈이 있다.** 한 청크에서 LLM이 같은 `node_id`를 두 번 내면 두 번째 노드는 새 id를 받지만 edge는 항상 첫 노드로 연결된다(`setdefault`) | 코드 확인 | 🟡 일부 해결(`fix/backend-alignment`): 자기 참조·중복 edge 제거(`removed_edge_count`에 포함), 실패 청크 위치 `details.chunk_index`·`chunk_count`. **남음**: 중복 `node_id` 처리(두 번째 노드를 버릴지 합칠지 명세에 없음) |

### 실제 호출 결과 (2026-09-29)

PR #12 병합 뒤 `deepseek/deepseek-v4-flash`(OpenRouter 경유)로 실제 호출했다(총 8번). 모두 성공 응답이었고 스키마 검증·근거 대조를 통과했다. **연결과 응답 형식은 정상이고, 품질이 문제다.**

| 케이스 | 시간 | 결과 | 판단 |
| --- | --- | --- | --- |
| NLCD 피터 파커 | 4.6초 | 책임감이 강함·자신감 부족 / 비폭력 / 벤 삼촌(영향을 준 사람) / 혐오 | 내용은 대체로 맞음. 명세 예시("책임감 강함", "폭력 회피", "불안")와 표현이 다름 (T21) |
| NLCD 솔직함 | 13.3초 | 성격 솔직함·정직함, 가치 솔직함 | 명세 기대값 "정직"과 다름 (T21) |
| REX 계약 마법 | 1.9초 | 규칙 0개 | 명세 예시 "마법은 계약 없이 발현될 수 없다"를 못 뽑음 (T21, T22) |
| SCDS (evals 케이스) | 0초 | `no_candidate` | 룰 검출에서 끝나 AI 호출 없음. 정상 |
| SCDS 분리 흐름 | 규칙 0.00초 / 분석 32.0초 | `run_scds_rules` → `queued`, `run_scds_analysis` → `completed`, 충돌 1건(high) | 흐름 정상. 조언에 원고에 없는 원작 지식이 섞임 (T21). 시간 초과 위험 → ✅ PR #17에서 90초로 늘림 |
| SSM | 5.8초 | 막 1개, 노드 1개 | `character_ids`에 캐릭터 ID 대신 이름("피터 파커")이 들어감 (A12) |
| AIQ | 29.7초 | 원고 근거로 답변 | 시간 초과 위험 → ✅ PR #13에서 90초로 늘림 |
| AIQ 후속 질문 | 5.5초 / 3.8초 | 두 번째 질문의 "그 인물"을 첫 답의 "벤 삼촌"으로 이어받음 | PR #15 동작 확인 |

`evals --real`의 채점은 글자 완전 일치라 위 결과는 표현 차이만으로 실패로 나온다. 결과는 사람이 보고 판단한다(E9).

---

## A. 팀 결정 항목

### 결정됨

| # | 항목 | 결정 | 다음 할 일 | 담당 |
| --- | --- | --- | --- | --- |
| A1 | NLCD가 캐릭터 이름도 추출하는가 | **추출한다** (2026-09-28) | NLCD API 명세에 `character_name` 필드 추가를 백엔드와 합의한 뒤 `nlcd/schema.py`에 필드 추가. 합의 전에는 구현하지 않음. 이름이 없어도 ASS 초안 수정(4.4 PATCH)으로 사용자가 넣을 수 있어 불능은 아니다 | Dev A |
| A7 | SCDS `related_chapter_ref` | **만들지 않는다** (방침) | 없음. 채우려면 명세에 없는 입력이 필요하다 | — |
| A8 | AIQ 답변 근거 대조 | **적용하지 않는다** (방침) | 없음. 적용하려면 AIQ 명세 변경이 필요하다 | — |
| A12 | SSM 노드 `character_ids` | **① 확정 캐릭터 목록을 입력으로 받는다** (2026-09-29, 백엔드 `structure_node_characters.character_id` uuid 외래키 기준) | 백엔드가 `run_ssm(text, characters=확정 캐릭터 목록)`으로 호출 | Dev B |
| A11 | SSM 청크 하나가 실패할 때 | **전체 실패로 반환한다** (현재 동작, 방침) | 없음. 부분 성공은 명세에 없는 상태다 | — |

### 보류 (결정 필요)

| # | 항목 | 문제 (명세 근거) | 현재 코드 동작 | 선택지 | 담당 | 코드 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | SCDS RULE-01/03/04 판정 방식 | 예시(SCDS 4.6)는 가치관 "폭력 회피"와 문구 "잔혹하게 살해"를 연결하지만 그 연결 기준이 명세에 없다. RULE-03은 이름조차 없고, RULE-04 기준인 `Character.status`(B8)와 관계 데이터(SCDS 2.3·4.5)는 입력으로 받지 않는다 | `WorldRule.violation_keywords` 매칭(RULE-02)만 동작 | ① 가치관별 위반 키워드 사전(팀 제공, 코드와 분리된 데이터 파일) ② RULE-02만 유지 ③ 캐릭터에 values가 있으면 항상 AI 분석(기획서 "선택적 AI 호출" 원칙과 충돌) | Dev B | `modules/scds/rules.py` |
| A3 | SCDS severity 판정 기준 | SCDS 2.7은 `low/medium/high` 값만 있다 | LLM이 고름(기준 없음) | ① AI가 판단(프롬프트에 기준 명시) ② 룰별 고정값 | Dev B | `modules/scds/schema.py` |
| A5 | NLCD `duplicate_of` 판정 주체 | NLCD 2.1/4.1. 이전 추출 이력은 백엔드 DB에만 있다 | 패키지는 관여하지 않음 | ① 백엔드 ② 패키지(이전 추출 목록을 입력으로 받음) | Dev A | — |
| A6 | REX `source_chapter`를 채우는 주체 | REX 2.1에 필드는 있지만 `run_rex`는 원고 텍스트만 받아 챕터 번호를 모른다 | 채우지 않음. 단, LLM이 지어낸 값이 통과할 수 있음(T30) | ① 챕터 목록(MSU Chapter)을 입력으로 받아 챕터별로 추출(긴 원고 T9도 함께 해결) ② 백엔드가 챕터별로 호출하고 번호를 붙임(같은 규칙이 챕터마다 중복될 수 있음) | Dev A | `modules/rex/schema.py` |
| A9 | SSM 분량 부족 기준 | SSM 1.4/4.1에 `MANUSCRIPT_TOO_SHORT`(422)는 있지만 기준값이 없다 | 완전히 비어 있을 때만 반환 | ① 현재 유지 ② 최소 글자 수 ③ 최소 챕터 수 | Dev B | `modules/ssm/module.py` |
| A10 | SSM 챕터 경계 기준 | MSU 2.2에 `Chapter(chapter_no, title, content)`가 이미 있다 | "제N장/N장" 줄로 자름. 오인·미인식 있음(T5) | ① MSU 챕터 목록을 입력으로 받음(정확, 시그니처 변경) ② 제목 패턴 유지 | Dev B | `modules/ssm/chunking.py` |
| A13 | ASS AI 재추천을 이 저장소에서 만드는가 | ASS 4.8(선택 기능, 기본 비활성화, `AI_SUGGESTION_DISABLED`)은 AI 호출 기능인데 이 패키지에 없다 | 없음 | ① 이 저장소에서 만든다(새 모듈) ② 이 저장소 범위가 아니다 | 공동 | — |
| A14 | **LLM 호출·프롬프트·룰 엔진을 누가 맡는가** | 백엔드 ROADMAP은 모듈마다 `build_input`·`prompt_template`·`parse_result`·`confirm`만 두고 LLM 호출은 백엔드 잡 인프라가 한다고 적었다. SCDS 룰 엔진도 백엔드에서 인메모리+Redis로 100ms 안에 돌린다고 적었다(D1). 이 패키지는 프롬프트·LLM 호출·룰 검출을 모두 `run_*` 안에 갖고 있다 | 패키지가 모두 수행 | ① 패키지가 수행(현재), 백엔드 ROADMAP 수정 ② 백엔드가 호출, 패키지는 프롬프트·스키마·파싱만 제공(대규모 변경) ③ 룰 엔진은 백엔드, AI 분석은 패키지 | 공동 + 백엔드 | 전체 |

A6·A10(과 해결된 A12)은 모두 "MSU 챕터 목록이나 확정 캐릭터 목록을 입력으로 받을지"라는 같은 질문이라, 백엔드와 입력 형식을 한 번에 정하면 함께 풀린다(T5·T6·T23·T30도 함께). A14는 다른 모든 연동 작업보다 먼저 정해야 한다.

---

## B. 명세끼리 안 맞는 부분 (명세 원문 수정 필요)

| # | 위치 | 문제 |
| --- | --- | --- |
| B1 | NLCD 4.2, SCDS 4.7 실패 응답 예시 | `data`와 `error`를 한 응답에 같이 담는다. 공통 응답 형식(성공 `{data, meta}` / 실패 `{error}`)과 맞지 않는다 |
| B2 | SCDS 4.7 실패 예시 | 코드는 `AI_ANALYSIS_FAILED`인데 메시지는 "AI 응답 시간이 초과되었습니다"다 |
| B3 | AIQ 4.6 재시도 | 409 `INVALID_STATUS_TRANSITION`을 쓰지만 AIQ 1.4 에러 코드 표에 없다 |
| B4 | NLCD 4.3 재시도 | `completed` 상태 재시도를 `EXTRACTION_NOT_READY`로 거부한다. 코드 이름과 상황이 반대다 |
| B5 | REX 4.3 재시도 | 409 설명이 "`EXTRACTION_NOT_READY`는 해당 없음"이라 어떤 코드를 쓰는지 알 수 없다 |
| B6 | NLCD 머리말 ↔ ASS 2.3, 4.1 | NLCD는 "ASS와 필드명이 이미 같다"고 하지만 영향 관계 대상 필드가 NLCD는 `value`, ASS는 `target`이다. ASS 입력(4.1)은 evidence 없는 문자열 배열이라 근거가 전달되지 않는다. NLCD 결과를 ASS 입력으로 바꾸는 코드는 이 패키지에 없다(백엔드가 변환) |
| B7 | ASS 2.4 ↔ SCDS 2.1 | 같은 캐릭터를 `personality_tags/core_values/influence_relations`와 `traits/values/influences`로 부른다. `core/mapping.py`로 해결(PR #3). `emotion_keywords`와 영향 관계의 `type`·`status`는 SCDS에 대응 필드가 없어 버려진다 |
| B8 | SCDS 2.1 `Character.status` | `alive/deceased/removed`(RULE-04 판정 기준)가 ASS `ConfirmedCharacter`와 DB 어디에도 없다 |
| B9 | REX 2.2 ↔ SCDS 2.2 `WorldRule` | REX는 `origin`, `extraction_id`, `evidence`, `updated_at`을 추가했지만 SCDS 정의에는 없다 |
| B10 | SCDS 2.6 `skipped_reason` | "`NO_REFERENCE_DATA` 등"으로만 적혀 있다 (`core/status.py` TODO) |
| B11 | REX·AIQ·SSM 머리말 | 원본 기능 명세서 없이 "합리적으로 가정"했다고 밝힌다. 상태값·오류 처리 전체가 가정이다. SSM `Edge.relation`은 "인과관계"(2.2)와 `"causes"`(4.4 예시)뿐이고 값 목록이 없다 |
| B12 | SCDS.md 끝부분 | 파일이 596행 `##`에서 끊겨 있다 |
| B13 | SCDS 2.6 ↔ 4.6 | `candidates[].rule_id`가 WorldRule id(`wr_001`)인지 룰 종류(`RULE-01`)인지 알 수 없다. 실제 백엔드 `conflicts.rule_id`는 `world_rules` uuid 외래키라 패키지는 WorldRule id를 넣는다(백엔드 기준) |
| B14 | AIQ 2.1 `selection_range` ↔ MSU 2.1·2.2 | "문자 오프셋"이 원고 전체(`Manuscript.content`) 기준인지 챕터(`Chapter.content`) 기준인지, 단위(코드포인트 등)가 무엇인지 없다. 원고를 자동저장(MSU 4.4)으로 고친 뒤 후속 질문·재시도하면 저장된 오프셋이 다른 문단을 가리킨다 |
| B15 | SSM 4.3 재분석 ↔ 4.6 PATCH | 사용자가 고친 노드를 재분석 때 어떻게 할지(보존·병합) 규칙이 없다. 패키지는 매번 `node_1`부터 새로 만든다. 백엔드 ROADMAP §12-2도 같은 문제를 미결로 적었다 |
| B16 | NLCD ↔ ASS 4.1 | ASS는 `source_session_id`("nlsession_882"), NLCD는 `extraction_id`를 쓴다. NLCD 4.5는 "병합 대상 캐릭터 정보를 함께 실어" 보낸다고 하지만 ASS 4.1 요청에는 그 필드가 없다 |
| B17 | 개요.md 1항 | AI 모듈로 NLCD·SCDS만 적었다. REX·AIQ·SSM이 빠졌다 |
| B18 | 기획.md 11-1 기술 스택 | AI가 "Claude API · GPT API"로 적혀 있다. 실제는 OpenRouter 경유 DeepSeek이다(PR #12) |

---

## C. DB 설계(db.md)와 API 명세 불일치

db.md 기준이다. 실제 백엔드 마이그레이션(`prolog-backend-master`)은 db.md와 다르며, 그 기준 현황은 마지막 칸과 D절에 있다.

| # | 대상 | API 명세 | DB 설계(db.md) | 영향 | 실제 백엔드 스키마 |
| --- | --- | --- | --- | --- | --- |
| C1 | NLCD 결과 저장 | 항목마다 `evidence`, `emotion_keywords`, `influence_relations`, 추출 작업 | `CharacterPersonalityTags`·`CharacterCoreValues`에 `value`만 | 근거·감정 키워드를 저장할 곳이 없다 | 해소: 마이그레이션 0002에서 카테고리 4종·`evidence` 추가. 영향 관계 `type`은 저장 칸 없음 |
| C2 | 작업(job) 테이블 | NLCD·REX·SCDS·SSM 작업 상태값 | 없음 | 폴링 상태를 저장할 곳이 없다 | 해소: `ops.jobs`(result/error jsonb) 있음. 상태값 제약은 D6 |
| C3 | 세계관 규칙 | `description`, `violation_keywords`, `origin`, `evidence` | `WorldRules(content)`만 | SCDS 룰 검출 입력을 만들 수 없다 | 해소: `world_rules`에 `violation_keywords`, `evidence`, `origin`, `source_chapter_no` 있음 |
| C4 | AIQ | 스레드·메시지(`role`, `content`, `status`), 오프셋 | `ManuscriptQuestions(question, target_text)` | 답변 저장 컬럼이 없고 범위를 텍스트로 저장한다 | `qa_threads` 있음. `scope`는 패키지가 백엔드 값으로 맞춤 |
| C5 | 충돌(Conflict) | `conflict_target`, `input_event`, `chapter`, 상태 `pending/accepted/ignored/modified` | `description`, Events FK, `chapter_id`, 샘플 상태 `open/resolved` | 필드·타입·상태값이 모두 다르다 | **여전히 막힘** (D3) |
| C6 | 스토리 구조 분석 | `acts[{act_name, chapter_from, chapter_to, summary}]`, `nodes`, `edges` | `result jsonb`, 샘플 구조가 완전히 다름 | 이 패키지는 API 명세 구조로 출력한다 | `structure_maps`·`structure_nodes`·`structure_node_characters`로 저장 가능 |
| C7 | 챕터 참조 | 챕터 번호(정수) | `chapter_id`(uuid), `Chapters`에 본문·순번 없음 | 백엔드가 번호와 id를 변환해야 하고, DB만으로는 챕터 본문을 모을 수 없다(AIQ·SSM 입력) | 확인 필요 |
| C8 | 상태값 샘플 | 복선 `resolved/unresolved`, ASS `pending_review/confirmed/discarded` | 복선 `planted`, 캐릭터 `draft/confirmed` | 상태값 목록이 다르다 | 확인 필요 |

---

## D. 실제 백엔드와 연동 확인 (2026-09-29, `prolog-backend-master` 기준)

| # | 등급 | 내용 | 근거 | 해야 할 일 |
| --- | --- | --- | --- | --- |
| D1 | 🔴 | **역할이 겹친다.** 백엔드는 LLM 호출·프롬프트를 잡 인프라에서, SCDS 룰 엔진을 인메모리+Redis(100ms 이내)로 직접 돌릴 계획이다 | 백엔드 `ROADMAP.md` Phase 2(`build_input`·`prompt_template`·`parse_result`·`confirm`), Phase 4 | A14 결정 |
| D3 | 🔴 | **SCDS 충돌 대상을 저장할 수 없다.** `conflicts`에 `conflict_target`·`chapter`가 없고 상태 기본값이 `open`이다 | `insight.conflicts` | 백엔드 스키마 보완 (C5) |
| D7 | 🟠 | **연동 준비가 없다.** 백엔드 의존성에 `prolog-ai`가 없고, `.env.example`에 `OPENROUTER_API_KEY`가 없으며, `app/ai/`·AI 워커(`ai` 큐)·celery가 비어 있다 | 백엔드 `pyproject.toml`, `worker/`, ROADMAP "(Phase 3)" | 백엔드 Phase 3·4 |
| D8 | 🟠 | **동기 함수를 `async def` 안에서 그대로 부르면 서버 전체가 멈춘다.** 호출 한 번이 최악 약 4분 40초(AIQ·SCDS)다. 큐 메시지 가시성 타임아웃도 지정돼 있지 않다 | 백엔드 `app/events/queue.py` | 워커 또는 `run_in_threadpool`로 호출, 작업 시간 제한·가시성 타임아웃 5분 이상 (handoff.md에 안내) |
| D9 | ⚪ | db.md 기준 C2·C3는 실제 스키마에서 해소됐다 | `ops.jobs`, `world_rules` | C절에 반영함 |

D2(백엔드 0002에서 해소), D4·D5·D6·D10(`fix/backend-alignment`)은 해결되어 0절로 옮겼다.

---

## E. 보완 권장 (명세 근거 없음, ⚪ 하지 않음)

`WARN_2.md` 3절에서 옮긴 것 중 명세 근거가 없는 운영·품질 개선이다. 방침상 하지 않으며, 팀이 따로 정하면 진행한다. 명세 근거가 있거나 실제 오작동인 항목(스키마 설명, SCDS dict 문자열, 후보 중복, `USE_FAKE_LLM` 예시, 제공사 라우팅, SSM `character_ids`)은 T절로 옮겼다.

| # | 대상 | 현재 | 권장 |
| --- | --- | --- | --- |
| E1 | 생성 설정 | `temperature` 미지정 | 추출 모듈은 낮은 temperature로 결과를 안정시킨다 |
| E2 | SSM | 챕터마다 순차 호출 | 동시 호출(동시 수 제한), 실패한 챕터만 재시도 |
| E3 | 시간 초과 재시도 | 시간 초과도 3번 반복 | 시간 초과는 1회만 재시도. 409 재시도도 재검토 |
| E4 | AIQ | 질문마다 원고 전체, 대화 이력 무제한 | 선택 구간 주변만, 대화는 최근 N개, 제공사 프롬프트 캐시 활용 |
| E5 | LLM 클라이언트 | 호출마다 `openai.OpenAI()` 생성 | 모듈 수준에서 한 번 만들어 재사용 |
| E6 | 출력 한도 | 모든 모듈 `max_tokens=4096` | 모듈별로 다르게 |
| E7 | 로깅 | 로그 없음 | 모듈명·시도 횟수·소요 시간·토큰 사용량 기록(원고 본문 제외) |
| E8 | 실제 경로 검증 | CI는 가짜 LLM만 | SCDS 후보 있음·SSM 다챕터 케이스를 evals에 추가 |
| E9 | evals 채점 | 글자 완전 일치 | 정규화 비교·동의어 허용 |
| E10 | 의존성 | `openai` 버전 범위 없음, 쓰지 않는 `python-dotenv` | 버전 범위 고정, 안 쓰는 의존성 제거 |
| E11 | 배포 | 버전 태그 없이 main 최신본 설치 | 태그로 고정 (CLAUDE.md에서 하지 않기로 함) |
| E12 | 쓰지 않는 코드 | `ErrorCode.AI_TIMEOUT`, `SCDSCheckStatus`, `RunStatus.FAILED`, `dropped_emotion_keywords` 계산값 | 정리 |

---

## F. 명세 ↔ 실제 백엔드 DB·코드 대조 (2026-09-29)

명세 13종을 db.md, 실제 백엔드(`prolog-backend-master` 마이그레이션 0001·0002와 코드)와 대조했다. **db.md는 실제 DB와 거의 달라**(팀·프로젝트·알림·원고·챕터 구조 등) 실제 마이그레이션을 기준으로 삼았다. db.md는 실제 마이그레이션 기준으로 다시 써야 한다.

### F1. 명세를 실제 DB에 맞춰 고친 것 (`docs/spec-align-db`)

| 명세 | 바꾼 내용 | DB 근거 |
| --- | --- | --- |
| ASS | 초안 status `pending_review` → `pending` | `character_drafts_status_chk` |
| ASS | 항목 `field` 값 복수형 → 단수형(`personality_tag` 등) | `character_draft_items_category_chk` |
| ASS | 확정 캐릭터 status `confirmed` → `active`/`archived` | `characters_status_chk` |
| ASS | 편집 이력: `added/modified/removed`, `value`, `at` → `phase`, `create/update/delete`, `before_value`, `after_value`, `created_at` | `character_edit_histories` |
| ASS | `create_new`는 다른 이름(`character_name`)을 함께 보내야 함 | `characters_project_name_active_uq` |
| SCDS | 충돌 status `pending` → `open` | `conflicts_status_chk` |
| SCDS | ConflictCheck status를 `skipped/queued/running/completed/failed`로. 후보 없음도 `skipped`, `rule_result`로 구분. **패키지도 `no_candidate` 대신 `skipped`를 반환** | `jobs_status_chk` |
| SCDS | 무시 억제 키를 `sha256(character_id : rule_id : normalize(사건 description))`로 | `conflicts.suppression_key` |
| SCDS·REX | WorldRule에 `title`(필수, 200자) 추가. REX `extracted_rules`에도 `title` 추가, **패키지가 제목을 만든다**(비면 설명 앞부분) | `world_rules.title` NOT NULL |
| NLCD·REX·SSM | 작업 status `analyzing`/`extracting` → `queued`/`running` | `jobs_status_chk` |
| FTS | status `unresolved` → `planted`, `abandoned` 추가 | `foreshadowings_status_chk` |
| FTS | 챕터 역할·마커 `linked` → `hint` | `foreshadowing_chapters_role_chk` |
| AIQ | scope `whole` → `project`/`chapter`/`selection`, `chapter_id` 추가. 스레드 제목 200자 | `qa_threads_scope_chk`, `qa_threads.title` |
| SSM | 노드 제목 200자. **패키지가 200자로 자른다** | `structure_nodes.title` |
| MSU | source_type `file` → `upload`, status에 `draft` 추가·`extraction_failed` → `failed`, `file_url` → `file_key` | `manuscripts_*_chk` |

### F2. 명세는 유지하고 백엔드 DB에 칸을 추가해야 하는 것 (팀 결정: 기능 유지)

| # | 명세 | 없는 칸 | 없으면 |
| --- | --- | --- | --- |
| F2-1 | SCDS 2.7·4.11 Conflict | `conflict_target`, `chapter`, `modified_content`, `resolved_at` | 충돌 대상 표시·수정 내용·해결 시각을 저장할 수 없다 (D3 확장) |
| F2-2 | ASS 2.3 영향 관계 | `type`, `status`(예: "고인") | 4.6 PATCH로 받은 상태가 버려진다 |
| F2-3 | RCV 2.2 관계 이력 | `event_id`, `event_deleted` | RCV-004 사건 연결을 저장할 수 없다 |
| F2-4 | SCDS 2.1 Character | `status`(`alive`/`deceased`/`removed`) | RULE-04 판단 기준이 없다 (B8) |

### F3. 이미 구현된 백엔드 코드의 버그 (백엔드 담당)

| # | 문제 | 근거 |
| --- | --- | --- |
| F3-1 | 초대 수락 토큰이 초대 생성 응답에만 있고 알림에 없어 피초대자가 수락할 수 없다 | `teams/service.py`, `projects/service.py`, `notifications/schemas.py` |
| F3-2 | 만료된 초대를 `expired`로 바꾸는 코드가 없어 계속 `pending`, 재초대 시 409 | `teams/service.py` |
| F3-3 | 가입 시 이메일 중복(`users_email_lower_uq`)을 처리하지 않아 500 | `auth/service.py` |
| F3-4 | DB 제약 위반(IntegrityError·DataError) 처리기가 없어 형식 없는 500 | `main.py` |
| F3-5 | 복선이 걸린 챕터·원고 삭제 시 `ON DELETE RESTRICT`로 500 (FTS 구현 후 발생) | `0001_initial.py`, `manuscripts/service.py` |
| F3-6 | 업로드 파일 크기 제한이 없고(명세 413 `FILE_TOO_LARGE`), 워커가 파일 전체를 메모리로 읽음 | `manuscripts/storage.py` |
| F3-7 | 원고 추출 실패 사유를 조회할 API가 없음 | `jobs/service.py` |
| F3-8 | 프로젝트 초대 권한이 owner만 (명세는 owner/editor) | `api/router.py` |

### F4. 남은 불일치 (결정·작업 필요)

- **챕터 번호**: 명세는 챕터를 정수 번호로 부르지만, DB `chapter_no`는 원고 안에서만 유일하다. 원고가 여러 개면 번호가 여러 챕터를 가리킨다. 번호를 복사해 둔 `relationship_histories.chapter_no`, `foreshadowings.*_chapter_no`는 챕터 번호를 바꿔도 갱신되지 않는다.
- **억제 키**: 가치관 기반 충돌은 `rule_id`가 null이라 한 사건의 서로 다른 충돌이 같은 키로 합쳐진다(F1에서 명세를 DB 키로 맞췄지만 이 한계는 남음).
- **캐릭터 확정 중복 값**: 사용자가 추가한 값·병합 대상 값의 중복은 `character_attributes` 유니크 인덱스에 걸린다(NLCD 출력 중복은 T32에서 해결). 백엔드 확정 로직에서 걸러야 한다.
- **초안 직접 생성**: `character_drafts.source_text` NOT NULL인데 ASS 4.1 요청에 없다.
- **프론트 연동 차이(명세 미수정)**: AUTH 3·4절이 옛 로그인 방식(로컬·네이버) 그대로, MSU 업로드 방식(presigned URL + `file/complete`)·챕터 경로(`/projects/{id}/chapters`), 작업 응답 키 `job_id`(명세 `analysis_id`), 재시도 전이(`failed → queued`) 없음, 알림 설정 구조(유형별 ↔ 전체+`muted_types`), 명세에 없는 에러 코드(`DUPLICATE_INVITATION`, `INVITATION_NOT_PENDING`, `NOT_FOUND`, `HTTP_ERROR`).
- **백엔드 구현 현황**: 명세 엔드포인트 135개 중 약 44개(AUTH·TEAM·PRJ·NOTI 일부·MSU). ASS·NLCD·REX·SCDS·RCV·FTS·AIQ·SSM API와 작업 조회 API, AI 워커는 없다.
