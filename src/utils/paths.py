# src/utils/paths.py
from __future__ import annotations
from pathlib import Path

def project_root() -> Path:
    # Assumes this file is under src/utils/
    return Path(__file__).resolve().parents[2]

def data_dir() -> Path:
    return project_root() / "data"

def pdfs_dir() -> Path:
    return data_dir() / "pdfs"

def indexes_dir() -> Path:
    return data_dir() / "indexes"

def metadata_dir() -> Path:
    d = indexes_dir() / "metadata"
    d.mkdir(parents=True, exist_ok=True)
    return d

def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d