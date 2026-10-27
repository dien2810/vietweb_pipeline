"""Sample documents for manual annotation and compute precision and Cohen's kappa.

Workflow (weeks 11-12):
1. `vietweb sample-labels --per-reason 150` -> outputs/eval/labels_to_annotate.csv
2. Two annotators open the CSV (Excel / Google Sheets) and fill label_a / label_b:
   1 = low quality (removal is correct), 0 = acceptable (removal is wrong).
   Each annotator works independently without looking at the other column.
3. `vietweb score-labels outputs/eval/labels_to_annotate.csv` -> precision per removal reason and kappa.
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
    sample = sample.sample(frac=1, random_state=seed)  # shuffle so annotators cannot infer the reason from the order
    out = pd.DataFrame({
        "doc_id": sample["doc_id"],
        "url": sample["url"],
        "drop_stage": sample["drop_stage"],
        "drop_reason": sample["drop_reason"],
        "text_excerpt": sample["text"].str.slice(0, max_chars).str.replace("\n", " ⏎ ", regex=False),
        "label_a": "",
        "label_b": "",
        "note": "",
    })
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")  # utf-8-sig so Excel displays Vietnamese correctly
    return out


def cohen_kappa(a: list[int], b: list[int]) -> float:
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
        a = pd.to_numeric(g["label_a"], errors="coerce")
        b = pd.to_numeric(g["label_b"], errors="coerce")
        both = a.notna() & b.notna()
        lab = a.where(a.notna(), b)  # prefer annotator A; fall back to B when A is missing
        lab = lab.dropna()
        rows.append({
            "drop_reason": reason,
            "labeled": int(len(lab)),
            # KEPT: share of low-quality documents that slipped through; removal reasons: precision of the removal
            "share_low_quality": round(float(lab.mean()), 4) if len(lab) else None,
            "double_labeled": int(both.sum()),
            "kappa": round(cohen_kappa(a[both].astype(int).tolist(), b[both].astype(int).tolist()), 4)
            if both.sum() >= 10 else None,
        })
    a = pd.to_numeric(df["label_a"], errors="coerce")
    b = pd.to_numeric(df["label_b"], errors="coerce")
    both = a.notna() & b.notna()
    rows.append({"drop_reason": "ALL", "labeled": int((a.notna() | b.notna()).sum()),
                 "share_low_quality": None, "double_labeled": int(both.sum()),
                 "kappa": round(cohen_kappa(a[both].astype(int).tolist(), b[both].astype(int).tolist()), 4)
                 if both.sum() else None})
    return pd.DataFrame(rows)
