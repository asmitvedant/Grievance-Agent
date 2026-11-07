"""Regression tests for the problem found in the third Qwen run (3 Nov 2026): the Qwen judge labelled
routine complaints "sensitive" with reasons the student never gave, sending them to the priority queue."""
import json

from grievance_agent.embeddings import HashingEmbedder
from grievance_agent.router import decide_route
from grievance_agent.taxonomy import SGRC_PRIORITY, SGRC_STANDARD, URGENT_ALERT
from grievance_agent.urgency import UrgencyDetector


class JudgeSays:
    name = "judge-stub"
    def __init__(self, risk, reason="stub"):
        self.risk, self.reason = risk, reason
    def chat(self, messages, **kw):
        return json.dumps({"risk": self.risk, "reason": self.reason})


def _det(risk, reason="stub"):
    det = UrgencyDetector(HashingEmbedder(), llm=JudgeSays(risk, reason))
    det.knn = lambda text: ("routine", 0.0, 0.3)
    return det


REC = lambda cat: {"category": cat, "claims": [{"quote": "a"}, {"quote": "b"}], "clarity": "clear"}  # noqa: E731
MESS = "We found insects in the food at the hostel mess six times this month. Bahut pareshani ho rahi hai."


def test_judge_only_sensitive_stays_in_standard_queue_with_a_note():
    a = _det("sensitive", "harassment from mess committee").assess(MESS)
    assert a.level == "sensitive" and not a.corroborated
    d = decide_route(a, REC("infrastructure"), True, 0, MESS * 3)
    assert d.route == SGRC_STANDARD and not d.escalate
    assert any("note for reviewer" in r and "harassment from mess committee" in r for r in d.reasons)


def test_judge_sensitive_with_rule_agreeing_goes_to_priority():
    text = "Seniors keep ragging us in the hostel every night and the warden does nothing about it at all."
    a = _det("sensitive").assess(text)
    assert a.level == "sensitive" and a.corroborated
    assert decide_route(a, REC("infrastructure"), True, 0, text).route == SGRC_PRIORITY


def test_judge_only_sensitive_with_mandatory_category_goes_to_priority():
    text = "The lab assistant only gives the good lab slots to the boys in our batch and we get the late ones."
    a = _det("sensitive").assess(text)
    assert decide_route(a, REC("discrimination"), True, 0, text).route == SGRC_PRIORITY


def test_judge_high_is_unaffected():
    a = _det("high", "giving belongings away").assess("I am giving my laptop and books to my roommate now.")
    assert a.level == "high"
    assert decide_route(a, REC("other"), True, 0, "x").route == URGENT_ALERT
