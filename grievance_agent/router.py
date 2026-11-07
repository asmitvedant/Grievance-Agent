"""Escalation router: decides which human queue a case goes to. It never closes a case."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .taxonomy import (ESCALATION_ROUTES, HUMAN_REVIEW_AMBIGUOUS, MANDATORY_HUMAN_CATEGORIES, SGRC_PRIORITY,
                       SGRC_STANDARD, URGENT_ALERT)
from .urgency import UrgencyAssessment

VAGUE_MARKERS = [
    r"\bsomething\s+(happened|bad|is\s+going\s+on|went\s+wrong)\b", r"\bi\s+(can'?t|cannot|don'?t\s+want\s+to)\s+(say|tell|explain|talk\s+about)\b",
    r"\bdon'?t\s+know\s+how\s+to\s+(say|explain|put\s+it)\b", r"\bit'?s\s+(complicated|hard\s+to\s+explain|difficult\s+to\s+say)\b",
    r"\bsome(one|body)\s+(did|said)\s+something\b", r"\byou\s+know\s+what\s+i\s+mean\b", r"\bnot\s+sure\s+(what|if|how)\b",
    r"\bnever\s*mind\b", r"\bforget\s+it\b", r"\bkuch\s+hua\b", r"\bbata\s+nahi\s+sakt", r"\bi\s+don'?t\s+remember\b",
]
_VAGUE = [re.compile(p, re.I) for p in VAGUE_MARKERS]


def vagueness_score(student_text: str) -> int:
    return sum(bool(p.search(student_text)) for p in _VAGUE)


@dataclass
class RoutingDecision:
    route: str
    reasons: list[str] = field(default_factory=list)

    @property
    def escalate(self) -> bool:
        return self.route in ESCALATION_ROUTES

    def as_dict(self) -> dict:
        return {"route": self.route, "escalate": self.escalate, "reasons": self.reasons}


def decide_route(urgency: UrgencyAssessment, record: dict | None, verification_ok: bool,
                 dropped_claims: int, student_text: str, extraction_error: str | None = None) -> RoutingDecision:
    if urgency.level == "high":
        return RoutingDecision(URGENT_ALERT, ["high urgency: " + "; ".join(urgency.reasons[:3])])
    reasons: list[str] = []
    if extraction_error or record is None:
        reasons.append(f"record could not be built ({extraction_error or 'no record'})")
    else:
        if not record.get("claims"):
            reasons.append("no verifiable statements in the account")
        if record.get("clarity") == "unclear" and len(record.get("claims", [])) < 2:
            reasons.append("extraction judged the account unclear")
        if not verification_ok:
            reasons.append("record failed verification")
    if not urgency.confident:
        reasons.append("urgency assessment not confident: " + "; ".join(urgency.reasons[:2]))
    v = vagueness_score(student_text)
    if v >= 2 or (v == 1 and len(student_text.split()) < 40):
        reasons.append(f"vague account ({v} vagueness marker(s))")
    if reasons:
        return RoutingDecision(HUMAN_REVIEW_AMBIGUOUS, reasons)
    cat = (record or {}).get("category")
    mandatory = cat in MANDATORY_HUMAN_CATEGORIES
    # a "sensitive" label from the Qwen judge alone needs the record's category to agree (see urgency.py)
    sensitive = urgency.level == "sensitive" and (getattr(urgency, "corroborated", True) or mandatory)
    if mandatory or sensitive:
        why = [f"category '{cat}' requires human handling"] if mandatory else []
        if urgency.level == "sensitive":
            why.append("sensitive content: " + "; ".join(urgency.reasons[:2]))
        return RoutingDecision(SGRC_PRIORITY, why)
    notes = [f"{dropped_claims} unverifiable statement(s) removed from the record"] if dropped_claims else []
    if urgency.level == "sensitive":
        notes.append("note for reviewer, not confirmed by rules, similar cases or category: "
                     + "; ".join(urgency.reasons[:2]))
    return RoutingDecision(SGRC_STANDARD, notes or ["routine grievance"])
