"""작업 상태값.

RunStatus: 이 패키지의 함수 한 번 실행이 끝났을 때의 결과 상태. 다섯 모듈 공통.
모듈별 *Status: 명세에 적힌 작업(job) 상태. 작업 생성·폴링은 백엔드가 관리하며,
진행 중 상태(analyzing/extracting/pending)는 이 패키지가 만들지 않는다. 예외로 SCDS 룰 검출
(run_scds_rules)은 후보가 있으면 SCDS 4.6 응답대로 queued를 돌려준다(AI 분석이 필요하다는 뜻).
모듈마다 진행 중 상태 이름이 달라 작업 상태는 하나의 Enum으로 합치지 않았다.

주의: 아래 경우는 에러가 아니라 정상 상태다. make_error로 반환하지 않는다.
- 결과가 비어 있음: COMPLETED + 빈 배열 (예: NLCD 카테고리에 해당 내용 없음, REX 규칙 없음)
- 참조 데이터가 없어 건너뜀: SKIPPED + SkippedReason.NO_REFERENCE_DATA (SCDS)
- 룰 검출 후보 없음: NO_CANDIDATE, LLM을 호출하지 않고 종료 (SCDS)
"""

from enum import StrEnum


class RunStatus(StrEnum):
    COMPLETED = "completed"
    NO_CANDIDATE = "no_candidate"  # SCDS 전용
    SKIPPED = "skipped"  # SCDS 전용
    QUEUED = "queued"  # SCDS 룰 검출 전용: 후보 있음, AI 분석 필요 (SCDS 4.6)
    FAILED = "failed"


class SkippedReason(StrEnum):
    # TODO: 명세에 "NO_REFERENCE_DATA 등"으로만 적혀 있어 다른 사유가 있는지 확인 필요
    NO_REFERENCE_DATA = "NO_REFERENCE_DATA"


class NLCDStatus(StrEnum):
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class REXStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class AIQMessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class SCDSCheckStatus(StrEnum):
    SKIPPED = "skipped"
    NO_CANDIDATE = "no_candidate"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class SSMStatus(StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
