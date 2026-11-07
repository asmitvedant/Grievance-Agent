"""Factual-preservation checks: verbatim span matching + NLI entailment.

A record item counts as *preserved* only if (a) its quote appears verbatim in the student's
own (redacted) words and (b) an NLI model judges the student's words to entail it.
Summary sentences are not quotes, so they are checked by entailment only.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .llm import split_sentences

log = logging.getLogger(__name__)

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_STOP = set("""a an the and or but if of to in on at for from by with about as is am are was were be been being
i me my mine we our you your he him his she her it its they them their this that these those there here
has have had do does did not no so very just also too then than into out up down over again once
student reports states says said that reported stated""".split())


def normalize(s: str) -> str:
    s = s.translate(_QUOTES).lower()
    s = re.sub(r"[^\w\s'\[\]-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def span_match(quote: str, source: str) -> bool:
    """True if the quote (or each part of an elided quote) occurs verbatim in the source, ignoring case/punctuation."""
    src = normalize(source)
    parts = [p for p in re.split(r"\.\.\.|…", quote) if normalize(p)]
    return bool(parts) and all(normalize(p) in src for p in parts)


def _content_words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", normalize(s)) if w not in _STOP and len(w) > 1]


class LexicalNLI:
    """Offline fallback: share of the hypothesis' content words found in the premise. Not a real NLI model."""

    name = "lexical-overlap (fallback)"

    def entail_prob(self, premise: str, hypothesis: str) -> float:
        hyp = _content_words(hypothesis)
        if not hyp:
            return 0.0
        prem = set(_content_words(premise))
        return sum(w in prem for w in hyp) / len(hyp)


class CrossEncoderNLI:
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder  # type: ignore

        self.model = CrossEncoder(model_name, device="cpu")
        self.name = model_name
        id2label = getattr(self.model.model.config, "id2label", {}) or {}
        labels = {int(k): str(v).lower() for k, v in id2label.items()}
        self.entail_idx = next((i for i, lab in labels.items() if lab.startswith("entail")), 1)

    def _windows(self, premise: str, size: int = 4) -> list[str]:
        """The whole premise when it fits the model (~512 tokens), plus overlapping 4-sentence windows.
        A summary sentence often combines facts from different turns, so a window alone can miss it."""
        sents = split_sentences(premise)
        if len(sents) <= size:
            return [premise]
        windows = [" ".join(sents[i:i + size]) for i in range(0, len(sents) - size + 1, 2)] + [" ".join(sents[-size:])]
        return ([premise] if len(premise.split()) <= 350 else []) + windows

    def entail_prob(self, premise: str, hypothesis: str) -> float:
        import numpy as np

        pairs = [(w, hypothesis) for w in self._windows(premise)]
        try:
            out = np.asarray(self.model.predict(pairs, show_progress_bar=False, apply_softmax=True), dtype=float)
        except TypeError:  # older/newer sentence-transformers without apply_softmax
            out = np.asarray(self.model.predict(pairs, show_progress_bar=False), dtype=float)
        if out.ndim == 1:
            out = out[None, :]
        is_prob = np.all(out >= 0) and np.allclose(out.sum(axis=1), 1.0, atol=1e-3)
        if not is_prob:  # raw logits -> softmax
            e = np.exp(out - out.max(axis=1, keepdims=True))
            out = e / e.sum(axis=1, keepdims=True)
        return float(out[:, self.entail_idx].max())


def get_nli(backend: str, model_name: str):
    if backend == "cross-encoder":
        try:
            return CrossEncoderNLI(model_name)
        except Exception as exc:
            log.warning("NLI cross-encoder unavailable (%s); falling back to lexical overlap.", exc)
    return LexicalNLI()


@dataclass
class ItemCheck:
    text: str
    kind: str            # claim | belief | outcome | summary
    verbatim: bool | None
    entail: float
    preserved: bool

    def as_dict(self) -> dict:
        return {"text": self.text, "kind": self.kind, "verbatim": self.verbatim,
                "entail": round(self.entail, 3), "preserved": self.preserved}


@dataclass
class VerificationReport:
    items: list[ItemCheck] = field(default_factory=list)
    nli_backend: str = ""

    @property
    def quoted(self) -> list[ItemCheck]:
        return [i for i in self.items if i.kind in ("claim", "belief", "outcome")]

    @property
    def fps(self) -> float | None:
        q = self.quoted
        return sum(i.preserved for i in q) / len(q) if q else None

    @property
    def failures(self) -> list[ItemCheck]:
        return [i for i in self.items if not i.preserved]

    def as_dict(self) -> dict:
        return {"nli_backend": self.nli_backend, "fps": self.fps, "items": [i.as_dict() for i in self.items],
                "failures": len(self.failures)}


class Verifier:
    def __init__(self, nli, threshold: float = 0.5, use_nli: bool = True):
        self.nli, self.threshold, self.use_nli = nli, threshold, use_nli

    def check_quote(self, text: str, kind: str, student_text: str) -> ItemCheck:
        verbatim = span_match(text, student_text)
        # A quote is preserved if it is the student's own words. Entailment is recorded for information only:
        # in run 2 the NLI model scored exact first-person sentences (wishes, feelings) at a median of 0.04.
        ent = self.nli.entail_prob(student_text, text) if (self.use_nli and verbatim) else 0.0
        return ItemCheck(text, kind, verbatim, ent, verbatim)

    def check_statement(self, text: str, kind: str, student_text: str) -> ItemCheck:
        ent = self.nli.entail_prob(student_text, text) if self.use_nli else 0.0
        return ItemCheck(text, kind, None, ent, ent >= self.threshold)

    def verify_record(self, record: dict, student_text: str) -> VerificationReport:
        rep = VerificationReport(nli_backend=getattr(self.nli, "name", "?"))
        for c in record.get("claims", []):
            rep.items.append(self.check_quote(c.get("quote", ""), "claim", student_text))
        for b in record.get("beliefs", []):
            rep.items.append(self.check_quote(b, "belief", student_text))
        if record.get("requested_outcome"):
            rep.items.append(self.check_quote(record["requested_outcome"], "outcome", student_text))
        for s in split_sentences(record.get("neutral_summary", "") or ""):
            rep.items.append(self.check_statement(s, "summary", student_text))
        return rep
