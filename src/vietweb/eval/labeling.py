"""Random sample of kept and removed documents for manual labelling, and Cohen's kappa.

1. `vietweb sample-labels --per-reason 150` -> outputs/eval/labels_to_annotate.csv (contains page text: not
   tracked by Git).
2. Open the CSV (Excel / Google Sheets) and fill the `label` column:
   1 = low quality (removal is correct), 0 = acceptable (removal is wrong).
3. `vietweb score-labels outputs/eval/labels_to_annotate.csv` -> share of poor pages per removal reason.

This samples at random within each removal reason. The threshold calibration in LUAT_LOC.md (section 7.4)
samples pages near the thresholds instead, with scripts/calibration_sample.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def sample_for_labeling(processed_dir: Path, out_csv: Path, per_reason: int = 150, seed: int = 42,
                        n_kept: int = 150, max_chars: int = 1500) -> pd.DataFrame:
    dropped = pd.concat([pd.read_parquet(p) for p in sorted((processed_dir / "dropped").glob("*.parquet"))],
                        ignore_index=True)
    kept = pd.concat([pd.read_parquet(p) for p in sorted((processed_dir / "kept").glob("*.parquet"))],
                     ignore_index=True)
    parts = []
    for reason, g in dropped.groupby("drop_reason"):
        parts.append(g.sample(n=min(per_reason, len(g)), random_state=seed))
    kept_s = kept.sample(n=min(n_kept, len(kept)), random_state=seed).assign(drop_reason="KEPT", drop_stage="")
    sample = pd.concat(parts + [kept_s], ignore_index=True)
    sample = sample.sample(frac=1, random_state=seed)  # shuffle so the reason cannot be guessed from the order
    out = pd.DataFrame({
        "doc_id": sample["doc_id"],
        "url": sample["url"],
        "drop_stage": sample["drop_stage"],
        "drop_reason": sample["drop_reason"],
        "text_excerpt": sample["text"].str.slice(0, max_chars).str.replace("\n", " ⏎ ", regex=False),
        "label": "",
        "note": "",
    })
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")  # utf-8-sig so Excel displays Vietnamese correctly
    return out


def cohen_kappa(a: list[int], b: list[int]) -> float:
    """Cohen's kappa between two binary decisions (used for the keep/drop agreement with FineWeb-2)."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def score_labels(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    rows = []
    for reason, g in df.groupby("drop_reason"):
        lab = pd.to_numeric(g["label"], errors="coerce").dropna()
        rows.append({
            "drop_reason": reason,
            "labeled": int(len(lab)),
            # KEPT: share of low-quality documents that slipped through; removal reasons: precision of the removal
            "share_low_quality": round(float(lab.mean()), 4) if len(lab) else None,
        })
    lab = pd.to_numeric(df["label"], errors="coerce")
    rows.append({"drop_reason": "ALL", "labeled": int(lab.notna().sum()), "share_low_quality": None})
    return pd.DataFrame(rows)
