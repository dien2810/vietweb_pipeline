"""Sample documents near the stage 7 thresholds for manual labelling, then score the labels (RQ1).

For each rule bound (for example gopher_word_count, min 50), two groups are built from
outputs/stats/quality_stats.parquet (run the pipeline with quality.save_stats: true):
- fail: documents that violate this bound and pass every other rule, so this threshold alone decides
  whether they are dropped;
- pass: documents that pass every rule.
From each group, the `band` documents closest to the threshold are taken and `n` of them are sampled.
The labelling file hides the rule, the group and the metric value, so the labels are blind; they are kept
in a separate key file.

Files are split in collection order (data/raw/<crawl>/_manifest.jsonl): the first --dev-files files form
the development split, the others the test split. Choose thresholds on dev, then check them once on test.

Run from the repository root:
  python scripts/calibration_sample.py                        # -> outputs/eval/calibration_dev.csv (+ _key.csv)
  # fill the label column: 1 = poor quality (should be dropped), 0 = acceptable
  python scripts/calibration_sample.py --score outputs/eval/calibration_dev.csv
  python scripts/calibration_sample.py --split test           # after changing configs/vie_thresholds.yaml
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vietweb.config import load_config, load_yaml, resolve  # noqa: E402
from vietweb.stages.s07_quality import RULES  # noqa: E402

# Rule bounds that alone decide the most documents in wet_200 (see LUAT_LOC.md, section 7). Left out:
# gopher_mean_word_length:max (no document above 10) and gopher_dup_lines (18 documents in the dev split).
DEFAULT_BOUNDS = ["gopher_word_count:min", "fineweb_dup_line_chars:max", "gopher_mean_word_length:min",
                  "gopher_top_4gram:max", "gopher_stopwords:min"]
TEXT_CHARS = 2000


def bound_thresholds(t: dict, bound: str, value: float | None = None) -> dict:
    """Thresholds of one rule with only `bound` active (the other bound can never trigger)."""
    t = dict(t)
    if value is not None:
        t[bound] = value
    if bound == "min" and "max" in t:
        t["max"] = math.inf
    if bound == "max" and "min" in t:
        t["min"] = -math.inf
    return t


def load_metrics(cfg: dict) -> tuple[pd.DataFrame, dict, list[str]]:
    stats = resolve(cfg, cfg["paths"]["stats_dir"])
    q = pd.read_parquet(stats / "quality_stats.parquet")
    thresholds = load_yaml(resolve(cfg, cfg["quality"]["thresholds_file"]))
    rules = [r for r in cfg["quality"]["rule_order"]
             if thresholds.get(r, {}).get("enabled", True) and f"q_{r}" in q.columns]
    for r in rules:
        decide = RULES[r][1]
        q[f"fail_{r}"] = [decide(v, thresholds.get(r, {})) for v in q[f"q_{r}"]]
    q["n_fail"] = q[[f"fail_{r}" for r in rules]].sum(axis=1)
    return q, thresholds, rules


def split_of_docs(cfg: dict) -> pd.Series:
    """doc_id -> 'dev' or 'test', by the position of its raw file in the collection manifest."""
    crawl = cfg["collect"]["crawl"]
    raw_dir = resolve(cfg, cfg["paths"]["raw_dir"]) / crawl
    rows = [json.loads(line) for line in open(raw_dir / "_manifest.jsonl", encoding="utf-8")]
    parts = []
    for i, r in enumerate(rows):
        ids = pd.read_parquet(raw_dir / r["parquet"], columns=["doc_id"])["doc_id"]
        parts.append(pd.Series(i, index=ids.values))
    return pd.concat(parts)


def groups(q: pd.DataFrame, thresholds: dict, rule: str, bound: str) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    t = thresholds[rule]
    thr = t[bound]
    decide = RULES[rule][1]
    fails_bound = np.array([decide(v, bound_thresholds(t, bound)) for v in q[f"q_{rule}"]])
    only_this = fails_bound & (q["n_fail"] == 1) & q[f"fail_{rule}"]
    dist = (q[f"q_{rule}"] - thr).abs()
    fail = q[only_this].assign(dist=dist[only_this]).sort_values("dist")
    passing = q[q["n_fail"] == 0].assign(dist=dist[q["n_fail"] == 0]).sort_values("dist")
    return fail, passing, thr


def texts(cfg: dict, ids: set[str]) -> pd.DataFrame:
    proc = resolve(cfg, cfg["paths"]["processed_dir"])
    out = []
    for f in sorted((proc / "kept").glob("*.parquet")) + sorted((proc / "dropped").glob("*.parquet")):
        d = pd.read_parquet(f, columns=["doc_id", "url", "text"])
        out.append(d[d["doc_id"].isin(ids)])
    return pd.concat(out).drop_duplicates("doc_id").set_index("doc_id")


def sample(cfg: dict, split: str, n: int, band: int, dev_files: int, bounds: list[str], seed: int) -> None:
    q, thresholds, rules = load_metrics(cfg)
    file_idx = split_of_docs(cfg)
    q["file_idx"] = q["doc_id"].map(file_idx)
    q = q[(q["file_idx"] < dev_files) if split == "dev" else (q["file_idx"] >= dev_files)]
    rng = np.random.default_rng(seed)
    key = []
    for item in bounds:
        rule, bound = item.split(":")
        if rule not in rules or bound not in thresholds.get(rule, {}):
            print(f"skip {item}: rule disabled or bound not in vie_thresholds.yaml")
            continue
        fail, passing, thr = groups(q, thresholds, rule, bound)
        if fail.empty:
            print(f"skip {item}: no document is dropped by this bound alone")
            continue
        for side, g in (("fail", fail), ("pass", passing)):
            near = g.head(band)
            pick = near.iloc[rng.permutation(len(near))[:n]]
            key += [{"doc_id": d, "rule": rule, "bound": bound, "threshold": thr, "side": side, "value": v}
                    for d, v in zip(pick["doc_id"], pick[f"q_{rule}"])]
        print(f"{rule} {bound} {thr}: {len(fail)} documents dropped by this bound alone, "
              f"sampled {min(n, len(fail))} of the {min(band, len(fail))} closest + "
              f"{min(n, len(passing))} kept documents")
    key = pd.DataFrame(key)
    docs = key.drop_duplicates("doc_id")[["doc_id"]].sample(frac=1, random_state=seed).reset_index(drop=True)
    docs["id"] = [f"{split}{i + 1:04d}" for i in range(len(docs))]
    key = key.merge(docs, on="doc_id")
    t = texts(cfg, set(docs["doc_id"]))
    sheet = docs.assign(url=docs["doc_id"].map(t["url"]),
                        text=docs["doc_id"].map(t["text"]).str.slice(0, TEXT_CHARS),
                        label="", note="")[["id", "url", "text", "label", "note"]]
    out = resolve(cfg, cfg["paths"]["eval_dir"])
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"calibration_{split}.csv"
    if path.exists() and pd.read_csv(path, encoding="utf-8-sig")["label"].notna().any():
        sys.exit(f"{path} already has labels; rename it first so that they are not overwritten")
    sheet.to_csv(path, index=False, encoding="utf-8-sig")
    key[["id", "doc_id", "rule", "bound", "threshold", "side", "value"]].to_csv(
        out / f"calibration_{split}_key.csv", index=False, encoding="utf-8-sig")
    print(f"\n{len(sheet)} documents to label -> {path}\nKey (do not open while labelling) -> "
          f"{out / f'calibration_{split}_key.csv'}")


def score(cfg: dict, labels_path: str) -> None:
    labels = pd.read_csv(labels_path, encoding="utf-8-sig")
    key = pd.read_csv(str(labels_path).replace(".csv", "_key.csv"), encoding="utf-8-sig")
    df = key.merge(labels[["id", "label"]], on="id")
    df = df[pd.to_numeric(df["label"], errors="coerce").isin([0, 1])].astype({"label": int})
    print(f"Labelled: {df['id'].nunique()} of {labels['id'].nunique()} documents\n")
    q, thresholds, _ = load_metrics(cfg)
    for (rule, bound), g in df.groupby(["rule", "bound"], sort=False):
        thr = g["threshold"].iloc[0]
        decide = RULES[rule][1]
        others_pass = q["n_fail"] - q[f"fail_{rule}"] == 0       # this rule decides for these documents
        f, p = g[g["side"] == "fail"], g[g["side"] == "pass"]
        print(f"## {rule}, {bound} = {thr}")
        print(f"   dropped side: {len(f)} labelled, share poor = {f['label'].mean():.2f}  (precision of dropping near the threshold)")
        print(f"   kept side:    {len(p)} labelled, share poor = {p['label'].mean():.2f}  (junk kept near the threshold)")
        rows = []
        cands = sorted(set(g["value"].round(4)) | {thr})
        for t in cands:
            th = bound_thresholds(thresholds[rule], bound, t)
            d = np.array([decide(v, th) for v in g["value"]])
            all_d = sum(decide(v, th) for v in q.loc[others_pass, f"q_{rule}"])
            rows.append({"threshold": t, "labelled_dropped": int(d.sum()),
                         "precision": round(g["label"][d].mean(), 2) if d.any() else None,
                         "poor_kept": int(((~d) & (g["label"] == 1)).sum()),
                         "good_dropped": int((d & (g["label"] == 0)).sum()),
                         "docs_dropped_in_run": int(all_d), "current": "<-" if t == thr else ""})
        print(pd.DataFrame(rows).to_string(index=False))
        print()
    print("Precision is measured on the sampled band only; both sides are sampled equally, so read it as a\n"
          "guide near the threshold, not as the precision over the whole data. Check the chosen thresholds\n"
          "once on the test split.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "configs/pipeline.yaml"))
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--n", type=int, default=20, help="documents sampled per side of each threshold")
    ap.add_argument("--band", type=int, default=150, help="sample among this many documents closest to the threshold")
    ap.add_argument("--dev-files", type=int, default=150, help="the first N collected files form the dev split")
    ap.add_argument("--bounds", default=",".join(DEFAULT_BOUNDS), help="rule:min|max, comma separated")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--score", metavar="LABELLED_CSV", help="score a labelled file instead of sampling")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if a.score:
        score(cfg, a.score)
    else:
        sample(cfg, a.split, a.n, a.band, a.dev_files, a.bounds.split(","), a.seed)


if __name__ == "__main__":
    main()
