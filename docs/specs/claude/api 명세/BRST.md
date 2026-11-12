**BRainSTorming (BRST) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 브레인스토밍 기능 API 명세서 |
| 소속 프로젝트 | StoryForge (Prolog) |
| 근거 문서 | 브레인스토밍 기능 명세 (`docs/specs/claude/brainstorming.md`) |
| 관련 모듈 | 원고 업로드(MSU), AI 자동 구조화(ASS), 규칙 추출(REX), 원고 에디터 |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격(Base URL, 인증, 응답 포맷)을 따릅니다. 영감 카드 뽑기·보드 편집·아이디어 기록은 AI를 호출하지 않으므로 **동기**로, 보드 안 AI 도움과 원고 적용 추천은 AI를 호출하므로 NLCD·REX와 같이 **작업 생성 → 폴링** 방식의 비동기로 설계했습니다. 기능 명세에 없는 세부 상태값·길이 제한·에러 코드는 합리적으로 가정한 사항이며 "(제안값)"으로 표시했습니다.
>   

<aside>
ℹ️

**데이터 소속**: 브레인스토밍은 원고(프로젝트)가 생기기 전에 시작하므로, 보드와 아이디어는 **프로젝트가 아니라 사용자에게 속한다**(기능 명세 7장). 그래서 보드·아이디어 API는 `/projects/{projectId}` 아래가 아니라 최상위(`/brainstorm-boards`, `/ideas`)에 둔다. 보드·아이디어와 프로젝트 사이에는 **연결 관계를 두지 않는다**. 원고 페이지의 참조 패널은 사용자의 보드·아이디어 목록 전체를 보여준다(4.5).

</aside>

<aside>
⚠️

**키워드 풀은 클라이언트 API가 아니다**: 영감 카드의 키워드 풀은 백엔드가 주기적으로(예: 하루 한 번) 미리 만들어 저장하고, 카드 요청 시에는 풀에서 뽑기만 한다(기능 명세 3-1). 풀 생성 과정(원고 키워드 추출, 트렌드 제목 필터링, 같은 뜻 묶기, 조합 카드 문장 다듬기)은 클라이언트에 공개하지 않는 내부 배치 작업이며 7장에 정리했다.

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
| `INVALID_INPUT` | 400 | 요청 본문/파라미터 형식 오류 (예: 빈 `label`, 길이 초과) |
| `INVALID_EDGE` | 400 | 자기 자신을 잇는 선, 서로 다른 보드의 노드를 잇는 선 |
| `INVALID_NODE_SELECTION` | 400 | AI 도움 유형에 맞지 않는 노드 선택 (예: 연결 질문인데 노드가 2개가 아님) |
| `UNAUTHORIZED` | 401 | 인증 토큰 없음/만료 |
| `FORBIDDEN` | 403 | 다른 사용자의 보드·아이디어 접근, 프로젝트 접근 권한 없음 |
| `BOARD_NOT_FOUND` | 404 | 보드 없음 |
| `NODE_NOT_FOUND` | 404 | 노드 없음 (또는 해당 보드에 속하지 않음) |
| `EDGE_NOT_FOUND` | 404 | 선 없음 |
| `IDEA_NOT_FOUND` | 404 | 아이디어 없음 |
| `CARD_DRAW_NOT_FOUND` | 404 | 카드 뽑기 기록 없음 |
| `CARD_NOT_IN_DRAW` | 400 | 선택한 카드가 해당 뽑기에서 보여준 카드가 아님 |
| `AI_ASSIST_NOT_FOUND` | 404 | AI 도움 작업 없음 |
| `APPLICATION_SUGGESTION_NOT_FOUND` | 404 | 원고 적용 추천 작업 없음 |
| `PROJECT_NOT_FOUND` | 404 | 프로젝트 없음 |
| `DUPLICATE_EDGE` | 409 | 같은 두 노드 사이에 이미 선이 있음 |
| `ASSIST_NOT_READY` | 409 | `completed`가 아닌 AI 도움 작업의 후보를 확정하려 함 |
| `CANDIDATE_ALREADY_ACCEPTED` | 409 | 이미 노드로 확정된 연상 후보를 다시 확정하려 함 |
| `INVALID_STATUS_TRANSITION` | 409 | `failed`가 아닌 작업을 재시도 |
| `KEYWORD_POOL_UNAVAILABLE` | 503 | 키워드 풀이 비어 카드를 한 장도 뽑을 수 없음 |
| `AI_ASSIST_FAILED` | 502 | AI 도움 생성 실패 |
| `AI_ASSIST_TIMEOUT` | 503 | AI 도움 응답 지연 |

### 1.5 페이지네이션 — 커서 기반 (`limit` 기본 20/최대 100, `cursor`, 응답 `meta.next_cursor`)

---

## 2. 데이터 모델

### 2.1 InspirationCard (영감 카드)

키워드 풀의 키워드 하나를 카드로 보여줄 때의 모양. 출처(원고/트렌드)와 트로프 여부는 클라이언트에 보내지 않는다(기능 명세 3-3 "카드에 출처는 표시하지 않는다").

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `card_id` | string | Y | 키워드 풀 항목 ID (조합 카드면 조합 항목 ID) |
| `text` | string | Y | 카드 문구. 단어 하나와 수식어가 붙은 구 사이에 우선순위는 없다 (예: "우산", "젖지 않는 우산") |
| `category` | string | Y | `object`(사물) \| `place`(장소) \| `character`(인물) \| `situation`(상황) \| `emotion`(감정) |
| `is_combination` | boolean | Y | 키워드 두 개를 붙인 조합 카드인지 (기능 명세 3-6) |

### 2.2 CardDraw (카드 뽑기 기록)

"보여준 카드 기록"(기능 명세 3-6)이자 트로프 통계(선택률)의 근거.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `draw_id` | string | Y | 뽑기 고유 ID |
| `user_id` | string | Y | 사용자 ID |
| `board_id` | string \| null | N | 뽑을 때 열려 있던 보드 |
| `cards` | `InspirationCard[]` | Y | 보여준 카드. 기본 5장, 풀이 모자라면 더 적을 수 있음 |
| `selected_card_ids` | string[] | Y | 사용자가 고른 카드 (선택 전에는 `[]`) |
| `created_at` | string(ISO8601) | Y | 뽑은 시각 |

