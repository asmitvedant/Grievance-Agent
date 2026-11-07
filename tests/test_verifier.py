from grievance_agent.verifier import LexicalNLI, Verifier, span_match

SRC = "My scholarship has been on hold for four months. I think they are ignoring me on purpose."


def test_span_match_ignores_case_and_punctuation():
    assert span_match("my scholarship has been on hold for four months", SRC)
    assert span_match("My scholarship has been on hold ... four months", SRC)
    assert not span_match("My scholarship has been on hold for six months", SRC)


def test_record_verification_and_fps():
    v = Verifier(LexicalNLI(), 0.5)
    rec = {"claims": [{"quote": "My scholarship has been on hold for four months.", "kind": "event"},
                      {"quote": "The office lost my documents.", "kind": "event"}],
           "beliefs": ["I think they are ignoring me on purpose."], "requested_outcome": None,
           "neutral_summary": "The student reports the scholarship has been on hold for four months."}
    rep = v.verify_record(rec, SRC)
    assert [i.preserved for i in rep.quoted] == [True, False, True]
    assert abs(rep.fps - 2 / 3) < 1e-9
    assert rep.items[-1].kind == "summary" and rep.items[-1].preserved
