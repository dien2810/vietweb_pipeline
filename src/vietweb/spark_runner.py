"""SKELETON (weeks 8-10): run the per-document stages on Spark when the data no longer fits in memory.

Idea: normalize / boilerplate / langid / url_filter / quality / pii process each document independently, so they can
run with mapInPandas on each partition. Deduplication needs the whole collection:
- exact: groupBy the SHA-1 of the text and keep the first document.
- near: compute a MinHash signature per document, split it into 14 bands, groupBy (band_id, band_hash)
  to find candidate pairs, then merge clusters (connected components, e.g. GraphFrames or union-find).

On Windows, PySpark needs Java 17 and winutils; the least painful option is to run inside WSL2 (Ubuntu)
or Docker. See HUONG_DAN_CHAY.md, section on moving to Spark.

This file is NOT tested yet; use it as a starting point.
"""
from __future__ import annotations

from .config import load_config, resolve
from .stages import s03_normalize, s03b_boilerplate, s04_langid, s05_url_filter, s07_quality, s08_pii

PER_DOC = {
    "normalize": s03_normalize.run,
    "boilerplate": s03b_boilerplate.run,
    "langid": s04_langid.run,
    "url_filter": s05_url_filter.run,
    "quality": s07_quality.run,
    "pii": s08_pii.run,
}


def run_per_doc_stages_spark(config_path: str = "configs/pipeline.yaml", stages=("normalize", "boilerplate", "langid", "url_filter")):
    from pyspark.sql import SparkSession

    cfg = load_config(config_path)
    spark = (SparkSession.builder.appName("vietweb").master("local[*]")
             .config("spark.sql.execution.arrow.pyspark.enabled", "true").getOrCreate())
    raw = spark.read.parquet(str(resolve(cfg, cfg["paths"]["raw_dir"]) / "*" / "*.parquet"))

    def apply(batches):
        for pdf in batches:
            pdf = pdf.copy()
            pdf["drop_stage"] = None
            pdf["drop_reason"] = None
            for name in stages:
                active = pdf[pdf["drop_reason"].isna()]
                if active.empty:
                    break
                res = PER_DOC[name](active, cfg)
                if res.text is not None:
                    pdf.loc[active.index, "text"] = res.text
                if res.drop_reason is not None:
                    hit = res.drop_reason.dropna()
                    pdf.loc[hit.index, "drop_reason"] = hit
                    pdf.loc[hit.index, "drop_stage"] = name
            yield pdf[["doc_id", "url", "domain", "snapshot", "text", "drop_stage", "drop_reason"]]

    schema = "doc_id string, url string, domain string, snapshot string, text string, drop_stage string, drop_reason string"
    out = raw.mapInPandas(apply, schema=schema)
    out.write.mode("overwrite").parquet(str(resolve(cfg, cfg["paths"]["data_dir"]) / "spark_out"))
    return out


# TODO: exact dedup via groupBy on SHA-1; near dedup via MinHash banding as described at the top of this file.
