# WARN: 문제점·결정 항목 정리

명세를 근거로 구현하면서 확인된 문제점과, 팀이 결정해야 하지만 아직 결정되지 않은 항목을 모은 문서다.
(작성: 2026-09-28 / 2026-09-29 실제 API 호출 결과 반영 / 2026-09-29 전체 재검토 결과 반영, `WARN_2.md` 통합)

**방침 (2026-09-29)**

- 명세(API 명세, db.md)에 근거가 없는 작업은 하지 않는다. 그런 항목은 ⚪ "하지 않음(명세 근거 없음)"으로 표시했다.
- 기획.md에만 있고 API 명세에 없는 기능은 폐기된 아이디어로 보고 이 문서에서 다루지 않는다.
- 남은 작업의 담당·순서는 `CLAUDE.md` "후속 작업 계획"에 있다.

| 절 | 내용 | 현황 |
| --- | --- | --- |
| 0. 진행 현황 | 끝난 작업과 병합 대기 중인 수정 | 완료 PR 17개, 병합 대기 브랜치 2개 |
| 1. 한눈에 보기 | 남은 문제를 "안 고치면 무엇이 안 되는지" 기준으로 등급별 정리 | — |
| T. 발견한 문제 | 코드가 명세 의도대로 동작하지 않는 것 | 37건: ✅ 해결 10, 🔵 병합 대기 2, 🟡 일부 해결 3, ⚪ 하지 않음 3, 미해결 19 |
| A. 팀 결정 항목 | 이 저장소에서 정할 수 있지만 팀 결정이 필요한 것 | 14개: 결정 5, 보류 9 |
| B. 명세끼리 안 맞는 부분 | 명세 원문 수정이 필요한 것 | 18건 |
| C. DB 설계와 API 명세 불일치 | db.md 기준 (백엔드 확인) | 8건 (실제 백엔드 스키마 기준 현황은 D절) |
| D. 실제 백엔드와 연동 확인 | `prolog-backend-master` 코드·마이그레이션을 직접 읽은 결과 | 10건 |
| E. 보완 권장 | 기능은 되지만 품질·비용·운영이 아쉬운 것 (명세 근거 없음) | 12건, 모두 ⚪ |

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

### 🔵 수정 완료, 병합 대기 (PR 없음)

| 브랜치 | 내용 | 관련 항목 | 확인 결과 |
| --- | --- | --- | --- |
| `fix/core-schema-error-code` | 스키마 불일치를 모듈별 `AI_*_FAILED`로 반환하고 원래 코드는 `details.internal_code`에 남김 | T18, A4 | main과 합쳐 테스트 통과. 모든 `error.code`가 `HTTP_STATUS`에 있음 |
| `fix/scds-conflict-target-filter` | AI가 충돌 대상 문자열 대신 후보 번호(`candidate_index`)를 고르고, 패키지가 후보에서 `character_id`·`conflict_target`을 채움 | T3 | main과 합쳐 테스트 통과. 후속 보완 T28·T36 |

