"""Case inbox: source-first review, urgent alerts, decisions and the audit trail."""
from __future__ import annotations

import streamlit as st

import ui
from common import shared
from grievance_agent.store import utcnow
from grievance_agent.taxonomy import (CATEGORIES, HUMAN_REVIEW_AMBIGUOUS, ROUTE_LABELS, ROUTE_PRIORITY, SGRC_PRIORITY,
                                      SGRC_STANDARD, URGENT_ALERT)

settings, store, *_ = shared()
ss = st.session_state
actor = f"reviewer:{ss.reviewer}"

all_cases = store.list_cases(("crisis", "submitted", "in_review", "closed"))
open_cases = [c for c in all_cases if c.status != "closed"]


def unacked(cid: str) -> int:
    return sum(1 for e in store.escalations(cid) if e.acknowledged_at is None and e.route == URGENT_ALERT)


ui.hero("Case inbox", "Read the student's own words first. The AI record unlocks after that.", eyebrow="Review queue", icon="inbox")
count = lambda r: sum(1 for c in open_cases if c.route == r)  # noqa: E731
ui.kpis([
    ("emergency", ui.RED, "Urgent alerts", store.unacknowledged_alerts(), "not yet acknowledged"),
    ("help", ui.ORANGE, "Human review", count(HUMAN_REVIEW_AMBIGUOUS), "unclear accounts"),
    ("priority_high", ui.PURPLE, "Priority", count(SGRC_PRIORITY), "sensitive or statutory"),
    ("inbox", ui.BLUE, "Standard", count(SGRC_STANDARD), "normal process"),
    ("task_alt", ui.GREEN, "Closed", sum(1 for c in all_cases if c.status == "closed"), "all time"),
])

if not all_cases:
    with st.container(key="glass_empty"):
        ui.html_block(f'<div class="lockcard">{ui.ms("inbox")}<b>No cases in the queue.</b><br>'
                      'New grievances appear here as soon as a student submits. To try it out, load the demo cases on the Admin page.</div>')
        st.info("No cases in the queue.")
    st.stop()

FILTERS = {"Open": None, "Urgent": URGENT_ALERT, "Review": HUMAN_REVIEW_AMBIGUOUS, "Priority": SGRC_PRIORITY,
           "Standard": SGRC_STANDARD, "Closed": "closed"}
f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
flt = f1.segmented_control("Filter", list(FILTERS), default="Open", key="flt", label_visibility="collapsed") or "Open"
q = f2.text_input("Search", placeholder="Search by reference or category", label_visibility="collapsed", key="q").strip().lower()

want = FILTERS[flt]
cases = [c for c in all_cases if (c.status == "closed") == (want == "closed") and (want in (None, "closed") or c.route == want)]
if q:
    cases = [c for c in cases if q in c.id.lower() or q in CATEGORIES.get(c.category or "", "").lower()]
cases.sort(key=lambda c: (ROUTE_PRIORITY.get(c.route or "", 9), -unacked(c.id), c.created_at))

left, right = st.columns([1.25, 2.3], gap="large")
with left:
    if not cases:
        st.caption("Nothing matches this filter.")
        st.stop()
    colour_name = {URGENT_ALERT: "red", HUMAN_REVIEW_AMBIGUOUS: "orange", SGRC_PRIORITY: "violet", SGRC_STANDARD: "blue"}
    ids = [c.id for c in cases]
    by_id = {c.id: c for c in cases}
    if ss.get("open_case") not in ids:
        ss.open_case = ids[0]
    with st.container(key="inbox"):
        case_id = st.radio(
            "Cases", ids, key="open_case", label_visibility="collapsed",
            format_func=lambda cid: (f":{colour_name.get(by_id[cid].route, 'gray')}[●] "
                                     f"{CATEGORIES.get(by_id[cid].category or '', 'Awaiting category').split(' (')[0].split(',')[0]}"
                                     + ("  :red[**· ALERT**]" if unacked(cid) else "")),
            captions=[f"{ROUTE_LABELS.get(c.route or '', 'Intake')} · {c.id} · {ui.ago(c.created_at)}" for c in cases])

case = store.get_case(case_id)
turns = store.get_turns(case_id)

