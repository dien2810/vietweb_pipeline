"""Generate report figures from outputs/stats/ into report/figures/ (or the folder given by --out).

Available:
- fig_funnel.pdf        Figure 3: document funnel through the stages
- fig_calibration.pdf   Figure 4: distribution of mean word length (for calibrating the Gopher threshold)
- fig_rule_hist.pdf     Distribution of every quality metric (internal use when choosing thresholds)
TODO: Figure 1 (data profile), Figure 5 (duplicate clusters), Figure 6 (speed-up by number of cores).

Run: python scripts/plot_report_figures.py --out ../report/figures
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def fig_funnel(stats: Path, out: Path) -> None:
    f = pd.read_csv(stats / "funnel.csv")
    f = f[f["stage"] != "export"]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh(f["stage"][::-1], f["docs_out"][::-1], color="#4C72B0")
    for y, (v, pct) in enumerate(zip(f["docs_out"][::-1], f["pct_of_input"][::-1])):
        ax.text(v, y, f" {v:,} ({pct:.1f}%)", va="center", fontsize=8)
    ax.set_xlabel("Documents retained")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig_funnel.pdf")
    plt.close(fig)


def fig_calibration(stats: Path, out: Path) -> None:
    q = pd.read_parquet(stats / "quality_stats.parquet")
    col = "q_gopher_mean_word_length"
    if col not in q:
        print("Skipping fig_calibration: run the pipeline with quality.save_stats: true")
        return
    with open(ROOT / "configs/vie_thresholds.yaml", encoding="utf-8") as fh:
        thr = yaml.safe_load(fh)["gopher_mean_word_length"]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.hist(q[col].dropna(), bins=60, color="#55A868")
    for x in (3, 10):
        ax.axvline(x, color="red", ls="--", lw=1)
    ax.axvspan(thr["min"], thr["max"], color="orange", alpha=0.15, label="current threshold")
    ax.set_xlabel("Mean word length (characters)")
    ax.set_ylabel("Documents")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_calibration.pdf")
    plt.close(fig)


def fig_rule_hist(stats: Path, out: Path) -> None:
    q = pd.read_parquet(stats / "quality_stats.parquet")
    cols = [c for c in q.columns if c.startswith("q_")]
    if not cols:
        return
    n = len(cols)
    ncol = 4
    fig, axes = plt.subplots(math.ceil(n / ncol), ncol, figsize=(12, 2.4 * math.ceil(n / ncol)))
    for ax, c in zip(axes.flat, cols):
        ax.hist(q[c].dropna(), bins=40, color="#8172B2")
        ax.set_title(c[2:], fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "fig_rule_hist.pdf")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default=str(ROOT / "outputs/stats"))
    ap.add_argument("--out", default=str(ROOT / "outputs/figures"))
    a = ap.parse_args()
    stats, out = Path(a.stats), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_funnel(stats, out)
    if (stats / "quality_stats.parquet").exists():
        fig_calibration(stats, out)
        fig_rule_hist(stats, out)
    print(f"Figures written to {out}")


if __name__ == "__main__":
    main()
