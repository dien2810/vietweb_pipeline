"""Stage 8: mask personal information with regular expressions.

The patterns are simple; measure the false-positive rate on a labeled sample
(for example, a 12-digit sequence may be an order number rather than a citizen ID).
"""
from __future__ import annotations

import re
from functools import partial

import pandas as pd

from ..parallel import pmap_series
from .base import StageResult

PATTERNS = {
    "email": (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "<EMAIL>"),
    "ipv4": (re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "<IP>"),
    # Vietnamese mobile numbers: 0, 84 or +84, then a 3/5/7/8/9 prefix and 8 digits; spaces, dots, dashes allowed
    "phone_vn": (re.compile(r"(?<!\d)(?:\+?84|0)[\s.-]?[35789](?:[\s.-]?\d){8}(?!\d)"), "<PHONE>"),
    # Vietnamese citizen ID (CCCD): 12 consecutive digits
    "cccd": (re.compile(r"(?<!\d)\d{12}(?!\d)"), "<ID>"),
}


def mask(text: str, enabled: dict) -> tuple[str, dict]:
    counts = {}
    for name, (pat, repl) in PATTERNS.items():
        if enabled.get(name, True):
            text, n = pat.subn(repl, text)
            counts[name] = n
    return text, counts


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    enabled = cfg.get("pii", {})
    out = pmap_series(partial(mask, enabled=enabled), df["text"], cfg)
    new_text = out.map(lambda x: x[0])
    counts = pd.DataFrame(list(out.map(lambda x: x[1])), index=df.index).fillna(0).astype(int)
    extra = {f"pii_{c}": counts[c] for c in counts.columns}
    return StageResult(text=new_text, extra=extra, stats={f"masked_{c}": int(counts[c].sum()) for c in counts.columns})
