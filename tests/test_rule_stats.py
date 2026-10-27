"""Test scripts/rule_stats.py on the statistics produced by a pipeline run on the synthetic WET file."""
import copy
import importlib.util
from pathlib import Path

import pandas as pd

from vietweb.collect import collect_local
from vietweb.config import load_config
from vietweb.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rule_stats_tables(tmp_path):
    cfg = copy.deepcopy(load_config("configs/pipeline.yaml"))
    for k in ("data_dir", "raw_dir", "processed_dir", "stats_dir", "eval_dir", "tmp_dir"):
        cfg["paths"][k] = str(tmp_path / k)
    wet = _load_script("make_sample_wet").make(tmp_path / "sample.warc.wet.gz")
    collect_local(cfg, [wet], crawl="SAMPLE")
    run_pipeline(cfg)

    rs = _load_script("rule_stats")
    stats = tmp_path / "stats_dir"
    funnel = rs.funnel_table(stats)
    assert "| quality |" in funnel and "| langid |" in funnel

    _, fail, order, _ = rs.quality_frames(stats, cfg)
    # the recomputed violations must agree with the pass counts measured by the pipeline
    costs = pd.read_csv(stats / "filter_costs.csv").set_index("rule")
    for r in order:
        assert int(fail[r].sum()) == costs.loc[r, "evaluated"] - costs.loc[r, "passed"]

    table = rs.quality_table(stats, cfg)
    assert table.count("\n| ") == len(order) + 1   # header row + one row per rule
    assert rs.condition("fineweb_line_punct", {"min": 0.12}) == "<= 0.12"
    assert rs.condition("gopher_word_count", {"min": 50, "max": 100000}) == "< 50 or > 100000"
