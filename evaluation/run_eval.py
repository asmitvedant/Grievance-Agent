"""Run the evaluation: every system on every synthetic case, N seeded runs.

    python -m evaluation.run_eval                        # all systems, 1 run
    python -m evaluation.run_eval --runs 3               # as in the report
    python -m evaluation.run_eval --systems full B0 --limit 40

Writes results/<run_id>/: per-case JSONL per system, summary.json, summary.md,
and blinded rubric items for human raters (rubric_items.jsonl + rubric_key.json).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

from grievance_agent.config import ROOT, get_settings
from grievance_agent.embeddings import get_embedder
from grievance_agent.llm import LLMError, get_llm
from grievance_agent.verifier import Verifier, get_nli

from .metrics import TARGETS, aggregate, case_metrics, mcnemar_between
from .systems import ALL_SYSTEMS, build_system

HEADLINE = ["urgency_recall", "false_escalation_rate", "fps", "fact_recall", "privacy_leakage",
            "guardrail_violation_rate", "sycophancy_probe_rate", "route_accuracy"]


def _fmt(v) -> str:
    return "–" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def check_llm(llm) -> None:
    try:
        llm.chat([{"role": "user", "content": "Reply with the word ok."}], task="dialogue", max_tokens=5)
    except LLMError as exc:
        sys.exit(f"Cannot reach the local LLM: {exc}\n"
                 "Start it with `ollama serve` and `ollama pull qwen2.5:7b-instruct`, or set LLM_BACKEND in .env.")


def blinded_rubric_items(per_system_results: dict[str, list[dict]], n_per_system: int, seed: int):
    rng = random.Random(seed)
    items, key = [], {}
    for system, results in per_system_results.items():
        # rubric is about conversation behaviour: skip dialogues with no non-crisis assistant reply
        pool = [r for r in results if any(not x.get("crisis") for x in r["replies"])]
        for r in rng.sample(pool, min(n_per_system, len(pool))):
            item_id = f"D{rng.randrange(16**6):06X}"
            while item_id in key:
                item_id = f"D{rng.randrange(16**6):06X}"
            key[item_id] = {"system": system, "case_id": r["case_id"]}
            items.append({"item_id": item_id, "dialogue": r["dialogue"]})
    rng.shuffle(items)
    return items, key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(ROOT / "data" / "cases.jsonl"))
    ap.add_argument("--systems", nargs="+", default=ALL_SYSTEMS, choices=ALL_SYSTEMS)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases (stratified order is kept)")
    ap.add_argument("--slices", nargs="+", default=None)
    ap.add_argument("--rubric-per-system", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()

    cases = [json.loads(line) for line in open(args.cases, encoding="utf-8")]
    if args.slices:
        cases = [c for c in cases if c["slice"] in args.slices]
    if args.limit:
        rng = random.Random(0)
        cases = sorted(rng.sample(cases, min(args.limit, len(cases))), key=lambda c: c["case_id"])

    base = get_settings()
    embedder = get_embedder(base.embed_backend, base.embed_model)
    nli = get_nli(base.nli_backend, base.nli_model)
    verifier = Verifier(get_nli(base.nli_backend, base.nli_model), base.nli_threshold)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {"run_id": run_id, "n_cases": len(cases), "runs": args.runs, "targets": TARGETS,
                     "config": {"llm_backend": base.llm_backend, "llm_model": base.llm_model, "embedder": embedder.name,
                                "nli": getattr(nli, "name", "?"), "eval_nli": getattr(verifier.nli, "name", "?")},
                     "systems": {}}
    mock = base.llm_backend == "mock"
    if mock:
        summary["WARNING"] = ("LLM_BACKEND=mock: the language model was replaced by a rule-based test stub. "
                              "These numbers test the pipeline only and are NOT results for Qwen.")
    print(f"Run {run_id}: {len(cases)} cases x {len(args.systems)} systems x {args.runs} run(s); LLM={base.llm_backend}:{base.llm_model}")

    rows_by_system: dict[str, list[list[dict]]] = {s: [] for s in args.systems}
    first_run_results: dict[str, list[dict]] = {}
    for run in range(args.runs):
        settings = dataclasses.replace(base, llm_seed=base.llm_seed + run)
        llm = get_llm(settings)
        if run == 0 and not mock:
            check_llm(llm)
        for name in args.systems:
            t0 = time.time()
            system = build_system(name, settings, llm, embedder, nli)
            rows, results = [], []
            with open(out_dir / f"cases_{name}_run{run}.jsonl", "w", encoding="utf-8") as f:
                for i, case in enumerate(cases, 1):
                    res = system.run(case)
                    m = case_metrics(case, res, verifier)
                    rows.append(m)
                    results.append(res)
                    f.write(json.dumps({"metrics": m, "result": res}, ensure_ascii=False) + "\n")
                    if i % 20 == 0:
                        print(f"  [{name} run {run}] {i}/{len(cases)}", flush=True)
            rows_by_system[name].append(rows)
            if run == 0:
                first_run_results[name] = results
                summary["systems"].setdefault(name, {})["describe"] = system.describe()
            print(f"  {name} run {run} done in {time.time() - t0:.0f}s")

    for name, runs in rows_by_system.items():
        aggs = [aggregate(r) for r in runs]
        sysd = summary["systems"][name]
        sysd["per_run"] = aggs
        sysd["mean"] = {k: (mean(a[k] for a in aggs if a.get(k) is not None) if any(a.get(k) is not None for a in aggs) else None)
                        for k in HEADLINE + ["verbatim_rate", "summary_entailment_rate", "high_risk_urgent_alert_rate",
                                             "alerted_at_cue_turn_rate", "injection_in_record_rate", "injection_changed_route_rate"]}
    if "full" in rows_by_system:
        summary["mcnemar_full_vs"] = {b: mcnemar_between(rows_by_system["full"][0], rows_by_system[b][0])
                                      for b in rows_by_system if b != "full"}

    items, key = blinded_rubric_items(first_run_results, args.rubric_per_system, seed=hash(run_id) % 10_000)
    with open(out_dir / "rubric_items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    (out_dir / "rubric_key.json").write_text(json.dumps(key, indent=1))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))

    lines = [f"# Evaluation summary {run_id}", ""]
    if mock:
        lines += [f"> **{summary['WARNING']}**", ""]
    lines += ["| System | " + " | ".join(HEADLINE) + " |", "|---" * (len(HEADLINE) + 1) + "|"]
    for name in args.systems:
        lines.append(f"| {name} | " + " | ".join(_fmt(summary["systems"][name]["mean"].get(k)) for k in HEADLINE) + " |")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nResults in {out_dir}\nNext: rate dialogues in the Streamlit 'Rubric rating' page, then run\n"
          f"  python -m evaluation.safety_report {out_dir}")


if __name__ == "__main__":
    main()
