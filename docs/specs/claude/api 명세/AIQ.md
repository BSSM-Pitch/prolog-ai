**AI Q&A (AIQ) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | AI 질문 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | AI 질문 기능 명세서 v0.1 |
| 관련 모듈 | 원고 업로드(MSU), 원고 에디터 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격을 따릅니다. 원본 기능 명세서는 "원고 전체 또는 드래그한 일부에 대해 챗봇에게 질문 가능"이라고만 정의하고 있어, 대화 스레드 구조와 비동기 처리 방식은 합리적으로 가정한 사항입니다.
> 
- AI 응답은 지연 가능성이 있으므로 메시지 전송 후 **폴링**으로 답변 완료를 확인하는 방식으로 설계했습니다.

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
| `INVALID_INPUT` | 400 | 요청 본문 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근 권한 없음 |
| `MANUSCRIPT_NOT_FOUND` | 404 | 대상 원고 없음 |
| `QA_THREAD_NOT_FOUND` | 404 | 질문 스레드 없음 |
| `QA_MESSAGE_NOT_FOUND` | 404 | 메시지 없음 |
| `INVALID_SELECTION_RANGE` | 400 | `scope=selection`인데 범위가 원고 길이를 벗어남 |
| `AI_RESPONSE_FAILED` | 502 | AI 응답 생성 실패 |
| `AI_RESPONSE_TIMEOUT` | 503 | AI 응답 지연 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`)

---

## 2. 데이터 모델

### 2.1 QAThread (질문 스레드)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `thread_id` | string | Y | 스레드 고유 ID |
| `manuscript_id` | string | Y | 대상 원고 ID |
| `scope` | string | Y | `whole`(원고 전체) | `selection`(드래그 일부) |
| `selection_range` | object | null | N | `{start, end}` 문자 오프셋, `scope=selection`일 때 필수 |
| `title` | string | null | N | 스레드 제목(첫 질문으로 자동 생성 가능) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.2 QAMessage

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `message_id` | string | Y | 메시지 고유 ID |
| `thread_id` | string | Y | 소속 스레드 ID |
| `role` | string | Y | `user` | `assistant` |
| `content` | string | Y | 메시지 본문(질문 또는 답변) |
| `status` | string | Y | `pending` | `completed` | `failed` (assistant 메시지에만 의미 있음) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | GET | `/projects/{projectId}/manuscripts/{manuscriptId}/qa-threads` | 질문 스레드 목록 조회 |
| 2 | POST | `.../qa-threads` | 스레드 생성 + 첫 질문 전송 |
| 3 | GET | `.../qa-threads/{threadId}` | 스레드 상세(메시지 이력 포함) 조회 |
| 4 | POST | `.../qa-threads/{threadId}/messages` | 스레드에 후속 질문 추가 |
| 5 | GET | `.../qa-threads/{threadId}/messages/{messageId}` | 특정 메시지(답변) 상태 폴링 |
| 6 | POST | `.../qa-threads/{threadId}/messages/{messageId}/retry` | 답변 생성 재시도 (`failed` 상태에서만) |
| 7 | DELETE | `.../qa-threads/{threadId}` | 스레드 삭제 |

---

## 4. 엔드포인트 상세 명세

### 4.1 질문 스레드 목록 조회

`GET /projects/{projectId}/manuscripts/{manuscriptId}/qa-threads` — **Response 200**: `QAThread[]`(마지막 메시지 미리보기 포함)

### 4.2 스레드 생성 + 첫 질문

`POST /projects/{projectId}/manuscripts/{manuscriptId}/qa-threads`

**Request Body — 전체 원고 대상**

```json
{ "scope": "whole", "question": "주인공의 동기가 후반부에서 일관되게 유지되나요?" }
```

**Request Body — 드래그한 일부 대상**

```json
{ "scope": "selection", "selection_range": { "start": 1200, "end": 1580 }, "question": "이 문단의 어조가 앞부분과 어울리나요?" }
```

**Response 201**

```json
{
  "data": {
    "thread": { "thread_id": "qa_501", "scope": "selection", "selection_range": { "start": 1200, "end": 1580 } },
    "messages": [
      { "message_id": "msg_1", "role": "user", "content": "이 문단의 어조가...", "status": "completed" },
      { "message_id": "msg_2", "role": "assistant", "content": null, "status": "pending" }
    ]
  }
}
```

**Response 400**: `scope=selection`인데 `selection_range` 누락/범위 오류 시 `INVALID_SELECTION_RANGE`

### 4.3 스레드 상세 조회

`GET .../qa-threads/{threadId}` — **Response 200**: `QAThread` + 전체 `messages[]` (시간순)

### 4.4 후속 질문 추가

`POST .../qa-threads/{threadId}/messages`

**Request Body**: `{ "content": "그럼 3장에서 수정한다면 어떤 방향이 좋을까요?" }` → **Response 201**: 신규 user 메시지 + `status: pending`인 assistant 메시지

### 4.5 메시지(답변) 상태 폴링

`GET .../qa-threads/{threadId}/messages/{messageId}`

**Response 200 — 완료**

```json
{ "data": { "message_id": "msg_2", "role": "assistant", "content": "전반적으로 유지되나, 3장에서...", "status": "completed" } }
```

**Response 200 — 대기 중**: `status: "pending"`, `content: null`

### 4.6 답변 재시도

`POST .../messages/{messageId}/retry` — **Response 202**: `status: "pending"`으로 재설정 · **Response 409**: 이미 `completed`인 메시지 재시도 시 `INVALID_STATUS_TRANSITION`

### 4.7 스레드 삭제

`DELETE .../qa-threads/{threadId}` — **Response 204**

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 질문 범위 선택(전체/드래그) | 사용자 | `POST qa-threads` (`scope`) |
| 2단계: AI 응답 생성 대기 | AI | `GET .../messages/{id}` 폴링 |
| 3단계: 답변 확인, 후속 질문 | 사용자 | `POST .../messages` |
| 4단계: 실패 시 재시도 | 사용자 | `POST .../messages/{id}/retry` |

---

## 6. 부록 — 예시 시나리오

1. **일부 드래그하여 질문** `POST /projects/proj_1/manuscripts/ms_301/qa-threads` `{ "scope": "selection", "selection_range": {"start":1200,"end":1580}, "question": "이 문단의 어조가 앞부분과 어울리나요?" }` → `thread_id: qa_501`
2. **답변 폴링** `GET .../qa-threads/qa_501/messages/msg_2` → `status: completed`
3. **후속 질문** `POST .../qa-threads/qa_501/messages` `{ "content": "3장에서는 어떤 방향이 좋을까요?" }`
4. **원고 전체에 대한 새 질문(별도 스레드)** `POST .../qa-threads` `{ "scope": "whole", "question": "복선 회수가 잘 되었나요?" }`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 실시간 스트리밍 응답 | 폴링 대신 WebSocket/SSE로 토큰 단위 전송 전환 |
| 규칙 추출(REX)·설정 충돌 감지(SCDS) 데이터 연계 | 질문 컨텍스트에 확정 규칙/캐릭터 설정을 함께 전달하는 옵션 추가 |
| 즐겨찾기/북마크 | 유용한 질답을 별도로 표시하는 `PATCH .../messages/{id}/bookmark` 추가 가능성 |