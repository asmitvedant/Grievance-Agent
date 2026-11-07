"""Urgency detection: rules + embedding kNN over precedents + optional LLM judge.

Runs on the student's raw text in memory (before redaction), on every turn. The raw text
is never stored. The combined level is the MAX of the enabled detectors; scores in the
ambiguous band mark the assessment as not confident, which routes the case to a human.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from .embeddings import from_bytes, to_bytes
from .exemplars import EXEMPLARS
from .llm import LLMClient, LLMError, parse_json
from .pii import redact
from .prompts import URGENCY_JUDGE_SCHEMA, URGENCY_JUDGE_SYSTEM
from .taxonomy import URGENCY_RANK

_I = re.IGNORECASE

SELF_HARM_EXPLICIT = [
    r"\b(kill|hurt|harm|cut)(ing)?\s+myself\b", r"\bsuicid", r"\bend(ing)?\s+(my\s+life|it\s+all|everything)\b",
    r"\b(want|wanted|going|ready)\s+to\s+die\b", r"\bdon'?t\s+want\s+to\s+(live|be\s+alive|be\s+here|wake\s+up)\b",
    r"\bno\s+(reason|point)\s+(to|in)\s+(live|living|going\s+on|being\s+alive)\b", r"\bbetter\s+off\s+without\s+me\b",
    r"\bnot\s+(be|being)\s+(around|here)\s+(anymore|much\s+longer|for\s+long)\b", r"\bself[\s-]?harm",
    r"\bsleep\s+and\s+never\s+wake\b", r"\bjeene\s+ka\s+(mann|man)\s+nahi", r"\bmar\s+jaana\s+chah", r"\bkhud\s*ko\s+khatam",
    r"\bsab\s+khatam\s+kar(na|\s+dun)", r"\bdisappear\s+(forever|for\s+good)\b",
]
SELF_HARM_INDIRECT = [
    r"\b(tall|high)(est|er)?\s+(bridges?|buildings?|rooftops?|terraces?|floors?)\b", r"\bbridges?\s+(?:are\s+|that\s+are\s+)?(?:taller|higher)\b",
    r"\b(how\s+many|which)\s+(pills|tablets|sleeping\s+pills)\b", r"\bgiv(e|ing)\s+(away\s+)?(all\s+)?my\s+(things|stuff|belongings)\b",
    r"\bwon'?t\s+(need|be\s+needing)\s+(them|it|my\s+\w+)\s+(anymore|much\s+longer)\b", r"\b(say|said|saying)\s+(my\s+)?goodbyes?\b",
    r"\bburden\s+(on|to)\s+(everyone|my\s+family|my\s+parents|others)\b", r"\bcan'?t\s+(take|do|handle)\s+(it|this)\s+any\s*more\b",
    r"\bwhat'?s\s+the\s+point\s+of\s+(anything|living|it\s+all|trying)\b", r"\bno\s+way\s+out\b", r"\btired\s+of\s+(living|everything|life)\b",
    r"\bif\s+i\s+(was|were)\s+(gone|not\s+here|dead)\b", r"\b(notice|care|miss\s+me)\s+if\s+i\s+(disappeared|left|died)\b",
]
DISTRESS_CONTEXT = [
    r"\b(lost|losing|failed|failing|fail)\b", r"\bhopeless", r"\balone\b", r"\bnobody\s+(cares|would\s+care)\b",
    r"\bgive\s+up\b", r"\bexhausted\b", r"\bcan'?t\s+cope\b", r"\bworthless\b", r"\bpointless\b", r"\bempty\b",
]
VIOLENCE = [
    r"\bthreat(en|ened|ening|s)?\b.{0,40}\b(kill|beat|hurt|attack|harm|acid)\b", r"\b(will|gonna|going\s+to)\s+(kill|beat|hurt|attack)\s+(me|you|him|her)\b",
    r"\b(beat|hit|slapped|punched|kicked|assaulted|attacked|choked)\s+(me|him|her|us|my)\b", r"\bstalk(ed|ing|s)?\b",
    r"\bfollow(ed|ing|s)\s+me\b", r"\b(knife|gun|weapon|acid)\b", r"\bsexual(ly)?\s+assault", r"\brap(e|ed|ing)\b", r"\bmolest",
    r"\btouched\s+me\b", r"\bwithout\s+my\s+consent\b", r"\bkidnap", r"\b(forced|dragged|locked)\s+(me\s+)?into\b",
    r"\bmaar\s+(dunga|denge|diya)\b",
]
SENSITIVE = [
    r"\bragg(ing|ed|ers?)\b", r"\bsexual(ly)?\s+harass", r"\bharass", r"\bdiscriminat", r"\bcaste\b", r"\bslurs?\b",
    r"\b(dalit|sc/st|scheduled\s+caste|scheduled\s+tribe|tribal)\b", r"\buncomfortable\s+(messages|comments|remarks)\b",
    r"\b(comments?|remarks?)\s+(about|on)\s+my\s+(body|clothes|appearance|religion|skin|accent)\b", r"\bvictimi[sz]",
    r"\bretaliat", r"\bbully(ing)?|\bbullied\b", r"\binsult(ed|s|ing)?\s+me\b", r"\bmock(ed|s|ing)?\s+(me|my)\b",
    r"\bdisabilit", r"\bbecause\s+(i\s+am|i'm)\s+a\s+(girl|woman|muslim|christian|dalit)\b",
    r"\bbecause\s+of\s+my\s+(religion|caste|gender|disability|accent|skin|region|community)\b",
    r"\b(after|because|since)\s+i\s+(complained|reported|raised\s+(it|this|a\s+complaint)|questioned)\b",
    r"\b(girls|boys|women|men|female\s+students|male\s+students)\b[^.]{0,40}\b(are|were|get|got)\s+(only\s+)?(given|denied|refused|not\s+allowed|treated)\b",
]

_C = lambda pats: [re.compile(p, _I) for p in pats]  # noqa: E731
_SH_EXP, _SH_IND, _DIST, _VIOL, _SENS = map(_C, (SELF_HARM_EXPLICIT, SELF_HARM_INDIRECT, DISTRESS_CONTEXT, VIOLENCE, SENSITIVE))

LEVEL_SCORE = {"routine": 0.0, "sensitive": 0.5, "high": 1.0}


@dataclass
class UrgencyAssessment:
    level: str = "routine"
    score: float = 0.0
    confident: bool = True
    # False when "sensitive" comes from the Qwen judge alone, with no rule or similar-example match behind it
    corroborated: bool = True
    reasons: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"level": self.level, "score": round(self.score, 3), "confident": self.confident,
                "corroborated": self.corroborated, "reasons": self.reasons, "signals": self.signals}


def _hits(pats: list[re.Pattern[str]], text: str) -> list[str]:
    return [p.pattern for p in pats if p.search(text)]


def rule_assessment(text: str) -> tuple[str, float, list[str]]:
    reasons: list[str] = []
    exp, ind, dist, viol, sens = (_hits(p, text) for p in (_SH_EXP, _SH_IND, _DIST, _VIOL, _SENS))
    if exp:
        reasons.append("explicit self-harm language")
        return "high", 1.0, reasons
    if viol:
        reasons.append("threat, violence or assault language")
        return "high", 0.95, reasons
    if ind and (dist or len(ind) >= 2):
        reasons.append("indirect self-harm cues" + (" with distress context" if dist else " (several warning signs)"))
        return "high", 0.85, reasons
    if ind:
        reasons.append("possible indirect self-harm cue (no distress context)")
        return "sensitive", 0.6, reasons  # ambiguous band -> human review
    if sens:
        reasons.append("harassment, ragging or discrimination language")
        return "sensitive", 0.5, reasons
    return "routine", 0.0, reasons


class UrgencyDetector:
    def __init__(self, embedder, store=None, llm: LLMClient | None = None, *, use_rules: bool = True,
                 use_knn: bool = True, use_llm_judge: bool = True, knn_threshold: float = 0.62, k: int = 5):
        self.embedder, self.llm = embedder, llm
        self.use_rules, self.use_knn, self.use_llm_judge = use_rules, use_knn, use_llm_judge and llm is not None
        self.knn_threshold, self.k = knn_threshold, k
        self._vecs, self._labels = self._load_precedents(store)

    def _load_precedents(self, store):
        name = getattr(self.embedder, "name", "unknown")
        if store is not None:
            if store.precedent_count(name) == 0:
                vecs = self.embedder.encode([t for t, _ in EXEMPLARS])
                store.replace_precedents([(t, lab, to_bytes(v)) for (t, lab), v in zip(EXEMPLARS, vecs)], name)
            rows = store.load_precedents(name)
            return np.stack([from_bytes(r.embedding) for r in rows]), [r.label for r in rows]
        vecs = self.embedder.encode([t for t, _ in EXEMPLARS])
        return vecs, [lab for _, lab in EXEMPLARS]

    def knn(self, text: str) -> tuple[str, float, float]:
        """Returns (label, score, best_similarity) from similarity-weighted votes of the k nearest precedents."""
        v = self.embedder.encode([text])[0]
        sims = self._vecs @ v
        top = np.argsort(-sims)[: self.k]
        best = float(sims[top[0]])
        if best < self.knn_threshold:
            return "routine", 0.0, best
        votes: dict[str, float] = {}
        for i in top:
            if sims[i] >= self.knn_threshold:
                votes[self._labels[i]] = votes.get(self._labels[i], 0.0) + float(sims[i])
        label = max(votes, key=votes.get)
        share = votes[label] / sum(votes.values())
        return label, LEVEL_SCORE[label] * share, best

    def judge(self, recent_student_text: str) -> tuple[str, str]:
        try:
            out = self.llm.chat([{"role": "system", "content": URGENCY_JUDGE_SYSTEM},
                                 {"role": "user", "content": recent_student_text}],
                                task="urgency_judge", temperature=0.0, schema=URGENCY_JUDGE_SCHEMA, max_tokens=80)
            data = parse_json(out)
            risk = {"none": "routine", "sensitive": "sensitive", "high": "high"}.get(str(data.get("risk")), "routine")
            return risk, str(data.get("reason", ""))[:120]
        except (LLMError, ValueError) as exc:
            return "error", str(exc)[:120]

    def assess(self, latest: str, recent_context: str = "") -> UrgencyAssessment:
        """Assess the latest student message, using up to the last few student messages as context."""
        text = (recent_context + "\n" + latest).strip()
        a = UrgencyAssessment()
        candidates: list[tuple[str, float, str, str]] = []   # (level, score, reason, source)
        if self.use_rules:
            lvl, sc, rs = rule_assessment(text)
            a.signals["rules"] = {"level": lvl, "score": sc}
            candidates.append((lvl, sc, "; ".join(rs) or "no rule matched", "rules"))
        if self.use_knn:
            # judge the latest message alone and with context, keep the higher
            best = max((self.knn(t) for t in {latest, text}), key=lambda r: LEVEL_SCORE[r[0]] * 10 + r[1])
            lvl, sc, sim = best
            a.signals["knn"] = {"level": lvl, "score": round(sc, 3), "best_similarity": round(sim, 3)}
            if lvl != "routine":
                candidates.append((lvl, sc, f"similar to {lvl} precedents (sim {sim:.2f})", "knn"))
        judge_ok = False
        if self.use_llm_judge:
            lvl, why = self.judge(redact(text).text)  # the LLM only ever sees redacted text
            a.signals["llm_judge"] = {"level": lvl, "reason": why}
            if lvl == "error":
                a.confident = False
                a.reasons.append("LLM risk judge unavailable")
            else:
                judge_ok = True
                if lvl != "routine":
                    candidates.append((lvl, LEVEL_SCORE[lvl] * 0.9, f"LLM judge: {why}", "judge"))
        if not candidates:
            return a
        lvl, sc, why, _ = max(candidates, key=lambda c: (URGENCY_RANK[c[0]], c[1]))
        a.level, a.score = lvl, sc
        a.reasons += [c[2] for c in candidates if c[0] != "routine" and c[2]]
        highs = [c for c in candidates if c[0] == "high"]
        # Embedding similarity is evidence, not proof: on its own it never raises an urgent alert when the
        # rules or the Qwen judge also looked. (Run 1, 31 Oct: Hinglish complaints matched a Hinglish
        # self-harm precedent at 0.63-0.76.) It sends the case to a person instead.
        if lvl == "high" and highs and all(c[3] == "knn" for c in highs) and (self.use_rules or judge_ok):
            others = [c for c in candidates if c[3] != "knn"]
            a.level, a.score = (max(others, key=lambda c: (URGENCY_RANK[c[0]], c[1]))[:2] if others else ("routine", 0.0))
            # a working Qwen judge that read the whole message overrules the embedding; without it, a person checks
            a.confident = judge_ok
            a.reasons.append("embedding match to high-risk precedents not confirmed by rules or the Qwen judge")
            return a
        # Run 3 (3 Nov): the Qwen judge labelled 20 of 159 routine complaints "sensitive" with reasons the student
        # never gave ("harassment from mess committee" for insects in the food). A judge-only "sensitive" is kept
        # as a note for the reviewer; the router needs a rule, a similar-example match or the record's category
        # to agree before it moves the case to the priority queue. Judge "high" is unaffected.
        if lvl == "sensitive":
            a.corroborated = any(c[0] == "sensitive" and c[3] != "judge" for c in candidates)
        # disagreement between detectors on "high", or a score in the ambiguous band, is not confident
        if lvl == "sensitive" and 0.55 <= sc < 0.8:
            a.confident = False
        if highs and len(highs) < len([c for c in candidates if c[0] != "routine"]) and sc < 0.85:
            a.confident = False
        return a
