"""Stage 3b: remove boilerplate lines (menus, sidebars, footers) from WET text, page by page.

WET files contain all visible text of a page, so navigation menus, category lists, and footers remain.
FineWeb sets its quality thresholds on text extracted from WARC HTML with trafilatura, where this
boilerplate is already gone. This stage removes it from the plain text, without HTML.

Two methods:
- justext (default): the context-sensitive classification of jusText (Pomikalek, 2011), applied to lines
  instead of HTML blocks. Link density is not available in WET text, so a URL-share rule replaces it.
    1. Context-free class of each line:
       bad       contains a bad pattern (copyright notice), or URLs make up most of the line,
                 or stop-word density < stopwords_low (for lines that are not short)
       short     fewer than length_low characters
       neargood  stopwords_low <= density < stopwords_high, or density >= stopwords_high but shorter than length_high
       good      at least length_high characters and density >= stopwords_high
    2. Short lines take the class of their nearest good/bad neighbours (page edges count as bad).
    3. Near-good lines become good unless both nearest good/bad neighbours are bad.
  Only good lines are kept.
- c4_lines: the line rules of C4 (Raffel et al., 2020): keep lines that end with terminal punctuation
  and have at least c4_min_words syllables; drop lines that mention "javascript". With c4_drop_ellipsis,
  lines ending with "..." or "…" are dropped too: on WET pages they are mostly truncated excerpts of other
  articles ("Xem thêm…"), and keeping them made gopher_ellipsis_lines drop whole pages.

A document whose remaining text is shorter than min_chars_after is dropped ("boilerplate_too_short").
"""
from __future__ import annotations

import re

import pandas as pd

from ..config import load_wordlist, resolve
from ..text.tokenize import syllables
from .base import StageResult

C4_TERMINAL = (".", "!", "?", '"', "”", "…")
ELLIPSIS = ("...", "…")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

DEFAULTS = {
    "method": "justext",
    "length_low": 70,
    "length_high": 150,
    "stopwords_low": 0.08,
    "stopwords_high": 0.12,
    "max_url_ratio": 0.3,
    "bad_patterns": ["©", "copyright", "bản quyền", "all rights reserved"],
    "c4_min_words": 5,
    "c4_drop_ellipsis": False,
    "min_chars_after": 200,
}


def _params(cfg_section: dict | None) -> dict:
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (cfg_section or {}).items() if k in DEFAULTS})
    p["bad_patterns"] = [s.lower() for s in p["bad_patterns"]]
    return p


def context_free_class(line: str, p: dict, stopwords: set[str]) -> str:
    low = line.lower()
    if any(pat in low for pat in p["bad_patterns"]):
        return "bad"
    url_chars = sum(len(m) for m in _URL.findall(line))
    if url_chars > p["max_url_ratio"] * len(line):
        return "bad"
    if len(line) < p["length_low"]:
        return "short"
    toks = syllables(line)
    density = sum(t in stopwords for t in toks) / len(toks) if toks else 0.0
    if density >= p["stopwords_high"]:
        return "good" if len(line) >= p["length_high"] else "neargood"
    if density >= p["stopwords_low"]:
        return "neargood"
    return "bad"


def _neighbour(classes: list[str], i: int, step: int, ignore_neargood: bool) -> str:
    """Class of the nearest good/bad (or near-good) line in one direction; page edges count as bad."""
    i += step
    while 0 <= i < len(classes):
        c = classes[i]
        if c in ("good", "bad"):
            return c
        if c == "neargood" and not ignore_neargood:
            return c
        i += step
    return "bad"


def revise_classes(classes: list[str]) -> list[str]:
    """Context-sensitive revision of jusText (short lines first, then near-good lines)."""
    cls = list(classes)
    new = {}
    for i, c in enumerate(cls):
        if c != "short":
            continue
        prev_c = _neighbour(cls, i, -1, ignore_neargood=True)
        next_c = _neighbour(cls, i, 1, ignore_neargood=True)
        pair = {prev_c, next_c}
        if pair == {"good"}:
            new[i] = "good"
        elif pair == {"bad"}:
            new[i] = "bad"
        elif (prev_c == "bad" and _neighbour(cls, i, -1, ignore_neargood=False) == "neargood") or \
             (next_c == "bad" and _neighbour(cls, i, 1, ignore_neargood=False) == "neargood"):
            new[i] = "good"
        else:
            new[i] = "bad"
    for i, c in new.items():
        cls[i] = c

    new = {}
    for i, c in enumerate(cls):
        if c != "neargood":
            continue
        prev_c = _neighbour(cls, i, -1, ignore_neargood=True)
        next_c = _neighbour(cls, i, 1, ignore_neargood=True)
        new[i] = "bad" if (prev_c, next_c) == ("bad", "bad") else "good"
    for i, c in new.items():
        cls[i] = c
    return cls


def keep_mask(lines: list[str], p: dict, stopwords: set[str]) -> list[bool]:
    """True for each line to keep. `lines` are the non-empty, stripped lines of one page."""
    if p["method"] == "c4_lines":
        return [ln.endswith(C4_TERMINAL) and len(syllables(ln)) >= p["c4_min_words"]
                and "javascript" not in ln.lower()
                and not (p["c4_drop_ellipsis"] and ln.endswith(ELLIPSIS)) for ln in lines]
    if p["method"] == "justext":
        classes = revise_classes([context_free_class(ln, p, stopwords) for ln in lines])
        return [c == "good" for c in classes]
    raise ValueError(f"Invalid boilerplate.method: {p['method']}")


def clean_text(text: str, p: dict, stopwords: set[str]) -> str:
    """Remove boilerplate lines from one page. Paragraph breaks between kept lines become single newlines."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return ""
    keep = keep_mask(lines, p, stopwords)
    return "\n".join(ln for ln, k in zip(lines, keep) if k)


def _cld2_primary_vie(df: pd.DataFrame) -> pd.Series:
    if "cld2_langs" not in df.columns:
        return pd.Series(True, index=df.index)
    return df["cld2_langs"].fillna("").str.split(",").str[0].eq("vie")


def load_params_and_stopwords(cfg: dict) -> tuple[dict, set[str]]:
    p = _params(cfg.get("boilerplate"))
    stop = set(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
    return p, stop


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    p, stop = load_params_and_stopwords(cfg)
    new_text = df["text"].map(lambda t: clean_text(t, p, stop))
    old_chars = df["text"].str.len()
    new_chars = new_text.str.len()
    ratio = (new_chars / old_chars.where(old_chars > 0, 1)).round(4)

    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    drop[new_chars < p["min_chars_after"]] = "boilerplate_too_short"
    old_lines = df["text"].map(lambda t: sum(1 for ln in t.split("\n") if ln.strip()))
    new_lines = new_text.map(lambda t: t.count("\n") + 1 if t else 0)
    return StageResult(
        text=new_text,
        drop_reason=drop,
        extra={"bp_chars_ratio": ratio},
        stats={"method": p["method"],
               "removed_lines": int((old_lines - new_lines).sum()),
               "removed_char_share": round(1 - new_chars.sum() / max(old_chars.sum(), 1), 4),
               "too_short": int(drop.notna().sum()),
               # pages whose CLD2 primary language is not Vietnamese lose almost every line here, because the
               # classification relies on Vietnamese stop words; this count separates them from Vietnamese pages
               "too_short_cld2_not_vie": int((drop.notna() & ~_cld2_primary_vie(df)).sum())},
    )
