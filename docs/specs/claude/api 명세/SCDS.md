# 설정 충돌 감지 시스템 API 명세 (SCDS)

**Setting Conflict Detection System (SCDS) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 설정 충돌 감지 시스템 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 설정 충돌 감지 시스템 기능 명세서 v0.1 |
| 관련 모듈 | 구조화 저장 엔진, AI 디렉터 패널, 타임라인 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 이 문서는 기능 명세서(SCDS-001~007)에 정의된 동작을 REST API로 구현하기 위한 명세입니다. 아래 항목은 기능 명세서에 명시되지 않아 합리적으로 가정한 사항이며, 실제 구현 시 팀 컨벤션에 맞춰 조정이 필요합니다.
> 
- API 스타일: REST + JSON
- 인증 방식: Bearer Token (JWT)
- AI 분석은 지연 가능성이 있으므로 **비동기(작업 생성 → 폴링)** 방식으로 설계 (룰 기반 검출은 기능 명세서 14항 성능 요구사항에 따라 동기 처리)

---

## 1. 공통 사항

### 1.1 Base URL

```
https://api.storyforge.io/v1
```

### 1.2 인증

모든 요청은 `Authorization` 헤더에 Bearer Token을 포함해야 한다.

```
Authorization: Bearer {access_token}
```

### 1.3 공통 요청 헤더

| 헤더 | 필수 | 설명 |
| --- | --- | --- |
| `Authorization` | Y | Bearer 액세스 토큰 |
| `Content-Type` | Y (POST/PUT/PATCH) | `application/json` |
| `X-Project-Id` | N | 프로젝트 ID를 헤더로 전달할 경우 사용 (경로 파라미터와 중복 시 경로 우선) |

### 1.4 공통 응답 포맷

**성공**

```json
{
  "data": { },
  "meta": { }
}
```

**실패**

```json
{
  "error": {
    "code": "CONFLICT_NOT_FOUND",
    "message": "해당 충돌 항목을 찾을 수 없습니다.",
    "details": {}
  }
}
```

### 1.5 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 형식 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `CHARACTER_NOT_FOUND` | 404 | 캐릭터 리소스 없음 |
| `EVENT_NOT_FOUND` | 404 | 사건(입력) 리소스 없음 |
| `CONFLICT_CHECK_NOT_FOUND` | 404 | 충돌 검사 작업(job) 없음 |
| `CONFLICT_NOT_FOUND` | 404 | 충돌(조언) 리소스 없음 |
| `INVALID_STATUS_TRANSITION` | 409 | 이미 처리된 충돌에 대한 중복 처리 요청 |
| `RULE_ENGINE_ERROR` | 500 | 룰 기반 필터링 처리 중 서버 오류 |
| `AI_ANALYSIS_FAILED` | 502 | AI 분석 호출 실패 |
| `AI_ANALYSIS_TIMEOUT` | 503 | AI 분석 응답 지연 |

### 1.6 페이지네이션

목록 조회 API는 커서 기반 페이지네이션을 사용한다.

| 파라미터 | 설명 |
| --- | --- |
| `limit` | 페이지당 항목 수 (기본 20, 최대 100) |
| `cursor` | 다음 페이지 조회를 위한 커서 값 |

응답의 `meta`에 `next_cursor`가 포함된다.

---

## 2. 데이터 모델

### 2.1 Character (캐릭터 설정)

기능 명세서 9항 데이터 구조 기반.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `character_id` | string | Y | 캐릭터 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `name` | string | Y | 캐릭터 이름 |
| `traits` | string[] | N | 성격 특성 목록 |
| `values` | string[] | N | 가치관 목록 (충돌 판단 기준) |
| `influences` | string[] | N | 캐릭터에게 영향을 준 인물/사건 |
| `status` | string | N | `alive` | `deceased` | `removed` (RULE-04 판단 기준) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 수정 시각 |

### 2.2 WorldRule (세계관 규칙)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `rule_id` | string | Y | 규칙 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `title` | string | Y | 규칙 제목, 최대 200자 (DB `world_rules.title` NOT NULL) |
| `description` | string | Y | 규칙 설명 |
| `violation_keywords` | string[] | N | RULE-02 판정에 사용되는 위반 키워드 |

