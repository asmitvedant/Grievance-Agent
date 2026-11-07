"""Demo data, case tracking and admin page (mock LLM, no browser)."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from grievance_agent.config import ROOT, reload_settings
from grievance_agent.demo import DEMO_CASES, clear_demo, seed_demo
from grievance_agent.taxonomy import HUMAN_REVIEW_AMBIGUOUS, SGRC_PRIORITY, SGRC_STANDARD, URGENT_ALERT


def test_demo_cases_cover_every_queue_and_hide_pii(agent):
    res = seed_demo(agent)
    assert len(res) == len(DEMO_CASES)
    routes = {title.split(" (")[0]: route for title, _, route in res}
    assert routes["Hidden crisis sign"] == URGENT_ALERT
    assert routes["Vague account"] == HUMAN_REVIEW_AMBIGUOUS
    assert routes["Ragging in the hostel"] == SGRC_PRIORITY and routes["Caste remarks in class"] == SGRC_PRIORITY
    assert routes["Scholarship delay"] == SGRC_STANDARD
    pii_id = [cid for t, cid, _ in res if t.startswith("Personal details")][0]
    text = agent.store.dump_case_text(pii_id)
    assert "9876543210" not in text and "riya.k@example.com" not in text and "2345 6789 0123" not in text
    assert clear_demo(agent.store) == len(DEMO_CASES)
    assert all(agent.store.get_case(cid) is None for _, cid, _ in res)


@pytest.fixture
def file_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    reload_settings()
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


STUDENT = str(ROOT / "app" / "student_app.py")
STAFF = str(ROOT / "app" / "staff_app.py")


def _click(at, label):
    [b for b in at.button if b.label == label][0].click().run()


def _run_case(home):
    home.toggle[0].set_value(True).run()
    _click(home, "Start")
    home.chat_input[0].set_value("My bus stop near the library was removed last month.").run()
    _click(home, "Review my record")
    _click(home, "Submit")
    return home.session_state["case_id"]


def test_track_my_case(file_db):
    home = AppTest.from_file(STUDENT, default_timeout=60).run()
    cid = _run_case(home)
    tr = AppTest.from_file(STUDENT, default_timeout=60).run()
    tr.switch_page("student/track.py").run()
    tr.text_input[0].input(cid.lower())
    _click(tr, "Check status")
    assert any("Received" in s.value for s in tr.subheader)
    tr.text_input[0].input("NOSUCHCASE01")
    _click(tr, "Check status")
    assert tr.error and "No case found" in tr.error[0].value


def test_admin_page_loads_demo_and_lists_cases(file_db):
    import re
    ad = AppTest.from_file(STAFF, default_timeout=120).run()
    ad.text_input[0].input("Admin")
    ad.text_input[1].input("test-pass")
    _click(ad, "Sign in")
    ad.switch_page("staff/admin.py").run()
    assert "System status" in " ".join(m.value for m in ad.markdown)
    _click(ad, "Load demo cases")
    assert ad.success and "Loaded" in ad.success[0].value
    body = " ".join(m.value for m in ad.markdown)
    assert re.search(r"All cases</div><div class=\"v\">6<", body)
    assert re.search(r"Unacknowledged alerts</div><div class=\"v\">1<", body)


def test_dotenv_strips_inline_comments(tmp_path, monkeypatch):
    from grievance_agent import config
    f = tmp_path / ".env"
    f.write_text("LLM_MODEL=qwen2.5:7b-instruct            # low-RAM laptops: qwen2.5:3b-instruct\n"
                 "SUPPORT_CONTACTS='Emergency: 112 | Desk #4'\nX_PLAIN=abc\n")
    for k in ("LLM_MODEL", "SUPPORT_CONTACTS", "X_PLAIN"):
        monkeypatch.delenv(k, raising=False)
    config._load_dotenv(f)
    import os
    assert os.environ["LLM_MODEL"] == "qwen2.5:7b-instruct"
    assert os.environ["SUPPORT_CONTACTS"] == "Emergency: 112 | Desk #4" and os.environ["X_PLAIN"] == "abc"
