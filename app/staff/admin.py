"""Admin: system health, queue statistics, demo data, export, retention and the full audit log."""
from __future__ import annotations

import re

import altair as alt
import pandas as pd
import requests
import streamlit as st

import ui
from common import get_agent, shared
from grievance_agent.demo import DEMO_REF, clear_demo, seed_demo
from grievance_agent.llm import LLMError
from grievance_agent.prompts import PROMPT_VERSION
from grievance_agent.taxonomy import CATEGORIES, ROUTE_LABELS, ROUTES

settings, store, llm, emb, nli = shared()
actor = f"reviewer:{st.session_state.reviewer}"

ui.hero("Admin", "System health, statistics, demo data, retention and the audit log.", eyebrow="Manage", icon="tune")

# ------------------------------------------------------------------ statistics
cases = store.list_cases(None)
df = pd.DataFrame([{
    "Case": c.id, "Opened (UTC)": c.created_at.strftime("%Y-%m-%d %H:%M"), "Status": c.status,
    "Queue": ROUTE_LABELS.get(c.route or "", "–"), "Category": CATEGORIES.get(c.category or "", "–").split(" (")[0],
    "Urgency": c.urgency_level, "Outcome": c.reviewer_outcome or "", "Demo": "yes" if c.student_ref == DEMO_REF else "",
} for c in cases], columns=["Case", "Opened (UTC)", "Status", "Queue", "Category", "Urgency", "Outcome", "Demo"])
n_open = int(df["Status"].isin(["submitted", "in_review", "crisis"]).sum())
ui.kpis([
    ("folder_open", ui.BLUE, "All cases", len(df), "live cases in the store"),
    ("pending_actions", ui.INDIGO, "Open", n_open, "submitted, in review or alerted"),
    ("emergency", ui.RED, "Unacknowledged alerts", store.unacknowledged_alerts(), "need a person now"),
    ("priority_high", ui.PURPLE, "Priority queue", int((df["Queue"] == ROUTE_LABELS["SGRC_PRIORITY"]).sum()), "sensitive or statutory"),
    ("task_alt", ui.GREEN, "Closed", int((df["Status"] == "closed").sum()), f"deleted {settings.retention_days} days after closing"),
])
tab_over, tab_cases, tab_demo, tab_ret, tab_audit = st.tabs(["Overview", "Cases", "Demo data", "Retention", "Audit log"])

