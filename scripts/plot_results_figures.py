"""Figures of the final reports, in Vietnamese and English (report/figures/).

- fig_threshold_labels.pdf / _en.pdf: share of poor pages among pages dropped near the final thresholds,
  dev and test splits, with 95% Wilson intervals.
- fig_dup_scale.pdf / _en.pdf: exact and near-duplicate rate by number of WET files.

The numbers are copied from LUAT_LOC.md: section 7.4 (labels near the thresholds) and section 13 (duplicate
rate by number of WET files, from scripts/dedup_stats.py). Update them there first.
Run from the repository root: python scripts/plot_results_figures.py [--out ../report/figures]
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

BLUE, ORANGE, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})

# (rule label vi, rule label en, (poor, labelled) dev, (poor, labelled) test)
RULES = [("gopher_stopwords  (< 4)", "gopher_stopwords  (< 4)", (34, 38), (14, 15)),
         ("gopher_word_count  (< 53)", "gopher_word_count  (< 53)", (31, 39), (13, 15)),
         ("gopher_top_4gram  (> 0,16)", "gopher_top_4gram  (> 0.16)", (17, 20), (13, 15)),
         ("gopher_mean_word_length  (< 3)", "gopher_mean_word_length  (< 3)", (15, 20), (11, 15)),
         ("fineweb_dup_line_chars  (≥ 0,23; tắt)", "fineweb_dup_line_chars  (≥ 0.23; disabled)", (28, 50), (5, 15))]
FILES = [25, 50, 100, 150, 200]
EXACT, EXACT_SD = [0.85, 1.31, 2.16, 2.75, 3.23], [0.21, 0.21, 0.16, 0.07, 0.0]
NEAR, NEAR_SD = [0.71, 1.09, 1.78, 2.52, 3.36], [0.06, 0.07, 0.14, 0.04, 0.0]

TEXT = {
    "vi": {"dev": "Tập dev", "test": "Tập test", "rule": "Mức dùng để dời ngưỡng (0,8)",
           "xlab": "Tỉ lệ trang kém trong số trang bị loại gần ngưỡng (khoảng tin cậy Wilson 95%)",
           "exact": "Trùng chính xác", "near": "Trùng gần đúng", "files": "Số file WET (CC-MAIN-2026-39)",
           "pct": "% số tài liệu", "suffix": "", "comma": True},
    "en": {"dev": "Dev split", "test": "Test split", "rule": "Cut-off used to move a threshold (0.8)",
           "xlab": "Share of poor pages among pages dropped near the threshold (95% Wilson CI)",
           "exact": "Exact duplicates", "near": "Near duplicates", "files": "Number of WET files (CC-MAIN-2026-39)",
           "pct": "% of documents", "suffix": "_en", "comma": False},
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def fmt(comma: bool, spec: str):
    return FuncFormatter(lambda v, _: format(v, spec).replace(".", ",") if comma else format(v, spec))


def thresholds(out: Path, t: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    for i, (vi, en, dev, test) in enumerate(RULES):
        y = len(RULES) - 1 - i
        for (k, n), off, col, lab in ((dev, 0.17, BLUE, t["dev"]), (test, -0.17, ORANGE, t["test"])):
            p, lo, hi = wilson(k, n)
            ax.plot([lo, hi], [y + off] * 2, color=col, lw=2, solid_capstyle="round", alpha=0.45)
            ax.plot(p, y + off, "o", color=col, ms=6, mec="white", mew=1.2, label=lab if i == 0 else None)
            ax.text(1.005, y + off, f"{k}/{n}", va="center", ha="left", fontsize=7, color=INK2)
    ax.axvline(0.8, color=INK2, lw=0.8, ls=(0, (3, 3)), label=t["rule"])
    names = [r[0] if t["comma"] else r[1] for r in RULES]
    ax.set_yticks(range(len(RULES)), names[::-1])
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, len(RULES) - 0.4)
    ax.set_xlabel(t["xlab"])
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(fmt(t["comma"], ".1f"))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=7,
              handletextpad=0.3, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(out / f"fig_threshold_labels{t['suffix']}.pdf")
    plt.close(fig)


def dup_scale(out: Path, t: dict) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 2.3))
    for ys, sd, col, lab in ((EXACT, EXACT_SD, BLUE, t["exact"]), (NEAR, NEAR_SD, ORANGE, t["near"])):
        ax.errorbar(FILES, ys, yerr=sd, color=col, lw=2, marker="o", ms=5, mec="white", mew=1, capsize=0,
                    elinewidth=1, label=lab)
    ax.set_xlabel(t["files"])
    ax.set_ylabel(t["pct"])
    ax.set_xticks(FILES)
    ax.set_xlim(15, 210)
    ax.set_ylim(0, 4)
    ax.legend(loc="upper left", frameon=False, fontsize=7)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(fmt(t["comma"], "g"))
    fig.tight_layout()
    fig.savefig(out / f"fig_dup_scale{t['suffix']}.pdf")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "report" / "figures"))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for t in TEXT.values():
        thresholds(out, t)
        dup_scale(out, t)
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
