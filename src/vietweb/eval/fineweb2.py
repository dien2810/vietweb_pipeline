"""RQ3: compare keep/drop decisions with FineWeb-2 by URL, and look for personal data left in FineWeb-2.

FineWeb-2 (HuggingFaceFW/fineweb-2) covers 96 Common Crawl snapshots up to April 2024, so the comparison
uses an older snapshot collected and processed with this pipeline (for example CC-MAIN-2024-10). For
Vietnamese, data/vie_Latn (kept, about 130 GB) and data/vie_Latn_removed (removed by the FineWeb-2 filters,
about 178 GB) are Parquet files that are not split by snapshot. They are too large to download, so
`fw2-urls` reads only the url, dump, file_path and (in vie_Latn_removed) filter_reason columns over HTTP (Parquet column chunks, through
huggingface_hub.HfFileSystem), keeps the rows of one snapshot, and skips row groups whose dump statistics
exclude it. Every finished file is recorded in a manifest, so an interrupted run resumes where it stopped.

Commands (see HUONG_DAN_CHAY.md, section 5d):
  python -m vietweb fw2-urls --dump CC-MAIN-2024-10 --probe    # read only the file footers: transfer estimate
  python -m vietweb fw2-urls --dump CC-MAIN-2024-10            # -> data/fineweb2/<dump>/<subset>/*.parquet
  python -m vietweb fw2-compare --dump CC-MAIN-2024-10         # -> outputs/eval/fineweb2_<dump>.md and _examples.csv
  python -m vietweb fw2-pii --n 10000                          # PII patterns on FineWeb-2 vie_Latn text

Interpretation: FineWeb-2 extracts text from WARC HTML with trafilatura, identifies the language with GlotLID
and deduplicates globally across all snapshots before filtering. A URL of ours that is in neither subset was
removed by that global deduplication or not identified as vie_Latn, so it is reported apart from the
agreement on URLs present in both.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from ..config import resolve
from ..reference import warc_path_for
from ..stages.s08_pii import PATTERNS
from .labeling import cohen_kappa

log = logging.getLogger(__name__)

REPO = "datasets/HuggingFaceFW/fineweb-2"
SUBSETS = ("vie_Latn", "vie_Latn_removed")
COLUMNS = ("url", "dump", "file_path", "filter_reason")     # filter_reason exists only in the _removed subsets
PLACEHOLDER_EMAIL_DOMAINS = ("example.com", "example.org")   # FineWeb replaces e-mail addresses with these


def hf_filesystem():
    try:
        from huggingface_hub import HfFileSystem
    except ImportError as e:
        raise ImportError("The fw2 commands need huggingface_hub: pip install huggingface_hub") from e
    return HfFileSystem()


def list_files(fs, subset: str, root: str = REPO) -> list[str]:
    return sorted(fs.glob(f"{root}/data/{subset}/train/*.parquet"))


def _text(v) -> str:
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


def agreement(ours: pd.DataFrame, fw2: pd.DataFrame) -> dict:
    """ours: columns url, kept (bool). fw2: columns url, kept (bool). Only URLs present in both are compared."""
    m = ours[["url", "kept"]].merge(fw2[["url", "kept"]], on="url", suffixes=("_ours", "_fw2"))
    if m.empty:
        return {"overlap": 0}
    a = m["kept_ours"].astype(int).tolist()
    b = m["kept_fw2"].astype(int).tolist()
    return {
        "overlap": len(m),
        "agreement": round(sum(x == y for x, y in zip(a, b)) / len(m), 4),
        "kappa": round(cohen_kappa(a, b), 4),
        "fw2_kept_ours_dropped_pct": round(100 * ((m["kept_fw2"]) & (~m["kept_ours"])).mean(), 2),
        "fw2_dropped_ours_kept_pct": round(100 * ((~m["kept_fw2"]) & (m["kept_ours"])).mean(), 2),
    }


# ---------------------------------------------------------------- fw2-urls: read url/dump/file_path columns

def scan_file(fs, path: str, dump: str, read: bool = True) -> tuple[pd.DataFrame | None, dict]:
    """Rows of one FineWeb-2 Parquet file whose dump equals `dump` (columns url, dump, warc_file).

    With read=False only the footer is read: the result gives the number of row groups that would be read
    and the compressed size of their url/dump/file_path column chunks.
    """
    with fs.open(path, "rb") as f:
        pf = pq.ParquetFile(f)
        md = pf.metadata
        names = pf.schema_arrow.names
        cols = [c for c in COLUMNS if c in names]
        info = {"file": path, "row_groups": md.num_row_groups, "rows": md.num_rows, "read_row_groups": 0,
                "skipped_row_groups": 0, "column_bytes": 0, "text_bytes": 0, "matched": 0, "columns": names}
        ranges = []
        parts = []
        for i in range(md.num_row_groups):
            rg = md.row_group(i)
            chunks = {rg.column(j).path_in_schema: rg.column(j) for j in range(rg.num_columns)}
            info["text_bytes"] += chunks["text"].total_compressed_size if "text" in chunks else 0
            st = chunks["dump"].statistics if "dump" in chunks else None
            if st is not None and st.has_min_max:
                lo, hi = _text(st.min), _text(st.max)
                ranges.append((lo, hi))
                if not lo <= dump <= hi:
                    info["skipped_row_groups"] += 1
                    continue
            info["read_row_groups"] += 1
            info["column_bytes"] += sum(chunks[c].total_compressed_size for c in cols if c in chunks)
            if read:
                t = pf.read_row_group(i, columns=cols).to_pandas()
                parts.append(t[t["dump"] == dump])
        info["dump_ranges_sample"] = ranges if len(ranges) <= 6 else ranges[:3] + ["..."] + ranges[-3:]
    if not read:
        return None, info
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)
    if "file_path" in df.columns:
        df["warc_file"] = df["file_path"].astype(str).str.rsplit("/", n=1).str[-1]
        df = df.drop(columns="file_path")
    info["matched"] = len(df)
    return df, info


def fineweb2_dir(cfg: dict, dump: str) -> Path:
    return resolve(cfg, cfg["paths"].get("fineweb2_dir", "data/fineweb2")) / dump


def _done(manifest: Path) -> dict[str, dict]:
    if not manifest.exists():
        return {}
    rows = [json.loads(line) for line in open(manifest, encoding="utf-8") if line.strip()]
    return {r["file"]: r for r in rows}


def fw2_urls(cfg: dict, dump: str, subsets=SUBSETS, probe: bool = False, max_files: int | None = None,
             fs=None, root: str = REPO, retries: int = 3) -> dict:
    fs = fs or hf_filesystem()
    out_dir = fineweb2_dir(cfg, dump)
    summary = {}
    for subset in subsets:
        files = list_files(fs, subset, root)[:max_files]
        if not files:
            raise FileNotFoundError(f"No Parquet files for {subset} under {root}")
        if probe:
            _, info = scan_file(fs, files[0], dump, read=False)
            n = len(files)
            summary[subset] = {
                "files": n, "first_file": files[0], "columns": info["columns"],
                "row_groups_in_first_file": info["row_groups"], "rows_in_first_file": info["rows"],
                "row_groups_to_read_in_first_file": info["read_row_groups"],
                "dump_ranges_sample": info["dump_ranges_sample"],
                "estimated_transfer_gb": round(n * info["column_bytes"] / 1e9, 2),
                "text_column_gb_in_first_file": round(info["text_bytes"] / 1e9, 2)}
            continue
        sub_dir = out_dir / subset
        sub_dir.mkdir(parents=True, exist_ok=True)
        manifest = sub_dir / "_manifest.jsonl"
        done = _done(manifest)
        for k, path in enumerate(files, 1):
            if path in done:
                continue
            for attempt in range(1, retries + 1):
                try:
                    t0 = time.time()
                    df, info = scan_file(fs, path, dump)
                    break
                except Exception as e:  # network errors: retry with a pause
                    if attempt == retries:
                        raise
                    log.warning("%s: %s; retrying in %d s", path, e, 30 * attempt)
                    time.sleep(30 * attempt)
            df.to_parquet(sub_dir / Path(path).name, index=False)
            entry = {k2: info[k2] for k2 in ("file", "rows", "row_groups", "read_row_groups", "skipped_row_groups",
                                              "column_bytes", "matched")}
            entry["seconds"] = round(time.time() - t0, 1)
            with open(manifest, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            log.info("%s %d/%d %s: %d rows of %s (%.2f GB read, %.0f s)", subset, k, len(files), Path(path).name,
                     entry["matched"], dump, entry["column_bytes"] / 1e9, entry["seconds"])
        done = _done(manifest)
        summary[subset] = {"files_done": len(done), "files_total": len(files),
                           "rows_matched": sum(r["matched"] for r in done.values()),
                           "gb_read": round(sum(r["column_bytes"] for r in done.values()) / 1e9, 2)}
    return summary


# ---------------------------------------------------------------- fw2-compare

def load_fw2(cfg: dict, dump: str) -> pd.DataFrame:
    """url, kept (True for vie_Latn, False for vie_Latn_removed), warc_file, filter_reason (removed rows)."""
    parts = []
    for subset, kept in (("vie_Latn", True), ("vie_Latn_removed", False)):
        d = fineweb2_dir(cfg, dump) / subset
        files = sorted(d.glob("*.parquet")) if d.exists() else []
        if not files:
            raise FileNotFoundError(f"No FineWeb-2 rows in {d}. Run: python -m vietweb fw2-urls --dump {dump}")
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        parts.append(df.assign(kept=kept))
    return pd.concat(parts, ignore_index=True)


def our_warc_files(cfg: dict, dump: str) -> set[str]:
    manifest = resolve(cfg, cfg["paths"]["raw_dir"]) / dump / "_manifest.jsonl"
    rows = [json.loads(line) for line in open(manifest, encoding="utf-8") if line.strip()]
    return {warc_path_for(r["wet_path"]).rsplit("/", 1)[-1] for r in rows}


def load_ours(cfg: dict, dump: str) -> pd.DataFrame:
    proc = resolve(cfg, cfg["paths"]["processed_dir"])
    cols = ["url", "snapshot", "text"]
    kept = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted((proc / "kept").glob("*.parquet"))])
    dropped = pd.concat([pd.read_parquet(f, columns=cols + ["drop_stage", "drop_reason"])
                         for f in sorted((proc / "dropped").glob("*.parquet"))])
    ours = pd.concat([kept.assign(kept=True), dropped.assign(kept=False)], ignore_index=True)
    ours = ours[ours["snapshot"] == dump]
    if ours.empty:
        raise ValueError(f"data/processed has no documents of {dump}. Run: python -m vietweb run --crawl {dump}")
    return ours.drop_duplicates("url")


def compare(cfg: dict, dump: str, n_examples: int = 15) -> str:
    ours = load_ours(cfg, dump)
    fw = load_fw2(cfg, dump).drop_duplicates("url")
    files = our_warc_files(cfg, dump)
    fw_ours = fw[fw["warc_file"].isin(files)] if "warc_file" in fw.columns else fw
    if "filter_reason" not in fw.columns:
        fw["filter_reason"] = None
    m = ours.merge(fw[["url", "kept", "filter_reason"]].rename(columns={"kept": "fw2_kept", "filter_reason": "fw2_reason"}),
                   on="url", how="left")
    m["fw2"] = m["fw2_kept"].map({True: "kept", False: "removed"}).fillna("absent")
    both = m[m["fw2"] != "absent"]
    ag = agreement(both[["url", "kept"]], both[["url", "fw2_kept"]].rename(columns={"fw2_kept": "kept"}))
    seen = set(ours["url"])
    fw_missing = fw_ours[~fw_ours["url"].isin(seen)]

    cross = pd.crosstab(m["kept"].map({True: "ours kept", False: "ours dropped"}), m["fw2"])
    by_reason = (m[(~m["kept"]) & (m["fw2"] == "kept")]["drop_reason"].value_counts()
                 .rename_axis("our drop reason").reset_index(name="pages FineWeb-2 kept"))
    absent_by = m.groupby("kept")["fw2"].apply(lambda s: round(100 * (s == "absent").mean(), 1))
    removed = m[m["fw2"] == "removed"]
    fw2_reasons = (removed.assign(ours=removed["kept"].map({True: "ours kept", False: "ours dropped"}))
                   .pivot_table(index="fw2_reason", columns="ours", values="url", aggfunc="count", fill_value=0))
    if len(fw2_reasons):
        fw2_reasons = fw2_reasons.assign(total=fw2_reasons.sum(axis=1)).sort_values("total", ascending=False)
    both_dropped = m[(~m["kept"]) & (m["fw2"] == "removed")]
    pairs = (both_dropped.groupby(["drop_reason", "fw2_reason"]).size().sort_values(ascending=False).head(15)
             .rename("pages").reset_index())

    lines = [f"# Comparison with FineWeb-2, {dump}", "",
             f"- Our documents (collected with CLD2 'vie' and processed): {len(ours)} from {len(files)} WARC files",
             f"- FineWeb-2 rows of {dump}: {len(fw)}; from the same {len(files)} WARC files: {len(fw_ours)} "
             f"(kept {int(fw_ours['kept'].sum())}, removed {int((~fw_ours['kept']).sum())})",
             f"- Our URLs present in FineWeb-2 (kept or removed): {len(both)} ({100 * len(both) / len(m):.1f}%); "
             f"absent: {int((m['fw2'] == 'absent').sum())} (global deduplication, or not identified as vie_Latn)",
             f"- Absent among the documents we kept: {absent_by.get(True, float('nan'))}%; "
             f"among those we dropped: {absent_by.get(False, float('nan'))}%",
             f"- FineWeb-2 Vietnamese documents from our WARC files that our collection never saw "
             f"(CLD2 without 'vie', or under 200 characters): {len(fw_missing)} "
             f"(of which FineWeb-2 kept {int(fw_missing['kept'].sum())})", "",
             "## Agreement on URLs present in both", "",
             f"- Overlap: {ag.get('overlap', 0)}; agreement A = {ag.get('agreement')}; Cohen's kappa = {ag.get('kappa')}",
             f"- FineWeb-2 kept, we dropped: {ag.get('fw2_kept_ours_dropped_pct')}% of the overlap; "
             f"FineWeb-2 removed, we kept: {ag.get('fw2_dropped_ours_kept_pct')}%", "",
             "```", cross.to_string(), "```", "",
             "## Pages FineWeb-2 kept but we dropped, by our drop reason", "",
             "```", by_reason.to_string(index=False) if len(by_reason) else "(none)", "```", "",
             "## Pages FineWeb-2 removed, by FineWeb-2 filter_reason and our decision", "",
             "```", fw2_reasons.to_string() if len(fw2_reasons) else "(none)", "```", "",
             "## Pages both removed: our drop reason x FineWeb-2 filter_reason (top 15)", "",
             "```", pairs.to_string(index=False) if len(pairs) else "(none)", "```", ""]
    md = "\n".join(lines)

    ex = []
    for name, sel in (("fw2 kept, ours dropped", (~m["kept"]) & (m["fw2"] == "kept")),
                      ("fw2 removed, ours kept", m["kept"] & (m["fw2"] == "removed")),
                      ("both kept", m["kept"] & (m["fw2"] == "kept"))):
        g = m[sel]
        ex.append(g.sample(n=min(n_examples, len(g)), random_state=cfg.get("seed", 42)).assign(group=name))
    ex = pd.concat(ex, ignore_index=True)
    ex["text"] = ex["text"].str.slice(0, 1500)
    out = resolve(cfg, cfg["paths"]["eval_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / f"fineweb2_{dump}.md").write_text(md, encoding="utf-8")
    ex[["group", "url", "drop_stage", "drop_reason", "fw2_reason", "text"]].assign(note="").to_csv(
        out / f"fineweb2_{dump}_examples.csv", index=False, encoding="utf-8-sig")
    return md + f"\nWritten: {out / f'fineweb2_{dump}.md'} and fineweb2_{dump}_examples.csv\n"


# ---------------------------------------------------------------- fw2-pii

def count_pii(texts: pd.Series) -> dict:
    """Documents with at least one match and total matches per pattern of stage 8."""
    res = {}
    for name, (pat, _) in PATTERNS.items():
        hits = texts.map(lambda t: [m for m in pat.findall(t)
                                    if not (name == "email" and m.lower().endswith(PLACEHOLDER_EMAIL_DOMAINS))])
        res[name] = {"docs": int((hits.map(len) > 0).sum()), "matches": int(hits.map(len).sum())}
    return res


def fw2_pii(cfg: dict, n: int = 10_000, subset: str = "vie_Latn", n_files: int = 10, fs=None, root: str = REPO) -> str:
    """Read the text of a few row groups spread over `n_files` files until `n` documents, then count PII matches."""
    fs = fs or hf_filesystem()
    files = list_files(fs, subset, root)
    step = max(1, len(files) // n_files)
    picked = files[::step][:n_files]
    per_file = -(-n // len(picked))
    parts, read_bytes = [], 0
    for path in picked:
        with fs.open(path, "rb") as f:
            pf = pq.ParquetFile(f)
            got = 0
            for i in range(pf.metadata.num_row_groups):
                rg = pf.metadata.row_group(i)
                read_bytes += sum(rg.column(j).total_compressed_size for j in range(rg.num_columns)
                                  if rg.column(j).path_in_schema in ("text", "url", "dump"))
                t = pf.read_row_group(i, columns=["url", "dump", "text"]).to_pandas()
                parts.append(t.head(per_file - got))
                got += len(parts[-1])
                if got >= per_file:
                    break
        log.info("%s: %d documents", path, got)
    docs = pd.concat(parts, ignore_index=True).head(n)
    res = count_pii(docs["text"])
    lines = [f"# PII patterns on FineWeb-2 {subset}", "",
             f"{len(docs)} documents from {len(picked)} files, dumps {docs['dump'].min()} to {docs['dump'].max()}; "
             f"{read_bytes / 1e9:.2f} GB read", "",
             "| pattern | documents with a match | % | matches |", "|---|---:|---:|---:|"]
    for name, r in res.items():
        lines.append(f"| {name} | {r['docs']} | {100 * r['docs'] / len(docs):.2f} | {r['matches']} |")
    lines += ["", "FineWeb-2 anonymises e-mail and IP addresses; matches of example.com / example.org are not counted.",
              "Phone numbers and 12-digit numbers are not anonymised by FineWeb-2. The patterns over-match "
              "(see LUAT_LOC.md, section 8), so read the counts as upper bounds and check a sample by hand."]
    md = "\n".join(lines)
    out = resolve(cfg, cfg["paths"]["eval_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / f"fineweb2_pii_{subset}.md").write_text(md, encoding="utf-8")
    sample = docs.assign(**{f"has_{k}": docs["text"].map(lambda t, p=v[0]: bool(p.search(t))) for k, v in PATTERNS.items()})
    sample["text"] = sample["text"].str.slice(0, 1500)
    sample[sample[[f"has_{k}" for k in PATTERNS]].any(axis=1)].head(200).to_csv(
        out / f"fineweb2_pii_{subset}_examples.csv", index=False, encoding="utf-8-sig")
    return md + f"\nWritten: {out / f'fineweb2_pii_{subset}.md'} and the _examples.csv file next to it\n"
