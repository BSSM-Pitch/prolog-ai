# prolog-ai

Prolog 서비스의 AI 모듈만 담는 파이썬 패키지입니다. 백엔드(FastAPI)가 이 패키지를 설치해 함수를 호출합니다.

## 설치 방법

```bash
pip install git+https://github.com/BSSM-Pitch/prolog-ai.git
```

## 로컬 개발 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

패키지는 `.env` 파일을 직접 읽지 않는다(환경변수만 본다). 로컬에서 `.env` 값을 쓰려면 셸에 불러온다.

```bash
set -a; source .env; set +a
```

테스트는 실제 API 없이 돈다: `pytest`, `ruff check .`

## 환경변수

| 이름 | 설명 |
| --- | --- |
| `OPENROUTER_API_KEY` | OpenRouter API 키 (`sk-or-v1-…`). LLM은 OpenRouter를 거쳐 DeepSeek 모델을 부른다 |
| `PROLOG_AI_MODEL` | 호출할 OpenRouter 모델 이름. 비우면 `deepseek/deepseek-v4-flash` |
| `USE_FAKE_LLM` | 값이 정확히 `1`이면 API를 부르지 않고 스키마에 맞는 가짜 응답(빈 배열·빈 문자열)을 돌려준다. `true` 등 다른 값은 실제 호출로 처리된다 |

## 공개 함수

`from prolog_ai import run_nlcd, run_rex, run_aiq, run_scds, run_scds_rules, run_scds_analysis, run_ssm`

모든 함수는 **동기 함수**이고, 어떤 입력·오류에도 예외를 던지지 않고 아래 응답 형식 중 하나로 반환한다.
작업 생성·폴링(비동기)과 저장은 백엔드가 맡는다.

| 함수 | 입력 | 성공 시 `data` |
| --- | --- | --- |
| `run_nlcd(source_text)` | 캐릭터 서술 문장 | `personality_tags`, `core_values`, `emotion_keywords` (`[{value, evidence}]`), `influence_relations` (`[{value, type, evidence}]`) |
| `run_rex(manuscript_text)` | 원고 본문 | `extracted_rules` (`[{description, violation_keywords, evidence, source_chapter}]`) |
| `run_aiq(question, manuscript_text, scope="whole", selection_range=None, messages=None)` | 질문, 원고, `whole`/`selection`, `{start, end}` 문자 오프셋, 같은 스레드의 이전 메시지(후속 질문일 때, 시간순 `[{role, content}]`. `role`은 `user`/`assistant`. 그 밖의 필드는 무시. 답변이 없는 `pending`·`failed` 메시지는 빼고 넘긴다) | `content` (답변 문자열) |
| `run_scds_rules(event, world_rules, characters=None)` | 사건 `{character_ids, content}`, WorldRule 목록 `[{rule_id, description, violation_keywords}]`, ASS 확정 캐릭터 목록(선택) | 룰 검출만(LLM 호출 없음). `status`(`skipped`/`no_candidate`/`queued`), `rule_result` |
| `run_scds_analysis(event, rule_result, characters=None)` | 사건, `run_scds_rules`가 준 `rule_result`(SCDS 2.6), ASS 확정 캐릭터 목록(선택) | AI 분석만. `status`(`completed`), `rule_result`, `conflicts` (`[{character_id, conflict_target, severity, advice}]`) |
| `run_scds(event, world_rules, characters=None)` | `run_scds_rules`와 같음 | 룰 검출 + AI 분석을 한 번에. `status`, `rule_result`, 완료 시 `conflicts` |
| `run_ssm(manuscript_text)` | 원고 본문 | `acts`, `nodes`, `edges` (SSM 명세 StructureMap 구조) |

필드 정의는 각 모듈의 `schema.py`와 `docs/specs/claude/api 명세/`를 따른다.

### 응답 형식

성공 (`run_nlcd` 예시, 원문에 없는 근거를 가진 항목 1개가 제거됨):

```json
{
  "data": {
    "personality_tags": [
      {"value": "책임감 강함", "evidence": "책임감이 강하지만"},
      {"value": "자신감 부족", "evidence": "자신감이 부족한"}
    ],
    "core_values": [{"value": "폭력 회피", "evidence": "폭력을 싫어한다"}],
    "influence_relations": [{"value": "벤 삼촌", "type": "영향", "evidence": "벤 삼촌의 영향을 크게 받았으며"}],
    "emotion_keywords": []
  },
  "meta": {"removed_evidence_count": 1}
}
```

실패:

```json
{"error": {"code": "INVALID_INPUT", "message": "source_text가 비어 있습니다.", "details": {"field": "source_text"}}}
```

해당 내용이 없는 카테고리는 에러가 아니라 빈 배열이다.

`meta`에 들어가는 값:

