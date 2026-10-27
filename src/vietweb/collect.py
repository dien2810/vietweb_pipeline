"""Stages 1-2: collect Vietnamese records from WET files and store them as raw Parquet.

Each WET file is processed independently: it is downloaded to a temporary folder, its Vietnamese
records are written to data/raw/<crawl>/<file name>.parquet, a line is appended to _manifest.jsonl,
and the WET file is deleted. Rerunning the command skips files already listed in the manifest.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from tqdm import tqdm

from .config import resolve
from .io import commoncrawl as cc
from .io.storage import Manifest, write_parquet

log = logging.getLogger(__name__)


def _shard_name(wet_path: str) -> str:
    # crawl-data/CC-MAIN-.../segments/<seg>/wet/CC-MAIN-...-00001.warc.wet.gz -> <seg>__<file>
    parts = wet_path.split("/")
    seg = parts[-3] if len(parts) >= 3 else "seg"
    return f"{seg}__{parts[-1].replace('.warc.wet.gz', '')}"


def process_wet_file(wet_file: Path, wet_path: str, crawl: str, out_dir: Path, ccfg: dict,
                     manifest: Manifest, measure_total: bool = True) -> dict:
    t0 = time.time()
    records = list(cc.iter_wet_records(wet_file, language=ccfg.get("language_prefilter", "vie"),
                                       min_chars=ccfg.get("min_chars", 0), snapshot=crawl))
    total = cc.count_records(wet_file) if measure_total else 0
    out = out_dir / f"{_shard_name(wet_path)}.parquet"
    write_parquet(records, out)
    row = {
        "wet_path": wet_path,
        "parquet": str(out.name),
        "records_total": total,
        "records_vie": len(records),
        "bytes": wet_file.stat().st_size,
        "seconds": round(time.time() - t0, 2),
    }
    manifest.add(row)
    return row


def collect(cfg: dict, n_files: int, crawl: str | None = None) -> dict:
    ccfg = cfg["collect"]
    crawl = crawl or ccfg["crawl"]
    http = ccfg.get("http", {})
    http_args = {k: http[k] for k in ("timeout", "max_retries", "backoff_seconds") if k in http}
    tmp_dir = resolve(cfg, cfg["paths"]["tmp_dir"])
    raw_dir = resolve(cfg, cfg["paths"]["raw_dir"]) / crawl
    paths_file = cc.download_wet_paths(crawl, ccfg["base_url"], resolve(cfg, cfg["paths"]["data_dir"]) / "paths",
                                       **http_args)
    all_paths = cc.read_wet_paths(paths_file)
    chosen = cc.select_paths(all_paths, n_files, ccfg.get("sample", "random"), cfg.get("seed", 42))
    manifest = Manifest(raw_dir / "_manifest.jsonl")
    todo = [p for p in chosen if p not in manifest]
    log.info("%s: %d WET files listed, %d selected, %d to download", crawl, len(all_paths), len(chosen), len(todo))

    for wet_path in tqdm(todo, desc=f"collect {crawl}", unit="file"):
        local = tmp_dir / Path(wet_path).name
        cc.http_get_to_file(f"{ccfg['base_url']}/{wet_path}", local, **http_args)
        row = process_wet_file(local, wet_path, crawl, raw_dir, ccfg, manifest)
        log.info("%s: %d/%d Vietnamese records (%.1fs)", row["parquet"], row["records_vie"],
                 row["records_total"], row["seconds"])
        if not ccfg.get("keep_wet", False):
            local.unlink(missing_ok=True)
        time.sleep(http.get("pause_between_files", 0))
    return manifest.summary()


def collect_local(cfg: dict, wet_files: list[Path], crawl: str = "LOCAL") -> dict:
    """Collect from WET files already on disk (offline use and testing)."""
    ccfg = cfg["collect"]
    raw_dir = resolve(cfg, cfg["paths"]["raw_dir"]) / crawl
    manifest = Manifest(raw_dir / "_manifest.jsonl")
    for f in wet_files:
        key = f"local/{f.name}"
        if key in manifest:
            continue
        process_wet_file(f, key, crawl, raw_dir, ccfg, manifest)
    return manifest.summary()
