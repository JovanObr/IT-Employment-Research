"""Hacker News 'Who is hiring?' text analysis (Stream B2).

Inputs (local only, git-ignored; raw text must not be committed or redistributed)
  data/raw/hn_whoishiring_posts.csv   post_id, thread_month, flags (remote, junior, ai_ml, ...), company_guess
  data/raw/hn_whoishiring_text.csv    post_id, text

What is here
  1. topic model      TF-IDF + NMF, auto labels from top terms, monthly topic shares
  2. change points    plain-numpy binary segmentation (no extra dependency), with a noise-based stopping rule
  3. junior and AI    monthly shares; AI before/after 2022-11-30 with a pre-trend check (association, not cause)
  4. flag validation  random sample of posts to label by hand, then precision and recall with Wilson intervals,
                      plus a cheap negation diagnostic that needs no labels

Command line (from the project root)
  python -m analysis.hn_text run            # topics + change points -> data/processed/hn_topics_monthly.csv
  python -m analysis.hn_text sample         # writes data/manual/hn_validation_sample.csv (100 random posts, to label)
  python -m analysis.hn_text validate       # reads the labelled copy and prints precision / recall
  python -m analysis.hn_text flags          # aggregates only -> hn_flags_monthly.csv, hn_change_points.csv (remote, ai_ml)

Limits to repeat whenever numbers are quoted: the posts are startup-skewed; the flags are keyword rules without
negation handling; the NMF topics depend on k and on the seed.
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from collectors.common import MANUAL, PROCESSED, RAW

CHATGPT = pd.Timestamp("2022-11-30")
# The November 2022 thread is posted on 1 Nov, i.e. BEFORE ChatGPT: threads up to 2022-11 are "before".
LAST_PRE_AI_THREAD = pd.Timestamp("2022-11-01")
SEED = 42

# Words that carry no topic information, plus the logistics words that the keyword flags already measure
# (otherwise one topic would simply be "remote" and the topic shares would repeat the remote share).
EXTRA_STOP = {
    "hiring", "company", "team", "teams", "looking", "join", "apply", "email", "com", "www", "http", "https",
    "work", "working", "experience", "experienced", "engineer", "engineers", "engineering", "developer",
    "developers", "years", "year", "new", "help", "build", "building", "built", "us", "role", "roles",
    "position", "positions", "job", "jobs", "full", "time", "ft", "pt", "send", "resume", "cv", "contact",
    "want", "like", "using", "use", "great", "strong", "good", "ability", "etc", "including", "within",
    "remote", "onsite", "site", "visa", "relocation", "hybrid", "salary", "equity", "usd", "href", "nofollow",
}
TOKEN_PATTERN = r"(?<![\w])[a-z][a-z0-9+#]+(?![\w])"   # keeps c++, c#, ai, ml; splits node.js into node, js
_URL = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+", re.I)


# ------------------------------------------------------------------ loading
def load_posts(path: Path | None = None) -> pd.DataFrame:
    p = pd.read_csv(path or RAW / "hn_whoishiring_posts.csv", dtype={"post_id": str, "thread_id": str})
    p["month"] = pd.to_datetime(p["thread_month"]).dt.to_period("M").dt.to_timestamp()
    return p


def load_text(path: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(path or RAW / "hn_whoishiring_text.csv", dtype={"post_id": str}, keep_default_na=False)


def load_joined() -> pd.DataFrame:
    posts, text = load_posts(), load_text()
    return posts.merge(text, on="post_id", how="inner")


# ------------------------------------------------------------------ 1. topics
def clean_for_topics(text: str) -> str:
    return _URL.sub(" ", str(text)).lower()


def fit_topics(texts: pd.Series, k: int = 10, *, min_df: int | float = 10, max_df: float = 0.5,
               seed: int = SEED, max_features: int = 20000):
    """TF-IDF + NMF. Returns (W normalised so each row sums to 1, topic term table, fitted vectoriser, model, keep mask).
    Rows without any retained term get weight 0 everywhere and are excluded through the mask."""
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

    vec = TfidfVectorizer(preprocessor=clean_for_topics, token_pattern=TOKEN_PATTERN, ngram_range=(1, 2),
                          min_df=min_df, max_df=max_df, sublinear_tf=True, max_features=max_features,
                          stop_words=sorted(set(ENGLISH_STOP_WORDS) | EXTRA_STOP))
    X = vec.fit_transform(texts.fillna(""))
    keep = np.asarray(X.sum(axis=1)).ravel() > 0
    nmf = NMF(n_components=k, init="nndsvd", random_state=seed, max_iter=400)
    W = nmf.fit_transform(X)
    sums = W.sum(axis=1, keepdims=True)
    Wn = np.divide(W, sums, out=np.zeros_like(W), where=sums > 0)
    keep &= sums.ravel() > 0
    terms = np.array(vec.get_feature_names_out())
    rows = []
    for t, comp in enumerate(nmf.components_):
        top = np.argsort(comp)[::-1][:10]
        rows.append({"topic_id": t, "top_terms": ", ".join(terms[top]), "label": f"T{t + 1}: " + ", ".join(terms[top[:3]])})
    return Wn, pd.DataFrame(rows), vec, nmf, keep


def monthly_topic_shares(months: pd.Series, W: np.ndarray, keep: np.ndarray, labels: list[str],
                         method: str = "dominant") -> pd.DataFrame:
    """Share of posts per month and topic. method 'dominant': each post counts for its strongest topic;
    'weights': mean of the normalised topic weights. Both sum to 1 within a month."""
    m = pd.Series(months.to_numpy()[keep])
    Wk = W[keep]
    if method == "dominant":
        M = np.zeros_like(Wk)
        M[np.arange(len(Wk)), Wk.argmax(axis=1)] = 1.0
    elif method == "weights":
        M = Wk
    else:
        raise ValueError("method must be 'dominant' or 'weights'")
    df = pd.DataFrame(M, columns=labels)
    df["month"] = m.to_numpy()
    out = df.groupby("month")[labels].mean().stack().rename("share").reset_index()
    out.columns = ["month", "topic", "share"]
    out["month"] = pd.to_datetime(out["month"]).dt.strftime("%Y-%m")
    return out


def topic_model_monthly(df: pd.DataFrame, k: int = 10, names: dict[int, str] | None = None, **kw):
    """Convenience: fit, label (optionally with hand-written names {topic_id: name}) and return (shares, term table)."""
    W, terms, *_rest, keep = fit_topics(df["text"], k=k, **kw)
    if names:
        terms["label"] = [f"T{r.topic_id + 1}: {names[r.topic_id]}" if r.topic_id in names else r.label
                          for r in terms.itertuples()]
    shares = monthly_topic_shares(df["month"], W, keep, terms["label"].tolist())
    return shares, terms


def reconstruction_by_k(texts: pd.Series, ks=(8, 10, 12), **kw) -> pd.DataFrame:
    """Reconstruction error for each k: a rough guide only (error always falls as k grows)."""
    rows = []
    for k in ks:
        _, _, _, nmf, _ = fit_topics(texts, k=k, **kw)
        rows.append({"k": k, "reconstruction_err": nmf.reconstruction_err_})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 2. change points
def monthly_share(posts: pd.DataFrame, flag: str) -> pd.Series:
    return posts.groupby("month")[flag].mean().sort_index().rename(flag)


def _sse(x: np.ndarray) -> float:
    return float(((x - x.mean()) ** 2).sum()) if len(x) else 0.0


def _best_split(x: np.ndarray, lo: int, hi: int, min_size: int):
    """Best single split of x[lo:hi] by sum of squared errors. Returns (index, gain) or (None, 0)."""
    seg = x[lo:hi]
    base = _sse(seg)
    best_i, best_gain = None, 0.0
    for i in range(lo + min_size, hi - min_size + 1):
        gain = base - _sse(x[lo:i]) - _sse(x[i:hi])
        if gain > best_gain:
            best_i, best_gain = i, gain
    return best_i, best_gain


def binary_segmentation(x, *, n_bkps: int | None = None, min_size: int = 6, pen_factor: float = 3.0) -> list[int]:
    """Binary segmentation of the mean (squared-error cost). Returns sorted break indices (a break at i starts a
    new segment at position i). With n_bkps=None the search stops when the best remaining gain is below
    pen_factor * sigma2 * log(n), where sigma2 is the noise variance estimated from first differences (so a level
    shift does not inflate it). With n_bkps given, exactly that many breaks are returned (if the series allows)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2 * min_size:
        return []
    sigma2 = float(np.var(np.diff(x)) / 2) if n > 2 else 0.0
    threshold = pen_factor * sigma2 * math.log(n)
    bkps: list[int] = []
    segments = [(0, n)]
    while True:
        cand = []
        for lo, hi in segments:
            i, g = _best_split(x, lo, hi, min_size)
            if i is not None:
                cand.append((g, i, lo, hi))
        if not cand:
            break
        g, i, lo, hi = max(cand)
        if n_bkps is None and g <= threshold:
            break
        bkps.append(i)
        segments.remove((lo, hi))
        segments += [(lo, i), (i, hi)]
        if n_bkps is not None and len(bkps) >= n_bkps:
            break
    return sorted(bkps)


