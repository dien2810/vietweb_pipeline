"""Stage 3: text normalization and legacy-encoding detection."""
from __future__ import annotations

import pandas as pd

from ..text.normalize import legacy_encoding_score, normalize_text
from .base import StageResult


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    c = cfg["normalize"]
    new_text = df["text"].map(lambda t: normalize_text(
        t, fix_mojibake=c.get("fix_mojibake", True), form=c.get("unicode_form", "NFC"),
        tone_style=c.get("tone_mark_style", "old")))
    changed = (new_text != df["text"])
    legacy = new_text.map(legacy_encoding_score)
    flagged = legacy >= c.get("legacy_encoding_threshold", 0.02)

    drop = None
    if c.get("legacy_encoding_action", "flag") == "drop":
        drop = pd.Series([None] * len(df), index=df.index, dtype=object)
        drop[flagged] = "legacy_encoding"

    return StageResult(
        text=new_text,
        drop_reason=drop,
        extra={"legacy_score": legacy.round(4)},
        stats={"modified_docs": int(changed.sum()), "legacy_flagged": int(flagged.sum())},
    )
