"""Serve defaults + filesystem paths.

``Config`` holds the handful of knobs the serve loop needs (overridable via CLI
flags). Calibration is persisted under ``~/.camcontrol/`` (override the base dir
with the ``CAMCONTROL_HOME`` env var).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8765
    camera_index: int = 0
    one_euro_min_cutoff: float = 1.0
    one_euro_beta: float = 0.05
    max_inference_dim: int = 256


def config_dir() -> Path:
    """Base dir for calibration (and any future state)."""
    env = os.environ.get("CAMCONTROL_HOME")
    return Path(env) if env else Path.home() / ".camcontrol"


def calibration_path() -> Path:
    return config_dir() / "calibration.json"
