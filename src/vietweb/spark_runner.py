"""Run stages 3-9 of the pipeline on Apache Spark (local mode on one machine, or a cluster).

The output is meant to be the same as `python -m vietweb run` (check it with scripts/compare_runs.py):

- Stages 3-5 (normalize, boilerplate, langid, url_filter) and 7-8 (quality, pii) treat each document on its
  own. They run in mapInPandas, which calls the same pandas functions as the in-memory pipeline on batches
  of documents, one batch per Spark task.
- Exact deduplication: a window over the SHA-1 of the normalized text keeps the first document of each
  group, "first" meaning the order of the in-memory pipeline (raw files sorted by name, rows in file order).
- Near deduplication: each document's MinHash signature (the same permutations as stage 6) is cut into 14
  bands of 8 values; Spark finds the band values that occur in more than one document. Stage 6 removes a
  document when it shares a band with a document KEPT before it, so the result depends on the order. The
  documents that share at least one band are few (a few percent), so the driver walks through them in order
  and applies exactly that rule; every other document cannot match anything and is kept. Bands are compared
  by their MD5 (a collision would need 2^64 work).
- Line deduplication: Spark counts, for every line of at least min_line_chars characters, the documents of
  the same domain and the distinct domains that contain it; the lines to remove are sent to the tasks.
- The quality stage runs with save_stats: false (it stops at the first failed rule). The decisions are the
  same; the per-rule metrics (quality_stats.parquet) and filter_costs.csv are not written.

Usage (Linux or WSL2 with Java 17 or 21; from the repository root). Spark 3.5 fails in mapInPandas on Java 21
(Arrow cannot allocate memory), so use Spark 4.0:
    pip install pyspark==4.0.1
    python -m vietweb.spark_runner --cores 8 --out data/spark_out
    python scripts/compare_runs.py outputs/runs/wet_200_par/processed data/spark_out
    python -m vietweb.spark_runner --cores 1 2 4 8 --out data/spark_out    # throughput by number of cores

Writes <out>/kept and <out>/dropped (Parquet), and <out>/funnel.csv and <out>/spark_runs.csv (time of each
phase). Differences from the in-memory run: no per-stage seconds (Spark fuses the stages; the phases are timed
instead), near_dup_cluster names the earliest kept document of the cluster, and the column order may differ.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import load_config, resolve
from .io.storage import raw_files
from .stages import s03_normalize, s03b_boilerplate, s04_langid, s05_url_filter, s06_dedup, s07_quality, s08_pii

log = logging.getLogger(__name__)

PER_DOC = {"normalize": s03_normalize.run, "boilerplate": s03b_boilerplate.run, "langid": s04_langid.run,
           "url_filter": s05_url_filter.run}
LATE = {"quality": s07_quality.run, "pii": s08_pii.run}
ORDER = ["normalize", "boilerplate", "langid", "url_filter", "dedup_exact", "dedup_near", "dedup_line",
         "quality", "pii"]
RAW_COLUMNS = ["doc_id", "url", "domain", "snapshot", "warc_record_id", "warc_refers_to", "crawl_date",
               "cld2_langs", "text"]
EXTRA = {"legacy_score": "double", "legacy_encoding": "string", "bp_chars_ratio": "double",
         "lang_score": "double", "spam_kw_hits": "double", "text_sha1": "string", "near_dup_cluster": "string",
         "pii_email": "double", "pii_ipv4": "double", "pii_phone_vn": "double", "pii_cccd": "double"}
SCHEMA = ", ".join([f"{c} string" for c in RAW_COLUMNS] + ["order long", "drop_stage string", "drop_reason string"]
                   + [f"{c} {t}" for c, t in EXTRA.items()])


# ---------------------------------------------------------------------------------------------------------
# Functions that run inside the Spark tasks (on pandas batches)

def _apply(pdf: pd.DataFrame, names: list[str], funcs: dict, cfg: dict) -> pd.DataFrame:
    """Run stages on the still-kept rows of a batch, exactly as pipeline._run_stage does on the whole table."""
    for name in names:
        active = pdf[pdf["drop_reason"].isna()]
        if active.empty:
            continue
        res = funcs[name](active, cfg)
        if res.text is not None:
            pdf.loc[active.index, "text"] = res.text
        for col, values in res.extra.items():
            if col in EXTRA:
                pdf.loc[active.index, col] = values
        if res.drop_reason is not None:
            hit = res.drop_reason.dropna()
            pdf.loc[hit.index, "drop_reason"] = hit
            pdf.loc[hit.index, "drop_stage"] = name
    return pdf


def _conform(pdf: pd.DataFrame) -> pd.DataFrame:
    """Column order and types of SCHEMA."""
    for col, typ in EXTRA.items():
        if typ == "double":
            pdf[col] = pd.to_numeric(pdf[col], errors="coerce").astype("float64")
        else:
            pdf[col] = pdf[col].astype(object).where(pdf[col].notna(), None)
    for col in ("drop_stage", "drop_reason"):
        pdf[col] = pdf[col].astype(object).where(pdf[col].notna(), None)
    return pdf[RAW_COLUMNS + ["order", "drop_stage", "drop_reason"] + list(EXTRA)]


def _sha1(text: str) -> str:
    return hashlib.sha1(s06_dedup._norm_for_hash(text).encode("utf-8")).hexdigest()


def _per_doc_fn(cfg: dict, names: list[str]):
    def fn(batches):
        for pdf in batches:
            pdf = pdf.reset_index(drop=True)
            pdf["drop_stage"], pdf["drop_reason"] = None, None
            for col in EXTRA:
                pdf[col] = None
            pdf = _apply(pdf, names, PER_DOC, cfg)
            act = pdf["drop_reason"].isna()
            # Key of the exact deduplication (stage 6 hashes the same text: stages 4-5 do not change it)
            pdf.loc[act, "text_sha1"] = [_sha1(t) for t in pdf.loc[act, "text"]]
            yield _conform(pdf)
    return fn


def _bands_fn(cfg: dict):
    c = cfg["dedup"]["near"]
    unit, n, num_perm, b, r = c.get("unit", "syllable"), c.get("ngram", 5), c.get("num_perm", 112), c["bands"], c["rows"]

    def fn(batches):
        for pdf in batches:
            orders, ids, bands, keys = [], [], [], []
            for o, d, t in zip(pdf["order"], pdf["doc_id"], pdf["text"]):
                hv = s06_dedup.signature(t, unit, n, num_perm)
                for i in range(b):
                    orders.append(o)
                    ids.append(d)
                    bands.append(i)
                    keys.append(hashlib.md5(hv[i * r:(i + 1) * r].tobytes()).hexdigest())
            yield pd.DataFrame({"order": orders, "doc_id": ids, "band": bands, "key": keys})
    return fn


def _line_keys_fn(min_chars: int):
    def fn(batches):
        for pdf in batches:
            doms, lines = [], []
            for dom, text in zip(pdf["domain"], pdf["text"]):
                for ln in {ln.strip() for ln in text.split("\n") if len(ln.strip()) >= min_chars}:
                    doms.append(dom)
                    lines.append(ln)
            yield pd.DataFrame({"domain": doms, "line": lines})
    return fn


def _line_strip_fn(same_domain: frozenset, cross: frozenset, min_chars: int):
    def strip(dom: str, text: str) -> tuple[str, int, int, bool]:
        keep, n_same, n_cross = [], 0, 0
        for ln in text.split("\n"):
            s = ln.strip()
            if len(s) >= min_chars:
                if (dom, s) in same_domain:
                    n_same += 1
                    continue
                if s in cross:
                    n_cross += 1
                    continue
            keep.append(ln)
        return "\n".join(keep).strip(), n_same, n_cross, n_cross > 0

    def fn(batches):
        for pdf in batches:
            pdf = pdf.reset_index(drop=True)
            act = pdf["drop_reason"].isna()
            pdf["_same"], pdf["_cross"], pdf["_hit"] = 0, 0, False
            if act.any():
                out = [strip(d, t) for d, t in zip(pdf.loc[act, "domain"], pdf.loc[act, "text"])]
                pdf.loc[act, "text"] = [o[0] for o in out]
                pdf.loc[act, "_same"] = [o[1] for o in out]
                pdf.loc[act, "_cross"] = [o[2] for o in out]
                pdf.loc[act, "_hit"] = [o[3] for o in out]
                empty = act & (pdf["text"].str.len() == 0)
                pdf.loc[empty, "drop_reason"] = "empty_after_line_dedup"
                pdf.loc[empty, "drop_stage"] = "dedup_line"
            out = _conform(pdf.drop(columns=["_same", "_cross", "_hit"]))
            out["_same"], out["_cross"], out["_hit"] = pdf["_same"].astype("int64"), pdf["_cross"].astype("int64"), pdf["_hit"]
            yield out
    return fn


def _late_fn(cfg: dict):
    def fn(batches):
        for pdf in batches:
            pdf = pdf.reset_index(drop=True)
            yield _conform(_apply(pdf, ["quality", "pii"], LATE, cfg))
    return fn


# ---------------------------------------------------------------------------------------------------------
# Driver

def _greedy_near(cand: pd.DataFrame) -> dict[str, str]:
    """Stage-6 rule on the documents that share a band: in order, a document that shares a band with an
    already kept document is removed; otherwise it is kept. Returns {removed doc_id: earliest kept match}."""
    owner: dict[tuple[int, str], tuple[int, str]] = {}      # band value -> (order, doc_id) of the kept document
    removed: dict[str, str] = {}
    if cand.empty:
        return removed
    cand = cand.sort_values(["order", "band"])
    for (order, doc_id), g in cand.groupby(["order", "doc_id"], sort=True):
        keys = list(zip(g["band"], g["key"]))
        hits = [owner[k] for k in keys if k in owner]
        if hits:
            removed[doc_id] = min(hits)[1]
        else:
            for k in keys:
                owner[k] = (order, doc_id)
    return removed


def _session(cores: int, driver_memory: str, raw_bytes: int):
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    src = str(Path(__file__).resolve().parents[1])            # .../src, so that the tasks can import vietweb
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (src, os.environ.get("PYTHONPATH", "")) if p)
    from pyspark.sql import SparkSession
    split = max(1 << 20, min(128 << 20, raw_bytes // max(4 * cores, 1)))   # about 4 input tasks per core
    spark = (SparkSession.builder.appName("vietweb").master(f"local[{cores}]")
             .config("spark.driver.memory", driver_memory)
             .config("spark.sql.files.maxPartitionBytes", str(split))
             .config("spark.sql.shuffle.partitions", str(max(4 * cores, 4)))
             .config("spark.sql.execution.arrow.pyspark.enabled", "true")
             .config("spark.sql.execution.arrow.maxRecordsPerBatch", "2000")
             .config("spark.ui.enabled", "false")
             # Apache Arrow (used by mapInPandas) needs this on Java 11+
             .config("spark.driver.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
             .config("spark.executor.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    return spark


def run_spark(cfg: dict, out_dir: Path, cores: int, crawls: list[str] | None = None,
              driver_memory: str = "4g") -> dict:
    from pyspark import StorageLevel
    from pyspark.sql import functions as F
    from pyspark.sql import Window

    stages = [s for s in cfg["stages"]]
    if stages != ORDER:
        raise ValueError(f"spark_runner supports the default stage order only: {ORDER}")
    cfg = copy.deepcopy(cfg)
    cfg["parallel"] = {"workers": 1}            # Spark runs the tasks in parallel; no processes inside a task
    cfg["quality"]["save_stats"] = False
    c_line = cfg["dedup"]["line"]
    k, min_chars, min_domains = c_line.get("min_docs_per_domain", 3), c_line.get("min_line_chars", 10), \
        c_line.get("min_domains", 0) or 0

    files = raw_files(resolve(cfg, cfg["paths"]["raw_dir"]), crawls)
    raw_bytes = sum(f.stat().st_size for f in files)
    # Order of the in-memory pipeline: files sorted by name, rows in file order; first copy of a doc_id wins
    import pyarrow.parquet as pq
    ids = pd.concat([pq.read_table(f, columns=["doc_id"]).to_pandas() for f in files], ignore_index=True)
    ids["order"] = range(len(ids))
    ids = ids.drop_duplicates("doc_id")
    ids["doc_id"] = ids["doc_id"].astype(object)          # plain strings for createDataFrame (pandas 3)

    spark = _session(cores, driver_memory, raw_bytes)
    times: dict[str, float] = {}
    try:
        t0 = time.perf_counter()
        order_df = spark.createDataFrame(ids)
        raw = spark.read.parquet(*[str(f) for f in files]).select(*RAW_COLUMNS).dropDuplicates(["doc_id"])
        raw = raw.join(F.broadcast(order_df), "doc_id")
        n_input = len(ids)

        # Phase 1: stages 3-5
        t = time.perf_counter()
        df = raw.mapInPandas(_per_doc_fn(cfg, list(PER_DOC)), schema=SCHEMA).persist(StorageLevel.MEMORY_AND_DISK)
        df.count()
        times["stages 3-5"] = time.perf_counter() - t

        # Phase 2: exact duplicates
        t = time.perf_counter()
        w = Window.partitionBy("text_sha1").orderBy("order")
        rn = F.when(F.col("drop_reason").isNull(), F.row_number().over(w))
        df2 = (df.withColumn("_rn", rn)
               .withColumn("drop_stage", F.when(F.col("_rn") > 1, F.lit("dedup_exact")).otherwise(F.col("drop_stage")))
               .withColumn("drop_reason", F.when(F.col("_rn") > 1, F.lit("exact_duplicate")).otherwise(F.col("drop_reason")))
               .drop("_rn").persist(StorageLevel.MEMORY_AND_DISK))
        df2.count()
        df.unpersist()
        times["exact dedup"] = time.perf_counter() - t

        # Phase 3: near duplicates
        t = time.perf_counter()
        active = df2.filter(F.col("drop_reason").isNull()).select("order", "doc_id", "text")
        bands = active.mapInPandas(_bands_fn(cfg), schema="order long, doc_id string, band int, key string")
        bands = bands.persist(StorageLevel.MEMORY_AND_DISK)
        shared = bands.groupBy("band", "key").count().filter(F.col("count") > 1).select("band", "key")
        cand = bands.join(shared, ["band", "key"]).select("order", "doc_id", "band", "key").toPandas()
        bands.unpersist()
        removed = _greedy_near(cand)
        near = spark.createDataFrame(pd.DataFrame({"doc_id": list(removed), "_rep": list(removed.values())}),
                                     schema="doc_id string, _rep string")
        df3 = (df2.join(F.broadcast(near), "doc_id", "left")
               .withColumn("_near", F.col("drop_reason").isNull() & F.col("_rep").isNotNull())
               .withColumn("near_dup_cluster", F.when(F.col("_near"), F.col("_rep"))
                           .when(F.col("drop_reason").isNull(), F.col("doc_id")).otherwise(F.col("near_dup_cluster")))
               .withColumn("drop_stage", F.when(F.col("_near"), F.lit("dedup_near")).otherwise(F.col("drop_stage")))
               .withColumn("drop_reason", F.when(F.col("_near"), F.lit("near_duplicate")).otherwise(F.col("drop_reason")))
               .drop("_rep", "_near").persist(StorageLevel.MEMORY_AND_DISK))
        df3.count()
        df2.unpersist()
        times["near dedup"] = time.perf_counter() - t

        # Phase 4: repeated lines
        t = time.perf_counter()
        pairs = (df3.filter(F.col("drop_reason").isNull()).select("domain", "text")
                 .mapInPandas(_line_keys_fn(min_chars), schema="domain string, line string")
                 .persist(StorageLevel.MEMORY_AND_DISK))
        same = pairs.groupBy("domain", "line").count().filter(F.col("count") >= k).select("domain", "line").toPandas()
        cross = set()
        if min_domains:
            cross = set(pairs.groupBy("line").agg(F.countDistinct("domain").alias("n"))
                        .filter(F.col("n") >= min_domains).select("line").toPandas()["line"])
        pairs.unpersist()
        same_set = frozenset(zip(same["domain"], same["line"]))
        line_schema = SCHEMA + ", _same long, _cross long, _hit boolean"
        df4p = df3.mapInPandas(_line_strip_fn(same_set, frozenset(cross), min_chars), schema=line_schema)
        df4p = df4p.persist(StorageLevel.MEMORY_AND_DISK)
        line_stats = df4p.agg(F.sum("_same"), F.sum("_cross"), F.sum(F.col("_hit").cast("int"))).collect()[0]
        df4 = df4p.drop("_same", "_cross", "_hit")
        df3.unpersist()
        times["line dedup"] = time.perf_counter() - t

        # Phase 5: stages 7-8
        t = time.perf_counter()
        df5 = df4.mapInPandas(_late_fn(cfg), schema=SCHEMA).persist(StorageLevel.MEMORY_AND_DISK)
        df5.count()
        times["stages 7-8"] = time.perf_counter() - t

        # Phase 6: export
        t = time.perf_counter()
        shard = cfg.get("export", {}).get("shard_size", 20000)
        kept = df5.filter(F.col("drop_reason").isNull())
        n_kept = kept.count()
        n_dropped = n_input - n_kept
        out_dir.mkdir(parents=True, exist_ok=True)
        (kept.drop("drop_stage", "drop_reason", "order").coalesce(max(1, -(-n_kept // shard)))
         .write.mode("overwrite").parquet(str(out_dir / "kept")))
        (df5.filter(F.col("drop_reason").isNotNull()).drop("order").coalesce(max(1, -(-n_dropped // shard)))
         .write.mode("overwrite").parquet(str(out_dir / "dropped")))
        counts = {(r["drop_stage"], r["drop_reason"]): r["count"]
                  for r in df5.groupBy("drop_stage", "drop_reason").count().collect()}
        df4p.unpersist()
        df5.unpersist()
        times["export"] = time.perf_counter() - t
        times["total"] = time.perf_counter() - t0
    finally:
        spark.stop()

    # Funnel (same columns as outputs/stats/funnel.csv; seconds are not per stage)
    rows, docs = [{"stage": "input", "docs_in": n_input, "docs_out": n_input, "removed": 0, "top_reason": ""}], n_input
    for name in ORDER:
        by_reason = {r: n for (s, r), n in counts.items() if s == name}
        removed_n = sum(by_reason.values())
        top = max(by_reason, key=by_reason.get) if by_reason else ""
        rows.append({"stage": name, "docs_in": docs, "docs_out": docs - removed_n, "removed": removed_n, "top_reason": top})
        docs -= removed_n
    funnel = pd.DataFrame(rows)
    funnel["pct_of_input"] = (100 * funnel["docs_out"] / max(n_input, 1)).round(2)
    funnel.to_csv(out_dir / "funnel.csv", index=False)
    info = {"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cores": cores,
            "files": len(files), "n_input": n_input, "n_kept": n_kept,
            "near_candidates": int(cand["doc_id"].nunique()) if len(cand) else 0, "near_removed": len(removed),
            "removed_lines_same_domain": int(line_stats[0] or 0), "removed_lines_cross_site": int(line_stats[1] or 0),
            "docs_with_cross_site_lines": int(line_stats[2] or 0), "cross_site_distinct_lines": len(cross),
            "seconds": {k_: round(v, 2) for k_, v in times.items()}}
    (out_dir / "run_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--crawl", action="append", help="only process this crawl (repeatable)")
    ap.add_argument("--cores", type=int, nargs="+", default=[os.cpu_count() or 1],
                    help="Spark local[N]; several values run the pipeline once per value")
    ap.add_argument("--out", default="data/spark_out")
    ap.add_argument("--driver-memory", default="4g")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    crawls = args.crawl or [cfg["collect"]["crawl"]]
    out = resolve(cfg, args.out)
    runs = []
    for cores in args.cores:
        info = run_spark(cfg, out, cores, crawls, args.driver_memory)
        print(json.dumps(info, ensure_ascii=False))
        runs.append({"cores": cores, "n_input": info["n_input"], "n_kept": info["n_kept"],
                     **{f"s_{k_}": v for k_, v in info["seconds"].items()}})
    table = pd.DataFrame(runs)
    table["docs_per_s"] = (table["n_input"] / table["s_total"]).round(1)
    path = out / "spark_runs.csv"
    if path.exists() and len(args.cores) == 1:
        table = pd.concat([pd.read_csv(path), table], ignore_index=True)
    table.to_csv(path, index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
