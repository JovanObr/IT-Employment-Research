"""Hacker News keyword rules (collectors/hn.features). Known limitation: no negation handling."""
import pytest

from collectors import hn


def f(text):
    return hn.features(text)


@pytest.mark.parametrize("text,expected", [
    ("Acme | Remote (US) | Python", 1), ("Fully REMOTE team", 1), ("Remotely hosted", 0), ("onsite only", 0),
])
def test_remote_flag(text, expected):
    assert f(text)["remote"] == expected


@pytest.mark.parametrize("text", ["Junior Engineer", "Summer internship", "entry-level role", "Entry level",
                                  "New grad welcome", "recent graduates"])
def test_junior_flag_positive(text):
    assert f(text)["junior"] == 1


def test_junior_flag_negative_and_known_false_positive():
    assert f("Senior backend engineer")["junior"] == 0
    # documented weakness: negation is ignored, so this is (wrongly) flagged. If this ever flips, update the notes.
    assert f("No interns, no juniors please")["junior"] == 1


def test_ai_rule_is_case_sensitive_for_short_acronyms_only():
    assert f("We build AI products")["ai_ml"] == 1
    assert f("Experience with LLMs")["ai_ml"] == 1
    assert f("said the maid, ai")["ai_ml"] == 0           # lowercase 'ai' / words containing it do not count
    assert f("machine learning engineer")["ai_ml"] == 1   # long phrases are case-insensitive
    assert f("Deep Learning and NLP")["ai_ml"] == 1


def test_senior_and_visa_and_games():
    out = f("Staff engineer, visa sponsorship, Unity gameplay")
    assert out["senior"] == 1 and out["visa"] == 1 and out["games"] == 1


def test_company_guess_from_first_line_pipe():
    out = f("Acme Corp | Berlin | Remote\nWe are hiring.")
    assert out["company_guess"] == "Acme Corp"
    assert out["first_line"].startswith("Acme Corp")
    assert f("No pipe in the first line\nAcme | x")["company_guess"] == ""
    assert out["text_len"] == len("Acme Corp | Berlin | Remote\nWe are hiring.")


def test_skills_present():
    out = f("Python, C++, C#, Kubernetes, Postgres")
    assert out["python"] == out["cpp"] == out["csharp"] == out["kubernetes"] == out["postgres"] == 1
    assert out["rust"] == 0


def test_clean_html():
    raw = "Acme | Remote<p>We use &lt;Rust&gt;<br>and Go &amp; C"
    assert hn.clean_html(raw) == "Acme | Remote\nWe use <Rust>\nand Go & C"
    assert hn.clean_html(None) == ""


def test_title_regex():
    m = hn.TITLE_RE.match("Ask HN: Who is hiring? (March 2021)")
    assert m and m.groups() == ("March", "2021")
    assert hn.TITLE_RE.match("Ask HN: Who wants to be hired? (March 2021)") is None
