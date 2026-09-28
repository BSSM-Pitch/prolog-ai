# WARN: 문제점·의문점 정리

명세를 근거로 구현하면서 확인된 문제점과, 팀이 결정해야 하지만 아직 결정되지 않은 항목을 모은 문서다.
(작성: 2026-09-28, 6단계 팀 결정 질문 결과 반영)

- **A. 팀 결정 항목**: 이 저장소에서 정할 수 있지만 팀 결정이 필요한 것 (12개 중 결정 1, 보류 11)
- **B. 명세끼리 안 맞는 부분**: 명세 원문 수정이 필요한 것 (백엔드·기획 확인)
- **C. DB 설계와 API 명세 불일치**: 이 저장소가 정할 수 없는 것 (백엔드 확인)

담당: NLCD·REX·AIQ = Dev A, SCDS·SSM = Dev B, 공통 = 공동

---

## A. 팀 결정 항목

### 결정됨

| # | 항목 | 결정 | 다음 할 일 | 담당 |
| --- | --- | --- | --- | --- |
| A1 | NLCD가 캐릭터 이름도 추출하는가 | **추출한다** (2026-09-28) | NLCD API 명세에 `character_name` 필드 추가를 백엔드와 합의한 뒤, `nlcd/schema.py`에 필드 추가. 합의 전에는 구현하지 않음 | Dev A |

A1 근거: ASS 확정 시 `character_name`이 비어 있으면 400 `MISSING_REQUIRED_FIELD`(ASS 1.4, 4.9)인데, NLCD 출력(NLCD 2.1)에는 이름 필드가 없다. 현재 코드: `modules/nlcd/schema.py` TODO.

### 보류 (결정 필요)

| # | 항목 | 문제 (명세 근거) | 현재 코드 동작 | 선택지 | 담당 | 코드 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| A2 | SCDS RULE-01/03/04 판정 방식 | 예시(SCDS 4.6)는 가치관 "폭력 회피"와 문구 "잔혹하게 살해"를 연결하지만, 그 연결 사전이 명세에 없다. 원본 기능 명세서(SCDS v0.1)도 없음 | `WorldRule.violation_keywords` 매칭(RULE-02)만 동작. 캐릭터 가치관 충돌은 감지 못 함 | ① 가치관별 위반 키워드 사전(팀 제공) ② RULE-02만 유지 ③ 캐릭터에 values가 있으면 항상 AI 분석(기획서 11-2 "선택적 AI 호출" 원칙과 충돌) | Dev B | `modules/scds/rules.py` |
| A3 | SCDS severity 판정 기준 | SCDS 2.7은 `low/medium/high` 값만 있고 기준이 없다 | LLM이 고르도록 스키마만 있음 (기준 없음) | ① AI가 판단(프롬프트에 기준 명시) ② 룰별 고정값 | Dev B | `modules/scds/schema.py` |
| A4 | 내부용 에러 코드 노출 방식 | `AI_TIMEOUT`, `SCHEMA_VALIDATION_FAILED`는 명세에 없다 | LLM 응답이 스키마와 안 맞으면 `SCHEMA_VALIDATION_FAILED`가 그대로 나감. HTTP 상태 미정 | ① 모듈별 `AI_*_FAILED`(502)로 바꿔 보내고 원래 코드는 details에 남김 ② 그대로 노출하고 명세에 코드·HTTP 상태 추가 | 공동 | `core/errors.py`, `core/runner.py` |
| A5 | NLCD `duplicate_of` 판정 주체 | NLCD 2.1/4.1. 이전 추출 이력은 백엔드 DB에만 있다 | 패키지는 관여하지 않음 | ① 백엔드 ② 패키지(이전 추출 목록을 입력으로 받아 유사도 판정, 시그니처 변경) | Dev A | — |
| A6 | REX `source_chapter`를 채우는 주체 | REX 2.1에 필드는 있지만 `run_rex`는 원고 텍스트만 받아 챕터 번호를 모른다 | 항상 `null` | ① 챕터 목록(MSU Chapter)을 입력으로 받아 패키지가 채움(시그니처 변경) ② 백엔드가 챕터별로 호출하고 번호를 붙임 | Dev A | `modules/rex/schema.py` |
| A7 | SCDS `related_chapter_ref` | SCDS 2.7 선택(N) 필드. 설정이 어느 챕터에서 정의됐는지는 입력에 없다 | 필드를 만들지 않음 | ① 만들지 않음(필요하면 백엔드가 채움) ② 설정별 정의 챕터를 입력으로 받아 AI가 채움 | Dev B | `modules/scds/schema.py` |
| A8 | AIQ 답변 근거 대조 | AIQ 2.2 `QAMessage`에는 `content`만 있고 근거 필드가 없다 | 근거 대조 안 함 | ① 적용 안 함 ② 답변에 원고 인용 목록을 추가하고 대조(명세 변경 필요) | Dev A | `modules/aiq/schema.py` |
| A9 | SSM 분량 부족 기준 | SSM 1.4/4.1에 `MANUSCRIPT_TOO_SHORT`(422)는 있지만 기준값이 없다 | 완전히 비어 있을 때만 반환 | ① 현재 유지 ② 최소 글자 수 ③ 최소 챕터 수 | Dev B | `modules/ssm/module.py` |
| A10 | SSM 챕터 경계 기준 | MSU 2.2에 `Chapter(chapter_no, title, content)`가 이미 있다 | "제N장/N장" 제목 패턴으로 자름. 패턴이 없으면 원고 전체가 청크 하나 | ① MSU 챕터 목록을 입력으로 받음(정확, 시그니처 변경) ② 제목 패턴 유지 | Dev B | `modules/ssm/chunking.py` |
| A11 | SSM 청크 하나가 실패할 때 | SSM 명세는 작업 단위의 `failed`만 정의하고 부분 실패는 언급이 없다 | 첫 실패를 그대로 반환(전체 실패) | ① 전체 실패 ② 성공한 챕터만 병합하고 실패 챕터는 meta에 기록(명세에 없는 상태) | Dev B | `modules/ssm/module.py` |
| A12 | SSM 노드 `character_ids` | SSM 2.3은 ASS/SCDS 캐릭터 ID를 참조하라고만 한다. 입력에 캐릭터 목록이 없다 | 항상 빈 배열 | ① 확정 캐릭터(id, name) 목록을 입력으로 받아 AI가 ID 선택, 목록에 없는 ID는 제거 ② 빈 배열 유지(백엔드도 채울 정보가 없음) | Dev B | `modules/ssm/schema.py` |

보류 항목이 많은 영역: SSM(4개), SCDS(3개). A6·A10·A12는 모두 "MSU 챕터 목록이나 확정 캐릭터 목록을 입력으로 받을지"라는 같은 질문이므로, 백엔드와 입력 형식을 한 번에 정하면 함께 풀린다.

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
