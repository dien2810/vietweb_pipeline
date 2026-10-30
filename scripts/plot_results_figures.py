"""Figures of the final reports, in Vietnamese and English (report/figures/).

- fig_threshold_labels.pdf / _en.pdf: share of poor pages among pages dropped near the final thresholds,
  dev and test splits, with 95% Wilson intervals.
- fig_dup_scale.pdf / _en.pdf: exact-duplicate rate by number of WET files (nested subsets of the 1,000-file run,
  log scale), and the near-duplicate rate of the full 200- and 1,000-file runs.
- With --column: the same figures sized for one column of the 5-page IEEE papers (report/ieee/), saved as
  fig_threshold_labels_col.pdf, fig_dup_scale_col.pdf and their _en versions.

The numbers are copied from LUAT_LOC.md: section 7.4 (labels near the thresholds) and section 14.6 (duplicate
rate by number of WET files, from scripts/dedup_stats.py on wet_1000). Update them there first.
Run from the repository root: python scripts/plot_results_figures.py [--out ../report/figures] [--column]
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
# Exact duplicates: nested subsets of wet_1000 (mean, sd over 5 repeats). Near duplicates: only the full runs are
# exact (on subsets the representative of a cluster is often missing), so only wet_200_final and wet_1000 are drawn.
FILES = [25, 50, 100, 150, 200, 400, 600, 800, 1000]
EXACT = [0.97, 1.46, 2.12, 2.70, 3.13, 4.44, 5.34, 6.07, 6.65]
EXACT_SD = [0.11, 0.25, 0.13, 0.17, 0.09, 0.09, 0.08, 0.06, 0.0]
NEAR_FILES, NEAR = [200, 1000], [3.36, 6.43]

TEXT = {
    "vi": {"dev": "Tập dev", "test": "Tập test", "rule": "Mức dùng để dời ngưỡng (0,8)",
           "xlab": "Tỉ lệ trang kém trong số trang bị loại gần ngưỡng (khoảng tin cậy Wilson 95%)",
           "xlab_col": "Tỉ lệ trang kém (khoảng tin cậy Wilson 95%)", "rule_col": "Mức 0,8",
           "exact": "Trùng chính xác (tập con)", "near": "Trùng gần đúng (lần chạy đầy đủ)",
           "files": "Số file WET (CC-MAIN-2026-39, thang log)",
           "pct": "% số tài liệu", "suffix": "", "comma": True},
    "en": {"dev": "Dev split", "test": "Test split", "rule": "Cut-off used to move a threshold (0.8)",
           "xlab": "Share of poor pages among pages dropped near the threshold (95% Wilson CI)",
           "xlab_col": "Share of poor pages (95% Wilson CI)", "rule_col": "0.8 cut-off",
           "exact": "Exact duplicates (subsets)", "near": "Near duplicates (full runs)",
           "files": "Number of WET files (CC-MAIN-2026-39, log scale)",
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


def thresholds(out: Path, t: dict, col: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(3.45, 2.9) if col else (6.3, 2.9))
    for i, (vi, en, dev, test) in enumerate(RULES):
        y = len(RULES) - 1 - i
        for (k, n), off, col, lab in ((dev, 0.17, BLUE, t["dev"]), (test, -0.17, ORANGE, t["test"])):
            p, lo, hi = wilson(k, n)
            ax.plot([lo, hi], [y + off] * 2, color=col, lw=2, solid_capstyle="round", alpha=0.45)
            ax.plot(p, y + off, "o", color=col, ms=6, mec="white", mew=1.2, label=lab if i == 0 else None)
            ax.text(1.005, y + off, f"{k}/{n}", va="center", ha="left", fontsize=7, color=INK2)
    ax.axvline(0.8, color=INK2, lw=0.8, ls=(0, (3, 3)), label=t["rule_col"] if col else t["rule"])
    names = [r[0] if t["comma"] else r[1] for r in RULES]
    if col:                                            # rule name and threshold on two lines
        names = [n.replace("  ", "\n") for n in names]
    ax.set_yticks(range(len(RULES)), names[::-1], fontsize=7 if col else None)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, len(RULES) - 0.4)
    ax.set_xlabel(t["xlab_col"] if col else t["xlab"])
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(fmt(t["comma"], ".1f"))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=7,
              handletextpad=0.3, borderaxespad=0.2, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(out / f"fig_threshold_labels{'_col' if col else ''}{t['suffix']}.pdf",
                bbox_inches="tight" if col else None, pad_inches=0.02)
    plt.close(fig)


def dup_scale(out: Path, t: dict, col: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(3.45, 2.2) if col else (4.6, 2.5))
    ax.errorbar(FILES, EXACT, yerr=EXACT_SD, color=BLUE, lw=2, marker="o", ms=5, mec="white", mew=1, capsize=0,
                elinewidth=1, label=t["exact"])
    ax.plot(NEAR_FILES, NEAR, color=ORANGE, lw=1.5, ls=(0, (3, 2)), marker="s", ms=5, mec="white", mew=1,
            label=t["near"])
    ax.set_xscale("log", base=2)
    ax.set_xlabel(t["files"])
    ax.set_ylabel(t["pct"])
    ticks = [25, 50, 100, 200, 400, 1000]
    ax.set_xticks(ticks, [format(x, ",").replace(",", ".") if t["comma"] else format(x, ",") for x in ticks])
    ax.minorticks_off()
    ax.set_xlim(20, 1250)
    ax.set_ylim(0, 8)
    h, lab = ax.get_legend_handles_labels()            # exact duplicates first
    order = [lab.index(t["exact"]), lab.index(t["near"])]
    ax.legend([h[i] for i in order], [lab[i] for i in order], loc="upper left", frameon=False, fontsize=7)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(fmt(t["comma"], "g"))
    fig.tight_layout()
    fig.savefig(out / f"fig_dup_scale{'_col' if col else ''}{t['suffix']}.pdf")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "report" / "figures"))
    ap.add_argument("--column", action="store_true", help="one-column versions for the IEEE papers")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for t in TEXT.values():
        thresholds(out, t, args.column)
        dup_scale(out, t, args.column)
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
