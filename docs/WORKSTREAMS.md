# Two-person work split: 21 to 27 October 2026

Two people, each with a coding agent, work **in parallel, at their own hours, with minimal interference**.
The **repository is the only channel**: nothing is sent around as files. Each agent reads `AGENTS.md`
(project context), this file (the plan) and its own task brief in `docs/tasks/`.

## 0. One-time setup (about 45 minutes)

1. *(owner)* Create a **private** GitHub repo and push the project (`.gitignore` is already correct).
2. *(owner)* Invite the collaborator. Optional but recommended: Settings > Branches > protect `main` (pull request + passing CI).
3. *(collaborator)* Clone, then `pip install -r requirements.txt -r requirements-dev.txt`.
4. *(both)* Set **your own** keys: `CONTACT_EMAIL`, `CENSUS_API_KEY` (free), optional `BLS_API_KEY`. Never share or commit keys.
5. *(both)* Download the layoffs CSV into `data/manual/` (Kaggle "swaptr/layoffs-2022"; it is not in git on purpose). The dataset is updated over time, so for identical numbers the owner can share his copy privately.
6. *(both)* `python collect.py`, then `python build_master.py` and `python build_metro_panel.py` (about 15 minutes; QCEW is the slow part). Raw data is local, never committed.

## 1. The split at a glance

| | **Stream A: Companies and causes** | **Stream B: Text, geography and quality** |
|---|---|---|
| Theme | who gets laid off, and why | what employers ask for, where IT moved, and a safety net |
| Tasks | **A1** SEC financials; **A2** tech-company universe (SIC); **A3** company-quarter panel + layoff-risk baseline; **A4** *(stretch)* macro data and causes tests | **B1** tests + CI *(do first)*; **B2** Hacker News text analysis; **B3** geography maps and code-stability check; **B4** *(stretch)* County Business Patterns for the 5 missing metros |
| New notebooks | `03_company_layoff_risk`, `04_causes` | `05_skills_nlp`, `06_geography_maps` |
| Main outputs | `data/processed/company_panel.csv` | `data/processed/hn_topics_monthly.csv`, map figures, `tests/` |
| Effort | about 16 to 22 hours | about 14 to 19 hours |

Tasks inside a stream are sequential. The two streams do not depend on each other this week.

## 2. Who touches what

| Stream A owns | Stream B owns |
|---|---|
| `collectors/sec.py`, `collectors/macro.py` (new), `collectors/eurostat.py` | `collectors/hn.py`, `collectors/fhfa.py`, `collectors/census_*.py` (incl. new gazetteer/CBP collectors) |
| `analysis/company_*.py`, `analysis/causes.py` | `analysis/hn_text.py`, `analysis/geo.py`, `analysis/metro_models.py` |
| `masterfile/adapters.py`, `build_master.py`, `config/segment_map.csv`, `config/company_aliases.csv` | `build_metro_panel.py`, `config/msad_parent.csv`, `tests/`, `.github/`, `requirements-dev.txt` |
| notebooks `03_*`, `04_*`; `data/processed/company_panel.csv` | notebooks `05_*`, `06_*`; `data/processed/hn_topics_monthly.csv` |

**Unowned this week** (change only after agreeing via *Requests* in `docs/STATUS.md`): `collect.py` (frozen: it auto-discovers new collectors), `collectors/common.py`, `collectors/qcew.py`, `bls.py`, `nomis.py`, `indeed.py`, `layoffs.py`, notebooks `01_*` and `02_*`, `AGENTS.md` (the owner updates it at the Day-7 sync).

**Shared files** (edit only by *adding*; on a conflict keep both versions): `README.md`, `DATA_DICTIONARY.md`, `DATA_SOURCES.md`, `requirements.txt`.
**Do not edit** the other stream's files. If you need a change there, write a line under *Requests* in `docs/STATUS.md`.

**Adding a data source needs no edit to `collect.py`.** Put `SOURCES = {"name": lambda args: [...]}` at module level in your new `collectors/<module>.py`; it is discovered automatically.
Anything new this week produces its **own processed table**; only Stream A may change the master file.

## 3. Git workflow (five rules)

1. Work on a branch: `stream-a/<topic>` or `stream-b/<topic>`. Never commit to `main` directly.
2. Start every session with `git pull --rebase origin main`; push at least once a day.
3. Small pull requests (one task or part of a task). The other person (or agent) skims and merges when CI is green.
4. Never commit keys, `data/raw`, `data/cache`, `data/manual` or `layoffs_clean.csv`. Never force-push `main`.
5. After a task: tick it in `docs/STATUS.md` (your section only) with one line on what changed.

## 4. Rhythm (no meetings needed)

- **Start:** pull, read `docs/STATUS.md`. **End:** push, update your status section.
- **Day 4:** a 15-minute check or an async note: blockers, anything to re-split.
- **Day 7 (about 30 minutes):** show results, merge everything, decide next week. Each notebook owner converts his notebook to Slovenian and the explainer gets updated.

## 5. Where the streams meet

- Read-only shared inputs: `data/processed/layoffs_clean.csv`, `data/raw/sec_company_matches.csv`, the master file.
- Optional link for later: Hacker News `company_guess` vs layoff company names.
- Merge conflicts should be rare because outputs are separate tables and file ownership does not overlap.

## 6. Cut line if you fall behind

A drops **A4**. B drops **B4** and part (b)/(c) of **B3**. Both keep B1 and A1 to A3 as the minimum.

## 7. Starter prompts (paste once into your agent)

**Stream A:** "You are Stream A (companies and causes) on this repository. Read AGENTS.md, then docs/WORKSTREAMS.md and docs/tasks/STREAM_A_companies_and_causes.md. Do tasks A1, A2, A3 in order (A4 only if time allows), on a branch named stream-a/<topic>. Do not edit files owned by Stream B. Test with mocks (no network in tests), never commit keys or data folders, and when a task is done tick it in docs/STATUS.md under Stream A with a one-line summary."

**Stream B:** "You are Stream B (text, geography and quality) on this repository. Read AGENTS.md, then docs/WORKSTREAMS.md and docs/tasks/STREAM_B_text_geo_tests.md. Do B1 first (tests and CI), then B2, then B3 (B4 only if time allows), on a branch named stream-b/<topic>. Do not edit files owned by Stream A. Never commit keys or data folders, and when a task is done tick it in docs/STATUS.md under Stream B with a one-line summary."
