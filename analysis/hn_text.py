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
    ap.add_argument("cmd", choices=["run", "sample", "validate"])
    ap.add_argument("-k", type=int, default=10)
    ap.add_argument("-n", type=int, default=100)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.k)
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
