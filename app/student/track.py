"""Students check the status of a grievance with their case reference. Reviewer notes are never shown."""
from __future__ import annotations

import streamlit as st

import ui
from common import shared
from grievance_agent.taxonomy import CATEGORIES, ROUTE_STUDENT_MESSAGE

settings, store, *_ = shared()

STATUS_TEXT = {
    "intake": ("Not submitted yet", "You started this grievance but did not submit it. Start a new one from New grievance."),
    "crisis": ("Staff alerted", "A member of staff was alerted and will contact you. If you are in danger now, call 112."),
    "submitted": ("Received", "Your grievance is waiting for a member of the Grievance Cell."),
    "in_review": ("Being reviewed", "A member of the Grievance Cell is working on your grievance."),
    "closed": ("Closed", "Your grievance has been closed. Contact the Grievance Cell if you need more help."),
}
ORDER = ["submitted", "in_review", "closed"]

ui.hero("Track my case", "Enter the reference you got when you submitted.", eyebrow="Status", icon="travel_explore")

with st.container(key="glass_track"):
    with st.form("track", border=False):
        ref = st.text_input("Case reference", placeholder="e.g. 3F9A1C27B0D4").strip().upper()
        go = st.form_submit_button("Check status", type="primary", width="stretch", icon=":material/search:")

if go and ref:
    case = store.get_case(ref)
    if case is None or case.source != "live":
        if any(e.event == "deleted" for e in store.consent_events(ref)):
            st.info("This case was withdrawn and its data deleted at your request.")
        else:
            st.error("No case found with that reference. Check it and try again.")
        st.stop()
    label, text = STATUS_TEXT.get(case.status, (case.status, ""))
    color = ui.STATUS_STYLE.get(case.status, (ui.GRAY, ""))[0]
    with st.container(key="glass_status"):
        st.subheader(f"Status: {label}")
        head = (f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:-4px 0 12px">{ui.pill(label, color, "radio_button_checked", solid=True)}'
                f'{ui.pill(CATEGORIES.get(case.category or "", "Category not set yet").split(" (")[0], ui.INDIGO, "label")}</div>'
                f'<p style="color:var(--ink2)">{ui.esc(text)}</p>')
        if case.route and case.status != "intake":
            head += f'<p style="color:var(--ink2)">{ui.esc(ROUTE_STUDENT_MESSAGE.get(case.route, ""))}</p>'
        cur = ORDER.index(case.status) if case.status in ORDER else (0 if case.status == "crisis" else -1)
        steps_html = []
        for i, (key, title, when) in enumerate([
                ("submitted", "Received", f"{case.created_at:%d %b %Y}"),
                ("in_review", "Being reviewed", "A member of staff reads your own words first"),
                ("closed", "Closed", f"{case.closed_at:%d %b %Y}" if case.closed_at else "You'll see the outcome here")]):
            cls = "done" if i < cur or (i == cur and key == "closed") else ("on" if i == cur else "")
            steps_html.append(f'<div class="tl {cls}"><b>{title}</b><span>{ui.esc(when)}</span></div>')
        ui.html_block(head + f'<div class="timeline">{"".join(steps_html)}</div>')
        if case.reviewer_outcome:
            st.success(f"Outcome so far: **{case.reviewer_outcome}**")
        if case.closed_at:
            st.caption(f"Data is deleted {settings.retention_days} days after closing.")
    st.caption("For your privacy, this page shows only the status. Reviewer notes and your conversation are not shown here.")
elif go:
    st.warning("Type your case reference first.")
