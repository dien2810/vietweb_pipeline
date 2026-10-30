"""Do Vietnamese benchmark items appear in the cleaned data? (n-gram overlap, as in GPT-3 and Llama 2)

Reads benchmark files (.jsonl, .json, .csv or .parquet; a folder is searched recursively) and takes every
text field of each item (question, choices, context...). An item is flagged when one of its fields shares a
syllable n-gram with a kept document (n = 13 by default; n = 8 is reported too, as a looser check). Text on
both sides goes through the stage-3 normalization, so tone-mark placement and Unicode form do not matter.

VMLU (10,880 questions): download the zip from https://vmlu.ai (Data section) and unzip it, then
    python scripts/benchmark_overlap.py data/benchmarks/vmlu --name VMLU
Writes outputs/eval/benchmark_overlap_<name>.md and benchmark_overlap_<name>_examples.csv (not tracked by Git).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb.config import load_config, resolve  # noqa: E402
from vietweb.text.normalize import normalize_text  # noqa: E402
from vietweb.text.tokenize import syllables  # noqa: E402


def read_items(path: Path) -> list[dict]:
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*")
                                                 if p.suffix.lower() in (".jsonl", ".json", ".csv", ".parquet"))
    items = []
    for f in files:
        if f.suffix.lower() == ".jsonl":
            rows = [json.loads(line) for line in f.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        elif f.suffix.lower() == ".json":
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            rows = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
        elif f.suffix.lower() == ".csv":
            rows = pd.read_csv(f, encoding="utf-8-sig").to_dict("records")
        else:
            rows = pd.read_parquet(f).to_dict("records")
        for i, r in enumerate(rows):
            if isinstance(r, dict):
                items.append({"file": f.name, "item": str(r.get("id", i)), "fields": list(text_fields(r))})
    return items


def text_fields(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in text_fields(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in text_fields(v)]
    return []


def ngrams(toks: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bench", type=Path, help="benchmark file or folder")
    ap.add_argument("--name", default="benchmark")
    ap.add_argument("--processed", default="outputs/runs/wet_200_final/processed")
    ap.add_argument("--n", type=int, nargs="+", default=[13, 8])
    args = ap.parse_args()
    cfg = load_config()
    tone = cfg["normalize"].get("tone_mark_style", "old")

    items = read_items(args.bench)
    if not items:
        raise SystemExit(f"No items found in {args.bench}")
    toks = [[syllables(normalize_text(s, tone_style=tone)) for s in it["fields"]] for it in items]
    kept = pd.concat([pd.read_parquet(f, columns=["doc_id", "url", "text"])
                      for f in sorted(resolve(cfg, args.processed).joinpath("kept").glob("*.parquet"))])

    lines = [f"# {args.name}: overlap with the kept documents of {args.processed}", "",
             f"{len(items)} items from {len({it['file'] for it in items})} file(s); {len(kept)} kept documents.", "",
             "| n | Items long enough to test | Items with a shared n-gram | Share |", "|---:|---:|---:|---:|"]
    examples = []
    for n in args.n:
        index = defaultdict(set)                       # n-gram -> items that contain it
        testable = 0
        for k, fields in enumerate(toks):
            grams = set().union(*(ngrams(f, n) for f in fields)) if fields else set()
            testable += bool(grams)
            for g in grams:
                index[g].add(k)
        hit_items = {}
        for doc_id, url, text in zip(kept["doc_id"], kept["url"], kept["text"]):
            t = syllables(text)
            for i in range(len(t) - n + 1):
                g = tuple(t[i:i + n])
                if g in index:
                    for k in index[g]:
                        hit_items.setdefault(k, (doc_id, url, " ".join(g)))
        lines.append(f"| {n} | {testable} | {len(hit_items)} | {len(hit_items) / max(testable, 1) * 100:.2f}% |")
        examples += [{"n": n, "file": items[k]["file"], "item": items[k]["item"], "doc_id": d, "url": u, "ngram": g}
                     for k, (d, u, g) in hit_items.items()]
    out_dir = resolve(cfg, cfg["paths"]["eval_dir"])
    slug = args.name.lower().replace(" ", "_")
    pd.DataFrame(examples).to_csv(out_dir / f"benchmark_overlap_{slug}_examples.csv", index=False, encoding="utf-8-sig")
    report = "\n".join(lines) + "\n"
    (out_dir / f"benchmark_overlap_{slug}.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
