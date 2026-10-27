"""Test the WARC + trafilatura reference (vietweb reference) and its comparison with stage 3b (extract-eval).

A synthetic WARC file with HTML responses is served by a local HTTP server that mimics data.commoncrawl.org.
Vietnamese strings are test inputs.
"""
import copy
import io
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest

from vietweb.config import load_config
from vietweb.io.storage import Manifest, write_parquet
from vietweb.reference import build_reference, warc_path_for

pytest.importorskip("trafilatura")
from warcio.statusandheaders import StatusAndHeaders  # noqa: E402
from warcio.warcwriter import WARCWriter  # noqa: E402

CRAWL = "CC-MAIN-TEST"
WET_PATH = f"crawl-data/{CRAWL}/segments/1/wet/{CRAWL}-00000.warc.wet.gz"
MENU = ["Trang chủ", "Giới thiệu", "Sản phẩm", "Tin tức", "Liên hệ"]
PARAS = [
    "Khi tham gia một buổi tiệc, việc lựa chọn kiểu tóc phù hợp không chỉ giúp bạn trở nên nổi bật mà còn tạo "
    "điểm nhấn cho trang phục. Dưới đây là những gợi ý được nhiều người áp dụng và có thể tự làm tại nhà.",
    "Váy dạ hội dài thường đi kèm phong cách trang trọng và quý phái. Một kiểu tóc búi cao, bóng mượt sẽ là lựa "
    "chọn hoàn hảo để tôn lên chiếc cổ thon dài và vẻ đẹp sang trọng của bạn trong buổi tiệc tối.",
    "Với những chiếc váy maxi mềm mại, kiểu tóc uốn xoăn nhẹ tự nhiên sẽ mang đến vẻ đẹp nữ tính và lãng mạn. "
    "Tóc xoăn nhẹ cũng giúp gương mặt trông thanh thoát hơn và rất dễ phối với nhiều loại phụ kiện.",
]
FOOTER = "Copyright 2026 © Example. Bản quyền thuộc về công ty."


def _html(title: str) -> bytes:
    nav = "".join(f"<li><a href='/{i}'>{m}</a></li>" for i, m in enumerate(MENU))
    body = "".join(f"<p>{p}</p>" for p in PARAS)
    return (f"<html><head><title>{title}</title></head><body><nav><ul>{nav}</ul></nav>"
            f"<article><h1>{title}</h1>{body}</article><footer>{FOOTER}</footer></body></html>").encode("utf-8")


def _wet_text(title: str) -> str:
    return "\n".join([title, *MENU, title, *PARAS, FOOTER])


def _write_warc(path: Path, pages: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w = WARCWriter(f, gzip=True)
        for url, title in pages:
            http = StatusAndHeaders("200 OK", [("Content-Type", "text/html; charset=utf-8")], protocol="HTTP/1.1")
            w.write_record(w.create_warc_record(url, "response", payload=io.BytesIO(_html(title)), http_headers=http))


def test_warc_path_for():
    assert warc_path_for(WET_PATH) == f"crawl-data/{CRAWL}/segments/1/warc/{CRAWL}-00000.warc.gz"
    with pytest.raises(ValueError):
        warc_path_for("local/sample.warc.wet.gz")


def test_reference_and_extract_eval(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    cfg = copy.deepcopy(load_config("configs/pipeline.yaml"))
    for k in ("data_dir", "raw_dir", "processed_dir", "stats_dir", "eval_dir", "tmp_dir", "reference_dir"):
        cfg["paths"][k] = str(tmp_path / k)
    cfg["collect"]["http"]["pause_between_files"] = 0
    cfg["boilerplate"]["method"] = "justext"     # the assertions below are written for jusText on this page

    # Raw records as `collect` would have written them; one is missing from the WARC file
    pages = [("https://a.example.vn/toc-1", "Kiểu tóc dự tiệc"), ("https://b.example.vn/toc-2", "Tóc cho váy dạ hội")]
    raw = pd.DataFrame({
        "doc_id": ["d1", "d2", "d3"],
        "url": [pages[0][0], pages[1][0], "https://c.example.vn/missing"],
        "domain": ["a.example.vn", "b.example.vn", "c.example.vn"],
        "snapshot": CRAWL, "warc_record_id": "", "warc_refers_to": "", "crawl_date": "", "cld2_langs": "vie",
        "text": [_wet_text(pages[0][1]), _wet_text(pages[1][1]), _wet_text("Không có")],
    })
    raw_dir = tmp_path / "raw_dir" / CRAWL
    write_parquet(raw, raw_dir / "1__test.parquet")
    Manifest(raw_dir / "_manifest.jsonl").add({"wet_path": WET_PATH, "parquet": "1__test.parquet",
                                               "records_total": 10, "records_vie": 3, "bytes": 1, "seconds": 0})

    site = tmp_path / "site"
    _write_warc(site / warc_path_for(WET_PATH), pages)
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        cfg["collect"]["base_url"] = f"http://127.0.0.1:{server.server_address[1]}"
        summary = build_reference(cfg, n_files=1, crawl=CRAWL)
        assert summary["files"] == 1 and summary["docs"] == 3 and summary["found_in_warc"] == 2
        assert not any((tmp_path / "tmp_dir").glob("*.warc.gz"))         # the WARC file was deleted
        assert build_reference(cfg, n_files=1, crawl=CRAWL)["files"] == 1  # a rerun does not download again
    finally:
        server.shutdown()

    ref = pd.read_parquet(tmp_path / "reference_dir" / CRAWL / "1__test.parquet").set_index("doc_id")
    assert ref.at["d1", "found_in_warc"] and not ref.at["d3", "found_in_warc"]
    assert PARAS[1] in ref.at["d1", "ref_text"] and "Giới thiệu" not in ref.at["d1", "ref_text"]

    from vietweb.eval.extraction_eval import evaluate, label_lines, load_pairs
    pairs = load_pairs(cfg, CRAWL)
    assert len(pairs) == 2
    labels = label_lines([ln for ln in pairs.at[0, "wet"].split("\n") if ln.strip()], pairs.at[0, "ref"])
    assert labels[1:6] == [False] * 5            # menu lines are not content
    assert all(labels[7:10])                     # paragraphs are content

    text = evaluate(cfg, CRAWL)
    grid = pd.read_csv(tmp_path / "eval_dir" / "extraction_grid.csv")
    current = grid[grid["current_config"]].iloc[0]
    assert current["precision"] == 1.0 and current["recall"] > 0.9   # stage 3b keeps the paragraphs only
    none = grid[grid["method"] == "none"].iloc[0]
    assert none["recall"] == 1.0 and none["precision"] < current["precision"]
    assert "Quality stage on the three versions" in text
