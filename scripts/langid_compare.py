"""Compare the two language identifiers of stage 4: the heuristic (in configs/pipeline.yaml) and GlotLID (used by FineWeb-2).

Both run on the documents that reach stage 4 (raw documents after stages 3 and 3b). Reports how many
documents each keeps at several thresholds, where they disagree, and which languages GlotLID gives to the
documents the heuristic removes. Disagreements go to outputs/eval/langid_examples.csv (not tracked by Git).

First time only (about 1.6 GB):
    pip install fasttext-wheel huggingface_hub
    python scripts/langid_compare.py --download
Then:
    python scripts/langid_compare.py --workers 0
"""
from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb import parallel  # noqa: E402
from vietweb.config import load_config, load_wordlist, resolve  # noqa: E402
from vietweb.io.storage import read_raw  # noqa: E402
from vietweb.stages import s03_normalize, s03b_boilerplate  # noqa: E402
from vietweb.stages.s04_langid import fasttext_predict, heuristic_score  # noqa: E402

GLOTLID_REPO, GLOTLID_FILE = "cis-lmu/glotlid", "model.bin"
THRESHOLDS = (0.3, 0.5, 0.6, 0.7, 0.8, 0.9)


def download(dest: Path) -> Path:
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo_id=GLOTLID_REPO, filename=GLOTLID_FILE, local_dir=str(dest)))


def kappa(a: pd.Series, b: pd.Series) -> float:
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="models/glotlid/model.bin")
    ap.add_argument("--download", action="store_true", help="download the GlotLID model and stop")
    ap.add_argument("--workers", type=int, help="processes for stages 3-3b (default: configuration)")
    ap.add_argument("--threshold", type=float, help="threshold for the comparison (default: langid.threshold)")
    args = ap.parse_args()

    cfg = load_config()
    model_path = resolve(cfg, args.model)
    if args.download:
        print("Downloaded to", download(model_path.parent))
        return
    if args.workers is not None:
        cfg["parallel"] = {**cfg.get("parallel", {}), "workers": args.workers}
    thr = args.threshold if args.threshold is not None else cfg["langid"].get("threshold", 0.6)
    import fasttext  # noqa: E402  (pip install fasttext-wheel)
    model = fasttext.load_model(str(model_path))

    raw = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]), [cfg["collect"]["crawl"]]).drop_duplicates("doc_id")
    df = raw.reset_index(drop=True)
    df["text"] = s03_normalize.run(df, cfg).text
    bp = s03b_boilerplate.run(df, cfg)
    df["text"] = bp.text
    df = df[bp.drop_reason.isna()].copy()
    parallel_cfg = cfg
    stop = frozenset(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
    df["heuristic"] = parallel.pmap(partial(heuristic_score, stopwords=stop), df["text"].tolist(), parallel_cfg)
    parallel.shutdown()

    top_label, top_prob, vie_prob = [], [], []
    for text in df["text"]:
        labels, probs = fasttext_predict(model, text, k=3)
        if not labels:                       # no known n-gram in the text: fastText returns nothing
            labels, probs = ["__label__und"], [0.0]
        top_label.append(labels[0].replace("__label__", ""))
        top_prob.append(float(probs[0]))
        vie_prob.append(next((float(p) for lab, p in zip(labels, probs) if lab == "__label__vie_Latn"), 0.0))
    df["glotlid_top"], df["glotlid_top_prob"], df["glotlid_vie"] = top_label, top_prob, vie_prob

    n = len(df)
    lines = [f"# Language identification at stage 4: heuristic vs GlotLID ({cfg['collect']['crawl']})", "",
             f"{n} documents reach stage 4 (after stages 3 and 3b).", "",
             "| Threshold | Kept by heuristic | Kept by GlotLID (P(vie_Latn)) |", "|---:|---:|---:|"]
    for t in THRESHOLDS:
        lines.append(f"| {t} | {int((df.heuristic >= t).sum())} | {int((df.glotlid_vie >= t).sum())} |")
    h, g = df.heuristic >= thr, df.glotlid_vie >= thr
    lines += ["", f"At threshold {thr}:", "",
              f"- Both keep: {int((h & g).sum())}; both remove: {int((~h & ~g).sum())}",
              f"- Heuristic keeps, GlotLID removes: {int((h & ~g).sum())}",
              f"- Heuristic removes, GlotLID keeps: {int((~h & g).sum())}",
              f"- Agreement {float((h == g).mean()):.4f}; Cohen's kappa {kappa(h, g):.3f}", "",
              "GlotLID top label of the documents the heuristic removes:", ""]
    lines += [f"- {lab}: {cnt}" for lab, cnt in df.loc[~h, "glotlid_top"].value_counts().head(12).items()]
    lines += ["", "GlotLID top label of the documents the heuristic keeps but GlotLID removes:", ""]
    lines += [f"- {lab}: {cnt}" for lab, cnt in df.loc[h & ~g, "glotlid_top"].value_counts().head(12).items()]

    out_dir = resolve(cfg, "outputs/eval")
    dis = df[h != g].copy()
    dis["side"] = ["heuristic keeps" if x else "GlotLID keeps" for x in h[h != g]]
    dis["excerpt"] = dis["text"].str.slice(0, 300)
    dis[["side", "doc_id", "url", "cld2_langs", "heuristic", "glotlid_top", "glotlid_top_prob", "glotlid_vie",
         "excerpt"]].to_csv(out_dir / "langid_examples.csv", index=False, encoding="utf-8-sig")
    df[["doc_id", "heuristic", "glotlid_top", "glotlid_top_prob", "glotlid_vie"]].to_csv(
        out_dir / "langid_scores.csv", index=False)
    report = "\n".join(lines) + "\n"
    (out_dir / "langid_compare.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
