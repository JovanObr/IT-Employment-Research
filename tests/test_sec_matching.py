"""SEC company-name normalisation and matching (alias > exact > prefix > fuzzy)."""
import pandas as pd
import pytest

from collectors import sec


@pytest.mark.parametrize("raw,want", [
    ("Amazon.com, Inc.", "amazon"), ("Booking.com", "booking"), ("AT&T Inc", "at and t"),
    ("The Walt Disney Company", "walt disney"), ("Meta Platforms, Inc.", "meta platforms"),
    ("Shopify Inc.", "shopify"), ("", ""),
])
def test_norm(raw, want):
    assert sec.norm(raw) == want


TICKERS = pd.DataFrame([
    {"cik": 1, "ticker": "UBER", "title": "Uber Technologies, Inc."},
    {"cik": 2, "ticker": "RIVN", "title": "Rivian Automotive, Inc. / DE"},
    {"cik": 3, "ticker": "AMAT", "title": "APPLIED MATERIALS INC /DE"},
    {"cik": 4, "ticker": "GOOGL", "title": "Alphabet Inc."},
    {"cik": 5, "ticker": "SHOP", "title": "Shopify Inc."},
])
FRAMES = pd.DataFrame([
    {"cik": 77, "entityName": "Zendesk, Inc."},          # delisted: only in the frames
    {"cik": 78, "entityName": "Twitter, Inc."},
])


@pytest.fixture
def universe():
    return sec.build_universe(TICKERS, FRAMES)


def match(names, universe, aliases=None):
    out = sec.match_companies(names, universe, TICKERS, aliases or {})
    return out.set_index("layoffs_company") if len(out) else out


def test_exact_match_is_not_flagged(universe):
    m = match(["Shopify"], universe)
    assert m.loc["Shopify", "cik"] == 5 and m.loc["Shopify", "match_type"] == "exact"
    assert m.loc["Shopify", "needs_review"] == 0


def test_alias_wins_and_is_not_flagged(universe):
    m = match(["Google"], universe, {"google": "GOOGL"})
    assert m.loc["Google", "cik"] == 4 and m.loc["Google", "match_type"] == "alias"
    assert m.loc["Google", "needs_review"] == 0
    m2 = match(["Foo"], universe, {"foo": "77"})            # alias by numeric CIK
    assert m2.loc["Foo", "cik"] == 77


def test_prefix_match_flagged_for_review(universe):
    m = match(["Uber", "Rivian"], universe)
    assert m.loc["Uber", "cik"] == 1 and m.loc["Uber", "match_type"] == "prefix"
    assert m.loc["Rivian", "cik"] == 2 and m.loc["Rivian", "needs_review"] == 1


def test_fuzzy_match_flagged_and_needs_same_first_token(universe):
    m = match(["Applied Material", "Material Applied"], universe)
    assert m.loc["Applied Material", "cik"] == 3 and m.loc["Applied Material", "match_type"] == "fuzzy"
    assert m.loc["Applied Material", "needs_review"] == 1
    assert "Material Applied" not in m.index


def test_delisted_company_found_through_frames(universe):
    m = match(["Zendesk", "Twitter"], universe)
    assert m.loc["Zendesk", "cik"] == 77 and m.loc["Zendesk", "name_source"] == "frames"
    assert m.loc["Twitter", "cik"] == 78
    assert 77 not in set(TICKERS["cik"])                   # it really is not in the current-filer list


def test_unknown_company_is_not_matched(universe):
    assert len(match(["Totally Unknown Startup"], universe)) == 0


def test_ambiguous_prefix_is_not_guessed():
    t = pd.DataFrame([{"cik": 1, "ticker": "AA", "title": "Alpha Labs Inc"},
                      {"cik": 2, "ticker": "AB", "title": "Alpha Systems Inc"}])
    u = sec.build_universe(t, pd.DataFrame(columns=["cik", "entityName"]))
    out = sec.match_companies(["Alpha"], u, t, {})
    assert len(out) == 0                                   # two different CIKs share the prefix