### 2.3 Relationship (관계 데이터)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `relationship_id` | string | Y | 관계 고유 ID |
| `character_a_id` | string | Y | 캐릭터 A |
| `character_b_id` | string | Y | 캐릭터 B |
| `state` | string | Y | 현재 관계 상태 (예: `ally`, `enemy`, `family`) |
| `history` | object[] | N | 관계 변화 이력 `[{state, chapter, changed_at}]` |

### 2.4 Event (신규 입력/사건)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `event_id` | string | Y | 사건 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `chapter` | integer | Y | 발생 챕터 |
| `character_ids` | string[] | Y | 관련 캐릭터 ID 목록 |
| `content` | string | Y | 사건/행동 내용 (자연어) |
| `created_at` | string(ISO8601) | Y | 저장 시각 |

### 2.5 ConflictCheck (충돌 검사 작업)

룰 기반 검출 결과 + AI 분석 진행 상태를 담는 작업(job) 단위.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `check_id` | string | Y | 검사 작업 고유 ID |
| `event_id` | string | Y | 대상 사건 ID |
| `rule_result` | object | Y | 룰 기반 필터링 결과 (2.6 참고) |
| `status` | string | Y | `skipped` | `queued` | `running` | `completed` | `failed` (DB `ops.jobs.status`). 룰 검출 후보가 없을 때도 `skipped`이며, 참조 데이터가 없어 건너뛴 경우(`rule_result.skipped: true`)와 후보가 없는 경우(`rule_result.skipped: false`, `has_candidate: false`)는 `rule_result`로 구분한다 |
| `conflict_ids` | string[] | N | 분석 완료 후 생성된 충돌(Conflict) ID 목록 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.6 RuleResult (룰 기반 필터링 결과)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `has_candidate` | boolean | 충돌 후보 존재 여부 |
| `skipped` | boolean | 참조할 기존 설정 데이터가 없어 검사를 생략했는지 여부 |
| `skipped_reason` | string | null | `NO_REFERENCE_DATA` 등 |
| `candidates` | object[] | `[{rule_id, character_id, conflict_target, matched_keyword}]` |

### 2.7 Conflict (충돌 감지 결과 / 조언)

기능 명세서 9항 데이터 구조 기반.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `conflict_id` | string | Y | 충돌 고유 ID |
| `check_id` | string | Y | 발생 근거가 된 충돌 검사 작업 ID |
| `character_id` | string | Y | 대상 캐릭터 ID |
| `chapter` | integer | Y | 발생 챕터 |
| `conflict_target` | string | Y | 충돌이 발생한 설정 항목 (예: "폭력 회피") |
| `input_event` | string | Y | 충돌을 유발한 신규 입력 내용 |
| `severity` | string | Y | `low` | `medium` | `high` |
| `advice` | string | Y | AI가 생성한 조언 문장 |
| `related_chapter_ref` | object | N | `{chapter, anchor}` 관련 설정이 정의된 챕터 참조 |
| `status` | string | Y | `open`(검토 대기) | `accepted` | `ignored` | `modified` (DB `conflicts_status_chk`) |
| `modified_content` | string | null | N | 사용자가 `modified` 처리 시 입력한 수정 내용 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `resolved_at` | string(ISO8601) | null | N | 사용자 처리 시각 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 | 관련 기능 ID |
| --- | --- | --- | --- | --- |
| 1 | GET | `/projects/{projectId}/characters` | 캐릭터 목록 조회 | SCDS-001 |
| 2 | GET | `/projects/{projectId}/characters/{characterId}` | 캐릭터 상세 조회 | SCDS-001 |
| 3 | PUT | `/projects/{projectId}/characters/{characterId}` | 캐릭터 설정 갱신 | SCDS-001 |
| 4 | GET | `/projects/{projectId}/world-rules` | 세계관 규칙 목록 조회 | SCDS-001 |
| 5 | GET | `/projects/{projectId}/relationships` | 관계 데이터 목록 조회 | SCDS-001 |
| 6 | POST | `/projects/{projectId}/chapters/{chapterId}/events` | 신규 사건 입력 저장 + 룰 기반 후보 검출(즉시) | SCDS-001, SCDS-002 |
| 7 | GET | `/projects/{projectId}/conflict-checks/{checkId}` | 충돌 검사 작업 상태/결과 조회 (AI 분석 폴링) | SCDS-003 |
| 8 | POST | `/projects/{projectId}/conflict-checks/{checkId}/retry` | AI 분석 재시도 | SCDS-003, 예외처리 |
| 9 | GET | `/projects/{projectId}/conflicts` | 충돌(조언) 목록 조회 — AI 디렉터 패널 | SCDS-004 |
| 10 | GET | `/projects/{projectId}/conflicts/{conflictId}` | 충돌 상세 조회 | SCDS-004 |
| 11 | PATCH | `/projects/{projectId}/conflicts/{conflictId}` | 사용자 처리(수용/무시/수정) | SCDS-005 |
| 12 | GET | `/projects/{projectId}/conflicts/history` | 충돌 이력 조회 | SCDS-006 (선택) |
| 13 | POST | `/projects/{projectId}/chapters/{chapterId}/rescan` | 챕터 단위 재검사 실행 | SCDS-007 (선택) |