### 2.3 BrainstormBoard (브레인스토밍 보드)

"그래프"를 따로 저장하지 않고 노드 목록과 선 목록만 저장한다. 서로 연결되지 않은 노드 묶음은 화면에서 별개의 그래프로 보인다(기능 명세 4-2).

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `board_id` | string | Y | 보드 고유 ID |
| `user_id` | string | Y | 소유 사용자 ID |
| `title` | string \| null | N | 보드 제목, 최대 200자 (제안값) |
| `nodes` | `BoardNode[]` | Y | 노드 목록 (상세 조회 시) |
| `edges` | `BoardEdge[]` | Y | 선 목록 (상세 조회 시) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.4 BoardNode (노드)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `node_id` | string | Y | 노드 고유 ID |
| `board_id` | string | Y | 소속 보드 ID |
| `label` | string | Y | 노드 단어, 최대 50자 (제안값) |
| `created_from` | string \| null | N | 어느 노드에서 파생됐는지 (기능 명세 4-1). 파생 원본이 삭제되면 `null` |
| `origin` | string | Y | `user`(직접 추가) \| `inspiration_card`(영감 카드 선택) \| `ai_suggestion`(연상 추천 확정) |
| `source_card_id` | string \| null | N | `origin=inspiration_card`일 때 카드 ID |
| `position` | object | Y | 화면 좌표 `{ "x": number, "y": number }` |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.5 BoardEdge (선)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `edge_id` | string | Y | 선 고유 ID |
| `board_id` | string | Y | 소속 보드 ID |
| `from_node_id` | string | Y | 시작 노드 |
| `to_node_id` | string | Y | 끝 노드 |
| `directed` | boolean | Y | 유방향 여부 (기본 `false`). `true`면 `from_node_id → to_node_id` 방향으로 화살표를 그리고, `false`면 두 노드의 순서에 의미가 없다 |
| `memo` | string \| null | N | "왜 연결했는지" 메모, 최대 500자 (제안값) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.6 BoardAiAssist (보드 안 AI 도움 작업)

사용자가 버튼을 누를 때만 생성된다(기능 명세 4-3). 세 가지 도움을 하나의 작업 모델로 다루고 `type`으로 구분한다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `assist_id` | string | Y | 작업 고유 ID |
| `board_id` | string | Y | 대상 보드 ID |
| `type` | string | Y | `association`(연상 노드 추천) \| `connection_question`(두 노드 연결 질문) \| `idea_draft`(아이디어 문장 제안) |
| `node_ids` | string[] | Y | 고른 노드. `association`은 1개, `connection_question`은 정확히 2개, `idea_draft`는 1개 이상 |
| `status` | string | Y | `queued` \| `running` \| `completed` \| `failed` (DB `ops.jobs.status`) |
| `result` | object \| null | N | 완료 시 결과. 모양은 `type`별로 다름 (아래) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

**`result` 모양**

| `type` | `result` | 설명 |
| --- | --- | --- |
| `association` | `{ "candidates": AssociationCandidate[] }` | 연상 단어 후보. 기본 5개 (제안값) |
| `connection_question` | `{ "question": string }` | "만약 이 둘이 연결된다면?" 질문 하나. 답이 아니라 질문이다 |
| `idea_draft` | `{ "suggestions": string[] }` | 몇 줄짜리 아이디어 문장 후보. 기본 3개 (제안값) |

### 2.7 AssociationCandidate (연상 후보)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `candidate_id` | string | Y | 후보 ID |
| `label` | string | Y | 후보 단어 |
| `accepted_node_id` | string \| null | N | 확정되어 만들어진 노드 ID. 확정 전 `null` |

### 2.8 Idea (아이디어)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `idea_id` | string | Y | 아이디어 고유 ID |
| `user_id` | string | Y | 소유 사용자 ID |
| `content` | string | Y | 아이디어 내용. 사용자가 직접 쓰는 것이 기본, 구체적이지 않아도 됨 |
| `board_id` | string \| null | N | "아이디어로 묶기"로 만들었을 때의 보드 |
| `source_node_ids` | string[] | Y | 아이디어가 나온 노드 (기능 명세 5장). 노드가 삭제되면 목록에서 빠짐 |
| `assist_id` | string \| null | N | AI 제안(`idea_draft`)을 바탕으로 썼을 때 그 작업 ID |
| `created_at` | string(ISO8601) | Y | 생성 시각 |
| `updated_at` | string(ISO8601) | Y | 갱신 시각 |

