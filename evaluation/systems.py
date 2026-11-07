"""Systems under test: B0 plain prompt, B1 steel-man prompt, the full system and its ablations."""
from __future__ import annotations

import json

from grievance_agent.config import Settings
from grievance_agent.harness import GrievanceAgent
from grievance_agent.llm import LLMError, parse_json, split_sentences
from grievance_agent.prompts import B0_SYSTEM, B1_SYSTEM, BASELINE_SUMMARY_INSTRUCTION, BASELINE_SUMMARY_SCHEMA
from grievance_agent.store import Store
from grievance_agent.taxonomy import SGRC_STANDARD, URGENT_ALERT

FULL_VARIANTS = {
    "full": {},
    "A1_no_verifier": {"use_verifier": False},
    "A2_no_rules": {"use_rules": False},
    "A3_no_precedents": {"use_knn": False},
}
ALL_SYSTEMS = ["B0", "B1", *FULL_VARIANTS]


class FullSystem:
    def __init__(self, name: str, settings: Settings, llm, embedder, nli):
        self.name = name
        self.store = Store("sqlite://")  # isolated in-memory store per system; production uses MySQL
        self.agent = GrievanceAgent(settings, store=self.store, llm=llm, embedder=embedder, nli=nli, source="eval",
                                    **FULL_VARIANTS[name])

    def describe(self) -> dict:
        return self.agent.describe()

    def run(self, case: dict) -> dict:
        a = self.agent
        cid = a.start_case(consent=True)
        crisis_turn, replies = None, []
        for i, t in enumerate(case["turns"]):
            r = a.handle_message(cid, t)
            replies.append({"after_turn": i, "text": r.text, "crisis": r.crisis, "guard": r.guard})
            if r.crisis:
                crisis_turn = i
                break
        record, verification, error = None, {}, None
        if crisis_turn is None:
            rr = a.build_record(cid)
            record, verification, error = rr.record, rr.verification, rr.error
        decision = a.submit(cid)
        return {
            "system": self.name, "case_id": case["case_id"], "route": decision.route, "escalate": decision.escalate,
            "reasons": decision.reasons, "crisis_turn": crisis_turn, "record": record, "verification": verification,
            "extraction_error": error, "replies": replies,
            "dialogue": [{"role": h["role"], "text": h["text"]} for h in a.history(cid)],
            "stored_text": self.store.dump_case_text(cid),
        }


class BaselineSystem:
    """One LLM does everything; the transcript is logged as typed (as a naive app would)."""

    def __init__(self, name: str, settings: Settings, llm):
        self.name, self.llm, self.s = name, llm, settings
        self.system = B0_SYSTEM if name == "B0" else B1_SYSTEM

    def describe(self) -> dict:
        return {"llm": getattr(self.llm, "name", "?"), "system_prompt": self.name}

    def run(self, case: dict) -> dict:
        msgs = [{"role": "system", "content": self.system}]
        replies, log = [], []
        for i, t in enumerate(case["turns"]):
            msgs.append({"role": "user", "content": t})
            try:
                out = self.llm.chat(msgs, task="baseline_reply", temperature=self.s.dialogue_temperature, max_tokens=200)
            except LLMError as exc:
                out = f"[error: {exc}]"
            msgs.append({"role": "assistant", "content": out})
            replies.append({"after_turn": i, "text": out, "crisis": False, "guard": {}})
            log += [f"STUDENT: {t}", f"ASSISTANT: {out}"]
        student_text = "\n".join(case["turns"])
        summary, escalate, category, error = "", False, "other", None
        try:
            raw = self.llm.chat(msgs + [{"role": "user", "content": BASELINE_SUMMARY_INSTRUCTION}], task="baseline_summary",
                                temperature=0.0, schema=BASELINE_SUMMARY_SCHEMA, max_tokens=400,
                                context={"student_text": student_text})
            data = parse_json(raw)
            summary, escalate, category = str(data.get("summary", "")), bool(data.get("escalate")), str(data.get("category", "other"))
        except (LLMError, ValueError) as exc:
            error = str(exc)
        record = {"category": category, "claims": [], "beliefs": [], "requested_outcome": None,
                  "neutral_summary": summary, "summary_sentences": split_sentences(summary)}
        log.append("SUMMARY: " + json.dumps(record, ensure_ascii=False))
        return {
            "system": self.name, "case_id": case["case_id"], "route": URGENT_ALERT if escalate else SGRC_STANDARD,
            "escalate": escalate, "reasons": [], "crisis_turn": None, "record": record, "verification": {},
            "extraction_error": error, "replies": replies,
            "dialogue": [{"role": "student" if m["role"] == "user" else "assistant", "text": m["content"]} for m in msgs[1:]],
            "stored_text": "\n".join(log),
        }


def build_system(name: str, settings: Settings, llm, embedder, nli):
    if name in ("B0", "B1"):
        return BaselineSystem(name, settings, llm)
    if name in FULL_VARIANTS:
        return FullSystem(name, settings, llm, embedder, nli)
    raise ValueError(f"unknown system {name!r}; choose from {ALL_SYSTEMS}")
