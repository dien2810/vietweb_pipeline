"""Test the collect command against a local HTTP server that mimics data.commoncrawl.org."""
import copy
import gzip
import importlib.util
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from vietweb.collect import collect
from vietweb.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CRAWL = "CC-MAIN-TEST"


def _make_wet(path: Path) -> Path:
    spec = importlib.util.spec_from_file_location("make_sample_wet", ROOT / "scripts" / "make_sample_wet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.make(path)


def test_collect_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    site = tmp_path / "site"
    rels = [f"crawl-data/{CRAWL}/segments/1/wet/{CRAWL}-0000{i}.warc.wet.gz" for i in range(2)]
    for r in rels:
        _make_wet(site / r)
    with gzip.open(site / f"crawl-data/{CRAWL}/wet.paths.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(rels) + "\n")

    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        cfg = copy.deepcopy(load_config("configs/pipeline.yaml"))
        for k in ("data_dir", "raw_dir", "processed_dir", "stats_dir", "eval_dir", "tmp_dir"):
            cfg["paths"][k] = str(tmp_path / k)
        cfg["collect"]["base_url"] = f"http://127.0.0.1:{server.server_address[1]}"
        cfg["collect"]["http"]["pause_between_files"] = 0

        s = collect(cfg, n_files=2, crawl=CRAWL)
        assert s["files"] == 2 and s["records_vie"] >= 16
        assert not any((tmp_path / "tmp_dir").glob("*.gz"))       # temporary WET files were deleted
        assert len(list((tmp_path / "raw_dir" / CRAWL).glob("*.parquet"))) == 2
        assert collect(cfg, n_files=2, crawl=CRAWL)["files"] == 2  # a rerun does not download again
    finally:
        server.shutdown()
