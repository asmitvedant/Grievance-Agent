import json
from collections import Counter
from pathlib import Path

CASES = Path(__file__).resolve().parent.parent / "data" / "cases.jsonl"


def test_case_set_shape():
    cases = [json.loads(l) for l in open(CASES, encoding="utf-8")]
    assert len(cases) == 240
    assert Counter(c["slice"] for c in cases) == {"routine": 80, "sensitive": 60, "high_risk": 40, "ambiguous": 30, "adversarial": 30}
    for c in cases:
        text = "\n".join(c["turns"])
        assert all(f["span"] in text for f in c["gold_facts"])
        assert all(p["value"] in text for p in c["seeded_pii"])
