"""Explain the pipeline's decision for a single page, stage by stage.

The demo app (dashboard/demo.py) uses this module to show what stages 3, 3b, 4, 5, 7 and 8 do to one page.
It calls the same functions as the stages, and tests/test_explain.py checks that the final decision equals
running the stage modules on a one-row DataFrame. Stage 6 (deduplication) needs the whole corpus, so it is
not part of a single-page explanation; the demo shows MinHash on two texts instead (minhash_pair).

Unlike the pipeline, which stops at the first removal, explain() runs every stage, so the demo can show what
the later stages would have done; first_drop() gives the stage and reason the pipeline would report.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from .config import load_wordlist, load_yaml, resolve
from .io.commoncrawl import domain_of
from .stages.s03_normalize import normalize_doc
from .stages.s03b_boilerplate import C4_TERMINAL, ELLIPSIS, context_free_class, keep_mask, load_params_and_stopwords, revise_classes
from .stages.s04_langid import VN_DIACRITICS, heuristic_score
from .stages.s05_url_filter import _blocked_domain
from .stages.s06_dedup import MinHasher, _norm_for_hash
from .stages.s07_quality import RULES, evaluate
from .stages.s08_pii import mask
from .text.normalize import legacy_encoding_score
from .text.tokenize import shingles, syllables

STAGES = ("normalize", "boilerplate", "langid", "url_filter", "quality", "pii")


@dataclass
class StageView:
    key: str                          # one of STAGES
    drop_reason: str | None           # removal reason of this stage, None = passes
    text_after: str                   # text handed to the next stage
    details: dict = field(default_factory=dict)


@dataclass
class Resources:
    """Everything the stages read from configuration files, loaded once."""
    cfg: dict
    stopwords: frozenset
    bp_params: dict
    keywords: list[str]
    blocked_domains: set[str]
    thresholds: dict
    order: tuple[str, ...]
    disabled: tuple[str, ...]
    langid_model: object = None       # fastText model when langid.backend is fasttext or glotlid


def load_resources(cfg: dict) -> Resources:
    bp, stop = load_params_and_stopwords(cfg)
    q = cfg["quality"]
    thresholds = load_yaml(resolve(cfg, q["thresholds_file"]))
    all_rules = tuple(q.get("rule_order", list(RULES)))
    order = tuple(r for r in all_rules if thresholds.get(r, {}).get("enabled", True))
    disabled = tuple(r for r in all_rules if r not in order)
    u = cfg["url_filter"]
    model = None
    if cfg["langid"].get("backend", "heuristic") in ("fasttext", "glotlid"):
        from .stages.s04_langid import _load_fasttext
        model = _load_fasttext(str(resolve(cfg, cfg["langid"]["model_path"])))
    return Resources(cfg=cfg, stopwords=frozenset(stop), bp_params=bp,
                     keywords=load_wordlist(resolve(cfg, u["keyword_blocklist"])),
                     blocked_domains=set(load_wordlist(resolve(cfg, u["domain_blocklist"]))),
                     thresholds=thresholds, order=order, disabled=disabled, langid_model=model)


def line_reasons(lines: list[str], p: dict, stopwords: set | frozenset) -> list[str | None]:
    """Why stage 3b drops each line (None = kept). The keep/drop decision itself comes from keep_mask()."""
    keep = keep_mask(lines, p, set(stopwords))
    if p["method"] == "justext":
        classes = revise_classes([context_free_class(ln, p, set(stopwords)) for ln in lines])
        return [None if k else f"justext_{c}" for k, c in zip(keep, classes)]
    out = []
    for ln, k in zip(lines, keep):
        if k:
            out.append(None)
        elif "javascript" in ln.lower():
            out.append("javascript")
        elif not ln.endswith(C4_TERMINAL):
            out.append("no_terminal_punct")
        elif len(syllables(ln)) < p["c4_min_words"]:
            out.append("too_few_syllables")
        elif p["c4_drop_ellipsis"] and ln.endswith(ELLIPSIS):
            out.append("ellipsis")
        else:
            out.append("other")
    return out


def _langid_parts(text: str, stopwords: frozenset) -> tuple[float, float]:
    toks = syllables(text)
    if not toks:
        return 0.0, 0.0
    diacritic = sum(any(ch in VN_DIACRITICS for ch in t) for t in toks) / len(toks)
    stop = sum(t in stopwords for t in toks) / len(toks)
    return diacritic, stop


def explain(text: str, url: str, res: Resources) -> list[StageView]:
    """Run stages 3, 3b, 4, 5, 7 and 8 on one page and return what each stage saw and decided."""
    cfg = res.cfg
    views: list[StageView] = []

    # 3 Normalization
    c = cfg["normalize"]
    action = c.get("legacy_encoding_action", "flag")
    out, enc = normalize_doc(text, fix_mojibake=c.get("fix_mojibake", True), form=c.get("unicode_form", "NFC"),
                             tone_style=c.get("tone_mark_style", "old"),
                             stopwords=res.stopwords if action == "convert" else None)
    legacy = legacy_encoding_score(out)
    drop = "legacy_encoding" if action == "drop" and legacy >= c.get("legacy_encoding_threshold", 0.02) else None
    views.append(StageView("normalize", drop, out, {"changed": out != text, "encoding": enc, "legacy_score": legacy,
                                                    "text_in": text, "chars_in": len(text), "chars_out": len(out)}))

    # 3b Boilerplate removal
    p = res.bp_params
    lines = [ln.strip() for ln in out.split("\n") if ln.strip()]
    reasons = line_reasons(lines, p, res.stopwords)
    clean = "\n".join(ln for ln, r in zip(lines, reasons) if r is None)
    drop = "boilerplate_too_short" if len(clean) < p["min_chars_after"] else None
    views.append(StageView("boilerplate", drop, clean, {"lines": list(zip(lines, reasons)), "method": p["method"],
                                                         "min_chars_after": p["min_chars_after"],
                                                         "chars_in": len(out), "chars_out": len(clean)}))

    # 4 Language identification
    lc = cfg["langid"]
    thr = lc.get("threshold", 0.6)
    if res.langid_model is None:
        score = heuristic_score(clean, set(res.stopwords))
    else:
        from .stages.s04_langid import fasttext_score
        score = fasttext_score(clean, res.langid_model)
    diacritic, stop_share = _langid_parts(clean, res.stopwords)
    views.append(StageView("langid", "langid_low_score" if score < thr else None, clean,
                           {"score": score, "threshold": thr, "backend": lc.get("backend", "heuristic"),
                            "diacritic_share": diacritic, "stopword_share": stop_share}))

    # 5 URL and spam filter
    domain = domain_of(url) if url else ""
    blocked = bool(domain) and _blocked_domain(domain, res.blocked_domains)
    lower = clean.lower()
    hits = {k: lower.count(k) for k in res.keywords if lower.count(k)}
    min_hits = cfg["url_filter"].get("keyword_min_hits", 3)
    drop = "url_blocklist" if blocked else ("spam_keywords" if sum(hits.values()) >= min_hits else None)
    views.append(StageView("url_filter", drop, clean, {"domain": domain, "domain_blocked": blocked,
                                                        "keyword_hits": hits, "min_hits": min_hits}))

    # 7 Quality rules (every rule is evaluated, as with save_stats: true)
    q = cfg["quality"]
    reason, values, _, _, passed, _ = evaluate(clean, res.order, res.thresholds, res.stopwords,
                                               q.get("unit", "syllable"), True)
    rules = [{"rule": r, "value": v, "threshold": res.thresholds.get(r, {}), "passed": ok}
             for r, v, ok in zip(res.order, values, passed)]
    views.append(StageView("quality", reason, clean, {"rules": rules, "disabled": list(res.disabled),
                                                       "unit": q.get("unit", "syllable")}))

    # 8 PII masking
    masked, counts = mask(clean, cfg.get("pii", {}))
    views.append(StageView("pii", None, masked, {"counts": counts}))
    return views


def first_drop(views: list[StageView]) -> tuple[str, str] | None:
    """(stage, reason) of the first removal, as the pipeline would record it; None if the page is kept."""
    for v in views:
        if v.drop_reason:
            return v.key, v.drop_reason
    return None


def text_sha1(text: str) -> str:
    """The key used by exact deduplication (stage 6)."""
    return hashlib.sha1(_norm_for_hash(text).encode("utf-8")).hexdigest()


def minhash_pair(a: str, b: str, unit: str = "syllable", n: int = 5, num_perm: int = 112,
                 bands: int = 14, rows: int = 8) -> dict:
    """Exact Jaccard, MinHash estimate, and LSH band matches for two texts (stage 6 settings by default)."""
    sa, sb = shingles(a, unit, n), shingles(b, unit, n)
    jac = len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    hasher = MinHasher(num_perm)
    ha, hb = hasher(sa).hashvalues, hasher(sb).hashvalues
    est = float(np.mean(ha == hb))
    matched = [i for i in range(bands) if np.array_equal(ha[i * rows:(i + 1) * rows], hb[i * rows:(i + 1) * rows])]
    p = candidate_probability(jac, bands, rows)
    return {"shingles_a": len(sa), "shingles_b": len(sb), "shared": len(sa & sb), "jaccard": jac,
            "minhash_estimate": est, "bands_matched": matched, "bands": bands, "rows": rows,
            "candidate": bool(matched), "p_candidate": p, "threshold": (1 / bands) ** (1 / rows)}


def candidate_probability(s: float, bands: int = 14, rows: int = 8) -> float:
    """Probability that two documents with Jaccard similarity s share at least one LSH band."""
    return 1 - (1 - s ** rows) ** bands
