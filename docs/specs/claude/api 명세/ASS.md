**Auto Structuring System (ASS) API Specification**

| 항목          | 내용                                                                                    |
| ------------- | --------------------------------------------------------------------------------------- |
| 문서명        | AI 자동 구조화 시스템 API 명세서                                                        |
| 소속 프로젝트 | StoryForge (Prolog)                                                                     |
| 근거 문서     | AI 자동 구조화 시스템 기능 명세서 v0.1                                                  |
| 관련 모듈     | 자연어 입력 기반 캐릭터 설간, 구조화 저장 엔진, 설정 충돌 감지 시스템, 관계 변화 시각화 |
| 문서 버전     | v0.1 (Draft)                                                                            |
| 상태          | 작성 중                                                                                 |

> SCDS·RCV·FTS API 명세서와 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다.

<aside>
⚠️

**명세서 간 데이터 모델 정합성 확인 필요**: 본 문서의 확정된 구조화 데이터 필드명(`personality_tags`, `core_values`, `influence_relations`, `emotion_keywords`)이 SCDS API 명세서의 `Character` 모델 필드명(`traits`, `values`, `influences`)과 다릅니다. 두 문서 모두 "캐릭터의 성격·가치관·영향 관계"라는 동일한 개념을 가리키는 것으로 보이얰매, 실제로는 ASS가 이 데이터의 확정·저장을 담당하고 SCDS/RCV가 이를 참조하는 관계입니다. 구현 전 필드명을 하나로 통일하거나 매핑 규직을 정의해야 합니다. 이 문서는 ASS 기능 명세서 9항에 명시된 필드명을 기준으로 API를 설계했습니다.

