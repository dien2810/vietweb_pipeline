"""Output checks before export (plain pandas; the same checks could be written as a Pandera schema)."""
from __future__ import annotations

import pandas as pd

from .stages.s08_pii import PATTERNS


def validate_output(kept: pd.DataFrame) -> list[str]:
    problems = []
    if kept.empty:
        return ["no documents left after filtering"]
    if kept["doc_id"].duplicated().any():
        problems.append("duplicate doc_id")
    empty = (kept["text"].str.strip().str.len() == 0).sum()
    if empty:
        problems.append(f"{empty} empty texts")
    for name in ("email", "phone_vn"):
        pat, _ = PATTERNS[name]
        n = kept["text"].map(lambda t: bool(pat.search(t))).sum()
        if n:
            problems.append(f"{n} documents still contain {name} patterns (is the pii stage disabled or misplaced?)")
    return problems
