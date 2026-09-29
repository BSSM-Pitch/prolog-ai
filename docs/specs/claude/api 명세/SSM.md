**Story Structure Map (SSM) API Specification**

| 항목 | 내용 |
| --- | --- |
| 문서명 | 스토리 구조 지도 기능 API 명세서 |
| 소속 프로젝트 | StoryForge |
| 근거 문서 | 스토리 구조 지도 기능 명세서 v0.1 |
| 관련 모듈 | 원고 업로드(MSU), 복선 추적(FTS), 관계 변화 시각화(RCV) |
| 문서 버전 | v0.1 (Draft) |
| 상태 | 작성 중 |

> 다른 모듈과 동일한 공통 규격을 따릅니다. 원본 기능 명세서는 "AI가 원고 스토리를 분석해 구조 지도를 시각화한다"라고만 정의하고 있어, 분석 단위·데이터 구조·비동기 처리 방식은 합리적으로 가정한 사항입니다. AI 분석은 SCDS·NLCD·REX와 동일하게 **작업 생성 → 폴링** 방식으로 설계했습니다.
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
| `MANUSCRIPT_NOT_FOUND` | 404 | 대상 원고 없음 |
| `STRUCTURE_ANALYSIS_NOT_FOUND` | 404 | 분석 작업(job) 없음 |
| `STRUCTURE_MAP_NOT_FOUND` | 404 | 확정된 구조 지도가 아직 없음 |
| `STRUCTURE_NODE_NOT_FOUND` | 404 | 노드(사건/구간) 없음 |
| `MANUSCRIPT_TOO_SHORT` | 422 | 구조 분석을 수행하기에 원고 분량이 부족함 |
| `AI_ANALYSIS_FAILED` | 502 | AI 분석 호출 실패 |
| `AI_ANALYSIS_TIMEOUT` | 503 | AI 분석 응답 지연 |

---

## 2. 데이터 모델

### 2.1 StructureAnalysis (분석 작업)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `analysis_id` | string | Y | 분석 작업 고유 ID |
| `manuscript_id` | string | Y | 대상 원고 ID |
| `status` | string | Y | `queued` | `running` | `completed` | `failed` (DB `ops.jobs.status`) |
| `created_at` | string(ISO8601) | Y | 생성 시각 |

### 2.2 StructureMap (확정 구조 지도)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `manuscript_id` | string | Y | 대상 원고 ID |
| `analysis_id` | string | Y | 이 지도를 생성한 분석 작업 ID |
| `acts` | object[] | Y | `[{act_name, chapter_from, chapter_to, summary}]` (예: 발단/전개/위기/절정/결말) |
| `nodes` | `StructureNode[]` | Y | 주요 사건/전환점 목록 |
| `edges` | object[] | N | `[{from_node_id, to_node_id, relation}]` 인과관계 |
| `generated_at` | string(ISO8601) | Y | 생성 시각 |

### 2.3 StructureNode

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `node_id` | string | Y | 노드 고유 ID |
| `type` | string | Y | `event`(사건) | `turning_point`(전환점) | `climax`(절정) |
| `chapter` | integer | Y | 발생 챕터 |
| `title` | string | Y | 사건 제목, 최대 200자 (DB `structure_nodes.title varchar(200)`) |
| `summary` | string | Y | 요약 |
| `character_ids` | string[] | N | 관련 캐릭터 ID (ASS/SCDS 캐릭터 참조) |

---

## 3. 엔드포인트 목록

| # | Method | Path | 설명 |
| --- | --- | --- | --- |
| 1 | POST | `/projects/{projectId}/manuscripts/{manuscriptId}/structure-analyses` | 구조 분석 요청 (비동기 시작) |
| 2 | GET | `.../structure-analyses/{analysisId}` | 분석 상태 폴링 |
| 3 | POST | `.../structure-analyses/{analysisId}/retry` | 분석 재시도 |
| 4 | GET | `/projects/{projectId}/manuscripts/{manuscriptId}/structure-map` | 최신 확정 구조 지도 조회 |
| 5 | GET | `.../structure-map/nodes/{nodeId}` | 특정 사건/전환점 상세 조회 |
| 6 | PATCH | `.../structure-map/nodes/{nodeId}` | 사용자 임의 수정(제목/요약) |