with right:
    # ---------------------------------------------------------------- header
    with st.container(key="glasstight_head"):
        ui.html_block(
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            f'<h2 style="margin:0;padding:0;font-size:1.45rem">Case <span class="mono" style="font-size:1.2rem">{ui.esc(case.id)}</span></h2>'
            f'{ui.route_pill(case.route, solid=True)}{ui.status_pill(case.status)}{ui.urgency_pill(case.urgency_level)}'
            f'<span class="mini" style="margin-left:auto">{ui.ms("schedule")} opened {case.created_at:%d %b %Y, %H:%M} UTC</span></div>')

    if case.route == URGENT_ALERT and unacked(case_id):
        with st.container(key="glassalert"):
            ui.html_block(f'<div style="display:flex;gap:12px;align-items:center"><div class="row" style="border:none;padding:0">'
                          f'<div class="ic" style="background:{ui.RED}">{ui.ms("emergency")}</div></div>'
                          '<div><b style="color:#b3261e">URGENT: risk indicators were detected during intake.</b><br>'
                          '<span style="color:var(--ink2)">Contact the student through the crisis protocol now.</span></div></div>')
            if st.button("I have acknowledged this alert and started the crisis protocol", type="primary", icon=":material/check_circle:"):
                store.acknowledge_escalations(case_id, ss.reviewer)
                store.audit(case_id, actor, "urgent_alert_acknowledged")
                st.rerun()

    # ---------------------------------------------------------------- 1 source first
    with st.container(key="glass_source"):
        ui.section("1", "The student's own words", f"{sum(1 for t in turns if t.role == 'student')} messages · personal details removed")
        with st.container(height=380, border=False):
            ui.html_block(ui.bubbles([(t.role, t.text_redacted) for t in turns if t.role in ("student", "assistant")],
                                     me_label="Student", ai_label="Assistant"))
        read_key = f"read_{case_id}"
        read = st.checkbox("I have read the student's full account", key=read_key)
        if read and not ss.get(read_key + "_logged"):
            store.audit(case_id, actor, "source_read")
            ss[read_key + "_logged"] = True

    # ---------------------------------------------------------------- 2 AI record
    with st.container(key="glass_record"):
        ui.section("2", "AI-prepared record", "verified against the student's words", color=ui.INDIGO if read else ui.GRAY)
        if not read:
            ui.html_block(f'<div class="lockcard">{ui.ms("lock")}<b>Locked until you have read the account</b><br>'
                          'Reading first reduces the pull of the AI summary on your judgement.</div>')
        else:
            rec = store.latest_record(case_id)
            urg = [t.meta.get("urgency", {}) for t in turns if t.role == "student" and t.meta.get("urgency")]
            signals = sorted({r for u in urg for r in u.get("reasons", [])})
            esc_reasons = [r for e in store.escalations(case_id) for r in e.reasons] or ["routine grievance"]
            info = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px">'
                    f'<div class="quote" style="--qc:{ui.ROUTE_STYLE.get(case.route, (ui.GRAY,))[0]}"><span class="mini">QUEUE</span><br>'
                    f'<b>{ui.esc(ROUTE_LABELS.get(case.route or "", "–"))}</b><br>'
                    f'<span class="mini">urgency {ui.esc(case.urgency_level)} · score {case.urgency_score:.2f}</span></div>'
                    f'<div class="quote" style="--qc:{ui.ORANGE}"><span class="mini">WHY IT WAS ROUTED HERE</span><br>'
                    + "<br>".join(f"• {ui.esc(r)}" for r in esc_reasons) + "</div></div>")
            ui.html_block(info)
            if signals:
                st.caption("Urgency signals: " + "; ".join(signals))
            if rec is None:
                st.warning("No record was built (the case may have stopped at an urgent alert).")
            elif "error" in rec.record_json:
                st.warning(f"Record could not be built: {rec.record_json['error']}")
            else:
                r = rec.record_json
                checks = {(i["kind"], i["text"]): i for i in rec.verification_json.get("items", [])}

                def badge(kind: str, text: str) -> str:
                    i = checks.get((kind, text))
                    if not i:
                        return ""
                    if i["preserved"]:
                        return ui.pill("verbatim", ui.GREEN, "verified") + ui.pill(f"entail {i['entail']:.2f}", ui.GRAY)
                    return ui.pill("not verified", ui.ORANGE, "warning")

                parts = [f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">'
                         f'{ui.pill(CATEGORIES.get(r["category"], r["category"]).split(" (")[0], ui.INDIGO, "label")}'
                         f'{ui.pill(f"record v{rec.version}", ui.GRAY)}'
                         + (ui.pill("confirmed by student", ui.GREEN, "how_to_reg") if rec.student_confirmed else "") + "</div>",
                         '<p class="mini" style="margin:6px 0 0">STATEMENTS · VERBATIM</p>']
                parts += [ui.quote(cl["quote"], ui.pill(cl["kind"], ui.BLUE) + badge("claim", cl["quote"]), ui.BLUE) for cl in r["claims"]]
                if r["beliefs"]:
                    parts.append('<p class="mini" style="margin:12px 0 0">STUDENT\'S BELIEFS · NOT FINDINGS OF FACT</p>')
                    parts += [ui.quote(b, badge("belief", b), ui.PURPLE) for b in r["beliefs"]]
                if r.get("requested_outcome"):
                    parts.append('<p class="mini" style="margin:12px 0 0">REQUESTED OUTCOME</p>' + ui.quote(r["requested_outcome"], color=ui.GREEN))
                if r.get("neutral_summary"):
                    parts.append('<p class="mini" style="margin:12px 0 4px">NEUTRAL SUMMARY</p>'
                                 f'<p style="color:var(--ink2);margin:0">{ui.esc(r["neutral_summary"])}</p>')
                ui.html_block("".join(parts))
                if r.get("dropped_unverified"):
                    with st.expander(f"{len(r['dropped_unverified'])} item(s) removed by the verifier", icon=":material/rule:"):
                        for d in r["dropped_unverified"]:
                            st.markdown(f"- ({d['kind']}) {d['text']}")
                if r.get("flagged_instructions"):
                    with st.expander("Instructions to the system found in the conversation (not recorded as claims)", icon=":material/block:"):
                        for fi in r["flagged_instructions"]:
                            st.markdown(f"- {fi}")
                if r.get("missing"):
                    st.caption("Missing information: " + ", ".join(r["missing"]))

    # ---------------------------------------------------------------- 3 decision
    with st.container(key="glass_decision"):
        ui.section("3", "Your decision", "saved to the audit log", color=ui.GREEN if read else ui.GRAY)
        OUTCOMES = ["(choose)", "Forwarded to SGRC", "Needs more information from student",
                    "Referred to Internal Committee (sexual harassment)", "Referred to Anti-Ragging Squad",
                    "Referred to counselling centre", "Crisis protocol completed", "Resolved", "Closed - no action"]
        with st.form(f"decision_{case_id}", border=False):
            d1, d2 = st.columns(2)
            outcome = d1.selectbox("Outcome", OUTCOMES,
                                   index=OUTCOMES.index(case.reviewer_outcome) if case.reviewer_outcome in OUTCOMES else 0)
            cat_keys = list(CATEGORIES)
            category = d2.selectbox("Category", cat_keys,
                                    index=cat_keys.index(case.category) if case.category in cat_keys else len(cat_keys) - 1,
                                    format_func=CATEGORIES.get)
            notes = st.text_area("Notes (do not paste personal identifiers)", value=case.reviewer_notes or "")
            close = st.toggle("Close the case", value=case.status == "closed")
            if st.form_submit_button("Save decision", type="primary", disabled=not read, icon=":material/save:"):
                if outcome == "(choose)":
                    st.error("Choose an outcome.")
                else:
                    store.update_case(case_id, reviewer_outcome=outcome, category=category, reviewer_notes=notes,
                                      status="closed" if close else "in_review", closed_at=utcnow() if close else None)
                    store.audit(case_id, actor, "decision_saved", {"outcome": outcome, "category": category, "closed": close})
                    st.toast("Decision saved", icon=":material/check_circle:")
                    st.rerun()
        if not read:
            st.caption("Saving a decision is enabled after you confirm you have read the account.")

    with st.expander("Audit log", icon=":material/history:"):
        log = store.audit_log(case_id)
        ui.html_block('<div class="timeline">' + "".join(
            f'<div class="tl done"><b>{ui.esc(a.action.replace("_", " "))}</b>'
            f'<span>{a.at:%d %b %H:%M:%S} · {ui.esc(a.actor)}{" · " + ui.esc(str(a.detail)) if a.detail else ""}</span></div>'
            for a in log) + "</div>" if log else '<span class="mini">No actions yet.</span>')
