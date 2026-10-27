"""Stage 1: download the WET path list, download WET files, and read their text records.

Common Crawl data can be downloaded over HTTPS from https://data.commoncrawl.org without an AWS account.
The server may return 503 when it receives too many requests, so every request is retried
with exponential backoff.
"""
from __future__ import annotations

import gzip
import hashlib
import logging
import random
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

import requests
from warcio.archiveiterator import ArchiveIterator

log = logging.getLogger(__name__)

USER_AGENT = "vietweb-student-project/0.1 (UIT data processing course)"


def http_get_to_file(url: str, dest: Path, timeout: int = 120, max_retries: int = 6,
                     backoff_seconds: float = 5.0) -> Path:
    """Download `url` to `dest` (via a .part file, then rename); retry on network errors and 5xx responses."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, max_retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout,
                              headers={"User-Agent": USER_AGENT}) as r:
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                expected = int(r.headers.get("Content-Length", 0))
                with open(part, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            if expected and part.stat().st_size != expected:
                raise IOError(f"incomplete download: {part.stat().st_size}/{expected} bytes")
            part.replace(dest)
            return dest
        except (requests.RequestException, IOError) as e:
            wait = backoff_seconds * (2 ** (attempt - 1))
            log.warning("Download failed (%s), attempt %d/%d, waiting %.0fs: %s", e, attempt, max_retries, wait, url)
            if attempt == max_retries:
                raise
            time.sleep(wait)
    raise RuntimeError("unreachable")


def download_wet_paths(crawl: str, base_url: str, dest_dir: Path, **http) -> Path:
    """Download wet.paths.gz (the list of WET file paths) for one crawl snapshot."""
    dest = dest_dir / f"{crawl}.wet.paths.gz"
    if dest.exists():
        log.info("%s already exists, skipping download", dest)
        return dest
    url = f"{base_url}/crawl-data/{crawl}/wet.paths.gz"
    return http_get_to_file(url, dest, **http)


def read_wet_paths(paths_file: Path) -> list[str]:
    with gzip.open(paths_file, "rt", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def select_paths(paths: list[str], n: int, how: str = "random", seed: int = 42) -> list[str]:
    """Pick n WET files. 'random' uses a fixed seed, so a larger n extends the previous selection."""
    if how == "first":
        return paths[:n]
    rng = random.Random(seed)
    return rng.sample(paths, min(n, len(paths)))


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def doc_id(url: str, record_id: str) -> str:
    return hashlib.sha1(f"{record_id}|{url}".encode("utf-8")).hexdigest()[:20]


def iter_wet_records(wet_file: Path, language: str | None = "vie", min_chars: int = 0,
                     snapshot: str = "") -> Iterator[dict]:
    """Yield the 'conversion' records of a WET file.

    Only records whose WARC-Identified-Content-Language contains `language` are returned (CLD2 pre-filter).
    Pass language=None to get every record (useful to measure how many Vietnamese pages the pre-filter misses).
    """
    with open(wet_file, "rb") as stream:
        for rec in ArchiveIterator(stream):
            if rec.rec_type != "conversion":
                continue
            langs = rec.rec_headers.get_header("WARC-Identified-Content-Language") or ""
            if language and language not in langs.split(","):
                continue
            text = rec.content_stream().read().decode("utf-8", errors="replace")
            if len(text) < min_chars:
                continue
            url = rec.rec_headers.get_header("WARC-Target-URI") or ""
            rid = rec.rec_headers.get_header("WARC-Record-ID") or ""
            yield {
                "doc_id": doc_id(url, rid),
                "url": url,
                "domain": domain_of(url),
                "snapshot": snapshot,
                "warc_record_id": rid,
                # ID of the WARC response record this text was converted from (used to find the HTML)
                "warc_refers_to": rec.rec_headers.get_header("WARC-Refers-To") or "",
                "crawl_date": rec.rec_headers.get_header("WARC-Date") or "",
                "cld2_langs": langs,
                "text": text,
            }


def count_records(wet_file: Path) -> int:
    """Count all text records in a WET file (used to compute the share of Vietnamese pages)."""
    n = 0
    with open(wet_file, "rb") as stream:
        for rec in ArchiveIterator(stream):
            if rec.rec_type == "conversion":
                n += 1
    return n
