**Project Management (PRJ) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 프로젝트 생성 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 프로젝트 생성 기능 명세서 v0.1 |
| 관련 모듈 | 회원 관리(AUTH), 팀 생성(TEAM), 원고 업로드(MSU), 알림(NOTI) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격을 따릅니다. 원본 기능 명세서는 "여러 프로젝트 생성 가능, 개인 또는 여러 사람과 공유하여 동시 작업 가능, 프로젝트 내에서 원고를 1개 이상 작성"만 정의하고 있어, 초대·권한 구조는 합리적으로 가정한 사항입니다. 다른 모든 모듈(SCDS/RCV/FTS/ASS/NLCD/REX/AIQ/SSM/MSU)의 `{projectId}` 경로 파라미터는 이 문서에서 생성되는 `Project` 리소스를 가리킨다.
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
| `INVALID_INPUT` | 400 | 요청 본문 오류 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 프로젝트 접근/수정 권한 없음 |
| `PROJECT_NOT_FOUND` | 404 | 프로젝트 없음 |
| `MEMBER_NOT_FOUND` | 404 | 프로젝트 멤버 없음 |
| `INVITATION_NOT_FOUND` | 404 | 초대 없음 |
| `TEAM_NOT_FOUND` | 404 | `owner_type=team`인데 팀이 존재하지 않음 |
| `NOT_TEAM_MEMBER` | 403 | 팀 소속이 아닌 사용자가 팀 프로젝트 생성 시도 |
| `ALREADY_MEMBER` | 409 | 이미 참여 중인 사용자를 재초대 |
| `LAST_OWNER_CANNOT_LEAVE` | 409 | 유일한 owner의 탈퇴/강등 시도 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`)

---

## 2. 데이터 모델

### 2.1 Project

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `project_id` | string | Y | 프로젝트 고유 ID |
| `title` | string | Y | 프로젝트(작품) 제목 |
| `owner_type` | string | Y | `personal`(개인) | `team`(팀 소속) |
| `team_id` | string | null | N | `owner_type=team`일 때 소속 팀 ID |
| `created_by` | string | Y | 생성자 `user_id` |
| `manuscript_count` | integer | Y | 포함된 원고 수 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 수정 시각 |

### 2.2 ProjectMember

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `project_id` | string | Y | 프로젝트 ID |
| `user_id` | string | Y | 사용자 ID |
| `role` | string | Y | `owner` | `editor` | `viewer` |
| `joined_at` | string(ISO8601) | Y | 참여 시각 |

### 2.3 ProjectInvitation

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `invitation_id` | string | Y | 초대 고유 ID |
| `project_id` | string | Y | 대상 프로젝트 ID |
| `invited_email` | string | Y | 초대받은 이메일 |
| `role` | string | Y | 부여될 역할(`editor`|`viewer`) |
| `status` | string | Y | `pending` | `accepted` | `expired` |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | GET | `/projects` | 내가 접근 가능한 프로젝트 목록 (개인 + 참여 팀) |
| 2 | POST | `/projects` | 프로젝트 생성 |
| 3 | GET | `/projects/{projectId}` | 프로젝트 상세 조회 |
| 4 | PATCH | `/projects/{projectId}` | 프로젝트 정보 수정 (제목 등) |
| 5 | DELETE | `/projects/{projectId}` | 프로젝트 삭제 |
| 6 | GET | `/projects/{projectId}/members` | 참여 멤버 목록 조회 |
| 7 | POST | `/projects/{projectId}/invitations` | 공동 작업자 초대 |
| 8 | POST | `/projects/{projectId}/invitations/{invitationId}/accept` | 초대 수락 |
| 9 | DELETE | `/projects/{projectId}/invitations/{invitationId}` | 초대 취소 |
| 10 | PATCH | `/projects/{projectId}/members/{userId}` | 멤버 역할 변경 |
| 11 | DELETE | `/projects/{projectId}/members/{userId}` | 멤버 제거/프로젝트 나가기 |

---

## 4. 엔드포인트 상세 명세

### 4.1 프로젝트 목록 조회

`GET /projects` — **Query**: `owner_type`(선택), `team_id`(선택) · **Response 200**: `Project[]`

### 4.2 프로젝트 생성

`POST /projects`

**Request Body — 개인 프로젝트**

```json
{ "title": "거미줄 너머", "owner_type": "personal" }
```

**Request Body — 팀 프로젝트**

```json
{ "title": "공동 세계관 프로젝트", "owner_type": "team", "team_id": "team_10" }
```

**Response 201**: 생성자를 `role: owner`인 `ProjectMember`로 자동 등록 · **Response 403**: `owner_type=team`인데 해당 팀 소속이 아니면 `NOT_TEAM_MEMBER`

### 4.3 프로젝트 상세 조회

`GET /projects/{projectId}` — **Response 200**: `Project` 객체 · **Response 403**: 멤버가 아니면 `FORBIDDEN`

### 4.4 프로젝트 정보 수정

`PATCH /projects/{projectId}` — `role: owner` | `editor`만 가능 · **Request Body**: `{ "title": "..." }`

### 4.5 프로젝트 삭제

`DELETE /projects/{projectId}` — `role: owner`만 가능 · **Response 204**: 포함된 원고·관련 데이터 함께 삭제(cascade)

### 4.6 멤버 목록 조회

`GET /projects/{projectId}/members` — **Response 200**: `ProjectMember[]` (사용자 이름 포함)

### 4.7 공동 작업자 초대

`POST /projects/{projectId}/invitations`

**Request Body**: `{ "invited_email": "friend@example.com", "role": "editor" }` → **Response 201**: `ProjectInvitation`(`status: pending`) · **Response 409**: 이미 멤버면 `ALREADY_MEMBER`

**비고**: 초대 생성 시 알림 기능(NOTI)을 통해 대상자에게 알림이 발송된다. 미가입 이메일이면 회원가입 유도 알림으로 대체된다.

### 4.8 초대 수락

`POST /projects/{projectId}/invitations/{invitationId}/accept` — **Response 200**: `ProjectMember` 생성, `invitation.status: accepted`

### 4.9 초대 취소

`DELETE /projects/{projectId}/invitations/{invitationId}` — **Response 204**

### 4.10 멤버 역할 변경

`PATCH /projects/{projectId}/members/{userId}` — **Request Body**: `{ "role": "viewer" }` · **Response 409**: 유일한 `owner`를 강등 시도 시 `LAST_OWNER_CANNOT_LEAVE`

### 4.11 멤버 제거/나가기

`DELETE /projects/{projectId}/members/{userId}` — 본인 탈퇴 또는 owner의 멤버 제거 · **Response 409**: 유일한 owner 본인 탈퇴 시 `LAST_OWNER_CANNOT_LEAVE`(먼저 소유권 위임 필요)

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 프로젝트 생성(개인/팀) | 사용자 | `POST /projects` |
| 2단계: 공동 작업자 초대 | owner/editor | `POST /invitations` → NOTI 알림 발송 |
| 3단계: 초대 수락 및 동시 작업 시작 | 피초대자 | `POST /invitations/{id}/accept` |
| 4단계: 프로젝트 내 원고 작성 | 멤버 | MSU `POST /projects/{projectId}/manuscripts` |

---

## 6. 부록 — 예시 시나리오

1. **개인 프로젝트 생성** `POST /projects` `{ "title": "거미줄 너머", "owner_type": "personal" }` → `project_id: proj_1`
2. **공동 작업자 초대** `POST /projects/proj_1/invitations` `{ "invited_email": "co-writer@example.com", "role": "editor" }`
3. **피초대자가 수락** `POST /projects/proj_1/invitations/inv_1/accept` → 이제 두 명이 함께 원고 작성 가능
4. **팀 프로젝트 생성(팀 생성 이후)** `POST /projects` `{ "title": "공동 세계관", "owner_type": "team", "team_id": "team_10" }`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 프로젝트 템플릿/복제 | `POST /projects/{projectId}/duplicate` 신규 엔드포인트 |
| 세부 권한(원고별 편집 제한) | `ProjectMember.role`을 원고 단위로 확장하는 정책 필요 |
| 활동 로그 | `GET /projects/{projectId}/activity-log` 추가 가능성 |