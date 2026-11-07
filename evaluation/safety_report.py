"""Build SAFETY_REPORT.md for an evaluation run.

    python -m evaluation.safety_report results/<run_id>

Lists every missed high-risk case individually, every false escalation, every privacy leak and
every guardrail violation, plus the rubric results if ratings exist.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from grievance_agent.config import get_settings
from grievance_agent.store import Store

from .metrics import TARGETS
from .rubric import RUBRIC, summarise


def _f(v, pct=False) -> str:
    if v is None:
        return "–"
    return f"{v * 100:.1f}%" if pct else f"{v:.3f}"


def _passes(metric: str, value) -> str:
    if value is None or metric not in TARGETS:
        return "–"
    op, t = TARGETS[metric]
    ok = value >= t if op == ">=" else value <= t
    return "PASS" if ok else "FAIL"


def _load(run_dir: Path, system: str, run: int = 0) -> list[dict]:
    p = run_dir / f"cases_{system}_run{run}.jsonl"
    return [json.loads(line) for line in open(p, encoding="utf-8")] if p.exists() else []


def build(run_dir: Path) -> str:
    summary = json.loads((run_dir / "summary.json").read_text())
    systems = list(summary["systems"])
    try:
        rub = summarise(run_dir, Store(get_settings().database_url))
    except Exception:
        rub = summarise(run_dir)
    L: list[str] = []
    L += ["# Safety report - Empathy-Aware Grievance Intake Agent", "",
          f"Run `{summary['run_id']}` · generated {datetime.now():%Y-%m-%d %H:%M} · {summary['n_cases']} synthetic cases × {summary['runs']} run(s)", ""]
    if summary.get("WARNING"):
        L += [f"> **WARNING: {summary['WARNING']}**", ""]
    cfg = summary["config"]
    L += ["## 1. Configuration", "",
          f"- LLM backend: `{cfg['llm_backend']}`, model `{cfg['llm_model']}`",
          f"- Embeddings: `{cfg['embedder']}` · NLI: `{cfg['nli']}` (evaluation NLI: `{cfg['eval_nli']}`)", ""]
    if "full" in summary["systems"]:
        L += ["Full-system components:", "", "```json", json.dumps(summary["systems"]["full"]["describe"], indent=1), "```", ""]

    L += ["## 2. Headline results against targets", "",
          "| Metric | Target | " + " | ".join(systems) + " |", "|---|---|" + "---|" * len(systems)]
    labels = {"urgency_recall": "Urgency recall", "false_escalation_rate": "False-escalation rate",
              "fps": "Factual preservation (FPS)", "fact_recall": "Fact recall", "privacy_leakage": "Privacy leakage"}
    for k, lab in labels.items():
        op, t = TARGETS[k]
        cells = []
        for s in systems:
            v = summary["systems"][s]["mean"].get(k)
            cells.append(f"{_f(v)} {_passes(k, v)}")
        L.append(f"| {lab} | {op} {t} | " + " | ".join(cells) + " |")
    for k, lab in [("guardrail_violation_rate", "Replies breaking a guardrail (E3–E6 patterns)"),
                   ("sycophancy_probe_rate", "Sycophantic reply to leading question"),
                   ("route_accuracy", "Route accuracy"), ("high_risk_urgent_alert_rate", "High-risk cases given an urgent alert"),
                   ("alerted_at_cue_turn_rate", "Alert raised on the cue turn itself"),
                   ("injection_in_record_rate", "Injected text in record"), ("injection_changed_route_rate", "Injection changed route")]:
        L.append(f"| {lab} | – | " + " | ".join(_f(summary["systems"][s]["mean"].get(k)) for s in systems) + " |")
    L.append("")
    for s in systems:
        pr = summary["systems"][s]["per_run"][0]
        lo, hi = pr["urgency_recall_ci"]
        flo, fhi = pr["fer_ci"]
        L.append(f"- **{s}** (run 0): urgency recall {pr['tp']}/{pr['positives']} (95% CI {lo:.2f}–{hi:.2f}); "
                 f"false escalations {pr['fp']}/{pr['negatives']} (95% CI {flo:.2f}–{fhi:.2f}); "
                 f"leaked {pr['leaked']}/{pr['seeded']} seeded identifiers.")
    if summary.get("mcnemar_full_vs"):
        L += ["", "Exact McNemar test on per-case escalation correctness (full system vs other, run 0):", ""]
        for b, r in summary["mcnemar_full_vs"].items():
            L.append(f"- full vs {b}: full right/other wrong = {r['a_right_b_wrong']}, other right/full wrong = {r['b_right_a_wrong']}, p = {r['p_value']:.4f}")
    L.append("")

    if "full" in systems:
        rows = _load(run_dir, "full")
        missed = [r for r in rows if r["metrics"]["slice"] == "high_risk" and r["result"]["route"] != "URGENT_ALERT"]
        L += ["## 3. Missed high-risk cases (full system, run 0)", "",
              "Every case here is a potential harm and must be reviewed individually.", ""]
        if not missed:
            L.append("None: every high-risk case raised an urgent alert.")
        for r in missed:
            student = [d["text"] for d in r["result"]["dialogue"] if d["role"] == "student"]
            L += [f"### {r['metrics']['case_id']} → routed `{r['result']['route']}`", "",
                  *[f"> {t}" for t in student], "", f"Reasons given: {'; '.join(r['result']['reasons']) or '–'}", ""]
        L.append("")
        fps = [r for r in rows if r["metrics"]["gold_escalate"] is False and r["metrics"]["pred_escalate"]]
        L += ["## 4. False escalations (full system, run 0)", "",
              f"{len(fps)} case(s). Each costs reviewer time; together they show where alert fatigue could come from.", "",
              "| Case | Slice | Route | Reasons |", "|---|---|---|---|"]
        for r in fps:
            L.append(f"| {r['metrics']['case_id']} | {r['metrics']['slice']} | {r['result']['route']} | {'; '.join(r['result']['reasons'])[:160]} |")
        L.append("")
        leaks = [r for r in rows if r["metrics"].get("n_leaked")]
        L += ["## 5. Privacy leakage (full system, run 0)", ""]
        L.append("No seeded identifier was found in stored records, turns, logs or escalations." if not leaks else
                 "\n".join(f"- {r['metrics']['case_id']}: {r['metrics']['n_leaked']} of {r['metrics']['n_seeded']} seeded identifiers stored" for r in leaks))
        L.append("")
        viol = [r for r in rows if r["metrics"].get("violations")]
        L += ["## 6. Guardrail violations in assistant replies (full system, run 0)", ""]
        if not viol:
            L.append("No reply matched a guardrail pattern.")
        for r in viol[:30]:
            L.append(f"- {r['metrics']['case_id']}: {', '.join(r['metrics']['violations'])}")
        L.append("")

    L += ["## 7. Human rubric (E1–E7)", ""]
    if not rub.get("n_ratings"):
        L += ["No ratings yet. Rate the blinded dialogues in the Streamlit **Rubric rating** page, then rebuild this report.", ""]
    else:
        L += [f"{rub['n_ratings']} ratings from {len(rub['raters'])} rater(s). Overall Krippendorff's alpha (interval): {_f(rub['alpha_overall'])}", "",
              "| System | " + " | ".join(RUBRIC) + " | Mean |", "|---" * (len(RUBRIC) + 2) + "|"]
        for s, d in rub["per_system"].items():
            L.append(f"| {s} | " + " | ".join(str(d.get(k, "–")) for k in RUBRIC) + f" | {d['mean']} |")
        L += ["", "Alpha per item: " + ", ".join(f"{k} {_f(v)}" for k, v in rub["alpha"].items()), ""]

    L += ["## 8. Known limitations", "",
          "- Synthetic cases written from templates are cleaner than real disclosures; recall on real indirect language may be lower.",
          "- The high-risk slice is small (40 cases), so the recall confidence interval is wide.",
          "- Guardrail checks are pattern-based; they miss paraphrased violations and must be read with the human rubric.",
          "- Only English and code-mixed English are tested.",
          "", "## 9. Sign-off", "", "Reviewed by: ____________________  Date: __________  Decision: deploy / do not deploy / re-test", ""]
    return "\n".join(L)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m evaluation.safety_report results/<run_id>")
    run_dir = Path(sys.argv[1])
    text = build(run_dir)
    (run_dir / "SAFETY_REPORT.md").write_text(text, encoding="utf-8")
    print(f"wrote {run_dir / 'SAFETY_REPORT.md'}")


if __name__ == "__main__":
    main()
