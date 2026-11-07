"""Load (or remove) the six demo cases so the reviewer dashboard has something to show.

    python scripts/seed_demo.py           # runs them through Qwen (a few minutes on a laptop)
    python scripts/seed_demo.py --mock    # instant, uses the test stub instead of Qwen
    python scripts/seed_demo.py --clear   # removes the demo cases
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ap = argparse.ArgumentParser()
ap.add_argument("--mock", action="store_true", help="use the test stub instead of Qwen")
ap.add_argument("--clear", action="store_true", help="remove demo cases")
args = ap.parse_args()
if args.mock:
    os.environ["LLM_BACKEND"] = "mock"

from grievance_agent.config import get_settings  # noqa: E402
from grievance_agent.demo import clear_demo, seed_demo  # noqa: E402
from grievance_agent.harness import GrievanceAgent  # noqa: E402
from grievance_agent.store import Store  # noqa: E402

s = get_settings()
store = Store(s.database_url)
if args.clear:
    print(f"Removed {clear_demo(store)} demo case(s).")
    sys.exit(0)

agent = GrievanceAgent(s, store=store)
print(f"LLM: {s.llm_backend}:{s.llm_model}   database: {s.database_url.split('@')[-1]}")
for title, cid, route in seed_demo(agent, lambda i, n, t: print(f"[{i + 1}/{n}] {t}") if t != "done" else None):
    print(f"   {cid}  {route:<24} {title}")
print("Done. Open the Reviewer Dashboard to see them.")