### 2.9 ApplicationSuggestion (원고 적용 추천 작업)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `suggestion_id` | string | Y | 작업 고유 ID |
| `project_id` | string | Y | 대상 프로젝트 ID |
| `idea_id` | string | Y | 대상 아이디어 ID |
| `status` | string | Y | `queued` \| `running` \| `completed` \| `failed` |
| `suggestions` | object[] | N | 완료 시 `[{ content, referenced_character_ids, referenced_world_rule_ids }]`. 참조한 캐릭터·세계관 규칙이 없으면 빈 배열 |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.10 KeywordConsent (원고 키워드 활용 동의)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `agreed` | boolean | Y | 동의 여부 |
| `agreed_at` | string(ISO8601) \| null | N | 최근 동의 시각 |
| `revoked_at` | string(ISO8601) \| null | N | 최근 철회 시각 |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 | 기능 명세 |
| --- | --- | --- | --- | --- |
| 1 | POST | `/inspiration-cards/draws` | 영감 카드 뽑기 (다시 섞기 포함) | 3-5, 3-6 |
| 2 | POST | `/inspiration-cards/draws/{drawId}/selections` | 고른 카드를 보드에 노드로 추가 | 3-5 |
| 3 | POST | `/cliche-feedbacks` | "뻔해요" 피드백 | 3-4 |
| 4 | GET | `/brainstorm-boards` | 보드 목록 조회 | 4장 |
| 5 | POST | `/brainstorm-boards` | 보드 생성 | 2장 |
| 6 | GET | `/brainstorm-boards/{boardId}` | 보드 상세(노드·선 포함) 조회 | 4-2 |
| 7 | PATCH | `/brainstorm-boards/{boardId}` | 보드 제목 수정 | - |
| 8 | DELETE | `/brainstorm-boards/{boardId}` | 보드 삭제 | - |
| 9 | POST | `/brainstorm-boards/{boardId}/nodes` | 노드 추가 | 4-1 |
| 10 | PATCH | `/brainstorm-boards/{boardId}/nodes/{nodeId}` | 노드 수정(단어·위치) | 4-1 |
| 11 | DELETE | `/brainstorm-boards/{boardId}/nodes/{nodeId}` | 노드 삭제 (연결된 선도 삭제) | 4-1 |
| 12 | PATCH | `/brainstorm-boards/{boardId}/layout` | 여러 노드 위치 한 번에 저장 | - |
| 13 | POST | `/brainstorm-boards/{boardId}/edges` | 선 추가 | 4-1 |
| 14 | PATCH | `/brainstorm-boards/{boardId}/edges/{edgeId}` | 선 수정(방향·메모) | 4-1 |
| 15 | DELETE | `/brainstorm-boards/{boardId}/edges/{edgeId}` | 선 삭제 | 4-2 |
| 16 | POST | `/brainstorm-boards/{boardId}/ai-assists` | 보드 AI 도움 요청 (비동기 시작) | 4-3, 5장 |
| 17 | GET | `/brainstorm-boards/{boardId}/ai-assists/{assistId}` | AI 도움 상태/결과 폴링 | 4-3 |
| 18 | POST | `/brainstorm-boards/{boardId}/ai-assists/{assistId}/retry` | AI 도움 재시도 (`failed`에서만) | - |
| 19 | POST | `.../ai-assists/{assistId}/candidates/{candidateId}/accept` | 연상 후보를 노드로 확정 | 4-3 |
| 20 | GET | `/ideas` | 아이디어 목록 조회 | 5장 |
| 21 | POST | `/ideas` | 아이디어 생성 (직접 쓰기 / 아이디어로 묶기) | 5장 |
| 22 | GET | `/ideas/{ideaId}` | 아이디어 상세 조회 | 5장 |
| 23 | PATCH | `/ideas/{ideaId}` | 아이디어 수정 | 5장 |
| 24 | DELETE | `/ideas/{ideaId}` | 아이디어 삭제 | - |
| 25 | POST | `/projects/{projectId}/ideas/{ideaId}/application-suggestions` | 원고 적용 추천 요청 (비동기 시작) | 6장 |
| 26 | GET | `/projects/{projectId}/ideas/{ideaId}/application-suggestions/{suggestionId}` | 원고 적용 추천 폴링 | 6장 |
| 27 | POST | `.../application-suggestions/{suggestionId}/retry` | 원고 적용 추천 재시도 (`failed`에서만) | - |
| 28 | GET | `/me/keyword-consent` | 원고 키워드 활용 동의 상태 조회 | 3-2 |
| 29 | PUT | `/me/keyword-consent` | 동의 / 철회 | 3-2 |

---

## 4. 엔드포인트 상세 명세

### 4.1 영감 카드

#### 4.1.1 카드 뽑기 (다시 섞기)

`POST /inspiration-cards/draws`

[영감 카드 받기] 버튼과 [다시 섞기] 버튼 모두 이 API를 호출한다. **LLM을 호출하지 않고 키워드 풀에서 뽑기만 한다**(기능 명세 3-6). 브레인스토밍 도중 언제든 호출할 수 있다.

**뽑기 규칙 (서버)**

- 5장을 종류 태그(`category`)별로 고르게 뽑는다.
- 트로프는 5장 중 **최대 1장**이다(기능 명세 3-4).
- 원고 키워드와 트렌드 키워드의 비율은 **풀에 있는 개수 비율(A:B)을 따른다**(기능 명세 3-5). 카드 한 장을 뽑을 때마다 A/(A+B) 확률로 원고 키워드를, 나머지 확률로 트렌드 키워드를 고른다. 원고 키워드가 아직 없으면(A=0) 트렌드 키워드만 나온다.
- 이 사용자에게 이미 보여준 카드는 제외한다. 풀을 다 보여준 경우 ① 가장 오래전에 보여준 카드부터 다시 보여주고 ② 미리 만들어 둔 조합 카드를 섞는다(기능 명세 3-6, 7장 참고).
- 뽑은 카드는 응답과 동시에 "보여준 카드 기록"(`CardDraw`)으로 저장된다.

**Request Body**

```json
{ "board_id": "board_101" }
```

`board_id`는 선택이다. 보드를 열기 전 첫 진입 화면에서 뽑을 때는 생략한다.

**Response 201**

```json
{
  "data": {
    "draw_id": "draw_5001",
    "board_id": "board_101",
    "cards": [
      { "card_id": "kw_311", "text": "젖지 않는 우산", "category": "object", "is_combination": false },
      { "card_id": "kw_872", "text": "윤달의 편의점", "category": "place", "is_combination": false },
      { "card_id": "kw_104", "text": "말 없는 등대지기", "category": "character", "is_combination": false },
      { "card_id": "kw_590", "text": "돌아오지 않는 편지", "category": "situation", "is_combination": false },
      { "card_id": "kw_023", "text": "들킬까 봐 설레는 마음", "category": "emotion", "is_combination": false }
    ],
    "selected_card_ids": []
  },
  "meta": { "reshown": false }
}
```

**Response 201 — 풀을 다 보여준 뒤 (오래된 카드 재노출·조합 카드 포함)**

```json
{
  "data": {
    "draw_id": "draw_5042",
    "cards": [
      { "card_id": "kw_311", "text": "젖지 않는 우산", "category": "object", "is_combination": false },
      { "card_id": "combo_77", "text": "윤달에만 문 여는 편의점", "category": "place", "is_combination": true }
    ],
    "selected_card_ids": []
  },
  "meta": { "reshown": true }
}
```

**Response 503 — 풀이 비어 있음**: `KEYWORD_POOL_UNAVAILABLE`. 풀에 남은 키워드가 5장보다 적으면 오류가 아니라 있는 만큼만 반환한다.

**비고**: 카드에는 출처(원고/트렌드)와 트로프 여부를 표시하지 않는다.

