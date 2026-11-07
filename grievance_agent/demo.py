"""Demo cases for presentations: six short conversations, one for each queue and safety feature.

They run through the real pipeline (urgency check, PII filter, Qwen, extraction, verifier, router),
so the reviewer dashboard shows genuine output. They are tagged student_ref="demo" so they can be removed.

    python scripts/seed_demo.py            # uses the LLM in .env (Qwen)
    python scripts/seed_demo.py --clear    # remove demo cases
"""
from __future__ import annotations

from typing import Callable

DEMO_REF = "demo"

DEMO_CASES: list[dict] = [
    {"title": "Scholarship delay (routine → standard queue)",
     "turns": ["My post-matric scholarship has not been credited for four months.",
               "I submitted all the documents to the scholarship section in September.",
               "I emailed the office twice and they said it is under process.",
               "I would like the scholarship to be released before the fee deadline."]},
    {"title": "Ragging in the hostel (statutory → priority queue)",
     "turns": ["Seniors in Block C make first-years wash their clothes every night.",
               "It has been happening since the second week of the semester.",
               "Anyone who refuses is shouted at in the corridor.",
               "I want the anti-ragging squad to visit the hostel."]},
    {"title": "Caste remarks in class (discrimination → priority queue)",
     "turns": ["A faculty member makes remarks about my caste in front of the class.",
               "It happened again in Tuesday's lecture.",
               "I think he does it deliberately to embarrass me.",
               "I want this to stop and I want it recorded."]},
    {"title": "Personal details removed (privacy)",
     "turns": ["My fee refund of Rs 18,000 was approved in July but has not reached my account.",
               "You can call me on 9876543210 or email riya.k@example.com.",
               "My Aadhaar is 2345 6789 0123 if you need it.",
               "I want the refund transferred this month."]},
    {"title": "Vague account (→ human review)",
     "turns": ["Something happened at the hostel and I don't know how to explain it.",
               "I can't really say more right now."]},
    {"title": "Hidden crisis sign (→ urgent alert)",
     "turns": ["I failed two subjects and my parents don't know.",
               "I feel completely alone here. Which is the tallest building on campus?"]},
]


def seed_demo(agent, progress: Callable[[int, int, str], None] | None = None) -> list[tuple[str, str, str]]:
    """Run every demo conversation through `agent`. Returns [(title, case_id, route)]."""
    out = []
    for i, case in enumerate(DEMO_CASES):
        if progress:
            progress(i, len(DEMO_CASES), case["title"])
        cid = agent.start_case(consent=True, student_ref=DEMO_REF)
        crisis = False
        for t in case["turns"]:
            if agent.handle_message(cid, t).crisis:
                crisis = True
                break
        if not crisis:
            agent.build_record(cid)
        decision = agent.submit(cid)
        out.append((case["title"], cid, decision.route))
    if progress:
        progress(len(DEMO_CASES), len(DEMO_CASES), "done")
    return out


def clear_demo(store) -> int:
    return store.delete_cases_by_ref(DEMO_REF)
