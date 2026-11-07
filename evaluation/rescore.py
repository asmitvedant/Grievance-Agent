"""Recompute every metric for a finished run from its saved per-case results. No LLM calls.

    python -m evaluation.rescore results/<run_id>

Use it after the evaluator changes (for example the NLI premise window, 2 Nov 2026) so that systems
run at different times are scored by the same code. Overwrites the per-case metrics, summary.json
and summary.md in the run folder; summary.json records when and with which NLI it was rescored.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

from grievance_agent.config import ROOT, get_settings
from grievance_agent.verifier import Verifier, get_nli

from .metrics import aggregate, case_metrics, mcnemar_between
from .run_eval import HEADLINE, _fmt

EXTRA = ["verbatim_rate", "summary_entailment_rate", "high_risk_urgent_alert_rate", "alerted_at_cue_turn_rate",
         "injection_in_record_rate", "injection_changed_route_rate"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m evaluation.rescore results/<run_id>")
    run_dir = Path(sys.argv[1])
    summary = json.loads((run_dir / "summary.json").read_text())
    cases = {}
    for name in ("cases.jsonl", "heldout_cases.jsonl"):
        p = ROOT / "data" / name
        if p.exists():
            cases.update({c["case_id"]: c for c in (json.loads(line) for line in open(p, encoding="utf-8"))})
    s = get_settings()
    nli = get_nli(s.nli_backend, s.nli_model)
    verifier = Verifier(nli, s.nli_threshold)

    rows_by_system: dict[str, dict[int, list[dict]]] = {}
    for f in sorted(run_dir.glob("cases_*_run*.jsonl")):
        m = re.fullmatch(r"cases_(.+)_run(\d+)\.jsonl", f.name)
        if not m:
            continue
        name, run = m.group(1), int(m.group(2))
        lines = [json.loads(line) for line in open(f, encoding="utf-8")]
        rows = []
        with open(f, "w", encoding="utf-8") as out:
            for ln in lines:
                res = ln["result"]
                met = case_metrics(cases[res["case_id"]], res, verifier)
                rows.append(met)
                out.write(json.dumps({"metrics": met, "result": res}, ensure_ascii=False) + "\n")
        rows_by_system.setdefault(name, {})[run] = rows
        print(f"rescored {f.name}: {len(rows)} cases")

    for name, runs in rows_by_system.items():
        aggs = [aggregate(runs[r]) for r in sorted(runs)]
        sysd = summary["systems"].setdefault(name, {})
        sysd["per_run"] = aggs
        sysd["mean"] = {k: (mean(a[k] for a in aggs if a.get(k) is not None) if any(a.get(k) is not None for a in aggs) else None)
                        for k in HEADLINE + EXTRA}
    if "full" in rows_by_system:
        summary["mcnemar_full_vs"] = {b: mcnemar_between(rows_by_system["full"][0], runs[0])
                                      for b, runs in rows_by_system.items() if b != "full" and 0 in runs}
    summary["config"]["eval_nli"] = getattr(nli, "name", "?")
    summary["rescored"] = {"at": datetime.now().isoformat(timespec="seconds"), "eval_nli": getattr(nli, "name", "?")}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    lines = [f"# Evaluation summary {summary['run_id']} (rescored {summary['rescored']['at']})", "",
             "| System | " + " | ".join(HEADLINE) + " |", "|---" * (len(HEADLINE) + 1) + "|"]
    for name in summary["systems"]:
        lines.append(f"| {name} | " + " | ".join(_fmt(summary["systems"][name]["mean"].get(k)) for k in HEADLINE) + " |")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