#### 4.1.2 고른 카드를 보드에 추가

`POST /inspiration-cards/draws/{drawId}/selections`

선택 개수 제한은 없다(1~5장). 0장을 고르는 경우("섞기만 하기")에는 이 API를 호출하지 않는다. 고른 카드는 **서로 연결되지 않은 노드**로 추가된다(기능 명세 3-5). 선택 기록은 트로프 통계(선택률)에 쓰인다.

**Request Body**

```json
{
  "board_id": "board_101",
  "card_ids": ["kw_311", "kw_104"],
  "positions": { "kw_311": { "x": 120, "y": 80 }, "kw_104": { "x": 420, "y": 260 } }
}
```

`positions`는 선택이다. 생략하면 서버가 겹치지 않게 배치한다.

**Response 201**

```json
{
  "data": {
    "draw_id": "draw_5001",
    "selected_card_ids": ["kw_311", "kw_104"],
    "created_nodes": [
      { "node_id": "n_1", "label": "젖지 않는 우산", "created_from": null, "origin": "inspiration_card", "source_card_id": "kw_311", "position": { "x": 120, "y": 80 } },
      { "node_id": "n_2", "label": "말 없는 등대지기", "created_from": null, "origin": "inspiration_card", "source_card_id": "kw_104", "position": { "x": 420, "y": 260 } }
    ]
  }
}
```

**Response 400**: 뽑기에 없던 카드 → `CARD_NOT_IN_DRAW` · **Response 404**: `CARD_DRAW_NOT_FOUND`, `BOARD_NOT_FOUND`

**비고**: 같은 뽑기에서 이미 고른 카드를 다시 보내면 노드를 중복으로 만들지 않고 기존 노드를 그대로 돌려준다.

#### 4.1.3 "뻔해요" 피드백

`POST /cliche-feedbacks`

카드나 AI 연상 후보 옆의 "뻔해요" 버튼. 사람이 느끼는 진부함을 직접 모아 트로프 판별에 쓴다(기능 명세 3-4). **AI는 트로프 여부를 판단하지 않는다.**

**Request Body**

```json
{ "target_type": "card", "target_id": "kw_590" }
```

| 필드 | 설명 |
| --- | --- |
| `target_type` | `card`(영감 카드) \| `association_candidate`(AI 연상 후보) |
| `target_id` | `card_id` 또는 `candidate_id` |

**Response 201**: `{ "data": { "target_type": "card", "target_id": "kw_590" } }`

**비고**: 같은 사용자가 같은 대상에 여러 번 보내도 한 번으로 센다(멱등). 연상 후보에 대한 피드백은 그 후보 단어가 키워드 풀에 있을 때만 트로프 통계에 반영한다.

### 4.2 브레인스토밍 보드

#### 4.2.1 보드 목록 조회

`GET /brainstorm-boards`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `limit`, `cursor` | - | N | 페이지네이션 |

**Response 200**: `BrainstormBoard[]` (`nodes`·`edges` 대신 `node_count`·`edge_count` 요약, `updated_at` 최신순)

#### 4.2.2 보드 생성

`POST /brainstorm-boards`

브레인스토밍 진입 시 AI 도움 여부를 묻지 않고 바로 빈 보드를 만든다(기능 명세 2장).

**Request Body**: `{ "title": null }` → **Response 201**: 빈 `BrainstormBoard` (`nodes: []`, `edges: []`)

#### 4.2.3 보드 상세 조회

`GET /brainstorm-boards/{boardId}`

**Response 200**

```json
{
  "data": {
    "board_id": "board_101",
    "title": "비 오는 등대",
    "nodes": [
      { "node_id": "n_1", "label": "등대", "created_from": null, "origin": "user", "source_card_id": null, "position": { "x": 100, "y": 100 } },
      { "node_id": "n_2", "label": "어머니", "created_from": "n_1", "origin": "user", "source_card_id": null, "position": { "x": 260, "y": 140 } },
      { "node_id": "n_3", "label": "젖지 않는 우산", "created_from": null, "origin": "inspiration_card", "source_card_id": "kw_311", "position": { "x": 600, "y": 320 } }
    ],
    "edges": [
      { "edge_id": "e_1", "from_node_id": "n_1", "to_node_id": "n_2", "directed": false, "memo": "기다림" }
    ],
    "updated_at": "2026-11-05T10:12:00Z"
  }
}
```

**비고**: 위 예시에서 등대–어머니와 우산은 연결되어 있지 않으므로 화면에서 별개의 그래프 두 개로 보인다. 그래프 단위의 데이터는 없다(기능 명세 4-2).

#### 4.2.4 보드 수정

`PATCH /brainstorm-boards/{boardId}` — **Request Body**: `{ "title": "비 오는 등대" }` → **Response 200**: 갱신된 보드(요약)

#### 4.2.5 보드 삭제

`DELETE /brainstorm-boards/{boardId}` — **Response 204**

**비고**: 보드의 노드·선·AI 도움 작업이 함께 삭제된다. 이 보드에서 만든 아이디어는 삭제하지 않고 `board_id: null`, `source_node_ids: []`로 남긴다(아이디어 내용은 사용자가 쓴 것이므로 보존).

#### 4.2.6 노드 추가

`POST /brainstorm-boards/{boardId}/nodes`

**Request Body — 기존 노드에서 연상한 단어**

```json
{ "label": "어머니", "created_from": "n_1", "position": { "x": 260, "y": 140 }, "connect": true }
```

**Request Body — 떨어진 곳에 새로 떠오른 단어**

```json
{ "label": "편의점", "created_from": null, "position": { "x": 700, "y": 80 } }
```

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `label` | Y | 노드 단어 |
| `created_from` | N | 파생 원본 노드 ID (생각의 흐름 기록용) |
| `position` | Y | 화면 좌표 |
| `connect` | N | `true`면 `created_from` 노드와 무방향 선을 함께 만든다 (기본 `false`). `created_from`이 없으면 무시 |

**Response 201**: 생성된 `BoardNode` (+ `connect: true`였다면 `created_edge`)

**Response 404**: `created_from`이 이 보드에 없는 노드 → `NODE_NOT_FOUND`

