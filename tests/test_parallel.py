"""Several processes must give the same output as one process."""
from functools import partial

import pandas as pd

from vietweb.parallel import n_workers, pmap, pmap_series, shutdown
from vietweb.stages.s08_pii import mask
from vietweb.text.normalize import normalize_text


def test_n_workers():
    assert n_workers({}) == 1
    assert n_workers({"parallel": {"workers": 3}}) == 3
    assert n_workers({"parallel": {"workers": 0}}) >= 1


def test_pmap_same_as_loop():
    texts = [f"Hoà bình số {i}\n\n\nthuỷ lợi, gọi 0912 345 678" for i in range(300)]
    cfg = {"parallel": {"workers": 2, "min_items": 1}}
    norm = partial(normalize_text, tone_style="old")
    pii = partial(mask, enabled={})
    try:
        assert pmap(norm, texts, cfg) == [norm(t) for t in texts]
        s = pd.Series(texts, index=range(1000, 1300))
        out = pmap_series(pii, s, cfg)
        assert list(out.index) == list(s.index)
        assert out.tolist() == [pii(t) for t in texts]
    finally:
        shutdown()
