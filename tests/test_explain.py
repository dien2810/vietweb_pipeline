"""The single-page explanation used by the demo app must give the same decision as the stage modules."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from vietweb.config import load_config
from vietweb.explain import explain, first_drop, load_resources, minhash_pair
from vietweb.io.commoncrawl import domain_of
from vietweb.stages import s03_normalize, s03b_boilerplate, s04_langid, s05_url_filter, s07_quality, s08_pii

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("demo_examples", ROOT / "dashboard" / "demo_examples.py")
examples = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(examples)

STAGES = [("normalize", s03_normalize), ("boilerplate", s03b_boilerplate), ("langid", s04_langid),
          ("url_filter", s05_url_filter), ("quality", s07_quality), ("pii", s08_pii)]


@pytest.fixture(scope="module")
def cfg():
    c = load_config(ROOT / "configs" / "pipeline.yaml")
    c["_root"] = str(ROOT)
    c["parallel"] = {"workers": 1}
    c["langid"]["backend"] = "heuristic"
    return c


def run_stages(text: str, url: str, cfg: dict):
    """Run the stage modules on a one-row DataFrame, stopping at the first removal like the pipeline."""
    df = pd.DataFrame({"doc_id": ["d0"], "url": [url], "domain": [domain_of(url)], "text": [text]})
    for name, mod in STAGES:
        res = mod.run(df, cfg)
        if res.drop_reason is not None and res.drop_reason.notna().any():
            return (name, res.drop_reason.iloc[0]), df["text"].iloc[0]
        if res.text is not None:
            df["text"] = res.text
    return None, df["text"].iloc[0]


@pytest.mark.parametrize("label", list(examples.EXAMPLES))
def test_explain_matches_stages(cfg, label):
    url, text, _ = examples.EXAMPLES[label]
    views = explain(text, url, load_resources(cfg))
    expected, final_text = run_stages(text, url, cfg)
    assert first_drop(views) == expected
    if expected is None:
        assert views[-1].text_after == final_text


def test_examples_end_where_described(cfg):
    res = load_resources(cfg)
    ends = {label: first_drop(explain(text, url, res)) for label, (url, text, _) in examples.EXAMPLES.items()}
    assert ends["Trang tin có menu và chân trang"] is None
    assert ends["Trang viết bằng bảng mã TCVN3"] is None
    assert ends["Trang quảng cáo cờ bạc"] == ("url_filter", "spam_keywords")
    assert ends["Trang tiếng Anh"] == ("langid", "langid_low_score")
    assert ends["Trang chỉ có menu"] == ("boilerplate", "boilerplate_too_short")
    assert ends["Trang rao vặt lặp lại"][0] == "quality"
    news = explain(examples.NEWS, "https://a.example/x", res)
    assert news[-1].details["counts"]["phone_vn"] == 1 and news[-1].details["counts"]["email"] == 1
    tcvn = explain(examples.EXAMPLES["Trang viết bằng bảng mã TCVN3"][1], "", res)
    assert tcvn[0].details["encoding"] == "tcvn3"


def test_minhash_pair():
    same = minhash_pair(examples.PAIR_A, examples.PAIR_A)
    assert same["jaccard"] == 1.0 and same["candidate"] and len(same["bands_matched"]) == 14
    pair = minhash_pair(examples.PAIR_A, examples.PAIR_B)
    assert 0 < pair["jaccard"] < 1
    assert abs(pair["minhash_estimate"] - pair["jaccard"]) < 0.25
    other = minhash_pair(examples.PAIR_A, examples.SPAM)
    assert other["jaccard"] == 0.0 and not other["candidate"]
