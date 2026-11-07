"""Staff portal (reviewers and admins), separate from the student app.
Run:  streamlit run app/staff_app.py --server.port 8502
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import shared  # noqa: I001  (sets sys.path)

import hmac

import streamlit as st

import ui

st.set_page_config(page_title="Grievance Cell · Staff", page_icon="🗂️", layout="wide")
ui.inject_theme("staff")
settings, store, *_ = shared()
ss = st.session_state


def sign_in() -> None:
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.write("")
        with st.container(key="glass_signin"):
            ui.html_block(f'<div class="signin"><div class="appicon">{ui.ms("shield_person")}</div>'
                          '<h2 style="margin:0">Staff portal</h2>'
                          f'<p style="color:var(--ink2);margin:4px 0 6px">Grievance Cell · {ui.esc(settings.institution_name)}</p></div>')
            with st.form("signin", border=False):
                name = st.text_input("Your name", placeholder="e.g. Dr. Asha Rao")
                pw = st.text_input("Password", type="password")
                ok = st.form_submit_button("Sign in", type="primary", width="stretch", icon=":material/login:")
            if ok:
                if name.strip() and hmac.compare_digest(pw, settings.reviewer_password):
                    ss.reviewer = name.strip()
                    store.audit(None, f"reviewer:{ss.reviewer}", "signed_in")
                    st.rerun()
                st.error("Wrong password, or name missing.")
            if settings.reviewer_password == "change-me":
                st.caption("Default password is `change-me`. Set REVIEWER_PASSWORD in .env before any real use.")
        st.caption("Every sign-in and every action is written to the audit log.")


signed_in = bool(ss.get("reviewer"))
alerts = store.unacknowledged_alerts() if signed_in else 0
inbox_title = f"Inbox · {alerts} urgent" if alerts else "Inbox"
nav = st.navigation([
    st.Page("staff/inbox.py", title=inbox_title, icon=":material/inbox:", default=True),
    st.Page("staff/admin.py", title="Admin", icon=":material/tune:"),
    st.Page("staff/rubric.py", title="Rubric rating", icon=":material/star_rate:"),
    st.Page("staff/evaluation.py", title="Evaluation", icon=":material/monitoring:"),
], position="top" if signed_in else "hidden")

if not signed_in:   # every page (including deep links like /admin) shows the sign-in card first
    sign_in()
    st.stop()

with st.sidebar:
    initials = "".join(w[0] for w in ss.reviewer.split()[:2]).upper() or "?"
    ui.html_block(f'<div class="profile"><div class="avatar">{ui.esc(initials)}</div><div><b>{ui.esc(ss.reviewer)}</b>'
                  '<div class="mini">Grievance Cell reviewer</div></div></div>')
    st.write("")
    if alerts:
        ui.html_block(f'<div class="banner" style="background:rgba(255,59,48,.12);border-color:rgba(255,59,48,.35);color:#b3261e">'
                      f'{ui.ms("emergency")} {alerts} urgent alert{"s" if alerts != 1 else ""} not yet acknowledged</div>')
    ui.mock_banner(settings)
    if st.button("Sign out", width="stretch", icon=":material/logout:"):
        store.audit(None, f"reviewer:{ss.reviewer}", "signed_out")
        ss.pop("reviewer")
        st.rerun()

nav.run()
