"""Stage 4: language identification.

Three backends:
- heuristic (default): no model download. The score combines the share of syllables carrying
  Vietnamese diacritics and the share of stop words. Unaccented text scores low (LUAT_LOC.md, section 14.3).
- fasttext: the fastText lid.176.bin model (126 MB download).
- glotlid: the GlotLID model used by FineWeb-2 (Hugging Face repository cis-lmu/glotlid).
"""
from __future__ import annotations

from functools import lru_cache, partial
from pathlib import Path

import pandas as pd

from ..config import load_wordlist, resolve
from ..parallel import pmap_series
from ..text.tokenize import syllables
from .base import StageResult

# Vietnamese letters that carry a diacritic or tone mark
VN_DIACRITICS = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")


def heuristic_score(text: str, stopwords: set[str]) -> float:
    toks = syllables(text)
    if not toks:
        return 0.0
    diacritic = sum(any(ch in VN_DIACRITICS for ch in t) for t in toks) / len(toks)
    stop = sum(t in stopwords for t in toks) / len(toks)
    # Typical Vietnamese prose: roughly 50-70% of syllables carry a diacritic and 10-20% are stop words.
    return round(0.6 * min(1.0, diacritic / 0.5) + 0.4 * min(1.0, stop / 0.12), 4)


@lru_cache(maxsize=2)
def _load_fasttext(model_path: str):
    try:
        import fasttext
    except ImportError as e:  # pragma: no cover
        raise ImportError("The fasttext/glotlid backends require: pip install fasttext-wheel") from e
    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. See HUONG_DAN_CHAY.md (language identification with a model).")
    return fasttext.load_model(model_path)


def fasttext_predict(model, text: str, k: int = 3) -> tuple[list[str], list[float]]:
    """Top-k labels and probabilities. Calls the C++ binding directly: model.predict of fasttext-wheel 0.9.2
    fails with numpy 2 ("Unable to avoid copy while creating an array")."""
    pairs = model.f.predict(text.replace("\n", " "), k, 0.0, "strict")
    return [lab for _, lab in pairs], [float(p) for p, _ in pairs]


def fasttext_score(text: str, model) -> float:
    labels, probs = fasttext_predict(model, text, k=3)
    for lab, p in zip(labels, probs):
        if lab in ("__label__vi", "__label__vie_Latn"):
            return float(p)
    return 0.0


def run(df: pd.DataFrame, cfg: dict) -> StageResult:
    c = cfg["langid"]
    backend = c.get("backend", "heuristic")
    if backend == "heuristic":
        stop = set(load_wordlist(resolve(cfg, cfg["quality"]["stopwords_file"])))
        score = pmap_series(partial(heuristic_score, stopwords=stop), df["text"], cfg).astype(float)
    elif backend in ("fasttext", "glotlid"):
        model = _load_fasttext(str(resolve(cfg, c["model_path"])))
        score = df["text"].map(lambda t: fasttext_score(t, model))
    else:
        raise ValueError(f"Invalid langid.backend: {backend}")

    thr = c.get("threshold", 0.6)
    drop = pd.Series([None] * len(df), index=df.index, dtype=object)
    drop[score < thr] = "langid_low_score"
    return StageResult(drop_reason=drop, extra={"lang_score": score},
                       stats={"backend": backend, "threshold": thr, "mean_score": float(score.mean() or 0)})
