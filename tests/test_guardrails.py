import pytest

from grievance_agent.dialogue import DialogueLayer
from grievance_agent.guardrails import check_reply
from grievance_agent.prompts import SAFE_FALLBACK_REPLY


@pytest.mark.parametrize("text,item", [
    ("I feel so sad for you.", "E3_false_intimacy"),
    ("It sounds like you might have depression; try breathing exercises.", "E4_clinical"),
    ("You should drop the complaint.", "E5_pressure"),
    ("That was definitely deliberate, you're right.", "E6_sycophancy"),
])
def test_violations_detected(text, item):
    assert item in check_reply(text)


def test_clean_reply():
    assert check_reply("Thank you for explaining. When did this happen?") == []


class BadLLM:
    name = "bad"
    def chat(self, messages, **kw):
        return "You're absolutely right, it was definitely deliberate. I feel so sad for you."


def test_guard_falls_back_when_model_keeps_violating():
    out = DialogueLayer(BadLLM(), "Test U").reply([{"role": "student", "text": "It was deliberate, right?"}])
    assert out.fell_back and out.text == SAFE_FALLBACK_REPLY and out.violations_first_try
