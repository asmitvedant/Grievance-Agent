"""Smoke tests of both Streamlit apps with Streamlit's AppTest (no browser, mock LLM)."""
import json

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from grievance_agent.config import ROOT, reload_settings

STUDENT = str(ROOT / "app" / "student_app.py")
STAFF = str(ROOT / "app" / "staff_app.py")


@pytest.fixture(autouse=True)
def file_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    reload_settings()
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def html(at) -> str:
    return " ".join(m.value for m in at.markdown)


def click(at, label):
    [b for b in at.button if b.label == label][0].click().run()


def start(at):
    at.toggle[0].set_value(True).run()
    click(at, "Start")


def staff_signed_in():
    rv = AppTest.from_file(STAFF, default_timeout=60).run()
    assert "Staff portal" in html(rv)
    rv.text_input[0].input("Asha")
    rv.text_input[1].input("test-pass")
    click(rv, "Sign in")
    return rv


def test_student_flow_and_reviewer():
    at = AppTest.from_file(STUDENT, default_timeout=60).run()
    assert "Before you start" in html(at)
    start(at)
    at.chat_input[0].set_value("Seniors are ragging us in Block C every weekend. Call me on 9876543210.").run()
    at.chat_input[0].set_value("I want the anti-ragging squad to visit the hostel.").run()
    assert "Thank you" in html(at) and "9876543210" not in html(at)
    click(at, "Review my record")
    assert "Check your record" in html(at)
    click(at, "Submit")
    case_id = at.session_state["case_id"]
    assert "Submitted" in html(at) and case_id in html(at)

    rv = staff_signed_in()
    assert "Case inbox" in html(rv)
    assert rv.radio(key="open_case").value == case_id
    assert "Locked until you have read" in html(rv)
    rv.checkbox(key=f"read_{case_id}").check().run()
    body = html(rv)
    assert "9876543210" not in body and "[PHONE]" in body
    assert "SGRC priority queue" in body and "verbatim" in body


def test_wrong_password_is_refused():
    rv = AppTest.from_file(STAFF, default_timeout=60).run()
    rv.text_input[0].input("Asha")
    rv.text_input[1].input("nope")
    click(rv, "Sign in")
    assert rv.error and "Wrong password" in rv.error[0].value
    assert "Case inbox" not in html(rv)


def test_crisis_flow():
    at = AppTest.from_file(STUDENT, default_timeout=60).run()
    start(at)
    at.chat_input[0].set_value("I keep thinking about killing myself.").run()
    assert at.session_state["stage"] == "crisis"
    assert "112" in html(at) and "You are not alone" in html(at)


def test_student_text_is_escaped_in_reviewer_view():
    at = AppTest.from_file(STUDENT, default_timeout=60).run()
    start(at)
    at.chat_input[0].set_value("My bus pass <script>alert(1)</script> was cancelled in March.").run()
    click(at, "Review my record")
    click(at, "Submit")
    rv = staff_signed_in()
    assert "<script>" not in html(rv) and "&lt;script&gt;" in html(rv)


def test_rubric_and_results_pages():
    run = ROOT / "results" / "pytest-run"
    run.mkdir(parents=True, exist_ok=True)
    try:
        (run / "rubric_items.jsonl").write_text(json.dumps({"item_id": "DTEST01", "dialogue": [
            {"role": "student", "text": "My bus stop was removed."}, {"role": "assistant", "text": "When did that start?"}]}) + "\n")
        (run / "rubric_key.json").write_text(json.dumps({"DTEST01": {"system": "full", "case_id": "C001"}}))
        at = staff_signed_in()
        at.switch_page("staff/rubric.py").run()
        at.selectbox[0].select(run).run()
        assert at.text_input[0].value == "Asha"          # rater name defaults to the signed-in reviewer
        click(at, "Save and next")
        assert at.success and "rated every dialogue" in at.success[0].value
        assert (run / "ratings.csv").exists()
        at.switch_page("staff/evaluation.py").run()
        assert not at.exception
    finally:
        for p in run.glob("*"):
            p.unlink()
        run.rmdir()
