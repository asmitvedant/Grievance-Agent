"""Student intake: consent -> conversation -> check the record -> submit (or withdraw at any point)."""
from __future__ import annotations

import streamlit as st

import ui
from common import get_agent, shared
from grievance_agent.llm import LLMError
from grievance_agent.taxonomy import CATEGORIES, ROUTE_STUDENT_MESSAGE

settings = shared()[0]
ss = st.session_state
ss.setdefault("stage", "consent")
STEPS = ["Consent", "Tell us", "Check record", "Submitted"]


def reset() -> None:
    for k in ("stage", "case_id", "record", "decision"):
        ss.pop(k, None)
    ss.stage = "consent"


def help_card() -> None:
    with st.container(key="glass_help"):
        ui.html_block(f'<div class="sec"><div class="n" style="background:{ui.GREEN}">{ui.ms("support_agent")}</div>'
                      '<h3>Need to talk to someone now?</h3></div>' + ui.help_contacts(settings.support_contacts))
        st.caption("This assistant is an AI intake tool. It is not a counsellor and cannot give medical or legal advice.")


ui.mock_banner(settings)

# ------------------------------------------------------------------ consent
if ss.stage == "consent":
    ui.hero("Raise a concern, safely.", "Tell us what happened in your own words. A person in the Grievance Cell reads every case.",
            eyebrow=f"Student Grievance Cell · {settings.institution_name}", icon="verified_user")
    ui.steps(STEPS, 0)
    with st.container(key="glass_consent"):
        ui.html_block('<div class="sec"><h3>Before you start</h3></div>' + "".join([
            ui.row("smart_toy", ui.INDIGO, "An AI intake tool, not a counsellor",
                   "It helps you put your grievance into words. People in the Grievance Cell decide what happens."),
            ui.row("shield_lock", ui.BLUE, "What is kept",
                   "Your messages, with phone numbers, ID numbers, emails and health details removed automatically, and the record you approve."),
            ui.row("group", ui.PURPLE, "Who can see it",
                   "Authorised members of the Grievance Cell and the Students' Grievance Redressal Committee."),
            ui.row("schedule", ui.TEAL, "How long",
                   f"Until {settings.retention_days} days after your case is closed. Then it is deleted."),
            ui.row("undo", ui.ORANGE, "Your choice", "You can withdraw and delete your data at any time."),
            ui.row("sos", ui.RED, "In danger right now?", "Call <b>112</b>. Don't wait for this form."),
        ]))
        agree = st.toggle("I understand and want to continue", key="agree")
        if st.button("Start", type="primary", disabled=not agree, width="stretch", icon=":material/arrow_forward:"):
            ss.case_id = get_agent().start_case(consent=True)
            ss.stage = "chat"
            st.rerun()
    help_card()
    st.stop()

agent = get_agent()
case_id = ss.case_id

# ------------------------------------------------------------------ chat
if ss.stage in ("chat", "crisis"):
    ui.hero("Tell us what happened", "Take your time. Short messages are fine.", eyebrow="Private conversation", icon="lock")
    ui.steps(STEPS, 1)
    if ss.stage == "crisis":
        calls = "".join(f'<a class="call" href="tel:{n}">{ui.ms("call")} {n}</a>' for n in ("112", "14416"))
        ui.html_block(f'<div class="crisis">{ui.ms("health_and_safety")}<h2>You are not alone</h2>'
                      '<p>A member of staff has been alerted and will contact you.</p>'
                      '<p>If you are in immediate danger, call 112 now. Tele-MANAS is free, any time.</p>'
                      f'{calls}</div>')
    hist = agent.history(case_id)
    with st.container(key="glass_chat"):
        ui.html_block(f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                      f'<span class="mini">{ui.ms("lock")} Personal details are removed before saving</span>'
                      f'{ui.pill("Ref " + case_id, ui.BLUE, "tag")}</div>')
        ui.html_block(ui.bubbles([(h["role"], h["text"]) for h in hist]))
    msg = st.chat_input("Message")
    if msg:
        try:
            with st.spinner("Thinking…"):
                r = agent.handle_message(case_id, msg)
            if r.crisis:
                ss.stage = "crisis"
        except LLMError as exc:
            st.error(f"The local language model is not responding. Please try again shortly. ({exc})")
        st.rerun()
    if ss.stage == "chat":
        n_student = sum(1 for h in hist if h["role"] == "student")
        if n_student >= 3:
            st.info("When you have said everything you want to, tap **Review my record**. You can still add or correct things after that.",
                    icon=":material/task_alt:")
        c1, c2 = st.columns(2)
        if c1.button("Review my record", type="primary", disabled=n_student == 0, width="stretch", icon=":material/fact_check:"):
            with st.spinner("Preparing your record from your own words…"):
                ss.record = agent.build_record(case_id)
            ss.stage = "review"
            st.rerun()
        with c2.container(key="danger_withdraw"):
            if st.button("Withdraw and delete my data", width="stretch", icon=":material/delete:"):
                agent.withdraw(case_id)
                ss.stage = "withdrawn"
                st.rerun()
    else:
        help_card()

