**Notification (NOTI) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 알림 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 알림 기능 명세서 v0.1 |
| 관련 모듈 | 회원 관리(AUTH), 프로젝트 생성(PRJ), 팀 생성(TEAM) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격을 따릅니다. 원본 기능 명세서는 "팀 참가 등 이벤트에 대해 서비스 내부 알림을 제공하며, 연동한 gmail/네이버 메일로도 알림을 받을 수 있다"만 정의하고 있어, 알림 생성·구독 설정·이메일 연동 구조는 합리적으로 가정한 사항입니다. 알림 자체는 시스템 내부 이벤트(초대, 멘션 등)로 생성되므로 공개 생성 API는 두지 않는다.
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
| `NOTIFICATION_NOT_FOUND` | 404 | 알림 리소스 없음(타인의 알림 포함) |
| `EMAIL_INTEGRATION_NOT_FOUND` | 404 | 이메일 연동 정보 없음 |
| `OAUTH_PROVIDER_ERROR` | 502 | gmail/네이버 인증 공급자 오류 |
| `EMAIL_ALREADY_CONNECTED` | 409 | 이미 동일 제공자 계정이 연동됨 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`)

---

## 2. 데이터 모델

### 2.1 Notification

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `notification_id` | string | Y | 알림 고유 ID |
| `user_id` | string | Y | 수신자 ID |
| `type` | string | Y | `team_invite` | `project_invite` | `team_joined` | `mention` | `system` 등 |
| `title` | string | Y | 알림 제목 |
| `body` | string | Y | 알림 내용 |
| `related_ref` | object | null | N | `{type, id}` 관련 리소스(예: `{type:"team_invitation", id:"inv_9"}`) |
| `channels_sent` | string[] | Y | 실제 발송된 채널 `["in_app", "email"]` |
| `read_at` | string(ISO8601) | null | N | 읽음 처리 시각 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.2 NotificationSetting

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `type` | string | Y | 알림 유형 (2.1 `type`과 동일 enum) |
| `in_app_enabled` | boolean | Y | 서비스 내부 알림 수신 여부 (기본 `true`) |
| `email_enabled` | boolean | Y | 이메일 알림 수신 여부 (기본 `true`, 연동 계정이 없으면 무시) |

### 2.3 EmailIntegration

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `integration_id` | string | Y | 연동 고유 ID |
| `provider` | string | Y | `gmail` | `naver` |
| `email_address` | string | Y | 연동된 이메일 주소 |
| `connected_at` | string(ISO8601) | Y | 연동 시각 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | GET | `/notifications` | 내 알림 목록 조회 (읽음/안읽음 필터) |
| 2 | GET | `/notifications/{notificationId}` | 알림 상세 조회 |
| 3 | PATCH | `/notifications/{notificationId}` | 읽음 처리 |
| 4 | PATCH | `/notifications/read-all` | 전체 읽음 처리 |
| 5 | DELETE | `/notifications/{notificationId}` | 알림 삭제 |
| 6 | GET | `/users/me/notification-settings` | 알림 유형별 채널 설정 조회 |
| 7 | PATCH | `/users/me/notification-settings` | 알림 유형별 채널 설정 변경 |
| 8 | GET | `/users/me/email-integrations` | 연동된 이메일 계정 목록 조회 |
| 9 | POST | `/users/me/email-integrations` | gmail/네이버 이메일 계정 연동 (OAuth) |
| 10 | DELETE | `/users/me/email-integrations/{integrationId}` | 이메일 연동 해제 |

---

## 4. 엔드포인트 상세 명세

### 4.1 알림 목록 조회

`GET /notifications`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `unread_only` | boolean | N | 안읽은 알림만 조회 (기본 `false`) |
| `type` | string | N | 알림 유형 필터 |

**Response 200**

```json
{
  "data": [
    { "notification_id": "noti_1", "type": "team_invite", "title": "팀 초대", "body": "'StoryForge 창작팀'에서 초대했습니다", "related_ref": { "type": "team_invitation", "id": "inv_9" }, "channels_sent": ["in_app", "email"], "read_at": null, "created_at": "2026-08-30T09:00:00Z" }
  ],
  "meta": { "next_cursor": null, "unread_count": 1 }
}
```

### 4.2 알림 상세 조회

`GET /notifications/{notificationId}` — **Response 200**: `Notification` · **Response 404**: `NOTIFICATION_NOT_FOUND`

### 4.3 읽음 처리

`PATCH /notifications/{notificationId}` — **Request Body**: `{ "read": true }` → **Response 200**: `read_at` 설정된 `Notification`

### 4.4 전체 읽음 처리

`PATCH /notifications/read-all` — **Response 200**: `{ "data": { "updated_count": 5 } }`

### 4.5 알림 삭제

`DELETE /notifications/{notificationId}` — **Response 204**

### 4.6 알림 설정 조회

`GET /users/me/notification-settings` — **Response 200**: `NotificationSetting[]` (유형별)

### 4.7 알림 설정 변경

`PATCH /users/me/notification-settings`

**Request Body**: `{ "type": "team_invite", "in_app_enabled": true, "email_enabled": false }` → **Response 200**: 갱신된 `NotificationSetting`

### 4.8 연동된 이메일 계정 목록

`GET /users/me/email-integrations` — **Response 200**: `EmailIntegration[]`

### 4.9 이메일 계정 연동

`POST /users/me/email-integrations`

**Request Body**: `{ "provider": "gmail", "oauth_code": "authcode_from_provider" }` → **Response 201**: `EmailIntegration` · **Response 409**: 동일 제공자 계정이 이미 연동되어 있으면 `EMAIL_ALREADY_CONNECTED` · **Response 502**: `OAUTH_PROVIDER_ERROR`

### 4.10 이메일 연동 해제

`DELETE /users/me/email-integrations/{integrationId}` — **Response 204**: 해제 이후 신규 알림은 `in_app`으로만 발송

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 이벤트 발생(팀 초대 등) | PRJ/TEAM | 내부적으로 `Notification` 레코드 생성(공개 API 없음) |
| 2단계: 채널별 발송 여부 결정 | 시스템 | `NotificationSetting` 조회 후 `channels_sent` 결정 |
| 3단계: 이메일 채널 발송(연동 시) | 시스템 | `EmailIntegration` 존재 시에만 실제 메일 발송 |
| 4단계: 사용자 확인 | 사용자 | `GET /notifications`, `PATCH .../{id}` |

**시퀀스 요약**

```
[TEAM] POST /teams/{teamId}/invitations
      │
      ▼
