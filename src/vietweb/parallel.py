"""Run a per-document function on several processes.

Used by the stages that treat each document on its own (normalize, boilerplate, heuristic langid, pii).
The number of processes is `parallel.workers` in configs/pipeline.yaml: 1 = no extra process (default),
0 = one per CPU core. The result is the same list, in the same order, as a plain loop.

On Windows, child processes start with "spawn": the function must be defined at module level (bind its
parameters with functools.partial) and every entry point needs an `if __name__ == "__main__":` guard.
"""
from __future__ import annotations

import atexit
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Iterable

import pandas as pd

_POOL: ProcessPoolExecutor | None = None
_POOL_WORKERS = 0


def n_workers(cfg: dict) -> int:
    w = cfg.get("parallel", {}).get("workers", 1)
    w = int(w) if w is not None else 1
    return (os.cpu_count() or 1) if w <= 0 else w


def _pool(workers: int) -> ProcessPoolExecutor:
    """One pool for the whole run, so processes start once instead of once per stage."""
    global _POOL, _POOL_WORKERS
    if _POOL is None or _POOL_WORKERS != workers:
        shutdown()
        _POOL = ProcessPoolExecutor(max_workers=workers)
        _POOL_WORKERS = workers
    return _POOL


def shutdown() -> None:
    global _POOL, _POOL_WORKERS
    if _POOL is not None:
        _POOL.shutdown()
        _POOL, _POOL_WORKERS = None, 0


atexit.register(shutdown)


def pmap(func: Callable[[Any], Any], items: Iterable, cfg: dict) -> list:
    """[func(x) for x in items], split over `parallel.workers` processes when there are enough items."""
    items = list(items)
    p = cfg.get("parallel", {})
    workers = min(n_workers(cfg), len(items))
    if workers <= 1 or len(items) < p.get("min_items", 200):
        return [func(x) for x in items]
    # Chunks of documents per task: large enough to amortize pickling, small enough to balance the load
    chunk = p.get("chunksize") or max(1, min(256, len(items) // (workers * 8)))
    return list(_pool(workers).map(func, items, chunksize=chunk))


def pmap_series(func: Callable[[Any], Any], s: pd.Series, cfg: dict) -> pd.Series:
    """Like s.map(func), with the same index."""
    return pd.Series(pmap(func, s.tolist(), cfg), index=s.index)
