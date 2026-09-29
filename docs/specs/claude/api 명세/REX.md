**Rule Extraction (REX) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 규칙 추출 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 규칙 추출 기능 명세서 v0.1 |
| 관련 모듈 | 원고 업로드(MSU), 설정 충돌 감지(SCDS) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> SCDS/NLCD API 명세서와 동일한 공통 규격을 따릅니다. AI 호출이 있으므로 NLCD와 동일하게 **작업 생성 → 폴링** 방식의 비동기 처리로 설계했습니다. 원본 기능 명세서는 "원고에서 세계관 중심 규칙을 추출하고 사용자가 임의로 수정 가능"이라고만 정의하고 있어, 세부 상태값과 오류 처리는 합리적으로 가정한 사항입니다.
> 

<aside>
⚠️

**모델 재사용 안내**: 이 문서의 확정 산출물은 SCDS API 명세서의 `WorldRule` 모델(2.2)과 동일한 리소스다. REX는 `WorldRule`의 생성(추출/직접 추가)·수정·삭제를 담당하고, SCDS는 이를 참조하여 충돌 판정에 사용한다. 구현 시 두 문서의 `WorldRule` 필드 정의를 반드시 통일해야 한다.

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

**성공**: `{ "data": { }, "meta": { } }` · **실패**: `{ "error": { "code": "...", "message": "...", "details": {} } }`

### 1.4 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `MANUSCRIPT_NOT_FOUND` | 404 | 대상 원고 없음 |
| `RULE_EXTRACTION_NOT_FOUND` | 404 | 추출 작업(job) 없음 |
| `WORLD_RULE_NOT_FOUND` | 404 | 규칙 리소스 없음 |
| `EXTRACTION_NOT_READY` | 409 | 추출 완료 전 확정 시도 |
| `AI_EXTRACTION_FAILED` | 502 | AI 추출 호출 실패 |
| `AI_EXTRACTION_TIMEOUT` | 503 | AI 추출 응답 지연 |

---

## 2. 데이터 모델

### 2.1 RuleExtraction (추출 작업)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `extraction_id` | string | Y | 추출 작업 고유 ID |
| `manuscript_id` | string | Y | 대상 원고 ID |
| `status` | string | Y | `queued` | `running` | `completed` | `failed` (DB `ops.jobs.status`) |
| `extracted_rules` | object[] | N | 완료 시 `[{title, description, violation_keywords, evidence, source_chapter}]`. `title`은 AI가 만드는 규칙 제목(최대 200자) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.2 WorldRule (SCDS 2.2와 동일 리소스, 필드 확장)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `rule_id` | string | Y | 규칙 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `title` | string | Y | 규칙 제목, 최대 200자 (DB `world_rules.title` NOT NULL). AI 추출 시 `extracted_rules[].title`을 그대로 쓴다 |
| `description` | string | Y | 규칙 설명 |
| `violation_keywords` | string[] | N | 위반 판정 키워드 (SCDS RULE-02 판정에 사용) |
| `origin` | string | Y | `ai_extracted` | `user_added` |
| `extraction_id` | string | null | N | AI 추출로 생성된 경우 근거 작업 ID |
| `evidence` | string | null | N | 원문 근거 문장(AI 추출 시) |
| `updated_at` | string(ISO8601) | Y | 수정 시각(사용자 편집 포함) |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | POST | `/projects/{projectId}/manuscripts/{manuscriptId}/rule-extractions` | 규칙 추출 요청 (비동기 시작) |
| 2 | GET | `.../rule-extractions/{extractionId}` | 추출 상태/결과 폴링 |
| 3 | POST | `.../rule-extractions/{extractionId}/retry` | 추출 재시도 (`failed` 상태에서만) |
| 4 | POST | `.../rule-extractions/{extractionId}/confirm` | 추출 결과 중 선택 항목을 `WorldRule`로 확정 저장 |
| 5 | GET | `/projects/{projectId}/world-rules` | 확정된 규칙 목록 조회 (SCDS와 공유) |
| 6 | POST | `/projects/{projectId}/world-rules` | 사용자가 직접 규칙 추가 |
| 7 | PATCH | `/projects/{projectId}/world-rules/{ruleId}` | 규칙 수정 (AI 추출본도 임의 수정 가능) |
| 8 | DELETE | `/projects/{projectId}/world-rules/{ruleId}` | 규칙 삭제 |

---

## 4. 엔드포인트 상세 명세

### 4.1 규칙 추출 요청

`POST /projects/{projectId}/manuscripts/{manuscriptId}/rule-extractions`

**Response 202**