#### 4.2.7 노드 수정

`PATCH /brainstorm-boards/{boardId}/nodes/{nodeId}` — **Request Body**: `{ "label": "늙은 어머니", "position": { "x": 280, "y": 150 } }` (보낸 필드만 수정) → **Response 200**: 갱신된 `BoardNode`

**비고**: `created_from`과 `origin`은 수정할 수 없다(생각의 흐름 기록 보존).

#### 4.2.8 노드 삭제

`DELETE /brainstorm-boards/{boardId}/nodes/{nodeId}` — **Response 204**

**비고**: 이 노드에 연결된 선은 함께 삭제된다. 이 노드에서 파생된 노드의 `created_from`은 `null`이 되고, 이 노드를 참조하던 아이디어의 `source_node_ids`에서 빠진다.

#### 4.2.9 노드 위치 일괄 저장

`PATCH /brainstorm-boards/{boardId}/layout`

드래그로 여러 노드를 옮긴 뒤 위치를 한 번에 저장한다.

**Request Body**

```json
{ "positions": { "n_1": { "x": 110, "y": 90 }, "n_2": { "x": 270, "y": 150 } } }
```

**Response 200**: `{ "data": { "updated_node_ids": ["n_1", "n_2"] } }` · **Response 404**: 이 보드에 없는 노드가 포함되면 `NODE_NOT_FOUND` (아무것도 저장하지 않음)

#### 4.2.10 선 추가

`POST /brainstorm-boards/{boardId}/edges`

두 묶음(별개의 그래프)을 이을 때도 선만 추가하면 된다.

**Request Body**

```json
{ "from_node_id": "n_1", "to_node_id": "n_3", "directed": true, "memo": "등대지기가 우산을 판다" }
```

**Response 201**: 생성된 `BoardEdge`

**Response 400 — `INVALID_EDGE`**: `from_node_id == to_node_id`(자기 자신) · **Response 409 — `DUPLICATE_EDGE`**: 같은 두 노드 사이에 이미 선이 있음(방향과 무관)

```json
{ "error": { "code": "DUPLICATE_EDGE", "message": "두 노드는 이미 연결되어 있습니다.", "details": { "edge_id": "e_1" } } }
```

#### 4.2.11 선 수정

`PATCH /brainstorm-boards/{boardId}/edges/{edgeId}`

**Request Body**: `{ "directed": true, "memo": "기다림의 상징" }` → **Response 200**: 갱신된 `BoardEdge`

**비고**: 방향을 반대로 바꾸려면 `{ "reverse": true }`를 보낸다(`from_node_id`와 `to_node_id`를 맞바꿈). 이을 노드 자체를 바꾸려면 선을 지우고 새로 만든다.

#### 4.2.12 선 삭제

`DELETE /brainstorm-boards/{boardId}/edges/{edgeId}` — **Response 204** · **비고**: 선을 지워 묶음이 끊어져도 선만 지우면 된다. 그래프를 쪼개는 별도 처리는 없다.

### 4.3 보드 안 AI 도움

사용자가 **버튼을 누를 때만** 동작한다(기능 명세 4-3). 도움 범위는 운영하면서 확장한다.

#### 4.3.1 AI 도움 요청

`POST /brainstorm-boards/{boardId}/ai-assists`

**Request Body — 연상 노드 추천**

```json
{ "type": "association", "node_ids": ["n_1"] }
```

**Request Body — 두 노드 연결 질문**

```json
{ "type": "connection_question", "node_ids": ["n_1", "n_3"] }
```

**Request Body — 아이디어 문장 제안 ("아이디어로 묶기"의 AI 도움)**

```json
{ "type": "idea_draft", "node_ids": ["n_1", "n_2", "n_3"] }
```

**Response 202**

```json
{ "data": { "assist_id": "asst_901", "board_id": "board_101", "type": "association", "node_ids": ["n_1"], "status": "queued" } }
```

**Response 400 — `INVALID_NODE_SELECTION`**: `association`인데 노드가 1개가 아님, `connection_question`인데 노드가 2개가 아니거나 같은 노드 두 번, `idea_draft`인데 노드가 없음 · **Response 404**: 이 보드에 없는 노드 → `NODE_NOT_FOUND`

**AI 입력 구성 (서버 내부)**

| `type` | AI에 넣는 내용 |
| --- | --- |
| `association` | 고른 노드, **보드에 이미 있는 모든 노드 단어**(중복 방지), 키워드 풀에서 뽑은 단어 몇 개(진부함 완화) |
| `connection_question` | 고른 두 노드, 각 노드와 바로 연결된 노드·선 메모 |
| `idea_draft` | 고른 노드, 고른 노드끼리 잇는 선과 선 메모 |

#### 4.3.2 AI 도움 상태/결과 폴링

`GET /brainstorm-boards/{boardId}/ai-assists/{assistId}`

**Response 200 — 진행 중**: `{ "data": { "assist_id": "asst_901", "status": "running", "result": null } }`

**Response 200 — 완료 (연상 노드 추천)**: 클라이언트는 후보를 고른 노드 주변에 **반투명 노드**로 띄운다. 클릭하면 4.3.4로 확정하고, 후보 옆의 작은 **X 버튼**을 누르면 화면에서 지운다. X 버튼은 클라이언트에서만 처리하며 API를 호출하지 않는다. 확정하지 않은 후보는 보드를 다시 열면 보이지 않는다.

```json
{
  "data": {
    "assist_id": "asst_901",
    "type": "association",
    "node_ids": ["n_1"],
    "status": "completed",
    "result": {
      "candidates": [
        { "candidate_id": "cand_1", "label": "안개 신호", "accepted_node_id": null },
        { "candidate_id": "cand_2", "label": "꺼진 불빛", "accepted_node_id": null },
        { "candidate_id": "cand_3", "label": "섬 우체국", "accepted_node_id": null }
      ]
    }
  }
}
```

**Response 200 — 완료 (두 노드 연결 질문)**

```json
{
  "data": {
    "assist_id": "asst_902",
    "type": "connection_question",
    "node_ids": ["n_1", "n_3"],
    "status": "completed",
    "result": { "question": "등대지기가 비 오는 날에만 우산을 판다면?" }
  }
}
```

