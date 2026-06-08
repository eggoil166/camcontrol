from __future__ import annotations

import logging
import math
import os
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

from camcontrol.tracker.base import HeadAngles, Tracker, TrackerResult, TrackerSettings

logger = logging.getLogger(__name__)


def _default_model_path() -> Path:
    env = os.environ.get("CAMCONTROL_MODEL_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "resources" / "models" / "face_landmarker.task"


def euler_yxz_from_matrix(rotation: np.ndarray) -> tuple[float, float]:
    sy = math.sqrt(rotation[0, 2] ** 2 + rotation[2, 2] ** 2)
    if sy > 1e-6:
        pitch = math.atan2(-rotation[1, 2], sy)
        yaw = math.atan2(rotation[0, 2], rotation[2, 2])
    else:
        pitch = math.atan2(-rotation[1, 2], sy)
        yaw = math.atan2(-rotation[2, 0], rotation[0, 0])
    return math.degrees(yaw), math.degrees(pitch)


class MediaPipeTracker(Tracker):
    def __init__(self) -> None:
        self._landmarker: mp_vision.FaceLandmarker | None = None
        self._mirror = True
        # MediaPipe's VIDEO mode requires strictly increasing timestamps.
        self._last_ts_ms = -1
        self._max_inference_dim: int | None = None

    def start(self, settings: TrackerSettings) -> None:
        if self._landmarker is not None:
            return
        if settings.cv_thread_cap > 0:
            cv2.setNumThreads(settings.cv_thread_cap)
        model_path = Path(settings.model_path) if settings.model_path else _default_model_path()
        if not model_path.exists():
            raise FileNotFoundError(f"Missing model file: {model_path}")
        options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=settings.min_detection_confidence,
            min_face_presence_confidence=settings.min_presence_confidence,
            min_tracking_confidence=settings.min_tracking_confidence,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self._last_ts_ms = -1
        self._max_inference_dim = settings.max_inference_dim

    def stop(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self._last_ts_ms = -1

    def step(self, frame_bgr: np.ndarray, ts_ms: int) -> TrackerResult:
        if self._landmarker is None:
            raise RuntimeError("MediaPipeTracker.step() before start()")

        if ts_ms <= self._last_ts_ms:
            ts_ms = self._last_ts_ms + 1
        self._last_ts_ms = ts_ms

        t0 = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        inference_frame = frame_bgr
        if self._max_inference_dim is not None:
            longest = max(w, h)
            if longest > self._max_inference_dim:
                scale = self._max_inference_dim / longest
                new_w = max(1, round(w * scale))
                new_h = max(1, round(h * scale))
                inference_frame = cv2.resize(
                    frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA
                )
        rgb = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, ts_ms)
        inference_ms = (time.perf_counter() - t0) * 1000.0

        if not result.facial_transformation_matrixes or not result.face_landmarks:
            return TrackerResult(inference_ms=inference_ms)

        matrix = np.asarray(result.facial_transformation_matrixes[0], dtype=np.float64)
        yaw, pitch = euler_yxz_from_matrix(matrix[:3, :3])

        # Frame is mirrored upstream; negate yaw so "look right" maps to +yaw.
        if self._mirror:
            yaw = -yaw

        return TrackerResult(
            angles=HeadAngles(yaw=yaw, pitch=pitch),
            detected=True,
            inference_ms=inference_ms,
        )
