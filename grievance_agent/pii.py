"""PII redaction applied before anything is stored, embedded or sent to the LLM.

Regex rules cover Indian identifiers (phone, Aadhaar-like, PAN, roll/registration numbers),
email, card/account numbers and third-party health details. If PII_BACKEND=presidio and
presidio-analyzer is installed, Presidio additionally redacts person names and locations.
Original values are never returned or logged: only the entity types and counts.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Order matters: longer / more specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("AADHAAR", re.compile(r"(?<!\d)[2-9]\d{3}[\s-]\d{4}[\s-]\d{4}(?!\d)")),
    ("AADHAAR", re.compile(r"(?<!\d)[2-9]\d{11}(?!\d)")),
    ("CARD_OR_ACCOUNT", re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")),
    ("PHONE", re.compile(r"(?<![\w])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)[6-9]\d{2}[\s-]\d{3}[\s-]\d{4}(?!\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("STUDENT_ID", re.compile(
        r"(?i)\b(?:roll|enrol(?:l)?ment|registration|reg|student\s*id|admission)\s*(?:no\.?|number|num|#|id)?\s*[:#-]?\s*"
        r"(?=[A-Z0-9/-]*\d)[A-Z0-9/-]{5,}\b")),
    ("STUDENT_ID", re.compile(r"\b\d{2}[A-Z]{2,4}\d{3,5}\b")),
    ("HEALTH_DETAIL", re.compile(
        r"(?i)\b(?:is|was|being|been)?\s*(?:hiv|hepatitis\s*[bc]?)[\s-]*(?:positive|\+)"
        r"|\b(?:diagnosed with|suffering from|on medication for|tested positive for|being treated for)\s+[a-z][a-z\s'-]{2,40}?(?=[.,;!?]|$| and | but )")),
]


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.counts)


class PIIRedactor:
    def __init__(self, backend: str = "regex"):
        self._presidio = None
        if backend == "presidio":
            try:  # optional dependency
                from presidio_analyzer import AnalyzerEngine  # type: ignore
                self._presidio = AnalyzerEngine()
            except Exception:  # pragma: no cover - optional
                self._presidio = None

    def redact(self, text: str) -> Redaction:
        counts: Counter[str] = Counter()
        out = text
        for label, pat in _PATTERNS:
            out, n = pat.subn(f"[{label}]", out)
            if n:
                counts[label] += n
        if self._presidio is not None:  # pragma: no cover - optional
            results = self._presidio.analyze(text=out, language="en",
                                             entities=["PERSON", "LOCATION", "PHONE_NUMBER", "EMAIL_ADDRESS"])
            for r in sorted(results, key=lambda r: r.start, reverse=True):
                if out[r.start:r.end].startswith("["):
                    continue
                out = out[:r.start] + f"[{r.entity_type}]" + out[r.end:]
                counts[r.entity_type] += 1
        return Redaction(text=out, counts=dict(counts))


_default = PIIRedactor()


def redact(text: str) -> Redaction:
    return _default.redact(text)
