**Authentication & Account (AUTH) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 로그인/회원가입 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 로그인/ 회원가입 기능 명세서 v0.1 |
| 관련 모듈 | 회원 관리, 소셜 로그인 연동, 프로젝트/팀 접근 제어 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 원본 기능 명세서는 입력 요소(아이디·비밀번호·이메일·역할)와 간편 로그인 대체 가능 여부만 정의하고 있어, 아래 엔드포인트·에러 코드·데이터 모델은 다른 모듈과의 정합성을 고려해 합리적으로 가정한 사항입니다. 실제 구현 시 팀 컨벤션에 맞춰 조정이 필요합니다.
> 
- API 스타일: REST + JSON, 다른 모듈(SCDS/RCV/FTS/ASS/NLCD)과 동일한 공통 규격을 따름
- 인증 방식: Bearer Token (JWT, Access + Refresh)
- **로그인 수단은 Google OAuth 단일이다 (v0.2).** 로컬 비밀번호 가입/로그인과 네이버 로그인은 제거되었다.
- `POST /auth/oauth/google`, `POST /auth/signup`, `POST /auth/token/refresh`, `GET /users/check-username`을 제외한 모든 요청은 인증이 필요하다

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
{ "error": { "code": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다.", "details": {} } }
```

### 1.4 공통 에러 코드

| 코드 | HTTP 상태 | 설명 |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | 요청 본문 형식 오류 |
| `USERNAME_REQUIRED` | 400 | 최초 가입 시 아이디 누락(소셜 가입 포함) |
| `USERNAME_TAKEN` | 409 | 이미 사용 중인 아이디 |
| `SIGNUP_TICKET_INVALID` | 401 | 가입 티켓 만료/위조 |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `REFRESH_TOKEN_INVALID` | 401 | 리프레시 토큰 만료/폐기됨 |
| `OAUTH_PROVIDER_ERROR` | 502 | 소셜 로그인 공급자 응답 오류 |
| `USER_NOT_FOUND` | 404 | 사용자 리소스 없음 |

---

## 2. 데이터 모델

### 2.1 User

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `user_id` | string | Y | 사용자 고유 ID |
| `username` | string | Y | 아이디 (가입 방식에 관계없이 항상 필요) |
| `email` | string | null | N | 이메일 (Google 공급자로부터 수신. 공급자가 제공하지 않으면 NULL) |
| `role` | string | Y | `writer`(현직 작가) | `aspiring_writer`(지망생) | `reader`(독자). Google이 제공하지 않으므로 가입 완료 단계에서 사용자가 선택 |
| `auth_provider` | string | Y | `google` (v0.2 기준 단일 값) |
| `provider_user_id` | string | Y | Google `sub`. **이메일을 넣지 않는다** — 이메일은 변경 가능하지만 `sub`는 불변이므로, 이메일을 키로 쓰면 주소 변경 시 계정이 갈라진다 |
| `created_at` | string(ISO8601) | Y | 가입 시각 |
| `updated_at` | string(ISO8601) | Y | 수정 시각 |

### 2.2 AuthTokens (응답 전용, 저장하지 않음)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `access_token` | string | API 호출용 단기 토큰 |
| `refresh_token` | string | 액세스 토큰 재발급용 장기 토큰 |
| `expires_in` | integer | 액세스 토큰 만료(초) |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | POST | `/auth/signup` | 로컬 회원가입 (아이디/비밀번호/이메일/역할) |
| 2 | POST | `/auth/oauth/{provider}` | 소셜 회원가입 또는 로그인 (`google`|`naver`) |
| 3 | POST | `/auth/login` | 로컬 로그인 |
| 4 | POST | `/auth/token/refresh` | 액세스 토큰 재발급 |
| 5 | POST | `/auth/logout` | 로그아웃 (리프레시 토큰 폐기) |
| 6 | GET | `/users/me` | 내 정보 조회 |
| 7 | PATCH | `/users/me` | 내 정보 수정 (이메일/역할) |
| 8 | GET | `/users/check-username` | 아이디 중복 확인 |
| 9 | POST | `/auth/password/reset-request` | 비밀번호 재설정 요청 (로컬 계정, 선택) |
| 10 | POST | `/auth/password/reset` | 비밀번호 재설정 확정 (선택) |

---

## 4. 엔드포인트 상세 명세

### 4.1 로컬 회원가입

`POST /auth/signup`

**Request Body**

```json
{ "username": "mkpark", "password": "P@ssw0rd!", "email": "mkpark@example.com", "role": "aspiring_writer" }
```

**Response 201**

```json
{
  "data": {
    "user": { "user_id": "user_101", "username": "mkpark", "email": "mkpark@example.com", "role": "aspiring_writer", "auth_provider": "local" },
    "tokens": { "access_token": "eyJ...", "refresh_token": "rt_...", "expires_in": 3600 }
  }
}
```

**Response 409**: 아이디 중복 시 `USERNAME_TAKEN`, 이메일 중복 시 `EMAIL_TAKEN`

### 4.2 소셜 회원가입/로그인

`POST /auth/oauth/{provider}`

간편 회원가입/로그인 시 이메일·비밀번호 입력을 대체한다. 신규 사용자는 `username`을 함께 전달해야 하며, 기존 연동 계정이면 로그인으로 처리되고 `username`은 무시된다.

**Request Body**

```json
{ "oauth_code": "authcode_from_provider", "username": "mkpark" }
```

**Response 201 — 신규 가입**

```json
{ "data": { "user": { "user_id": "user_102", "username": "mkpark", "auth_provider": "naver" }, "tokens": { } }, "meta": { "is_new_user": true } }
```

**Response 200 — 기존 계정 로그인**: 위와 동일 구조, `meta.is_new_user: false`

**Response 400**: 신규 사용자인데 `username` 누락 시 `USERNAME_REQUIRED`

### 4.3 로컬 로그인

`POST /auth/login`

**Request Body**

```json
{ "username": "mkpark", "password": "P@ssw0rd!" }
```

**Response 200**: `AuthTokens` 포함 · **Response 401**: `INVALID_CREDENTIALS`

### 4.4 토큰 재발급

`POST /auth/token/refresh`

**Request Body**: `{ "refresh_token": "rt_..." }` · **Response 200**: 신규 `access_token`, `expires_in` · **Response 401**: `REFRESH_TOKEN_INVALID`

### 4.5 로그아웃

`POST /auth/logout` — **Response 204**: 전달된 리프레시 토큰을 폐기

### 4.6 내 정보 조회

`GET /users/me` — **Response 200**: `User` 객체 (비밀번호 관련 필드 제외)

### 4.7 내 정보 수정

`PATCH /users/me`

**Request Body**: `{ "email": "new@example.com", "role": "writer" }` (일부 필드만 전송 가능, `username`은 이 API로 변경 불가로 가정)

**Response 200**: 갱신된 `User` 객체

### 4.8 아이디 중복 확인

`GET /users/check-username?username=mkpark`

**Response 200**: `{ "data": { "username": "mkpark", "available": false } }`

### 4.9~4.10 비밀번호 재설정 (선택 기능)

로컬 계정 전용. 이메일로 재설정 링크/코드 발송 후(`reset-request`) 코드와 새 비밀번호로 확정(`reset`)한다. 소셜 전용 계정은 `SOCIAL_ONLY_ACCOUNT`(400) 반환.

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 가입 방식 선택(로컬/소셜) | 사용자 | `POST /auth/signup` 또는 `POST /auth/oauth/{provider}` |
| 2단계: 로그인·토큰 발급 | 사용자 | `POST /auth/login`, `POST /auth/oauth/{provider}` |
| 3단계: 세션 유지 | 클라이언트 | `POST /auth/token/refresh` (access_token 만료 시) |
| 4단계: 프로젝트/팀 API 접근 | 사용자 | 모든 후속 API 호출에 `Authorization` 헤더 사용 |

---

## 6. 부록 — 예시 시나리오

1. **지망생으로 로컬 회원가입** `POST /auth/signup` `{ "username": "mkpark", "password": "P@ssw0rd!", "email": "mkpark@example.com", "role": "aspiring_writer" }` → `user_id: user_101`, 토큰 발급
2. **내 정보 조회** `GET /users/me` → 역할이 `aspiring_writer`임을 확인
3. **네이버 간편 로그인으로 재방문** `POST /auth/oauth/naver` `{ "oauth_code": "..." }` (이미 연동된 계정) → `is_new_user: false`
4. **액세스 토큰 만료 후 재발급** `POST /auth/token/refresh` `{ "refresh_token": "rt_..." }`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 이메일 인증 절차 추가 | `POST /auth/email/verify` 등 신규 엔드포인트 필요 |
| 2단계 인증(2FA) | 로그인 응답에 `mfa_required` 플래그 및 별도 검증 API 추가 |
| 소셜 계정 추가 연결/해제 | `POST/DELETE /users/me/oauth-connections/{provider}` 신규 엔드포인트 |
| 팀/프로젝트 초대 수락과 연계 | 미가입 이메일 초대 시 회원가입 플로우로 자동 연결(알림 기능과 연계) |