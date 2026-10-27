"""RQ4: suggest a quality-rule order based on cost and removal rate.

For independent filters, the expected cost is minimized by sorting them by (1 - p_i) / c_i in
decreasing order, where p_i is the share of documents passing rule i and c_i its mean time per document.
Inputs come from outputs/stats/filter_costs.csv (run the pipeline with quality.save_stats: true).
"""
from __future__ import annotations

import pandas as pd


def expected_cost(order: list[str], p: dict[str, float], c: dict[str, float]) -> float:
    total, reach = 0.0, 1.0
    for r in order:
        total += reach * c[r]
        reach *= p[r]
    return total


def suggest_order(costs: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    df = costs.dropna(subset=["pass_rate", "sec_per_doc"]).copy()
    df["rank"] = (1 - df["pass_rate"]) / df["sec_per_doc"].clip(lower=1e-9)
    df = df.sort_values("rank", ascending=False)
    return df["rule"].tolist(), df


def report(costs_csv: str) -> str:
    costs = pd.read_csv(costs_csv)
    order, table = suggest_order(costs)
    p = dict(zip(costs["rule"], costs["pass_rate"]))
    c = dict(zip(costs["rule"], costs["sec_per_doc"]))
    original = costs["rule"].tolist()
    e0, e1 = expected_cost(original, p, c), expected_cost(order, p, c)
    lines = [
        table[["rule", "pass_rate", "sec_per_doc", "rank"]].to_string(index=False),
        "",
        f"Expected cost per document: current order {e0 * 1e6:.1f} us, suggested order {e1 * 1e6:.1f} us "
        f"(theoretical speed-up x{e0 / max(e1, 1e-12):.2f})",
        "",
        "Paste into configs/pipeline.yaml -> quality.rule_order:",
        *[f"    - {r}" for r in order],
        "",
        "Then rerun with quality.save_stats: false to measure the actual runtime (Table 8 of the report).",
    ]
    return "\n".join(lines)
