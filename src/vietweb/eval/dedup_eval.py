"""Evaluate MinHash-LSH against exact Jaccard similarity on a subset (RQ1, Table 6).

Exact Jaccard over all pairs is O(n^2): use a subset of a few thousand to 10,000 documents.
"""
from __future__ import annotations

import time
from itertools import combinations

import pandas as pd
from datasketch import MinHashLSH

from ..stages.s06_dedup import MinHasher
from ..text.tokenize import shingles


def exact_pairs(sets: list[set[str]], threshold: float) -> set[tuple[int, int]]:
    pairs = set()
    for i, j in combinations(range(len(sets)), 2):
        a, b = sets[i], sets[j]
        if a and b and len(a & b) / len(a | b) >= threshold:
            pairs.add((i, j))
    return pairs


def lsh_pairs(sets: list[set[str]], num_perm: int = 112, bands: int = 14, rows: int = 8) -> set[tuple[int, int]]:
    mh = MinHasher(num_perm)
    lsh = MinHashLSH(num_perm=num_perm, params=(bands, rows))
    # empty shingle sets all get the same signature and would match each other, so they are left out
    sigs = {i: mh(s) for i, s in enumerate(sets) if s}
    for i, m in sigs.items():
        lsh.insert(i, m)
    pairs = set()
    for i, m in sigs.items():
        for j in lsh.query(m):
            if j != i:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def compare_units(texts: list[str], units: list[tuple[str, int]], threshold: float = 0.75) -> pd.DataFrame:
    """units: list of (unit, n), e.g. [("syllable", 5), ("word", 5), ("char", 15)]."""
    rows = []
    for unit, n in units:
        t0 = time.perf_counter()
        sets = [shingles(t, unit, n) for t in texts]
        truth = exact_pairs(sets, threshold)
        pred = lsh_pairs(sets)
        tp = len(truth & pred)
        prec = tp / len(pred) if pred else float("nan")
        rec = tp / len(truth) if truth else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if pred and truth and (prec + rec) else float("nan")
        rows.append({"unit": f"{unit}-{n}", "true_pairs": len(truth), "lsh_pairs": len(pred),
                     "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                     "seconds": round(time.perf_counter() - t0, 2)})
    return pd.DataFrame(rows)
