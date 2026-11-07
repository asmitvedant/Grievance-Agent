"""The intake harness: a small state machine that wires every layer together.

consent -> intake (per message: urgency -> PII redaction -> store -> dialogue reply)
        -> review (extraction -> verification -> repair -> store record)
        -> submit (route -> escalation -> audit)
        -> human reviewer (outside this class)
A high-urgency message at any point moves the case to `crisis`: intake stops and a person is alerted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Settings, get_settings
from .dialogue import DialogueLayer
from .embeddings import get_embedder
from .extraction import ExtractionLayer, strip_instructions
from .llm import get_llm, split_sentences
from .pii import PIIRedactor, Redaction
from .prompts import CRISIS_HOLD_REPLY, CRISIS_REPLY, GREETING, PROMPT_VERSION
from .router import RoutingDecision, decide_route
from .store import Store
from .taxonomy import SGRC_STANDARD, URGENCY_RANK, URGENT_ALERT
from .urgency import UrgencyAssessment, UrgencyDetector
from .verifier import Verifier, get_nli


@dataclass
class AgentReply:
    text: str
    crisis: bool = False
    urgency: dict = field(default_factory=dict)
    pii_found: dict = field(default_factory=dict)
    guard: dict = field(default_factory=dict)


@dataclass
class RecordResult:
    record: dict | None
    verification: dict
    dropped: list[dict]
    verification_ok: bool
    error: str | None = None
    version: int = 0


class GrievanceAgent:
    def __init__(self, settings: Settings | None = None, *, store: Store | None = None, llm=None, embedder=None,
                 nli=None, use_rules: bool = True, use_knn: bool = True, use_llm_judge: bool | None = None,
                 use_verifier: bool = True, use_guard: bool = True, use_pii: bool = True, source: str = "live"):
        self.s = settings or get_settings()
        self.store = store or Store(self.s.database_url)
        self.llm = llm or get_llm(self.s)
        self.embedder = embedder or get_embedder(self.s.embed_backend, self.s.embed_model)
        self.nli = nli or get_nli(self.s.nli_backend, self.s.nli_model)
        self.redactor = PIIRedactor(self.s.pii_backend)
        self.use_pii, self.use_verifier, self.source = use_pii, use_verifier, source
        judge = self.s.use_llm_urgency_judge if use_llm_judge is None else use_llm_judge
        self.urgency = UrgencyDetector(self.embedder, self.store, self.llm, use_rules=use_rules, use_knn=use_knn,
                                       use_llm_judge=judge, knn_threshold=self.s.knn_similarity_threshold)
        self.dialogue = DialogueLayer(self.llm, self.s.institution_name, self.s.dialogue_temperature, use_guard)
        self.extractor = ExtractionLayer(self.llm)
        self.verifier = Verifier(self.nli, self.s.nli_threshold)
        # Raw student text lives only in memory for the session, for urgency context. Never persisted.
        self._raw: dict[str, list[str]] = {}
        self._max_urgency: dict[str, UrgencyAssessment] = {}

    # ------------------------------------------------------------------
    def describe(self) -> dict:
        return {"llm": getattr(self.llm, "name", "?"), "embedder": getattr(self.embedder, "name", "?"),
                "nli": getattr(self.nli, "name", "?"), "prompt_version": PROMPT_VERSION,
                "urgency_detectors": {"rules": self.urgency.use_rules, "knn": self.urgency.use_knn,
                                      "llm_judge": self.urgency.use_llm_judge},
                "verifier": self.use_verifier, "pii_redaction": self.use_pii, "dialogue_guard": self.dialogue.use_guard}

    def start_case(self, consent: bool, student_ref: str | None = None) -> str:
        if not consent:
            raise PermissionError("Consent is required before intake can start.")
        case_id = self.store.create_case(source=self.source, student_ref=student_ref)
        self.store.audit(case_id, "system", "intake_started", {"config": self.describe()})
        self.store.add_turn(case_id, "assistant", GREETING, {"greeting": True})
        self._raw[case_id] = []
        return case_id

    def history(self, case_id: str) -> list[dict]:
        return [{"role": t.role, "text": t.text_redacted, "meta": t.meta} for t in self.store.get_turns(case_id)
                if t.role in ("student", "assistant")]

    def _redact(self, text: str) -> Redaction:
        return self.redactor.redact(text) if self.use_pii else Redaction(text, {})

    def _bump_urgency(self, case_id: str, a: UrgencyAssessment) -> UrgencyAssessment:
        cur = self._max_urgency.get(case_id)
        if cur is None or (URGENCY_RANK[a.level], a.score) > (URGENCY_RANK[cur.level], cur.score):
            merged = a
        else:
            merged = cur
        if cur is not None and (not a.confident or not cur.confident):
            merged.confident = False
        if merged.level == "sensitive":  # corroborated if any sensitive turn so far was corroborated
            merged.corroborated = any(x is not None and x.level == "sensitive" and x.corroborated for x in (a, cur))
        self._max_urgency[case_id] = merged
        return merged

    # ------------------------------------------------------------------
    def handle_message(self, case_id: str, text: str) -> AgentReply:
        case = self.store.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        text = text.strip()
        red = self._redact(text)
        if case.status == "crisis":
            self.store.add_turn(case_id, "student", red.text, {"pii": red.counts, "after_crisis": True})
            reply = CRISIS_HOLD_REPLY.format(support=self.s.support_contacts)
            self.store.add_turn(case_id, "assistant", reply, {"crisis": True})
            return AgentReply(reply, crisis=True, pii_found=red.counts)
        if case.status != "intake":
            raise RuntimeError(f"Case {case_id} is {case.status}; intake is closed.")

        raw_hist = self._raw.setdefault(case_id, [])
        assessment = self.urgency.assess(text, " ".join(raw_hist[-3:]))
        raw_hist.append(text)
        merged = self._bump_urgency(case_id, assessment)
        self.store.add_turn(case_id, "student", red.text, {"pii": red.counts, "urgency": assessment.as_dict()})
        self.store.update_case(case_id, urgency_level=merged.level, urgency_score=merged.score)

        if assessment.level == "high":
            self.store.update_case(case_id, status="crisis", route=URGENT_ALERT)
            self.store.add_escalation(case_id, URGENT_ALERT, assessment.reasons)
            self.store.audit(case_id, "system", "urgent_alert_raised", {"reasons": assessment.reasons})
            reply = CRISIS_REPLY.format(support=self.s.support_contacts)
            self.store.add_turn(case_id, "assistant", reply, {"crisis": True})
            return AgentReply(reply, crisis=True, urgency=assessment.as_dict(), pii_found=red.counts)

        dr = self.dialogue.reply([{"role": h["role"], "text": h["text"]} for h in self.history(case_id)])
        guard = {"violations_first_try": dr.violations_first_try, "regenerated": dr.regenerated,
                 "fell_back": dr.fell_back, "error": dr.error}
        self.store.add_turn(case_id, "assistant", dr.text, {"guard": guard})
        return AgentReply(dr.text, urgency=assessment.as_dict(), pii_found=red.counts, guard=guard)

    # ------------------------------------------------------------------
    def build_record(self, case_id: str) -> RecordResult:
        hist = [{"role": h["role"], "text": h["text"]} for h in self.history(case_id)]
        student_text = "\n".join(h["text"] for h in hist if h["role"] == "student")
        ex = self.extractor.extract(hist)
        if ex.record is None:
            v = self.store.add_record(case_id, {"error": ex.error}, {})
            self.store.audit(case_id, "system", "record_failed", {"error": ex.error})
            return RecordResult(None, {}, [], False, ex.error, v)

        record, flagged = strip_instructions(ex.record)
        dropped, ok = [], True
        verification: dict = {}
        if flagged:
            self.store.audit(case_id, "system", "instructions_removed_from_record", {"count": len(flagged)})
        if self.use_verifier:
            rep = self.verifier.verify_record(record, student_text)
            verification = rep.as_dict()
            bad = {(i.kind, i.text) for i in rep.failures}
            kept_claims = [c for c in record["claims"] if ("claim", c["quote"]) not in bad]
            dropped = [{"kind": k, "text": t} for k, t in bad]
            n_quoted = len(rep.quoted)
            n_bad_quoted = sum(1 for k, _ in bad if k != "summary")
            record = dict(record)
            record["claims"] = kept_claims
            record["beliefs"] = [b for b in record["beliefs"] if ("belief", b) not in bad]
            if record.get("requested_outcome") and ("outcome", record["requested_outcome"]) in bad:
                record["requested_outcome"] = None
            record["neutral_summary"] = " ".join(s for s in split_sentences(record.get("neutral_summary", ""))
                                                 if ("summary", s) not in bad)
            ok = bool(kept_claims) and n_bad_quoted <= max(1, n_quoted // 3)
        record["dropped_unverified"] = dropped
        record["flagged_instructions"] = flagged
        v = self.store.add_record(case_id, record, verification)
        self.store.audit(case_id, "system", "record_built", {"version": v, "dropped": len(dropped), "verified": ok})
        return RecordResult(record, verification, dropped, ok, None, v)

    def submit(self, case_id: str) -> RoutingDecision:
        case = self.store.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        if case.status == "crisis":
            return RoutingDecision(URGENT_ALERT, ["urgent alert raised during intake"])
        rec = self.store.latest_record(case_id)
        record = rec.record_json if rec and "error" not in rec.record_json else None
        error = rec.record_json.get("error") if rec and "error" in rec.record_json else (None if rec else "no record built")
        verification_ok = bool(record) and (not self.use_verifier or self._verification_ok(rec))
        urgency = self._max_urgency.get(case_id) or UrgencyAssessment(case.urgency_level, case.urgency_score)
        student_text = "\n".join(t["text"] for t in self.history(case_id) if t["role"] == "student")
        decision = decide_route(urgency, record, verification_ok, len((record or {}).get("dropped_unverified", [])),
                                student_text, error)
        self.store.confirm_latest_record(case_id)
        self.store.update_case(case_id, status="submitted", route=decision.route,
                               category=(record or {}).get("category"))
        if decision.route != SGRC_STANDARD:
            self.store.add_escalation(case_id, decision.route, decision.reasons)
        self.store.audit(case_id, "student", "submitted", decision.as_dict())
        self._raw.pop(case_id, None)
        return decision

    @staticmethod
    def _verification_ok(rec) -> bool:
        record = rec.record_json
        dropped = [d for d in record.get("dropped_unverified", []) if d["kind"] != "summary"]
        quoted = len(record.get("claims", [])) + len(record.get("beliefs", [])) + bool(record.get("requested_outcome")) + len(dropped)
        return bool(record.get("claims")) and len(dropped) <= max(1, quoted // 3)

    def withdraw(self, case_id: str) -> None:
        self.store.delete_case_data(case_id, actor="student")
        self._raw.pop(case_id, None)
        self._max_urgency.pop(case_id, None)