def describe_breaks(series: pd.Series, bkps: list[int]) -> pd.DataFrame:
    """One row per segment: start month, end month, mean share, number of months."""
    edges = [0, *bkps, len(series)]
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        seg = series.iloc[a:b]
        rows.append({"start": seg.index[0].strftime("%Y-%m"), "end": seg.index[-1].strftime("%Y-%m"),
                     "months": len(seg), "mean_share": float(seg.mean())})
    return pd.DataFrame(rows)


def break_months(series: pd.Series, bkps: list[int]) -> list[str]:
    return [series.index[i].strftime("%Y-%m") for i in bkps]


# ------------------------------------------------------------------ 3. junior and AI
def two_proportion(a_hits: int, a_n: int, b_hits: int, b_n: int) -> dict:
    """Difference b - a in percentage points with a normal-approximation 95% interval (posts treated as independent,
    which they are not exactly: months cluster, so the interval is optimistic)."""
    if a_n == 0 or b_n == 0:
        nan = float("nan")
        return {"before_share": nan, "after_share": nan, "diff_pp": nan, "ci_low_pp": nan, "ci_high_pp": nan,
                "n_before": a_n, "n_after": b_n}
    pa, pb = a_hits / a_n, b_hits / b_n
    se = math.sqrt(pa * (1 - pa) / a_n + pb * (1 - pb) / b_n)
    d = pb - pa
    return {"before_share": pa, "after_share": pb, "diff_pp": d * 100, "ci_low_pp": (d - 1.96 * se) * 100,
            "ci_high_pp": (d + 1.96 * se) * 100, "n_before": a_n, "n_after": b_n}


