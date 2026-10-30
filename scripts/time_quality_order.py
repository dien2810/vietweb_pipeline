"""RQ4: time stage 7 (quality rules) in production mode under the current and the cost-based rule order.

The cost-based order sorts rules by (1 - p) / c (Hellerstein and Stonebraker, 1993), where p is the pass
rate of a rule under the thresholds in configs/vie_thresholds.yaml (from outputs/stats/quality_stats.parquet)
and c its mean time per document (outputs/stats/filter_costs.csv). Each order runs with save_stats: false,
so a document stops at its first violated rule; the two orders alternate for --repeats rounds and the
median time is reported. The set of documents passing must be the same under both orders.

Input: the documents that entered stage 7 in the last run (data/processed, kept + dropped at quality).
Run from the repository root:  python scripts/time_quality_order.py --repeats 3
"""
from __future__ import annotations

import argparse
import copy
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vietweb.config import load_config, load_yaml, resolve  # noqa: E402
from vietweb.ordering import expected_cost, suggest_order  # noqa: E402
from vietweb.stages import s07_quality  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "configs/pipeline.yaml"))
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--sample", type=int, help="time a random sample of N documents instead of all")
    a = ap.parse_args()
    cfg = load_config(a.config)

    proc = resolve(cfg, cfg["paths"]["processed_dir"])
    kept = pd.concat(pd.read_parquet(f, columns=["doc_id", "text"]) for f in (proc / "kept").glob("*.parquet"))
    dropped = pd.concat(pd.read_parquet(f, columns=["doc_id", "text", "drop_stage"])
                        for f in (proc / "dropped").glob("*.parquet"))
    docs = pd.concat([kept, dropped[dropped["drop_stage"] == "quality"][["doc_id", "text"]]], ignore_index=True)
    if a.sample:
        docs = docs.sample(n=min(a.sample, len(docs)), random_state=cfg.get("seed", 42)).reset_index(drop=True)

    stats = resolve(cfg, cfg["paths"]["stats_dir"])
    q = pd.read_parquet(stats / "quality_stats.parquet")
    th = load_yaml(resolve(cfg, cfg["quality"]["thresholds_file"]))
    costs = pd.read_csv(stats / "filter_costs.csv")
    costs = costs[[th.get(r, {}).get("enabled", True) and f"q_{r}" in q.columns for r in costs["rule"]]]
    costs["pass_rate"] = [sum(not s07_quality.RULES[r][1](v, th.get(r, {})) for v in q[f"q_{r}"]) / len(q)
                          for r in costs["rule"]]
    suggested, _ = suggest_order(costs)
    current = [r for r in cfg["quality"]["rule_order"] if r in suggested]
    p, c = dict(zip(costs["rule"], costs["pass_rate"])), dict(zip(costs["rule"], costs["sec_per_doc"]))

    orders = {"current": current, "cost-based": suggested}
    times = {k: [] for k in orders}
    passing = {}
    for _ in range(a.repeats):
        for name, order in orders.items():
            run_cfg = copy.deepcopy(cfg)
            run_cfg["quality"]["save_stats"] = False
            run_cfg["quality"]["rule_order"] = order
            run_cfg["parallel"] = {"workers": 1}    # one process, so the rule costs are not affected by other processes
            t0 = time.perf_counter()
            res = s07_quality.run(docs[["text"]], run_cfg)
            times[name].append(time.perf_counter() - t0)
            passing[name] = frozenset(docs["doc_id"][res.drop_reason.isna().values])

    print(f"Documents: {len(docs)}; repeats: {a.repeats}; thresholds: {cfg['quality']['thresholds_file']}")
    for name, order in orders.items():
        med = statistics.median(times[name])
        print(f"{name:11s} median {med:7.2f} s  ({1000 * med / len(docs):.3f} ms/doc; "
              f"expected rule cost {1000 * expected_cost(order, p, c):.3f} ms/doc)  runs: "
              + ", ".join(f"{t:.2f}" for t in times[name]))
    print(f"Speed-up of stage 7: {statistics.median(times['current']) / statistics.median(times['cost-based']):.2f}x")
    print(f"Same documents pass under both orders: {passing['current'] == passing['cost-based']}")
    print("Cost-based order: " + ", ".join(suggested))


if __name__ == "__main__":
    main()
