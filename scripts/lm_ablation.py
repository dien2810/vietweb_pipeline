"""Does the cleaning help a language model? Train the same small GPT on raw and on cleaned text and compare.

Both corpora come from the same pages: "raw" is the stage-1 text (WET, CLD2 "vie") of every document that
entered a run, "clean" is the text that run kept. Each model sees the same number of tokens (one pass, no
repetition), with one BPE tokenizer trained on an equal mix of both, so the losses are directly comparable.
The main measure is the loss (and perplexity) on held-out Vietnamese Wikipedia articles, text that neither
corpus contains; the loss on held-out clean and raw web text is reported too. FineWeb compared filtering
choices the same way, with much larger models and benchmark scores (Penedo et al., 2024).

1. Prepare the data (on the machine that has the run; needs data/raw, the run's processed/ folder and
   Wikipedia files from `python scripts/quality_model.py --download`):
       pip install tokenizers
       python scripts/lm_ablation.py prepare --processed outputs/runs/wet_200_final/processed
   -> data/lm/: train_raw.bin, train_clean.bin, val_wiki.bin, val_wiki_full.bin, val_web.bin, val_raw.bin,
      tokenizer.json, meta.json
2. Train, once per corpus and seed. Only torch and numpy are needed, so this step can run on Colab
   (Runtime > GPU) after uploading data/lm and this file:
       python scripts/lm_ablation.py train --corpus raw   --seed 0 --preset gpu
       python scripts/lm_ablation.py train --corpus clean --seed 0 --preset gpu
   (--preset cpu: a smaller model and 3 M tokens, about 5 minutes per run on 8 cores)
3. Summarize: python scripts/lm_ablation.py report   -> outputs/eval/lm_ablation.md
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EOT = "<|endoftext|>"
PRESETS = {
    # n_layer, n_head, d_model, context, batch, lr, max_tokens (per corpus)
    "gpu": dict(n_layer=6, n_head=6, d_model=384, ctx=256, batch=64, lr=1e-3, max_tokens=20_000_000),
    "cpu": dict(n_layer=4, n_head=4, d_model=256, ctx=128, batch=32, lr=1e-3, max_tokens=3_000_000),
}


# ---------------------------------------------------------------------------------------------------------
# 1. prepare

def _prepare(a: argparse.Namespace) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    import pandas as pd
    from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, trainers, decoders

    from vietweb.config import load_config, resolve
    from vietweb.io.storage import raw_files
    from vietweb.stages.s03b_boilerplate import clean_text, load_params_and_stopwords

    cfg = load_config()
    rng = random.Random(a.seed)
    processed = resolve(cfg, a.processed)
    kept = pd.concat([pd.read_parquet(f, columns=["doc_id", "text"]) for f in sorted((processed / "kept").glob("*.parquet"))])
    dropped_ids = pd.concat([pd.read_parquet(f, columns=["doc_id"]) for f in sorted((processed / "dropped").glob("*.parquet"))])
    run_ids = set(kept["doc_id"]) | set(dropped_ids["doc_id"])
    raw = pd.concat([pd.read_parquet(f, columns=["doc_id", "text"])
                     for f in raw_files(resolve(cfg, cfg["paths"]["raw_dir"]), [a.crawl or cfg["collect"]["crawl"]])])
    raw = raw[raw["doc_id"].isin(run_ids)].drop_duplicates("doc_id")
    print(f"{len(raw)} raw documents (input of the run), {len(kept)} kept documents")

    p3b, stop = load_params_and_stopwords(cfg)
    # Wikipedia is only the validation set: read it in batches and stop at 3,000 long articles
    import pyarrow.parquet as pq
    import unicodedata
    pairs = []          # (article as published, article after the stage-3b line rules)
    for f in sorted(resolve(cfg, a.wiki).rglob("*.parquet")):
        for rb in pq.ParquetFile(f).iter_batches(columns=["text"], batch_size=5000):
            for x in rb.column(0).to_pylist():
                if len(x) >= 1000:
                    w = clean_text(x, p3b, stop)
                    if len(w) >= 1000:
                        pairs.append((unicodedata.normalize("NFC", x), w))
            if len(pairs) >= 3000:
                break
        if len(pairs) >= 3000:
            break
    if not pairs:
        raise SystemExit("No Wikipedia files: run python scripts/quality_model.py --download first")

    raw_texts, clean_texts = raw["text"].tolist(), kept["text"].tolist()
    rng.shuffle(raw_texts)
    rng.shuffle(clean_texts)
    rng.shuffle(pairs)
    wiki = [w for _, w in pairs]
    # The same articles with headings, lists and short lines kept: val_wiki has the line format of the clean
    # corpus (sentence lines only), so it could favour the clean model; val_wiki_full does not
    wiki_full = [x for x, _ in pairs]

    # Tokenizer: byte-level BPE on an equal number of characters from both corpora (never Wikipedia)
    def sample_chars(texts, n_chars):
        out, total = [], 0
        for t in texts:
            out.append(t)
            total += len(t)
            if total >= n_chars:
                break
        return out
    tok = Tokenizer(models.BPE())
    tok.normalizer = normalizers.NFC()
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=a.vocab, special_tokens=[EOT], show_progress=False,
                                  initial_alphabet=pre_tokenizers.ByteLevel.alphabet())
    mix = sample_chars(raw_texts, a.tok_chars // 2) + sample_chars(clean_texts, a.tok_chars // 2)
    tok.train_from_iterator(mix, trainer=trainer)
    eot = tok.token_to_id(EOT)

    def encode(texts, budget=None):
        """Token ids of whole documents (each followed by EOT), in chunks so that memory stays small, until
        `budget` tokens (None: all documents). Returns (uint16 array, number of documents used)."""
        parts, n_tok, used = [], 0, 0
        for i in range(0, len(texts), 256):
            for enc in tok.encode_batch(texts[i:i + 256]):
                ids = enc.ids
                ids.append(eot)
                parts.append(np.array(ids, dtype=np.uint16))
                n_tok += len(ids)
                used += 1
            if budget is not None and n_tok >= budget:
                break
        arr = np.concatenate(parts) if parts else np.zeros(0, dtype=np.uint16)
        return (arr[:budget] if budget is not None else arr), used

    out = ROOT / a.out if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    # Validation sets first (fixed size), then the training budget from what is left
    val_wiki, _ = encode(wiki, a.val_tokens)
    val_web, n_web = encode(clean_texts, a.val_tokens)
    val_raw, n_raw = encode(raw_texts, a.val_tokens)
    clean_rest, raw_rest = clean_texts[n_web:], raw_texts[n_raw:]
    clean_all, _ = encode(clean_rest)                    # the clean corpus is the smaller one
    budget = min(a.tokens, len(clean_all))
    train_clean = clean_all[:budget]
    train_raw, _ = encode(raw_rest, budget)
    budget = min(len(train_clean), len(train_raw))
    train_clean, train_raw = train_clean[:budget], train_raw[:budget]
    val_wiki_full, _ = encode(wiki_full, a.val_tokens)
    for name, arr in (("train_raw", train_raw), ("train_clean", train_clean), ("val_wiki", val_wiki),
                      ("val_web", val_web), ("val_raw", val_raw), ("val_wiki_full", val_wiki_full)):
        arr.tofile(out / f"{name}.bin")
    tok.save(str(out / "tokenizer.json"))
    meta = {"vocab_size": tok.get_vocab_size(), "eot": eot, "train_tokens": int(budget),
            "val_tokens": {"wiki": len(val_wiki), "web": len(val_web), "raw": len(val_raw),
                           "wiki_full": len(val_wiki_full)},
            "chars_per_token": {"clean": round(sum(map(len, clean_rest)) / max(len(clean_all), 1), 2)},
            "processed": str(a.processed), "seed": a.seed}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    if budget < a.tokens:
        print(f"Note: the clean corpus has only {budget} training tokens (asked {a.tokens}); "
              f"the train step uses at most this many.")


# ---------------------------------------------------------------------------------------------------------
# 2. train (torch + numpy only)

def _model(vocab: int, n_layer: int, n_head: int, d_model: int, ctx: int):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.ln1, self.ln2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
            self.qkv = nn.Linear(d_model, 3 * d_model)
            self.proj = nn.Linear(d_model, d_model)
            self.mlp = nn.Sequential(nn.Linear(d_model, 4 * d_model), nn.GELU(), nn.Linear(4 * d_model, d_model))

        def forward(self, x):
            b, t, c = x.shape
            q, k, v = self.qkv(self.ln1(x)).split(c, dim=2)
            q, k, v = (z.view(b, t, n_head, c // n_head).transpose(1, 2) for z in (q, k, v))
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True).transpose(1, 2).reshape(b, t, c)
            x = x + self.proj(y)
            return x + self.mlp(self.ln2(x))

    class GPT(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok = nn.Embedding(vocab, d_model)
            self.pos = nn.Embedding(ctx, d_model)
            self.blocks = nn.ModuleList(Block() for _ in range(n_layer))
            self.ln = nn.LayerNorm(d_model)
            self.head = nn.Linear(d_model, vocab, bias=False)
            self.head.weight = self.tok.weight                   # tied embeddings
            self.apply(self._init)

        @staticmethod
        def _init(m):
            if isinstance(m, (nn.Linear, nn.Embedding)):
                nn.init.normal_(m.weight, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

        def forward(self, idx, targets=None):
            t = idx.shape[1]
            x = self.tok(idx) + self.pos(torch.arange(t, device=idx.device))
            for blk in self.blocks:
                x = blk(x)
            logits = self.head(self.ln(x))
            loss = None if targets is None else F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
            return logits, loss

    return GPT()


def _train(a: argparse.Namespace) -> None:
    import torch

    p = dict(PRESETS[a.preset])
    data = Path(a.data)
    meta = json.loads((data / "meta.json").read_text(encoding="utf-8"))
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    device = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    train = np.fromfile(data / f"train_{a.corpus}.bin", dtype=np.uint16)
    n_tokens = min(len(train), a.tokens or p["max_tokens"], meta["train_tokens"])
    train = train[:n_tokens]
    vals = {k: np.fromfile(data / f"val_{k}.bin", dtype=np.uint16) for k in ("wiki", "web", "raw", "wiki_full")
            if (data / f"val_{k}.bin").exists()}
    ctx, bs = p["ctx"], p["batch"]
    steps = max(1, n_tokens // (ctx * bs))
    model = _model(meta["vocab_size"], p["n_layer"], p["n_head"], p["d_model"], ctx).to(device)
    n_params = sum(x.numel() for x in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=p["lr"], betas=(0.9, 0.95), weight_decay=0.1)
    warm = max(1, steps // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * (0.1 + 0.45 * (1 + math.cos(math.pi * min(s, steps) / steps))))
    amp = device == "cuda"
    dtype = torch.bfloat16 if amp and torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=amp and dtype == torch.float16)
    # One pass over the corpus in a shuffled order of non-overlapping windows
    starts = np.random.permutation(np.arange(0, n_tokens - ctx - 1, ctx))[: steps * bs]

    def batch(arr, idx):
        x = np.stack([arr[i:i + ctx] for i in idx]).astype(np.int64)
        y = np.stack([arr[i + 1:i + 1 + ctx] for i in idx]).astype(np.int64)
        return torch.from_numpy(x).to(device), torch.from_numpy(y).to(device)

    @torch.no_grad()
    def evaluate():
        model.eval()
        out = {}
        for k, arr in vals.items():
            idx = np.arange(0, len(arr) - ctx - 1, ctx)
            tot, n = 0.0, 0
            for i in range(0, len(idx), bs):
                x, y = batch(arr, idx[i:i + bs])
                with torch.autocast(device_type="cuda", dtype=dtype, enabled=amp):
                    _, loss = model(x, y)
                tot += float(loss) * len(x)
                n += len(x)
            out[k] = tot / max(n, 1)
        model.train()
        return out

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"lm_ablation_{a.corpus}_s{a.seed}_{a.preset}"
    log_rows, t0 = [], time.time()
    every = max(1, steps // a.evals)
    print(f"{a.corpus}: {n_tokens} tokens, {steps} steps, {n_params / 1e6:.1f} M parameters, device {device}")
    for step in range(steps):
        x, y = batch(train, starts[step * bs:(step + 1) * bs])
        with torch.autocast(device_type="cuda", dtype=dtype, enabled=amp):
            _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        sched.step()
        if (step + 1) % every == 0 or step + 1 == steps:
            v = evaluate()
            row = {"step": step + 1, "tokens": (step + 1) * bs * ctx, "train_loss": round(float(loss), 4),
                   **{f"val_{k}": round(val, 4) for k, val in v.items()}, "seconds": round(time.time() - t0, 1)}
            log_rows.append(row)
            print(row, flush=True)
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0]))
        w.writeheader()
        w.writerows(log_rows)
    final = {"corpus": a.corpus, "seed": a.seed, "preset": a.preset, "tokens": int(n_tokens),
             "params_m": round(n_params / 1e6, 2), "device": device, "seconds": log_rows[-1]["seconds"],
             **{k: v for k, v in log_rows[-1].items() if k.startswith("val_")}}
    (out_dir / f"{name}.json").write_text(json.dumps(final, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------
# 3. report

def _report(a: argparse.Namespace) -> None:
    out_dir = Path(a.out)
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("lm_ablation_*_s*.json"))]
    if not runs:
        raise SystemExit(f"No runs in {out_dir}")
    L = ["# Small GPT trained on raw vs cleaned text (same pages, same tokenizer, same number of tokens)", "",
         "Validation loss in nats per token (perplexity = e^loss); lower is better.", "",
         "Wikipedia: held-out articles after the stage-3b line rules (sentence lines, as in the clean corpus); "
         "Wikipedia, full text: the same articles with headings, lists and short lines.", "",
         "| Preset | Corpus | Seed | Tokens | Params (M) | Wikipedia | Wikipedia, full text | Clean web | Raw web | Seconds |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(runs, key=lambda r: (r["preset"], r["corpus"], r["seed"])):
        full = f"{r['val_wiki_full']:.3f}" if "val_wiki_full" in r else "–"
        L.append(f"| {r['preset']} | {r['corpus']} | {r['seed']} | {r['tokens']:,} | {r['params_m']} | "
                 f"{r['val_wiki']:.3f} ({math.exp(r['val_wiki']):.0f}) | {full} | {r['val_web']:.3f} | "
                 f"{r['val_raw']:.3f} | {r['seconds']:.0f} |")
    L += ["", "Mean over seeds, clean minus raw (negative = the cleaned corpus gives a lower loss):", ""]
    for preset in sorted({r["preset"] for r in runs}):
        for k, label in (("val_wiki", "Wikipedia"), ("val_wiki_full", "Wikipedia, full text"),
                         ("val_web", "clean web"), ("val_raw", "raw web")):
            c = [r[k] for r in runs if r["preset"] == preset and r["corpus"] == "clean" and k in r]
            w = [r[k] for r in runs if r["preset"] == preset and r["corpus"] == "raw" and k in r]
            if c and w:
                L.append(f"- {preset}, {label}: {sum(c) / len(c) - sum(w) / len(w):+.3f} "
                         f"(clean {sum(c) / len(c):.3f}, n = {len(c)}; raw {sum(w) / len(w):.3f}, n = {len(w)})")
    report = "\n".join(L) + "\n"
    (out_dir / "lm_ablation.md").write_text(report, encoding="utf-8")
    print(report)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--processed", default="outputs/runs/wet_200_final/processed")
    p.add_argument("--crawl")
    p.add_argument("--wiki", default="data/wikipedia")
    p.add_argument("--tokens", type=int, default=20_000_000, help="training tokens per corpus (at most)")
    p.add_argument("--val-tokens", type=int, default=500_000)
    p.add_argument("--vocab", type=int, default=16000)
    p.add_argument("--tok-chars", type=int, default=20_000_000, help="characters used to train the tokenizer")
    p.add_argument("--out", default="data/lm")
    p.add_argument("--seed", type=int, default=42)
    p = sub.add_parser("train")
    p.add_argument("--corpus", choices=["raw", "clean"], required=True)
    p.add_argument("--preset", choices=list(PRESETS), default="cpu")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tokens", type=int, help="training tokens (default: the preset's maximum)")
    p.add_argument("--data", default=str(ROOT / "data" / "lm"))
    p.add_argument("--out", default=str(ROOT / "outputs" / "eval"))
    p.add_argument("--evals", type=int, default=10, help="number of evaluations during training")
    p.add_argument("--device")
    p = sub.add_parser("report")
    p.add_argument("--out", default=str(ROOT / "outputs" / "eval"))
    a = ap.parse_args()
    {"prepare": _prepare, "train": _train, "report": _report}[a.cmd](a)


if __name__ == "__main__":
    main()
