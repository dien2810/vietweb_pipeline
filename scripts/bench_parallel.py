"""Measure the speed of stage 3 (normalization) and stage 3b (boilerplate) with 1, 2, 4, ... processes.

Also times ftfy on the whole text (the earlier version of stage 3) against ftfy on the lines it could change.
Writes outputs/eval/parallel_bench.csv and prints a table. Run from the repository root:

    python scripts/bench_parallel.py --n 10000 --workers 1 2 4 8

The documents are a random sample (seed 42) of data/raw for the crawl in configs/pipeline.yaml.
Close other heavy programs while it runs: the numbers depend on the machine and its load.
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from functools import partial
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb import parallel  # noqa: E402
from vietweb.config import load_config, resolve  # noqa: E402
from vietweb.io.storage import read_raw  # noqa: E402
from vietweb.stages.s03b_boilerplate import clean_text, load_params_and_stopwords  # noqa: E402
from vietweb.text import normalize as N  # noqa: E402


def normalize_whole_ftfy(text: str) -> str:
    """The earlier stage 3 (runs up to wet_200_final): ftfy on the whole text, then the other steps."""
    if N.ftfy is not None:
        text = N.ftfy.fix_text(text, normalization="NFC")
    return N.normalize_text(text, fix_mojibake=False)


def timed(func, texts, cfg) -> tuple[list, float]:
    t0 = time.perf_counter()
    out = parallel.pmap(func, texts, cfg)
    return out, time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=10000, help="number of documents")
    ap.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--out", default="outputs/eval/parallel_bench.csv")
    args = ap.parse_args()

    cfg = load_config()
    raw = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]), [cfg["collect"]["crawl"]])
    texts = raw.sample(n=min(args.n, len(raw)), random_state=cfg.get("seed", 42))["text"].tolist()
    print(f"{len(texts)} documents, {sum(map(len, texts)) / 1e6:.1f} M characters; "
          f"{os.cpu_count()} logical CPUs; {platform.platform()}")

    one = {"parallel": {"workers": 1}}
    rows = []
    ref_norm, secs = timed(normalize_whole_ftfy, texts, one)
    rows.append({"stage": "normalize (ftfy on whole text)", "workers": 1, "seconds": secs})
    p, stop = load_params_and_stopwords(cfg)
    norm = partial(N.normalize_text)
    bp = partial(clean_text, p=p, stopwords=stop)
    ref_bp = None
    for w in args.workers:
        c = {"parallel": {"workers": w, "min_items": 1}}
        parallel.pmap(len, ["warm up"] * (2 * w), c)  # start the processes before timing
        out_norm, s_norm = timed(norm, texts, c)
        out_bp, s_bp = timed(bp, out_norm, c)
        parallel.shutdown()
        if out_norm != ref_norm:
            raise SystemExit(f"normalize output differs from the reference with {w} workers")
        ref_bp = ref_bp or out_bp
        if out_bp != ref_bp:
            raise SystemExit(f"boilerplate output differs with {w} workers")
        rows.append({"stage": "normalize (ftfy by line)", "workers": w, "seconds": s_norm})
        rows.append({"stage": "boilerplate", "workers": w, "seconds": s_bp})

    df = pd.DataFrame(rows)
    df["ms_per_doc"] = (1000 * df["seconds"] / len(texts)).round(3)
    df["docs_per_s"] = (len(texts) / df["seconds"]).round(1)
    base = df[df.workers == 1].set_index("stage")["seconds"]
    base_norm = base["normalize (ftfy on whole text)"]
    df["speedup_vs_1_process"] = [round(base.get(s, base_norm) / sec, 2) for s, sec in zip(df.stage, df.seconds)]
    df["speedup_vs_before"] = [round(base_norm / sec, 2) if s.startswith("normalize") else None
                               for s, sec in zip(df.stage, df.seconds)]
    df["seconds"] = df["seconds"].round(2)
    out = resolve(cfg, args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print(f"Outputs identical for every number of workers. Written to {out}")


if __name__ == "__main__":
    main()
