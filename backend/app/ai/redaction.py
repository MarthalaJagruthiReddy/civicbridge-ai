from __future__ import annotations

import re


EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\d)")


def redact_pii(text: str) -> tuple[str, int]:
    """Redact obvious contact data before the text is embedded or sent to an LLM."""
    matches = len(EMAIL.findall(text)) + len(PHONE.findall(text))
    redacted = EMAIL.sub("[REDACTED_EMAIL]", text)
    redacted = PHONE.sub("[REDACTED_PHONE]", redacted)
    return redacted, matches
