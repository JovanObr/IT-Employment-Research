"""A1 tests: no network. `fetch` is replaced by a fake that serves tiny XBRL 'frames' replies."""
import json

import pandas as pd
import pytest
import requests

from collectors import sec


def frame(*pairs):
    return json.dumps({"data": [{"cik": c, "entityName": f"Co{c}", "val": v} for c, v in pairs]}).encode()


def make_fetch(table):
    """table: {(tag, period): bytes}; anything missing behaves like a 404."""
    def fake(url, **kw):
        tag = url.split("/us-gaap/")[1].split("/")[0]
        period = url.rsplit("/", 1)[1].removesuffix(".json")
        if (tag, period) not in table:
            raise requests.HTTPError("404")
        return table[(tag, period)]
    return fake


def test_instant_periods_only_past_quarter_ends():
    import datetime as dt
    got = list(sec._instant_periods(2024, 2024, today=dt.date(2024, 7, 15)))
    assert got == ["CY2024Q1I", "CY2024Q2I"]


def test_period_kind():
    assert sec._period_kind("CY2020Q1I") == "instant"
    assert sec._period_kind("CY2020") == "annual"
    assert sec._period_kind("CY2020Q2") == "quarter"


def test_tag_priority_and_company_filter(monkeypatch):
    monkeypatch.setattr(sec, "fetch", make_fetch({
        ("NetIncomeLoss", "CY2020Q1"): frame((1, 10), (2, 20), (99, 5)),
        ("ProfitLoss", "CY2020Q1"): frame((1, 111), (3, 30)),   # cik 1 has both: higher-priority tag wins
    }))
    df = sec.fetch_concept_frames("net_income", sec.FIN_FLOWS["net_income"], ["CY2020Q1"], {1, 2, 3})
    got = df.set_index("cik")["value"].to_dict()
    assert got == {1: 10, 2: 20, 3: 30}          # 99 is not a matched company
    assert df.set_index("cik").loc[1, "tag"] == "NetIncomeLoss"


def test_missing_frames_give_empty_table(monkeypatch):
    monkeypatch.setattr(sec, "fetch", make_fetch({}))
    df = sec.fetch_concept_frames("gross_profit", ["GrossProfit"], ["CY2020Q1"], {1})
    assert df.empty and list(df.columns) == sec.FIN_COLUMNS


def test_derived_q4_needs_all_inputs():
    rows = [("CY2020Q1", 10), ("CY2020Q2", 20), ("CY2020Q3", 30), ("CY2020", 100),      # complete
            ("CY2021Q1", 1), ("CY2021", 50)]                                              # incomplete
    fin = pd.DataFrame([{"cik": 1, "period": p, "concept": "rnd", "value": v, "kind": sec._period_kind(p),
                         "tag": "x"} for p, v in rows])
    out = sec.add_derived_q4_long(fin)
    q4 = out[out["kind"] == "derived_q4"]
    assert q4["period"].tolist() == ["CY2020Q4"] and q4["value"].tolist() == [40]


def test_negative_values_are_kept(monkeypatch):
    monkeypatch.setattr(sec, "fetch", make_fetch({("OperatingIncomeLoss", "CY2022Q1"): frame((1, -5.5))}))
    df = sec.fetch_concept_frames("operating_income", ["OperatingIncomeLoss"], ["CY2022Q1"], {1})
    assert df["value"].iloc[0] == -5.5


def test_coverage_table_counts_quarters():
    rows = [{"cik": 1, "period": f"CY2020Q{q}I", "concept": "assets", "value": 1.0, "kind": "instant", "tag": "Assets"}
            for q in (1, 2, 3, 4)]
    rows += [{"cik": 1, "period": f"CY{y}Q{q}I", "concept": "assets", "value": 1.0, "kind": "instant", "tag": "Assets"}
             for y in (2021,) for q in (1, 2, 3, 4)]                      # cik 1: 8 quarters
    rows += [{"cik": 2, "period": "CY2020Q1I", "concept": "assets", "value": 1.0, "kind": "instant", "tag": "Assets"}]
    cov = sec.coverage_table(pd.DataFrame(rows), {1, 2, 3}).set_index("concept")
    assert cov.loc["assets", "companies_any"] == 2
    assert cov.loc["assets", "companies_8q"] == 1
    assert cov.loc["assets", "share_8q"] == pytest.approx(1 / 3, abs=1e-3)
    assert cov.loc["net_income", "companies_any"] == 0


def test_at_least_five_concepts():
    assert len(sec.FIN_FLOWS) + len(sec.FIN_INSTANTS) >= 5


