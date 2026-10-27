"""Compare boilerplate removal on WET text (stage 3b) with the trafilatura reference from WARC HTML.

Inputs: the reference Parquet files written by `vietweb reference` and the raw WET text of the same
documents. Both texts go through the same normalization (stage 3) first.

1. Line-level agreement. Each non-empty WET line is labelled "content" when it also appears in the
   reference text: a line of 30 characters or more counts when it is a substring of the reference
   (whitespace collapsed); a shorter line counts only when it equals a whole reference line, so that
   menu items such as "Tin tức" do not match inside sentences. Precision and recall are weighted by
   characters. A page that the stage drops (less than min_chars_after left) keeps nothing.
   Evaluated for a grid of jusText settings, the C4 line rules, and "none" (keep everything).
2. Quality-stage outcome. The quality rules (stage 7) run on three versions of the same pages: raw WET,
   WET after stage 3b with the current configuration, and the trafilatura text.

Outputs in outputs/eval/: extraction_grid.csv, extraction_quality.csv, extraction_eval.md.
"""
from __future__ import annotations

import copy
import itertools

import pandas as pd

from ..config import resolve
from ..io.storage import read_raw
from ..reference import reference_dir
from ..stages import s07_quality
from ..stages.s03b_boilerplate import clean_text, keep_mask, load_params_and_stopwords
from ..text.normalize import normalize_text

SHORT_LINE = 30


def _ws(s: str) -> str:
    return " ".join(s.split())


def label_lines(lines: list[str], ref_text: str) -> list[bool]:
    ref_flat = _ws(ref_text)
    ref_lines = {_ws(ln.strip().lstrip("-•*|").strip()) for ln in ref_text.split("\n") if ln.strip()}
    labels = []
    for ln in lines:
        n = _ws(ln)
        labels.append(n in ref_lines or (len(n) >= SHORT_LINE and n in ref_flat))
    return labels


def _normalize(text: str, cfg: dict) -> str:
    c = cfg["normalize"]
    return normalize_text(text, fix_mojibake=c.get("fix_mojibake", True), form=c.get("unicode_form", "NFC"),
                          tone_style=c.get("tone_mark_style", "old"))


def load_pairs(cfg: dict, crawl: str | None = None) -> pd.DataFrame:
    """doc_id, url, wet (normalized WET text), ref (normalized trafilatura text) for documents found in WARC."""
    crawl = crawl or cfg["collect"]["crawl"]
    files = sorted(reference_dir(cfg, crawl).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No reference files in {reference_dir(cfg, crawl)}. Run `vietweb reference` first.")
    ref = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    ref = ref[ref["found_in_warc"]]
    raw = read_raw(resolve(cfg, cfg["paths"]["raw_dir"]), [crawl])[["doc_id", "text", "cld2_langs"]]
    df = ref.merge(raw, on="doc_id", how="inner")
    df["wet"] = df["text"].map(lambda t: _normalize(t, cfg))
    df["ref"] = df["ref_text"].map(lambda t: _normalize(t, cfg) if t else "")
    return df[["doc_id", "url", "cld2_langs", "wet", "ref"]].reset_index(drop=True)


def line_scores(pairs: pd.DataFrame, params: dict, stopwords: set[str]) -> dict:
    tp = fp = fn = 0
    doc_kept = doc_ref = doc_both = 0
    min_after = params["min_chars_after"]
    for wet, ref in zip(pairs["wet"], pairs["ref"]):
        lines = [ln.strip() for ln in wet.split("\n") if ln.strip()]
        labels = label_lines(lines, ref)
        if params["method"] == "none":
            keep = [True] * len(lines)
        else:
            keep = keep_mask(lines, params, stopwords)
            if sum(len(ln) for ln, k in zip(lines, keep) if k) < min_after:
                keep = [False] * len(lines)        # the page is dropped by the stage
        for ln, k, y in zip(lines, keep, labels):
            n = len(ln)
            tp += n * (k and y)
            fp += n * (k and not y)
            fn += n * (y and not k)
        kept_any = any(keep)
        has_ref = len(ref) >= min_after
        doc_kept += kept_any
        doc_ref += has_ref
        doc_both += kept_any and has_ref
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "pages_kept": doc_kept, "pages_with_reference": doc_ref, "pages_both": doc_both}


