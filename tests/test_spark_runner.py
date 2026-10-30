"""The near-duplicate rule of spark_runner (bands + greedy walk in order) must give the same decisions as
stage 6 (datasketch MinHash-LSH queried document by document). Pure Python: Spark is not needed."""
import hashlib
import random

import pandas as pd

from vietweb.spark_runner import _greedy_near
from vietweb.stages import s06_dedup

CFG = {"dedup": {"near": {"unit": "syllable", "ngram": 5, "num_perm": 112, "bands": 14, "rows": 8}}, "parallel": {}}
WORDS = "một hai ba bốn năm sáu bảy tám chín mười nhà cửa đường phố sông núi biển trời mây gió".split()


def make_docs(n=120, seed=3):
    rng = random.Random(seed)
    base = [" ".join(rng.choice(WORDS) for _ in range(60)) for _ in range(n // 3)]
    docs = []
    for i in range(n):
        b = base[rng.randrange(len(base))].split()
        k = rng.choice([0, 1, 3, 20])                 # 0-3 changed words: near duplicate; 20: different
        for _ in range(k):
            b[rng.randrange(len(b))] = rng.choice(WORDS)
        docs.append(" ".join(b))
    return docs


def test_greedy_matches_stage6():
    docs = make_docs()
    df = pd.DataFrame({"doc_id": [f"d{i}" for i in range(len(docs))], "text": docs})
    stage6 = s06_dedup.run_near(df, CFG).drop_reason
    c = CFG["dedup"]["near"]
    rows = []
    for order, (doc_id, text) in enumerate(zip(df.doc_id, df.text)):
        hv = s06_dedup.signature(text, c["unit"], c["ngram"], c["num_perm"])
        for b in range(c["bands"]):
            rows.append((order, doc_id, b, hashlib.md5(hv[b * c["rows"]:(b + 1) * c["rows"]].tobytes()).hexdigest()))
    bands = pd.DataFrame(rows, columns=["order", "doc_id", "band", "key"])
    shared = bands.groupby(["band", "key"]).doc_id.transform("size") > 1
    removed = _greedy_near(bands[shared])
    assert set(removed) == set(df.doc_id[stage6.notna()])
    assert 0 < len(removed) < len(df)