</aside>

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
    "code": "DRAFT_NOT_FOUND",
    "message": "해당 초안을 찾을 수 없습니다.",
    "details": {}
  }
}
```

### 1.4 공통 에러 코드

| 코드                            | HTTP 상태 | 설명                                                                        |
| ------------------------------- | --------- | --------------------------------------------------------------------------- |
| `INVALID_INPUT`                 | 400       | 요청 본문/파라미터 형식 오류                                                |
| `UNAUTHORIZED`                  | 401       | 인증 토큰 없음/만료                                                         |
| `FORBIDDEN`                     | 403       | 프로젝트 접근 권한 없음                                                     |
| `DRAFT_NOT_FOUND`               | 404       | 초안 리소스 없음                                                            |
| `ITEM_NOT_FOUND`                | 404       | 초안 내 항목(item) 없음                                                     |
| `CHARACTER_NOT_FOUND`           | 404       | 확정된 캐릭터 리소스 없음                                                   |
| `DRAFT_ALREADY_RESOLVED`        | 409       | 이미 `confirmed`/`discarded` 처리된 초안에 대한 편집·확정·폐기 재요청       |
| `MISSING_REQUIRED_FIELD`        | 400       | 확정 시 필수 항목(예: 캐릭터 이름)이 비어 있음 (12항 예외처리)              |
| `DUPLICATE_CHARACTER_CANDIDATE` | 409       | 동일 캐릭터로 추정되는 기존 확정 데이터가 존재 (12항 예외처리)              |
| `AI_SUGGESTION_DISABLED`        | 403       | AI 재추천 기능이 비활성화된 상태에서 호출 (15항 제약사항 — 기본값 비활성화) |

### 1.5 페이지네이션

| 파라미터 | 설명                                 |
| -------- | ------------------------------------ |
| `limit`  | 페이지당 항목 수 (기본 20, 최대 100) |
| `cursor` | 다음 페이지 커서                     |

---

## 2. 데이터 모델

### 2.1 CharacterDraft (초안)

기능 명세서 9항 데이터 구조 기반. 각 초안 항목은 개별 수정·삭제가 가능하도록 `item_id`를 밀여한 구조로 확장함.

| 필드                     | 타입                   | 필수 | 설명                             |
| ------------------------ | ---------------------- | ---- | -------------------------------- | -------------------------------------------------- | ----------- |
| `draft_id`               | string                 | Y    | 초안 고유 ID                     |
| `project_id`             | string                 | Y    | 소속 프로젝트 ID                 |
| `character_name`         | string                 | N    | 캐릭터 이름 (확정 시 필수, 12항) |
| `personality_tags`       | `DraftItem[]`          | N    | 성격 태그 목록                   |
| `core_values`            | `DraftItem[]`          | N    | 핵심 가치 목록                   |
| `influence_relations`    | `DraftInfluenceItem[]` | N    | 영향 관계 목록                   |
| `emotion_keywords`       | `DraftItem[]`          | N    | 감정 키워드 목록                 |
| `status`                 | string                 | Y    | `pending`                        | `confirmed`                                        | `discarded` (DB `character_drafts_status_chk`) |
| `source_session_id`      | string                 | null | N                                | 자연어 입력 기반 캐릭터 설간 기능의 원본 세션 참조 |
| `confirmed_character_id` | string                 | null | N                                | 확정 후 생성/병합된 캐릭터 ID                      |
| `created_at`             | string(ISO8601)        | Y    | 수신 시각                        |

### 2.2 DraftItem (초안 단일 항목)

| 필드      | 타입   | 필수 | 설명               |
| --------- | ------ | ---- | ------------------ | --------------------------- | ------------------ |
| `item_id` | string | Y    | 항목 고유 ID       |
| `field`   | string | Y    | `personality_tag` | `core_value`               | `emotion_keyword` (DB `character_draft_items.category` 값. 목록 필드명은 복수형 그대로) |
| `value`   | string | Y    | 항목 값            |
| `origin`  | string | Y    | `ai_extracted`     | `user_added` (EDIT-03 대응) |

### 2.3 DraftInfluenceItem (영향 관계 항목)

| 필드      | 타입   | 필수 | 설명                         |
| --------- | ------ | ---- | ---------------------------- | ----------------------------- |
| `item_id` | string | Y    | 항목 고유 ID                 |
| `field`   | string | Y    | 고정값 `influence_relation` |
| `target`  | string | Y    | 영향을 준 대상 이름          |
| `type`    | string | N    | 관계 유형 (예: "영향")       |
| `status`  | string | null | N                            | 대상의 현재 상태 (예: "고인") |
| `origin`  | string | Y    | `ai_extracted`               | `user_added`                  |

### 2.4 ConfirmedCharacter (확정된 구조화 캐릭터 데이터)

| 필드                  | 타입            | 필수 | 설명                       |
| --------------------- | --------------- | ---- | -------------------------- |
| `character_id`        | string          | Y    | 캐릭터 고유 ID             |
| `project_id`          | string          | Y    | 소속 프로젝트 ID           |
| `name`                | string          | Y    | 캐릭터 이름                |
| `personality_tags`    | string[]        | N    | 성격 태그                  |
| `core_values`         | string[]        | N    | 핵심 가지                  |
| `influence_relations` | object[]        | N    | `[{target, type, status}]` |
| `emotion_keywords`    | string[]        | N    | 감정 키워드                |
| `status`              | string          | Y    | `active` \| `archived` (DB `characters_status_chk`. 확정 직후는 `active`) |
| `confirmed_at`        | string(ISO8601) | Y    | 확정 시각                  |
| `updated_at`          | string(ISO8601) | Y    | 마지막 수정 시각           |

### 2.5 EditHistoryEntry (편집 이력 항목)

DB `authoring.character_edit_histories` 구조를 따른다.

| 필드           | 타입            | 필수 | 설명                                             |
| -------------- | --------------- | ---- | ------------------------------------------------ |
| `phase`        | string          | Y    | `draft`(확정 전) \| `confirmed`(확정 후)        |
| `action`       | string          | Y    | `create` \| `update` \| `delete`               |
| `field`        | string          | Y    | 대상 필드명 (예: `core_value`, `character_name`) |
| `before_value` | string \| null  | N    | 바뀌기 전 값 (`create`면 null)                   |
| `after_value`  | string \| null  | N    | 바뀐 뒤 값 (`delete`면 null)                     |
| `created_at`   | string(ISO8601) | Y    | 변경 시각                                        |

---

## 3. 엔드포인트 목록

| #   | Method | Path                                                                          | 설명                                    | 관련 기능 ID  |
| --- | ------ | ----------------------------------------------------------------------------- | --------------------------------------- | ------------- |
| 1   | POST   | `/projects/{projectId}/character-drafts`                                      | 초안 데이터 수신                        | ASS-001       |
| 2   | GET    | `/projects/{projectId}/character-drafts`                                      | 초안 목록 조회                          | ASS-002       |
| 3   | GET    | `/projects/{projectId}/character-drafts/{draftId}`                            | 초안 상세 조회                          | ASS-002       |
| 4   | PATCH  | `/projects/{projectId}/character-drafts/{draftId}`                            | 초안 최상위 필드 수정 (캐릭터 이름 등)  | ASS-003       |
| 5   | POST   | `/projects/{projectId}/character-drafts/{draftId}/items`                      | 항목 추가                               | ASS-005       |
| 6   | PATCH  | `/projects/{projectId}/character-drafts/{draftId}/items/{itemId}`             | 항목 수정                               | ASS-003       |
| 7   | DELETE | `/projects/{projectId}/character-drafts/{draftId}/items/{itemId}`             | 항목 삭제                               | ASS-004       |
| 8   | POST   | `/projects/{projectId}/character-drafts/{draftId}/items/{itemId}/suggestions` | 특정 항목 AI 대안 값 재추천 요청 (선택) | 11항          |
| 9   | POST   | `/projects/{projectId}/character-drafts/{draftId}/confirm`                    | 확정 및 구조화 데이터 저장              | ASS-006       |
| 10  | POST   | `/projects/{projectId}/character-drafts/{draftId}/discard`                    | 초안 폐기                               | 12항 예외처리 |
| 11  | GET    | `/projects/{projectId}/character-drafts/{draftId}/edit-history`               | 초안 편집 이력 조회 (확정 전)           | ASS-008       |
| 12  | GET    | `/projects/{projectId}/characters`                                            | 확정된 구조화 캐릭터 목록 조회          | ASS-007       |
| 13  | GET    | `/projects/{projectId}/characters/{characterId}`                              | 확정된 구조화 캐릭터 상세 조회          | ASS-007       |
| 14  | GET    | `/projects/{projectId}/characters/{characterId}/edit-history`                 | 확정 이후 편집 이력 조회                | ASS-008       |

---

## 4. 엔드포인트 상세 명세

### 4.1 초안 데이터 수신

`POST /projects/{projectId}/character-drafts`

자연어 입력 기반 캐릭터 설간 기능이 추출을 완료한 뒤 이 API를 호출하여 초안을 생성한다.

**Request Body**

```json
{
  "character_name": "피터 파커",
  "personality_tags": ["책임감 강함", "자신감 부족"],
  "core_values": ["폭력 회피"],
  "influence_relations": [{ "target": "벤 삼촌", "type": "영향" }],
  "emotion_keywords": ["불안"],
  "source_session_id": "nlsession_882"
}
```

**Response 201**

```json
{
  "data": {
    "draft_id": "draft_0212",
    "character_name": "피터 파커",
    "personality_tags": [
      {
        "item_id": "itm_1",
        "field": "personality_tag",
        "value": "책임감 강함",
        "origin": "ai_extracted"
      },
      {
        "item_id": "itm_2",
        "field": "personality_tag",
        "value": "자신감 부족",
        "origin": "ai_extracted"
      }
    ],
    "core_values": [
      {
        "item_id": "itm_3",
        "field": "core_value",
        "value": "폭력 회피",
        "origin": "ai_extracted"
      }
    ],
    "influence_relations": [
      {
        "item_id": "itm_4",
        "field": "influence_relation",
        "target": "벤 삼촌",
        "type": "영향",
        "status": null,
        "origin": "ai_extracted"
      }
    ],
    "emotion_keywords": [
      {
        "item_id": "itm_5",
        "field": "emotion_keyword",
        "value": "불안",
        "origin": "ai_extracted"
      }
    ],
    "status": "pending",
    "source_session_id": "nlsession_882",
    "confirmed_character_id": null
  }
}
```

**비고 (12항 "초안 데이터 수신 실패")**: 이 API 호출 자신이 실패(타임아웃/오류)하면 클라이언트는 불 편집 화을 대 표시하고 자연어 입력 단계 재요청을 안내한다 — 서버 쓸 별도 처리는 없다.

### 4.2 초안 목록 조회

`GET /projects/{projectId}/character-drafts`

**Query Parameters**: `status` (`pending`|`confirmed`|`discarded`), `limit`, `cursor`

**Response 200**: `CharacterDraft[]`

### 4.3 초안 상세 조회

`GET /projects/{projectId}/character-drafts/{draftId}`

편집 화장(ASS-002) 로딩 시 호출한다.

**Response 200**: `CharacterDraft` 객체 (전체 item 포함) · **Response 404**: `DRAFT_NOT_FOUND`

### 4.4 초안 최상위 필드 수정

`PATCH /projects/{projectId}/character-drafts/{draftId}`

**Request Body**

```json
{ "character_name": "피터 B. 파커" }
```

**Response 200**: 수정된 `CharacterDraft` 객체 · **Response 409**: `status`가 `confirmed`/`discarded`인 경우 `DRAFT_ALREADY_RESOLVED` · **비고**: 이 호출은 편집 이력에 `{action: "update", field: "character_name", ...}`로 기록된다(ASS-008).

### 4.5 항목 추가

`POST /projects/{projectId}/character-drafts/{draftId}/items`

사용자가 AI가 추출하지 미쁩 항목을 직접 추가한다(ASS-005, EDIT-03).

**Request Body — 일반 항목**

```json
{ "field": "core_value", "value": "책임 중시" }
```

**Request Body — 영향 관계 항목**

```json
{
  "field": "influence_relation",
  "target": "메이 숙모",
  "type": "영향",
  "status": null
}
```

**Response 201**: 생성된 항목 (`origin: "user_added"`, 편집 이력에 `create`로 기록) · **Response 409**: `DRAFT_ALREADY_RESOLVED`

### 4.6 항목 수정

`PATCH /projects/{projectId}/character-drafts/{draftId}/items/{itemId}`

**Request Body**

```json
{ "value": "책임 중시" }
```

영향 관계 항목의 경우:

```json
{ "status": "고인" }
```

**Response 200**: 수정된 항목 (편집 이력에 `update`로 기록, EDIT-01) · **Response 404**: `ITEM_NOT_FOUND`

### 4.7 항목 삭제

`DELETE /projects/{projectId}/character-drafts/{draftId}/items/{itemId}`

**Response 204** (편집 이력에 `delete`로 기록, EDIT-02) · **Response 404**: `ITEM_NOT_FOUND`

### 4.8 항목 AI 재추천 요청 (선택 기능)

`POST /projects/{projectId}/character-drafts/{draftId}/items/{itemId}/suggestions`

11항 "재추천 기능" — 사용자가 지정적으로 요청할 때만 호출된다. 프로젝트/조직 설정에서 기본값은 비활성화(15항 제약사항)이므로, 비활성 상태에서 호출 시 오류를 반환한다.

**Response 200 — 활성화된 경우**

```json
{
  "data": {
    "item_id": "itm_3",
    "suggestions": ["책임 중시", "정의감", "보호 본능"]
  }
}
```

**Response 403 — 기능 비활성화**

```json
{
  "error": {
    "code": "AI_SUGGESTION_DISABLED",
    "message": "AI 재추천 기능이 비활성화되어 있습니다. 프로젝트 설정에서 활성화할 수 있습니다.",
    "details": {}
  }
}
```

**비고**: 이 API는 대안 값을 제안만 하어, 적용은 4.6(항목 수정) API를 통해 사용자가 직접 확정해야 한다(11항 "AI는 사용자 편집 내용을 임의로 바꾸지 않는다").

### 4.9 확정 및 저장

`POST /projects/{projectId}/character-drafts/{draftId}/confirm`

**Request Body (기본)**

```json
{}
```

**Response 201 — 신규 캐릭터로 확정**

```json
{
  "data": {
    "character_id": "char_001",
    "name": "피터 파커",
    "personality_tags": ["책임감 강함", "자신감 부족"],
    "core_values": ["폭력 회피", "책임 중시"],
    "influence_relations": [
      { "target": "벤 삼촌", "type": "영향", "status": "고인" }
    ],
    "emotion_keywords": ["불안"],
    "status": "active",
    "confirmed_at": "2026-08-27T10:05:00Z"
  }
}
```

**Response 400 — 필수 항목 누랬 (12항 예외처리)**

```json
{
  "error": {
    "code": "MISSING_REQUIRED_FIELD",
    "message": "캐릭터 이름이 비어 있어 확정할 수 없습니다.",
    "details": { "field": "character_name" }
  }
}
```

**Response 409 — 중복 캐릭터 후보 발견 (12항 예외처리)**

```json
{
  "error": {
    "code": "DUPLICATE_CHARACTER_CANDIDATE",
    "message": "동일한 이름의 확정된 캐릭터가 이미 존재합니다. 병합할지, 이름을 바꿔 새 캐릭터로 생성할지 선택해 주세요.",
    "details": { "candidate_character_id": "char_001" }
  }
}
```

**Request Body — 중복 후보에 대한 재요청**

```json
{ "resolution": "merge", "merge_target_character_id": "char_001" }
```

또는

```json
{ "resolution": "create_new", "character_name": "피터 B. 파커" }
```

`create_new`는 **기존 캐릭터와 다른 이름**(`character_name`)을 함께 보내야 한다. DB가 한 프로젝트 안에서 같은 이름(대소문자 무시)의 활성 캐릭터를 하나만 허용하기 때문이다(`characters_project_name_active_uq`). 바꾼 이름도 겹치면 다시 409 `DUPLICATE_CHARACTER_CANDIDATE`를 반환한다.

**Response 201/200**: `resolution`에 따라 병합된 `ConfirmedCharacter` 또는 신규 `ConfirmedCharacter` 반환

### 4.10 초안 폐기

`POST /projects/{projectId}/character-drafts/{draftId}/discard`

사용자가 편집을 마처지 앞엀거 폐기할 때 호출한다. 화장을 그대로 이탈하는 경우(EDIT-04)에는 이 API를 호출하지 않으매, 초안은 `pending` 상태로 그대로 보관된다.

**Response 200**

```json
{ "data": { "draft_id": "draft_0212", "status": "discarded" } }
```

**Response 409**: `DRAFT_ALREADY_RESOLVED`

### 4.11 초안 편집 이력 조회 (확정 전)

`GET /projects/{projectId}/character-drafts/{draftId}/edit-history`

**Response 200**

```json
{
  "data": [
    {
      "phase": "draft",
      "action": "create",
      "field": "core_value",
      "before_value": null,
      "after_value": "책임 중시",
      "created_at": "2026-08-27T10:02:00Z"
    },
    {
      "phase": "draft",
      "action": "update",
      "field": "personality_tag",
      "before_value": "책임감 강함",
      "after_value": "책임감이 강함",
      "created_at": "2026-08-27T10:03:00Z"
    }
  ]
}
```

### 4.12 확정된 구조화 캐릭터 목록 조회 (데이터 제겁용 API)

`GET /projects/{projectId}/characters`

SCDS·RCV 등 다른 기능 모듈이 구조화 데이터를 조회하기 위해 사용하는 API(ASS-007).

**Query Parameters**: `limit`, `cursor`

**Response 200**: `ConfirmedCharacter[]`

### 4.13 확정된 구조화 캐릭터 상세 조회

`GET /projects/{projectId}/characters/{characterId}`

**Response 200**: `ConfirmedCharacter` 객체 · **Response 404**: `CHARACTER_NOT_FOUND`

### 4.14 확정 이후 편집 이력 조회

`GET /projects/{projectId}/characters/{characterId}/edit-history`

확정 이후에도 구조화 데이터가 수정될 경우(예: 캐릭터 직접 수정) 이 API로 전생적 변경 이력을 추적한다(추적성, 14항 버쟁었 요구사항).

**Response 200**: `EditHistoryEntry[]`

---

## 5. 처리 흐름 — API 매핑

| 기능 명세서 단계                      | 처리 주체       | 대응 API                                                                  |
| ------------------------------------- | --------------- | ------------------------------------------------------------------------- |
| 1단계: 초안 데이터 수신               | 시스템          | `POST /character-drafts`                                                  |
| 2단계: 편집 UI 표시                   | 시스템 → 사용자 | `GET /character-drafts/{draftId}`                                         |
| 3단계: 수정·삭제·추가                 | 사용자          | `PATCH .../items/{itemId}`, `DELETE .../items/{itemId}`, `POST .../items` |
| 4단계: 확정 요청                      | 사용자          | `POST /character-drafts/{draftId}/confirm`                                |
| 5단계: 구조화 데이터 저장 + 이력 기록 | 시스템          | 확정 처리 결과가 `ConfirmedCharacter`로 저장, `EditHistoryEntry` 누적     |
| 6단계: 타 기능 모듈에 데이터 제겁     | 시스템          | `GET /characters`, `GET /characters/{characterId}`                        |

**시퀀스 요약**

```
[자연어 입력 기능] POST /character-drafts (초안 생성)
      │
      ▼
