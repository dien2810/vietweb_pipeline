"""Print per-rule statistics of the last pipeline run as Markdown tables (used to update LUAT_LOC.md).

Reads outputs/stats/ (funnel.csv, filter_costs.csv, quality_stats.parquet, run_info.json) and the
current thresholds. Quality metrics exist only when the run used `quality.save_stats: true`.

Columns of the quality table:
- failed:   documents that violate the rule (every rule is evaluated for every document)
- dropped:  documents whose drop_reason is this rule (the first violated rule in rule_order)
- sole:     documents that violate only this rule (they would be kept if the rule were removed)
- p10 / p50 / p90: distribution of the metric

Note: the decision is recomputed from metric values rounded to 5 decimals, so a document lying
exactly on a threshold may be counted differently from the pipeline run.

Run from the repository root:
    python scripts/rule_stats.py
    python scripts/rule_stats.py --out outputs/stats/rule_stats.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from vietweb.config import load_config, load_yaml, resolve
from vietweb.stages.s07_quality import RULES

ROOT = Path(__file__).resolve().parents[1]


def condition(rule: str, th: dict) -> str:
    """Human-readable removal condition, matching the decisions in stages/s07_quality.py."""
    if rule.startswith("c4_"):
        return "present"
    if rule == "fineweb_line_punct":
        return f"<= {th['min']}"
    if rule.startswith("fineweb_"):
        return f">= {th['max']}"
    parts = []
    if "min" in th:
        parts.append(f"< {th['min']}")
    if "max" in th:
        parts.append(f"> {th['max']}")
    return " or ".join(parts)


def _pct(n: int, total: int) -> str:
    return f"{n} ({100 * n / total:.1f}%)" if total else str(n)


def _num(x: float) -> str:
    return f"{x:.0f}" if abs(x) >= 1000 else f"{x:.3g}"


def run_header(stats_dir: Path) -> str:
    p = stats_dir / "run_info.json"
    if not p.exists():
        return ""
    info = json.loads(p.read_text(encoding="utf-8"))
    return (f"Run finished {info.get('finished_utc')} (UTC): {info.get('n_input')} documents in, "
            f"{info.get('n_kept')} kept; langid={info.get('langid_backend')}, "
            f"quality unit={info.get('quality_unit')}, near-dup unit={info.get('near_dup_unit')}.")


def funnel_table(stats_dir: Path) -> str:
    f = pd.read_csv(stats_dir / "funnel.csv")
    f = f[~f["stage"].isin(["input", "export"])]
    rows = ["| Stage | In | Removed | Kept (% of input) | Top reason | Seconds |",
            "|---|---:|---:|---:|---|---:|"]
    for r in f.itertuples(index=False):
        top = r.top_reason if isinstance(r.top_reason, str) else ""
        rows.append(f"| {r.stage} | {r.docs_in} | {r.removed} | {r.pct_of_input}% | {top} | {r.seconds:.1f} |")
    return "\n".join(rows)


def quality_frames(stats_dir: Path, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    """Return (metric values, violation flags, rule order, thresholds) for the quality stage."""
    q = pd.read_parquet(stats_dir / "quality_stats.parquet").set_index("doc_id")
    thresholds = load_yaml(resolve(cfg, cfg["quality"]["thresholds_file"]))
    order = [r for r in cfg["quality"]["rule_order"] if f"q_{r}" in q.columns]
    values = q[[f"q_{r}" for r in order]]
    if values.isna().any().any():
        raise SystemExit("quality_stats.parquet has missing metrics. Rerun with quality.save_stats: true.")
    values.columns = order
    fail = pd.DataFrame({r: [bool(RULES[r][1](v, thresholds.get(r, {}))) for v in values[r]] for r in order},
                        index=values.index)
    return values, fail, order, thresholds


def quality_table(stats_dir: Path, cfg: dict) -> str:
    values, fail, order, thresholds = quality_frames(stats_dir, cfg)
    n = len(fail)
    n_fail = fail.sum(axis=1)
    any_fail = n_fail > 0
    first = fail[any_fail].idxmax(axis=1).value_counts()   # idxmax returns the first True column in rule order
    sole = fail[n_fail == 1].sum()
    costs_path = stats_dir / "filter_costs.csv"
    us_per_doc = (pd.read_csv(costs_path).set_index("rule")["sec_per_doc"] * 1e6) if costs_path.exists() else pd.Series(dtype=float)

    rows = [f"Documents evaluated: {n}; violating at least one rule: {_pct(int(any_fail.sum()), n)}.", "",
            "| # | Rule | Drop if | Failed | Dropped | Sole | p10 / p50 / p90 | us/doc |",
            "|---:|---|---|---:|---:|---:|---|---:|"]
    for i, r in enumerate(order, 1):
        v = values[r]
        dist = f"{_num(v.quantile(0.1))} / {_num(v.median())} / {_num(v.quantile(0.9))}"
        cost = f"{us_per_doc[r]:.0f}" if r in us_per_doc.index else ""
        rows.append(f"| {i} | {r} | {condition(r, thresholds.get(r, {}))} | {_pct(int(fail[r].sum()), n)} "
                    f"| {int(first.get(r, 0))} | {int(sole[r])} | {dist} | {cost} |")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("--stats-dir", default=None, help="defaults to paths.stats_dir in the configuration")
    ap.add_argument("--out", default=None, help="also write the Markdown to this file")
    args = ap.parse_args()

    cfg = load_config(args.config)
    stats_dir = Path(args.stats_dir) if args.stats_dir else resolve(cfg, cfg["paths"]["stats_dir"])
    parts = [run_header(stats_dir), "", "## Funnel", "", funnel_table(stats_dir)]
    if (stats_dir / "quality_stats.parquet").exists():
        parts += ["", "## Quality rules", "", quality_table(stats_dir, cfg)]
    md = "\n".join(parts) + "\n"
    print(md)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