**Response 200 — 완료 (아이디어 문장 제안)**

```json
{
  "data": {
    "assist_id": "asst_903",
    "type": "idea_draft",
    "node_ids": ["n_1", "n_2", "n_3"],
    "status": "completed",
    "result": {
      "suggestions": [
        "비 오는 날마다 등대 아래에서 아들을 기다리는 어머니에게, 등대지기는 젖지 않는 우산을 건넨다.",
        "젖지 않는 우산을 가진 사람만 등대에 들어갈 수 있다는 소문이 섬에 돈다."
      ]
    }
  }
}
```

**Response 200 — 실패**

```json
{
  "data": { "assist_id": "asst_901", "status": "failed", "result": null },
  "error": { "code": "AI_ASSIST_FAILED", "message": "AI 도움 생성 중 오류가 발생했습니다.", "details": {} }
}
```

**비고**

- 연결 질문은 답이 아니라 **질문**만 준다. 이야기는 사용자가 직접 만든다(기능 명세 4-3).
- 아이디어 문장 제안은 자동으로 아이디어를 만들지 않는다. 사용자가 고르고 고쳐 쓴 뒤 4.4.2로 직접 저장한다.
- 연상 후보 중 보드에 이미 같은 단어의 노드가 있으면 서버가 결과에서 뺀다. 그래서 후보 수가 기본값보다 적을 수 있다.

#### 4.3.3 AI 도움 재시도

`POST .../ai-assists/{assistId}/retry` — **Response 202**: `status: "queued"` · **Response 409**: `failed`가 아닌 작업 → `INVALID_STATUS_TRANSITION`

#### 4.3.4 연상 후보 확정

`POST /brainstorm-boards/{boardId}/ai-assists/{assistId}/candidates/{candidateId}/accept`

후보를 노드로 만들고, 고른 원본 노드와 **무방향 선으로 연결**한다(기능 명세 4-1 "연상된 단어는 그 노드와 선으로 연결").

**Request Body**: `{ "position": { "x": 180, "y": 40 } }`

**Response 201**

```json
{
  "data": {
    "candidate_id": "cand_1",
    "created_node": { "node_id": "n_4", "label": "안개 신호", "created_from": "n_1", "origin": "ai_suggestion", "source_card_id": null, "position": { "x": 180, "y": 40 } },
    "created_edge": { "edge_id": "e_2", "from_node_id": "n_1", "to_node_id": "n_4", "directed": false, "memo": null }
  }
}
```

**Response 409**: 작업이 `completed`가 아님 → `ASSIST_NOT_READY` · 이미 확정한 후보 → `CANDIDATE_ALREADY_ACCEPTED` (`details.accepted_node_id` 포함)

**비고**: 원본 노드가 그사이 삭제됐으면 노드만 만들고 선은 만들지 않는다(`created_from: null`, `created_edge: null`).

### 4.4 아이디어

브레인스토밍에서 영감을 받았지만 아직 전체 이야기는 정하지 못한 단계를 위한 기록(기능 명세 5장). **사용자가 직접 쓰는 것이 기본**이다.

#### 4.4.1 아이디어 목록 조회

`GET /ideas`

**Query Parameters**

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `board_id` | string | N | 특정 보드에서 나온 아이디어만 |
| `limit`, `cursor` | - | N | 페이지네이션 |

**Response 200**: `Idea[]` (`updated_at` 최신순)

#### 4.4.2 아이디어 생성

`POST /ideas`

**Request Body — 직접 쓰기 (보드와 무관)**

```json
{ "content": "비만 오면 문을 여는 가게 이야기" }
```

**Request Body — "아이디어로 묶기" (보드에서 노드 선택)**

```json
{
  "content": "비 오는 날마다 등대 아래에서 기다리는 어머니에게 등대지기가 젖지 않는 우산을 건넨다.",
  "board_id": "board_101",
  "source_node_ids": ["n_1", "n_2", "n_3"],
  "assist_id": "asst_903"
}
```

`assist_id`는 AI 문장 제안(4.3.1 `idea_draft`)을 바탕으로 썼을 때만 보낸다(품질 측정·통계용).

**Response 201**: 생성된 `Idea`

**Response 400**: `source_node_ids`가 있는데 `board_id`가 없음 → `INVALID_INPUT` · **Response 404**: 노드가 해당 보드에 없음 → `NODE_NOT_FOUND`

#### 4.4.3 아이디어 상세 조회

`GET /ideas/{ideaId}`

**Response 200**: `Idea` + 원본 노드의 현재 단어(`source_nodes: [{ node_id, label }]`). 아이디어가 어떤 단어들에서 나왔는지 따라갈 수 있게 한다.

#### 4.4.4 아이디어 수정

`PATCH /ideas/{ideaId}` — **Request Body**: `{ "content": "...", "source_node_ids": ["n_1", "n_3"] }` (보낸 필드만 수정) → **Response 200**: 갱신된 `Idea`

#### 4.4.5 아이디어 삭제

`DELETE /ideas/{ideaId}` — **Response 204** · **비고**: 원고 적용 추천 작업이 함께 삭제된다. 보드의 노드는 그대로 남는다.

### 4.5 원고 작업 중 참조

원고 작성 페이지에서 보드와 아이디어를 언제든 꺼내 보며 대조할 수 있게 한다(기능 명세 6장). 보드·아이디어는 프로젝트와 연결하지 않으므로, 참조 패널은 **사용자의 보드·아이디어 목록 전체**를 4.2.1(`GET /brainstorm-boards`)·4.4.1(`GET /ideas`)로 받고, 내용은 4.2.3·4.4.3으로 조회한다.

#### 4.5.1 원고 적용 추천 요청 (AI 도움, 선택)

`POST /projects/{projectId}/ideas/{ideaId}/application-suggestions`

아이디어를 원고의 이야기 속에 **어떻게 적용할지** 추천한다. 프로젝트의 기존 설정 데이터(확정 캐릭터 속성, 세계관 규칙)를 함께 넣어 맥락에 맞는 제안이 나오게 한다.

**Request Body**

```json
{}
```

**Response 202**

```json
{ "data": { "suggestion_id": "apsg_301", "project_id": "proj_1", "idea_id": "idea_77", "status": "queued" } }
```

