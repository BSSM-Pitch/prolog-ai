**Relationship Change Visualization (RCV) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 관계 변화 시각화 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 관계 변화 시각화 기능 명세서 v0.1 |
| 관련 모듈 | 구조화 저장 엔진, 관계 마인드맵 화면, 하단 타임라인 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> SCDS API 명세서와 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다. RCV는 AI 호출이 없는 순수 CRUD/조회 기반 기능이므로 전체 API가 동기(synchronous)로 동작하도록 설계했습니다.
> 

---

## 1. 공통 사항

### 1.1 Base URL

```
https://api.storyforge.io/v1
```

### 1.2 인증

```
Authorization: Bearer {access_token}
```

### 1.3 공통 응답 포맷

**성공**

```json
{ "data": { }, "meta": { } }
```

**실패**

```json
{
  "error": { "code": "RELATIONSHIP_NOT_FOUND", "message": "해당 관계를 찾을 수 없습니다.", "details": {} }
}
```

### 1.4 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 형식 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `CHARACTER_NOT_FOUND` | 404 | 대상 캐릭터 없음 |
| `RELATIONSHIP_NOT_FOUND` | 404 | 관계 리소스 없음 |
| `HISTORY_ENTRY_NOT_FOUND` | 404 | 해당 챕터의 이력 기록 없음 |
| `EVENT_NOT_FOUND` | 404 | 연결하려는 사건이 존재하지 않음 |
| `DUPLICATE_CHAPTER_RECORD` | 409 | 동일 챕터에 이미 상태 기록이 존재 (11항 예외처리) |
| `CHARACTER_HAS_DEPENDENT_RELATIONSHIPS` | 409 | 삭제하려는 캐릭터에 연결된 관계가 남아있음 |
| `INVALID_CHAPTER_RANGE` | 400 | 챕터 범위 파라미터 오류 (`chapter_from` > `chapter_to`) |

### 1.5 페이지네이션

| 파라미터 | 설명 |
| --- | --- |
| `limit` | 페이지당 항목 수 (기본 20, 최대 100) |
| `cursor` | 다음 페이지 커서 |

---

## 2. 데이터 모델

### 2.1 Relationship (관계)

기능 명세서 9항 데이터 구조 기반.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `relationship_id` | string | Y | 관계 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `source_character_id` | string | Y | 캐릭터 A |
| `target_character_id` | string | Y | 캐릭터 B |
| `history` | `RelationshipHistoryEntry[]` | Y | 챕터별 상태 변화 시계열 (챕터 오름차순) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 수정 시각 |

### 2.2 RelationshipHistoryEntry (관계 이력 항목)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `chapter` | integer | Y | 상태가 기록된 챕터 |
| `state` | string | Y | 관계 상태 (`우호`|`중립`|`긴장`|`갈등`|`적대`|`신뢰` 등, 프로젝트별 정의 세트) |
| `trust` | number | null | N | 신뢰도 등 수치 지표 (RCV-008) |
| `event_id` | string | null | N | 변화를 유발한 사건 ID (RCV-004) |
| `event_deleted` | boolean | N | 연결된 사건이 삭제되어 링크만 해제된 경우 `true` (기본 `false`) |

### 2.3 RelationshipSnapshot (시점 스냅샷 · RCV-007)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `relationship_id` | string | 관계 ID |
| `requested_chapter` | integer | 조회를 요청한 챕터 |
| `resolved_chapter` | integer | 실제로 사용된 이력의 챕터 (기록이 없으면 직전 챕터로 대체, 11항) |
| `state` | string | 해당 시점의 관계 상태 |
| `trust` | number | null | 해당 시점의 신뢰도 |
| `linked_event` | string | null | 연결 사건 ID |
| `is_carried_forward` | boolean | `requested_chapter`에 직접 기록이 없어 이전 값을 이어받았는지 여부 |

### 2.4 MindmapGraph (마인드맵 데이터 · RCV-005)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `chapter` | integer | 조회 기준 챕터 |
| `nodes` | object[] | `[{character_id, name}]` |
| `edges` | object[] | `[{relationship_id, source_character_id, target_character_id, state, trust, linked_event}]` |

