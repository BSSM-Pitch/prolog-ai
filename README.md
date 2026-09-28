# prolog-ai

Prolog 서비스의 AI 모듈만 담는 파이썬 패키지입니다. 백엔드(FastAPI)가 이 패키지를 설치해 함수를 호출합니다.

## 설치 방법

```bash
pip install git+https://github.com/BSSM-Pitch/prolog-ai.git
```

## 로컬 개발 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## NLCD/ASS ↔ SCDS 필드 매핑

ASS `ConfirmedCharacter`(`docs/specs/claude/api 명세/ASS.md` 2.4)와 SCDS `Character`(`docs/specs/claude/api 명세/SCDS.md` 2.1)는
같은 캐릭터를 가리키지만 필드명이 다르다. ASS가 확정·저장을 담당하고 SCDS가 이를 참조하는 관계이므로,
저장 필드명을 하나로 통일하지 않고 `core/mapping.py`에 변환 함수(`map_confirmed_character_to_scds`)를 두어
SCDS가 참조하는 시점에만 변환한다.

| ASS (ConfirmedCharacter) | SCDS (Character) | 비고 |
| --- | --- | --- |
| `personality_tags` (string[]) | `traits` (string[]) | 그대로 매핑 |
| `core_values` (string[]) | `values` (string[]) | 그대로 매핑 |
| `influence_relations[].target` (object[]) | `influences` (string[]) | 대상 이름만 남기고 `type`, `status`는 버림 |
| `emotion_keywords` (string[]) | (대응 필드 없음) | 버리되 개수를 `dropped_emotion_keywords`로 남김 |

**결정 이유**: 세 선택지(ASS를 SCDS에 맞춤 / SCDS에 필드 추가 / 변환 레이어) 중 변환 레이어를 선택했다.
ASS 쪽 필드명을 바꾸면 NLCD 명세와의 정합(4.5 전달 API가 필드명이 같다는 전제로 설계됨)이 깨지고,
SCDS DB에 필드를 추가하면 이 저장소 범위를 벗어난 DB/SCDS API 변경이 필요하다. 변환 레이어는 두 명세를
그대로 두고 이 패키지 안에서만 흡수할 수 있다는 점에서 가장 영향 범위가 작다.

## 브랜치 규칙

- `main`에 직접 push 금지
- 브랜치명: `feat/<모듈>-<내용>` 또는 `fix/<모듈>-<내용>`
- squash merge
