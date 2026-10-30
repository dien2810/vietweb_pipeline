"""How many Vietnamese pages in TCVN3 / VNI does the CLD2 pre-filter of stage 1 lose?

Stage 1 keeps only records that CLD2 labels "vie". Text in a legacy encoding read as Windows-1252 does not
look like Vietnamese, so CLD2 probably labels it as something else and the record never reaches stage 3.
This script downloads WET files, reads EVERY record (any language, at least 200 characters), and counts
the records that stage 3 would convert from TCVN3 or VNI.

    python scripts/legacy_scan.py --n-files 5

Writes outputs/eval/legacy_scan.md and outputs/eval/legacy_scan_examples.csv (not tracked by Git).
WET files are deleted after reading (--keep to keep them). About 1-2 minutes per file with 8 processes.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from functools import partial
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb import parallel  # noqa: E402
from vietweb.config import load_config, load_wordlist, resolve  # noqa: E402
from vietweb.io import commoncrawl as cc  # noqa: E402
from vietweb.text.legacy import convert_legacy, foreign_share  # noqa: E402
from vietweb.text.normalize import normalize_text  # noqa: E402


def scan(text: str, stopwords: frozenset) -> tuple[str | None, float]:
    """(encoding stage 3 would convert from, or None; highest foreign-code share)."""
    share = max(foreign_share(text, "tcvn3"), foreign_share(text, "vni"))
    if share < 0.02:                      # cheap test first: convert_legacy needs at least this share
        return None, share
    _, enc = convert_legacy(normalize_text(text, tone_style="none"), stopwords)
    return enc, share


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crawl")
    ap.add_argument("--n-files", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7, help="file selection seed (7: not the files of `collect`)")
    ap.add_argument("--workers", type=int, default=0, help="processes; 0 = one per CPU core")
    ap.add_argument("--keep", action="store_true", help="keep the downloaded WET files")
    args = ap.parse_args()

    cfg = load_config()
    cfg["parallel"] = {**cfg.get("parallel", {}), "workers": args.workers}
    ccfg = cfg["collect"]
    crawl = args.crawl or ccfg["crawl"]
    http = {k: v for k, v in ccfg.get("http", {}).items() if k in ("timeout", "max_retries", "backoff_seconds")}
    stop = frozenset(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
    paths = cc.read_wet_paths(cc.download_wet_paths(crawl, ccfg["base_url"],
                                                    resolve(cfg, cfg["paths"]["data_dir"]) / "paths", **http))
    chosen = cc.select_paths(paths, args.n_files, "random", args.seed)
    tmp = resolve(cfg, cfg["paths"]["tmp_dir"])

    total, by_lang, hits = 0, Counter(), []
    for i, wet_path in enumerate(chosen, 1):
        t0 = time.time()
        local = tmp / Path(wet_path).name
        cc.http_get_to_file(f"{ccfg['base_url']}/{wet_path}", local, **http)
        recs = list(cc.iter_wet_records(local, language=None, min_chars=ccfg.get("min_chars", 200), snapshot=crawl))
        res = parallel.pmap(partial(scan, stopwords=stop), [r["text"] for r in recs], cfg)
        for r, (enc, share) in zip(recs, res):
            total += 1
            if enc is not None:
                langs = r.get("cld2_langs") or ""
                by_lang[langs.split(",")[0] or "(none)"] += 1
                hits.append({"file": Path(wet_path).name, "url": r["url"], "cld2_langs": langs, "encoding": enc,
                             "foreign_share": round(share, 4), "kept_by_prefilter": "vie" in langs.split(","),
                             "text": r["text"][:300]})
        print(f"[{i}/{len(chosen)}] {Path(wet_path).name}: {len(recs)} records, "
              f"{sum(h['file'] == Path(wet_path).name for h in hits)} legacy ({time.time() - t0:.0f}s)")
        if not args.keep:
            local.unlink(missing_ok=True)
    parallel.shutdown()

    df = pd.DataFrame(hits)
    lost = int((~df["kept_by_prefilter"]).sum()) if len(df) else 0
    lines = [f"# Legacy-encoded Vietnamese pages in {len(chosen)} WET files of {crawl}", "",
             f"- Records read (any language, >= {ccfg.get('min_chars', 200)} characters): {total}",
             f"- Records stage 3 would convert: {len(df)} "
             f"(TCVN3 {int((df.encoding == 'tcvn3').sum()) if len(df) else 0}, "
             f"VNI {int((df.encoding == 'vni').sum()) if len(df) else 0})",
             f"- Of these, lost by the CLD2 \"vie\" pre-filter: {lost}", "",
             "Primary CLD2 label of the converted records:", ""]
    lines += [f"- {lang}: {n}" for lang, n in by_lang.most_common()]
    out_dir = resolve(cfg, "outputs/eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "legacy_scan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if len(df):
        df.to_csv(out_dir / "legacy_scan_examples.csv", index=False, encoding="utf-8-sig")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
