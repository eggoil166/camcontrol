"""4-corner calibration: head angles -> screen pixels (SPEC 5).

Capture (yaw, pitch) while looking at each screen corner, then fit a per-axis
affine map. The fit captures gain, offset, and sign at once. A placeholder
``default()`` lets the daemon map a dot before any real calibration is done.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# The order corners are captured in, shared by the CLI and GUI calibration flows.
CORNER_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("tl", "TOP-LEFT"),
    ("tr", "TOP-RIGHT"),
    ("bl", "BOTTOM-LEFT"),
    ("br", "BOTTOM-RIGHT"),
)

# Placeholder neutral-centered range: a comfortable head turn (degrees).
_DEFAULT_YAW = 12.0
_DEFAULT_PITCH = 8.0
_MIN_SPAN = 1e-3  # reject near-degenerate fits


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


@dataclass
class Corners:
    """(yaw, pitch) in degrees captured at each screen corner."""

    tl: tuple[float, float]
    tr: tuple[float, float]
    bl: tuple[float, float]
    br: tuple[float, float]


@dataclass
class Calibration:
    yaw_left: float
    yaw_right: float
    pitch_top: float
    pitch_bot: float
    screen_w: int
    screen_h: int
    is_default: bool = False

    @classmethod
    def fit_from_corners(
        cls, corners: Corners, screen_w: int, screen_h: int, *, is_default: bool = False
    ) -> Calibration:
        yaw_left = (corners.tl[0] + corners.bl[0]) / 2.0
        yaw_right = (corners.tr[0] + corners.br[0]) / 2.0
        pitch_top = (corners.tl[1] + corners.tr[1]) / 2.0
        pitch_bot = (corners.bl[1] + corners.br[1]) / 2.0
        if abs(yaw_right - yaw_left) < _MIN_SPAN or abs(pitch_bot - pitch_top) < _MIN_SPAN:
            raise ValueError(
                "degenerate calibration: corner angles too close to span the screen"
            )
        return cls(yaw_left, yaw_right, pitch_top, pitch_bot, screen_w, screen_h, is_default)

    @classmethod
    def default(cls, screen_w: int, screen_h: int) -> Calibration:
        corners = Corners(
            tl=(-_DEFAULT_YAW, _DEFAULT_PITCH),
            tr=(_DEFAULT_YAW, _DEFAULT_PITCH),
            bl=(-_DEFAULT_YAW, -_DEFAULT_PITCH),
            br=(_DEFAULT_YAW, -_DEFAULT_PITCH),
        )
        return cls.fit_from_corners(corners, screen_w, screen_h, is_default=True)

    def to_screen_px(self, yaw: float, pitch: float) -> tuple[float, float]:
        xn = _clamp01((yaw - self.yaw_left) / (self.yaw_right - self.yaw_left))
        yn = _clamp01((pitch - self.pitch_top) / (self.pitch_bot - self.pitch_top))
        return (xn * self.screen_w, yn * self.screen_h)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Calibration:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)
