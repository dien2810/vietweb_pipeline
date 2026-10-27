"""SKELETON (weeks 8-10): orchestration with Prefect.

Install: pip install prefect
Trial run: python flows/pipeline_flow.py
Each task calls the same functions as the CLI, so results match manual runs; Prefect adds
retries on failure, per-run logs, and scheduling.
This file is NOT tested yet.
"""
from prefect import flow, task

from vietweb.collect import collect
from vietweb.config import load_config
from vietweb.pipeline import run_pipeline


@task(retries=3, retry_delay_seconds=60)
def collect_task(cfg: dict, n_files: int, crawl: str | None = None) -> dict:
    return collect(cfg, n_files, crawl)


@task
def pipeline_task(cfg: dict) -> None:
    run_pipeline(cfg)


@flow(name="vietweb-pipeline")
def vietweb_flow(n_files: int = 10, crawl: str | None = None, config: str = "configs/pipeline.yaml"):
    cfg = load_config(config)
    collect_task(cfg, n_files, crawl)
    pipeline_task(cfg)


if __name__ == "__main__":
    vietweb_flow(n_files=10)
