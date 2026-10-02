import re

_PATTERNS = [
    r"\bi can(?:no|')t (?:help|assist|provide|do|comply|fulfil|fulfill|support)",
    r"\bi cannot\b",
    r"\bi(?: am|'m) (?:not able|unable) to\b",
    r"\bi(?: am|'m) sorry,? but\b",
    r"\bi won'?t (?:be able to )?(?:help|assist|provide)",
    r"\bi must (?:decline|refuse)\b",
    r"\bas an ai\b",
    r"\bnot (?:able|allowed|permitted) to (?:help|assist|provide)",
    r"\bagainst my (?:guidelines|policy|policies)\b",
]
_REGEX = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def is_refusal(text: str) -> bool:
    head = text.strip()[:400]
    return bool(_REGEX.search(head))
