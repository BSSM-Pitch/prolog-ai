**Natural Language Character Design (NLCD) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 자연어 입력 기반 캐릭터 설간 API 명세서 |
| 소속 프로젝트 | StoryForge (Prolog) |
| 근거 문서 | 자연어 입력 기반 캐릭터 설간 기능 명세서 v0.1 |
| 관련 모듈 | AI 자동 구조화 시스템, 캐릭터 지륨면화면, AI 디렉터 패널 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> SCDS·RCV·FTS·ASS API 명세서와 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다. NLCD는 AI 호출을 포함하므로 SCDS와 동일하게 **작업 생성 → 폴링** 방식의 비동기 처리로 설계했습니다.
> 

<aside>
ℹ️

**ASS API 명세서와의 관계**: NLCD는 추출(이 문서)까지만 담당하고, 편집·확정·영구 저장은 ASS API 명세서의 `character-drafts` 리소스가 담당한다(기능 명세서 5항 제외 범위). 두 문서의 앱테거리 필드명(`personality_tags`, `core_values`, `influence_relations`, `emotion_keywords`)은 이미 동일하게 맞춰져 있으므로, 4.5 전달 API에서 별도 매핑 없이 그대로 넘길 수 있다.

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
{ "data": { }, "meta": { } }
```

**실패**

```json
{
  "error": { "code": "EXTRACTION_NOT_FOUND", "message": "해당 추출 작업을 찾을 수 없습니다.", "details": {} }
}
```

### 1.4 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 형식 오류 (예: 번 문자열 `source_text`) |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `EXTRACTION_NOT_FOUND` | 404 | 추출 작업 리소스 없음 |
| `TARGET_CHARACTER_NOT_FOUND` | 404 | `target_character_id`로 지정한 캐릭터가 존재하지 않음 |
| `EXTRACTION_NOT_READY` | 409 | 아직 `completed` 상태가 아닌 추출 결과를 전달(forward) 시도 |
| `ALREADY_FORWARDED` | 409 | 이미 구조화 시스템으로 전달된 추출 결과를 재전달 시도 |
| `AI_EXTRACTION_FAILED` | 502 | AI 추출 호출 실패 |
| `AI_EXTRACTION_TIMEOUT` | 503 | AI 추출 응답 지연 |

### 1.5 페이지네이션

| 파라미터 | 설명 |
| --- | --- |
| `limit` | 페이지당 항목 수 (기본 20, 최대 100) |
| `cursor` | 다음 페이지 커서 |

---

## 2. 데이터 모델

### 2.1 NLExtraction (자연어 추출 작업)

기능 명세서 9항 데이터 구조 기반. AI 호출을 포함하므로 SCDS의 `ConflictCheck`와 동일하게 작업(job) 형태로 모델링함.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `extraction_id` | string | Y | 추출 작업 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `source_text` | string | Y | 창작자가 입력한 자연어 서술 텍스트 |
| `target_character_id` | string | null | N | 기존 캐릭터에 추가 입력하는 경우의 대상 (NLCD-006) |
| `status` | string | Y | `analyzing` | `completed` | `failed` |
| `personality_tags` | `ExtractedItem[]` | N | 성격 태그 (완료 시) |
| `core_values` | `ExtractedItem[]` | N | 핵심 가지 (완료 시) |
| `influence_relations` | `ExtractedInfluenceItem[]` | N | 영향 관계 (완료 시) |
| `emotion_keywords` | `ExtractedItem[]` | N | 감정 키워드 (완료 시) |
| `duplicate_of` | string | null | N | 동일/유사 문장으로 판단된 이전 추출 작업 ID (12항 "동일 문장 반복 입력") |
| `forwarded_draft_id` | string | null | N | ASS로 전달되어 생성된 초안(`draft_id`) — 전달 전에는 `null` |
| `created_at` | string(ISO8601) | Y | 요청 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.2 ExtractedItem

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `value` | string | Y | 추출된 항목 값 |
| `evidence` | string | Y | 원문 내 근거 구절 |

### 2.3 ExtractedInfluenceItem

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `value` | string | Y | 영향을 준 대상 이름 |
| `type` | string | N | 관계 유형 (예: "영향") |
| `evidence` | string | Y | 원문 내 근거 구절 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 | 관련 기능 ID |
| --- | --- | --- | --- | --- |
| 1 | POST | `/projects/{projectId}/nl-extractions` | 자연어 입력 제출 + 지륨면화면 추출 요청 | NLCD-002, NLCD-003 |
| 2 | GET | `/projects/{projectId}/nl-extractions/{extractionId}` | 추출 결과/상태 조회 (폴링) | NLCD-004 |
| 3 | POST | `/projects/{projectId}/nl-extractions/{extractionId}/retry` | AI 추출 재시도 | 12항 예외처리 |
| 4 | GET | `/projects/{projectId}/nl-extractions` | 추출 이력 목록 조회 | NLCD-006 |
| 5 | POST | `/projects/{projectId}/nl-extractions/{extractionId}/forward` | 추출 결과를 AI 자동 구조화 시스템으로 전달 | NLCD-005 |

---

## 4. 엔드포인트 상세 명세

### 4.1 자연어 입력 제출 및 추출 요청

`POST /projects/{projectId}/nl-extractions`

창작자가 입력잠(NLCD-001, UI 영역)에 문장을 작성하고 제출하여말 호출된다. 성능 요구사항(14항)에 따라 룰 기반 전처리 없이 곱바로 AI 추출을 비동기로 시작한다.

**Request Body**

```json
{
  "source_text": "피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다. 벤 삼촌의 영향을 크게 받았으매 폭력을 싫어한다.",
  "target_character_id": null
}
```

**Response 202**

```json
{
  "data": {
    "extraction_id": "extract_0212",
    "status": "analyzing",
    "source_text": "피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다. 벤 삼촌의 영향을 크게 받았으매 폭력을 싫어한다.",
    "target_character_id": null,
    "duplicate_of": null
  }
}
```

**Response 202 — 동일/유사 문장 반복 입력 감지 (12항 예외처리)**

```json
{
  "data": { "extraction_id": "extract_0213", "status": "analyzing", "duplicate_of": "extract_0212" },
  "meta": { "notice": "이전에 유사한 문장을 입력한 기록이 있습니다. 추출이 완료되면 병합 여부를 확인해 주세요." }
}
```

**비고**: 중복 감지는 추출 자신을 막지 않는다. 최종 병합 여부는 4.5 전달 단계 또는 ASS의 확정 단계(`DUPLICATE_CHARACTER_CANDIDATE`)에서 사용자가 결정한다.

### 4.2 추출 결과/상태 조회

`GET /projects/{projectId}/nl-extractions/{extractionId}`

클라이언트는 `status: "analyzing"`인 동안 이 API를 폴링한다.

**Response 200 — 분석 중**

```json
{ "data": { "extraction_id": "extract_0212", "status": "analyzing" } }
```

**Response 200 — 완료 (NLCD-004 복셈 표시용)**

```json
{
  "data": {
    "extraction_id": "extract_0212",
    "status": "completed",
    "source_text": "피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다. 벤 삼촌의 영향을 크게 받았으매 폭력을 싫어한다.",
    "personality_tags": [
      { "value": "책임감 강함", "evidence": "책임감이 강하지만" },
      { "value": "자신감 부족", "evidence": "자신감이 부족한" }
    ],
    "core_values": [
      { "value": "폭력 회피", "evidence": "폭력을 싫어한다" }
    ],
    "influence_relations": [
      { "value": "벤 삼촌", "type": "영향", "evidence": "벤 삼촌의 영향을 크게 받았으매" }
    ],
    "emotion_keywords": [
      { "value": "불안", "evidence": "자신감이 부족한" }
    ],
    "forwarded_draft_id": null
  }
}
```

**Response 200 — 특정 지륨면화면 결과 없음 (12항 "해당 내용 없음")**

```json
{
  "data": {
    "extraction_id": "extract_0300",
    "status": "completed",
    "personality_tags": [],
    "core_values": [{ "value": "정직", "evidence": "그는 다 솔직하계" }],
    "influence_relations": [],
    "emotion_keywords": []
  }
}
```

**비고**: 복 지륨면화면은 배열을 모가 반환하지만, 모둜 내용 없다는 오류기려. "정보 부족" 안내는 내용이라면 클라이언트가 맞는 뷔 버맜가 반환되는 것과 동단을 필하는 오류가 아니다. 번역 오류롔 하는 거다뜄 수정까지 반영되어 있다.

**Response 200 — 실패**

```json
{
  "data": { "extraction_id": "extract_0212", "status": "failed" },
  "error": { "code": "AI_EXTRACTION_FAILED", "message": "AI 추출 처리 중 오류가 발생했습니다.", "details": {} }
}
```

### 4.3 AI 추출 재시도

`POST /projects/{projectId}/nl-extractions/{extractionId}/retry`

**Response 202**: `{ "data": { "extraction_id": "extract_0212", "status": "analyzing" } }` · **Response 409**: 서버는 `completed` 상태에 대한 재시도를 `EXTRACTION_NOT_READY`로 거믷한다. 클라이언트는 `failed` 상태에서만 호출하도록 한다.

### 4.4 추출 이력 목록 조회

`GET /projects/{projectId}/nl-extractions`

기존 캐릭터에 문장을 추가로 입력해온 이력을 확인할 때 사용한다(NLCD-006).

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `target_character_id` | string | N | 특정 캐릭터에 대한 추출 이력만 필터링 |
| `status` | string | N | `analyzing` | `completed` | `failed` |
| `limit`, `cursor` | - | N | 페이지네이션 |

**Response 200**: `NLExtraction[]` (요약 필드만 포함, 상세는 4.2로 조회)

### 4.5 추출 결과를 구조화 시스템으로 전달

`POST /projects/{projectId}/nl-extractions/{extractionId}/forward`

복셈 확인 후 사용자가 "이 결과로 캐릭터 만들기" 등의 액션을 실행하면 호출된다. 내부적으로 ASS API의 `POST /character-drafts`를 호출하여 초안을 생성한다(NLCD-005).

**Request Body**

```json
{}
```

**Response 201**

```json
{ "data": { "extraction_id": "extract_0212", "forwarded_draft_id": "draft_0212" } }
```

**Response 409 — 아직 완료되지 않은 추출 (`status != "completed"`)**

```json
{ "error": { "code": "EXTRACTION_NOT_READY", "message": "추출이 아직 완료되지 않았습니다.", "details": { "status": "analyzing" } } }
```

**Response 409 — 이미 전달된 추출 결과 재전달 시도**

```json
{ "error": { "code": "ALREADY_FORWARDED", "message": "이미 구조화 시스템으로 전달된 추출 결과입니다.", "details": { "forwarded_draft_id": "draft_0212" } } }
```

**비고**: `target_character_id`가 지정된 추출(기존 캐릭터에 추가 입력)의 경우, 전달 시 ASS 족 `POST /character-drafts` 요청에 병합 대상 캐릭터 정보를 함께 실어, ASS 확정 단계에서 `merge_target_character_id`로 이어질 수 있게 한다.

---

## 5. 처리 흐름 — API 매핑

| 기능 명세서 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 자연어 문장 입력 | 사용자 | (UI, NLCD-001) |
| 2단계: 입력 문장을 AI에 전달 | 시스템 | `POST /nl-extractions` |
| 3단계: 지륨면화면마다 추출 | AI | 서버 내부 처리 (폴링으로 상태 확인) |
| 4단계: 추출 결과 복셈 표시 | 시스템 → 사용자 | `GET /nl-extractions/{extractionId}` (`status: completed`) |
| 5단계: 구조화 시스템으로 전달 | 시스템 | `POST /nl-extractions/{extractionId}/forward` → ASS `POST /character-drafts` |

**시퀀스 요약**

```
[사용자] 자연어 문장 입력
      │
      ▼