---

## 4. 엔드포인트 상세 명세

### 4.1 캐릭터 목록 조회

`GET /projects/{projectId}/characters`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `limit`, `cursor` | - | N | 페이지네이션 |

**Response 200**

```json
{
  "data": [
    {
      "character_id": "char_001",
      "name": "피터 파커",
      "traits": ["책임감 강함", "자신감 부족"],
      "values": ["폭력 회피", "책임 중시"],
      "influences": ["벤 삼촌"],
      "status": "alive"
    }
  ],
  "meta": { "next_cursor": null }
}
```

### 4.2 캐릭터 상세 조회

`GET /projects/{projectId}/characters/{characterId}`

**Response 200**: `Character` 객체 1건 · **Response 404**: `CHARACTER_NOT_FOUND`

### 4.3 캐릭터 설정 갱신

`PUT /projects/{projectId}/characters/{characterId}`

**Request Body**

```json
{
  "traits": ["책임감 강함", "자신감 부족"],
  "values": ["폭력 회피", "책임 중시"],
  "influences": ["벤 삼촌"],
  "status": "alive"
}
```

**Response 200**: 갱신된 `Character` 객체 · **비고**: 이 API는 구조화 저장 엔진에 반영되며, 이후 신규 입력 시 룰 기반 검출의 기준 데이터로 사용된다.

### 4.4 세계관 규칙 목록 조회

`GET /projects/{projectId}/world-rules`

**Response 200**

```json
{
  "data": [
    { "rule_id": "wr_001", "title": "계약 마법", "description": "마법은 계약 없이 발현될 수 없다", "violation_keywords": ["즉흥 마법", "무계약 시전"] }
  ]
}
```

### 4.5 관계 데이터 목록 조회

`GET /projects/{projectId}/relationships`

**Query Parameters**: `character_id` (특정 캐릭터 관련 관계만 필터링)

**Response 200**

```json
{
  "data": [
    {
      "relationship_id": "rel_001",
      "character_a_id": "char_001",
      "character_b_id": "char_002",
      "state": "ally",
      "history": [{ "state": "enemy", "chapter": 5, "changed_at": "2026-01-10T00:00:00Z" }]
    }
  ]
}
```

### 4.6 신규 사건 입력 저장 (핵심 트리거)

`POST /projects/{projectId}/chapters/{chapterId}/events`

새로 작성된 사건/캐릭터 변경 내용을 구조화 저장하고, **저장 시점에 즉시** 룰 기반 충돌 후보 검출을 수행한다(비기능 요구사항 14항). 후보가 없으면 AI를 호출하지 않고 종료하며, 후보가 있으면 AI 분석 작업을 비동기로 생성한다.

**Request Body**

```json
{
  "character_ids": ["char_001"],
  "content": "강도를 잔혹하게 살해함"
}
```

**Response 201 — 후보 없음 (AI 미호출)**

```json
{
  "data": {
    "event": { "event_id": "evt_501", "chapter": 35, "character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함" },
    "conflict_check": {
      "check_id": "chk_9001",
      "status": "skipped",
      "rule_result": { "has_candidate": false, "skipped": false, "skipped_reason": null, "candidates": [] }
    }
  }
}
```

**Response 201 — 후보 있음 (AI 분석 작업 생성됨)**

