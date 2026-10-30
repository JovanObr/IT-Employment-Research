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

### D4 Tests and preview
- `tests/test_viz_text_geo.py`: for each function, a smoke test on a synthetic frame (right number of traces, no exception on NaN, inputs not
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
docs/tasks/MILESTONE_petar_ch4_ch5.md. Do D1, then the chapter 4 functions, then D2 and the map, in that order, on a branch named
milestone/ch4-ch5-figures. Do not edit viz_theme.py or files owned by Stream A. Test with synthetic data only, never commit raw text, keys or data/raw.
All visible text is Slovenian; numbers in titles come from the data. Open the pull request on Monday 2 November at noon even if the stretch item is not done."
