**Manuscript Upload & Editor (MSU) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 원고 업로드 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 원고 업로드 기능 명세서 v0.1 |
| 관련 모듈 | 프로젝트 관리, 규칙 추출(REX), AI 질문(AIQ), 스토리 구조 지도(SSM) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> SCDS API 명세서와 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다. 원본 기능 명세서는 "완성 원고 파일 업로드"와 "에디터 내 직접 작성" 두 경로만 정의하고 있어, 아래 구조는 두 경로를 하나의 리소스(`Manuscript`)로 통합해 설계한 것입니다.
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

**성공**: `{ "data": { }, "meta": { } }` · **실패**: `{ "error": { "code": "...", "message": "...", "details": {} } }`

### 1.4 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `PROJECT_NOT_FOUND` | 404 | 프로젝트 없음 |
| `MANUSCRIPT_NOT_FOUND` | 404 | 원고 리소스 없음 |
| `CHAPTER_NOT_FOUND` | 404 | 챕터 리소스 없음 |
| `UNSUPPORTED_FILE_FORMAT` | 400 | 지원하지 않는 파일 형식 |
| `FILE_TOO_LARGE` | 413 | 업로드 파일 용량 초과 |
| `TEXT_EXTRACTION_FAILED` | 422 | 업로드 파일에서 텍스트 추출 실패 |
| `SOURCE_TYPE_IMMUTABLE` | 409 | 원고 생성 후 source_type(upload/editor) 변경 시도 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`)

---

## 2. 데이터 모델

### 2.1 Manuscript

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `manuscript_id` | string | Y | 원고 고유 ID |
| `project_id` | string | Y | 소속 프로젝트 ID |
| `title` | string | Y | 원고 제목 |
| `source_type` | string | Y | `upload`(업로드) | `editor`(에디터 작성), 생성 이후 불변 (DB `manuscripts_source_type_chk`) |
| `file_key` | string | null | N | `source_type=upload`일 때 저장소의 원본 파일 키 (URL은 만료되므로 키만 둔다) |
| `file_format` | string | null | N | `docx` | `txt` | `pdf` 등 |
| `content` | string | null | N | `source_type=editor`일 때 본문 텍스트(또는 업로드 후 추출된 텍스트) |
| `chapter_count` | integer | Y | 챕터 수 |
| `status` | string | Y | `draft`(업로드 원고의 파일 대기) | `processing`(파일 추출 중) | `ready` | `failed`(추출 실패) (DB `manuscripts_status_chk`) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 수정 시각(자동저장 포함) |

### 2.2 Chapter

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `chapter_id` | string | Y | 챕터 고유 ID |
| `manuscript_id` | string | Y | 소속 원고 ID |
| `chapter_no` | integer | Y | 챕터 순번 |
| `title` | string | null | N | 챕터 제목 |
| `content` | string | Y | 챕터 본문 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | GET | `/projects/{projectId}/manuscripts` | 원고 목록 조회 |
| 2 | POST | `/projects/{projectId}/manuscripts` | 원고 생성 (`source_type` 지정, 에디터 작성은 즉시 빈 본문으로 생성) |
| 3 | GET | `/projects/{projectId}/manuscripts/{manuscriptId}` | 원고 상세 조회 |
| 4 | PATCH | `/projects/{projectId}/manuscripts/{manuscriptId}` | 제목/본문 수정 (에디터 자동저장) |
| 5 | DELETE | `/projects/{projectId}/manuscripts/{manuscriptId}` | 원고 삭제 |
| 6 | POST | `/projects/{projectId}/manuscripts/{manuscriptId}/file` | 완성 원고 파일 업로드 (multipart, `source_type=upload` 전용) |
| 7 | GET | `/projects/{projectId}/manuscripts/{manuscriptId}/chapters` | 챕터 목록 조회 |
| 8 | POST | `/projects/{projectId}/manuscripts/{manuscriptId}/chapters` | 챕터 추가 |
| 9 | PATCH / DELETE | `.../chapters/{chapterId}` | 챕터 수정 / 삭제 |
| 10 | GET | `.../manuscripts/{manuscriptId}/versions` | 편집 이력(버전) 조회 (선택) |

---

## 4. 엔드포인트 상세 명세

### 4.1 원고 목록 조회

`GET /projects/{projectId}/manuscripts` — **Response 200**: `Manuscript[]` (페이지네이션)

### 4.2 원고 생성

`POST /projects/{projectId}/manuscripts`

**Request Body — 에디터 작성**

```json
{ "title": "거미줄 너머", "source_type": "editor" }
```

**Response 201**

```json
{ "data": { "manuscript_id": "ms_301", "title": "거미줄 너머", "source_type": "editor", "content": "", "chapter_count": 0, "status": "ready" } }
```

**Request Body — 파일 업로드 예정**: `{ "title": "거미줄 너머", "source_type": "upload" }` (`status: "draft"`로 생성, 4.6으로 실제 파일 업로드)

### 4.3 원고 상세 조회

`GET /projects/{projectId}/manuscripts/{manuscriptId}` — **Response 200**: `Manuscript` 객체 · **Response 404**: `MANUSCRIPT_NOT_FOUND`

### 4.4 제목/본문 수정 (자동저장)

`PATCH /projects/{projectId}/manuscripts/{manuscriptId}`

**Request Body**: `{ "content": "수정된 본문..." }` (일부 필드만 전송) · **Response 200**: 갱신된 `Manuscript` · **Response 409**: `source_type`을 변경 시도하면 `SOURCE_TYPE_IMMUTABLE`

### 4.5 원고 삭제

`DELETE /projects/{projectId}/manuscripts/{manuscriptId}` — **Response 204**: 챕터·연관 데이터 함께 삭제

### 4.6 원고 파일 업로드

`POST /projects/{projectId}/manuscripts/{manuscriptId}/file` (multipart/form-data, 필드명 `file`)

**Response 202 — 업로드 접수(텍스트 추출 진행)**

```json
{ "data": { "manuscript_id": "ms_301", "file_format": "docx", "status": "processing" } }
```

**Response 200 — 소용량 파일 즉시 완료**: `status: "ready"`, `content`에 추출된 텍스트 포함 · **Response 400**: `UNSUPPORTED_FILE_FORMAT` · **Response 413**: `FILE_TOO_LARGE`

**비고**: 처리 완료 여부는 4.3 상세 조회로 `status` 폴링하여 확인한다. 추출 실패 시 `status: "failed"`, `TEXT_EXTRACTION_FAILED` 오류가 `Manuscript.error` 필드에 기록된다(재업로드로 복구, 별도 재시도 API는 두지 않음).

### 4.7~4.9 챕터 CRUD

`GET/POST /chapters`, `PATCH/DELETE /chapters/{chapterId}` — 표준 CRUD. 챕터 삭제 시 복선 추적(FTS)에 연결된 복선이 있으면 해당 모듈이 참조 확인 후 재지정을 요청한다(FTS 문서 12항 참고).

### 4.10 편집 이력 조회 (선택)

`GET /projects/{projectId}/manuscripts/{manuscriptId}/versions` — 자동저장 스냅샷 이력 목록 반환

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 원고 생성 방식 선택 | 사용자 | `POST /manuscripts` (`source_type`) |
| 2-A: 파일 업로드 후 텍스트화 | 사용자 → 시스템 | `POST /manuscripts/{id}/file` → `status` 폴링 |
| 2-B: 에디터에서 직접 작성 | 사용자 | `PATCH /manuscripts/{id}` (자동저장) |
| 3단계: 챕터 구성 | 사용자 | `POST/PATCH /chapters` |
| 4단계: 완성된 원고를 타 모듈에 제공 | 시스템 | REX·AIQ·SSM이 `content`/`chapters`를 참조 |

---

## 6. 부록 — 예시 시나리오

1. **에디터 작성 원고 생성** `POST /projects/proj_1/manuscripts` `{ "title": "거미줄 너머", "source_type": "editor" }` → `manuscript_id: ms_301`
2. **자동저장** `PATCH /projects/proj_1/manuscripts/ms_301` `{ "content": "1화. ..." }`
3. **완성 원고 파일 업로드(다른 프로젝트)** `POST /projects/proj_2/manuscripts` `{ "title": "초고", "source_type": "upload" }` → `POST .../manuscripts/ms_302/file` (docx 첨부) → `status: "processing"`
4. **처리 완료 확인** `GET /projects/proj_2/manuscripts/ms_302` → `status: "ready"`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 공동 편집(실시간 협업) | WebSocket 기반 동시 편집 이벤트 스트림 추가 필요 |
| 편집 이력 되돌리기(undo) | `POST /manuscripts/{id}/versions/{versionId}/restore` 신규 엔드포인트 |
| 추가 파일 포맷 지원 | `file_format` enum 확장 및 포맷별 추출 파이프라인 추가 |
| 규칙 추출(REX)/AI 질문(AIQ) 트리거 | 원고 저장 완료 시 웹훅으로 자동 트리거하는 옵션 고려 |