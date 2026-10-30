"""Model-based quality signals for the junk that form-based rules miss (RQ1).

Both signals learn from Vietnamese Wikipedia as reference text and are scored on the hand-labelled pages:
- classifier: fastText, Wikipedia vs documents that reach stage 7 (the idea of GPT-3's quality filter);
  score = probability that a page is "web" rather than "wiki";
- perplexity: syllable trigram language model with interpolated absolute discounting, trained on Wikipedia
  (a light stand-in for the KenLM 5-gram of CCNet, which is hard to build on Windows).
Wikipedia articles first go through the stage-3b line rules, so both sides contain only sentence lines and the
models cannot just learn that web pages have menus.

Evaluation on the labelled pages (label 1 = poor): AUC for telling poor from acceptable pages, overall and
separately for pages the rules keep ("pass") and remove ("fail"); and the precision of removing the same
number of pages as the rules. Writes outputs/eval/quality_model.md, quality_model_scores.csv and
quality_model_examples.csv (kept pages with the worst scores; not tracked by Git).

    pip install fasttext-wheel huggingface_hub
    python scripts/quality_model.py --download        # Wikipedia files until there are enough long articles
    python scripts/quality_model.py

Most Vietnamese Wikipedia articles are bot-made species stubs of one or two sentences (in the file
train-00002-of-00004, 96% are under 200 characters after the stage-3b line rules). Training on them teaches the
models what a stub looks like, so only articles with at least --min-chars characters after the line rules are
used, and --download fetches files one by one until it has 3 x --n-train of them (or runs out of files).
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vietweb.config import load_config, resolve  # noqa: E402
from vietweb.eval.labels import load_labels, load_stage7_input  # noqa: E402
from vietweb.stages.s03b_boilerplate import clean_text, load_params_and_stopwords  # noqa: E402
from vietweb.stages.s04_langid import fasttext_predict  # noqa: E402
from vietweb.text.tokenize import syllables  # noqa: E402

WIKI_REPO = "wikimedia/wikipedia"
WIKI_FILES = [f"20231101.vi/train-0000{i}-of-00004.parquet" for i in (0, 1, 3, 2)]
CHUNK = 300  # syllables per training example, on both sides, so that length is not a cue


class TrigramLM:
    """Syllable trigram model with interpolated absolute discounting (D = 0.75) and an <unk> token."""

    def __init__(self, sentences: list[list[str]], min_count: int = 2, d: float = 0.75):
        uni = Counter(t for s in sentences for t in s)
        self.vocab = {t for t, c in uni.items() if c >= min_count}
        self.d = d
        self.c1, self.c2, self.c3 = Counter(), Counter(), Counter()
        self.ctx1, self.ctx2 = Counter(), Counter()          # counts of each history
        self.n1p1, self.n1p2 = Counter(), Counter()          # distinct continuations of each history
        for s in sentences:
            toks = ["<s>", "<s>"] + [self._map(t) for t in s] + ["</s>"]
            for i in range(2, len(toks)):
                u, v, w = toks[i - 2], toks[i - 1], toks[i]
                self.c1[w] += 1
                if self.c2[(v, w)] == 0:
                    self.n1p1[v] += 1
                self.c2[(v, w)] += 1
                self.ctx1[v] += 1
                if self.c3[(u, v, w)] == 0:
                    self.n1p2[(u, v)] += 1
                self.c3[(u, v, w)] += 1
                self.ctx2[(u, v)] += 1
        self.total = sum(self.c1.values())
        self.v_size = len(self.vocab) + 2

    def _map(self, t: str) -> str:
        return t if t in self.vocab else "<unk>"

    def prob(self, u: str, v: str, w: str) -> float:
        p1 = (self.c1[w] + 1) / (self.total + self.v_size)                       # add-one unigram
        h1 = self.ctx1[v]
        p2 = p1 if not h1 else (max(self.c2[(v, w)] - self.d, 0) / h1 + self.d * self.n1p1[v] / h1 * p1)
        h2 = self.ctx2[(u, v)]
        return p2 if not h2 else (max(self.c3[(u, v, w)] - self.d, 0) / h2 + self.d * self.n1p2[(u, v)] / h2 * p2)

    def perplexity(self, text: str, max_tokens: int = 2000) -> float:
        logp, n = 0.0, 0
        for line in text.split("\n"):
            toks = ["<s>", "<s>"] + [self._map(t) for t in syllables(line)] + ["</s>"]
            for i in range(2, len(toks)):
                logp += math.log2(self.prob(toks[i - 2], toks[i - 1], toks[i]))
                n += 1
            if n >= max_tokens:
                break
        return 2 ** (-logp / n) if n else float("inf")


def auc(scores: list[float], labels: list[int]) -> float:
    """Probability that a random poor page (1) scores higher than a random acceptable page (0); ties count 1/2."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    ranked = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + j + 1) / 2                      # ranks are 1-based
        rank_sum += avg * sum(lab for _, lab in ranked[i:j])
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def chunk(text: str) -> str:
    return " ".join(syllables(text)[:CHUNK])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--processed", default="outputs/runs/wet_200_final/processed")
    ap.add_argument("--wiki", default="data/wikipedia", help="folder with Wikipedia Parquet files (searched recursively)")
    ap.add_argument("--download", action="store_true", help="download Wikipedia files and stop")
    ap.add_argument("--n-train", type=int, default=15000, help="training examples per class")
    ap.add_argument("--min-chars", type=int, default=1000,
                    help="minimum length of a Wikipedia article after the stage-3b line rules")
    args = ap.parse_args()
    cfg = load_config()
    wiki_dir = resolve(cfg, args.wiki)
    p3b, stop = load_params_and_stopwords(cfg)

    def long_articles(path: Path) -> list[str]:
        texts = pd.read_parquet(path, columns=["text"])["text"]
        texts = texts[texts.str.len() >= args.min_chars]             # cheap pre-filter on the raw length
        return [w for w in (clean_text(t, p3b, stop) for t in texts) if len(w) >= args.min_chars]

    if args.download:
        from huggingface_hub import hf_hub_download
        have = 0
        for name in WIKI_FILES:
            p = Path(hf_hub_download(repo_id=WIKI_REPO, repo_type="dataset", filename=name, local_dir=str(wiki_dir)))
            have += len(long_articles(p))
            print(f"{p}: {have} articles of at least {args.min_chars} characters so far")
            if have >= 3 * args.n_train:
                break
        return
    import fasttext  # pip install fasttext-wheel

    rng = random.Random(cfg.get("seed", 42))
    files = sorted(wiki_dir.rglob("*.parquet"))
    if not files:
        raise SystemExit(f"No Wikipedia Parquet files in {wiki_dir}: run with --download first")
    wiki = [w for f in files for w in long_articles(f)]
    rng.shuffle(wiki)
    docs = load_stage7_input(resolve(cfg, args.processed))
    labels = load_labels(resolve(cfg, cfg["paths"]["eval_dir"]))
    web_pool = docs[~docs.doc_id.isin(labels.doc_id)]["text"].tolist()
    rng.shuffle(web_pool)
    # Hold out up to 2,000 documents of each class (at least 10%) before training
    n_hold = min(2000, max(1, len(wiki) // 10), max(1, len(web_pool) // 10))
    n = min(args.n_train, len(wiki) - n_hold, len(web_pool) - n_hold)
    if n < args.n_train:
        print(f"Warning: only {n} training examples per class ({len(wiki)} long Wikipedia articles in {len(files)} "
              f"file(s)); download more files for --n-train {args.n_train}")
    wiki_hold, wiki_train = wiki[:n_hold], wiki[n_hold:n_hold + n]
    held_web, web_train = web_pool[:n_hold], web_pool[n_hold:n_hold + n]

    # 1. fastText classifier
    examples = [f"__label__wiki {chunk(t)}" for t in wiki_train] + [f"__label__web {chunk(t)}" for t in web_train]
    rng.shuffle(examples)
    with tempfile.TemporaryDirectory() as tmp:
        train_file = Path(tmp) / "train.txt"
        train_file.write_text("\n".join(examples) + "\n", encoding="utf-8")
        clf = fasttext.train_supervised(str(train_file), epoch=10, wordNgrams=2, dim=64, lr=0.5, minCount=2,
                                        seed=cfg.get("seed", 42), thread=4, verbose=0)

    def p_web(text: str) -> float:
        labs, probs = fasttext_predict(clf, " ".join(syllables(text)[:1000]), k=2)
        return dict(zip(labs, probs)).get("__label__web", 0.0)

    # 2. Trigram language model on Wikipedia sentences (lines)
    sents = [syllables(line) for t in wiki_train for line in t.split("\n") if line.strip()]
    lm = TrigramLM(sents)

    lab = labels.merge(docs[["doc_id", "text", "stage7"]], on="doc_id")
    lab["p_web"] = lab["text"].map(p_web)
    lab["perplexity"] = lab["text"].map(lm.perplexity)
    acc_wiki = sum(p_web(t) < 0.5 for t in wiki_hold) / len(wiki_hold)
    acc_web = sum(p_web(t) >= 0.5 for t in held_web) / len(held_web)

    L = ["# Model-based quality signals on the hand-labelled pages", "",
         f"Training: {n} Wikipedia articles of 20231101.vi ({len(files)} file(s); at least {args.min_chars} "
         f"characters after the stage-3b line rules) and {n} stage-7 documents not in the labelled set. "
         f"Held-out accuracy of the classifier: {acc_wiki:.3f} on {n_hold} Wikipedia articles, {acc_web:.3f} on "
         f"{n_hold} web documents. Trigram model: {len(sents)} sentences, vocabulary {len(lm.vocab)} syllables.", "",
         f"Labelled pages found in {args.processed}: {len(lab)} ({int(lab.label.sum())} poor).", "",
         "| Signal | AUC, all | AUC, pages the rules keep (pass) | AUC, pages the rules remove (fail) |",
         "|---|---:|---:|---:|"]
    for name, col in (("fastText P(web)", "p_web"), ("Trigram perplexity", "perplexity")):
        row = [auc(lab[col].tolist(), lab.label.tolist())]
        for side in ("pass", "fail"):
            g = lab[lab.side == side]
            row.append(auc(g[col].tolist(), g.label.tolist()))
        L.append(f"| {name} | " + " | ".join(f"{x:.3f}" for x in row) + " |")
    # Same number of removals as the rules, among the labelled pages
    rules_drop = lab.stage7 == "removed"
    k = int(rules_drop.sum())
    L += ["", f"Removing the same number of labelled pages as the rules ({k} of {len(lab)}):", "",
          "| Method | Poor among removed | Poor among kept |", "|---|---:|---:|",
          f"| Rules (stage 7) | {lab.label[rules_drop].mean():.3f} | {lab.label[~rules_drop].mean():.3f} |"]
    for name, col in (("fastText P(web)", "p_web"), ("Trigram perplexity", "perplexity")):
        top = lab[col].rank(method="first", ascending=False) <= k
        L.append(f"| {name} | {lab.label[top].mean():.3f} | {lab.label[~top].mean():.3f} |")

    out_dir = resolve(cfg, cfg["paths"]["eval_dir"])
    lab[["doc_id", "rule", "side", "label", "stage7", "p_web", "perplexity"]].to_csv(
        out_dir / "quality_model_scores.csv", index=False)
    kept = docs[docs.stage7 == "kept"].sample(n=min(3000, int((docs.stage7 == "kept").sum())), random_state=1).copy()
    kept["p_web"] = kept["text"].map(p_web)
    kept["perplexity"] = kept["text"].map(lm.perplexity)
    L += ["", f"On {len(kept)} random kept documents: P(web) >= 0.9 for {(kept.p_web >= 0.9).mean() * 100:.1f}%; "
          f"median perplexity {kept.perplexity.median():.0f} (Wikipedia held-out "
          f"{pd.Series([lm.perplexity(t) for t in wiki_hold[:500]]).median():.0f})."]
    worst = kept.sort_values("p_web", ascending=False).head(50)
    worst.assign(excerpt=worst["text"].str.slice(0, 300))[["doc_id", "p_web", "perplexity", "excerpt"]].to_csv(
        out_dir / "quality_model_examples.csv", index=False, encoding="utf-8-sig")
    resolve(cfg, "models").mkdir(exist_ok=True)
    clf.save_model(str(resolve(cfg, "models/quality_fasttext.bin")))
    report = "\n".join(L) + "\n"
    (out_dir / "quality_model.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
