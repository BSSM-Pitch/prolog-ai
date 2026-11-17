"""Lossless logical section indexing, independent of persisted chapters and batches."""

import re

HEADING = re.compile(
    r"^[ \t]*(?:(?:제[ \t]*)?(\d{1,5})[ \t]*(장|화|회)|chapter[ \t]+(\d{1,5}))"
    r"(?:[ \t]+[^\n]*|[.:·][^\n]*)?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)


def sections(text: str) -> list[dict]:
    """Require an increasing run; a late planning note '1화 ...' is not a new act."""
    candidates = list(HEADING.finditer(text))
    accepted, previous = [], None
    for match in candidates:
        number = int(match[1] or match[3])
        if previous is None or number > previous:
            accepted.append(match)
            previous = number
    if len(accepted) < 2:
        return [{"start": 0, "end": len(text), "title": ""}]
    result = []
    for index, match in enumerate(accepted):
        start = 0 if index == 0 else match.start()
        end = accepted[index + 1].start() if index + 1 < len(accepted) else len(text)
        result.append({"start": start, "end": end, "title": match.group().strip()})
    return result
