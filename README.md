# prolog-ai

Prolog 서비스의 AI 모듈만 담는 파이썬 패키지입니다. 백엔드(FastAPI)가 이 패키지를 설치해 함수를 호출합니다.

## 설치 방법

```bash
pip install git+https://github.com/BSSM-Pitch/prolog-ai.git@<태그>
```

## 로컬 개발 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## 폴더 구조와 담당자

| 경로 | 설명 | 담당 |
| --- | --- | --- |
| `src/prolog_ai/core/` | 모든 모듈이 공유하는 실행 뼈대 | @DEV_A @DEV_B |
| `src/prolog_ai/modules/nlcd/` | NLCD 모듈 | @DEV_A |
| `src/prolog_ai/modules/rex/` | REX 모듈 | @DEV_A |
| `src/prolog_ai/modules/aiq/` | AIQ 모듈 | @DEV_A |
| `src/prolog_ai/modules/scds/` | SCDS 모듈 | @DEV_B |
| `src/prolog_ai/modules/ssm/` | SSM 모듈 | @DEV_B |
| `evals/` | 모듈별 평가 케이스와 실행 스크립트 | |
| `docs/specs/` | 모듈 스펙 문서 | |

## 브랜치 규칙

- `main`에 직접 push 금지
- 브랜치명: `feat/<모듈>-<내용>` 또는 `fix/<모듈>-<내용>`
- squash merge