```json
{
  "data": {
    "event": { "event_id": "evt_501", "chapter": 35, "character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함" },
    "conflict_check": {
      "check_id": "chk_9002",
      "status": "queued",
      "rule_result": {
        "has_candidate": true,
        "skipped": false,
        "skipped_reason": null,
        "candidates": [
          { "rule_id": "RULE-01", "character_id": "char_001", "conflict_target": "폭력 회피", "matched_keyword": "잔혹하게 살해" }
        ]
      }
    }
  }
}
```

**Response 201 — 참조할 기존 설정 없음 (검사 생략)**

```json
{
  "data": {
    "event": { "event_id": "evt_502", "chapter": 35, "character_ids": ["char_010"], "content": "..." },
    "conflict_check": {
      "check_id": "chk_9003",
      "status": "skipped",
      "rule_result": { "has_candidate": false, "skipped": true, "skipped_reason": "NO_REFERENCE_DATA", "candidates": [] }
    }
  }
}
```

**클라이언트 처리**: `status`가 `queued`인 경우, 4.7 API를 폴링하여 AI 분석 완료를 확인한다.

### 4.7 충돌 검사 작업 상태/결과 조회

`GET /projects/{projectId}/conflict-checks/{checkId}`

**Response 200 — 분석 중**

```json
{ "data": { "check_id": "chk_9002", "status": "running", "conflict_ids": [] } }
```

**Response 200 — 완료**

```json
{
  "data": {
    "check_id": "chk_9002",
    "status": "completed",
    "conflict_ids": ["conf_1024"]
  }
}
```

**Response 200 — 실패**

```json
{
  "data": { "check_id": "chk_9002", "status": "failed", "conflict_ids": [] },
  "error": { "code": "AI_ANALYSIS_FAILED", "message": "AI 응답 시간이 초과되었습니다.", "details": {} }
}
```

**비고**: `failed` 상태에서는 후보(candidate)만 표시되고 조언은 생성되지 않는다(기능 명세서 12항 예외 처리). 클라이언트는 4.8 재시도 API를 호출할 수 있다.

### 4.8 AI 분석 재시도

`POST /projects/{projectId}/conflict-checks/{checkId}/retry`

**Response 202**

```json
{ "data": { "check_id": "chk_9002", "status": "queued" } }
```

**Response 409**: 이미 `completed` 상태인 작업에 대한 재시도 요청 시 `INVALID_STATUS_TRANSITION`

### 4.9 충돌(조언) 목록 조회

`GET /projects/{projectId}/conflicts`

AI 디렉터 패널에서 사용하는 조회 API.

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `status` | string | N | `open` | `accepted` | `ignored` | `modified` |
| `chapter` | integer | N | 챕터 필터 |
| `character_id` | string | N | 캐릭터 필터 |
| `severity` | string | N | `low` | `medium` | `high` |

**Response 200**

```json
{
  "data": [
    {
      "conflict_id": "conf_1024",
      "character_id": "char_001",
      "chapter": 35,
      "conflict_target": "폭력 회피",
      "input_event": "강도를 잔혹하게 살해함",
      "severity": "high",
      "advice": "현재 캐릭터 설정과 비교했을 때 과도하게 공격적인 행동처럼 보입니다. 분노 끝에 멈추는 방향도 고려할 수 있습니다.",
      "related_chapter_ref": { "chapter": 12, "anchor": "char_001_values_defined" },
      "status": "open"
    }
  ],
  "meta": { "next_cursor": null }
}
```

### 4.10 충돌 상세 조회

`GET /projects/{projectId}/conflicts/{conflictId}`

**Response 200**: `Conflict` 객체 1건 · **Response 404**: `CONFLICT_NOT_FOUND`

### 4.11 사용자 처리 액션 (수용/무시/수정)

`PATCH /projects/{projectId}/conflicts/{conflictId}`

**Request Body — 수용**

```json
{ "action": "accepted" }
```

**Request Body — 무시**

```json
{ "action": "ignored" }
```

**Request Body — 수정**

```json
{ "action": "modified", "modified_content": "분노 끝에 강도를 제압하되 살해하지는 않음" }
```

**Response 200**

```json
{
  "data": {
    "conflict_id": "conf_1024",
    "status": "modified",
    "modified_content": "분노 끝에 강도를 제압하되 살해하지는 않음",
    "resolved_at": "2026-08-27T09:00:00Z"
  }
}
```

