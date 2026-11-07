"""Employee counts read from 10-K text: the sentence finder, the filing picker and the streaming reader (no network)."""
import pytest

from collectors import sec_headcount as sh


@pytest.mark.parametrize("text,expected", [
    ("As of December 31, 2021, we had approximately 2,447 full-time employees.", 2447),
    ("As of January 31, 2022, we had 2,511 full-time employees located in 14 countries.", 2511),
    ("As of December 31, 2022, we employed approximately 1,200 people worldwide.", 1200),
    ("Our workforce consisted of approximately 3,100 full-time and part-time employees as of June 30, 2021.", 3100),
    ("We had a total of 164,000 employees at year end.", 164000),
    ("At December 31, 2023, we had approximately 1.2 thousand employees.", 1200),
    ("As of December 31, 2021, we had 87 employees.", 87),
    ("Human Capital. As of September 30, 2022, we had approximately 6,800 employees, including 2,000 in research and development.", 6800),
    ("Employees As of December 31, 2019, we had 12 full-time and 9 part-time employees.", 21),
    ("As of December 31, 2021, we had approximately 2,500 full-time and approximately 40 part-time employees.", 2540),
    ("As of October 30, 2021, we had approximately 24,700 employees, of whom approximately 11,000 are in engineering roles.", 24700),
])
def test_headcount_sentences_are_read(text, expected):
    value, snippet, score = sh.find_headcount("Item 1. Business. Some text. " + text + " More text follows.")
    assert value == expected and score >= 2 and snippet[-25:] in text


@pytest.mark.parametrize("text", [
    "In January 2023 we reduced our workforce by approximately 1,000 employees.",
    "Approximately 40% of our employees are located outside the United States.",
    "We hired 500 employees during the year.",
    "In 2021 employees were offered a stock purchase plan.",
    "Our customers include 3,000 enterprises.",
    "The restructuring affected approximately 300 employees.",
    "In these roles, she had oversight for more than 3,000 employees and oversaw operations.",
    "As of December 31, 2019, we had approximately 6,000 employees engaged in R&D activities.",
    "As of December 31, 2021, we had 371 full-time employees in our sales and marketing organization.",
    "As of November 2, 2019, the Company still employed 307 of the 464 employees included in this action.",
    "Accrued expenses consisted of the following at December 31, 2021 (in thousands): 72,498 employee related costs.",
    "We currently have 3 employees and a few consultants.",
    "At December 31, 2019 we employed approximately 2,000 employees in our international operations.",
    "As of December 31, 2022, we employed 34 individuals focused on selling and account management.",
    "As of December 31, 2021, our research and development team was comprised of approximately 994 employees.",
])
def test_sentences_that_are_not_the_headcount_are_ignored(text):
    assert sh.find_headcount(text)[0] is None


def test_the_dated_statement_wins_over_an_earlier_loose_one():
    text = ("We have 40 people in our team. Human capital: As of December 31, 2022, we had approximately 2,050 employees. "
            "Of these, 300 employees work in Europe.")
    assert sh.find_headcount(text)[0] == 2050


def test_html_is_stripped_and_entities_decoded():
    raw = ("<html><head><style>p{}</style></head><body><p>As of December&#160;31,&nbsp;2021, we had approximately "
           "<ix:nonFraction name='dei:x'>2,447</ix:nonFraction> full-time employees.</p></body></html>")
    text = sh.html_to_text(raw)
    assert "style" not in text and "<" not in text
    assert sh.find_headcount(text)[0] == 2447


def test_recheck_corrects_from_the_saved_sentence_or_drops_for_a_new_read():
    import pandas as pd
    done = pd.DataFrame({"accession": ["a", "b", "c", "d"], "employees": [2447.0, 6000.0, None, 9.0],
                         "snippet": ["As of December 31, 2021, we had approximately 2,447 full-time employees",
                                     "As of December 31, 2019, we had approximately 6,000 employees engaged in R&D activities", "",
                                     "As of December 31, 2019, we had 12 full-time and 9 part-time employees"]})
    kept, n = sh.recheck(done)
    assert n == 1 and list(kept["accession"]) == ["a", "c", "d"]
    assert kept.set_index("accession").loc["d", "employees"] == 21


def test_period_year_moves_january_to_march_year_ends_back():
    assert sh.period_year("2022-01-31") == 2021 and sh.period_year("2021-12-31") == 2021 and sh.period_year("2022-06-30") == 2022


def _sub(forms, dates, filing_dates, files=()):
    n = len(forms)
    return {"filings": {"recent": {"accessionNumber": [f"0001-{i}" for i in range(n)], "form": forms, "reportDate": dates,
                                   "primaryDocument": [f"d{i}.htm" for i in range(n)], "filingDate": filing_dates},
                        "files": list(files)}}


def test_annual_filings_keeps_original_10k_one_per_year():
    sub = _sub(["10-K", "10-K/A", "10-Q", "10-K", "10-K"], ["2022-12-31", "2022-12-31", "2023-03-31", "2021-12-31", "2019-12-31"],
               ["2023-02-20", "2023-04-01", "2023-05-01", "2022-02-20", "2018-02-20"])
    f = sh.annual_filings(sub)
    assert list(f["period_year"]) == [2019, 2021, 2022] and set(f["accession"]) == {"0001-0", "0001-3", "0001-4"}


def test_older_pages_are_read_only_when_recent_does_not_reach_2019():
    sub = _sub(["10-K"], ["2023-12-31"], ["2024-02-20"], files=[{"name": "CIK1-submissions-001.json", "filingTo": "2020-12-31"}])
    called = []

    def page(name):
        called.append(name)
        return {"accessionNumber": ["0002-0"], "form": ["10-K"], "reportDate": ["2019-12-31"], "primaryDocument": ["old.htm"]}

    f = sh.annual_filings(sub, page)
    assert called == ["CIK1-submissions-001.json"] and list(f["period_year"]) == [2019, 2023]


class _FakeResponse:
    def __init__(self, chunks):
        self.chunks, self.read = chunks, 0

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        for c in self.chunks:
            self.read += 1
            yield c

    def close(self):
        pass


def test_streaming_stops_once_the_headcount_is_found():
    chunks = [b"<p>Item 1. Business</p>", b"<p>As of December 31, 2021, we had 900 employees.</p>", b"x" * 1000, b"y" * 1000]
    resp = _FakeResponse(chunks)
    value, snippet, n = sh.stream_headcount("u", getter=lambda u: resp)
    assert value == 900 and resp.read == 2 and n < 200


def test_target_companies_are_tech_with_enough_quarters():
    import pandas as pd
    uni = pd.DataFrame({"cik": [1, 2, 3], "is_tech": [True, True, False], "revenue_quarters": [12, 4, 20]})
    assert sh.target_companies(uni) == [1]


def test_collect_needs_a_contact_email(monkeypatch):
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="CONTACT_EMAIL"):
        sh.collect()
