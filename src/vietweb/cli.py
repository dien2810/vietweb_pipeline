"""Command line: python -m vietweb <command> [options]   (or `vietweb <command>` after pip install -e .)

Commands, in the order they are usually used:
  paths           Download the list of WET files for a crawl snapshot
  collect         Stages 1-2: download N WET files, keep Vietnamese records, store raw Parquet
  collect-local   Same as collect but reads WET files already on disk (no network needed)
  run             Stages 3-9 (with 3b, boilerplate): run the pipeline, write the funnel and processed data
  status          Show how much has been collected and the funnel of the latest run
  peek            Print a few kept / removed documents for manual inspection
  order-filters   RQ4: suggest a quality-rule order based on cost
  sample-labels   Sample documents for manual annotation
  score-labels    Compute precision and Cohen's kappa from an annotated file
  dedup-eval      RQ1: compare shingling units on a subset
  reference       Download WARC files for collected WET files and extract them with trafilatura
  extract-eval    Compare boilerplate removal (stage 3b) with the trafilatura reference
  fw2-urls        RQ3: read the URLs of one snapshot from FineWeb-2 vie_Latn / vie_Latn_removed (needs internet)
  fw2-compare     RQ3: compare our keep/drop decisions with FineWeb-2 by URL
  fw2-pii         RQ3: count personal-data patterns in a sample of FineWeb-2 vie_Latn
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from .config import load_config, resolve


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("urllib3", "requests", "httpx", "httpcore", "huggingface_hub", "fsspec"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # print Vietnamese text correctly on the Windows console
    ap = argparse.ArgumentParser(prog="vietweb", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/pipeline.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("paths"); p.add_argument("--crawl")
    p = sub.add_parser("collect"); p.add_argument("--crawl"); p.add_argument("--n-files", type=int, required=True)
    p = sub.add_parser("collect-local"); p.add_argument("files", nargs="+"); p.add_argument("--crawl", default="LOCAL")
    p = sub.add_parser("run"); p.add_argument("--crawl", action="append", help="only process this crawl (repeatable)")
    p.add_argument("--limit", type=int, help="randomly sample N documents (quick trial runs)")
    sub.add_parser("status")
    p = sub.add_parser("peek"); p.add_argument("--kept", action="store_true"); p.add_argument("--reason")
    p.add_argument("-n", type=int, default=3); p.add_argument("--chars", type=int, default=600)
    sub.add_parser("order-filters")
    p = sub.add_parser("sample-labels"); p.add_argument("--per-reason", type=int, default=150)
    p = sub.add_parser("score-labels"); p.add_argument("csv")
    p = sub.add_parser("dedup-eval"); p.add_argument("--n", type=int, default=2000)
    p.add_argument("--units", default="syllable:5,char:15", help="e.g. syllable:5,word:5,char:15")
    p.add_argument("--processed-dir", help="sample cleaned texts that reached deduplication from this processed "
                   "folder (e.g. outputs/runs/wet_200_final/processed) instead of raw WET text")
    p = sub.add_parser("reference", help="download WARC files for collected WET files and extract them with trafilatura")
    p.add_argument("--n-files", type=int, required=True); p.add_argument("--crawl")
    p.add_argument("--keep-warc", action="store_true", help="keep the downloaded WARC files (about 1 GB each)")
    p = sub.add_parser("extract-eval", help="compare boilerplate removal with the trafilatura reference")
    p.add_argument("--crawl")
    p = sub.add_parser("fw2-urls", help="RQ3: read the URLs of one snapshot from FineWeb-2 (needs internet)")
    p.add_argument("--dump", required=True, help="Common Crawl snapshot, e.g. CC-MAIN-2024-10")
    p.add_argument("--probe", action="store_true", help="read only the file footers and estimate the transfer")
    p.add_argument("--subsets", default="vie_Latn,vie_Latn_removed")
    p.add_argument("--max-files", type=int, help="only the first N files of each subset (trial)")
    p = sub.add_parser("fw2-compare", help="RQ3: compare keep/drop decisions with FineWeb-2 by URL")
    p.add_argument("--dump", required=True)
    p = sub.add_parser("fw2-pii", help="RQ3: personal-data patterns in a sample of FineWeb-2 vie_Latn (needs internet)")
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--files", type=int, default=10, help="spread the sample over this many files")

    args = ap.parse_args(argv)
    _setup_logging(args.verbose)
    cfg = load_config(args.config)

    if args.cmd == "paths":
        from .io import commoncrawl as cc
        crawl = args.crawl or cfg["collect"]["crawl"]
        f = cc.download_wet_paths(crawl, cfg["collect"]["base_url"], resolve(cfg, cfg["paths"]["data_dir"]) / "paths")
        paths = cc.read_wet_paths(f)
        print(f"{crawl}: {len(paths)} WET files. Examples:\n  " + "\n  ".join(paths[:3]))

    elif args.cmd == "collect":
        from .collect import collect
        print(json.dumps(collect(cfg, args.n_files, args.crawl), indent=2))

    elif args.cmd == "collect-local":
        from .collect import collect_local
        print(json.dumps(collect_local(cfg, [Path(f) for f in args.files], args.crawl), indent=2))

    elif args.cmd == "run":
        from .pipeline import run_pipeline
        funnel = run_pipeline(cfg, args.crawl, args.limit)
        print("\n" + funnel[["stage", "docs_in", "removed", "docs_out", "pct_of_input", "seconds", "top_reason"]]
              .to_string(index=False))
        print(f"\nWritten: {resolve(cfg, cfg['paths']['stats_dir'])}/funnel.csv and {resolve(cfg, cfg['paths']['processed_dir'])}/")

    elif args.cmd == "status":
        from .io.storage import Manifest
        raw = resolve(cfg, cfg["paths"]["raw_dir"])
        for d in sorted(raw.glob("*")) if raw.exists() else []:
            if d.is_dir():
                s = Manifest(d / "_manifest.jsonl").summary()
                ratio = 100 * s["records_vie"] / s["records_total"] if s["records_total"] else 0
                print(f"{d.name}: {s['files']} files, {s['records_vie']} Vietnamese records / "
                      f"{s['records_total']} ({ratio:.2f}%), {s['bytes'] / 1e9:.2f} GB downloaded")
        f = resolve(cfg, cfg["paths"]["stats_dir"]) / "funnel.csv"
        if f.exists():
            print("\nFunnel of the latest run:\n" + pd.read_csv(f).to_string(index=False))

    elif args.cmd == "peek":
        proc = resolve(cfg, cfg["paths"]["processed_dir"])
        sub_dir = proc / ("kept" if args.kept else "dropped")
        df = pd.concat([pd.read_parquet(p) for p in sorted(sub_dir.glob("*.parquet"))], ignore_index=True)
        if args.reason and not args.kept:
            df = df[df["drop_reason"] == args.reason]
        for _, r in df.sample(n=min(args.n, len(df)), random_state=0).iterrows():
            tag = "KEPT" if args.kept else f"DROP {r['drop_stage']}/{r['drop_reason']}"
            print(f"\n=== {tag} | {r['url']}\n{r['text'][:args.chars]}")

    elif args.cmd == "order-filters":
        from .ordering import report
        print(report(str(resolve(cfg, cfg["paths"]["stats_dir"]) / "filter_costs.csv")))

    elif args.cmd == "sample-labels":
        from .eval.labeling import sample_for_labeling
        out = resolve(cfg, cfg["paths"]["eval_dir"]) / "labels_to_annotate.csv"
        df = sample_for_labeling(resolve(cfg, cfg["paths"]["processed_dir"]), out, args.per_reason, cfg.get("seed", 42))
        print(f"Wrote {len(df)} rows to {out}")

    elif args.cmd == "score-labels":
        from .eval.labeling import score_labels
        print(score_labels(Path(args.csv)).to_string(index=False))

    elif args.cmd == "dedup-eval":
        from .eval.dedup_eval import compare_units
        from .io.storage import read_raw
        if args.processed_dir:
            d = Path(args.processed_dir)
            kept = [pd.read_parquet(f, columns=["text"]) for f in sorted((d / "kept").glob("*.parquet"))]
            dropped = [pd.read_parquet(f, columns=["text", "drop_stage"]) for f in sorted((d / "dropped").glob("*.parquet"))]
            # documents as they entered deduplication; those emptied by the line stage are left out
            dropped = [x[x["drop_stage"].isin(["dedup_exact", "dedup_near", "quality"])] for x in dropped]
            df = pd.concat(kept + dropped, ignore_index=True)
            df = df[df["text"].str.len() >= 200]
        else:
            df = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]))
        texts = df.sample(n=min(args.n, len(df)), random_state=cfg.get("seed", 42))["text"].tolist()
        units = [(u.split(":")[0], int(u.split(":")[1])) for u in args.units.split(",")]
        res = compare_units(texts, units)
        out = resolve(cfg, cfg["paths"]["eval_dir"]) / "dedup_units.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        res.to_csv(out, index=False)
        print(res.to_string(index=False))

    elif args.cmd == "reference":
        from .reference import build_reference
        print(json.dumps(build_reference(cfg, args.n_files, args.crawl, args.keep_warc), indent=2))

    elif args.cmd == "extract-eval":
        from .eval.extraction_eval import evaluate
        print(evaluate(cfg, args.crawl))
        print(f"Written: {resolve(cfg, cfg['paths']['eval_dir'])}/extraction_*.csv and extraction_eval.md")

    elif args.cmd == "fw2-urls":
        from .eval.fineweb2 import fw2_urls
        print(json.dumps(fw2_urls(cfg, args.dump, args.subsets.split(","), args.probe, args.max_files), indent=2))

    elif args.cmd == "fw2-compare":
        from .eval.fineweb2 import compare
        print(compare(cfg, args.dump))

    elif args.cmd == "fw2-pii":
        from .eval.fineweb2 import fw2_pii
        print(fw2_pii(cfg, args.n, n_files=args.files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
