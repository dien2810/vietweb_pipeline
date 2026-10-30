"""Check that two runs give the same output: the same kept documents with the same text, and the same
removal stage and reason for every removed document.

    python scripts/compare_runs.py outputs/runs/wet_200_final/processed data/processed
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def load(folder: Path, part: str, cols: list[str]) -> pd.DataFrame:
    files = sorted((folder / part).glob("*.parquet"))
    if not files:
        raise SystemExit(f"No Parquet files in {folder / part}")
    return pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True).set_index("doc_id")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    args = ap.parse_args()
    ka, kb = load(args.a, "kept", ["doc_id", "text"]), load(args.b, "kept", ["doc_id", "text"])
    da = load(args.a, "dropped", ["doc_id", "drop_stage", "drop_reason"])
    db = load(args.b, "dropped", ["doc_id", "drop_stage", "drop_reason"])
    only_a, only_b = ka.index.difference(kb.index), kb.index.difference(ka.index)
    common = ka.index.intersection(kb.index)
    text_diff = int((ka.loc[common, "text"] != kb.loc[common, "text"]).sum())
    dcommon = da.index.intersection(db.index)
    reason_diff = int((da.loc[dcommon, ["drop_stage", "drop_reason"]]
                       != db.loc[dcommon, ["drop_stage", "drop_reason"]]).any(axis=1).sum())
    print(f"kept: {len(ka)} vs {len(kb)}; only in A: {len(only_a)}; only in B: {len(only_b)}; "
          f"different text: {text_diff}")
    print(f"dropped: {len(da)} vs {len(db)}; different stage or reason: {reason_diff}")
    same = not (len(only_a) or len(only_b) or text_diff or reason_diff or len(da) != len(db))
    print("IDENTICAL" if same else "DIFFERENT")
    raise SystemExit(0 if same else 1)


if __name__ == "__main__":
    main()
