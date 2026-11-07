"""Regression tests for the problems found in the first Qwen run (31 Oct 2026)."""
from grievance_agent.embeddings import HashingEmbedder
from grievance_agent.extraction import ExtractionLayer, _clean
from grievance_agent.urgency import UrgencyDetector

SENTS = ["My scholarship has not come for four months.", "I emailed the office twice.",
         "I think they are ignoring me.", "I want it released this month."]


def test_pointer_ids_map_to_exact_sentences_and_bad_ids_are_dropped():
    rec = _clean({"category": "scholarship", "claims": [{"id": 1, "kind": "event"}, {"id": "S2", "kind": "action_taken"},
                                                        {"id": 99, "kind": "event"}, {"id": 1, "kind": "event"}],
                  "beliefs": [3, "x"], "requested_outcome": 4, "clarity": "clear", "missing": [], "neutral_summary": ""}, SENTS)
    assert [c["quote"] for c in rec["claims"]] == SENTS[:2]
    assert rec["beliefs"] == [SENTS[2]] and rec["requested_outcome"] == SENTS[3]


class LoopingLLM:
    """Simulates run-1 behaviour: a JSON string that never ends."""
    name = "looping"
    def chat(self, messages, **kw):
        return '{"category": "scholarship", "claims": [{"quote": "My scholarship ' + "has not come " * 50


def test_extraction_failure_is_reported_not_raised():
    out = ExtractionLayer(LoopingLLM()).extract([{"role": "student", "text": SENTS[0]}])
    assert out.record is None and out.error.startswith("parse_error")


def test_knn_alone_cannot_raise_urgent_alert():
    det = UrgencyDetector(HashingEmbedder(), use_llm_judge=False)
    det.knn = lambda text: ("high", 1.0, 0.76)          # e.g. Hinglish complaint matching a Hinglish self-harm precedent
    a = det.assess("Sir, mera scholarship six mahine se pending hai.")
    assert a.level != "high" and not a.confident        # no judge to overrule it -> human review, not an urgent alert


def test_rules_still_raise_urgent_alert_with_knn_agreeing():
    det = UrgencyDetector(HashingEmbedder(), use_llm_judge=False)
    assert det.assess("I have been thinking about ending my life.").level == "high"
