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

from .config import resolve
from .io.storage import read_raw, write_sharded
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


def run_pipeline(cfg: dict, crawls: list[str] | None = None, limit: int | None = None) -> pd.DataFrame:
    stats_dir = resolve(cfg, cfg["paths"]["stats_dir"])
    stats_dir.mkdir(parents=True, exist_ok=True)

    df = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]), crawls)
    if limit:
        df = df.sample(n=min(limit, len(df)), random_state=cfg.get("seed", 42)).reset_index(drop=True)
    df = df.drop_duplicates("doc_id").reset_index(drop=True)
    df["drop_stage"] = None
    df["drop_reason"] = None
    n_input = len(df)
    log.info("Input: %d documents", n_input)

    funnel = [{"stage": "input", "docs_in": n_input, "docs_out": n_input, "removed": 0,
               "seconds": 0.0, "top_reason": "", "details": ""}]
    quality_extra = None

    for name in cfg["stages"]:
        if name not in STAGES:
            raise ValueError(f"Unknown stage: {name}. Valid stages: {list(STAGES)}")
        if name in _ENABLED and not _ENABLED[name](cfg):
            log.info("Skipping stage %s (disabled)", name)
            continue
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
        if name == "quality" and res.extra:
            quality_extra = pd.DataFrame(res.extra)
            quality_extra.insert(0, "doc_id", active["doc_id"].values)
        removed = 0
        top_reason = ""
        if res.drop_reason is not None:
            hit = res.drop_reason.dropna()
            df.loc[hit.index, "drop_reason"] = hit
            df.loc[hit.index, "drop_stage"] = name
            removed = len(hit)
            if removed:
                top_reason = hit.value_counts().index[0]
        details = {k: v for k, v in res.stats.items() if k != "rule_costs"}
        funnel.append({"stage": name, "docs_in": len(active), "docs_out": len(active) - removed,
                       "removed": removed, "seconds": round(secs, 3), "top_reason": top_reason,
                       "details": json.dumps(details, ensure_ascii=False)})
        log.info("%-12s in %7d  removed %7d  (%.1fs)  %s", name, len(active), removed, secs, top_reason)

        if name == "quality" and "rule_costs" in res.stats:
            pd.DataFrame(res.stats["rule_costs"]).to_csv(stats_dir / "filter_costs.csv", index=False)

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
        "langid_backend": cfg["langid"].get("backend"),
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
