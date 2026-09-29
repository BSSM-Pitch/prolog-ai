**Foreshadowing Tracking System (FTS) API Specification**

| 항목          | 내용                                            |
| ------------- | ----------------------------------------------- |
| 문서명        | 복선 추적 시스템 API 명세서                     |
| 소속 프로젝트 | StoryForge                                      |
| 근거 문서     | 복선 추적 시스템 기능 명세서 v0.1               |
| 관련 모듈     | 구조화 저장 엔진, AI 디렉터 패널, 하단 타임라인 |
| 문서 버전     | v0.1 (Draft)                                    |
| 상태          | 작성 중                                         |

> SCDS·RCV API 명세서와 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다. FTS는 자동 판정·AI 호출이 없는 사용자 주도 기록 기능이므로, "미회수 안내"(FTS-006) 역시 AI 호출이 아닌 **결정론적 템플릿 생성**으로 설계했습니다.

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
{ "data": {}, "meta": {} }
```

**실패**

```json
{
  "error": {
    "code": "FORESHADOWING_NOT_FOUND",
    "message": "해당 복선을 찾을 수 없습니다.",
    "details": {}
  }
}
```

### 1.4 공통 에러 코드

| 코드                       | HTTP 상태 | 설명                                                |
| -------------------------- | --------- | --------------------------------------------------- |
| `INVALID_INPUT`            | 400       | 요청 본문/파라미터 형식 오류                        |
| `UNAUTHORIZED`             | 401       | 인증 토큰 없음/만료                                 |
| `FORBIDDEN`                | 403       | 프로젝트 접근 권한 없음                             |
| `FORESHADOWING_NOT_FOUND`  | 404       | 복선 리소스 없음                                    |
| `LINKED_CHAPTER_NOT_FOUND` | 404       | 삭제하려는 연결 챕터가 존재하지 않음                |
| `LINK_TARGET_NOT_FOUND`    | 404       | 연결하려는 사건/캐릭터가 존재하지 않음              |
| `INVALID_PAYOFF_CHAPTER`   | 400       | 회수 챕터가 설치 챕터보다 앞선 경우 (12항 예외처리) |
| `PAYOFF_NOT_SET`           | 409       | 회수되지 않은 복선에 회수 취소를 요청한 경우        |

### 1.5 페이지네이션

| 파라미터 | 설명                                 |
| -------- | ------------------------------------ |
| `limit`  | 페이지당 항목 수 (기본 20, 최대 100) |
| `cursor` | 다음 페이지 커서                     |

---

## 2. 데이터 모델

### 2.1 Foreshadowing (복선)

기능 명세서 9항 데이터 구조 기반.

| 필드                   | 타입            | 필수 | 설명                                         |
| ---------------------- | --------------- | ---- | -------------------------------------------- | ------------------------------------- |
| `foreshadowing_id`     | string          | Y    | 복선 고유 ID                                 |
| `project_id`           | string          | Y    | 소속 프로젝트 ID                             |
| `title`                | string          | Y    | 복선 제목                                    |
| `description`          | string          | N    | 복선 설명                                    |
| `setup_chapter`        | integer         | Y    | 복선이 처음 설치된 챕터                      |
| `linked_chapters`      | integer[]       | N    | 복선이 언급·강화된 중간 챕터 목록 (오름차순) |
| `payoff_chapter`       | integer         | null | N                                            | 복선이 회수된 챕터 (미회수 시 `null`) |
| `status`               | string          | Y    | `planted`(미회수) | `resolved`(회수) | `abandoned`(회수 포기) — DB `foreshadowings_status_chk`. `abandoned`로 바꾸는 흐름은 명세에 없음 |
| `linked_event_ids`     | string[]        | N    | 연결된 사건 ID 목록 (FTS-008)                |
| `linked_character_ids` | string[]        | N    | 연결된 캐릭터 ID 목록 (FTS-008)              |
| `created_at`           | string(ISO8601) | Y    | 생성 시각                                    |
| `updated_at`           | string(ISO8601) | Y    | 수정 시각                                    |

### 2.2 UnresolvedForeshadowing (미회수 목록 항목 · FTS-005)

| 필드               | 타입    | 설명                                           |
| ------------------ | ------- | ---------------------------------------------- |
| `foreshadowing_id` | string  | 복선 ID                                        |
| `title`            | string  | 복선 제목                                      |
| `setup_chapter`    | integer | 설치 챕터                                      |
| `elapsed_chapters` | integer | 기준 챕터(`current_chapter`) 기준 경과 챕터 수 |

### 2.3 Advisory (미회수 안내 메시지 · FTS-006)

| 필드                    | 타입    | 설명                        |
| ----------------------- | ------- | --------------------------- | ------------------------------------- | ------------------------------- |
| `foreshadowing_id`      | string  | 대상 복선 ID                |
| `message`               | string  | 조언 형태의 안내 문장       |
| `setup_chapter`         | integer | 설치 챕터 (바로가기 링크용) |
| `latest_linked_chapter` | integer | null                        | 가장 최근 연결 챕터 (바로가기 링크용) |
| `priority`              | string  | `low`                       | `medium`                              | `high` — 경과 챕터 수 기준 산정 |

### 2.4 TimelineTrack (복선 타임라인 트랙 · FTS-007)

| 필드               | 타입     | 설명                                                                |
| ------------------ | -------- | ------------------------------------------------------------------- | ------------ | -------- |
| `foreshadowing_id` | string   | 복선 ID                                                             |
| `title`            | string   | 복선 제목                                                           |
| `status`           | string   | `planted` | `resolved` | `abandoned` |
| `markers`          | object[] | `[{chapter, type}]` — `type`: `setup` | `hint`(연결 챕터) | `payoff` (DB `foreshadowing_chapters.role`) |
| `is_open`          | boolean  | 회수 지점이 없는 "열린 트랙" 여부 (`status=planted`일 때 `true`) |

---

## 3. 엔드포인트 목록

| #   | Method | Path                                                                                   | 설명                                               | 관련 기능 ID     |
| --- | ------ | -------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------- |
| 1   | GET    | `/projects/{projectId}/foreshadowings`                                                 | 복선 목록 조회 (필터링)                            | FTS-009          |
| 2   | POST   | `/projects/{projectId}/foreshadowings`                                                 | 복선 생성                                          | FTS-001          |
| 3   | GET    | `/projects/{projectId}/foreshadowings/{foreshadowingId}`                               | 복선 상세 조회                                     | FTS-001          |
| 4   | PATCH  | `/projects/{projectId}/foreshadowings/{foreshadowingId}`                               | 복선 정보 수정                                     | FTS-001          |
| 5   | DELETE | `/projects/{projectId}/foreshadowings/{foreshadowingId}`                               | 복선 삭제                                          | FTS-001          |
| 6   | POST   | `/projects/{projectId}/foreshadowings/{foreshadowingId}/linked-chapters`               | 연결 챕터 추가                                     | FTS-002          |
| 7   | DELETE | `/projects/{projectId}/foreshadowings/{foreshadowingId}/linked-chapters/{chapter}`     | 연결 챕터 제거                                     | FTS-002          |
| 8   | PUT    | `/projects/{projectId}/foreshadowings/{foreshadowingId}/payoff`                        | 회수 처리(회수 챕터 기록)                          | FTS-003, FTS-004 |
| 9   | DELETE | `/projects/{projectId}/foreshadowings/{foreshadowingId}/payoff`                        | 회수 취소(미회수로 되돌림)                         | FTS-004          |
| 10  | GET    | `/projects/{projectId}/foreshadowings/unresolved`                                      | 미회수 목록 조회                                   | FTS-005          |
| 11  | GET    | `/projects/{projectId}/foreshadowings/unresolved/advisories`                           | 미회수 안내 메시지 조회                            | FTS-006          |
| 12  | GET    | `/projects/{projectId}/foreshadowing-timeline`                                         | 복선 타임라인 시각화 데이터                        | FTS-007          |
| 13  | POST   | `/projects/{projectId}/foreshadowings/{foreshadowingId}/links`                         | 사건/캐릭터 연결 추가                              | FTS-008          |
| 14  | DELETE | `/projects/{projectId}/foreshadowings/{foreshadowingId}/links/{targetType}/{targetId}` | 연결 해제                                          | FTS-008          |
| 15  | GET    | `/projects/{projectId}/chapters/{chapter}/foreshadowings`                              | 특정 챕터에 연결된 복선 조회 (챕터 삭제 전 확인용) | 12항 예외처리    |

---

## 4. 엔드포인트 상세 명세

### 4.1 복선 목록 조회

`GET /projects/{projectId}/foreshadowings`

**Query Parameters**

| 이름                         | 타입    | 필수 | 설명                                |
| ---------------------------- | ------- | ---- | ----------------------------------- | ------------ |
| `status`                     | string  | N    | `planted` | `resolved` | `abandoned` |
| `chapter_from`, `chapter_to` | integer | N    | 설치~회수 범위가 겹치는 복선 필터링 |
| `linked_character_id`        | string  | N    | 특정 캐릭터와 연결된 복선만 필터링  |
| `linked_event_id`            | string  | N    | 특정 사건과 연결된 복선만 필터링    |
| `limit`, `cursor`            | -       | N    | 페이지네이션                        |

**Response 200**

```json
{
  "data": [
    {
      "foreshadowing_id": "fs_001",
      "title": "낡은 회중시계",
      "description": "1화에서 주인공이 무심코 받은 시계가 이후 정체와 연결됨",
      "setup_chapter": 1,
      "linked_chapters": [12, 24],
      "payoff_chapter": 40,
      "status": "resolved",
      "linked_event_ids": ["evt_005", "evt_233"],
      "linked_character_ids": ["char_001"]
    }
  ],
  "meta": { "next_cursor": null }
}
```

### 4.2 복선 생성

`POST /projects/{projectId}/foreshadowings`

**Request Body**

```json
{
  "title": "사라진 편지",
  "description": "8화에서 언급된 발신인 불명의 편지",
  "setup_chapter": 8,
  "linked_event_ids": ["evt_040"],
  "linked_character_ids": ["char_003"]
}
```

**Response 201**

```json
{
  "data": {
    "foreshadowing_id": "fs_007",
    "title": "사라진 편지",
    "setup_chapter": 8,
    "linked_chapters": [],
    "payoff_chapter": null,
    "status": "planted",
    "linked_event_ids": ["evt_040"],
    "linked_character_ids": ["char_003"]
  },
  "meta": { "similar_candidates": [] }
}
```

**비고 (12항 "중복 복선 등록")**: 유사한 `title`/`description`을 가진 기존 복선이 있으면 생성은 정상 처리하되(별개 복선으로 관리), `meta.similar_candidates`에 `[{foreshadowing_id, title}]` 형태로 후보를 함께 반환하여 사용자에게 안내한다. 생성을 막지는 않는다.

### 4.3 복선 상세 조회

`GET /projects/{projectId}/foreshadowings/{foreshadowingId}`

**Response 200**: `Foreshadowing` 객체 · **Response 404**: `FORESHADOWING_NOT_FOUND`

### 4.4 복선 정보 수정

`PATCH /projects/{projectId}/foreshadowings/{foreshadowingId}`

**Request Body** (일부 필드만 전송 가능)

```json
{ "title": "사라진 편지 (수정)", "description": "..." }
```

**비고**: `setup_chapter` 변경도 이 API로 가능하다(12항 "설치 챕터 삭제 시 재지정" 대응). `payoff_chapter`/`status`는 4.8, 4.9 전용 API로만 변경한다.

**Response 200**: 수정된 `Foreshadowing` 객체

### 4.5 복선 삭제

`DELETE /projects/{projectId}/foreshadowings/{foreshadowingId}`

**Response 204**

### 4.6 연결 챕터 추가

`POST /projects/{projectId}/foreshadowings/{foreshadowingId}/linked-chapters`

**Request Body**

```json
{ "chapter": 12 }
```

**Response 201**: 갱신된 `linked_chapters` 배열 · **Response 400**: `chapter`가 `setup_chapter`보다 작은 경우 `INVALID_INPUT`

### 4.7 연결 챕터 제거

`DELETE /projects/{projectId}/foreshadowings/{foreshadowingId}/linked-chapters/{chapter}`

**Response 204** · **Response 404**: `LINKED_CHAPTER_NOT_FOUND`

### 4.8 회수 처리

`PUT /projects/{projectId}/foreshadowings/{foreshadowingId}/payoff`

**Request Body**

```json
{ "payoff_chapter": 40 }
```

**Response 200**

```json
{
  "data": {
    "foreshadowing_id": "fs_001",
    "payoff_chapter": 40,
    "status": "resolved"
  }
}
```

**Response 400 — 회수 챕터가 설치 챕터보다 앞선 경우 (12항 예외처리)**

```json
{
  "error": {
    "code": "INVALID_PAYOFF_CHAPTER",
    "message": "회수 챕터(5)는 설치 챕터(8)보다 앞설 수 없습니다.",
    "details": { "setup_chapter": 8, "requested_payoff_chapter": 5 }
  }
}
```

### 4.9 회수 취소

`DELETE /projects/{projectId}/foreshadowings/{foreshadowingId}/payoff`

회수 챕터를 해제하고 상태를 `planted`로 되돌린다(12항 "회수 후 회수 챕터 삭제" 예외처리).

**Response 200**

```json
{
  "data": {
    "foreshadowing_id": "fs_001",
    "payoff_chapter": null,
    "status": "planted"
  }
}
```

**Response 409**: 이미 미회수 상태인 복선에 요청 시 `PAYOFF_NOT_SET`

### 4.10 미회수 목록 조회

`GET /projects/{projectId}/foreshadowings/unresolved`

**Query Parameters**

| 이름              | 타입    | 필수 | 설명                                    |
| ----------------- | ------- | ---- | --------------------------------------- | ------------------- |
| `current_chapter` | integer | Y    | 경과 챕터 수 계산 기준이 되는 현재 챕터 |
| `sort`            | string  | N    | `elapsed_desc`(기본, 오래 경과한 순)    | `setup_chapter_asc` |

**Response 200**

```json
{
  "data": {
    "current_chapter": 35,
    "unresolved": [
      {
        "foreshadowing_id": "fs_007",
        "title": "사라진 편지",
        "setup_chapter": 8,
        "elapsed_chapters": 27
      },
      {
        "foreshadowing_id": "fs_011",
        "title": "이웃의 경고",
        "setup_chapter": 22,
        "elapsed_chapters": 13
      }
    ]
  }
}
```

### 4.11 미회수 안내 메시지 조회

`GET /projects/{projectId}/foreshadowings/unresolved/advisories`

AI 디렉터 패널에 표시할 조언 형태 안내 문장을 생성한다(FTS-006). 결정론적 템플릿 기반이며 AI 호출은 발생하지 않는다.

**Query Parameters**: `current_chapter` (필수)

**Response 200**

```json
{
  "data": [
    {
      "foreshadowing_id": "fs_007",
      "message": "8화에 설치한 '사라진 편지' 복선이 아직 회수되지 않았습니다. 현재 챕터 흐름에서 다시 언급하거나 회수를 고려할 수 있습니다.",
      "setup_chapter": 8,
      "latest_linked_chapter": null,
      "priority": "high"
    }
  ]
}
```

**비고**: `priority`는 `elapsed_chapters` 기준으로 산정한다(예: 임계값은 서비스 정책으로 정의, 초기값 제안: 10챕터 미만 `low`, 10~25 `medium`, 25 초과 `high`).

### 4.12 복선 타임라인 조회

`GET /projects/{projectId}/foreshadowing-timeline`

**Query Parameters**: `status`(필터), `chapter_from`, `chapter_to`

**Response 200**

```json
{
  "data": [
    {
      "foreshadowing_id": "fs_001",
      "title": "낡은 회중시계",
      "status": "resolved",
      "markers": [
        { "chapter": 1, "type": "setup" },
        { "chapter": 12, "type": "hint" },
        { "chapter": 24, "type": "hint" },
        { "chapter": 40, "type": "payoff" }
      ],
      "is_open": false
    },
    {
      "foreshadowing_id": "fs_007",
      "title": "사라진 편지",
      "status": "planted",
      "markers": [{ "chapter": 8, "type": "setup" }],
      "is_open": true
    }
  ]
}
```

**비고**: 관계 변화 시각화(RCV)와 동일한 하단 타임라인 컴포넌트에서 챕터 시점 기준으로 함께 동기화된다.

### 4.13 사건/캐릭터 연결 추가

`POST /projects/{projectId}/foreshadowings/{foreshadowingId}/links`

**Request Body**

```json
{ "target_type": "event", "target_id": "evt_233" }
```

`target_type` 값: `event` | `character`

**Response 201**: 갱신된 `linked_event_ids`/`linked_character_ids` · **Response 404**: `LINK_TARGET_NOT_FOUND`

### 4.14 연결 해제

`DELETE /projects/{projectId}/foreshadowings/{foreshadowingId}/links/{targetType}/{targetId}`

**Response 204** · **비고 (12항 "연결된 사건·캐릭터 삭제")**: 연결된 사건/캐릭터 자체가 삭제되는 경우, 해당 도메인(사건/캐릭터) 삭제 로직이 내부적으로 이 API를 호출하여 링크만 해제하고 복선 레코드는 유지한다.

### 4.15 특정 챕터에 연결된 복선 조회 (챕터 삭제 전 확인용)

`GET /projects/{projectId}/chapters/{chapter}/foreshadowings`

챕터 삭제 API(원고/타임라인 도메인)가 삭제 전 해당 챕터를 참조하는 복선이 있는지 확인하기 위해 호출한다(12항 "설치 챕터 삭제" 예외처리 지원).

**Response 200**

```json
{
  "data": [
    { "foreshadowing_id": "fs_007", "title": "사라진 편지", "role": "setup" },
    { "foreshadowing_id": "fs_001", "title": "낡은 회중시계", "role": "hint" }
  ]
}
```

`role` 값: `setup` | `hint`(연결 챕터) | `payoff` (DB `foreshadowing_chapters_role_chk`)

**연계 동작**: `role: "setup"`인 항목이 있으면 챕터 삭제 API는 사용자에게 해당 복선의 설치 챕터 재지정을 요청하도록 안내한다(자동 삭제/재지정하지 않음).

---

## 5. 처리 흐름 — API 매핑

| 기능 명세서 단계                 | 처리 주체       | 대응 API                                                                                                     |
| -------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------ |
| 1단계: 복선 생성·설치 챕터 지정  | 사용자          | `POST /foreshadowings`                                                                                       |
| 2단계: 연결 챕터 추가            | 사용자          | `POST /foreshadowings/{id}/linked-chapters`                                                                  |
| 3단계: 미회수 상태 저장·추적     | 시스템          | 생성 시 `status: "planted"`로 초기화                                                                      |
| 4단계: 회수 챕터 기록·상태 변경  | 사용자          | `PUT /foreshadowings/{id}/payoff`                                                                            |
| 5단계: 미회수 목록·타임라인 안내 | 시스템 → 사용자 | `GET /foreshadowings/unresolved`, `GET /foreshadowings/unresolved/advisories`, `GET /foreshadowing-timeline` |

**시퀀스 요약**

```
[사용자] POST /foreshadowings (설치 챕터 지정) → status: planted
      │
      ▼
