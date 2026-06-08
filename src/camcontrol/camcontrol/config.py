"""Runtime config + filesystem paths (SPEC 10).

All knobs live in ``Config`` with spec defaults; persisted as JSON under
``~/.camcontrol/`` (override the base dir with the ``CAMCONTROL_HOME`` env var).
``load`` merges a partial file onto the defaults and ignores unknown keys so
config files survive version skew.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Config:
    grid_rows: int = 1
    grid_cols: int = 2
    dwell_ms: int = 400
    hysteresis_margin: float = 0.04
    one_euro_min_cutoff: float = 1.0
    one_euro_beta: float = 0.05
    idle_timeout_s: float = 30
    hotkey: str = "ctrl+alt+h"
    terminal_processes: list[str] = field(default_factory=lambda: ["WindowsTerminal.exe"])
    control_port: int = 8765
    max_inference_dim: int = 256

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Config:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def load_or_default(cls, path: str | Path) -> Config:
        path = Path(path)
        return cls.load(path) if path.exists() else cls()


def config_dir() -> Path:
    """Base dir for config + calibration + runtime files."""
    env = os.environ.get("CAMCONTROL_HOME")
    return Path(env) if env else Path.home() / ".camcontrol"


def config_path() -> Path:
    return config_dir() / "config.json"


def calibration_path() -> Path:
    return config_dir() / "calibration.json"


def daemon_runtime_path() -> Path:
    """PID + control port of the running daemon."""
    return config_dir() / "daemon.json"


def log_path() -> Path:
    return config_dir() / "daemon.log"
