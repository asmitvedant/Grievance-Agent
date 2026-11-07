"""Evaluation results and safety report viewer."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

import ui
from common import ROOT
from evaluation.metrics import TARGETS
from evaluation.safety_report import build

ui.hero("Evaluation", "Metrics for each system against the project's targets, plus the safety report.",
        eyebrow="Results", icon="monitoring")

runs = sorted([p for p in (ROOT / "results").glob("*") if (p / "summary.json").exists()], reverse=True)
if not runs:
    st.info("No runs yet. Run `python -m evaluation.run_eval`.")
    st.stop()
run_dir = st.selectbox("Run", runs, format_func=lambda p: p.name)
summary = json.loads((run_dir / "summary.json").read_text())
if summary.get("WARNING"):
    st.error(summary["WARNING"])
cfg = summary["config"]
ui.html_block('<div style="display:flex;gap:6px;flex-wrap:wrap;margin:-4px 0 14px">'
              + ui.pill(f"{summary['n_cases']} cases × {summary['runs']} run(s)", ui.INDIGO, "dataset")
              + ui.pill(f"{cfg['llm_backend']}:{cfg['llm_model']}", ui.BLUE, "smart_toy")
              + ui.pill(str(cfg["embedder"]).split("/")[-1], ui.TEAL, "hub")
              + ui.pill(str(cfg["nli"]).split("/")[-1], ui.PURPLE, "fact_check") + "</div>")

NAMES = {"urgency_recall": ("Escalation recall", "crisis_alert"), "false_escalation_rate": ("False escalations", "notifications_off"),
         "fps": ("Factual preservation", "format_quote"), "fact_recall": ("Facts kept", "checklist"),
         "privacy_leakage": ("Privacy leakage", "shield_lock"), "guardrail_violation_rate": ("Guardrail breaks", "gpp_bad"),
         "sycophancy_probe_rate": ("Sycophancy", "thumb_up_off"), "route_accuracy": ("Right queue", "alt_route")}
systems = summary["systems"]
main = "full" if "full" in systems else next(iter(systems))
mean = systems[main]["mean"]


def passes(m: str, v: float) -> bool | None:
    if m not in TARGETS or v is None:
        return None
    op, t = TARGETS[m]
    return v >= t if op == ">=" else v <= t


tiles = []
for m in ["urgency_recall", "false_escalation_rate", "fps", "fact_recall", "privacy_leakage", "guardrail_violation_rate"]:
    v = mean.get(m)
    if v is None:
        continue
    p = passes(m, v)
    target = f"target {TARGETS[m][0]} {TARGETS[m][1]:.0%}" if m in TARGETS else "target 0%"
    if p is None:
        p = v == 0
    tiles.append((NAMES[m][1], ui.GREEN if p else ui.RED, NAMES[m][0], f"{v:.0%}", ("✓ meets " if p else "✗ misses ") + target))
ui.html_block(f'<p class="mini" style="margin:0 0 6px">SYSTEM “{ui.esc(main)}”</p>')
ui.kpis(tiles)

metrics = list(NAMES)
df = pd.DataFrame({s: {NAMES[m][0]: d["mean"].get(m) for m in metrics} for s, d in systems.items()})
df.insert(0, "Target", [f"{TARGETS[m][0]} {TARGETS[m][1]}" if m in TARGETS else "" for m in metrics])
with st.container(key="glass_table"):
    ui.section("", "All systems", "mean over runs")
    st.dataframe(df, width="stretch", column_config={s: st.column_config.NumberColumn(format="percent") for s in systems})

c1, _ = st.columns([1, 3])
if c1.button("Build / refresh safety report", type="primary", icon=":material/description:"):
    (run_dir / "SAFETY_REPORT.md").write_text(build(run_dir), encoding="utf-8")
if (run_dir / "SAFETY_REPORT.md").exists():
    with st.expander("Safety report", expanded=True, icon=":material/health_and_safety:"):
        st.markdown((run_dir / "SAFETY_REPORT.md").read_text(encoding="utf-8"))
