"""Load the documents that reach stage 7 in a finished run, and the hand labels of threshold calibration."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SHEETS = ["calibration_dev", "calibration_dev_r2", "calibration_test"]


def load_stage7_input(processed: Path) -> pd.DataFrame:
    """doc_id and text of the documents that entered stage 7: kept ones and those stage 7 removed."""
    kept = pd.concat([pd.read_parquet(f, columns=["doc_id", "text"])
                      for f in sorted((processed / "kept").glob("*.parquet"))])
    dropped = pd.concat([pd.read_parquet(f, columns=["doc_id", "text", "drop_stage"])
                         for f in sorted((processed / "dropped").glob("*.parquet"))])
    dropped = dropped[dropped["drop_stage"] == "quality"].drop(columns="drop_stage")
    return pd.concat([kept.assign(stage7="kept"), dropped.assign(stage7="removed")],
                     ignore_index=True).drop_duplicates("doc_id")


def load_labels(eval_dir: Path) -> pd.DataFrame:
    """doc_id, label (1 = poor page, 0 = acceptable), rule and side (fail / pass) of every labelled page."""
    rows = []
    for name in SHEETS:
        sheet, key = eval_dir / f"{name}.csv", eval_dir / f"{name}_key.csv"
        if sheet.exists() and key.exists():
            s = pd.read_csv(sheet, encoding="utf-8-sig")[["id", "label"]]
            k = pd.read_csv(key, encoding="utf-8-sig")[["id", "doc_id", "rule", "side"]].drop_duplicates("id")
            rows.append(k.merge(s, on="id").assign(sheet=name))
    if not rows:
        return pd.DataFrame(columns=["doc_id", "label", "rule", "side", "sheet"])
    lab = pd.concat(rows, ignore_index=True)
    lab = lab[pd.to_numeric(lab["label"], errors="coerce").isin([0, 1])]
    return lab.astype({"label": int}).drop_duplicates("doc_id")