def test_collect_financials_end_to_end(monkeypatch, tmp_path):
    table = {}
    for tag, per, val in [("NetIncomeLoss", "CY2020Q1", 1), ("NetIncomeLoss", "CY2020Q2", 2),
                          ("NetIncomeLoss", "CY2020Q3", 3), ("NetIncomeLoss", "CY2020", 20),
                          ("Assets", "CY2020Q1I", 500)]:
        table[(tag, per)] = frame((7, val))
    monkeypatch.setattr(sec, "fetch", make_fetch(table))
    monkeypatch.setattr(sec, "RAW", tmp_path)
    monkeypatch.setattr(sec, "ensure_dirs", lambda: None)
    monkeypatch.setenv("CONTACT_EMAIL", "test@example.com")
    pd.DataFrame({"cik": [7], "layoffs_company": ["Seven"]}).to_csv(tmp_path / "sec_company_matches.csv", index=False)
    monkeypatch.setattr(sec, "record", lambda *a, **k: {"ok": True})
    out = sec.collect_financials(2020)
    assert out == [{"ok": True}]
    df = pd.read_csv(tmp_path / "sec_financials_quarterly.csv")
    assert list(df.columns) == sec.FIN_COLUMNS
    assert set(df["kind"]) >= {"quarter", "annual", "instant", "derived_q4"}
    assert df[(df["period"] == "CY2020Q4")]["value"].iloc[0] == 14


def test_source_registered():
    assert "sec_fin" in sec.SOURCES


def _row(cik, period, concept, value, kind="quarter"):
    return {"cik": cik, "period": period, "concept": concept, "value": value, "kind": kind, "tag": "x"}


def test_derived_sga_and_gross_profit_fill_gaps_only():
    fin = pd.DataFrame([
        _row(1, "CY2021Q1", "sales_marketing", 30), _row(1, "CY2021Q1", "g_and_a", 20),         # -> sga 50
        _row(2, "CY2021Q1", "sales_marketing", 5), _row(2, "CY2021Q1", "g_and_a", 5),
        _row(2, "CY2021Q1", "sga", 999),                                                        # reported: keep
        _row(1, "CY2021Q1", "cost_of_revenue", 40),                                             # rev 100 -> gp 60
        _row(2, "CY2021Q1", "cost_of_revenue", 1), _row(2, "CY2021Q1", "gross_profit", 77),     # reported: keep
        _row(3, "CY2021Q1", "sales_marketing", 9),                                              # no G&A: nothing
    ])
    rev = pd.DataFrame({"cik": [1, 2], "period": ["CY2021Q1"] * 2, "revenue": [100, 100]})
    out = sec.add_derived_concepts(fin, rev)
    get = lambda cik, c: out[(out["cik"] == cik) & (out["concept"] == c)]["value"].tolist()
    assert get(1, "sga") == [50] and get(2, "sga") == [999] and get(3, "sga") == []
    assert get(1, "gross_profit") == [60] and get(2, "gross_profit") == [77]


def test_derived_concepts_without_revenue_file():
    fin = pd.DataFrame([_row(1, "CY2021Q1", "sales_marketing", 1), _row(1, "CY2021Q1", "g_and_a", 2),
                        _row(1, "CY2021Q1", "cost_of_revenue", 3)])
    out = sec.add_derived_concepts(fin, None)
    assert out[out["concept"] == "sga"]["value"].tolist() == [3]
    assert "gross_profit" not in set(out["concept"])


# ----------------------------------------------------------------------------- A2: SIC universe
def test_is_tech_sic_ranges():
    for ok in ("3571", "3663", "3674", "7372", 7379, "7370"):
        assert sec.is_tech_sic(ok), ok
    for bad in ("3580", "3660", "3680", "7380", "6770", "", None, "abc"):
        assert not sec.is_tech_sic(bad), bad


def test_parse_submission_keeps_sic_as_text():
    got = sec.parse_submission({"name": "Acme Inc", "sic": "7372", "sicDescription": "Services-Prepackaged Software",
                                "tickers": ["ACME", "ACMEW"]})
    assert got == {"name": "Acme Inc", "sic": "7372", "sic_description": "Services-Prepackaged Software", "ticker": "ACME"}
    assert sec.parse_submission({})["sic"] == ""


def test_build_universe_keeps_matched_outside_tech():
    info = {1: {"name": "SoftCo", "sic": "7372", "sic_description": "Software", "ticker": "SFT"},
            2: {"name": "BankCo", "sic": "6022", "sic_description": "State commercial banks", "ticker": "BNK"},
            3: {"name": "Retailer", "sic": "5961", "sic_description": "Catalog & mail-order", "ticker": "RTL"},
            4: None}                                            # lookup failed (404)
    quarters = pd.Series({1: 20, 2: 12, 3: 9, 4: 10})
    uni = sec.build_sic_universe({1, 2, 4}, quarters, {4: "Ghost Co"}, matched={1, 3}, fetcher=lambda c: info[c])
    u = uni.set_index("cik")
    assert list(uni.columns) == sec.UNIVERSE_COLUMNS
    assert set(u.index) == {1, 2, 3, 4}                         # matched cik 3 added although not in `ciks`
    assert u.loc[1, ["is_tech", "matched_layoff", "in_universe"]].tolist() == [True, True, True]
    assert u.loc[2, ["is_tech", "in_universe"]].tolist() == [False, False]
    assert u.loc[3, ["is_tech", "matched_layoff", "in_universe"]].tolist() == [False, True, True]   # positive outside SIC
    assert u.loc[4, "name"] == "Ghost Co" and u.loc[4, "sic"] == ""
    assert u.loc[3, "revenue_quarters"] == 9