[사용자] POST /foreshadowings/{id}/linked-chapters (필요 시 반복 추가)
      │
      ▼
[시스템] GET /foreshadowings/unresolved, /unresolved/advisories → AI 디렉터 패널 안내
      │
      ▼
[사용자] 회수 시점 도달 → PUT /foreshadowings/{id}/payoff (payoff_chapter 기록)
      │
      ▼
[시스템] status: resolved → 타임라인이 닫힌 트랙으로 갱신 (GET /foreshadowing-timeline)
```

---

## 6. 부록 — 예시 시나리오

기능 명세서 9, 10항 예시를 API 호출 순서로 재구성.

1. **복선 생성** `POST /projects/proj_1/foreshadowings`

```json
{ "title": "사라진 편지", "setup_chapter": 8, "linked_event_ids": ["evt_040"] }
```

→ `foreshadowing_id: fs_007`, `status: "planted"`

1. **35챕터 시점, 미회수 목록 확인** `GET /projects/proj_1/foreshadowings/unresolved?current_chapter=35` → `fs_007` 포함, `elapsed_chapters: 27`
2. **AI 디렉터 패널 안내 메시지 조회** `GET /projects/proj_1/foreshadowings/unresolved/advisories?current_chapter=35` → "8화에 설치한 '사라진 편지' 복선이 아직 회수되지 않았습니다. 현재 챕터 흐름에서 다시 언급하거나 회수를 고려할 수 있습니다."
3. **40챕터에서 복선 회수** `PUT /projects/proj_1/foreshadowings/fs_007/payoff`

```json
{ "payoff_chapter": 40 }
```

→ `status: "resolved"`

1. **타임라인에서 흐름 확인** `GET /projects/proj_1/foreshadowing-timeline` → `fs_007`의 `markers: [{chapter:8, setup}, {chapter:40, payoff}]`, `is_open: false`

---

## 7. 향후 확장 고려사항 (기능 명세서 15항 연계)

| 확장 항목                                          | API 영향                                                                                               |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 설정 충돌 감지 시스템 연계 (복선-설정 일관성 검사) | SCDS 룰 엔진이 `GET /foreshadowings`(linked_character_id 필터)를 참조 데이터로 호출하는 내부 연동 필요 |
| 관계 변화 시각화 연계 (복선-관계 연결)             | `Foreshadowing`에 `linked_relationship_ids` 필드 추가 가능성                                           |
| AI 기반 미회수 복선 회수 시점 제안                 | 4.11 API가 결정론적 템플릿 대신 선택적 AI 호출(SCDS와 동일한 후보 기반 방식)로 확장될 가능성           |
| 복선 밀도·회수율 통계 리포트                       | `GET /projects/{projectId}/foreshadowings/summary` 형태의 집계 API 추가 가능성                         |
