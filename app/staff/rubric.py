"""Blinded human rating of dialogues with the E1-E7 rubric."""
from __future__ import annotations

import json

import streamlit as st

import ui
from common import ROOT, shared
from evaluation.rubric import RUBRIC, SCALE, append_rating_csv, load_ratings, summarise

settings, store, *_ = shared()
ui.hero("Rubric rating", "Dialogues are blinded: you won't see which system wrote them. " + SCALE + ".",
        eyebrow="Empathy & manipulation · E1–E7", icon="star_rate")

runs = sorted([p for p in (ROOT / "results").glob("*") if (p / "rubric_items.jsonl").exists()], reverse=True)
if not runs:
    st.info("No evaluation runs yet. Run `python -m evaluation.run_eval` first.")
    st.stop()
c1, c2 = st.columns(2)
run_dir = c1.selectbox("Evaluation run", runs, format_func=lambda p: p.name)
rater = c2.text_input("Your rater name (use the same name every session)", value=st.session_state.get("reviewer", "")).strip()
if not rater:
    st.stop()

items = [json.loads(line) for line in open(run_dir / "rubric_items.jsonl", encoding="utf-8")]
done = {r["item_id"] for r in load_ratings(run_dir, store) if r["rater"] == rater}
todo = [it for it in items if it["item_id"] not in done]
st.progress(len(done) / len(items), text=f"{len(done)} of {len(items)} rated by {rater}")

if todo:
    it = todo[0]
    left, right = st.columns([1.25, 1], gap="large")
    with left, st.container(key="glass_dialogue"):
        ui.section("", f"Dialogue {it['item_id']}", f"{len(it['dialogue'])} turns")
        with st.container(height=560, border=False):
            ui.html_block(ui.bubbles([(t["role"], t["text"]) for t in it["dialogue"]], me_label="Student", ai_label="Assistant"))
    with right, st.container(key="glass_rate"):
        ui.section("", "Your scores", "rate the assistant only")
        with st.form(f"rate_{it['item_id']}", border=False):
            scores = {}
            for k, (name, desc) in RUBRIC.items():
                scores[k] = st.select_slider(f"{k} · {name}", options=[1, 2, 3, 4, 5], value=3, help=desc)
                st.caption(desc)
            comment = st.text_area("Comment (optional)")
            if st.form_submit_button("Save and next", type="primary", width="stretch", icon=":material/arrow_forward:"):
                store.add_rating(run_dir.name, it["item_id"], rater, scores, comment or None)
                append_rating_csv(run_dir, it["item_id"], rater, scores, comment)
                st.rerun()
else:
    with st.container(key="glass_rated"):
        ui.html_block(f'<div class="success"><div class="check">{ui.ms("check")}</div><h2 style="margin:0">All done</h2></div>')
        st.success("You have rated every dialogue in this run. Thank you.")

summary = summarise(run_dir, store)
if summary.get("n_ratings"):
    with st.expander("Current results (unblinded: open only after rating is finished)", icon=":material/visibility:"):
        st.json(summary)