def before_after(posts: pd.DataFrame, flag: str, cutoff_thread: pd.Timestamp = LAST_PRE_AI_THREAD) -> dict:
    pre, post = posts[posts["month"] <= cutoff_thread], posts[posts["month"] > cutoff_thread]
    return two_proportion(int(pre[flag].sum()), len(pre), int(post[flag].sum()), len(post))


def pretrend_gap(series: pd.Series, cutoff_thread: pd.Timestamp = LAST_PRE_AI_THREAD, fit_from: str | None = None) -> dict:
    """Extrapolate the linear trend of the months up to the cutoff and compare it with what happened after.
    A small gap means the post-cutoff level is what the earlier trend already implied: no evidence of a change."""
    pre = series[series.index <= cutoff_thread]
    if fit_from:
        pre = pre[pre.index >= pd.Timestamp(fit_from)]
    post = series[series.index > cutoff_thread]
    if len(pre) < 6 or len(post) == 0:
        return {"slope_pp_per_year": float("nan"), "mean_gap_pp": float("nan")}
    t = np.asarray((pre.index.year - 2000) * 12 + pre.index.month, dtype=float)
    slope, icpt = np.polyfit(t, pre.to_numpy(dtype=float), 1)
    tp = np.asarray((post.index.year - 2000) * 12 + post.index.month, dtype=float)
    pred = icpt + slope * tp
    return {"slope_pp_per_year": float(slope * 12 * 100), "mean_gap_pp": float((post.to_numpy() - pred).mean() * 100)}