[서버] Notification(type=team_invite) 생성
      │
      ├─ NotificationSetting.in_app_enabled=true → 인앱 알림 노출
      │
      └─ NotificationSetting.email_enabled=true AND EmailIntegration 존재
                 │
                 ▼
           이메일 발송 (gmail/naver)
      │
      ▼
[사용자] GET /notifications → PATCH /notifications/{id} (읽음 처리)
```

---

## 6. 부록 — 예시 시나리오

1. **gmail 계정 연동** `POST /users/me/email-integrations` `{ "provider": "gmail", "oauth_code": "..." }` → `integration_id: eint_1`
2. **팀 초대 발생(TEAM 연계)** → `Notification` 자동 생성, `channels_sent: ["in_app", "email"]`
3. **알림 목록 확인** `GET /notifications?unread_only=true` → 팀 초대 알림 확인
4. **읽음 처리** `PATCH /notifications/noti_1` `{ "read": true }`
5. **멘션 알림은 이메일 끄기** `PATCH /users/me/notification-settings` `{ "type": "mention", "in_app_enabled": true, "email_enabled": false }`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 실시간 알림(푸시/웹소켓) | 폴링 대신 WebSocket/SSE 또는 브라우저 푸시 채널 추가 |
| 알림 유형 확장(충돌 감지·복선 미회수 등) | SCDS/FTS의 AI 디렉터 패널 이벤트를 `type`에 추가 연계 |
| 다이제스트 이메일 | 실시간 발송 대신 일간/주간 요약 메일 옵션 추가 |