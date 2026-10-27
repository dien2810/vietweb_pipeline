"""Stages 2 and 9: write/read Parquet files and keep a manifest of processed WET files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

RAW_COLUMNS = ["doc_id", "url", "domain", "snapshot", "warc_record_id", "warc_refers_to", "crawl_date",
               "cld2_langs", "text"]


def write_parquet(records: Iterable[dict] | pd.DataFrame, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = records if isinstance(records, pd.DataFrame) else pd.DataFrame(list(records))
    if df.empty:
        df = pd.DataFrame(columns=RAW_COLUMNS)
    df.to_parquet(path, index=False)
    return len(df)


def write_sharded(df: pd.DataFrame, out_dir: Path, prefix: str, shard_size: int) -> list[Path]:
    """Write a DataFrame as several Parquet files with at most `shard_size` rows each."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{prefix}-*.parquet"):
        old.unlink()  # overwrite the previous run so outputs always match the current configuration
    paths = []
    for i, start in enumerate(range(0, max(len(df), 1), shard_size)):
        p = out_dir / f"{prefix}-{i:05d}.parquet"
        df.iloc[start:start + shard_size].to_parquet(p, index=False)
        paths.append(p)
    return paths


def read_raw(raw_dir: Path, crawls: list[str] | None = None) -> pd.DataFrame:
    """Read all raw Parquet files (optionally only for the given crawls) into one DataFrame."""
    files = []
    crawl_dirs = sorted(p for p in raw_dir.iterdir() if p.is_dir()) if raw_dir.exists() else []
    for d in crawl_dirs:
        if crawls and d.name not in crawls:
            continue
        files += sorted(d.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Parquet files found in {raw_dir}. Run the collect command first.")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


class Manifest:
    """Record processed WET files (JSON Lines) so that reruns do not ingest the same file twice."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.done: dict[str, dict] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        self.done[row["wet_path"]] = row

    def __contains__(self, wet_path: str) -> bool:
        return wet_path in self.done

    def add(self, row: dict) -> None:
        self.done[row["wet_path"]] = row
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        rows = list(self.done.values())
        return {
            "files": len(rows),
            "records_total": sum(r.get("records_total", 0) for r in rows),
            "records_vie": sum(r.get("records_vie", 0) for r in rows),
            "bytes": sum(r.get("bytes", 0) for r in rows),
        }
