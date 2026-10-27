"""Counting units for the quality rules and shingles for deduplication.

Three units (RQ1):
- syllable: split on whitespace; in Vietnamese each token is one syllable.
- word: word segmentation with underthesea (compound words joined with '_'); needs `pip install underthesea`.
- char: character n-grams over the whitespace-collapsed text.
"""
from __future__ import annotations

import re
from functools import lru_cache

_TOKEN = re.compile(r"\w+", re.UNICODE)


def syllables(text: str, lower: bool = True) -> list[str]:
    toks = _TOKEN.findall(text)
    return [t.lower() for t in toks] if lower else toks


@lru_cache(maxsize=1)
def _word_tokenizer():
    try:
        from underthesea import word_tokenize
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ImportError("The 'word' unit requires underthesea: pip install underthesea") from e
    return word_tokenize


def words(text: str, lower: bool = True) -> list[str]:
    """Vietnamese word segmentation. Much slower than syllable splitting; measure the cost when comparing (RQ1)."""
    tok = _word_tokenizer()
    out = []
    for line in text.split("\n"):
        if line.strip():
            out += [w.replace(" ", "_") for w in tok(line) if _TOKEN.search(w)]
    return [w.lower() for w in out] if lower else out


def tokens(text: str, unit: str = "syllable") -> list[str]:
    if unit == "syllable":
        return syllables(text)
    if unit == "word":
        return words(text)
    raise ValueError(f"Invalid unit: {unit}")


def shingles(text: str, unit: str = "syllable", n: int = 5) -> set[str]:
    """Set of shingles used for MinHash."""
    if unit == "char":
        s = " ".join(text.lower().split())
        return {s[i:i + n] for i in range(max(len(s) - n + 1, 1))}
    toks = tokens(text, unit)
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}
