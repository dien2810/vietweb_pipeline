"""Reference texts for the boilerplate experiment: WARC HTML extracted with trafilatura.

For a few WET files that were already collected, download the WARC file with the same segment and
file name (about 1 GB each, roughly 15 times the WET file), find the HTML responses of the Vietnamese
records collected from that WET file, and extract their main text with trafilatura. The settings are
those of the trafilatura extractor in datatrove, which FineWeb used:
favor_precision=True, include_comments=False, deduplicate=True.

Records are matched by the WARC response record ID (the WET header WARC-Refers-To, stored by `collect`
since this version) and otherwise by URL. Output: data/reference/<crawl>/<same name as the raw Parquet>
with columns doc_id, url, found_in_warc, html_bytes, ref_text. Reruns skip files listed in the
reference manifest; WARC files are deleted after use unless keep_warc is set.

eval/extraction_eval.py compares the boilerplate stage (stage 3b) with these reference texts.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator

import pandas as pd
from warcio.archiveiterator import ArchiveIterator

from .config import resolve
from .io import commoncrawl as cc
from .io.storage import Manifest, write_parquet

log = logging.getLogger(__name__)

TRAFILATURA_ARGS = {"favor_precision": True, "include_comments": False, "deduplicate": True}


def warc_path_for(wet_path: str) -> str:
    """crawl-data/<crawl>/segments/<seg>/wet/<name>.warc.wet.gz -> .../warc/<name>.warc.gz"""
    if "/wet/" not in wet_path or not wet_path.endswith(".warc.wet.gz"):
        raise ValueError(f"Not a Common Crawl WET path (files from collect-local have no WARC): {wet_path}")
    return wet_path.replace("/wet/", "/warc/").replace(".warc.wet.gz", ".warc.gz")


def reference_dir(cfg: dict, crawl: str) -> Path:
    return resolve(cfg, cfg["paths"].get("reference_dir", "data/reference")) / crawl


def extract_main_text(html: bytes) -> str:
    try:
        import trafilatura
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ImportError(f"The reference command needs trafilatura and its dependencies ({e}). "
                          "Install them with: pip install -r requirements.txt") from e
    return trafilatura.extract(html, **TRAFILATURA_ARGS) or ""


def iter_matching_responses(warc_file: Path, urls: set[str], record_ids: set[str]) -> Iterator[tuple[str, str, bytes]]:
    """Yield (url, record_id, payload) for the HTTP responses whose record ID or URL is requested."""
    with open(warc_file, "rb") as stream:
        for rec in ArchiveIterator(stream):
            if rec.rec_type != "response":
                continue
            rid = rec.rec_headers.get_header("WARC-Record-ID") or ""
            url = rec.rec_headers.get_header("WARC-Target-URI") or ""
            if rid in record_ids or url in urls:
                try:
                    payload = rec.content_stream().read()
                except Exception as e:  # e.g. an unsupported content encoding
                    log.warning("Cannot read the payload of %s: %s", url, e)
                    payload = b""
                yield url, rid, payload


def reference_for_file(raw: pd.DataFrame, warc_file: Path) -> tuple[pd.DataFrame, float]:
    """Match the raw records of one WET file to the HTML in its WARC file and extract the main text.

    A page whose HTML cannot be read or parsed gets an empty reference text.
    """
    by_rid = {}
    if "warc_refers_to" in raw.columns:
        by_rid = {r: u for r, u in zip(raw["warc_refers_to"].fillna(""), raw["url"]) if r}
    found: dict[str, tuple[str, int]] = {}
    seconds = 0.0
    for url, rid, html in iter_matching_responses(warc_file, set(raw["url"]), set(by_rid)):
        key = by_rid.get(rid, url)
        if key in found:
            continue
        t0 = time.perf_counter()
        try:
            text = extract_main_text(html) if html else ""
        except ImportError:
            raise
        except Exception as e:  # malformed HTML; keep going
            log.warning("trafilatura failed on %s: %s", key, e)
            text = ""
        found[key] = (text, len(html))
        seconds += time.perf_counter() - t0
    out = raw[["doc_id", "url"]].copy()
    out["found_in_warc"] = out["url"].isin(found.keys())
    out["html_bytes"] = out["url"].map(lambda u: found.get(u, ("", 0))[1])
    out["ref_text"] = out["url"].map(lambda u: found.get(u, ("", 0))[0])
    return out, seconds


def build_reference(cfg: dict, n_files: int, crawl: str | None = None, keep_warc: bool = False) -> dict:
    ccfg = cfg["collect"]
    crawl = crawl or ccfg["crawl"]
    http = ccfg.get("http", {})
    http_args = {k: http[k] for k in ("timeout", "max_retries", "backoff_seconds") if k in http}
    raw_dir = resolve(cfg, cfg["paths"]["raw_dir"]) / crawl
    tmp_dir = resolve(cfg, cfg["paths"]["tmp_dir"])
    out_dir = reference_dir(cfg, crawl)

    collected = Manifest(raw_dir / "_manifest.jsonl").done
    if not collected:
        raise FileNotFoundError(f"No collected WET files in {raw_dir}. Run the collect command first.")
    # The first n raw files by name: a larger n extends the previous selection
    rows = sorted(collected.values(), key=lambda r: r["parquet"])[:n_files]
    manifest = Manifest(out_dir / "_manifest.jsonl")

    for row in rows:
        if row["wet_path"] in manifest:
            continue
        warc_rel = warc_path_for(row["wet_path"])
        local = tmp_dir / Path(warc_rel).name
        t0 = time.time()
        cc.http_get_to_file(f"{ccfg['base_url']}/{warc_rel}", local, **http_args)
        download_seconds = time.time() - t0
        raw = pd.read_parquet(raw_dir / row["parquet"])
        ref, extract_seconds = reference_for_file(raw, local)
        write_parquet(ref, out_dir / row["parquet"])
        entry = {
            "wet_path": row["wet_path"],
            "warc_path": warc_rel,
            "parquet": row["parquet"],
            "docs": len(ref),
            "found_in_warc": int(ref["found_in_warc"].sum()),
            "empty_extraction": int((ref["found_in_warc"] & (ref["ref_text"] == "")).sum()),
            "warc_bytes": local.stat().st_size,
            "download_seconds": round(download_seconds, 1),
            "extract_seconds": round(extract_seconds, 1),
        }
        manifest.add(entry)
        log.info("%s: %d/%d records found in the WARC file, %d with empty extraction",
                 row["parquet"], entry["found_in_warc"], entry["docs"], entry["empty_extraction"])
        if not keep_warc:
            local.unlink(missing_ok=True)
        time.sleep(http.get("pause_between_files", 0))

    done = list(manifest.done.values())
    return {"files": len(done), "docs": sum(r["docs"] for r in done),
            "found_in_warc": sum(r["found_in_warc"] for r in done),
            "empty_extraction": sum(r["empty_extraction"] for r in done),
            "warc_gb": round(sum(r["warc_bytes"] for r in done) / 1e9, 2)}