### 2.5 TimelineData (타임라인 데이터 · RCV-006)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `relationship_id` | string | 관계 ID |
| `history` | `RelationshipHistoryEntry[]` | 전체 이력 |
| `change_points` | object[] | `[{chapter, from_state, to_state, event_id}]` — 상태가 바뀐 지점만 추출 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 | 관련 기능 ID |
| --- | --- | --- | --- | --- |
| 1 | GET | `/projects/{projectId}/relationships` | 관계 목록 조회 (필터링) | RCV-009 |
| 2 | POST | `/projects/{projectId}/relationships` | 관계 생성 | RCV-001 |
| 3 | GET | `/projects/{projectId}/relationships/{relationshipId}` | 관계 상세 조회 (전체 이력 포함) | RCV-001, RCV-003 |
| 4 | DELETE | `/projects/{projectId}/relationships/{relationshipId}` | 관계 삭제 | RCV-001 |
| 5 | GET | `/projects/{projectId}/relationships/{relationshipId}/history` | 관계 이력(시계열) 조회 | RCV-003 |
| 6 | POST | `/projects/{projectId}/relationships/{relationshipId}/history` | 특정 챕터 상태 기록 추가 | RCV-002, RCV-004 |
| 7 | PATCH | `/projects/{projectId}/relationships/{relationshipId}/history/{chapter}` | 특정 챕터 이력 수정 | RCV-003, RCV-004 |
| 8 | DELETE | `/projects/{projectId}/relationships/{relationshipId}/history/{chapter}` | 특정 챕터 이력 삭제 | RCV-003 |
| 9 | GET | `/projects/{projectId}/relationships/{relationshipId}/snapshot` | 특정 챕터 시점 스냅샷 조회 | RCV-007 |
| 10 | GET | `/projects/{projectId}/relationship-mindmap` | 챕터 시점 기준 마인드맵(노드-엣지) 조회 | RCV-005 |
| 11 | GET | `/projects/{projectId}/relationships/{relationshipId}/timeline` | 타임라인 데이터(변화 지점 포함) 조회 | RCV-006 |
| 12 | GET | `/projects/{projectId}/relationships/{relationshipId}/metrics` | 수치 지표(신뢰도 등) 시계열 조회 | RCV-008 (선택) |
| 13 | GET | `/projects/{projectId}/characters/{characterId}/relationships` | 특정 캐릭터의 연결 관계 목록 (삭제 전 확인용) | 11항 예외처리 |

---

## 4. 엔드포인트 상세 명세

### 4.1 관계 목록 조회

`GET /projects/{projectId}/relationships`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `character_id` | string | N | 특정 캐릭터가 포함된 관계만 필터링 |
| `state` | string | N | 현재(최신) 상태 기준 필터링 |
| `chapter_from`, `chapter_to` | integer | N | 이력이 해당 챕터 범위 내에 존재하는 관계만 필터링 |
| `limit`, `cursor` | - | N | 페이지네이션 |

**Response 200**

```json
{
  "data": [
    {
      "relationship_id": "rel_001",
      "source_character_id": "char_001",
      "target_character_id": "char_002",
      "history": [
        { "chapter": 1, "state": "우호", "trust": 80, "event_id": "evt_010" },
        { "chapter": 20, "state": "긴장", "trust": 40, "event_id": "evt_112" },
        { "chapter": 35, "state": "갈등", "trust": 10, "event_id": "evt_233" }
      ]
    }
  ],
  "meta": { "next_cursor": null }
}
```

### 4.2 관계 생성

`POST /projects/{projectId}/relationships`

두 캐릭터 사이에 관계를 생성한다. 최초 상태(챕터 1 이상)를 함께 입력한다.

**Request Body**

```json
{
  "source_character_id": "char_001",
  "target_character_id": "char_002",
  "initial_history": { "chapter": 1, "state": "우호", "trust": 80, "event_id": "evt_010" }
}
```

**Response 201**: 생성된 `Relationship` 객체 · **Response 400**: `source_character_id`와 `target_character_id`가 동일한 경우 `INVALID_INPUT`

### 4.3 관계 상세 조회

`GET /projects/{projectId}/relationships/{relationshipId}`

**Response 200**: `Relationship` 객체 (전체 `history` 포함) · **Response 404**: `RELATIONSHIP_NOT_FOUND`

### 4.4 관계 삭제

`DELETE /projects/{projectId}/relationships/{relationshipId}`

**Response 204**: 삭제 성공 (본문 없음) · **비고**: 이력 전체가 함께 삭제된다. 마인드맵/타임라인에서 즉시 제외된다.

### 4.5 관계 이력(시계열) 조회

`GET /projects/{projectId}/relationships/{relationshipId}/history`

**Query Parameters**: `chapter_from`, `chapter_to`

**Response 200**

```json
{
  "data": [
    { "chapter": 1, "state": "우호", "trust": 80, "event_id": "evt_010", "event_deleted": false },
    { "chapter": 20, "state": "긴장", "trust": 40, "event_id": "evt_112", "event_deleted": false },
    { "chapter": 35, "state": "갈등", "trust": 10, "event_id": "evt_233", "event_deleted": false }
  ]
}
```

### 4.6 특정 챕터 상태 기록 추가

`POST /projects/{projectId}/relationships/{relationshipId}/history`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `overwrite` | boolean | N | 동일 챕터에 이미 기록이 있을 때 덮어쓸지 여부 (기본 `false`) |

**Request Body**

