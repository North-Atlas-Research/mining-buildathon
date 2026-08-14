from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    return Path(os.environ.get("PROJECT_DATA_ROOT", "/workspace/data"))


def raw_dir() -> Path:
    return data_root() / "Raw"


def interim_dir() -> Path:
    return data_root() / "Interim"


def processed_dir() -> Path:
    return data_root() / "Processed"


def outputs_dir() -> Path:
    return data_root() / "Outputs"


def scratch_dir() -> Path:
    return data_root() / "Scratch"


def cache_dir() -> Path:
    return data_root() / "Cache"