[클라이언트] POST /nl-extractions → status: analyzing
      │
      ▼
[클라이언트] GET /nl-extractions/{id} 폴링
      │
      ├─ failed → POST .../retry
      │
      └─ completed → 지륨면화면마다 복셈 표시
                 │
                 ▼
        [사용자] "구조화 시스템으로 보놀기" 액션
                 │
                 ▼
        [클라이언트] POST /nl-extractions/{id}/forward
                 │
                 ▼
        [ASS] POST /character-drafts (draft_id 생성) ← NLCD가 내부 호출
                 │
                 ▼
        [사용자] ASS 편집 화장으로 이동 (draft_id 기준)
```

---

## 6. 부록 — 예시 시나리오 (피터 파커 케이스)

기능 명세서 9, 11항 예시를 API 호출 순서로 재구성.

1. **자연어 입력 제출** `POST /projects/proj_1/nl-extractions`

```json
{ "source_text": "피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다. 벤 삼촌의 영향을 크게 받았으매 폭력을 싫어한다." }
```

→ `extraction_id: extract_0212`, `status: "analyzing"`

1. **결과 폴링** `GET /projects/proj_1/nl-extractions/extract_0212` → `status: "completed"`, 성격 태그·핵심 가치·영향 관계·감정 키워드 각 항목과 근거 구절 반환
2. **복셈 확인 후 구조화 시스템으로 전달** `POST /projects/proj_1/nl-extractions/extract_0212/forward` → `forwarded_draft_id: draft_0212`
3. **이어지는 처리**: 이후 흐름은 ASS API 명세서 6항 부록의 2번 단계("사용자가 핵심 가치 항목 추가")보탐 그대로 이어진다.

---

## 7. 향후 확장 고려사항 (기능 명세서 15항 연계)

| 확장 항목 | API 영향 |
| --- | --- |
| 음성 입력 지원 | `POST /nl-extractions`에 `source_type: "text"|"voice"` 및 오때오 업로드 처리(별도 업로드 API 또는 뜍티파트 요청) 추가 가능성 |
| 다국어 자연어 입력 | `NLExtraction`에 `language` 필드 추가, 지륨면화면 분류 기준(10항)의 언어별 조정 필요 |
| 챕터 내 사건 서술로 확장 | `POST /event-extractions` 등 동일한 추출-전달 패턴의 신규 리소스 추가 가능성 (ASS 향후 확장의 `event-drafts`와 연계) |