| 키 | 함수 | 의미 |
| --- | --- | --- |
| `removed_evidence_count` | NLCD, REX | 근거가 원문에 없어 제거한 항목 수 |
| `removed_conflict_count` | SCDS | 없는 룰 후보 번호를 가리켜 제거한 충돌 수. AI는 후보 번호만 고르고, `character_id`·`conflict_target`은 패키지가 후보에서 채운다 |
| `removed_edge_count` | SSM | 없는 노드를 가리켜 제거한 연결 수 |

### SCDS 응답

SCDS는 명세의 ConflictCheck처럼 `status`와 `rule_result`를 항상 담는다. 룰 후보가 없거나 참조할 설정이 없으면 LLM을 부르지 않는다.

명세 흐름(SCDS 4.6·4.7·5항)대로 쓰려면 함수를 나눠 부른다.

1. 사건 저장 API(4.6)에서 `run_scds_rules`를 동기로 부르고, `status`·`rule_result`를 그대로 저장·응답한다.
2. `status`가 `queued`면 AI 워커에서 `run_scds_analysis(event, rule_result, characters)`를 부른다.
3. 재시도(4.8)는 저장해 둔 `rule_result`로 `run_scds_analysis`를 다시 부른다.

`run_scds`는 1과 2를 한 번에 하는 함수이고 결과는 두 함수를 차례로 부른 것과 같다.

| `data.status` | 조건 | LLM 호출 |
| --- | --- | --- |
| `skipped` | 세계관 규칙도, 사건 관련 캐릭터 설정도 없음 (`rule_result.skipped_reason: "NO_REFERENCE_DATA"`) | 안 함 |
| `no_candidate` | 룰 검출 후보 없음 | 안 함 |
| `queued` | 후보가 있어 AI 분석이 필요함 (`run_scds_rules`만) | 안 함 |
| `completed` | 후보가 있어 AI 분석 완료. `conflicts` 포함 (`run_scds_analysis`, `run_scds`) | 함 |

완료 예시:

```json
{
  "data": {
    "status": "completed",
    "rule_result": {
      "has_candidate": true, "skipped": false, "skipped_reason": null,
      "candidates": [{"rule_id": "wr_001", "character_id": "char_001", "conflict_target": "폭력 회피", "matched_keyword": "잔혹하게 살해"}]
    },
    "conflicts": [{"character_id": "char_001", "conflict_target": "폭력 회피", "severity": "high", "advice": "현재 캐릭터 설정과 비교했을 때 과도하게 공격적인 행동처럼 보입니다."}]
  },
  "meta": {"removed_conflict_count": 0}
}
```

AI 분석이 실패해도 룰 후보는 `error.details.rule_result`에 남는다(SCDS 4.7 "failed면 후보만 표시"):

```json
{"error": {"code": "AI_ANALYSIS_FAILED", "message": "...", "details": {"rule_result": {"has_candidate": true, "candidates": ["..."]}}}}
```

`characters`에는 ASS `ConfirmedCharacter`를 그대로 넘기면 된다. 사건의 `character_ids`에 있는 캐릭터만 아래 필드 매핑으로 바꿔 AI에 전달한다.

### 에러 코드

| 코드 | HTTP | 발생 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 입력이 비었거나 타입이 틀림, 인자 누락 (전 모듈) |
| `INVALID_SELECTION_RANGE` | 400 | AIQ `scope=selection`인데 범위가 없거나 `0 ≤ start < end ≤ 원고 길이`를 벗어남 |
| `MANUSCRIPT_TOO_SHORT` | 422 | SSM 원고가 비어 있음 |
| `RULE_ENGINE_ERROR` | 500 | SCDS 룰 검출 등 AI 호출 밖에서 예상 못 한 오류 (`run_scds_rules`, `run_scds`) |
| `AI_EXTRACTION_FAILED` / `AI_EXTRACTION_TIMEOUT` | 502 / 503 | NLCD, REX의 AI 실패 / 시간 초과 |
| `AI_RESPONSE_FAILED` / `AI_RESPONSE_TIMEOUT` | 502 / 503 | AIQ의 AI 실패 / 시간 초과 |
| `AI_ANALYSIS_FAILED` / `AI_ANALYSIS_TIMEOUT` | 502 / 503 | SCDS, SSM의 AI 실패 / 시간 초과 |
| `SCHEMA_VALIDATION_FAILED` | 미정 | AI 응답이 스키마와 맞지 않음. 모듈 내부용 코드로 명세에 없으며 HTTP 상태와 노출 방식은 미결정(`WARN.md` A4) |

HTTP 상태는 `prolog_ai.core.errors.HTTP_STATUS`에도 있다. `SCHEMA_VALIDATION_FAILED`는 이 표에 없으므로 `HTTP_STATUS.get(code, 502)`처럼 기본값을 두고 쓴다.

### 백엔드 작업(job) 상태와 연결

명세의 비동기 작업 상태(queued/analyzing 등)는 백엔드가 관리하고, 함수 호출이 끝나면 결과로 최종 상태를 정한다.

