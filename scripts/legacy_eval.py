"""Evaluate the TCVN3 / VNI conversion of stage 3.

1. Synthetic test: clean documents from a finished run are written in TCVN3 and in VNI (as they look when
   such a page is read as Windows-1252), then passed through stage 3. Reports how often the right encoding
   is chosen and how much of the text comes back exactly.
2. Real data: stage 3 with conversion on every raw document of the crawl. Reports how many documents are
   converted, and writes them to outputs/eval/legacy_examples.csv for reading (not tracked by Git).

    python scripts/legacy_eval.py --processed outputs/runs/wet_200_final/processed --n 2000
"""
from __future__ import annotations

import argparse
import sys
from difflib import SequenceMatcher
from functools import partial
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb import parallel  # noqa: E402
from vietweb.config import load_config, load_wordlist, resolve  # noqa: E402
from vietweb.io.storage import read_raw  # noqa: E402
from vietweb.stages.s03_normalize import normalize_doc  # noqa: E402
from vietweb.text.legacy import (TCVN3_TO_UNICODE, UNICODE_TO_TCVN3, UNICODE_TO_VNI,  # noqa: E402
                                 VNI_TO_UNICODE, encode_tcvn3, encode_vni)
from vietweb.text.normalize import legacy_encoding_score, normalize_text  # noqa: E402


VN_LETTERS = set(UNICODE_TO_TCVN3) | set(UNICODE_TO_VNI)
TCVN3_CODES = set(TCVN3_TO_UNICODE)
VNI_CODES = {ch for key in VNI_TO_UNICODE for ch in key if not ch.isascii()}


def char_accuracy(a: str, b: str) -> float:
    if len(a) == len(b):
        return sum(x == y for x, y in zip(a, b)) / max(len(a), 1)
    return SequenceMatcher(None, a[:2000], b[:2000]).ratio()


def representable(text: str, codes: set[str]) -> str:
    """Replace symbols that a legacy page could not contain as such (they are letter codes there) with "?"."""
    return "".join("?" if ch in codes and ch not in VN_LETTERS else ch for ch in text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--processed", default="outputs/runs/wet_200_final/processed")
    ap.add_argument("--n", type=int, default=2000, help="documents for the synthetic test")
    ap.add_argument("--skip-real", action="store_true", help="only run the synthetic test")
    ap.add_argument("--workers", type=int, help="processes (default: parallel.workers in the configuration)")
    args = ap.parse_args()

    cfg = load_config()
    if args.workers is not None:
        cfg["parallel"] = {**cfg.get("parallel", {}), "workers": args.workers}
    c = cfg["normalize"]
    stop = frozenset(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
    conv = partial(normalize_doc, fix_mojibake=c.get("fix_mojibake", True), form=c.get("unicode_form", "NFC"),
                   tone_style=c.get("tone_mark_style", "old"), stopwords=stop)
    lines = ["# TCVN3 / VNI conversion (stage 3)", ""]

    kept = pd.concat([pd.read_parquet(f, columns=["doc_id", "text"])
                      for f in sorted(resolve(cfg, args.processed).joinpath("kept").glob("*.parquet"))])
    sample = kept.sample(n=min(args.n, len(kept)), random_state=cfg.get("seed", 42))["text"].tolist()
    lines += [f"## Synthetic test: {len(sample)} clean documents written in each encoding", "",
              "| Encoding | Detected correctly | Exact text | Exact, ignoring case | Character accuracy (mean) |",
              "|---|---:|---:|---:|---:|"]
    for enc, encode, codes in (("tcvn3", encode_tcvn3, TCVN3_CODES), ("vni", encode_vni, VNI_CODES)):
        originals = [representable(t, codes) for t in sample]
        expected = [normalize_text(t, fix_mojibake=False, tone_style=c.get("tone_mark_style", "old"))
                    for t in originals]
        out = parallel.pmap(conv, [encode(t) for t in originals], cfg)
        det = sum(e == enc for _, e in out)
        exact = sum(t == x for (t, _), x in zip(out, expected))
        exact_ci = sum(t.lower() == x.lower() for (t, _), x in zip(out, expected))
        acc = sum(char_accuracy(t, x) for (t, _), x in zip(out, expected)) / len(sample)
        n = len(sample)
        lines.append(f"| {enc} | {det}/{n} ({100 * det / n:.1f}%) | {exact}/{n} ({100 * exact / n:.1f}%) | "
                     f"{exact_ci}/{n} ({100 * exact_ci / n:.1f}%) | {acc:.4f} |")
    out = parallel.pmap(conv, sample, cfg)
    fp = sum(e is not None for _, e in out)
    lines += ["", f"Clean documents converted by mistake: {fp}/{len(sample)}.", ""]

    if not args.skip_real:
        raw = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]), [cfg["collect"]["crawl"]])
        res = parallel.pmap(conv, raw["text"].tolist(), cfg)
        raw["converted"] = [e for _, e in res]
        raw["new_text"] = [t for t, _ in res]
        raw["legacy_score"] = raw["new_text"].map(legacy_encoding_score)
        flagged = raw["legacy_score"] >= c.get("legacy_encoding_threshold", 0.02)
        hit = raw[raw["converted"].notna()]
        lines += [f"## Real data: {len(raw)} raw documents of {cfg['collect']['crawl']}", "",
                  f"- Converted: {len(hit)} (TCVN3 {int((hit.converted == 'tcvn3').sum())}, "
                  f"VNI {int((hit.converted == 'vni').sum())})",
                  f"- Flagged by the marker score (>= {c.get('legacy_encoding_threshold', 0.02)}): "
                  f"{int(flagged.sum())}, of which converted: {int((flagged & raw.converted.notna()).sum())}", ""]
        ex = raw[raw["converted"].notna() | flagged].copy()
        ex["before"] = ex["text"].str.slice(0, 300)
        ex["after"] = ex["new_text"].str.slice(0, 300)
        out_csv = resolve(cfg, "outputs/eval/legacy_examples.csv")
        ex[["doc_id", "url", "cld2_langs", "legacy_score", "converted", "before", "after"]].to_csv(
            out_csv, index=False, encoding="utf-8-sig")
        lines.append(f"Converted and flagged documents: {out_csv.name} (not tracked by Git).")
    parallel.shutdown()
    report = "\n".join(lines) + "\n"
    out_md = resolve(cfg, "outputs/eval/legacy_eval.md")
    out_md.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