[사용자] GET /character-drafts/{id} (편집 화장 로딩)
      │
      ▼
[사용자] POST/PATCH/DELETE .../items (수정·삭제·추가, 반복)
      │
      ▼
[사용자] POST /character-drafts/{id}/confirm
      │
      ├─ 필수 항목 누랬 → 400, 편집 화장 유지
      │
      ├─ 중복 캐릭터 후보 → 409, 병합/신규 선택 후 재요청
      │
      └─ 성삱 → ConfirmedCharacter 생성/병합, 편집 이력 기록
                 │
                 ▼
        [SCDS/RCV 등] GET /characters/{characterId} (데이터 소뱄)
```

---

## 6. 부록 — 예시 시나리오 (피터 파커 케이스)

기능 명세서 9항 예시를 API 호출 순서로 재구성.

1. **초안 수신** `POST /projects/proj_1/character-drafts`

```json
{
  "character_name": "피터 파커",
  "personality_tags": ["책임감 강함", "자신감 부족"],
  "core_values": ["폭력 회피"],
  "influence_relations": [{ "target": "벤 삼촌", "type": "영향" }],
  "emotion_keywords": ["불안"]
}
```

→ `draft_id: draft_0212`

1. **사용자가 핵심 가치 항목 추가** `POST /projects/proj_1/character-drafts/draft_0212/items`

```json
{ "field": "core_value", "value": "책임 중시" }
```

1. **영향 관계 항목에 상태 정보 추가 수정** `PATCH /projects/proj_1/character-drafts/draft_0212/items/itm_4`

```json
{ "status": "고인" }
```

1. **편집 이력 확인** `GET /projects/proj_1/character-drafts/draft_0212/edit-history` → 기능 명세서 9항 편집 이력 예시와 동일한 2건 반환
2. **확정** `POST /projects/proj_1/character-drafts/draft_0212/confirm` → `character_id: char_001`, `status: "active"`
3. **SCDS가 확정 데이터를 참조** `GET /projects/proj_1/characters/char_001` → SCDS API 명세서의 `Character` 조회 시 참조하는 것과 동일한 캐릭터 레코드 (필드명 매핑 필요, 상단 정합성 안내 참고)

---

## 7. 향후 확장 고려사항 (기능 명세서 15항 연계)

| 확장 항목                            | API 영향                                                                                                                        |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| 사건·관계 데이터로 확장 적용         | `POST /event-drafts`, `POST /relationship-drafts` 등 동일한 초안-확정 패턴의 신규 리소스 추가 가능성                            |
| 편집 이력 기반 되돌리기(undo)        | `POST /character-drafts/{draftId}/edit-history/{entryId}/revert` 형태의 신규 엔드포인트 필요                                    |
| 확정 데이터 변경 시 실시간 알림 연동 | 확정/수정 시점에 SCDS·RCV로 이벽트를 전달하는 웹훅 또는 이벽트 버스 연동 필요 (현재는 각 모듈이 4.12~4.13 API를 직접 폴링/조회) |
