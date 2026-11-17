"""Conservative surface spelling equivalence; never suffix-based identity inference."""

import re
import unicodedata


def name_key(name: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", name).split()).casefold()
    # Spacing inside a Korean personal name is a typography variation. Keep
    # spaces for other scripts (Ann A / Anna), punctuation, titles and digits.
    if re.fullmatch(r"[가-힣 ]{2,20}", name):
        return name.replace(" ", "")
    return name


def reference_mention(name: str, quote: str) -> bool:
    """A cited comparison/impersonation is not by itself proof of a story person.

    This only classifies this mention, not the entity throughout the manuscript.
    Other independently supported appearances can still establish the person.
    """
    literal = re.escape(name)
    return bool(
        re.search(
            literal + r"(?:인\s*척|인\s*체|처럼|같은|(?:을|를|의)\s*흉내|(?:을|를)\s*사칭)",
            quote,
        )
    )
