from grievance_agent.pii import redact


def test_redacts_indian_identifiers():
    text = ("Call me on +91 98765 43210 or 9876543210, email asha.k@example.com, Aadhaar 2345 6789 0123, "
            "PAN ABCDE1234F, roll number 21BCE1234. My roommate is diagnosed with tuberculosis, and he is upset.")
    r = redact(text)
    for secret in ("98765", "9876543210", "asha.k@", "2345 6789", "ABCDE1234F", "21BCE1234", "tuberculosis"):
        assert secret not in r.text
    assert r.counts["PHONE"] == 2 and r.counts["EMAIL"] == 1 and r.counts["AADHAAR"] == 1
    assert "and he is upset" in r.text


def test_leaves_ordinary_numbers_alone():
    text = "My fee of Rs 25,500 for the 4th semester was paid on 12 November, room 214."
    assert redact(text).text == text


def test_does_not_eat_words_like_regarding():
    assert redact("I am writing regarding my registration form").text == "I am writing regarding my registration form"
