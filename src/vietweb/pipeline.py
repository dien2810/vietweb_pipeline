"""Runner: apply stages 3-8 in the configured order, then stage 9 (export).

- Removed documents are kept with `drop_stage` and `drop_reason` (the audit set) instead of being deleted.
- Each stage writes its input/output counts and runtime to outputs/stats/funnel.csv.
- The quality stage also writes outputs/stats/filter_costs.csv and quality_stats.parquet.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd

from . import parallel
from .config import resolve
from .io.storage import raw_files, read_raw, write_sharded
from .stages import s03_normalize, s03b_boilerplate, s04_langid, s05_url_filter, s06_dedup, s07_quality, s08_pii
from .validation import validate_output

log = logging.getLogger(__name__)

STAGES = {
    "normalize": s03_normalize.run,
    "boilerplate": s03b_boilerplate.run,
    "langid": s04_langid.run,
    "url_filter": s05_url_filter.run,
    "dedup_exact": s06_dedup.run_exact,
    "dedup_near": s06_dedup.run_near,
    "dedup_line": s06_dedup.run_line,
    "quality": s07_quality.run,
    "pii": s08_pii.run,
}

# Stages disabled in the configuration are skipped
_ENABLED = {
    "boilerplate": lambda c: c.get("boilerplate", {}).get("enabled", True)
    and c.get("boilerplate", {}).get("method", "justext") != "none",
    "dedup_exact": lambda c: c["dedup"]["exact"].get("enabled", True),
    "dedup_near": lambda c: c["dedup"]["near"].get("enabled", True),
    "dedup_line": lambda c: c["dedup"]["line"].get("enabled", True),
}


# Stages that look at one document at a time. With memory.batch_files > 0, the stages at the start of the
# configured order that are in this set run on a few raw files at a time; only the documents they produce
# (text already cleaned by stage 3b, about a third of the raw characters) are kept in memory for the
# stages that need every document at once (deduplication). The output is the same as without batches.
PER_DOC = {"normalize", "boilerplate", "langid", "url_filter"}


def _run_stage(name: str, df: pd.DataFrame, cfg: dict, stats_dir) -> dict:
    """Run one stage on the documents of df that are still kept; update df in place; return its funnel row."""
    active = df[df["drop_reason"].isna()]
    t0 = time.perf_counter()
    res = STAGES[name](active, cfg)
    secs = time.perf_counter() - t0
    if res.text is not None:
        df.loc[active.index, "text"] = res.text
    for col, values in res.extra.items():
        if name == "quality" and col.startswith("q_"):
            continue  # quality metrics are stored separately to keep the main table small
        df.loc[active.index, col] = values
    removed, top_reason = 0, ""
    if res.drop_reason is not None:
        hit = res.drop_reason.dropna()
        df.loc[hit.index, "drop_reason"] = hit
        df.loc[hit.index, "drop_stage"] = name
        removed = len(hit)
        if removed:
            top_reason = hit.value_counts().index[0]
    if name == "quality" and "rule_costs" in res.stats:
        pd.DataFrame(res.stats["rule_costs"]).to_csv(stats_dir / "filter_costs.csv", index=False)
    log.info("%-12s in %7d  removed %7d  (%.1fs)  %s", name, len(active), removed, secs, top_reason)
    row = {"stage": name, "docs_in": len(active), "docs_out": len(active) - removed, "removed": removed,
           "seconds": round(secs, 3), "top_reason": top_reason,
           "details": {k: v for k, v in res.stats.items() if k != "rule_costs"}}
    if name == "quality" and res.extra:
        qe = pd.DataFrame(res.extra)
        qe.insert(0, "doc_id", active["doc_id"].values)
        row["quality_extra"] = qe
    return row


def _merge_rows(rows: list[dict], df: pd.DataFrame) -> dict:
    """Combine the funnel rows of one stage over several batches."""
    name = rows[0]["stage"]
    docs_in = sum(r["docs_in"] for r in rows)
    details = {}
    for key in rows[0]["details"]:
        vals = [r["details"].get(key) for r in rows]
        if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
            details[key] = sum(vals)
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            details[key] = round(sum(v * r["docs_in"] for v, r in zip(vals, rows)) / max(docs_in, 1), 4)
        else:
            details[key] = vals[0]
    details["batches"] = len(rows)
    reasons = df.loc[df["drop_stage"] == name, "drop_reason"]
    return {"stage": name, "docs_in": docs_in, "docs_out": sum(r["docs_out"] for r in rows),
            "removed": sum(r["removed"] for r in rows), "seconds": round(sum(r["seconds"] for r in rows), 3),
            "top_reason": reasons.value_counts().index[0] if len(reasons) else "", "details": details}


def run_pipeline(cfg: dict, crawls: list[str] | None = None, limit: int | None = None) -> pd.DataFrame:
    stats_dir = resolve(cfg, cfg["paths"]["stats_dir"])
    stats_dir.mkdir(parents=True, exist_ok=True)
    for name in cfg["stages"]:
        if name not in STAGES:
            raise ValueError(f"Unknown stage: {name}. Valid stages: {list(STAGES)}")
    stages = []
    for name in cfg["stages"]:
        if name in _ENABLED and not _ENABLED[name](cfg):
            log.info("Skipping stage %s (disabled)", name)
        else:
            stages.append(name)
    batch_files = int(cfg.get("memory", {}).get("batch_files", 0) or 0)
    prefix = []
    if batch_files > 0 and not limit:
        for name in stages:
            if name not in PER_DOC:
                break
            prefix.append(name)

    raw_dir = resolve(cfg, cfg["paths"]["raw_dir"])
    rows: list[dict] = []
    try:
        if prefix:
            files = raw_files(raw_dir, crawls)
            parts, seen, batch_rows = [], set(), {name: [] for name in prefix}
            for i in range(0, len(files), batch_files):
                b = pd.concat([pd.read_parquet(f) for f in files[i:i + batch_files]], ignore_index=True)
                b = b.drop_duplicates("doc_id")
                b = b[~b["doc_id"].isin(seen)].reset_index(drop=True)
                seen.update(b["doc_id"])
                b["drop_stage"] = None
                b["drop_reason"] = None
                for name in prefix:
                    batch_rows[name].append(_run_stage(name, b, cfg, stats_dir))
                parts.append(b)
                log.info("Batch %d-%d of %d raw files done", i + 1, min(i + batch_files, len(files)), len(files))
            df = pd.concat(parts, ignore_index=True)
            del parts
            rows += [_merge_rows(batch_rows[name], df) for name in prefix]
        else:
            df = read_raw(raw_dir, crawls)
            if limit:
                df = df.sample(n=min(limit, len(df)), random_state=cfg.get("seed", 42)).reset_index(drop=True)
            df = df.drop_duplicates("doc_id").reset_index(drop=True)
            df["drop_stage"] = None
            df["drop_reason"] = None
        n_input = len(df)
        log.info("Input: %d documents", n_input)
        for name in stages[len(prefix):]:
            rows.append(_run_stage(name, df, cfg, stats_dir))
    finally:
        parallel.shutdown()  # stop the worker processes (parallel.workers > 1)

    quality_extra = next((r.pop("quality_extra") for r in rows if "quality_extra" in r), None)
    funnel = [{"stage": "input", "docs_in": n_input, "docs_out": n_input, "removed": 0,
               "seconds": 0.0, "top_reason": "", "details": ""}]
    funnel += [{**r, "details": json.dumps(r["details"], ensure_ascii=False)} for r in rows]

    # Stage 9: export
    t0 = time.perf_counter()
    export(df, cfg, quality_extra)
    kept = int(df["drop_reason"].isna().sum())
    funnel.append({"stage": "export", "docs_in": kept, "docs_out": kept, "removed": 0,
                   "seconds": round(time.perf_counter() - t0, 3), "top_reason": "", "details": ""})
    fdf = pd.DataFrame(funnel)
    fdf["pct_of_input"] = (100 * fdf["docs_out"] / max(n_input, 1)).round(2)
    fdf.to_csv(stats_dir / "funnel.csv", index=False)
    (stats_dir / "run_info.json").write_text(json.dumps({
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_input": n_input, "n_kept": kept, "stages": cfg["stages"],
        "quality_unit": cfg["quality"].get("unit"), "near_dup_unit": cfg["dedup"]["near"].get("unit"),
        "langid_backend": cfg["langid"].get("backend"), "workers": parallel.n_workers(cfg),
        "batch_files": batch_files if prefix else 0,
        "boilerplate_method": cfg.get("boilerplate", {}).get("method") if "boilerplate" in cfg["stages"] else None,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return fdf


def export(df: pd.DataFrame, cfg: dict, quality_extra: pd.DataFrame | None) -> None:
    out = resolve(cfg, cfg["paths"]["processed_dir"])
    shard = cfg.get("export", {}).get("shard_size", 20000)
    kept = df[df["drop_reason"].isna()].drop(columns=["drop_stage", "drop_reason"])
    dropped = df[df["drop_reason"].notna()]
    problems = validate_output(kept)
    if problems:
        log.warning("Output check found problems: %s", problems)
    write_sharded(kept, out / "kept", "kept", shard)
    write_sharded(dropped, out / "dropped", "dropped", shard)
    if quality_extra is not None:
        stats_dir = resolve(cfg, cfg["paths"]["stats_dir"])
        quality_extra.to_parquet(stats_dir / "quality_stats.parquet", index=False)