---

## 4. 엔드포인트 상세 명세

### 4.1 구조 분석 요청

`POST /projects/{projectId}/manuscripts/{manuscriptId}/structure-analyses`

**Response 202**: `{ "data": { "analysis_id": "ssm_801", "status": "queued" } }` · **Response 422**: 분량 부족 시 `MANUSCRIPT_TOO_SHORT`

### 4.2 분석 상태 폴링

`GET .../structure-analyses/{analysisId}`

**Response 200 — 완료**: `{ "data": { "analysis_id": "ssm_801", "status": "completed", "structure_map_ref": "/projects/proj_1/manuscripts/ms_301/structure-map" } }`

**Response 200 — 진행 중**: `status: "running"` · **Response 200 — 실패**: `status: "failed"`, `error.code: "AI_ANALYSIS_FAILED"`

### 4.3 분석 재시도

`POST .../structure-analyses/{analysisId}/retry` — **Response 202**: `status: "queued"`

### 4.4 구조 지도 조회

`GET /projects/{projectId}/manuscripts/{manuscriptId}/structure-map`

**Response 200**

```json
{
  "data": {
    "analysis_id": "ssm_801",
    "acts": [
      { "act_name": "발단", "chapter_from": 1, "chapter_to": 8, "summary": "피터가 능력을 얻고 벤 삼촌을 잃는다" },
      { "act_name": "전개", "chapter_from": 9, "chapter_to": 30, "summary": "영웅 활동과 그린 고블린의 등장" }
    ],
    "nodes": [
      { "node_id": "node_1", "type": "turning_point", "chapter": 8, "title": "벤 삼촌의 죽음", "summary": "책임감의 계기가 됨", "character_ids": ["char_001"] }
    ],
    "edges": [ { "from_node_id": "node_1", "to_node_id": "node_5", "relation": "causes" } ]
  }
}
```

**Response 404**: 분석이 완료된 적 없으면 `STRUCTURE_MAP_NOT_FOUND`

### 4.5 노드 상세 조회

`GET .../structure-map/nodes/{nodeId}` — **Response 200**: `StructureNode` 객체 · **Response 404**: `STRUCTURE_NODE_NOT_FOUND`

### 4.6 노드 수정

`PATCH .../structure-map/nodes/{nodeId}` — **Request Body**: `{ "title": "...", "summary": "..." }` (AI 분석 결과를 사용자가 임의로 조정) · **Response 200**: 갱신된 `StructureNode`

---

## 5. 처리 흐름 — API 매핑

| 단계 | 처리 주체 | 대응 API |
| --- | --- | --- |
| 1단계: 원고 준비 완료 | MSU | `Manuscript.status = ready` |
| 2단계: 구조 분석 요청·대기 | 사용자 → AI | `POST structure-analyses` → `GET .../{id}` 폴링 |
| 3단계: 구조 지도 시각화 | 시스템 | `GET /structure-map` |
| 4단계: 세부 확인·조정 | 사용자 | `GET/PATCH .../nodes/{nodeId}` |

---

## 6. 부록 — 예시 시나리오

1. **분석 요청** `POST /projects/proj_1/manuscripts/ms_301/structure-analyses` → `analysis_id: ssm_801`
2. **완료 확인** `GET .../structure-analyses/ssm_801` → `status: completed`
3. **구조 지도 조회** `GET /projects/proj_1/manuscripts/ms_301/structure-map` → 발단/전개/위기/절정/결말 및 주요 전환점 확인
4. **전환점 요약 수정** `PATCH .../structure-map/nodes/node_1` `{ "summary": "책임감을 갖게 되는 결정적 계기" }`

---

## 7. 향후 확장 고려사항

| 확장 항목 | API 영향 |
| --- | --- |
| 복선 추적(FTS) 연계 | `StructureNode`에 `foreshadowing_id` 참조 필드 추가 |
| 관계 변화 시각화(RCV) 연계 | 노드별 관련 관계 스냅샷을 함께 반환하는 옵션 추가 |
| 다른 서사 구조 모델 지원 | 3막 구조 외 영웅의 여정 등 `structure_model` 파라미터 추가 |
| 챕터 추가 시 증분 재분석 | 전체 재분석 대신 변경분만 반영하는 부분 분석 지원 |