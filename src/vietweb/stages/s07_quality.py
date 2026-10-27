"""Stage 7: quality filtering with Gopher, C4, and FineWeb rules.

Each rule is a metric function plus a removal condition. Thresholds come from configs/vie_thresholds.yaml.
The stage measures the time and pass rate of every rule (outputs/stats/filter_costs.csv) so that
`vietweb order-filters` can suggest a cost-optimal rule order (RQ4).

Two modes:
- save_stats: true  -> compute EVERY metric for every document (for threshold calibration, RQ1).
- save_stats: false -> stop at the first violated rule (production mode; runtime depends on rule order).
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..config import load_wordlist, load_yaml, resolve
from ..text.tokenize import tokens
from .base import StageResult

BULLETS = ("•", "-", "*", "·", "●", "▪", "‣", "◦", "–", "►", "✓")
TERMINAL_PUNCT = (".", "!", "?", "…", '"', "”", "’", ":", ";", ")")


@dataclass
class Doc:
    text: str
    toks: list[str]
    lines: list[str]        # non-empty lines
    stopwords: set[str]


def _dup_fraction(items: list[str]) -> float:
    if not items:
        return 0.0
    return (len(items) - len(set(items))) / len(items)


def _top_ngram_char_frac(toks: list[str], n: int) -> float:
    if len(toks) < n:
        return 0.0
    grams = Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))
    gram, count = grams.most_common(1)[0]
    total_chars = sum(len(t) for t in toks)
    return count * sum(len(t) for t in gram) / max(total_chars, 1)


# Each rule: (metric function, removal decision from the metric value and the thresholds)
Metric = Callable[[Doc], float]
Decide = Callable[[float, dict], bool]

RULES: dict[str, tuple[Metric, Decide]] = {
    "c4_lorem_ipsum": (lambda d: float("lorem ipsum" in d.text.lower()), lambda v, t: v > 0),
    "c4_curly_bracket": (lambda d: float("{" in d.text), lambda v, t: v > 0),
    "gopher_word_count": (lambda d: float(len(d.toks)),
                          lambda v, t: v < t["min"] or v > t["max"]),
    "gopher_mean_word_length": (lambda d: sum(len(w.replace("_", "")) for w in d.toks) / max(len(d.toks), 1),
                                lambda v, t: v < t["min"] or v > t["max"]),
    "gopher_symbol_ratio": (lambda d: (d.text.count("#") + d.text.count("...") + d.text.count("…")) / max(len(d.toks), 1),
                            lambda v, t: v > t["max"]),
    "gopher_bullet_lines": (lambda d: sum(ln.lstrip().startswith(BULLETS) for ln in d.lines) / max(len(d.lines), 1),
                            lambda v, t: v > t["max"]),
    "gopher_ellipsis_lines": (lambda d: sum(ln.rstrip().endswith(("...", "…")) for ln in d.lines) / max(len(d.lines), 1),
                              lambda v, t: v > t["max"]),
    "gopher_alpha_words": (lambda d: (lambda ws: sum(any(ch.isalpha() for ch in w) for w in ws) / max(len(ws), 1))(d.text.split()),
                           lambda v, t: v < t["min"]),
    "gopher_stopwords": (lambda d: float(len(d.stopwords.intersection(d.toks))),
                         lambda v, t: v < t["min"]),
    "gopher_dup_lines": (lambda d: _dup_fraction(d.lines), lambda v, t: v > t["max"]),
    "gopher_dup_paragraphs": (lambda d: _dup_fraction([p.strip() for p in d.text.split("\n\n") if p.strip()]),
                              lambda v, t: v > t["max"]),
    "gopher_top_2gram": (lambda d: _top_ngram_char_frac(d.toks, 2), lambda v, t: v > t["max"]),
    "gopher_top_3gram": (lambda d: _top_ngram_char_frac(d.toks, 3), lambda v, t: v > t["max"]),
    "gopher_top_4gram": (lambda d: _top_ngram_char_frac(d.toks, 4), lambda v, t: v > t["max"]),
    "fineweb_line_punct": (lambda d: sum(ln.rstrip().endswith(TERMINAL_PUNCT) for ln in d.lines) / max(len(d.lines), 1),
                           lambda v, t: v <= t["min"]),
    "fineweb_dup_line_chars": (lambda d: (lambda c: sum(len(l) * (n - 1) for l, n in c.items() if n > 1)
                                          / max(sum(len(l) for l in d.lines), 1))(Counter(d.lines)),
                               lambda v, t: v >= t["max"]),
    "fineweb_short_lines": (lambda d: sum(len(ln.strip()) < 30 for ln in d.lines) / max(len(d.lines), 1),
                            lambda v, t: v >= t["max"]),
}


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    c = cfg["quality"]
    thresholds = load_yaml(resolve(cfg, c["thresholds_file"]))
    stop = set(load_wordlist(resolve(cfg, c["stopwords_file"])))
    order = [r for r in c.get("rule_order", list(RULES)) if thresholds.get(r, {}).get("enabled", True)]
    unknown = [r for r in order if r not in RULES]
    if unknown:
        raise ValueError(f"Unknown rules: {unknown}")
    save_stats = c.get("save_stats", True)
    unit = c.get("unit", "syllable")

    evaluated = Counter()
    passed = Counter()
    seconds = Counter()
    prep_seconds = 0.0
    reasons, metrics = [], {r: [] for r in order}

    for text in df["text"]:
        t0 = time.perf_counter()
        doc = Doc(text=text, toks=tokens(text, unit),
                  lines=[ln for ln in text.split("\n") if ln.strip()], stopwords=stop)
        prep_seconds += time.perf_counter() - t0
        reason = None
        for rule in order:
            if reason is not None and not save_stats:
                metrics[rule].append(None)
                continue
            metric, decide = RULES[rule]
            t1 = time.perf_counter()
            v = metric(doc)
            fail = decide(v, thresholds.get(rule, {}))
            seconds[rule] += time.perf_counter() - t1
            evaluated[rule] += 1
            passed[rule] += not fail
            metrics[rule].append(round(v, 5))
            if fail and reason is None:
                reason = rule
        reasons.append(reason)

    costs = [{
        "rule": r,
        "evaluated": evaluated[r],
        "passed": passed[r],
        "pass_rate": round(passed[r] / evaluated[r], 5) if evaluated[r] else None,
        "total_seconds": round(seconds[r], 5),
        "sec_per_doc": seconds[r] / evaluated[r] if evaluated[r] else None,
    } for r in order]

    drop = pd.Series(reasons, index=df.index, dtype=object)
    extra = {f"q_{r}": pd.Series(v, index=df.index) for r, v in metrics.items()} if save_stats else {}
    return StageResult(drop_reason=drop, extra=extra,
                       stats={"unit": unit, "save_stats": save_stats, "prepare_seconds": round(prep_seconds, 4),
                              "rule_costs": costs})
