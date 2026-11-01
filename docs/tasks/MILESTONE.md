# Milestone (due Thursday 2026-11-05): figures for chapters 4 and 5 (Stream B agent)

## Context
The milestone is **complex data visualization**: several series on one axis, small multiples, heatmaps, maps, interactive where doable.
It is delivered as **one Slovenian notebook for a casual audience**, `notebooks/08_zgodba_SL.ipynb`, exported to HTML (and printed to PDF from
the browser). Stream A assembles the notebook and draws chapters 1-3 and 6. **You draw chapter 4 (what employers ask for, Hacker News) and
chapter 5 (where, metro maps).** You deliver *figure functions and the small aggregate files they read*; you do not write the notebook.

Interactive figures use **plotly** (already added to `requirements.txt`; run `pip install -r requirements.txt`). No kaleido, no other new
dependency, no internet at draw time (so no plotly built-in maps: they load their base layer from a CDN).

## Rules (same as WORKSTREAMS.md)
- Work on branch `milestone/ch4-ch5-figures`. Pull first, read `docs/STATUS.md`, `AGENTS.md`, `analysis/viz_theme.py`.
- **Files you own for this task:** `analysis/viz_text_geo.py` (new), `tests/test_viz_text_geo.py` (new), and a small, additive change to
  `analysis/hn_text.py` and `analysis/geo.py` (new functions only; do not change existing behaviour). Edit only your own section of `docs/STATUS.md`.
- **Do not edit** `analysis/viz_theme.py` (Stream A owns it). If you need something changed, write `B asks A: ...` under *Requests* in `docs/STATUS.md`.
- Tests: no network, no real data (`tests/conftest.py` sets a temporary `DATA_DIR`), synthetic frames only. `pytest -q` and
  `python -m compileall -q .` must pass before you push.
- Never commit raw post text, API keys, or `data/raw/`. **Only aggregates may be committed** (the two files in D1 and D2).

## Deliverables

### D1 Hacker News aggregates (committed, no raw text)
1. `data/processed/hn_flags_monthly.csv`, columns `month` (YYYY-MM), `flag` (`remote`, `ai_ml`), `share` (0-1), `n_posts`.
2. `data/processed/hn_change_points.csv`, columns `flag`, `start`, `end` (YYYY-MM), `months`, `mean_share` (the segments notebook 05 already finds
   for remote and ai_ml).
3. Writer: `python -m analysis.hn_text flags` (new sub-command) creates both from the local posts file, using the existing `monthly_share`,
   `binary_segmentation` and `break_months`. **Leave the `junior` flag out**: your own validation shows its recall is about 5 %, so it is not a
   usable measure of junior hiring.
4. Existing `data/processed/hn_topics_monthly.csv` (`month`, `topic`, `share`) is the topic input.

### D2 Map aggregate (committed; public Census coordinates plus our panel)
1. `data/processed/metro_map_data.csv`, one row per metro in `metro_panel.csv`: `cbsa_code` (5-char string), `metro_name`, `lat`, `lon`,
   `size_jobs`, `emp_it_2019`, `emp_it_2024`, `it_growth_pct`, `usable`, `estabs_it_2019`, `estab_growth_pct`, `usable_estab`, `wfh_share_pct_acs2019`.
   Build it from `analysis.geo.load_geo_panel` (needs `census_gazetteer_cbsa.csv`, which stays local). New sub-command: `python -m analysis.geo mapdata`.
2. Metros without a centroid stay in the file with empty `lat`/`lon` and are not drawn.

### D3 Figure functions in `analysis/viz_text_geo.py`
All functions are **pure**: DataFrame(s) in, `plotly.graph_objects.Figure` out, no file reads, no global state, inputs not modified.
Loaders (`load_topics()`, `load_flags()`, `load_change_points()`, `load_map_data()`) are separate small functions that read the committed CSVs.
Every figure uses `analysis.viz_theme` (`base_layout`, `add_event_lines`, `TOPIC_COLORS`, `PALETTE`, `DIVERGING`, and `sl_num` / `sl_pct` for numbers
written with a decimal comma). `analysis/viz.py` (Stream A, chapters 1-3) is a worked example of the same style; read it first.

**Chapter 4**
- `fig_topics_stacked_area(topics) -> Figure`: 10 topics stacked over time, hover shows topic and share in %, event lines (`fed`, `chatgpt`).
- `fig_topics_small_multiples(topics, ncols=5) -> Figure`: one small panel per topic, **shared y axis**, monthly share (thin) and 12-month
  rolling mean (thick), the 2022-11-30 line in each panel, panel title = topic name.
- `fig_topic_year_heatmap(topics) -> Figure`: rows = topics, columns = years, cell = mean share that year, values printed in the cells,
  rows ordered by change between the first and last three years.
- `fig_remote_ai_levels(flags, change_points=None) -> Figure`: remote and AI/ML shares on one axis, with the change-point segment means drawn
  as flat horizontal steps; event lines (`covid`, `fed`, `chatgpt`).

**Chapter 5**
- `fig_metro_map(geo, metric="it_growth_pct") -> Figure`: plain scatter map of the lower 48. The outline is `US48_OUTLINE` from `analysis/geo.py`
  drawn as a grey filled line trace; `x` = lon, `y` = lat; **equal-ish aspect** (`yaxis.scaleanchor="x"`, `scaleratio` about 1.3).
  Bubble area proportional to `size_jobs` (use sqrt for the diameter), colour = growth on `DIVERGING` centred on 0, clipped to a sensible range
  with the colour bar saying so. Hover: metro name, IT jobs 2019, growth in % (Slovenian). Metros whose growth is unusable are **grey crosses with the hover
  text "podatek je skrit", never zero growth**. A dropdown (`updatemenus`) switches between `it_growth_pct` (jobs) and `estab_growth_pct` (establishments)
  and uses the matching `usable` flag.
