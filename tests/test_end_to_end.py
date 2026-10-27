"""Run the whole pipeline on the synthetic WET file inside a temporary folder (real data/ is untouched)."""
import copy
import importlib.util
from pathlib import Path

import pandas as pd

from vietweb.collect import collect_local
from vietweb.config import load_config
from vietweb.ordering import suggest_order
from vietweb.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _make_wet(path: Path) -> Path:
    spec = importlib.util.spec_from_file_location("make_sample_wet", ROOT / "scripts" / "make_sample_wet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.make(path)


def test_pipeline_on_sample(tmp_path):
    cfg = copy.deepcopy(load_config("configs/pipeline.yaml"))
    for k in ("data_dir", "raw_dir", "processed_dir", "stats_dir", "eval_dir", "tmp_dir"):
        cfg["paths"][k] = str(tmp_path / k)
    wet = _make_wet(tmp_path / "sample.warc.wet.gz")

    summary = collect_local(cfg, [wet], crawl="SAMPLE")
    assert summary["records_vie"] >= 8          # English record removed by the pre-filter, short record dropped

    funnel = run_pipeline(cfg)
    by_stage = funnel.set_index("stage")
    assert by_stage.loc["url_filter", "removed"] >= 1      # gambling spam
    assert by_stage.loc["dedup_exact", "removed"] >= 1
    assert by_stage.loc["dedup_near", "removed"] >= 1

    kept = pd.concat(pd.read_parquet(p) for p in (tmp_path / "processed_dir" / "kept").glob("*.parquet"))
    assert kept["text"].str.contains("<PHONE>").any()
    assert not kept["text"].str.contains("0912 345 678").any()

    costs = pd.read_csv(tmp_path / "stats_dir" / "filter_costs.csv")
    order, _ = suggest_order(costs)
    assert set(order) <= set(costs["rule"])

    # a rerun does not ingest the same file twice
    assert collect_local(cfg, [wet], crawl="SAMPLE")["files"] == 1