def settings_grid(base: dict) -> list[dict]:
    grid = [dict(base, method="none"), dict(base, method="c4_lines")]
    for lh, hi, lo in itertools.product((120, 150, 200), (0.10, 0.12, 0.15), (0.06, 0.08, 0.10)):
        if lo < hi:
            grid.append(dict(base, method="justext", length_high=lh, stopwords_high=hi, stopwords_low=lo))
    return grid


def quality_outcome(texts: pd.Series, cfg: dict) -> tuple[pd.Series, int]:
    """Share of pages failing each quality rule (%), and the number of pages that pass all rules."""
    c = copy.deepcopy(cfg)
    c["quality"]["save_stats"] = True
    res = s07_quality.run(pd.DataFrame({"text": texts.values}), c)
    fails = {r["rule"]: round(100 * (1 - r["pass_rate"]), 1) for r in res.stats["rule_costs"] if r["evaluated"]}
    return pd.Series(fails), int(res.drop_reason.isna().sum())


def md_table(df: pd.DataFrame, index: bool = False) -> str:
    """Markdown table without the optional `tabulate` dependency."""
    d = df.reset_index() if index else df
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def evaluate(cfg: dict, crawl: str | None = None) -> str:
    pairs = load_pairs(cfg, crawl)
    base, stop = load_params_and_stopwords(cfg)
    min_after = base["min_chars_after"]

    rows = []
    for params in settings_grid(base):
        r = line_scores(pairs, params, stop)
        r.update({k: params[k] for k in ("method", "length_high", "stopwords_high", "stopwords_low")})
        if params["method"] != "justext":
            r.update({"length_high": None, "stopwords_high": None, "stopwords_low": None})
        r["current_config"] = params["method"] == base["method"] and all(
            params[k] == base[k] for k in ("length_high", "stopwords_high", "stopwords_low"))
        rows.append(r)
    grid = pd.DataFrame(rows).sort_values("f1", ascending=False, kind="stable")
    grid["length_high"] = grid["length_high"].astype("Int64")

    # Quality-stage outcome on three versions of the same pages
    cleaned = pairs["wet"].map(lambda t: clean_text(t, base, stop))
    versions = {"wet": pairs["wet"], "wet_boilerplate": cleaned, "trafilatura": pairs["ref"]}
    cols, entering, passing = {}, {}, {}
    for name, texts in versions.items():
        texts = texts[texts.str.len() >= min_after]
        entering[name] = len(texts)
        cols[name], passing[name] = quality_outcome(texts, cfg) if len(texts) else (pd.Series(dtype=float), 0)
    quality = pd.DataFrame(cols)
    quality.index.name = "rule (% of pages failing)"

    out_dir = resolve(cfg, cfg["paths"]["eval_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    grid.to_csv(out_dir / "extraction_grid.csv", index=False)
    quality.to_csv(out_dir / "extraction_quality.csv")

    n = len(pairs)
    summary = pd.DataFrame({"pages entering quality (>= min_chars_after)": entering,
                            "pages passing quality": passing}).T
    summary.index.name = "pages"
    md = ["# Boilerplate removal vs trafilatura reference",
          "",
          f"Pages found in WARC: {n}; pages whose trafilatura text has at least {min_after} characters: "
          f"{int((pairs['ref'].str.len() >= min_after).sum())}.",
          "",
          "## Line-level agreement (character-weighted), best settings first",
          "",
          md_table(grid.head(12)),
          "",
          "Current configuration:",
          "",
          md_table(grid[grid["current_config"]]),
          "",
          "## Quality stage on the three versions",
          "",
          md_table(summary, index=True),
          "",
          md_table(quality, index=True),
          ""]
    text = "\n".join(md)
    (out_dir / "extraction_eval.md").write_text(text, encoding="utf-8")
    return text
