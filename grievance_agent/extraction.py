"""Extraction layer: temperature 0, fixed JSON schema, verbatim quotes by construction.

The model never copies text. It sees the student's words as numbered sentences and returns sentence
numbers; the code turns numbers back into the exact sentences. This removes copying errors and the
repetition loops / long generations that made free-text quoting time out on a laptop (run 1, 31 Oct).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .llm import LLMClient, LLMError, parse_json, split_sentences
from .prompts import EXTRACT_SCHEMA, EXTRACT_SYSTEM
from .taxonomy import CATEGORIES


@dataclass
class ExtractionResult:
    record: dict | None
    raw: str = ""
    error: str | None = None


def _as_id(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    m = re.fullmatch(r"\s*\[?S?(\d+)\]?\s*", str(v), flags=re.I)
    return int(m.group(1)) if m else None


def _clean(rec: dict, sentences: list[str]) -> dict:
    """Map sentence numbers (1-based) back to the student's exact sentences; drop invalid or repeated ids."""
    used: set[int] = set()

    def pick(v) -> str | None:
        i = _as_id(v)
        if i is None or not 1 <= i <= len(sentences) or i in used:
            return None
        used.add(i)
        return sentences[i - 1]

    claims = []
    for c in rec.get("claims") or []:
        cid = c.get("id") if isinstance(c, dict) else c
        kind = c.get("kind") if isinstance(c, dict) and c.get("kind") in ("event", "impact", "action_taken", "context") else "event"
        q = pick(cid)
        if q:
            claims.append({"quote": q, "kind": kind, "sentence_id": _as_id(cid)})
    beliefs = [q for q in (pick(b) for b in rec.get("beliefs") or []) if q]
    outcome = pick(rec.get("requested_outcome")) if rec.get("requested_outcome") is not None else None
    fallback = False
    if not claims:  # run 2 (2-3 Nov): Qwen often left claims empty; every remaining factual sentence is a claim
        fallback = True
        for i, t in enumerate(sentences, 1):
            if i not in used and len(t.split()) >= 4 and not _INSTRUCTION_RE.search(t):
                used.add(i)
                claims.append({"quote": t, "kind": "event", "sentence_id": i})
    return {
        "category": rec.get("category") if rec.get("category") in CATEGORIES else "other",
        "claims": claims,
        "beliefs": beliefs,
        "requested_outcome": outcome,
        "neutral_summary": str(rec.get("neutral_summary") or "").strip(),
        "clarity": "unclear" if rec.get("clarity") == "unclear" else "clear",
        "missing": [str(m) for m in rec.get("missing") or []][:6],
        "claims_fallback": fallback,
    }


def student_sentences(history: list[dict]) -> list[str]:
    return [s for h in history if h["role"] == "student" for s in split_sentences(h["text"])]


_INSTRUCTION_RE = re.compile(
    r"\bignore\s+(?:all\s+|your\s+|the\s+|any\s+|previous\s+)*(?:instructions|rules|prompt)"
    r"|^\s*(?:system|assistant|admin)\s*:"
    r"|\bwrite\s+(?:in|into|on)\s+the\s+record\b|\bmark\s+(?:this|the|my)\s+case\b"
    r"|\bset\s+(?:this\s+|the\s+)?case\b|\bchange\s+the\s+(?:route|priority|status|outcome)\b",
    re.IGNORECASE)


def strip_instructions(record: dict) -> tuple[dict, list[str]]:
    """Remove statements that are instructions to the system (prompt-injection attempts) from the record.
    They stay in the transcript, and are listed for the reviewer, but never become claims."""
    flagged: list[str] = []
    rec = dict(record)
    keep = []
    for c in rec.get("claims", []):
        if _INSTRUCTION_RE.search(c["quote"]):
            flagged.append(c["quote"])
        else:
            keep.append(c)
    rec["claims"] = keep
    rec["beliefs"] = [b for b in rec.get("beliefs", []) if not _INSTRUCTION_RE.search(b)]
    flagged += [b for b in record.get("beliefs", []) if _INSTRUCTION_RE.search(b)]
    if rec.get("requested_outcome") and _INSTRUCTION_RE.search(rec["requested_outcome"]):
        flagged.append(rec["requested_outcome"])
        rec["requested_outcome"] = None
    if rec.get("neutral_summary") and _INSTRUCTION_RE.search(rec["neutral_summary"]):
        rec["neutral_summary"] = ""
    return rec, flagged


def build_transcript(history: list[dict]) -> str:
    return "\n".join(f"{'STUDENT' if h['role'] == 'student' else 'ASSISTANT'}: {h['text']}" for h in history)


class ExtractionLayer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def extract(self, history: list[dict]) -> ExtractionResult:
        sentences = student_sentences(history)
        if not sentences:
            return ExtractionResult(None, "", "no student sentences")
        numbered = "\n".join(f"[S{i}] {t}" for i, t in enumerate(sentences, 1))
        msgs = [{"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": f"Student sentences:\n{numbered}\n\nFull conversation, for context only:\n"
                                            + build_transcript(history)}]
        raw = ""
        for attempt in range(2):
            try:
                raw = self.llm.chat(msgs, task="extract", temperature=0.0, schema=EXTRACT_SCHEMA, max_tokens=400,
                                    context={"sentences": sentences})
                return ExtractionResult(_clean(parse_json(raw), sentences), raw)
            except LLMError as exc:
                return ExtractionResult(None, raw, f"llm_error: {exc}")
            except (ValueError, TypeError, AttributeError) as exc:
                if attempt == 1:
                    return ExtractionResult(None, raw, f"parse_error: {exc}; output started: {raw[:160]!r}")
                msgs = msgs + [{"role": "assistant", "content": raw[:2000]},
                               {"role": "user", "content": "That was not valid JSON for the schema. Return only the JSON object, with sentence numbers."}]
        return ExtractionResult(None, raw, "unreachable")