# ------------------------------------------------------------------ overview: health + charts
with tab_over:
    left, right = st.columns([1.1, 1], gap="large")

    def ollama_status() -> tuple[bool, str]:
        if settings.llm_backend != "ollama":
            return True, f"backend {settings.llm_backend}"
        try:
            tags = requests.get(f"{settings.ollama_host}/api/tags", timeout=3).json().get("models", [])
        except Exception:
            return False, f"Ollama is not running at {settings.ollama_host}. Open the Ollama app or run `ollama serve`."
        names = [x.get("name", "") for x in tags]
        if not any(n == settings.llm_model or n.split(":")[0] == settings.llm_model for n in names):
            return False, f"Model {settings.llm_model} not downloaded. Run `ollama pull {settings.llm_model}`."
        return True, f"{settings.llm_model} ready"

    with left, st.container(key="glass_health"):
        ui.section("", "System status")
        ok, msg = ollama_status()
        db = re.sub(r"//[^@]*@", "//***@", settings.database_url)
        rows = [
            ("Language model", ui.GREEN if ok else ui.RED, msg),
            ("Database", ui.GREEN, db + ("  (development: use MySQL for real use)" if db.startswith("sqlite") else "")),
            ("Embeddings", ui.ORANGE if "hashing" in emb.name else ui.GREEN,
             emb.name + ("  (fallback: run scripts/download_models.py)" if "hashing" in emb.name else "")),
            ("NLI checker", ui.ORANGE if "fallback" in nli.name else ui.GREEN, nli.name),
            ("Privacy filter", ui.GREEN, f"{settings.pii_backend}; kept {settings.retention_days} days after closing"),
            ("Prompt version", ui.BLUE, PROMPT_VERSION),
            ("Reviewer password", ui.ORANGE if settings.reviewer_password == "change-me" else ui.GREEN,
             "still the default: set REVIEWER_PASSWORD in .env" if settings.reviewer_password == "change-me" else "set"),
        ]
        ui.html_block("".join(f'<div class="status-row"><span class="dot" style="background:{c};box-shadow:0 0 0 4px {c}22"></span>'
                              f'<b>{ui.esc(n)}</b><span class="mono">{ui.esc(d)}</span></div>' for n, c, d in rows))
        if st.button("Test the language model", icon=":material/bolt:"):
            try:
                with st.spinner("Asking the model…"):
                    out = llm.chat([{"role": "user", "content": "Reply with the single word: ready"}], task="dialogue", max_tokens=5)
                st.success(f"Model replied: {out.strip()[:40]!r}")
            except LLMError as exc:
                st.error(f"Model did not respond: {exc}")

    with right, st.container(key="glass_charts"):
        ui.section("", "Cases by queue")
        if len(df):
            q = pd.DataFrame({"Queue": [ROUTE_LABELS[r] for r in ROUTES],
                              "Cases": [int((df["Queue"] == ROUTE_LABELS[r]).sum()) for r in ROUTES],
                              "colour": [ui.ROUTE_STYLE[r][0] for r in ROUTES]})
            bars = alt.Chart(q).mark_bar(cornerRadiusEnd=6, height=22).encode(
                x=alt.X("Cases:Q", title=None, axis=alt.Axis(grid=True, gridColor="#00000010", tickMinStep=1, domain=False)),
                y=alt.Y("Queue:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=12, domain=False, ticks=False)),
                color=alt.Color("colour:N", scale=None, legend=None),
                tooltip=["Queue", "Cases"])
            labels = bars.mark_text(align="left", dx=6, fontWeight=700, color="#1d1d1f").encode(text="Cases:Q", color=alt.value("#1d1d1f"))
            st.altair_chart((bars + labels).properties(height=190).configure_view(stroke=None).configure(background="transparent"),
                            width="stretch")
            s = df["Status"].map(lambda x: ui.STATUS_STYLE.get(x, (ui.GRAY, x))[1]).value_counts()
            ui.html_block('<p class="mini" style="margin:6px 0">BY STATUS</p><div style="display:flex;gap:6px;flex-wrap:wrap">'
                          + "".join(ui.pill(f"{k} · {v}", ui.GRAY) for k, v in s.items()) + "</div>")
        else:
            ui.html_block(f'<div class="lockcard">{ui.ms("bar_chart")}No cases yet. Load the demo cases to see the charts.</div>')
    if settings.llm_backend == "mock":
        st.warning("LLM_BACKEND=mock: the app is using the test stub, not Qwen. Set LLM_BACKEND=ollama in .env.")

# ------------------------------------------------------------------ cases
with tab_cases:
    if len(df):
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Case": st.column_config.TextColumn(width="small"), "Demo": st.column_config.TextColumn(width="small")})
        st.download_button("Download case list (CSV, no conversation text)", df.to_csv(index=False).encode(), "cases.csv", "text/csv",
                           icon=":material/download:", on_click=lambda: store.audit(None, actor, "cases_exported", {"n": len(df)}))
    else:
        st.info("No cases yet. Students can start one in the student app, or load the demo cases.")

# ------------------------------------------------------------------ demo data
with tab_demo, st.container(key="glass_demo"):
    ui.section("", "Demo data")
    st.write("Six example conversations, one for each queue: a routine complaint, ragging, caste remarks, personal details "
             "removed, a vague account and a hidden crisis sign. They go through the real system, so with Qwen this takes "
             "a few minutes on a laptop.")
    if msg := st.session_state.pop("demo_msg", None):
        st.success(msg)
    d1, d2 = st.columns(2)
    if d1.button("Load demo cases", type="primary", icon=":material/play_arrow:", width="stretch"):
        bar = st.progress(0.0, text="Starting…")
        try:
            res = seed_demo(get_agent(), lambda i, n, t: bar.progress(i / n, text=t))
            store.audit(None, actor, "demo_loaded", {"n": len(res)})
            st.session_state.demo_msg = "Loaded: " + ", ".join(f"{cid} → {ROUTE_LABELS[r]}" for _, cid, r in res)
            st.rerun()
        except LLMError as exc:
            st.error(f"The language model did not respond, so the demo stopped: {exc}")
    if d2.button("Remove demo cases", icon=":material/delete_sweep:", width="stretch"):
        st.session_state.demo_msg = f"Removed {clear_demo(store)} demo case(s)."
        st.rerun()

# ------------------------------------------------------------------ retention
with tab_ret, st.container(key="glass_ret"):
    ui.section("", "Retention")
    st.write(f"Closed cases are deleted {settings.retention_days} days after closing (RETENTION_DAYS in .env).")
    if st.button("Purge closed cases past retention now", icon=":material/auto_delete:"):
        n = store.purge_expired(settings.retention_days)
        store.audit(None, actor, "retention_purge_run", {"purged": n})
        st.success(f"Purged {n} case(s).")

# ------------------------------------------------------------------ audit
with tab_audit:
    st.dataframe(pd.DataFrame([{"At (UTC)": a.at.strftime("%Y-%m-%d %H:%M:%S"), "Case": a.case_id or "", "Actor": a.actor,
                                "Action": a.action} for a in store.recent_audit(200)]), hide_index=True, width="stretch")
    st.caption("Latest 200 actions across all cases.")
