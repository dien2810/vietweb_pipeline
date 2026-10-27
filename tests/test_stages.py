"""Tests for the individual processing stages. Vietnamese strings are test inputs."""
import copy

import pandas as pd
import pytest

from vietweb.config import load_config
from vietweb.stages import s04_langid, s06_dedup, s07_quality, s08_pii

GOOD = ("Trí tuệ nhân tạo đang thay đổi cách chúng ta làm việc và học tập. Các mô hình ngôn ngữ lớn được huấn "
        "luyện trên lượng văn bản khổng lồ thu thập từ internet, vì vậy chất lượng dữ liệu có vai trò rất quan trọng.\n"
        "Nếu dữ liệu chứa nhiều văn bản trùng lặp hoặc spam, mô hình sẽ học những mẫu không mong muốn.")


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/pipeline.yaml")


def frame(texts, domains=None):
    return pd.DataFrame({"doc_id": [f"d{i}" for i in range(len(texts))], "text": texts,
                         "domain": domains or ["example.vn"] * len(texts)})


def test_langid_heuristic(cfg):
    res = s04_langid.run(frame([GOOD, "The quick brown fox jumps over the lazy dog " * 5]), cfg)
    assert res.drop_reason.iloc[0] is None
    assert res.drop_reason.iloc[1] == "langid_low_score"


def test_exact_dedup(cfg):
    other = "khác hẳn " * 30   # unrelated Vietnamese text
    res = s06_dedup.run_exact(frame([GOOD, GOOD.upper(), other]), cfg)
    assert res.drop_reason.tolist() == [None, "exact_duplicate", None]


def test_near_dedup(cfg):
    near = GOOD.replace("rất quan trọng", "vô cùng quan trọng")
    unrelated = "một văn bản hoàn toàn khác về thời tiết hôm nay " * 5
    res = s06_dedup.run_near(frame([GOOD, near, unrelated]), cfg)
    assert res.drop_reason.tolist() == [None, "near_duplicate", None]


def test_line_dedup(cfg):
    footer = "Bản quyền thuộc về Báo Ví Dụ"   # a copyright footer repeated on every page of a site
    texts = [f"Bài {i}: nội dung riêng số {i} rất dài để không bị loại\n{footer}" for i in range(4)]
    res = s06_dedup.run_line(frame(texts), cfg)
    assert all(footer not in t for t in res.text)


def test_line_dedup_cross_site(cfg):
    shared = "Chưa có sản phẩm trong giỏ hàng."           # a theme string found on many shop websites
    texts = [f"Bài viết số {i} của website thứ {i}, nội dung riêng\n{shared}" for i in range(25)]
    domains = [f"site{i}.vn" for i in range(25)]
    c = copy.deepcopy(cfg)
    c["dedup"]["line"]["min_domains"] = 20
    res = s06_dedup.run_line(frame(texts, domains), c)
    assert all(shared not in t for t in res.text) and all(t.startswith("Bài viết số") for t in res.text)
    assert res.stats["removed_lines_cross_site"] == 25 and res.stats["docs_with_cross_site_lines"] == 25
    for off in (0, 26):                                     # rule off, or fewer domains than the threshold
        c["dedup"]["line"]["min_domains"] = off
        assert all(shared in t for t in s06_dedup.run_line(frame(texts, domains), c).text)


def test_quality_rules(cfg):
    listing = "\n".join(f"Áo {i}" for i in range(80))   # product list: very short lines
    res = s07_quality.run(frame([GOOD, listing, GOOD + " lorem ipsum"]), cfg)
    reasons = res.drop_reason.tolist()
    assert reasons[0] is None
    assert reasons[1] is not None
    assert reasons[2] == "c4_lorem_ipsum"
    assert {r["rule"] for r in res.stats["rule_costs"]} >= {"gopher_word_count", "fineweb_short_lines"}


def test_pii_mask():
    text, counts = s08_pii.mask("Gọi 0912 345 678, +84 987654321 hoặc a.b@example.com; CCCD 012345678901",
                                {"email": True, "ipv4": True, "phone_vn": True, "cccd": True})
    assert counts["phone_vn"] == 2 and counts["email"] == 1 and counts["cccd"] == 1
    assert "0912" not in text and "@" not in text
