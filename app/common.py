"""Shared Streamlit helpers: heavy components are loaded once per server process."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__file__).resolve().parent
for p in (ROOT, APP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402

from grievance_agent.config import get_settings  # noqa: E402
from grievance_agent.embeddings import get_embedder  # noqa: E402
from grievance_agent.harness import GrievanceAgent  # noqa: E402
from grievance_agent.llm import get_llm  # noqa: E402
from grievance_agent.store import Store  # noqa: E402
from grievance_agent.verifier import get_nli  # noqa: E402


@st.cache_resource(show_spinner="Loading local models...")
def shared():
    s = get_settings()
    return s, Store(s.database_url), get_llm(s), get_embedder(s.embed_backend, s.embed_model), get_nli(s.nli_backend, s.nli_model)


def get_agent() -> GrievanceAgent:
    if "agent" not in st.session_state:
        s, store, llm, emb, nli = shared()
        st.session_state.agent = GrievanceAgent(s, store=store, llm=llm, embedder=emb, nli=nli)
    return st.session_state.agent
