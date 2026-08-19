"""Shared paths + config loader used by every pipeline step.

Keeping this in one place means the whole pipeline reads the same params.yaml
and writes to the same folders, so runs stay reproducible.
"""
from __future__ import annotations

from pathlib import Path
import yaml

# Project root = parent of the src/ directory this file lives in.
ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH   = ROOT / "config" / "params.yaml"
DATA_RAW      = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DB_PATH       = ROOT / "db" / "finsight.db"
DOCS_GT       = ROOT / "docs" / "ground_truth"
OUTPUTS       = ROOT / "outputs"
OUTPUTS_PBI   = OUTPUTS / "powerbi"
SQL_DIR       = ROOT / "sql"


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    """Load params.yaml into a plain dict."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ensure_dirs() -> None:
    """Make sure every output folder exists before writing to it."""
    for d in (DATA_RAW, DATA_PROCESSED, DB_PATH.parent, DOCS_GT, OUTPUTS, OUTPUTS_PBI):
        d.mkdir(parents=True, exist_ok=True)
