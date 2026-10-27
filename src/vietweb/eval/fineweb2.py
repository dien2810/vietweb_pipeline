"""SKELETON (weeks 11-12): compare keep/drop decisions with FineWeb-2 by URL (RQ3, Table 7).

FineWeb-2 publishes both the kept data (vie_Latn) and the removed data (vie_Latn_removed).
Planned procedure:
1. Pick a crawl snapshot that FineWeb-2 covers (see its `dump` column) and collect it with
   `vietweb collect --crawl ...`.
2. Load a slice of FineWeb-2 for the same dump (streaming, keeping only the url and dump columns):
       from datasets import load_dataset
       ds = load_dataset("HuggingFaceFW/fineweb-2", name="vie_Latn", split="train", streaming=True)
   The _removed subset is downloaded directly from its file paths in the dataset repository (see the dataset card).
3. Join with data/processed (kept + dropped) on URL and compute agreement A and Cohen's kappa.

The functions below work on two input DataFrames; loading the FineWeb-2 data still needs to be written.
"""
from __future__ import annotations

import pandas as pd

from .labeling import cohen_kappa


def agreement(ours: pd.DataFrame, fw2: pd.DataFrame) -> dict:
    """ours: columns url, kept (bool). fw2: columns url, kept (bool). Only URLs present in both are compared."""
    m = ours[["url", "kept"]].merge(fw2[["url", "kept"]], on="url", suffixes=("_ours", "_fw2"))
    if m.empty:
        return {"overlap": 0}
    a = m["kept_ours"].astype(int).tolist()
    b = m["kept_fw2"].astype(int).tolist()
    return {
        "overlap": len(m),
        "agreement": round(sum(x == y for x, y in zip(a, b)) / len(m), 4),
        "kappa": round(cohen_kappa(a, b), 4),
        "fw2_kept_ours_dropped_pct": round(100 * ((m["kept_fw2"]) & (~m["kept_ours"])).mean(), 2),
        "fw2_dropped_ours_kept_pct": round(100 * ((~m["kept_fw2"]) & (m["kept_ours"])).mean(), 2),
    }


def load_fineweb2_urls(dump: str, limit: int = 200_000) -> pd.DataFrame:
    """TODO: load FineWeb-2 URLs (vie_Latn and vie_Latn_removed) for one dump."""
    raise NotImplementedError("To be implemented in weeks 11-12; see the module docstring")
