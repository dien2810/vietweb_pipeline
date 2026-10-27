"""Stage 5: filter by domain blocklist and spam keywords."""
from __future__ import annotations

import pandas as pd

from ..config import load_wordlist, resolve
from .base import StageResult


def _blocked_domain(domain: str, blocked: set[str]) -> bool:
    parts = domain.split(".")
    # subdomains match too: a.b.example.com is blocked if example.com is in the list
    return any(".".join(parts[i:]) in blocked for i in range(len(parts)))


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    c = cfg["url_filter"]
    domains = set(load_wordlist(resolve(cfg, c["domain_blocklist"])))
    keywords = load_wordlist(resolve(cfg, c["keyword_blocklist"]))
    min_hits = c.get("keyword_min_hits", 3)

    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    dom_hit = df["domain"].map(lambda d: _blocked_domain(d, domains))
    drop[dom_hit] = "url_blocklist"

    lower = df["text"].str.lower()
    kw_hits = lower.map(lambda t: sum(t.count(k) for k in keywords))
    drop[(kw_hits >= min_hits) & drop.isna()] = "spam_keywords"
    return StageResult(drop_reason=drop, extra={"spam_kw_hits": kw_hits},
                       stats={"domain_blocked": int(dom_hit.sum()), "keyword_blocked": int((kw_hits >= min_hits).sum())})
