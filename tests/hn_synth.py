"""Synthetic Hacker News data for tests and smoke runs: planted topics, a remote step at 2020-04 and an AI rise
after 2022-12. NOT real data; never use its numbers as results."""
import numpy as np
import pandas as pd

from collectors import hn

TOPICS = {
    "web": "react javascript frontend css typescript webpack ui components",
    "data": "python pandas spark sql airflow warehouse pipelines analytics",
    "ml": "machine learning pytorch model training inference vision research",
    "devops": "kubernetes docker terraform aws infrastructure deployment monitoring",
    "mobile": "ios android swift kotlin mobile app store",
    "security": "security encryption pentest vulnerability compliance threat",
}


def make_hn(posts_per_month: int = 60, seed: int = 0, start="2015-04", end="2026-06"):
    rng = np.random.default_rng(seed)
    months = pd.period_range(start, end, freq="M").to_timestamp()
    names = list(TOPICS)
    rows, texts, pid = [], [], 0
    for m in months:
        p_remote = 0.3 if m < pd.Timestamp("2020-04-01") else 0.8
        p_ai = 0.1 if m <= pd.Timestamp("2022-11-01") else min(0.6, 0.1 + 0.02 * ((m.year - 2022) * 12 + m.month - 11))
        p_jr = max(0.03, 0.10 - 0.005 * (m.year - 2015))
        for _ in range(posts_per_month):
            pid += 1
            topic = names[rng.integers(len(names))]
            words = rng.choice(TOPICS[topic].split(), size=8).tolist()
            parts = [f"Company{pid % 500} | {'SF' if rng.random() < .5 else 'Berlin'} | " + ("REMOTE" if rng.random() < p_remote else "Onsite")]
            if rng.random() < p_ai:
                parts.append("We use AI and LLMs.")
            if rng.random() < p_jr:
                parts.append("Junior and intern candidates welcome.")
            parts.append("We build " + " ".join(words))
            text = "\n".join(parts)
            rows.append({"thread_id": str(m.year * 100 + m.month), "thread_month": m.date().isoformat(),
                         "post_id": str(pid), "created_at": "", **hn.features(text)})
            texts.append({"post_id": str(pid), "text": text})
    return pd.DataFrame(rows), pd.DataFrame(texts)
