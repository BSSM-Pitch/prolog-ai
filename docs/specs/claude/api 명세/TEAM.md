**Team Management (TEAM) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 팀 생성 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 팀 생성 기능 명세서 v0.1 |
| 관련 모듈 | 회원 관리(AUTH), 프로젝트 생성(PRJ), 알림(NOTI) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격을 따릅니다. 원본 기능 명세서는 "협업 창작을 위해 팀을 만들어 팀원을 초대하고, 팀 내부에서 여러 프로젝트를 생성하며 해당 프로젝트는 팀 프로젝트 속성을 가진다"만 정의하고 있어, 세부 권한·초대 흐름은 합리적으로 가정한 사항입니다.
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
| `FORBIDDEN` | 403 | 팀 접근/관리 권한 없음 |
| `TEAM_NOT_FOUND` | 404 | 팀 없음 |
| `TEAM_MEMBER_NOT_FOUND` | 404 | 팀 멤버 없음 |
| `TEAM_INVITATION_NOT_FOUND` | 404 | 초대 없음 |
| `ALREADY_TEAM_MEMBER` | 409 | 이미 소속된 사용자 재초대 |
| `INVITATION_EXPIRED` | 410 | 만료된 초대 수락 시도 |
| `LAST_OWNER_CANNOT_LEAVE` | 409 | 유일한 owner의 탈퇴/제거/강등 시도 |
| `TEAM_HAS_ACTIVE_PROJECTS` | 409 | 진행 중인 팀 프로젝트가 있어 팀 삭제 불가 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`)

---

## 2. 데이터 모델

### 2.1 Team

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `team_id` | string | Y | 팀 고유 ID |
| `name` | string | Y | 팀 이름 |
| `description` | string | null | N | 팀 소개 |
| `created_by` | string | Y | 생성자 `user_id` (자동으로 `owner`가 됨) |
| `member_count` | integer | Y | 팀원 수 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.2 TeamMember

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `team_id` | string | Y | 팀 ID |
| `user_id` | string | Y | 사용자 ID |
| `role` | string | Y | `owner` | `admin` | `member` |
| `joined_at` | string(ISO8601) | Y | 합류 시각 |

### 2.3 TeamInvitation

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `invitation_id` | string | Y | 초대 고유 ID |
| `team_id` | string | Y | 대상 팀 ID |
| `invited_email` | string | Y | 초대받은 이메일 |
| `role` | string | Y | 부여될 역할(`admin`|`member`) |
| `status` | string | Y | `pending` | `accepted` | `expired` | `revoked` |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `expires_at` | string(ISO8601) | Y | 만료 시각 (기본 7일) |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | GET | `/teams` | 내가 속한 팀 목록 조회 |
| 2 | POST | `/teams` | 팀 생성 |
| 3 | GET | `/teams/{teamId}` | 팀 상세 조회 |
| 4 | PATCH | `/teams/{teamId}` | 팀 정보 수정 |
| 5 | DELETE | `/teams/{teamId}` | 팀 삭제 |
| 6 | GET | `/teams/{teamId}/members` | 팀원 목록 조회 |
| 7 | POST | `/teams/{teamId}/invitations` | 팀원 초대 |
| 8 | GET | `/teams/{teamId}/invitations` | 대기 중인 초대 목록 조회 |
| 9 | POST | `/teams/{teamId}/invitations/{invitationId}/accept` | 초대 수락 |
| 10 | DELETE | `/teams/{teamId}/invitations/{invitationId}` | 초대 취소 |
| 11 | PATCH | `/teams/{teamId}/members/{userId}` | 팀원 역할 변경 |
| 12 | DELETE | `/teams/{teamId}/members/{userId}` | 팀원 제거/팀 탈퇴 |
| 13 | GET | `/teams/{teamId}/projects` | 팀 소속 프로젝트 목록 조회 (PRJ `GET /projects?team_id=`와 동일 데이터) |

---

## 4. 엔드포인트 상세 명세

### 4.1 내 팀 목록 조회

`GET /teams` — **Response 200**: `Team[]`

### 4.2 팀 생성

`POST /teams`

**Request Body**: `{ "name": "StoryForge 창작팀", "description": "공동 세계관 작업" }` → **Response 201**: 생성자를 `role: owner`인 `TeamMember`로 자동 등록

### 4.3 팀 상세 조회

`GET /teams/{teamId}` — **Response 200**: `Team` · **Response 403**: 비멤버 접근 시 `FORBIDDEN`

### 4.4 팀 정보 수정

`PATCH /teams/{teamId}` — `owner`|`admin`만 가능 · **Request Body**: `{ "name": "...", "description": "..." }`

### 4.5 팀 삭제

`DELETE /teams/{teamId}` — `owner`만 가능 · **Response 409**: 진행 중인 팀 프로젝트가 있으면 `TEAM_HAS_ACTIVE_PROJECTS`(먼저 PRJ에서 프로젝트를 이전/삭제해야 함) · **Response 204**: 성공 시 팀·멤버·초대 이력 삭제

### 4.6 팀원 목록 조회

`GET /teams/{teamId}/members` — **Response 200**: `TeamMember[]`(사용자 이름 포함)

### 4.7 팀원 초대

`POST /teams/{teamId}/invitations`

**Request Body**: `{ "invited_email": "writer2@example.com", "role": "member" }` → **Response 201**: `TeamInvitation`(`status: pending`, `expires_at`: 7일 후) · **Response 409**: 이미 팀원이면 `ALREADY_TEAM_MEMBER`

**비고**: 초대 생성 시 알림 기능(NOTI)을 통해 대상자에게 알림이 발송된다. 미가입 이메일이면 회원가입 유도 알림으로 대체된다(AUTH 연계).

### 4.8 대기 중인 초대 목록

`GET /teams/{teamId}/invitations` — `owner`|`admin`만 조회 가능 · **Response 200**: `TeamInvitation[]`

### 4.9 초대 수락

`POST /teams/{teamId}/invitations/{invitationId}/accept` — **Response 200**: `TeamMember`(`role: member`) 생성 · **Response 410**: 만료된 초대는 `INVITATION_EXPIRED`

### 4.10 초대 취소

`DELETE /teams/{teamId}/invitations/{invitationId}` — **Response 204**: `status: revoked`

### 4.11 팀원 역할 변경

`PATCH /teams/{teamId}/members/{userId}` — **Request Body**: `{ "role": "admin" }` · **Response 409**: 유일한 `owner`를 강등 시도 시 `LAST_OWNER_CANNOT_LEAVE`

### 4.12 팀원 제거/탈퇴

`DELETE /teams/{teamId}/members/{userId}` — 본인 탈퇴 또는 `owner`|`admin`의 팀원 제거 · **Response 409**: 유일한 owner 본인 탈퇴 시 `LAST_OWNER_CANNOT_LEAVE`

### 4.13 팀 소속 프로젝트 목록

`GET /teams/{teamId}/projects` — **Response 200**: `Project[]` (`owner_type: team`, 해당 `team_id`)

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 팀 생성 | 사용자 | `POST /teams` |
| 2단계: 팀원 초대·수락 | owner/admin → 피초대자 | `POST /invitations` → NOTI 알림 → `POST .../accept` |
| 3단계: 팀 내부에 프로젝트 생성 | 팀원 | PRJ `POST /projects` (`owner_type: team`) |
| 4단계: 팀 프로젝트 목록 확인 | 팀원 | `GET /teams/{teamId}/projects` |

---

## 6. 부록 — 예시 시나리오

1. **팀 생성** `POST /teams` `{ "name": "StoryForge 창작팀" }` → `team_id: team_10`, 생성자 `role: owner`
2. **팀원 초대** `POST /teams/team_10/invitations` `{ "invited_email": "writer2@example.com", "role": "member" }`
3. **피초대자 수락** `POST /teams/team_10/invitations/inv_9/accept` → `TeamMember` 등록
4. **팀 내부 프로젝트 생성(PRJ 연계)** `POST /projects` `{ "title": "공동 세계관", "owner_type": "team", "team_id": "team_10" }`
5. **팀 프로젝트 목록 확인** `GET /teams/team_10/projects`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 팀 내 세부 권한 커스터마이징 | 역할별 권한 매트릭스를 관리하는 `PATCH /teams/{teamId}/roles` 추가 가능성 |
| 팀 소유권 이전 | `POST /teams/{teamId}/transfer-ownership` 신규 엔드포인트 |
| 팀 활동 로그 | `GET /teams/{teamId}/activity-log` 추가 가능성 |