**Response 409**: 이미 처리된 충돌에 재처리 요청 시 `INVALID_STATUS_TRANSITION`

**비고**: `ignored` 처리된 충돌은 동일한 억제 키 `sha256(character_id : rule_id : normalize(사건 description))`(DB `conflicts.suppression_key`, `conflict_suppressions`)에 대해 이후 룰 검출 단계에서 재감지되지 않도록 구조화 저장 엔진이 억제 처리한다(기능 명세서 12항).

### 4.12 충돌 이력 조회 (선택 기능 · SCDS-006)

`GET /projects/{projectId}/conflicts/history`

**Query Parameters**: `character_id`, `chapter_from`, `chapter_to`

**Response 200**

```json
{
  "data": [
    { "conflict_id": "conf_1020", "status": "accepted", "resolved_at": "2026-08-20T10:00:00Z" },
    { "conflict_id": "conf_1024", "status": "modified", "resolved_at": "2026-08-27T09:00:00Z" }
  ]
}
```

### 4.13 챕터 단위 재검사 (선택 기능 · SCDS-007)

`POST /projects/{projectId}/chapters/{chapterId}/rescan`

특정 챕터 저장 시 관련 설정에 한해 룰 기반 재검사를 수행한다.

**Response 202**

```json
{
  "data": {
    "rescan_id": "rescan_301",
    "chapter": 35,
    "status": "queued",
    "affected_check_ids": []
  }
}
```

---

## 5. 처리 흐름 — API 매핑

| 기능 명세서 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 구조화 저장 | 시스템 | `PUT /characters/{id}`, `POST /chapters/{chapterId}/events` |
| 2단계: 룰 기반 후보 검출 | 시스템(룰 엔진) | `POST /chapters/{chapterId}/events` 응답의 `conflict_check.rule_result` |
| 3단계: 선택적 AI 분석 | AI | `GET /conflict-checks/{checkId}` 폴링 (후보 있을 때만 생성됨) |
| 4단계: 조언 출력 → 사용자 처리 | 시스템 → 사용자 | `GET /conflicts`, `PATCH /conflicts/{conflictId}` |

**시퀀스 요약**

```
[클라이언트] POST /events
      │
      ▼
[서버] 구조화 저장 + 룰 필터링 (동기, 즉시 응답)
      │
      ├─ has_candidate=false → 종료 (AI 미호출)
      │
      └─ has_candidate=true → conflict_check(status=queued) 생성
                 │
                 ▼
        [AI 워커] 비동기 분석 수행
                 │
                 ▼
        conflict_check.status = completed
        Conflict 레코드 생성 (status=open)
                 │
                 ▼
[클라이언트] GET /conflict-checks/{id} 폴링 → completed 확인
      │
      ▼
[클라이언트] GET /conflicts → AI 디렉터 패널에 조언 표시
      │
      ▼
[클라이언트] PATCH /conflicts/{id} (accepted/ignored/modified)
```

---

## 6. 부록 — 예시 시나리오 (피터 파커 케이스)

기능 명세서 9, 11항의 예시를 API 호출 순서로 재구성한 예시.

1. **캐릭터 설정 확인** `GET /projects/proj_1/characters/char_001` → `values: ["폭력 회피", "책임 중시"]` 확인
2. **35챕터에 신규 사건 입력** `POST /projects/proj_1/chapters/35/events`

```json
{ "character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함" }
```

→ `RULE-01` 매칭, `conflict_check.status = "queued"` (`check_id: chk_9002`)

1. **AI 분석 결과 폴링** `GET /projects/proj_1/conflict-checks/chk_9002` → `status: "completed"`, `conflict_ids: ["conf_1024"]`
2. **AI 디렉터 패널에 조언 표시** `GET /projects/proj_1/conflicts?status=open&chapter=35` → `advice: "현재 캐릭터 설정과 비교했을 때 과도하게 공격적인 행동처럼 보입니다. 분노 끝에 멈추는 방향도 고려할 수 있습니다."`
3. **사용자가 "수정"으로 처리** `PATCH /projects/proj_1/conflicts/conf_1024`

```json
{ "action": "modified", "modified_content": "분노 끝에 강도를 제압하되 살해하지는 않음" }
```

---

##