`docs/add-project-docs` 브랜치의 `WARN_2.md`는 이 문서에 합쳤다. 위 두 fix 브랜치에도 같은 `WARN_2.md` 커밋이 들어 있으므로, 병합할 때 `WARN_2.md`는 빼야 한다. 두 브랜치는 WARN.md의 T3·T18·A4 줄도 고치므로 이 문서와 병합 충돌이 날 수 있다(이 문서의 🔵 표시가 최신).

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
| 🔴 | **D2~D5** 실제 백엔드 스키마 불일치 | NLCD 감정 키워드·영향 관계·근거, SCDS `conflict_target`을 저장할 곳이 없고, AIQ `scope` 값과 SSM `character_ids` 타입이 맞지 않는다 | 백엔드 |
| 🔴 | **T14 / A2** SCDS 가치관 기반 판정 없음 | 캐릭터 가치관만 있고 세계관 규칙이 없는 프로젝트는 항상 `no_candidate`다 | 기획 |
| 🔴 | **T22** REX가 위반 키워드를 만들지 않음 | REX가 뽑은 규칙에 키워드가 없어 SCDS 룰 검출(RULE-02)도 못 잡는다. REX → SCDS 경로가 끊긴다 | 다른 개발자 |
| 🔴 | **T6 / T23 / A10 / A12** SSM 구조 지도 | 챕터마다 따로 분석해 acts가 중복되고, 노드 chapter가 모두 1이며, 챕터를 넘는 연결을 만들 수 없고, 캐릭터 칸에 이름이 들어간다 | 백엔드와 입력 형식 합의 |
| 🔴 | **T21** 프롬프트·스키마 설명 부재 | 실제 호출에서 REX가 규칙 0개. 다른 모듈도 명세 예시와 다른 표현을 낸다 | 팀(담당 결정) |
| 🟠 | **T3** SCDS 조언 소실 | AI가 충돌 대상을 한 글자만 바꿔 써도 조언이 조용히 전부 버려진다 | 🔵 병합 대기 |
| 🟠 | **T18 / A4** 명세에 없는 에러 코드 | 백엔드가 `HTTP_STATUS[code]`를 그대로 쓰면 `KeyError`로 요청이 죽는다 | 🔵 병합 대기 |
| 🟠 | **T24** OpenAI 키가 OpenRouter로 전송됨 | `OPENROUTER_API_KEY`가 비면 SDK가 `OPENAI_API_KEY`를 대신 써서 openrouter.ai로 보낸다 | 다른 개발자 |
| 🟠 | **T25** `.env.example`의 `USE_FAKE_LLM=1` | 예시 파일을 그대로 운영에 복사하면 모든 결과가 조용히 빈 값이 된다 | 다른 개발자 |
| 🟠 | **T26** 도구 호출 미지원 제공사 라우팅 | OpenRouter가 도구 호출을 못 하는 제공사로 보내면 3번 실패한다 | 다른 개발자 |
| 🟠 | **T27** 공백 키워드 | `violation_keywords`에 `" "`가 있으면 모든 사건이 후보가 되어 AI를 불필요하게 부른다 | 다른 개발자 |
| 🟠 | **T35 / T9** 긴 원고 | REX·AIQ는 원고 전체를 한 번에 보내고, REX·NLCD·SSM은 시간 제한 30초 그대로이며, SSM은 챕터 수만큼 순차 호출한다 | 다른 개발자 / A6 |
| 🟠 | **D6~D8** 연동 준비 | 백엔드에 의존성·키·AI 워커가 없고, 동기 함수를 `async def`에서 부르면 서버 전체가 멈춘다. README의 SCDS 상태 매핑은 백엔드 `jobs` 제약에 걸린다 | 백엔드 / 문서 |
| 🟠 | **B14** AIQ 선택 구간 오프셋 기준 | 오프셋이 챕터 기준인지 원고 전체 기준인지 명세에 없어, 틀리면 `INVALID_SELECTION_RANGE`나 엉뚱한 구간에 답한다 | 기획·백엔드 |
| 🟡 | T5, T12, T28~T34, T36, T37 | 챕터 오인, 빈 값·중복·지어낸 값 통과, 억제 입력 없음 등 | 다른 개발자 / 결정 |
| ⚪ | T8, T9(크기 상한), T16, E1~E12 | 명세 근거 없음 | — |

---

## T. 발견한 문제

### 검토 이력

