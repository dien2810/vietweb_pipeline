"""Stage 3: text normalization, and conversion of text in the legacy TCVN3 / VNI encodings.

legacy_encoding_action (configs/pipeline.yaml):
- flag:    only store legacy_score (the marker-character share) for each document
- convert: decode TCVN3 / VNI text to Unicode when the decoded text reads as Vietnamese (text/legacy.py)
- drop:    remove documents whose legacy_score is at least legacy_encoding_threshold
"""
from __future__ import annotations

from functools import partial

import pandas as pd

from ..config import load_wordlist, resolve
from ..parallel import pmap_series
from ..text.legacy import convert_legacy
from ..text.normalize import legacy_encoding_score, normalize_text, normalize_tone_marks
from .base import StageResult


def normalize_doc(text: str, fix_mojibake: bool, form: str, tone_style: str,
                  stopwords: frozenset | None) -> tuple[str, str | None]:
    """Normalize one document; with stop words given, also convert TCVN3 / VNI text. Returns (text, encoding)."""
    if stopwords is None:
        return normalize_text(text, fix_mojibake=fix_mojibake, form=form, tone_style=tone_style), None
    # Tone marks are moved only after the conversion: on legacy text the mark rule would rewrite byte pairs
    # such as "oá" (VNI for "ố") as if they were Vietnamese rhymes
    text = normalize_text(text, fix_mojibake=fix_mojibake, form=form, tone_style="none")
    converted, enc = convert_legacy(text, stopwords)
    if enc is None:
        return normalize_tone_marks(text, tone_style), None
    return normalize_text(converted, fix_mojibake=False, form=form, tone_style=tone_style), enc


def _normalize_and_score(text: str, **kw) -> tuple[str, str | None, float]:
    """normalize_doc plus the legacy-encoding score of the result, so that both run in the worker process."""
    out, enc = normalize_doc(text, **kw)
    return out, enc, legacy_encoding_score(out)


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    c = cfg["normalize"]
    action = c.get("legacy_encoding_action", "flag")
    stop = None
    if action == "convert":
        stop = frozenset(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
    func = partial(_normalize_and_score, fix_mojibake=c.get("fix_mojibake", True), form=c.get("unicode_form", "NFC"),
                   tone_style=c.get("tone_mark_style", "old"), stopwords=stop)
    out = pmap_series(func, df["text"], cfg)
    new_text = out.map(lambda x: x[0])
    encoding = out.map(lambda x: x[1])
    changed = (new_text != df["text"])
    legacy = out.map(lambda x: x[2]).astype(float)
    flagged = legacy >= c.get("legacy_encoding_threshold", 0.02)

    drop = None
    if action == "drop":
        drop = pd.Series([None] * len(df), index=df.index, dtype=object)
        drop[flagged] = "legacy_encoding"

    stats = {"modified_docs": int(changed.sum()), "legacy_flagged": int(flagged.sum())}
    extra = {"legacy_score": legacy.round(4)}
    if action == "convert":
        stats.update({"legacy_converted_tcvn3": int((encoding == "tcvn3").sum()),
                      "legacy_converted_vni": int((encoding == "vni").sum())})
        extra["legacy_encoding"] = encoding
    return StageResult(text=new_text, drop_reason=drop, extra=extra, stats=stats)