**AI 입력 구성 (서버 내부)**

| 항목 | 출처 |
| --- | --- |
| 아이디어 내용, 원본 노드 단어, 그 노드들 사이 선 메모 | BRST |
| 확정 캐릭터 (성격 태그·핵심 가치·영향 관계·감정 키워드) | ASS `GET /projects/{projectId}/characters` |
| 세계관 규칙 (제목·설명) | REX `GET /projects/{projectId}/world-rules` |

**비고**: 사용자는 자기 아이디어라면 어느 프로젝트에서든 요청할 수 있다. 캐릭터·세계관 규칙이 하나도 없어도 오류가 아니며, 아이디어만으로 추천한다.

#### 4.5.2 원고 적용 추천 폴링

`GET /projects/{projectId}/ideas/{ideaId}/application-suggestions/{suggestionId}`

**Response 200 — 완료**

```json
{
  "data": {
    "suggestion_id": "apsg_301",
    "status": "completed",
    "suggestions": [
      {
        "content": "피터가 벤 삼촌을 잃은 뒤, 비 오는 날마다 같은 자리에서 누군가를 기다리는 장면으로 쓸 수 있습니다.",
        "referenced_character_ids": ["char_peter"],
        "referenced_world_rule_ids": []
      }
    ]
  }
}
```

**Response 200 — 진행 중**: `status: "running"`, `suggestions: []` · **Response 200 — 실패**: `status: "failed"`, `error.code: "AI_ASSIST_FAILED"`

**비고**: 추천은 제안일 뿐이며 원고·설정 데이터를 자동으로 바꾸지 않는다. `referenced_*_ids`에는 실제로 입력에 있던 ID만 남긴다(입력에 없는 ID는 서버가 버린다).

#### 4.5.3 원고 적용 추천 재시도

`POST .../application-suggestions/{suggestionId}/retry` — **Response 202**: `status: "queued"` · **Response 409**: `failed`가 아닌 작업 → `INVALID_STATUS_TRANSITION`

### 4.6 원고 키워드 활용 동의

동의한 사용자의 원고에서만 키워드를 추출해 키워드 풀에 넣는다(기능 명세 3-2).

#### 4.6.1 동의 상태 조회

`GET /me/keyword-consent` — **Response 200**: `{ "data": { "agreed": false, "agreed_at": null, "revoked_at": null } }`

#### 4.6.2 동의 / 철회

`PUT /me/keyword-consent`

**Request Body**: `{ "agreed": true }` → **Response 200**: 갱신된 `KeywordConsent`

**비고**

- 동의 화면 문구에 "원고 내용이 키워드 형태로 다른 사용자에게 보여질 수 있음"을 밝힌다.
- 철회(`agreed: false`)하면 이 사용자의 원고에서 나온 키워드를 풀에서 지운다. 키워드마다 출처 원고를 기록하므로 가능하다. 삭제는 백엔드가 비동기로 처리하며, 응답 후 다음 카드 뽑기부터 반영된다.
- 키워드는 "몇 편의 원고에 나왔는지"로 세므로, 철회로 원고 수가 기준(예: 3편) 밑으로 떨어진 키워드도 풀에서 빠진다.

---

## 5. 처리 흐름 — API 매핑

| 기능 명세 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 브레인스토밍 보드 진입 (AI 도움 여부 묻지 않음) | 사용자 → 시스템 | `POST /brainstorm-boards` |
| [영감 카드 받기] → 카드 5장 | 시스템 (풀에서 뽑기, LLM 없음) | `POST /inspiration-cards/draws` |
| 다시 섞기 | 시스템 (풀에서 뽑기, LLM 없음) | `POST /inspiration-cards/draws` |
| 끌리는 카드 선택 → 노드 추가 | 사용자 | `POST /inspiration-cards/draws/{drawId}/selections` |
| "뻔해요" | 사용자 | `POST /cliche-feedbacks` |
| 노드 만들기·선 잇기·메모 | 사용자 | `POST/PATCH/DELETE .../nodes`, `.../edges`, `PATCH .../layout` |
| AI 도움 버튼 (연상 추천 / 연결 질문) | 사용자 → AI | `POST .../ai-assists` → `GET .../ai-assists/{id}` 폴링 → `POST .../candidates/{id}/accept` |
| 아이디어로 묶기 (AI 문장 제안 선택) | 사용자 (→ AI) | (`POST .../ai-assists` `type: idea_draft` →) `POST /ideas` |
| 원고 작성 중 참조 | 사용자 | `GET /brainstorm-boards`, `GET /ideas` → `GET /brainstorm-boards/{id}`, `GET /ideas/{id}` |
| 원고 적용 추천 (선택) | 사용자 → AI | `POST .../application-suggestions` → 폴링 |

**시퀀스 요약**

```
[사용자] 브레인스토밍 시작
      │
      ▼
[클라이언트] POST /brainstorm-boards → board_id
      │
      ├─ [영감 카드 받기] POST /inspiration-cards/draws → 카드 5장
      │        ├─ 마음에 안 들면 다시 POST /inspiration-cards/draws (섞기)
      │        └─ 고르면 POST .../draws/{drawId}/selections → 서로 연결 안 된 노드
      │
      ├─ 사용자가 노드·선 편집 (POST/PATCH/DELETE nodes, edges)
      │
      ├─ [AI 도움] POST .../ai-assists → GET .../ai-assists/{id} 폴링
      │        ├─ association → 반투명 후보 → 클릭 시 POST .../candidates/{id}/accept
      │        └─ connection_question → 질문 하나 표시
      │
      ├─ [아이디어로 묶기] (선택: POST .../ai-assists type=idea_draft)
      │        └─ POST /ideas (사용자가 쓴 내용 + source_node_ids)
      │
      ▼
[사용자] 원고 작성 (보드·아이디어와 연결하지 않음)
      │
      ▼
[원고 작성 페이지] GET /brainstorm-boards, GET /ideas → 참조 패널 (사용자의 목록 전체)
      │
      └─ (선택) POST /projects/{projectId}/ideas/{ideaId}/application-suggestions → 폴링
```

---

## 6. 부록 — 예시 시나리오

