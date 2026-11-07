"""Student app: file a grievance and track it.   Run:  streamlit run app/student_app.py
Staff use the separate portal:                    streamlit run app/staff_app.py --server.port 8502
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: F401,I001  (sets sys.path)

import streamlit as st

import ui

st.set_page_config(page_title="Grievance Cell", page_icon="💬", layout="centered", initial_sidebar_state="collapsed")
ui.inject_theme("student")

nav = st.navigation([
    st.Page("student/intake.py", title="New grievance", icon=":material/edit_square:", default=True),
    st.Page("student/track.py", title="Track my case", icon=":material/travel_explore:"),
], position="top")
nav.run()
