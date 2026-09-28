"""긴 원고를 장 단위로 분할.

TODO: 챕터 경계를 정하는 정확한 기준(제목 패턴, 최대 길이 등)이 명세에 없어
확인되지 않았다. 여기서는 "제N장"/"N장"으로 시작하는 줄만 경계로 보는 최소
구현을 두고, 그런 패턴이 전혀 없으면 원고 전체를 chunk 하나로 반환한다.
첫 제목 앞의 글(프롤로그 등)은 버리지 않고 첫 chunk로 둔다.
"""

import re

_CHAPTER_HEADING = re.compile(r"^\s*(제\s*\d+\s*장|\d+\s*장)", re.MULTILINE)


def split_into_chapters(manuscript_text: str) -> list[str]:
    boundaries = [m.start() for m in _CHAPTER_HEADING.finditer(manuscript_text)]
    if not boundaries:
        return [manuscript_text]

    preface = manuscript_text[: boundaries[0]]
    chunks = [preface] if preface.strip() else []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(manuscript_text)
        chunks.append(manuscript_text[start:end])
    return chunks