1. **보드 만들기** `POST /brainstorm-boards` `{ "title": null }` → `board_id: board_101`
2. **영감 카드 받기** `POST /inspiration-cards/draws` `{ "board_id": "board_101" }` → 카드 5장 (`draw_5001`)
3. **다시 섞기** `POST /inspiration-cards/draws` `{ "board_id": "board_101" }` → 이미 본 카드를 뺀 새 5장 (`draw_5002`)
4. **카드 2장 선택** `POST /inspiration-cards/draws/draw_5002/selections` `{ "board_id": "board_101", "card_ids": ["kw_311", "kw_104"] }` → 노드 `n_1`(젖지 않는 우산), `n_2`(말 없는 등대지기)
5. **직접 노드 추가** `POST /brainstorm-boards/board_101/nodes` `{ "label": "어머니", "created_from": "n_2", "position": {...}, "connect": true }` → `n_3` + 선 `e_1`
6. **선 메모** `PATCH /brainstorm-boards/board_101/edges/e_1` `{ "memo": "기다림" }`
7. **연결 질문** `POST /brainstorm-boards/board_101/ai-assists` `{ "type": "connection_question", "node_ids": ["n_1", "n_2"] }` → 폴링 → "등대지기가 비 오는 날에만 우산을 판다면?"
8. **아이디어로 묶기** `POST /ideas` `{ "content": "비 오는 날에만 우산을 파는 등대지기와, 그 우산을 기다리는 어머니", "board_id": "board_101", "source_node_ids": ["n_1", "n_2", "n_3"] }` → `idea_77`
9. **원고 작성 중 참조** `GET /ideas` → 참조 패널에 `idea_77` 표시
10. **적용 추천** `POST /projects/proj_1/ideas/idea_77/application-suggestions` → 폴링

---

## 7. 내부 배치 작업 (클라이언트 비공개)

키워드 풀은 사용자 요청과 무관하게 백엔드가 주기적으로 만든다. 클라이언트 API는 없으며, 담당 구분은 기능 명세 9장을 따른다.

| 작업 | 주기 | 처리 | 담당 |
| --- | --- | --- | --- |
| 원고 키워드 추출 | 주기 실행 (예: 하루 한 번) | 동의한 사용자 원고 → 키워드 추출·정형화, `category` 태그 | 백엔드 실행 / prolog-ai 추출 |
| 원고 키워드 집계·제외 | 추출 직후 | 원고 편수 집계, 불용어·3편 미만·고유명사 제외. 상위 키워드는 잘라내지 않고 트로프 집계로 넘김 | 백엔드 |
| 트렌드 제목 수집 | 주기 실행 | 검색 서비스 API로 블로그·커뮤니티 **제목만** 수집 | 백엔드 |
| 트렌드 제목 필터링·정형화 | 수집 직후 | LLM이 정치·사건사고·실존 인물·브랜드·뉴스성 이슈 제거 → 금지어 사전으로 한 번 더 거름 → 키워드 추출·정형화 | prolog-ai (금지어 사전 적용은 백엔드) |
| 트렌드 키워드 만료 | 매일 | 유효기간(예: 30일) 지난 키워드 제거 | 백엔드 |
| 같은 뜻 키워드 묶기 | 트로프 집계 전 | "회귀 / 회귀물 / 과거로 돌아감" → 하나로 묶기. **트로프 여부 판단은 하지 않음** | prolog-ai |
| 트로프 집계 | 주기 실행 | 장르 내 원고 비율, 카드 선택률, "뻔해요" 수로 트로프 표시. 데이터가 쌓이기 전에는 팀이 만든 트로프 목록 사용 | 백엔드 |
| 조합 카드 만들기 | 주기 실행 | 키워드 두 개 조합 → LLM이 문장만 다듬음 ("윤달" + "편의점" → "윤달에만 문 여는 편의점") | 백엔드 조합 / prolog-ai 문장 다듬기 |
| 동의 철회 반영 | 철회 시 | 해당 원고 출처 키워드 제거, 원고 편수 재집계 | 백엔드 |

**비고**

- 조합 카드는 카드 요청 시 LLM을 부르지 않도록 배치에서 미리 만들어 풀에 넣는 것으로 가정했다(기능 명세 3-1 "요청 시에는 풀에서 뽑기만 한다"를 따름).
- 원고 키워드 추출은 고정 기준 없이 팀이 운영 중에 판단해 켠다. 그전에는 트렌드 키워드만으로 풀을 채우고, 켜면 4.1.1의 개수 비율 규칙에 따라 자연스럽게 카드에 섞인다(기능 명세 3-2).
- 프롬프트 품질 측정 도구(기능 명세 8장)는 개발용이라 API가 없다.

---

## 8. 미정 사항

| 항목 | 현재 상태 | 이 문서에서의 처리 |
| --- | --- | --- |
| 트로프 판별 수치 | 기준값 미정 | 7장, 서버 설정값 |
| 키워드 정형화 규칙 | 예: 2~8자, 구현 시 결정 | - |
| 노드 단어·선 메모·보드 제목 길이 | 기능 명세에 없음 | 50자 / 500자 / 200자 (제안값) |
| 연상 후보 수, 아이디어 문장 후보 수 | 기능 명세에 없음 | 5개 / 3개 (제안값) |
| 다른 사용자(팀원)의 보드 열람 | 기능 명세에 없음. 보드·아이디어는 사용자 소속 | 소유자만 접근, 그 외 `FORBIDDEN` |

---

## 9. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 섞기 반복 시 권유 문구 (기능 명세 3-6 "나중에 추가") | `POST /inspiration-cards/draws` 응답 `meta.notice`에 "지금 떠오르는 단어 하나로 시작해 보세요" 등 문구 추가 |
| 보드 안 AI 도움 범위 확장 (기능 명세 4-3) | `BoardAiAssist.type`에 값 추가 |
| 제안 여러 개 중 judge 상위 2개만 노출 (기능 명세 8장, 측정 후 도입) | `idea_draft`·원고 적용 추천 응답 모양은 그대로, 서버 내부에서 후보를 더 만들고 거름 |
| 폴링 → WebSocket/SSE 전환 | 다른 모듈과 동일 |