- `fig_region_small_multiples(geo) -> Figure` *(stretch)*: four panels (Northeast, Midwest, South, West; region from the first state code in
  the metro name), distribution of IT growth per region (strip or box), shared axis, median marked.

### D3b Explanations: every figure needs one (this is part of "done")
For each figure function add a companion `explain_<name>(same data) -> dict` returning four **Slovenian, plain-language** parts, then
`build_explanations(...)` returning them by figure name. The notebook shows them under the figure with `analysis.viz_theme.explanation_markdown`,
which refuses a missing or empty part. The keys and what each part must do:
- `kaj` (what we see): how to read the figure, in two to four short sentences: what is on each axis, what the colours or sizes mean, what to hover over.
- `zakaj` (why we did it): the question the figure answers, in one or two sentences, in everyday words.
- `pomen` (what it means): what the data shows, with **numbers computed from the data passed in** (use `sl_num` / `sl_pct`). If the pattern could come out
  differently with other data, the wording must adapt (for example "narasel" or "padel" chosen by the numbers), not be typed in.
- `omejitve` (what we do not know): the honest limits, always present, never empty: what the data cannot show, what is measured only roughly,
  what could explain the pattern otherwise.
- Style: no more than 3-5 sentences per part; explain every technical word the first time (for example "delež objav" not "TF-IDF", "premik skozi čas" not
  "change point"); no jargon without a gloss; no claims about causes.
`analysis/story_text.py` (Stream A) is the worked example for chapters 1-3; copy its structure.

### D3c Entry point for the notebook (exact signature, so assembly takes minutes)
`analysis/viz_text_geo.py` must expose `build_chapter_4_5() -> dict[str, tuple[plotly.graph_objects.Figure, dict]]`. It loads the committed CSVs itself
(through your loaders) and returns, for every figure, `(figure, explanation)` where `explanation` has the four keys `kaj`, `zakaj`, `pomen`, `omejitve`.
Figure names are fixed and prefixed with the chapter: `4_teme_povrsina`, `4_teme_mali_grafi`, `4_teme_toplotna`, `4_daljava_ui`, `5_zemljevid`
(and `5_regije` if you do the stretch). The notebook shows them in the order of the names. If a CSV is missing, raise a clear error (the notebook
catches it and shows a note in place of the chapter).

### D4 Tests and preview
- `tests/test_viz_text_geo.py`: `build_chapter_4_5()` returns exactly the names above, each with a figure and a complete explanation (use synthetic CSVs written to the temporary data directory); for each `explain_*` function: the four parts are present and non-empty, contain no 'nan' or 'None', and contain the numbers computed
  from the input (change the input and the text changes); a test that the wording flips when the data flips (for example growth vs decline). For each figure function, a smoke test on a synthetic frame (right number of traces, no exception on NaN, inputs not
  modified, hover text contains the metro or topic name, withheld metros are crosses and not zeros, dropdown has two entries). A test that every
  visible string is non-empty Slovenian is not needed; one that no title is hard-coded with a number is: numbers in titles must come from the data.
- `python -m analysis.viz_text_geo preview` writes every figure as `reports/figures_sl/preview_<name>.html` (uses `viz_theme.save_html`) so John can open them.

## Text rules (Slovenian, casual, honest)
- All visible text in Slovenian: titles, axes, hover, legend. Casual but exact; John proofreads before the export.
- A title says what you see, not how it is built. **Any number in a title or annotation is computed from the data passed in, never typed.**
- Terms: odpuščanja (layoffs), delež objav (share of posts), delo na daljavo (remote work), umetna inteligenca (UI) for AI/ML, metro območje,
  rast zaposlenosti v IT 2019-2024, podatek je skrit (withheld), delodajalci (employers).
- Honesty that must survive the casual tone: Hacker News is a startup-skewed corner of the market; the flags are keyword rules; withheld is not zero;
  IT means NAICS 5415 only (software publishers and big tech are not in it); everything is association over time.

## Schedule
| When | What |
|---|---|
| Sat 31 Oct | D1 and the four chapter 4 functions with tests; push the branch |
| Sun 1 Nov | D2, `fig_metro_map`, tests, `preview` command; push |
| Mon 2 Nov, noon | Stretch (`fig_region_small_multiples`) only if everything else is green; **open the pull request at noon either way** |
| Mon 2 - Wed 4 | Fixes requested by review only. No new features after Monday noon |

## Done means
`pytest -q` green on CI; the four D3 chapter 4 functions and `fig_metro_map` exist and open in a browser from `preview`; D1 and D2 files committed;
your line in `docs/STATUS.md` updated with what exists and what does not.

## Prompt to paste into the agent
"You are the Stream B agent on this repository. Read AGENTS.md, docs/WORKSTREAMS.md, docs/STATUS.md, analysis/viz_theme.py and
docs/tasks/MILESTONE.md. Do D1, then the chapter 4 functions with their explanations, then D2 and the map with its explanation, in that order, on a branch named
milestone/ch4-ch5-figures. Do not edit viz_theme.py or files owned by Stream A. Test with synthetic data only, never commit raw text, keys or data/raw.
All visible text is Slovenian; numbers in titles come from the data. Open the pull request on Monday 2 November at noon even if the stretch item is not done."