```json
{ "data": { "extraction_id": "rex_701", "manuscript_id": "ms_301", "status": "queued" } }
```

### 4.2 추출 상태/결과 폴링

`GET /projects/{projectId}/manuscripts/{manuscriptId}/rule-extractions/{extractionId}`

**Response 200 — 완료**

```json
{
  "data": {
    "extraction_id": "rex_701",
    "status": "completed",
    "extracted_rules": [
      { "title": "계약 마법", "description": "마법은 계약 없이 발현될 수 없다", "violation_keywords": ["즉흥 마법", "무계약 시전"], "evidence": "모든 주문은 정령과의 계약을 통해서만...", "source_chapter": 2 }
    ]
  }
}
```

**Response 200 — 진행 중**: `status: "running"`, `extracted_rules: []`

**Response 200 — 실패**: `status: "failed"`, `error.code: "AI_EXTRACTION_FAILED"`

**비고**: 원문에 규칙으로 볼 내용이 없으면 오류가 아니라 `extracted_rules: []`로 `completed` 처리한다.

### 4.3 추출 재시도

`POST .../rule-extractions/{extractionId}/retry` — **Response 202**: `status: "queued"` · **Response 409**: 이미 `completed`인 작업 재시도 시 `EXTRACTION_NOT_READY`는 해당 없음(완료본 재추출은 신규 추출 요청 4.1 사용을 권장)

### 4.4 추출 결과 확정

`POST .../rule-extractions/{extractionId}/confirm`

**Request Body**

```json
{ "selected_indices": [0], "edits": { "0": { "title": "계약 마법", "description": "마법은 반드시 정령과의 계약을 통해서만 발현된다" } } }
```

**Response 201**: 확정된 `WorldRule[]` 반환(각 `origin: "ai_extracted"`, `extraction_id` 포함) · **Response 409**: `status`가 `completed`가 아니면 `EXTRACTION_NOT_READY`

### 4.5 확정 규칙 목록 조회

`GET /projects/{projectId}/world-rules` — SCDS 4.4와 동일 응답 구조, `origin`/`extraction_id` 필드 포함하여 반환

### 4.6 사용자 직접 규칙 추가

`POST /projects/{projectId}/world-rules`

**Request Body**: `{ "title": "...", "description": "...", "violation_keywords": ["..."] }` (`title` 필수, 최대 200자) → **Response 201**: `origin: "user_added"`

### 4.7 규칙 수정

`PATCH /projects/{projectId}/world-rules/{ruleId}` — AI 추출본 여부와 무관하게 사용자가 자유롭게 수정 가능(원본 명세 "사용자 임의로 수정 가능") · **Response 200**: 갱신된 `WorldRule`

### 4.8 규칙 삭제

`DELETE /projects/{projectId}/world-rules/{ruleId}` — **Response 204** · **비고**: 삭제된 규칙은 SCDS의 룰 기반 검출에서 즉시 제외된다

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 원고 준비 완료 | MSU | `Manuscript.status = ready` |
| 2단계: 규칙 추출 요청·대기 | 사용자 → AI | `POST rule-extractions` → `GET rule-extractions/{id}` 폴링 |
| 3단계: 사용자 검토 후 확정/직접 추가 | 사용자 | `POST .../confirm`, `POST /world-rules` |
| 4단계: 규칙 수정·삭제 | 사용자 | `PATCH/DELETE /world-rules/{id}` |
| 5단계: 타 모듈이 규칙 참조 | SCDS | `GET /world-rules` |

---

## 6. 부록 — 예시 시나리오

1. **추출 요청** `POST /projects/proj_1/manuscripts/ms_301/rule-extractions` → `extraction_id: rex_701`, `status: queued`
2. **결과 폴링** `GET .../rule-extractions/rex_701` → `status: completed`, 규칙 1건 추출
3. **일부 수정 후 확정** `POST .../rule-extractions/rex_701/confirm` `{ "selected_indices": [0], "edits": {"0": {"description": "...계약을 통해서만 발현된다"}} }` → `WorldRule` 저장
4. **이후 사용자가 규칙 문구를 추가로 수정** `PATCH /projects/proj_1/world-rules/wr_001`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| SCDS와의 데이터 모델 통합 | `WorldRule` 스키마를 단일 소스로 관리하는 공유 서비스/문서 필요 |
| 챕터 추가 시 증분 추출 | `POST rule-extractions?since_chapter=N` 형태의 부분 추출 지원 |
| 규칙 간 모순 감지 | 추출된 규칙끼리 상충 시 경고하는 검증 단계 추가 |