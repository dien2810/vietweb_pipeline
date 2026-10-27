"""Stage 6: exact, near-duplicate (MinHash-LSH), and line-level deduplication.

This version runs in memory, which is enough for the pilot (tens of thousands of documents).
Weeks 8-10: move MinHash-LSH to Spark (see src/vietweb/spark_runner.py) for larger data.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

import pandas as pd
from datasketch import MinHash, MinHashLSH

from ..text.tokenize import shingles
from .base import StageResult


def _norm_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def run_exact(df: pd.DataFrame, cfg: dict) -> StageResult:
    """Keep the first document of each group of identical texts (after lowercasing and collapsing whitespace)."""
    h = df["text"].map(lambda t: hashlib.sha1(_norm_for_hash(t).encode("utf-8")).hexdigest())
    dup = h.duplicated(keep="first")
    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    drop[dup] = "exact_duplicate"
    return StageResult(drop_reason=drop, extra={"text_sha1": h}, stats={"exact_duplicates": int(dup.sum())})


class MinHasher:
    """Build MinHash signatures, reusing one set of permutations instead of regenerating it per document."""

    def __init__(self, num_perm: int, seed: int = 1):
        self.num_perm, self.seed = num_perm, seed
        base = MinHash(num_perm=num_perm, seed=seed)
        self._kw = {"permutations": base.permutations}
        if hasattr(base, "scheme"):  # datasketch >= 2.0 requires the scheme when permutations are reused
            self._kw["scheme"] = base.scheme

    def __call__(self, shingle_set: set[str]) -> MinHash:
        m = MinHash(num_perm=self.num_perm, seed=self.seed, **self._kw)
        m.update_batch([s.encode("utf-8") for s in shingle_set])
        return m


def run_near(df: pd.DataFrame, cfg: dict) -> StageResult:
    """MinHash-LSH with b bands x r rows. A document similar to an already kept document is removed.

    The effective similarity threshold is about (1/b)^(1/r); with b=14 and r=8 it is about 0.72.
    """
    c = cfg["dedup"]["near"]
    num_perm, b, r = c.get("num_perm", 112), c.get("bands", 14), c.get("rows", 8)
    if b * r > num_perm:
        raise ValueError("bands * rows must be <= num_perm")
    lsh = MinHashLSH(num_perm=num_perm, params=(b, r))
    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    cluster = pd.Series([None] * len(df), index=df.index, dtype=object)
    minhash = MinHasher(num_perm)
    for idx, text in df["text"].items():
        m = minhash(shingles(text, c.get("unit", "syllable"), c.get("ngram", 5)))
        hits = lsh.query(m)
        if hits:
            drop[idx] = "near_duplicate"
            cluster[idx] = hits[0]            # representative document of the cluster
        else:
            lsh.insert(str(df.at[idx, "doc_id"]), m)
            cluster[idx] = str(df.at[idx, "doc_id"])
    return StageResult(drop_reason=drop, extra={"near_dup_cluster": cluster},
                       stats={"near_duplicates": int(drop.notna().sum()), "unit": c.get("unit"), "ngram": c.get("ngram")})


def run_line(df: pd.DataFrame, cfg: dict) -> StageResult:
    """Remove repeated boilerplate lines. Both rules look at lines of at least min_line_chars characters.

    - Same domain: the line occurs in >= min_docs_per_domain documents of one domain (menus, footers, ads).
    - Cross-site: the line occurs on >= min_domains different domains (theme and plugin strings such as
      "Chưa có sản phẩm trong giỏ hàng.", comment forms, "Xem thêm"), in the spirit of the paragraph
      deduplication of CCNet (Wenzek et al., 2020). min_domains: 0 turns this rule off. The number of
      domains a line reaches grows with the amount of data, so check the threshold when the sample grows.
    A document left without text is dropped ("empty_after_line_dedup").
    """
    c = cfg["dedup"]["line"]
    k, min_chars = c.get("min_docs_per_domain", 3), c.get("min_line_chars", 10)
    min_domains = c.get("min_domains", 0) or 0

    counts: Counter = Counter()                               # (domain, line) -> number of documents
    for dom, text in zip(df["domain"], df["text"]):
        seen = {ln.strip() for ln in text.split("\n") if len(ln.strip()) >= min_chars}
        counts.update((dom, ln) for ln in seen)
    n_domains: Counter = Counter(ln for _, ln in counts)      # line -> number of distinct domains
    cross = {ln for ln, n in n_domains.items() if n >= min_domains} if min_domains else set()

    removed: Counter = Counter()
    docs_cross = 0

    def strip(dom: str, text: str) -> str:
        nonlocal docs_cross
        keep, hit = [], False
        for ln in text.split("\n"):
            s = ln.strip()
            if len(s) >= min_chars:
                if counts[(dom, s)] >= k:
                    removed["same_domain"] += 1
                    continue
                if s in cross:
                    removed["cross_site"] += 1
                    hit = True
                    continue
            keep.append(ln)
        docs_cross += hit
        return "\n".join(keep).strip()

    new_text = pd.Series([strip(d, t) for d, t in zip(df["domain"], df["text"])], index=df.index)
    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    drop[new_text.str.len() == 0] = "empty_after_line_dedup"
    top = sorted(cross, key=lambda s: (-n_domains[s], s))[:5]
    return StageResult(text=new_text, drop_reason=drop, stats={
        "removed_lines": removed["same_domain"] + removed["cross_site"],
        "removed_lines_same_domain": removed["same_domain"],
        "removed_lines_cross_site": removed["cross_site"],
        "min_domains": min_domains,
        "cross_site_distinct_lines": len(cross),
        "docs_with_cross_site_lines": docs_cross,
        "cross_site_top": [f"{n_domains[s]} domains: {s[:60]}" for s in top]})