def ai_summary(posts: pd.DataFrame) -> pd.DataFrame:
    """AI/ML mentions around ChatGPT, with the same table for the junior flag as a pre-trend comparison."""
    rows = []
    for flag in ("ai_ml", "junior"):
        r = before_after(posts, flag)
        r.update(pretrend_gap(monthly_share(posts, flag)))
        r["flag"] = flag
        rows.append(r)
    return pd.DataFrame(rows).set_index("flag")


# ------------------------------------------------------------------ 4. validation of the keyword flags
NEGATED_REMOTE = re.compile(
    r"\b(no|not|non|without|isn'?t|aren'?t|cannot|can'?t|unable to)[\s,:\-]{1,3}(\w+\s+){0,2}remote\b"
    r"|\bremote\b[\s,:\-]{0,3}(is\s+)?(not|no)\b|\bremote\s*[:\-]?\s*(no|not available|n/a)\b", re.I)
NEGATED_JUNIOR = re.compile(
    r"\b(no|not|non|without|nor)[\s,:\-]{1,3}(\w+\s+){0,2}(juniors?|interns?|internships?|entry[- ]level|new grads?|graduates?)\b",
    re.I)


# ------------------------------------------------------------------ 4b. junior_v2: a second, transparent junior rule (Milestone 2, D1)
# The old `junior` flag (collectors/hn.py) stays as it is because other code reads it. junior_v2 is computed from the text:
# a post counts when at least one entry-level phrase survives two checks on the ~60 characters before it:
#   * negation   ("no juniors", "not hiring interns or new grads", "can't do internships")
#   * mentoring  ("you will mentor junior engineers": a senior role that talks ABOUT juniors)
# Phrases found by reading the real posts (2026-11-10): junior / jr., intern(ship), entry-level, new or recent grad(uate)s,
# early career, "graduate" only as a role (graduate engineer/developer/programme/role/scheme), Engineer I, 0-2 years,
# bootcamp grads, apprentice(ship), trainee, starting (your) career, no experience required.
# Left out on purpose: "all levels", "mid-level", "mentorship", "student", "college" alone (they rarely invite juniors), and
# "1+ years" (in the real posts it is mostly a per-technology requirement inside senior ads, e.g. "7+ years C#, 1+ years Go").
# Found while reading: the old hand labels in data/manual/hn_validation_sample.csv mark 81 of 100 posts junior = 1, including
# staff and senior roles, so the "recall about 5 %" of the old flag reflects the labels more than the rule.
JUNIOR_V2_TERMS = re.compile(
    r"\bjuniors?\b|\bjr\b\.?(?=\s*(software|front|back|full|web|dev|eng|data|ios|android|python|java|ruby|php|\w+ (developer|engineer)))"
    r"|\binterns?\b|\binternships?\b|\bentry[- ]level\b"
    r"|\b(new|recent|fresh|college|university|bootcamp|boot camp|coding school)[- ](college |university )?grad(uate)?s?\b"
    r"|\bgrad(uate)?s? (from (a )?)?(boot ?camps?|coding (schools?|bootcamps?))"
    r"|\bgraduate ([a-z+#.]+ ){0,2}(engineers?|developers?|programmers?|programmes?|programs?|roles?|positions?|schemes?|placements?|hires?|jobs?)\b"
    r"|\bgraduating (in )?(19|20)\d\d\b"
    r"|\bearly[- ]career\b|\bapprentice(ship)?s?\b|\btrainees?\b"
    r"|\b(engineer|developer|programmer|analyst|scientist)[ \t]+(?-i:I)(?=[ \t]*([|,)(\-–/&]|$|\b(and|or|position|role)\b))(?![ \t]*[/\-][ \t]*(?-i:I))"
    r"|\b0\s*(-|to|–)\s*[1-3]\+?\s*(years?|yrs)\b|\b0\+\s*(years?|yrs)\b"
    r"|\bstart(ing)? (your|their|a) (tech |software |engineering |professional )?career\b"
    r"|\bno (prior |previous |professional )?experience (is )?(required|necessary|needed)\b",
    re.I)
