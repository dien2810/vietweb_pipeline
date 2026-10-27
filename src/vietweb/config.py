"""Load the YAML configuration and word-list files (stop words, blocklists)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = "configs/pipeline.yaml"


def repo_root() -> Path:
    """Repository root (the folder containing pyproject.toml), searched upward from the working directory."""
    here = Path.cwd().resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").exists() and (p / "configs").exists():
            return p
    return here


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    path = Path(path)
    if not path.is_absolute():
        path = repo_root() / path
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = str(repo_root())
    return cfg


def resolve(cfg: dict, rel: str | Path) -> Path:
    """Turn a path from the configuration into an absolute path relative to the repository root."""
    p = Path(rel)
    return p if p.is_absolute() else Path(cfg.get("_root", ".")) / p


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_wordlist(path: str | Path) -> list[str]:
    """Read one item per line, skipping blank lines and lines starting with '#'."""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line.lower())
    return items
