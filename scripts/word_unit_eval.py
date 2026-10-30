"""RQ1, counting unit: syllables (split on spaces) or words (underthesea word segmentation) in stage 7.

On the documents that reach stage 7 of a finished run, and on the hand-labelled pages, compares:
- the cost of tokenization and the number and length of tokens;
- the share of documents each token-based rule removes, with the current thresholds;
- the documents whose keep/remove decision changes, and how the labelled pages are decided.
The thresholds were calibrated on syllables, so this measures the effect of the unit, not a calibrated
word-based filter. Writes outputs/eval/word_unit_eval.md and word_unit_scores.csv.

    pip install underthesea
    python scripts/word_unit_eval.py --workers 0             # all documents (slow: word segmentation)
    python scripts/word_unit_eval.py --n 3000 --workers 0    # a random sample
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb import parallel  # noqa: E402
from vietweb.config import load_config, load_wordlist, load_yaml, resolve  # noqa: E402
from vietweb.eval.labels import load_labels, load_stage7_input  # noqa: E402
from vietweb.stages.s07_quality import RULES, Doc  # noqa: E402
from vietweb.text.tokenize import syllables, words  # noqa: E402

TOKEN_RULES = ["gopher_word_count", "gopher_mean_word_length", "gopher_symbol_ratio", "gopher_stopwords",
               "gopher_top_2gram", "gopher_top_3gram", "gopher_top_4gram"]

def decide(text: str, toks: list[str], order: list[str], thresholds: dict, stop: set) -> tuple[str | None, dict]:
    doc = Doc(text=text, toks=toks, lines=[ln for ln in text.split("\n") if ln.strip()], stopwords=stop)
    first, fails = None, {}
    for rule in order:
        metric, dec = RULES[rule]
        fail = dec(metric(doc), thresholds.get(rule, {}))
        if rule in TOKEN_RULES:
            fails[rule] = fail
        if fail and first is None:
            first = rule
    return first, fails


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--processed", default="outputs/runs/wet_200_final/processed")
    ap.add_argument("--n", type=int, help="random sample of the stage-7 documents (default: all)")
    ap.add_argument("--workers", type=int, help="processes for word segmentation (default: configuration)")
    args = ap.parse_args()

    cfg = load_config()
    if args.workers is not None:
        cfg["parallel"] = {**cfg.get("parallel", {}), "workers": args.workers}
    c = cfg["quality"]
    thresholds = load_yaml(resolve(cfg, c["thresholds_file"]))
    stop = set(load_wordlist(resolve(cfg, c["stopwords_file"])))
    order = [r for r in c.get("rule_order", list(RULES)) if thresholds.get(r, {}).get("enabled", True)]

    docs = load_stage7_input(resolve(cfg, args.processed))
    labels = load_labels(resolve(cfg, cfg["paths"]["eval_dir"]))
    pop = docs.sample(n=min(args.n, len(docs)), random_state=cfg.get("seed", 42)) if args.n else docs
    work = pd.concat([pop, docs[docs.doc_id.isin(labels.doc_id)]]).drop_duplicates("doc_id").reset_index(drop=True)
    texts = work["text"].tolist()

    t0 = time.perf_counter()
    syl = [syllables(t) for t in texts]
    t_syl = time.perf_counter() - t0
    t0 = time.perf_counter()
    wrd = parallel.pmap(words, texts, cfg)
    t_wrd = time.perf_counter() - t0
    parallel.shutdown()
    workers = min(parallel.n_workers(cfg), len(texts))

    # Words are longer than syllables, so the same word-count threshold is stricter with words. To separate the
    # effect of the unit from that of a stricter threshold, also decide with syllables and the minimum word count
    # scaled by the number of syllables per word.
    in_pop_ids = set(pop["doc_id"])
    ratio = (sum(len(s) for d, s in zip(work["doc_id"], syl) if d in in_pop_ids)
             / max(sum(len(w) for d, w in zip(work["doc_id"], wrd) if d in in_pop_ids), 1))
    scaled = {**thresholds, "gopher_word_count": {**thresholds.get("gopher_word_count", {}),
              "min": round(thresholds.get("gopher_word_count", {}).get("min", 50) * ratio)}}
    rows = []
    for doc_id, text, s, w in zip(work["doc_id"], texts, syl, wrd):
        ds, fs = decide(text, s, order, thresholds, stop)
        dw, fw = decide(text, w, order, thresholds, stop)
        dx, _ = decide(text, s, order, scaled, stop)
        rows.append({"doc_id": doc_id, "n_syllables": len(s), "n_words": len(w),
                     "decision_syllable": ds or "keep", "decision_word": dw or "keep",
                     "decision_syllable_scaled": dx or "keep",
                     **{f"fail_syl_{r}": fs[r] for r in fs}, **{f"fail_word_{r}": fw[r] for r in fw}})
    res = pd.DataFrame(rows)
    in_pop = res["doc_id"].isin(pop["doc_id"])
    p = res[in_pop]
    chars = work["text"].str.len().sum()

    L = [f"# Counting unit in stage 7: syllables vs words ({len(p)} stage-7 documents of {args.processed})", "",
         "## Cost and tokens", "",
         f"- Syllables: {1000 * t_syl / len(texts):.2f} ms per document (one process)",
         f"- Words (underthesea): {1000 * t_wrd / len(texts):.2f} ms per document with {workers} process(es), "
         f"about {1000 * t_wrd * workers / len(texts):.0f} ms of CPU; {chars / 1e6:.1f} M characters in all",
         f"- Median tokens per document: {int(p.n_syllables.median())} syllables, {int(p.n_words.median())} words; "
         f"syllables per word {p.n_syllables.sum() / max(p.n_words.sum(), 1):.2f}", "",
         "## Documents each token-based rule would remove (current thresholds)", "",
         "| Rule | Syllables | Words |", "|---|---:|---:|"]
    for r in TOKEN_RULES:
        if f"fail_syl_{r}" in p:
            L.append(f"| {r} | {p[f'fail_syl_{r}'].mean() * 100:.1f}% | {p[f'fail_word_{r}'].mean() * 100:.1f}% |")
    ks, kw = p.decision_syllable == "keep", p.decision_word == "keep"
    kx = p.decision_syllable_scaled == "keep"
    L += ["", f"Kept by stage 7: {int(ks.sum())} with syllables, {int(kw.sum())} with words; "
          f"kept only with syllables {int((ks & ~kw).sum())}, kept only with words {int((~ks & kw).sum())}. "
          f"With syllables and the word-count minimum scaled to {scaled['gopher_word_count']['min']}: "
          f"{int(kx.sum())} kept, {int((kx != kw).sum())} decisions differ from words.", ""]
    lab = labels.merge(res, on="doc_id")
    if len(lab):
        L += [f"## Hand-labelled pages ({len(lab)}; label 1 = poor, sampled near the syllable thresholds)", "",
              "| Unit | Poor pages removed | Acceptable pages removed | Decision matches label |", "|---|---:|---:|---:|"]
        smin = scaled["gopher_word_count"]["min"]
        for unit, col in (("syllables", "decision_syllable"), ("words", "decision_word"),
                          (f"syllables, word count >= {smin}", "decision_syllable_scaled")):
            drop = lab[col] != "keep"
            poor, ok = lab.label == 1, lab.label == 0
            L.append(f"| {unit} | {int((drop & poor).sum())}/{int(poor.sum())} | {int((drop & ok).sum())}/{int(ok.sum())} | "
                     f"{float((drop == poor).mean()):.3f} |")
    out_dir = resolve(cfg, cfg["paths"]["eval_dir"])
    res.to_csv(out_dir / "word_unit_scores.csv", index=False)
    report = "\n".join(L) + "\n"
    (out_dir / "word_unit_eval.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