JUNIOR_V2_NEGATION = re.compile(
    r"\b(no|not|non|nor|without|never|isn'?t|aren'?t|cannot|can'?t|don'?t|doesn'?t|won'?t|unable to|unfortunately|sorry)\b[^.!?\n]{0,45}$"
    r"|\b(not|no)\s+(hiring|looking|accepting|considering|taking|offering|open to|able to (hire|take|consider|accept))\b[^.!?\n]{0,40}$",
    re.I)
JUNIOR_V2_MENTOR = re.compile(
    r"\b(mentor(s|ing)?|coach(es|ing)?|guid(e|es|ing)|lead(s|ing)?|manag(e|es|ing)|support(s|ing)?|grow(s|ing)?|train(s|ing)?|"
    r"teach(es|ing)?|oversee(s|ing)?|supervis(e|es|ing))[ \t]+([\w-]+[ \t]+){0,3}$",
    re.I)
_JUNIOR_V2_WINDOW = 60


def junior_v2_matches(text: str) -> list[str]:
    """The entry-level phrases in `text` that are neither negated nor about mentoring juniors (empty list = not junior)."""
    t = str(text or "")
    keep = []
    for m in JUNIOR_V2_TERMS.finditer(t):
        before = t[max(0, m.start() - _JUNIOR_V2_WINDOW):m.start()]
        if JUNIOR_V2_NEGATION.search(before) or JUNIOR_V2_MENTOR.search(before):
            continue
        keep.append(m.group(0))
    return keep


def junior_v2(text: str) -> int:
    """1 if the post invites entry-level, intern or new-graduate applicants by the rule above, else 0."""
    return int(bool(junior_v2_matches(text)))


def add_junior_v2(df: pd.DataFrame) -> pd.DataFrame:
    """Copy of df (needs a `text` column) with a `junior_v2` column."""
    out = df.copy()
    out["junior_v2"] = out["text"].fillna("").map(junior_v2).astype(int)
    return out


# Any seniority word at all: used only to oversample the fresh validation sample, so that it contains enough true juniors.
SENIORITY_ANY = re.compile(
    r"\b(junior|jr|intern|internships?|entry[- ]level|grads?|graduates?|early[- ]career|apprentice|trainee|bootcamp|college|"
    r"students?|all levels|any level|mid[- ]level|engineer i|years? of experience|mentor(ship|ing)?)\b", re.I)


def make_stratified_sample(df: pd.DataFrame, n: int = 240, share_seniority: float = 0.5, seed: int = 20261110) -> pd.DataFrame:
    """Fresh validation sample for junior_v2 (a NEW seed, so it is not the sample the rule was designed on).
    Half the posts (share_seniority) come from posts that mention any seniority word (stratum 'seniority'), the rest are a
    simple random draw from the other posts (stratum 'other'). `weight` = posts in the stratum / posts drawn, so that population
    precision and recall can be estimated (`validate_weighted`). No flag values are shown, so the labeller is blind to the rule."""
    has = df["text"].fillna("").map(lambda t: bool(SENIORITY_ANY.search(t)))
    a, b = df[has], df[~has]
    na = min(len(a), int(round(n * share_seniority)))
    nb = min(len(b), n - na)
    parts = []
    for name, pool, k in (("seniority", a, na), ("other", b, nb)):
        s = pool.sample(n=k, random_state=seed)[["post_id", "thread_month", "text"]].copy()
        s["stratum"], s["weight"] = name, len(pool) / k if k else float("nan")
        parts.append(s)
    out = pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)
    out["label_junior"] = ""
    return out