```json
{ "chapter": 20, "state": "긴장", "trust": 40, "event_id": "evt_112" }
```

**Response 201**: 추가된 `RelationshipHistoryEntry`

**Response 409 — 동일 챕터 중복 기록 (`overwrite=false`, 11항 예외처리)**

```json
{
  "error": {
    "code": "DUPLICATE_CHAPTER_RECORD",
    "message": "해당 챕터에 이미 관계 상태 기록이 존재합니다. overwrite=true로 재요청하면 최신 입력으로 갱신됩니다.",
    "details": { "existing_entry": { "chapter": 20, "state": "긴장", "trust": 45, "event_id": "evt_100" } }
  }
}
```

### 4.7 특정 챕터 이력 수정

`PATCH /projects/{projectId}/relationships/{relationshipId}/history/{chapter}`

**Request Body** (일부 필드만 전송 가능)

```json
{ "state": "갈등", "trust": 15 }
```

**Response 200**: 수정된 `RelationshipHistoryEntry` · **Response 404**: `HISTORY_ENTRY_NOT_FOUND`

### 4.8 특정 챕터 이력 삭제

`DELETE /projects/{projectId}/relationships/{relationshipId}/history/{chapter}`

**Response 204** · **비고**: 남은 이력이 1개일 경우에도 삭제는 허용되며(11항, 이력 1개 = 단일 상태로 표시), 이력이 0개가 되면 관계는 "상태 미정" 상태로 취급된다.

### 4.9 특정 챕터 시점 스냅샷 조회

`GET /projects/{projectId}/relationships/{relationshipId}/snapshot`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `chapter` | integer | Y | 조회할 챕터 시점 |

**Response 200 — 해당 챕터에 직접 기록이 있는 경우**

```json
{
  "data": {
    "relationship_id": "rel_001",
    "requested_chapter": 20,
    "resolved_chapter": 20,
    "state": "긴장",
    "trust": 40,
    "linked_event": "evt_112",
    "is_carried_forward": false
  }
}
```

**Response 200 — 기록이 없어 직전 챕터 값을 이어받는 경우 (11항 예외처리)**

```json
{
  "data": {
    "relationship_id": "rel_001",
    "requested_chapter": 27,
    "resolved_chapter": 20,
    "state": "긴장",
    "trust": 40,
    "linked_event": "evt_112",
    "is_carried_forward": true
  }
}
```

### 4.10 마인드맵 조회

`GET /projects/{projectId}/relationship-mindmap`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `chapter` | integer | Y | 시각화 기준 챕터 시점 |
| `character_id` | string | N | 특정 캐릭터 중심으로 필터링 |

**Response 200**

```json
{
  "data": {
    "chapter": 20,
    "nodes": [
      { "character_id": "char_001", "name": "피터 파커" },
      { "character_id": "char_002", "name": "메리 제인" }
    ],
    "edges": [
      {
        "relationship_id": "rel_001",
        "source_character_id": "char_001",
        "target_character_id": "char_002",
        "state": "긴장",
        "trust": 40,
        "linked_event": "evt_112"
      }
    ]
  }
}
```

**비고**: 각 엣지의 `state`/`trust`는 4.9의 스냅샷 로직(직전 챕터 이어받기 포함)으로 계산된다. 클라이언트는 챕터 슬라이더 이동 시 이 API를 재호출하여 타임라인과 동기화한다(13항 비기능 요구사항).

### 4.11 타임라인 조회

`GET /projects/{projectId}/relationships/{relationshipId}/timeline`

**Response 200**

```json
{
  "data": {
    "relationship_id": "rel_001",
    "history": [
      { "chapter": 1, "state": "우호", "trust": 80, "event_id": "evt_010" },
      { "chapter": 20, "state": "긴장", "trust": 40, "event_id": "evt_112" },
      { "chapter": 35, "state": "갈등", "trust": 10, "event_id": "evt_233" }
    ],
    "change_points": [
      { "chapter": 20, "from_state": "우호", "to_state": "긴장", "event_id": "evt_112" },
      { "chapter": 35, "from_state": "긴장", "to_state": "갈등", "event_id": "evt_233" }
    ]
  }
}
```

### 4.12 관계 지표 시계열 조회 (선택 기능 · RCV-008)

`GET /projects/{projectId}/relationships/{relationshipId}/metrics`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `metric` | string | Y | 조회할 지표명 (예: `trust`) |

**Response 200**

```json
{
  "data": {
    "metric": "trust",
    "series": [
      { "chapter": 1, "value": 80 },
      { "chapter": 20, "value": 40 },
      { "chapter": 35, "value": 10 }
    ]
  }
}
```

### 4.13 캐릭터의 연결 관계 목록 (삭제 전 확인용)

`GET /projects/{projectId}/characters/{characterId}/relationships`