| 함수 결과 | 작업 상태 |
| --- | --- |
| `data`가 있음 | `completed` (SCDS는 `data.status` 값을 그대로 사용: `skipped` / `no_candidate` / `queued` / `completed`) |
| `error`가 있음 | `failed`, `error`를 그대로 응답에 싣는다 |

AI 호출 한 번의 시간 제한은 30초이고, 긴 글을 만드는 AIQ 답변과 SCDS 조언은 90초다. AI 재시도는 패키지 안에서 최대 2회 한다(시간 초과·연결 오류·429·5xx만. 인증 오류 등은 바로 실패). 사용자가 누르는 재시도 API는 같은 함수를 다시 호출하면 된다.

인수인계 요약과 알려진 한계는 `docs/handoff.md`, 미해결 문제는 `docs/specs/claude/WARN.md`에 있다.

## NLCD/ASS ↔ SCDS 필드 매핑

ASS `ConfirmedCharacter`(`docs/specs/claude/api 명세/ASS.md` 2.4)와 SCDS `Character`(`docs/specs/claude/api 명세/SCDS.md` 2.1)는
같은 캐릭터를 가리키지만 필드명이 다르다. ASS가 확정·저장을 담당하고 SCDS가 이를 참조하는 관계이므로,
저장 필드명을 하나로 통일하지 않고 `core/mapping.py`에 변환 함수(`map_confirmed_character_to_scds`)를 두어
SCDS가 참조하는 시점에만 변환한다.

| ASS (ConfirmedCharacter) | SCDS (Character) | 비고 |
| --- | --- | --- |
| `personality_tags` (string[]) | `traits` (string[]) | 그대로 매핑 |
| `core_values` (string[]) | `values` (string[]) | 그대로 매핑 |
| `influence_relations[].target` (object[]) | `influences` (string[]) | 대상 이름만 남기고 `type`, `status`는 버림 |
| `emotion_keywords` (string[]) | (대응 필드 없음) | 버리되 개수를 `dropped_emotion_keywords`로 남김 |

**결정 이유**: 세 선택지(ASS를 SCDS에 맞춤 / SCDS에 필드 추가 / 변환 레이어) 중 변환 레이어를 선택했다.
ASS 쪽 필드명을 바꾸면 NLCD 명세와의 정합(4.5 전달 API가 필드명이 같다는 전제로 설계됨)이 깨지고,
SCDS DB에 필드를 추가하면 이 저장소 범위를 벗어난 DB/SCDS API 변경이 필요하다. 변환 레이어는 두 명세를
그대로 두고 이 패키지 안에서만 흡수할 수 있다는 점에서 가장 영향 범위가 작다.

---

## 브랜치 규칙

- `main`에 직접 push 금지
- 브랜치명:
  - 기능 추가/구현: `feat/<모듈>-<내용>`
  - 에러 오류 해결: `fix/<모듈>-<내용>`
  - 문서 작업: `docs/<내용>`
  - 설정 변경 및 기타 업무: `chore/<내용>`
- squash merge

---

## 커밋 컨벤션

```text
<type>: <description>

<path>: <작업 내용>
<path>: <작업 내용>
```

### type

| type       | 설명              |
|------------| --------------- |
| `feat`     | 새로운 기능 추가       |
| `fix`      | 버그 수정           |
| `refactor` | 코드 구조 개선        |
| `docs`     | 문서 수정           |
| `test`     | 테스트 추가 및 수정     |
| `chore`    | 설정, 의존성 등 기타 작업 |
| `style`    | 코드 스타일 및 포맷팅 수정 |
| `perf`     | 성능 개선           |

### 작성 규칙

* 첫 줄에는 작업의 핵심 내용을 간결하게 작성한다.
* 첫 줄과 상세 내용 사이에는 한 줄을 띄운다.
* 상세 내용에는 작업한 파일 또는 디렉터리의 경로와 작업 내용을 작성한다.
* 여러 파일을 수정한 경우 각 파일을 별도의 줄에 작성한다.
* 작업 내용은 무엇을 변경했는지 구체적으로 작성한다.
* 불필요한 내용이나 의미 없는 커밋 메시지는 작성하지 않는다.

### 예시

```text
feat: 사용자 로그인 기능 추가

src/auth/LoginService.java: 로그인 인증 로직 구현
src/auth/LoginController.java: 로그인 API 추가
src/auth/LoginRequest.java: 로그인 요청 DTO 추가
```

```text
fix: 회원가입 중복 검사 오류 수정

src/user/UserService.java: 중복 회원 검사 조건 수정
src/user/UserRepository.java: 사용자 조회 쿼리 수정
```

```text
docs: 프로젝트 실행 문서 수정

README.md: 로컬 개발 환경 설정 방법 추가
docs/api.md: 회원 API 명세 수정
```