# ------------------------------------------------------------------ review
elif ss.stage == "review":
    ui.hero("Check your record", "This is what the Grievance Cell will receive. Statements are copied from your own words.",
            eyebrow="Nothing is sent until you submit", icon="visibility")
    ui.steps(STEPS, 2)
    rr = ss.record
    with st.container(key="glass_record"):
        if rr.record is None:
            st.warning("We couldn't build a record automatically. You can still submit: a person will read your full account.")
        else:
            rec = rr.record
            cat = CATEGORIES.get(rec["category"], rec["category"])
            parts = [f'<div class="sec"><h3>Your record</h3><span class="sub">{ui.pill(cat, ui.INDIGO, "label")}</span></div>',
                     f'<p class="mini" style="margin:0">{ui.ms("format_quote")} WHAT HAPPENED · YOUR EXACT WORDS</p>']
            parts += [ui.quote(c["quote"], color=ui.BLUE) for c in rec["claims"]]
            if rec["beliefs"]:
                parts.append(f'<p class="mini" style="margin:14px 0 0">{ui.ms("psychology")} WHAT YOU BELIEVE · RECORDED AS YOUR VIEW, NOT AS A FACT</p>')
                parts += [ui.quote(b, color=ui.PURPLE) for b in rec["beliefs"]]
            if rec.get("requested_outcome"):
                parts.append(f'<p class="mini" style="margin:14px 0 0">{ui.ms("flag")} WHAT YOU WOULD LIKE</p>')
                parts.append(ui.quote(rec["requested_outcome"], color=ui.GREEN))
            if rec.get("neutral_summary"):
                parts.append(f'<p class="mini" style="margin:14px 0 4px">{ui.ms("notes")} SUMMARY FOR THE COMMITTEE</p>'
                             f'<p style="margin:0;color:var(--ink2)">{ui.esc(rec["neutral_summary"])}</p>')
            ui.html_block("".join(parts))
            if rec.get("dropped_unverified"):
                st.info(f"{len(rec['dropped_unverified'])} statement(s) were left out because they did not match your exact words. "
                        "A reviewer can still read your full conversation.", icon=":material/rule:")
            if rec.get("flagged_instructions"):
                st.info("Instructions to the system were not added to the record.", icon=":material/block:")
            if rec.get("missing"):
                st.caption("Things the committee may ask you about: " + ", ".join(rec["missing"]))
    c1, c2, c3 = st.columns(3)
    if c1.button("Submit", type="primary", width="stretch", icon=":material/send:"):
        ss.decision = agent.submit(case_id)
        ss.stage = "done"
        st.rerun()
    if c2.button("Add or correct something", width="stretch", icon=":material/edit:"):
        ss.stage = "chat"
        st.rerun()
    with c3.container(key="danger_withdraw2"):
        if st.button("Withdraw and delete", width="stretch", icon=":material/delete:"):
            agent.withdraw(case_id)
            ss.stage = "withdrawn"
            st.rerun()

# ------------------------------------------------------------------ done
elif ss.stage == "done":
    ui.steps(STEPS, 3)
    with st.container(key="glass_done"):
        ui.html_block(f'<div class="success"><div class="check">{ui.ms("check")}</div>'
                      '<h2 style="margin:0">Submitted</h2>'
                      f'<p style="color:var(--ink2);max-width:480px;margin:8px auto">{ui.esc(ROUTE_STUDENT_MESSAGE[ss.decision.route])}</p>'
                      f'<p class="mini" style="margin:14px 0 0">YOUR CASE REFERENCE</p><div class="ref">{ui.esc(case_id)}</div>'
                      '<p class="mini">Keep it safe. You need it to check progress.</p></div>')
        c1, c2 = st.columns(2)
        c1.page_link("student/track.py", label="Track my case", icon=":material/travel_explore:", width="stretch")
        if c2.button("Start a new grievance", width="stretch", icon=":material/add:"):
            ss.pop("agent", None)
            reset()
            st.rerun()

elif ss.stage == "withdrawn":
    with st.container(key="glass_withdrawn"):
        ui.html_block(f'<div class="success"><div class="check" style="background:linear-gradient(180deg,#a1a1a6,#8E8E93);'
                      f'box-shadow:0 18px 36px -12px #8E8E93">{ui.ms("delete")}</div><h2 style="margin:0">Deleted</h2></div>')
        st.info("Your conversation and record have been deleted. Only a note that a deletion took place is kept.")
        if st.button("Start again", type="primary", width="stretch"):
            reset()
            st.rerun()