캐릭터 삭제 API(캐릭터 카드 도메인)를 호출하기 전, 종속된 관계가 있는지 확인하기 위한 조회용 API(11항 "캐릭터 삭제 시" 예외처리 지원).

**Response 200**

```json
{
  "data": [
    { "relationship_id": "rel_001", "target_character_id": "char_002", "latest_state": "갈등" }
  ]
}
```

**연계 동작**: 캐릭터 삭제 API는 이 목록이 비어있지 않으면 기본적으로 `409 CHARACTER_HAS_DEPENDENT_RELATIONSHIPS`를 반환하고, 클라이언트가 `cascade=true`로 재요청하거나 사용자 확인 후 관계를 먼저 정리하도록 안내한다(캐릭터 삭제 API 자체는 이 문서의 범위 밖이며, 여기서는 확인용 조회만 제공한다).

---

## 5. 처리 흐름 — API 매핑

| 기능 명세서 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 관계 생성·초기 상태 입력 | 사용자 | `POST /relationships` |
| 2단계: 챕터별 상태 변화 기록 + 사건 연결 | 사용자 | `POST /relationships/{id}/history`, `PATCH /relationships/{id}/history/{chapter}` |
| 3단계: 시계열 저장 | 시스템 | 위 API 처리 결과가 `Relationship.history`에 반영 |
| 4단계: 마인드맵·타임라인 시각화 | 시스템 | `GET /relationship-mindmap`, `GET /relationships/{id}/timeline` |
| 5단계: 챕터 슬라이더로 시점 탐색 | 사용자 | `GET /relationship-mindmap?chapter=N`, `GET /relationships/{id}/snapshot?chapter=N` (슬라이더 이동마다 재호출) |

**시퀀스 요약**

```
[사용자] POST /relationships (관계 생성 + 초기 상태)
      │
      ▼
[사용자] POST /relationships/{id}/history (챕터마다 상태 기록, 사건 연결)
      │
      ▼
[서버] history 시계열에 반영 (동일 챕터 중복 시 overwrite 정책 적용)
      │
      ▼
[클라이언트] GET /relationship-mindmap?chapter=N  ─┐
[클라이언트] GET /relationships/{id}/timeline      ├─ 동기화된 시각화
      │                                             ┘
      ▼
[사용자] 챕터 슬라이더 이동 → GET .../snapshot?chapter=N 재호출 → 마인드맵 갱신
```

---

## 6. 부록 — 예시 시나리오 (피터 파커 / 메리 제인 케이스)

기능 명세서 9항 예시를 API 호출 순서로 재구성.

1. **관계 생성** `POST /projects/proj_1/relationships`

```json
{ "source_character_id": "char_001", "target_character_id": "char_002",
  "initial_history": { "chapter": 1, "state": "우호", "trust": 80, "event_id": "evt_010" } }
```

→ `relationship_id: rel_001`

1. **20챕터 관계 악화 기록** `POST /projects/proj_1/relationships/rel_001/history`

```json
{ "chapter": 20, "state": "긴장", "trust": 40, "event_id": "evt_112" }
```

1. **35챕터 갈등 기록** `POST /projects/proj_1/relationships/rel_001/history`

```json
{ "chapter": 35, "state": "갈등", "trust": 10, "event_id": "evt_233" }
```

1. **27챕터 시점 조회 (기록 없음 → 직전 값 이어받기)** `GET /projects/proj_1/relationships/rel_001/snapshot?chapter=27` → `resolved_chapter: 20`, `state: "긴장"`, `is_carried_forward: true`
2. **마인드맵 조회 (20챕터 시점)** `GET /projects/proj_1/relationship-mindmap?chapter=20` → `char_001` ↔ `char_002` 엣지 상태 `"긴장"`
3. **타임라인 조회로 변화 지점 확인** `GET /projects/proj_1/relationships/rel_001/timeline` → `change_points: [{chapter:20, 우호→긴장}, {chapter:35, 긴장→갈등}]`

---

## 7. 향후 확장 고려사항 (기능 명세서 14항 연계)

| 확장 항목 | API 영향 |
| --- | --- |
| 설정 충돌 감지 시스템 연계 (관계 일관성 검사) | SCDS의 `RULE-03` 검출 시 이 API의 `GET /relationships/{id}/snapshot`을 참조 데이터로 호출하는 내부 연동 필요 |
| 복선 추적 시스템 연계 | `RelationshipHistoryEntry`에 `foreshadowing_id` 참조 필드 추가 가능성 |
| 관계 변화 통계·요약 리포트 | `GET /projects/{projectId}/relationships/summary` 형태의 집계 API 추가 가능성 |
| 다중 캐릭터 관계 패턴(삼각관계) 분석 | 그래프 분석 결과를 반환하는 `GET /projects/{projectId}/relationship-patterns` 신규 엔드포인트 필요 |