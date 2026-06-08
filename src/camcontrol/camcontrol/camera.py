from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraInfo:
    index: int
    name: str
    backend: str = ""

    @property
    def display_label(self) -> str:
        return f"{self.index}: {self.name}" if self.name else f"Camera {self.index}"


def enumerate_cameras() -> list[CameraInfo]:
    cams: list[CameraInfo] = []
    if sys.platform == "win32":
        try:
            from cv2_enumerate_cameras import enumerate_cameras as _enum

            for c in _enum():
                cams.append(
                    CameraInfo(index=c.index, name=c.name or "Unknown", backend=str(c.backend))
                )
        except Exception as exc:
            logger.debug("cv2-enumerate-cameras unavailable, falling back to probe: %s", exc)

    if not cams:
        for idx in range(5):
            cap = cv2.VideoCapture(idx)
            opened = cap.isOpened()
            cap.release()
            if opened:
                cams.append(CameraInfo(index=idx, name=f"Camera {idx}"))

    return cams


class CameraSource:
    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: float = 60.0,
        mirror: bool = True,
    ) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.mirror = mirror
        self._cap: cv2.VideoCapture | None = None
        self._backend_name: str = ""
        self._fourcc_negotiated: str = ""

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def actual_size(self) -> tuple[int, int]:
        if self._cap is None:
            return (self.width, self.height)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or self.width)
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or self.height)
        return (w, h)

    @property
    def actual_fps(self) -> float:
        if self._cap is None:
            return self.fps
        v = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        return v if v > 0 else self.fps

    @property
    def fourcc_name(self) -> str:
        return self._fourcc_negotiated

    def open(self) -> bool:
        if self.is_open:
            return True

        backends: Iterable[tuple[int, str]]
        if sys.platform == "win32":
            backends = (
                (cv2.CAP_ANY, "ANY"),
                (cv2.CAP_MSMF, "MSMF"),
                (cv2.CAP_DSHOW, "DSHOW"),
            )
        else:
            backends = ((cv2.CAP_ANY, "ANY"),)

        for backend, name in backends:
            try:
                cap = cv2.VideoCapture(self.index, backend)
            except cv2.error as exc:
                logger.debug("VideoCapture(%d, %s) raised: %s", self.index, name, exc)
                continue
            if not cap.isOpened():
                cap.release()
                continue
            try:
                # MJPG must be requested before resolution + FPS to unlock 60fps:
                # USB webcams default to YUYV which is bandwidth-capped at 30fps.
                mjpg = cv2.VideoWriter_fourcc(*"MJPG")
                cap.set(cv2.CAP_PROP_FOURCC, mjpg)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except cv2.error as exc:
                logger.warning(
                    "Camera %d on %s failed during property set: %s — trying next backend",
                    self.index, name, exc,
                )
                cap.release()
                continue
            self._cap = cap
            self._backend_name = name
            try:
                raw = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
                self._fourcc_negotiated = (
                    "".join(chr((raw >> (8 * i)) & 0xFF) for i in range(4)).strip()
                    if raw
                    else ""
                )
            except (cv2.error, ValueError):
                self._fourcc_negotiated = ""
            logger.info(
                "Camera index=%d opened via %s at %dx%d @ %.0f fps (%s)",
                self.index, name, *self.actual_size,
                self.actual_fps, self._fourcc_negotiated or "?",
            )
            return True

        logger.error("Could not open camera index=%d on any backend.", self.index)
        return False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None:
            return False, None
        try:
            ok, frame = self._cap.read()
        except cv2.error as exc:
            logger.debug("VideoCapture.read raised: %s", exc)
            return False, None
        if not ok or frame is None:
            return False, None
        try:
            if self.mirror:
                frame = cv2.flip(frame, 1)
        except cv2.error as exc:
            logger.debug("cv2.flip raised: %s", exc)
            return False, None
        return True, frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._backend_name = ""
            self._fourcc_negotiated = ""

    def __enter__(self) -> CameraSource:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = ["CameraInfo", "CameraSource", "enumerate_cameras"]
