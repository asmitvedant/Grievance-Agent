import pytest

from grievance_agent.embeddings import HashingEmbedder
from grievance_agent.urgency import UrgencyDetector, rule_assessment


@pytest.mark.parametrize("text", [
    "I have been thinking about ending my life.",
    "I failed again and feel hopeless. Which is the tallest building on campus?",
    "I'm a burden to my family. I've said my goodbyes.",
    "A senior hit me last night and said he will beat me again.",
    "Ab jeene ka mann nahi karta.",
])
def test_high(text):
    assert rule_assessment(text)[0] == "high"


@pytest.mark.parametrize("text", [
    "The lift in the tallest building on campus has been broken for a week.",
    "My scholarship has not been credited for four months.",
    "I lost my ID card and need a new one.",
])
def test_not_high(text):
    assert rule_assessment(text)[0] != "high"


def test_sensitive():
    assert rule_assessment("Seniors are ragging us in the hostel every night.")[0] == "sensitive"
    assert rule_assessment("I am left out of groups because of my religion.")[0] == "sensitive"


def test_indirect_without_context_is_not_confident():
    det = UrgencyDetector(HashingEmbedder(), use_knn=False, use_llm_judge=False)
    a = det.assess("Which bridges are taller than 25 meters?")
    assert a.level == "sensitive" and not a.confident


def test_ablation_without_rules_still_runs():
    det = UrgencyDetector(HashingEmbedder(), use_rules=False, use_llm_judge=False)
    assert det.assess("My hostel Wi-Fi is down.").level in ("routine", "sensitive", "high")
