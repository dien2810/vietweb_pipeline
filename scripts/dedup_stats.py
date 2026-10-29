"""RQ2: how much Vietnamese web text is duplicated (exact, near-duplicate, line level), from a finished run.

Reads a run directory (outputs/runs/<name>, with funnel.csv and processed/) and the raw collection manifest
of the crawl. Reports:
- the funnel of the three deduplication stages;
- exact duplicate groups (text_sha1) and near-duplicate pairs (near_dup_cluster): size, and whether the
  copies come from the same domain or from different domains;
- the line-level stage (same-domain and cross-site repeated lines);
- how the duplicate rates grow with the number of WET files, by recounting the duplicates inside random
  nested subsets of the files. Exact duplicates are recounted exactly from text_sha1; a near duplicate is
  counted when the document it matched is also in the subset (a slight undercount).

Run from the repository root:
  python scripts/dedup_stats.py --run outputs/runs/wet_200_final --crawl CC-MAIN-2026-39
Output: outputs/eval/dedup_stats_<run name>.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vietweb.config import load_config, resolve  # noqa: E402

DEDUP_STAGES = ["dedup_exact", "dedup_near", "dedup_line"]
LATER = ["dedup_exact", "dedup_near", "dedup_line", "quality"]   # stages at or after exact deduplication
COLS = ["doc_id", "domain", "text_sha1", "near_dup_cluster"]


def load_docs(run: Path) -> pd.DataFrame:
    kept = pd.concat(pd.read_parquet(f, columns=COLS) for f in sorted((run / "processed" / "kept").glob("*.parquet")))
    dropped = pd.concat(pd.read_parquet(f, columns=COLS + ["drop_stage", "drop_reason"])
                        for f in sorted((run / "processed" / "dropped").glob("*.parquet")))
    dropped = dropped[dropped["drop_stage"].isin(LATER)]
    return pd.concat([kept.assign(drop_stage=None, drop_reason=None), dropped], ignore_index=True)


def file_index(cfg: dict, crawl: str) -> pd.Series:
    raw = resolve(cfg, cfg["paths"]["raw_dir"]) / crawl
    rows = [json.loads(line) for line in open(raw / "_manifest.jsonl", encoding="utf-8") if line.strip()]
    parts = [pd.Series(i, index=pd.read_parquet(raw / r["parquet"], columns=["doc_id"])["doc_id"].values)
             for i, r in enumerate(rows)]
    return pd.concat(parts)


def scale_curve(docs: pd.DataFrame, n_files: int, sizes: list[int], repeats: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    near = docs[docs["drop_reason"] == "near_duplicate"]
    rows = []
    for r in range(repeats):
        order = rng.permutation(n_files)
        for k in sizes:
            files = set(order[:k])
            sub = docs[docs["file_idx"].isin(files)]
            exact = len(sub) - sub["text_sha1"].nunique()
            ids = set(sub["doc_id"])
            nd = near[near["file_idx"].isin(files) & near["near_dup_cluster"].isin(ids)]
            rows.append({"repeat": r, "files": k, "docs": len(sub), "exact": exact, "near": len(nd)})
    df = pd.DataFrame(rows)
    df["exact_pct"] = 100 * df["exact"] / df["docs"]
    df["near_pct"] = 100 * df["near"] / (df["docs"] - df["exact"])
    return (df.groupby("files")[["docs", "exact_pct", "near_pct"]]
            .agg(["mean", "std"]).round(2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=str(ROOT / "outputs/runs/wet_200_final"))
    ap.add_argument("--crawl", default=None)
    ap.add_argument("--config", default=str(ROOT / "configs/pipeline.yaml"))
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    cfg = load_config(a.config)
    crawl = a.crawl or cfg["collect"]["crawl"]
    run = Path(a.run)

    funnel = pd.read_csv(run / "funnel.csv").set_index("stage")
    docs = load_docs(run)
    idx = file_index(cfg, crawl)
    docs["file_idx"] = docs["doc_id"].map(idx)
    docs = docs[docs["file_idx"].notna()]
    n_files = int(idx.max()) + 1
    dom = docs.set_index("doc_id")["domain"]

    # exact groups
    grp = docs.groupby("text_sha1")
    sizes = grp.size()
    dup_groups = sizes[sizes > 1]
    ndom = grp["domain"].nunique()[dup_groups.index]
    exact_dropped = docs[docs["drop_reason"] == "exact_duplicate"]
    exact_same = int(exact_dropped["text_sha1"].map(lambda h: ndom.get(h, 1) == 1).sum())

    # near-duplicate pairs (document, the kept document it matched)
    near = docs[docs["drop_reason"] == "near_duplicate"]
    rep_dom = near["near_dup_cluster"].map(dom)
    near_same = int((rep_dom == near["domain"]).sum())
    near_known = int(rep_dom.notna().sum())
    csize = near["near_dup_cluster"].value_counts() + 1

    line = json.loads(funnel.loc["dedup_line", "details"])
    entering = docs.groupby("domain").size()

    sizes_list = [s for s in (25, 50, 100, 150) if s < n_files] + [n_files]
    curve = scale_curve(docs, n_files, sizes_list, a.repeats, cfg.get("seed", 42))

    def pct(x, n):
        return f"{x} ({100 * x / n:.1f}%)" if n else str(x)

    n_in = int(funnel.loc["dedup_exact", "docs_in"])
    lines = [f"# Duplication in {run.name} ({crawl}, {n_files} WET files)", "",
             "## Deduplication stages", "",
             "| stage | documents in | removed | % |", "|---|---:|---:|---:|"]
    for st in DEDUP_STAGES:
        lines.append(f"| {st} | {int(funnel.loc[st, 'docs_in'])} | {int(funnel.loc[st, 'removed'])} | "
                     f"{100 * funnel.loc[st, 'removed'] / funnel.loc[st, 'docs_in']:.2f} |")
    lines += ["", "## Exact duplicates", "",
              f"- Documents entering: {n_in}; groups with 2+ identical texts: {len(dup_groups)}; "
              f"removed copies: {len(exact_dropped)}",
              f"- Group size: median {int(dup_groups.median())}, max {int(dup_groups.max())}; groups of 2: "
              f"{pct(int((dup_groups == 2).sum()), len(dup_groups))}",
              f"- Removed copies whose whole group is on one domain: {pct(exact_same, len(exact_dropped))}", "",
              "## Near duplicates (MinHash-LSH, 5-syllable shingles, 14 bands x 8 rows)", "",
              f"- Removed: {len(near)}; matched document on the same domain: {pct(near_same, near_known)}",
              f"- Cluster size (kept document + its near duplicates): median {int(csize.median())}, max {int(csize.max())}",
              "", "## Line level", "",
              f"- Lines removed, repeated in >= 3 documents of the same domain: {line.get('removed_lines_same_domain')}",
              f"- Lines removed, found on >= {line.get('min_domains')} domains: {line.get('removed_lines_cross_site')} "
              f"({line.get('cross_site_distinct_lines')} distinct lines, in {line.get('docs_with_cross_site_lines')} documents)",
              f"- Documents left empty: {int(funnel.loc['dedup_line', 'removed'])}", "",
              "## Domains (documents entering exact deduplication)", "",
              f"- Domains: {len(entering)}; with a single document: {pct(int((entering == 1).sum()), len(entering))}; "
              f"documents on domains with 10+ documents: {pct(int(entering[entering >= 10].sum()), int(entering.sum()))}",
              "", "## Duplicate rate by number of WET files", "",
              f"Random nested subsets of the {n_files} files, {a.repeats} repeats (mean and standard deviation). "
              "exact_pct: share of documents that are exact copies; near_pct: share of the remaining documents "
              "removed as near duplicates.", "", "```", curve.to_string(), "```", ""]
    md = "\n".join(lines)
    out = resolve(cfg, cfg["paths"]["eval_dir"]) / f"dedup_stats_{run.name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md + f"\nWritten: {out}")


if __name__ == "__main__":
    main()