| 날짜 | 대상 | 방법 |
| --- | --- | --- |
| 2026-09-28 | main(PR #7 시점) | `pytest` 194개·ruff 통과 확인, 공개 함수를 실제 사용 흐름대로 호출하고 LLM 응답 자리에 원하는 값을 심어 관찰, 가짜 클라이언트로 실제 호출 경로 확인, wheel 설치 확인 |
| 2026-09-29 | main(PR #12~#17) | 실제 API 호출 (아래 "실제 호출 결과") |
| 2026-09-29 | main(PR #17) + 병합 대기 브랜치 2개 | 코드·API 명세 13종·db.md 전체 대조, 실제 백엔드 저장소(`prolog-backend-master`) 대조, 의심 지점을 가짜 LLM으로 재현. `WARN_2.md`(다른 개발자 검토) 통합. 병합 대기 브랜치를 main에 합쳐 테스트 290개 통과 확인 |

이상 없음으로 확인된 것:

- 공개 함수 7개(`run_nlcd`, `run_rex`, `run_aiq`, `run_scds`, `run_scds_rules`, `run_scds_analysis`, `run_ssm`) 모두 어떤 입력·AI 오류에도 예외 없이 정해진 형식으로 응답한다.
- 인자 누락·타입 오류는 `INVALID_INPUT`, 시간 초과는 `AI_*_TIMEOUT`, 그 밖의 AI 실패는 `AI_*_FAILED`로 분류된다.
- 실제 API에서 다섯 모듈 모두 정해진 스키마로 응답을 받았다.

심각도: **높음** = 명세의 핵심 기능이 동작하지 않거나 데이터·보안 사고 / **중간** = 운영 중 오류·비용·오판 위험 / **낮음** = 정리 필요

### 발견한 문제

| # | 심각도 | 모듈 | 문제 | 확인 방법·결과 | 대응 |
| --- | --- | --- | --- | --- | --- |
| T1 | 높음 | SCDS | **AI 분석에 캐릭터 설정이 전달되지 않는다.** `run_scds`는 `event`, `world_rules`만 받았다 | 프롬프트에 가치관 없음 | ✅ 해결(PR #8): `characters=`로 ASS 확정 캐릭터를 받아 mapping으로 변환 후 전달. 캐릭터 설정도 참조 데이터로 인정 |
| T2 | 높음 | SCDS | **AI 분석이 실패하면 룰 후보가 사라지고, 룰 검출과 AI 분석을 나눠 쓸 수 없다** (SCDS 4.6·4.7·5항) | LLM 실패를 심으면 `error`만 반환 | ✅ 해결(PR #8, #16): 실패 시 `error.details.rule_result`, 성공 시 `data.rule_result`. `run_scds_rules`(룰 검출만, 후보 있으면 `queued`)와 `run_scds_analysis`(AI 분석만, 재시도에도 사용)로 분리. `run_scds`는 둘을 차례로 부르는 함수로 유지 |
| T3 | 높음 | SCDS | **AI가 지어낸 충돌이 통과하거나, 반대로 정상 조언이 버려진다.** 처음에는 후보에 없는 캐릭터·설정으로 만든 충돌이 그대로 통과했다(PR #8에서 해결). 그 해결책인 문자열 완전 일치 필터(`_keep_candidate_conflicts`)는, AI가 충돌 대상을 한 글자만 바꿔 써도("폭력 회피" → "폭력을 회피하는 가치관") 조언을 전부 버리고 `completed`, `conflicts: []`로 내보낸다. 프롬프트에 "그대로 옮겨 적으라"는 지시도 없다 | 바꿔 쓴 충돌 대상을 심으면 `conflicts: []`, `removed_conflict_count: 1` (재현) | 🔵 병합 대기(`fix/scds-conflict-target-filter`): AI는 후보 번호만 고르고 패키지가 후보에서 필드를 채움. 후속 보완 T28·T36 |
| T4 | 높음 | SSM | **첫 챕터 제목 앞의 글(프롤로그)이 버려진다** | `split_into_chapters` 결과 확인 | ✅ 해결(PR #8): 첫 제목 앞 텍스트를 첫 청크로 보존 |
| T5 | 높음 | SSM | **챕터 인식이 흔한 형식에서 틀린다.** MSU 예시 형식 "1화"는 인식하지 못해 원고 전체가 청크 하나가 된다. 반대로 본문 줄 첫머리의 "3장의 편지를 썼다", "10장면 전환"도 챕터 경계로 오인한다 | "1화/2화" → 청크 1개, "3장의…"·"10장면…" → 경계로 잘림 (재현) | 미해결: A10 결정(MSU 챕터 목록을 입력으로 받기)이 근본 해결 |
| T6 | 높음 | SSM | **청크를 합친 구조 지도가 명세 구조와 다르다.** 청크마다 LLM을 따로 불러 이어붙이므로, 챕터마다 "발단"부터 새로 생겨 acts가 챕터 수만큼 쌓이고(3장 원고 → 발단 3개), 노드 `chapter`는 LLM이 몇 번째 챕터인지 몰라 모두 1이다. 명세 4.4 예시의 acts는 원고 전체 기준(발단 1~8장, 전개 9~30장)이다 | 다챕터 원고 병합 결과 확인 | 🟡 일부 해결(PR #8): node_id를 전체에서 새로 매기고 edges도 바꿈, 없는 노드를 가리키는 edge는 제거. **남음**: chapter 번호·acts를 전체 원고 기준으로 맞추기(A10과 함께). 챕터 간 연결은 T23 |
| T7 | 높음 | AIQ | **선택 구간 질문에 원고 전체만 보냈다** | 프롬프트 확인 | ✅ 해결(PR #8): 원고 전체와 함께 `선택 구간(start~end)` 블록을 넣음 |
| T8 | 높음 | 공통 | **`.env`를 읽지 않는다.** `python-dotenv`가 의존성에 있지만 쓰지 않는다 | `src/`에 dotenv 사용처 없음 | ⚪ 하지 않음(명세 근거 없음): 라이브러리는 환경변수만 본다. README에 셸에서 불러오는 방법을 적어 둠. 쓰지 않는 의존성은 E10 |
| T9 | 중간 | REX·AIQ·SSM | **입력 크기 상한이 없다.** REX는 원고 전체를 한 번에 넣는다(30만 자 → 프롬프트 300,036자). AIQ는 질문마다 원고 전체를 넣고, `selection`이면 선택 구간을 한 번 더 붙인다(10만 자 원고에 10자 선택 → 100,069자). SSM은 제목 패턴이 없으면 원고 전체가 청크 하나다. 출력은 `max_tokens=4096`이라 큰 출력은 잘려 재시도 없이 실패한다 | 호출 횟수·프롬프트 길이 관찰 | ⚪ 하지 않음(명세 근거 없음): 명세에 크기 기준이 없다. 실패해도 `AI_*_FAILED`로 정상 반환된다. REX 챕터 단위 호출은 A6, 시간 제한은 T35 |
| T10 | 중간 | 공통 | **실제 호출 재시도가 과했다.** 다시 해도 소용없는 오류도 3번 시도했고, SDK 자체 재시도와 겹쳐 요청이 최대 9번 나갔다 | 가짜 클라이언트로 확인 | 🟡 일부 해결(PR #8, #12): SDK 자체 재시도 끔(현재 `openai.OpenAI(..., max_retries=0)`), 408·409·429·5xx·연결 오류만 재시도, 그 밖의 4xx는 즉시 실패. 모델 미지정 시 `DEFAULT_MODEL` 사용. **남은 부분(키 누락 시 처리)은 하지 않음(명세 근거 없음)**. 단, 키 누락 시 다른 키가 전송되는 문제는 T24 |
| T11 | 중간 | 공통 | **출력이 잘린 것을 스키마 불일치로 보고했다** | 가짜 클라이언트로 확인 | ✅ 해결(PR #8): 잘리면 재시도 없이 `AI_*_FAILED`, 메시지에 잘림 명시 |
| T12 | 중간 | NLCD·REX | **근거 대조에 허점이 있다.** 공백만 있는 근거가 통과했다. `value`가 빈 문자열인 항목도 통과한다. 「」『』, 말줄임표 `…`/`...`는 정규화하지 않아 정상 근거가 지워질 수 있다. "마법"처럼 아주 짧은 근거도 원문에 있으면 통과한다 | `is_present("   ", ...)` → True였음 | 🟡 일부 해결(PR #8): 공백만 있는 근거 거부, 「」『』 정규화. **남음 (오류 수정, 다른 개발자)**: 빈 `value` 항목 처리. 말줄임표 정규화·최소 근거 길이는 하지 않음(명세 근거 없음) |
| T13 | 중간 | 공통 | **가짜 LLM 설정이 불안정했다** | 가짜 응답 검증 실패 확인 | ✅ 해결(PR #8): 가짜 응답이 `Literal`·`Enum`을 채움. `USE_FAKE_LLM`은 `1`만 인정한다고 README에 명시 |
| T14 | 중간 | SCDS | **룰 검출이 쉽게 빗나간다.** `character_ids`가 빈 배열이면 세계관 규칙 위반도 `no_candidate`가 된다. 키워드 사이 공백 한 칸 차이("잔혹하게  살해")로 검출되지 않는다. 후보의 `rule_id`에 WorldRule id(`wr_001`)를 넣는데 명세 예시는 룰 종류(`RULE-01`)를 넣는다. 가치관 기반 판정(RULE-01/03/04)은 없다 | 각 입력으로 status 확인 (재현) | 미해결: 판정 기준은 A2(기획). 공백 차이·빈 `character_ids` 처리는 오류 수정(다른 개발자). rule_id 의미는 B13. 공백 키워드는 T27, 후보 중복은 T28 |
| T15 | 중간 | SCDS | **응답 모양이 경우마다 달랐다** | data 키 비교 | ✅ 해결(PR #8): 모든 결과가 `data.status`와 `data.rule_result`를 가짐 |
| T16 | 중간 | 공통 | **프롬프트 인젝션 방어가 없다.** 시스템 프롬프트 없이 사용자 입력을 구분자 없이 지시문 뒤에 이어붙인다 | 생성된 프롬프트 확인 | ⚪ 하지 않음(명세 근거 없음): 프롬프트 튜닝이라 범위 밖. 프롬프트 작성(T21) 때 원고를 태그로 감싸면 함께 해결된다 |
| T17 | 중간 | AIQ | **후속 질문의 이전 대화를 받을 수 없었다** (AIQ 4.4) | 시그니처 확인 | ✅ 해결(PR #15): `run_aiq(..., messages=)`로 이전 메시지(`role`/`content`)를 받아 "이전 대화" 블록에 넣음. 실제 호출로 앞 대화를 이어받는 것 확인 |
| T18 | 중간 | 공통 | **명세에 없는 내부 코드가 밖으로 나간다.** 백엔드가 `HTTP_STATUS[code]`로 변환하면 `SCHEMA_VALIDATION_FAILED`에서 `KeyError`가 난다 | `core/errors.py` 확인 | 🔵 병합 대기(`fix/core-schema-error-code`): 모듈별 `AI_*_FAILED`로 반환, 원래 코드는 `details.internal_code` |
| T19 | 낮음 | 공통 | `core/mapping.py`가 어디에서도 쓰이지 않았다 | grep | ✅ 해결(PR #8): SCDS에서 사용 |
| T20 | 낮음 | 공통 | 버전이 두 곳에 따로 적혀 있었다 | 파일 확인 | ✅ 해결(PR #8): `__init__.py`의 `__version__` 한 곳 |
| T21 | 높음 | 공통 | **프롬프트와 스키마 설명이 자리표시 수준이다.** 다섯 모듈 `prompt.py`가 한두 줄짜리 지시문이고, LLM에 넘기는 도구 스키마(`model_json_schema()`)에도 필드 설명(`description`)이 하나도 없다. 모델은 무엇을 어떤 기준으로 뽑아야 하는지 모른다. SCDS 프롬프트는 사건·캐릭터 설정을 파이썬 dict 문자열(`{'key': ...}`)로 넣는다 | 실제 호출: REX 규칙 0개, NLCD 값 표현이 명세 예시와 다름, SCDS 조언에 원고에 없는 원작 지식("큰 힘에는 큰 책임")이 섞임 | 미해결: 절대 규칙상 프롬프트 튜닝은 범위 밖이라 담당·범위를 팀이 먼저 정한다. 스키마에 `Field(description=...)`로 명세 필드 정의를 옮기는 것만으로도 효과가 크다 |
| T22 | 높음 | REX·SCDS | **REX가 위반 키워드를 만들지 않아 SCDS 룰 검출이 끊긴다.** `rex/schema.py`의 `violation_keywords`는 필수가 아니고(기본값 빈 배열) 설명도 없으며, 프롬프트도 키워드를 요구하지 않는다. SCDS 룰 검출은 이 키워드로만 후보를 찾으므로(SCDS 2.2 "RULE-02 판정에 사용"), 사용자가 키워드를 직접 넣지 않는 한 REX가 뽑은 규칙으로는 SCDS가 아무것도 잡지 못한다 | 키워드 없는 규칙 → `no_candidate` (재현) | 미해결 (오류 수정, 다른 개발자): `violation_keywords`를 필수로 두고 필드 설명을 단다(T21과 함께). 공백·빈 키워드는 거른다(T27) |
| T23 | 높음 | SSM | **챕터를 넘는 연결(edges)을 만들 수 없다.** 청크마다 독립 호출이라 LLM은 다른 챕터의 노드를 모른다. 만들더라도 병합할 때 없는 노드로 보고 버린다. 결과적으로 edges는 한 챕터 안의 인과관계만 남고, 복선 → 회수 같은 장편의 핵심 연결이 빠진다 | 코드 흐름 확인 (`ssm/module.py`) | 미해결: A10(챕터 목록 입력)과 함께 "챕터별 요약 → 전체 기준 한 번 더 판단"하는 두 단계 구조가 필요하다 |
| T24 | 높음 | 공통 | **`OPENROUTER_API_KEY`가 비면 OpenAI 키가 OpenRouter로 전송된다.** `openai.OpenAI(api_key=None)`은 `OPENAI_API_KEY` 환경변수를 대신 쓴다. 백엔드 서버에 OpenAI 키가 있으면 그 키가 openrouter.ai로 나간다. 키가 둘 다 없을 때의 오류 메시지도 "OPENAI_API_KEY를 설정하라"고 나와 원인을 헷갈리게 한다 | 키 없이 `run_nlcd` 호출 → 메시지 확인 (재현), SDK 소스 확인 | 미해결 (오류 수정, 다른 개발자): 키가 없으면 SDK를 만들기 전에 `AI_*_FAILED`로 반환한다 |
| T25 | 중간 | 공통 | **`.env.example`에 `USE_FAKE_LLM=1`이 들어 있다.** 예시 파일을 그대로 운영 환경에 복사하면 모든 결과가 조용히 빈 값(가짜 응답)이 된다 | 파일 확인 | 미해결 (오류 수정, 다른 개발자): 예시 파일에서 값을 비우고 주석으로 용도를 적는다 |
| T26 | 중간 | 공통 | **도구 호출을 지원하지 않는 제공사로 라우팅될 수 있다.** OpenRouter에 제공사 조건을 주지 않아, 도구 호출을 못 하는 제공사로 가면 "respond 도구 호출이 없습니다"로 3번 실패한다 | `core/llm.py` 확인 | 미해결 (오류 수정, 다른 개발자): `extra_body={"provider": {"require_parameters": True}}`로 도구 호출을 지원하는 제공사만 쓰게 한다 |
| T27 | 중간 | SCDS | **공백만 있는 키워드 하나가 모든 사건을 후보로 만든다.** `rules.py`의 `if keyword and keyword in content`에서 `" "`는 참이고 거의 모든 본문에 들어 있다. 입력 검증도 빈 키워드를 막지 않는다. 불필요한 AI 호출과 비용이 생긴다 | `violation_keywords=[" "]`, 본문 "x y" → 후보 생성 (재현) | 미해결 (오류 수정, 다른 개발자): 공백만 있는 키워드는 무시하거나 `INVALID_INPUT` |
| T28 | 중간 | SCDS | **같은 (캐릭터, 규칙) 후보와 충돌이 중복된다.** 규칙 하나에 키워드가 여러 개 걸리거나 `character_ids`에 같은 id가 반복되면 후보가 곱으로 늘어난다("살해"·"잔혹하게 살해" → 후보 2개). 후보 번호 방식(🔵 T3)에서도 AI가 같은 번호를 두 번 고르면 충돌이 2개 생긴다 | 재현 | 미해결 (오류 수정, 다른 개발자): 후보를 (캐릭터, 규칙) 단위로 합치고, 같은 후보 번호의 충돌은 하나만 남긴다 |
| T29 | 낮음 | SCDS | **`run_scds_analysis`가 사건과 `rule_result`가 짝이 맞는지 확인하지 않는다.** 후보의 `character_id`가 사건의 `character_ids`에 없어도 진행하고, 그 캐릭터의 설정은 프롬프트에서 빠진다. 재시도(4.8) 때 다른 사건을 넘겨도 알 수 없다 | 코드 확인 | 미해결 (오류 수정, 다른 개발자) |
| T30 | 중간 | REX | **`source_chapter`를 LLM이 지어낼 수 있다.** 챕터 정보를 주지 않는데 도구 스키마에는 `source_chapter` 칸이 있어, 모델이 넣은 번호가 검증 없이 통과한다 | 스키마 확인 | 미해결: A6 결정 전까지는 패키지가 `null`로 덮어쓴다(오류 수정, 다른 개발자) |
| T31 | 낮음 | SSM | **노드·연결 병합에 빈틈이 있다.** 한 청크에서 LLM이 같은 `node_id`를 두 번 내면 두 번째 노드는 새 id를 받지만 edge는 항상 첫 노드로 연결된다(`setdefault`). 자기 자신을 가리키는 edge와 중복 edge도 거르지 않는다. 청크가 실패해도 몇 번째 청크인지 `details`에 없다 | 코드 확인 | 미해결 (오류 수정, 다른 개발자) |
| T32 | 중간 | NLCD | **같은 값이 두 번 나오면 백엔드 저장이 실패한다.** NLCD 결과의 중복 값을 거르지 않는데, 실제 백엔드 `character_attributes`에는 `(character_id, category, lower(value))` 유니크 인덱스가 있다 | 백엔드 마이그레이션 확인 | 미해결 (오류 수정, 다른 개발자): 같은 카테고리 안의 중복 값을 합친다 |
| T33 | 낮음 | 공통 | **HTTP 408 시간 초과가 `TIMEOUT`이 아니라 `FAILED`로 분류된다.** 408로 재시도가 끝나면 마지막 오류가 `APIStatusError`라서 `AI_*_FAILED`가 된다 | 코드 확인 | 미해결 (오류 수정, 다른 개발자) |
| T34 | 낮음 | AIQ | **입력 처리가 느슨하다.** 빈 원고(`""`, 공백만)로 질문해도 LLM을 부른다. 방금 저장한 현재 질문을 `messages`에 넣으면 질문이 두 번 들어가는데 README에 안내가 없다. `start`/`end`가 정수가 아닌 것도 `INVALID_SELECTION_RANGE`로 보낸다(명세는 범위 초과·누락에만 씀) | 코드 확인 | 미해결 (오류 수정, 다른 개발자): 빈 원고는 `INVALID_INPUT`, README에 "현재 질문은 `question`으로만" 안내 |
| T35 | 중간 | REX·NLCD·SSM | **긴 작업의 시간 제한이 기본 30초 그대로다.** AIQ·SCDS는 90초로 늘렸지만(PR #13, #17), 원고 전체를 한 번에 넣는 REX와 챕터를 분석하는 SSM은 30초다. SSM은 챕터 수만큼 순차 호출해 300장이면 최악 몇 시간이 걸리고, 하나만 실패해도 앞의 결과를 버린다(A11) | 코드 확인 | 미해결 (오류 수정, 다른 개발자): REX·SSM도 명세상 비동기(폴링)라 시간 상한이 없으므로 AIQ·SCDS처럼 늘린다 |
| T36 | 낮음 | SCDS | **후보 번호가 느슨하게 변환된다** (🔵 T3 후속). `candidate_index: int`라 AI가 `true`나 `"0"`을 넣어도 통과한다(`true` → 1번 후보) | 병합 대기 브랜치에서 재현 | 미해결 (오류 수정, 다른 개발자): `StrictInt` 등 엄격한 정수로 받는다 |
| T37 | 중간 | SCDS | **무시한 충돌을 다시 감지하지 않게 할 입력이 없다.** SCDS 4.11 비고는 `ignored` 처리된 (`character_id`, `conflict_target`, `input_event`) 조합을 "이후 룰 검출 단계에서 재감지되지 않도록" 하라고 하지만, `run_scds_rules`·`run_scds`는 억제 목록을 받지 않는다 | 시그니처 확인 | 미해결 (기능 누락): 백엔드가 결과에서 후보를 걸러내면 우회 가능하다. 패키지에서 받을지는 A14(룰 엔진 담당)와 함께 정한다 |

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
| AIQ 후속 질문 | 5.5초 / 3.8초 | 두 번째 질문의 "그 인물"을 첫 답의 "벤 삼촌"으로 이어받음 | ✅ PR #15 동작 확인 |

`evals --real`의 채점은 글자 완전 일치라 위 결과는 표현 차이만으로 실패로 나온다. 결과는 사람이 보고 판단한다(E9).

---

## A. 팀 결정 항목

### 결정됨

| # | 항목 | 결정 | 다음 할 일 | 담당 |
| --- | --- | --- | --- | --- |
| A1 | NLCD가 캐릭터 이름도 추출하는가 | **추출한다** (2026-09-28) | NLCD API 명세에 `character_name` 필드 추가를 백엔드와 합의한 뒤 `nlcd/schema.py`에 필드 추가. 합의 전에는 구현하지 않음. 이름이 없어도 ASS 초안 수정(4.4 PATCH)으로 사용자가 넣을 수 있어 불능은 아니다 | Dev A |
| A4 | 내부용 에러 코드 노출 방식 | **① 모듈별 `AI_*_FAILED`(502)로 바꿔 보내고 원래 코드는 `details.internal_code`에 남긴다** | 🔵 `fix/core-schema-error-code` 병합 | 공동 |
| A7 | SCDS `related_chapter_ref` | **만들지 않는다** (방침) | 없음. 채우려면 명세에 없는 입력이 필요하다 | — |
| A8 | AIQ 답변 근거 대조 | **적용하지 않는다** (방침) | 없음. 적용하려면 AIQ 명세 변경이 필요하다 | — |
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
| A12 | SSM 노드 `character_ids` | SSM 2.3은 ASS/SCDS 캐릭터 ID를 참조하라고만 한다. 입력에 캐릭터 목록이 없다. 실제 백엔드는 uuid 외래키다(D5) | 모델이 캐릭터 **이름**을 넣음(실제 호출 확인). 검증 없음 | ① 확정 캐릭터(id, name) 목록을 입력으로 받아 AI가 ID 선택, 목록에 없는 값은 제거 ② 항상 빈 배열로 비움 | Dev B | `modules/ssm/schema.py` |
| A13 | ASS AI 재추천을 이 저장소에서 만드는가 | ASS 4.8(선택 기능, 기본 비활성화, `AI_SUGGESTION_DISABLED`)은 AI 호출 기능인데 이 패키지에 없다 | 없음 | ① 이 저장소에서 만든다(새 모듈) ② 이 저장소 범위가 아니다 | 공동 | — |
| A14 | **LLM 호출·프롬프트·룰 엔진을 누가 맡는가** | 백엔드 ROADMAP은 모듈마다 `build_input`·`prompt_template`·`parse_result`·`confirm`만 두고 LLM 호출은 백엔드 잡 인프라가 한다고 적었다. SCDS 룰 엔진도 백엔드에서 인메모리+Redis로 100ms 안에 돌린다고 적었다(D1). 이 패키지는 프롬프트·LLM 호출·룰 검출을 모두 `run_*` 안에 갖고 있다 | 패키지가 모두 수행 | ① 패키지가 수행(현재), 백엔드 ROADMAP 수정 ② 백엔드가 호출, 패키지는 프롬프트·스키마·파싱만 제공(대규모 변경) ③ 룰 엔진은 백엔드, AI 분석은 패키지 | 공동 + 백엔드 | 전체 |

A6·A10·A12는 모두 "MSU 챕터 목록이나 확정 캐릭터 목록을 입력으로 받을지"라는 같은 질문이라, 백엔드와 입력 형식을 한 번에 정하면 함께 풀린다(T5·T6·T23·T30도 함께). A14는 다른 모든 연동 작업보다 먼저 정해야 한다.

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
| B13 | SCDS 2.6 ↔ 4.6 | `candidates[].rule_id`가 WorldRule id(`wr_001`)인지 룰 종류(`RULE-01`)인지 알 수 없다. 실제 백엔드 `conflicts.rule_id`는 `world_rules` uuid 외래키다 |
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
| C1 | NLCD 결과 저장 | 항목마다 `evidence`, `emotion_keywords`, `influence_relations`, 추출 작업 | `CharacterPersonalityTags`·`CharacterCoreValues`에 `value`만 | 근거·감정 키워드를 저장할 곳이 없다 | **여전히 막힘** (D2) |
| C2 | 작업(job) 테이블 | NLCD·REX·SCDS·SSM 작업 상태값 | 없음 | 폴링 상태를 저장할 곳이 없다 | 해소: `ops.jobs`(result/error jsonb) 있음. 상태값 제약은 D6 |
| C3 | 세계관 규칙 | `description`, `violation_keywords`, `origin`, `evidence` | `WorldRules(content)`만 | SCDS 룰 검출 입력을 만들 수 없다 | 해소: `world_rules`에 `violation_keywords`, `evidence`, `origin`, `source_chapter_no` 있음 |
| C4 | AIQ | 스레드·메시지(`role`, `content`, `status`), 오프셋 | `ManuscriptQuestions(question, target_text)` | 답변 저장 컬럼이 없고 범위를 텍스트로 저장한다 | `qa_threads` 있음. `scope` 값 불일치(D4) |
| C5 | 충돌(Conflict) | `conflict_target`, `input_event`, `chapter`, 상태 `pending/accepted/ignored/modified` | `description`, Events FK, `chapter_id`, 샘플 상태 `open/resolved` | 필드·타입·상태값이 모두 다르다 | **여전히 막힘** (D3) |
| C6 | 스토리 구조 분석 | `acts[{act_name, chapter_from, chapter_to, summary}]`, `nodes`, `edges` | `result jsonb`, 샘플 구조가 완전히 다름 | 이 패키지는 API 명세 구조로 출력한다 | 노드 캐릭터 연결은 D5 |
| C7 | 챕터 참조 | 챕터 번호(정수) | `chapter_id`(uuid), `Chapters`에 본문·순번 없음 | 백엔드가 번호와 id를 변환해야 하고, DB만으로는 챕터 본문을 모을 수 없다(AIQ·SSM 입력) | 확인 필요 |
| C8 | 상태값 샘플 | 복선 `resolved/unresolved`, ASS `pending_review/confirmed/discarded` | 복선 `planted`, 캐릭터 `draft/confirmed` | 상태값 목록이 다르다 | 확인 필요 |

---

## D. 실제 백엔드와 연동 확인 (2026-09-29, `prolog-backend-master` 기준)

| # | 등급 | 내용 | 근거 | 해야 할 일 |
| --- | --- | --- | --- | --- |
| D1 | 🔴 | **역할이 겹친다.** 백엔드는 LLM 호출·프롬프트를 잡 인프라에서, SCDS 룰 엔진을 인메모리+Redis(100ms 이내)로 직접 돌릴 계획이다 | 백엔드 `ROADMAP.md` Phase 2(`build_input`·`prompt_template`·`parse_result`·`confirm`), Phase 4 | A14 결정 |
| D2 | 🔴 | **NLCD 결과를 저장할 수 없다.** `character_attributes.category`는 `personality_tag`·`core_value`만 허용하고 근거 컬럼이 없다. 감정 키워드·영향 관계·근거가 버려진다 | 마이그레이션 `0001_initial.py` `character_attributes_category_chk` | 백엔드 스키마 보완 (C1) |
| D3 | 🔴 | **SCDS 충돌 대상을 저장할 수 없다.** `conflicts`에 `conflict_target`·`chapter`가 없고 상태 기본값이 `open`이다 | `insight.conflicts` | 백엔드 스키마 보완 (C5) |
| D4 | 🔴 | **AIQ `scope` 값이 다르다.** 백엔드는 `project`/`chapter`/`selection`, 명세·패키지는 `whole`/`selection`이다 | `qa_threads_scope_chk` | 명세와 백엔드 중 하나로 통일 (B14와 함께) |
| D5 | 🔴 | **SSM `character_ids` 타입이 다르다.** 백엔드는 uuid 외래키인데 패키지는 모델이 쓴 이름을 그대로 낸다 | `structure_node_characters.character_id` | A12 결정 |
| D6 | 🟠 | **README의 SCDS 상태 안내가 백엔드 `jobs` 제약에 걸린다.** README는 작업 상태에 `data.status`(`no_candidate` 포함)를 그대로 쓰라고 하는데, `jobs.status`는 `queued/running/completed/failed/skipped`만 허용한다 | `jobs_status_chk` | README 수정: `no_candidate`·`skipped`는 AI 작업을 만들지 않는 결과로 안내 |
| D7 | 🟠 | **연동 준비가 없다.** 백엔드 의존성에 `prolog-ai`가 없고, `.env.example`에 `OPENROUTER_API_KEY`가 없으며, `app/ai/`·AI 워커(`ai` 큐)·celery가 비어 있다 | 백엔드 `pyproject.toml`, `worker/`, ROADMAP "(Phase 3)" | 백엔드 Phase 3·4 |
| D8 | 🟠 | **동기 함수를 `async def` 안에서 그대로 부르면 서버 전체가 멈춘다.** 호출 한 번이 최악 약 4분 40초(AIQ·SCDS)다. 큐 메시지 가시성 타임아웃도 지정돼 있지 않다 | 백엔드 `app/events/queue.py` | 워커 또는 `run_in_threadpool`로 호출, 작업 시간 제한·가시성 타임아웃 5분 이상 (handoff.md에 안내) |
| D9 | ⚪ | db.md 기준 C2·C3는 실제 스키마에서 해소됐다 | `ops.jobs`, `world_rules` | C절에 반영함 |
| D10 | 🟡 | 백엔드는 Python 3.12인데 CI는 3.11만 검사한다 | 백엔드 `pyproject.toml`, `.github/workflows/ci.yml` | CI에 3.12 추가(오류 수정, 다른 개발자) |

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