def validate_weighted(labelled: pd.DataFrame, pred_col: str = "junior_v2", label_col: str = "label_junior") -> dict:
    """Precision and recall with the stratum weights of make_stratified_sample (point estimates; the Wilson intervals of
    validate_flags are unweighted). Rows without a 0/1 label are ignored."""
    g = labelled[pd.to_numeric(labelled[label_col], errors="coerce").isin([0, 1])]
    y, yhat, w = pd.to_numeric(g[label_col]).astype(int), g[pred_col].astype(int), g["weight"].astype(float)
    tp, fp, fn = float(w[(y == 1) & (yhat == 1)].sum()), float(w[(y == 0) & (yhat == 1)].sum()), float(w[(y == 1) & (yhat == 0)].sum())
    return {"precision_w": tp / (tp + fp) if tp + fp else float("nan"), "recall_w": tp / (tp + fn) if tp + fn else float("nan"),
            "prevalence_w": float(w[y == 1].sum() / w.sum()) if w.sum() else float("nan")}


# Decision rule for using junior_v2 in a figure, written down 2026-11-10 BEFORE any junior_v2 trend was looked at (brief D1.4).
JUNIOR_V2_RULE = {"min_precision": 0.8, "min_recall": 0.5, "min_recall_ci_low": 0.35}


def junior_v2_decision(row: pd.Series | dict) -> bool:
    """True if a validate_flags row for junior_v2 passes JUNIOR_V2_RULE."""
    r = dict(row)
    lo = r["recall_ci"][0] if isinstance(r.get("recall_ci"), (tuple, list)) else float("nan")
    return bool(r["precision"] >= JUNIOR_V2_RULE["min_precision"] and r["recall"] >= JUNIOR_V2_RULE["min_recall"]
                and lo >= JUNIOR_V2_RULE["min_recall_ci_low"])


def negation_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    """How many flagged posts contain an obvious negation next to the keyword? Needs no hand labels.
    A lower bound on false positives: negations phrased in other ways are not caught."""
    rows = []
    for flag, rx in (("remote", NEGATED_REMOTE), ("junior", NEGATED_JUNIOR)):
        sub = df[df[flag] == 1]
        neg = sub["text"].fillna("").map(lambda t: bool(rx.search(t))).astype(bool)
        rows.append({"flag": flag, "flagged_posts": len(sub), "with_obvious_negation": int(neg.sum()),
                     "share_pct": float(neg.mean() * 100) if len(sub) else float("nan")})
    return pd.DataFrame(rows).set_index("flag")


