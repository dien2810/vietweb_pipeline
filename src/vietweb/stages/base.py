from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class StageResult:
    """Result of one stage on the documents that are still kept.

    text:        new text (transformation stages), or None if unchanged.
    drop_reason: removal reason per document (None = keep), or None if the stage removes nothing.
    extra:       additional columns to store (e.g. language score, number of masked PII items).
    stats:       aggregate numbers for the stage (written to the log / funnel).
    """
    text: pd.Series | None = None
    drop_reason: pd.Series | None = None
    extra: dict[str, pd.Series] = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
