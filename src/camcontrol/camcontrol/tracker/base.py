from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class HeadAngles:
    yaw: float = 0.0
    pitch: float = 0.0


@dataclass
class TrackerResult:
    angles: HeadAngles = field(default_factory=HeadAngles)
    detected: bool = False
    inference_ms: float = 0.0


@dataclass
class TrackerSettings:
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    model_path: str | None = None
    max_inference_dim: int | None = None
    cv_thread_cap: int = 0


class Tracker(ABC):
    @abstractmethod
    def start(self, settings: TrackerSettings) -> None: ...

    @abstractmethod
    def step(self, frame_bgr: np.ndarray, ts_ms: int) -> TrackerResult: ...

    @abstractmethod
    def stop(self) -> None: ...