def make_validation_sample(df: pd.DataFrame, n: int = 100, seed: int = SEED) -> pd.DataFrame:
    """Simple random sample of posts to label by hand. Label columns start empty.
    Labelling guide: label_remote = 1 if the post offers remote work (fully or partly) for the advertised job,
    0 if it is on-site only or says remote is NOT possible. label_junior = 1 if the post invites entry-level,
    intern or new-graduate applicants, 0 if it only mentions such words in another sense or excludes them."""
    s = df.sample(n=min(n, len(df)), random_state=seed)[["post_id", "thread_month", "text"]].copy()
    s["label_remote"], s["label_junior"] = "", ""
    return s.reset_index(drop=True)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def validate_flags(labelled: pd.DataFrame, posts: pd.DataFrame, flags=("remote", "junior")) -> pd.DataFrame:
    """Precision and recall of the keyword flags against the hand labels (rows with a label only).
    Precision = of posts the rule flagged, the share truly positive. Recall = of truly positive posts, the share flagged."""
    lab = labelled.copy()
    lab["post_id"] = lab["post_id"].astype(str)
    m = lab.merge(posts[["post_id", *flags]], on="post_id", how="left")
    rows = []
    for f in flags:
        col = f"label_{f}"
        g = m[pd.to_numeric(m[col], errors="coerce").isin([0, 1])]
        y, yhat = pd.to_numeric(g[col]).astype(int), g[f].astype(int)
        tp, fp, fn, tn = int(((y == 1) & (yhat == 1)).sum()), int(((y == 0) & (yhat == 1)).sum()), \
            int(((y == 1) & (yhat == 0)).sum()), int(((y == 0) & (yhat == 0)).sum())
        pl, ph = wilson(tp, tp + fp)
        rl, rh = wilson(tp, tp + fn)
        rows.append({"flag": f, "labelled": len(g), "true_pos": tp, "false_pos": fp, "false_neg": fn, "true_neg": tn,
                     "precision": tp / (tp + fp) if tp + fp else float("nan"), "precision_ci": (round(pl, 3), round(ph, 3)),
                     "recall": tp / (tp + fn) if tp + fn else float("nan"), "recall_ci": (round(rl, 3), round(rh, 3)),
                     "warning": "fewer than 20 true positives: recall interval is wide" if tp + fn < 20 else ""})
    return pd.DataFrame(rows).set_index("flag")


# ------------------------------------------------------------------ aggregates for the milestone figures (no raw text)
MILESTONE_FLAGS = ("remote", "ai_ml")      # 'junior' left out on purpose: hand validation put its recall near 5 %


def flags_monthly(posts: pd.DataFrame, flags=MILESTONE_FLAGS) -> pd.DataFrame:
    """Long table month (YYYY-MM), flag, share (0-1), n_posts. Aggregates only, safe to commit."""
    n = posts.groupby("month").size().sort_index()
    rows = []
    for f in flags:
        s = monthly_share(posts, f)
        rows.append(pd.DataFrame({"month": s.index.strftime("%Y-%m"), "flag": f, "share": s.to_numpy(dtype=float),
                                  "n_posts": n.reindex(s.index).to_numpy(dtype=int)}))
    return pd.concat(rows, ignore_index=True)


def change_points_table(posts: pd.DataFrame, flags=MILESTONE_FLAGS, n_bkps: int | None = 3) -> pd.DataFrame:
    """Segments of the monthly share between level shifts (the same call as notebook 05: n_bkps=3).
    Columns flag, start, end (YYYY-MM), months, mean_share."""
    out = []
    for f in flags:
        s = monthly_share(posts, f)
        seg = describe_breaks(s, binary_segmentation(s.to_numpy(), n_bkps=n_bkps))
        seg.insert(0, "flag", f)
        out.append(seg)
    return pd.concat(out, ignore_index=True)[["flag", "start", "end", "months", "mean_share"]]


def write_flag_aggregates(posts: pd.DataFrame | None = None, outdir: Path | None = None,
                          with_junior_v2: bool = False) -> tuple[Path, Path]:
    """Writes hn_flags_monthly.csv and hn_change_points.csv from the local posts file (flags only, no text).
    with_junior_v2=True also adds the junior_v2 share (computed from the local text file; only if it passed JUNIOR_V2_RULE)."""
    flags = MILESTONE_FLAGS
    if posts is None:
        posts = load_posts()
        if with_junior_v2:
            posts = add_junior_v2(posts.merge(load_text(), on="post_id", how="left")).drop(columns="text")
    if with_junior_v2:
        flags = (*MILESTONE_FLAGS, "junior_v2")
    outdir = Path(outdir or PROCESSED)
    outdir.mkdir(parents=True, exist_ok=True)
    p1, p2 = outdir / "hn_flags_monthly.csv", outdir / "hn_change_points.csv"
    flags_monthly(posts, flags).to_csv(p1, index=False)
    change_points_table(posts, flags).to_csv(p2, index=False)
    return p1, p2


