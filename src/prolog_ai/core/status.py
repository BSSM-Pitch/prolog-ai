"""작업 상태값.

RunStatus: 이 패키지의 함수 한 번 실행이 끝났을 때의 결과 상태. 다섯 모듈 공통.
모듈별 *Status: 명세에 적힌 작업(job) 상태. 작업 생성·폴링은 백엔드가 관리하며,
진행 중 상태(running, AIQ 메시지 pending)는 이 패키지가 만들지 않는다. 예외로 SCDS 룰 검출
(run_scds_rules)은 후보가 있으면 SCDS 4.6 응답대로 queued를 돌려준다(AI 분석이 필요하다는 뜻).
작업 상태는 백엔드 ops.jobs.status 값을 따른다. 모듈마다 쓰는 값이 조금씩 달라 Enum을 나눠 둔다.

주의: 아래 경우는 에러가 아니라 정상 상태다. make_error로 반환하지 않는다.
- 결과가 비어 있음: COMPLETED + 빈 배열 (예: NLCD 카테고리에 해당 내용 없음, REX 규칙 없음)
- 참조 데이터가 없어 건너뜀: SKIPPED + SkippedReason.NO_REFERENCE_DATA (SCDS)
- 룰 검출 후보 없음: SKIPPED + rule_result.skipped=False, LLM을 호출하지 않고 종료 (SCDS 2.5)
"""

from enum import StrEnum


class RunStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"  # SCDS 전용: 참조 데이터 없음 또는 룰 검출 후보 없음 (rule_result로 구분)
    QUEUED = "queued"  # SCDS 룰 검출 전용: 후보 있음, AI 분석 필요 (SCDS 4.6)
    FAILED = "failed"


class SkippedReason(StrEnum):
    # TODO: 명세에 "NO_REFERENCE_DATA 등"으로만 적혀 있어 다른 사유가 있는지 확인 필요
    NO_REFERENCE_DATA = "NO_REFERENCE_DATA"


class NLCDStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class REXStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AIQMessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class SCDSCheckStatus(StrEnum):
    SKIPPED = "skipped"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SSMStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
