"""Tests for the FineWeb-2 comparison (RQ3) on small local Parquet files laid out like the dataset."""
import copy
import glob
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from vietweb.config import load_config
from vietweb.eval import fineweb2 as fw

DUMP = "CC-MAIN-2024-10"
WARC = "CC-MAIN-TEST-00000.warc.gz"


class LocalFS:
    """The two methods of huggingface_hub.HfFileSystem that the module uses, on the local disk."""

    def glob(self, pattern):
        return sorted(glob.glob(pattern))

    def open(self, path, mode="rb"):
        return open(path, mode)


def _write_subset(root, subset, urls_by_dump):
    rows = [{"text": "nội dung " * 50, "url": u, "dump": d,
             "file_path": f"s3://commoncrawl/crawl-data/{d}/segments/1/warc/{WARC}"}
            for d in sorted(urls_by_dump) for u in urls_by_dump[d]]
    if subset.endswith("_removed"):
        for r in rows:
            r["filter_reason"] = "gopher_repetition_filter"
    path = root / "data" / subset / "train" / "000_00000.parquet"
    path.parent.mkdir(parents=True)
    # one row group per dump, so the dump statistics let the scan skip the other dumps
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=3)
    return path


def _cfg(tmp_path):
    cfg = copy.deepcopy(load_config())
    for k in ("raw_dir", "processed_dir", "eval_dir", "fineweb2_dir"):
        cfg["paths"][k] = str(tmp_path / k)
    return cfg


def test_scan_reads_only_the_requested_dump(tmp_path):
    path = _write_subset(tmp_path / "hf", "vie_Latn", {"CC-MAIN-2023-50": ["x1", "x2", "x3"],
                                                       DUMP: ["a", "b", "c"], "CC-MAIN-2024-18": ["y1", "y2", "y3"]})
    df, info = fw.scan_file(LocalFS(), str(path), DUMP)
    assert sorted(df["url"]) == ["a", "b", "c"] and set(df["warc_file"]) == {WARC}
    assert info["read_row_groups"] == 1 and info["skipped_row_groups"] == 2


def test_urls_compare_and_resume(tmp_path):
    root = tmp_path / "hf"
    _write_subset(root, "vie_Latn", {DUMP: ["u1", "u2", "u3"]})
    _write_subset(root, "vie_Latn_removed", {DUMP: ["u4", "u5", "u9"]})
    cfg = _cfg(tmp_path)
    probe = fw.fw2_urls(cfg, DUMP, probe=True, fs=LocalFS(), root=str(root))
    assert probe["vie_Latn"]["row_groups_to_read_in_first_file"] == 1
    s = fw.fw2_urls(cfg, DUMP, fs=LocalFS(), root=str(root))
    assert s["vie_Latn"]["rows_matched"] == 3 and s["vie_Latn_removed"]["rows_matched"] == 3
    fw.fw2_urls(cfg, DUMP, fs=LocalFS(), root=str(root))        # second run: nothing new to read
    assert len(open(tmp_path / "fineweb2_dir" / DUMP / "vie_Latn" / "_manifest.jsonl").readlines()) == 1

    raw = tmp_path / "raw_dir" / DUMP
    raw.mkdir(parents=True)
    (raw / "_manifest.jsonl").write_text(json.dumps(
        {"wet_path": f"crawl-data/{DUMP}/segments/1/wet/CC-MAIN-TEST-00000.warc.wet.gz", "parquet": "x.parquet"}) + "\n")
    proc = tmp_path / "processed_dir"
    (proc / "kept").mkdir(parents=True)
    (proc / "dropped").mkdir(parents=True)
    base = {"snapshot": DUMP, "text": "văn bản"}
    pd.DataFrame([dict(base, url=u) for u in ("u1", "u2", "u4", "u7")]).to_parquet(proc / "kept" / "kept-00000.parquet")
    pd.DataFrame([dict(base, url=u, drop_stage="quality", drop_reason="gopher_word_count") for u in ("u3", "u5", "u8")]
                 ).to_parquet(proc / "dropped" / "dropped-00000.parquet")
    md = fw.compare(cfg, DUMP)
    # overlap u1..u5: ours kept u1 u2 u4, dropped u3 u5; FineWeb-2 kept u1 u2 u3, removed u4 u5 -> 3 of 5 agree
    assert "Overlap: 5; agreement A = 0.6" in md
    assert "gopher_repetition_filter" in md                    # FineWeb-2 removal reasons are reported
    assert "never saw (CLD2 without 'vie', or under 200 characters): 1" in md      # u9
    ex = pd.read_csv(tmp_path / "eval_dir" / f"fineweb2_{DUMP}_examples.csv", encoding="utf-8-sig")
    assert set(ex["group"]) == {"fw2 kept, ours dropped", "fw2 removed, ours kept", "both kept"}


def test_count_pii_skips_placeholder_emails():
    res = fw.count_pii(pd.Series(["Liên hệ email@example.com hoặc 0912 345 678", "Gửi về lienhe@congty.vn"]))
    assert res["email"] == {"docs": 1, "matches": 1}
    assert res["phone_vn"]["docs"] == 1