V2_SAMPLE = "hn_validation_sample_junior_v2.csv"


def validate_junior_v2(labelled: pd.DataFrame) -> tuple[pd.DataFrame, dict, bool]:
    """(validate_flags table for junior and junior_v2, weighted point estimates, decision) from a labelled V2_SAMPLE.
    Both rules are recomputed from the text in the file, so no other file is needed."""
    lab = labelled.copy()
    lab["post_id"] = lab["post_id"].astype(str)
    from collectors.hn import features
    pred = add_junior_v2(lab[["post_id", "text"]])
    pred["junior"] = lab["text"].map(lambda t: features(str(t))["junior"])
    lab["label_junior_v2"] = lab["label_junior"]
    table = validate_flags(lab, pred, flags=("junior", "junior_v2"))
    weighted = validate_weighted(lab.assign(junior_v2=pred["junior_v2"].to_numpy()))
    return table, weighted, junior_v2_decision(table.loc["junior_v2"])


# ------------------------------------------------------------------ command line
def run(k: int = 10, out: Path | None = None) -> pd.DataFrame:
    df = load_joined()
    shares, terms = topic_model_monthly(df, k=k)
    out = out or PROCESSED / "hn_topics_monthly.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    shares.to_csv(out, index=False)
    print(terms.to_string(index=False))
    for flag in ("remote", "ai_ml"):
        s = monthly_share(df, flag)
        print(f"\n{flag}: breaks at", break_months(s, binary_segmentation(s.to_numpy())))
    print("\n", ai_summary(df).round(3).to_string())
    print(f"\nTopic shares -> {out}")
    return shares


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "sample", "validate", "flags", "sample2", "validate2"])
    ap.add_argument("-k", type=int, default=10)
    ap.add_argument("-n", type=int, default=100)
    ap.add_argument("--with-junior-v2", action="store_true", help="flags: add junior_v2 (only after it passed validate2)")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.k)
    elif a.cmd == "flags":
        for p in write_flag_aggregates(with_junior_v2=a.with_junior_v2):
            print(f"wrote {p}")
    elif a.cmd == "sample2":
        path = MANUAL / V2_SAMPLE
        MANUAL.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SystemExit(f"{path} exists already (it may hold your labels). Move it first if you want a new sample.")
        make_stratified_sample(load_joined(), max(a.n, 200)).to_csv(path, index=False)
        print(f"Wrote {path}. Fill label_junior with 1/0 (guide: make_validation_sample), then: python -m analysis.hn_text validate2")
    elif a.cmd == "validate2":
        lab = pd.read_csv(MANUAL / V2_SAMPLE, dtype={"post_id": str}, keep_default_na=False)
        table, weighted, ok = validate_junior_v2(lab)
        print(table.to_string())
        print("weighted by stratum:", {k: round(v, 3) for k, v in weighted.items()})
        print(f"decision rule {JUNIOR_V2_RULE}: {'PASS, junior_v2 may be used in a figure' if ok else 'FAIL, junior hiring cannot be compared'}")
    elif a.cmd == "sample":
        path = MANUAL / "hn_validation_sample.csv"
        MANUAL.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SystemExit(f"{path} exists already (it may hold your labels). Move it first if you want a new sample.")
        make_validation_sample(load_joined(), a.n).to_csv(path, index=False)
        print(f"Wrote {path}. Fill label_remote and label_junior with 1/0, then run: python -m analysis.hn_text validate")
    else:
        lab = pd.read_csv(MANUAL / "hn_validation_sample.csv", dtype={"post_id": str}, keep_default_na=False)
        print(validate_flags(lab, load_posts()).to_string())


if __name__ == "__main__":
    main()