def test_universe_report_selection_share(caplog):
    uni = pd.DataFrame([
        {"cik": 1, "name": "a", "sic": "7372", "sic_description": "Software", "ticker": "", "is_tech": True,
         "matched_layoff": True, "in_universe": True, "revenue_quarters": 10},
        {"cik": 2, "name": "b", "sic": "5961", "sic_description": "Retail", "ticker": "", "is_tech": False,
         "matched_layoff": True, "in_universe": True, "revenue_quarters": 10},
        {"cik": 3, "name": "c", "sic": "7372", "sic_description": "Software", "ticker": "", "is_tech": True,
         "matched_layoff": False, "in_universe": True, "revenue_quarters": 10}], columns=sec.UNIVERSE_COLUMNS)
    with caplog.at_level("INFO", logger="covid_it_data"):
        sec.universe_report(uni)
    text = caplog.text
    assert "1 of 2 matched layoff companies (50%)" in text
    assert "2 tech" in text


def test_universe_source_registered():
    assert "sec_universe" in sec.SOURCES


def test_collect_universe_end_to_end(monkeypatch, tmp_path):
    rows = []                                    # cik 1: 3 years of Q1-Q3 + annual (12 quarters); cik 2: only 2 quarters
    for y in (2019, 2020, 2021):
        for p in (f"CY{y}Q1", f"CY{y}Q2", f"CY{y}Q3", f"CY{y}"):
            rows.append({"cik": 1, "entityName": "SoftCo", "val": 10.0, "period": p, "tag": "Revenues", "rank": 0})
    for p in ("CY2021Q1", "CY2021Q2"):
        rows.append({"cik": 2, "entityName": "Tiny", "val": 1.0, "period": p, "tag": "Revenues", "rank": 0})
    monkeypatch.setattr(sec, "fetch_frames", lambda a, b: pd.DataFrame(rows))
    monkeypatch.setattr(sec, "fetch_submission", lambda cik: {"name": f"N{cik}", "sic": "7372",
                                                                "sic_description": "Software", "ticker": "T"})
    monkeypatch.setattr(sec, "RAW", tmp_path)
    monkeypatch.setattr(sec, "ensure_dirs", lambda: None)
    monkeypatch.setattr(sec, "record", lambda *a, **k: {"ok": True})
    monkeypatch.setenv("CONTACT_EMAIL", "test@example.com")
    pd.DataFrame({"cik": [9], "layoffs_company": ["Nine"]}).to_csv(tmp_path / "sec_company_matches.csv", index=False)
    # build_sic_universe takes `fetcher` as a default argument bound at import, so patch it there too
    monkeypatch.setattr(sec.build_sic_universe, "__defaults__", (lambda cik: {"name": f"N{cik}", "sic": "7372",
                        "sic_description": "Software", "ticker": "T"}, 250))
    assert sec.collect_universe(2019) == [{"ok": True}, {"ok": True}]
    uni = pd.read_csv(tmp_path / "sec_universe_sic.csv", dtype={"sic": str})
    assert sorted(uni["cik"]) == [1, 9]          # cik 2 has < 8 quarters and no layoff: not looked up
    assert uni.set_index("cik").loc[9, "matched_layoff"]
    rv = pd.read_csv(tmp_path / "sec_revenue_universe.csv")
    assert set(rv["cik"]) == {1}                 # revenue for universe companies that have any (cik 9 has none in the frames)


def test_collect_financials_includes_tech_comparison_companies(monkeypatch, tmp_path):
    seen = {}
    def fake_fetch_financials(ciks, start_year=2015, end_year=None):
        seen["ciks"] = set(ciks)
        return pd.DataFrame([{"cik": c, "period": "CY2020Q1", "concept": "net_income", "value": 1.0,
                              "kind": "quarter", "tag": "x"} for c in sorted(ciks)])
    monkeypatch.setattr(sec, "fetch_financials", fake_fetch_financials)
    monkeypatch.setattr(sec, "RAW", tmp_path)
    monkeypatch.setattr(sec, "ensure_dirs", lambda: None)
    monkeypatch.setattr(sec, "record", lambda *a, **k: {"ok": True})
    monkeypatch.setenv("CONTACT_EMAIL", "test@example.com")
    pd.DataFrame({"cik": [9], "layoffs_company": ["Nine"]}).to_csv(tmp_path / "sec_company_matches.csv", index=False)
    pd.DataFrame({"cik": [1, 2, 9], "is_tech": [True, False, False], "sic": ["7372", "6022", "5961"]}
                 ).to_csv(tmp_path / "sec_universe_sic.csv", index=False)
    sec.collect_financials(2020)
    assert seen["ciks"] == {1, 9}                # matched (9) + tech comparison (1); the non-tech bank (2) is skipped
