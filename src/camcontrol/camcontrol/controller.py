"""Daemon orchestration (SPEC 2/3).

Owns the camera and the head-point pipeline, plus the arm/disarm state machine,
the foreground-terminal gate, the global hotkey, and the control server that the
``calibrate`` CLI drives. Camera + MediaPipe are imported lazily so the pure
helpers below (and the rest of the package) don't pull in cv2/mediapipe.

Pipeline (while ARMED): frame -> tracker -> (yaw,pitch) -> One Euro per axis ->
calibration -> screen px -> terminal rect -> normalize -> grid cell -> dwell ->
emit. CALIBRATING keeps producing filtered angles for `sample` but never commits.
"""

from __future__ import annotations

import logging
import os
import statistics
import threading
import time
from collections import deque
from enum import StrEnum

from camcontrol import window
from camcontrol.calibration import Calibration, Corners
from camcontrol.config import Config, calibration_path
from camcontrol.control import ControlServer
from camcontrol.dwell import DwellMachine
from camcontrol.filtering.one_euro import OneEuroFilter
from camcontrol.geometry import Grid
from camcontrol.hotkey import HotkeyListener
from camcontrol.intent import Emitter, LoggingEmitter
from camcontrol.service import clear_runtime, write_runtime

logger = logging.getLogger(__name__)

# Minimum detected samples in the rolling buffer before a calibration `sample`
# is trusted.
_MIN_SAMPLE_FRAMES = 3
# How long `sample` waits for enough detected frames before giving up. The camera
# is already running, but begin_calibration clears the buffer, so the first sample
# can land before frames have re-accumulated — wait rather than cry "no face".
_SAMPLE_WAIT_S = 2.0
_SAMPLE_POLL_S = 0.03


class State(StrEnum):
    DISARMED = "disarmed"
    ARMED = "armed"
    CALIBRATING = "calibrating"


class FrameSlot:
    """Thread-safe latest-wins slot: the reader thread overwrites, the pipeline
    reads whatever is freshest (SPEC 2)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame = None

    def set(self, frame) -> None:
        with self._lock:
            self._frame = frame

    def get(self):
        with self._lock:
            return self._frame


def median_angles(samples: list[tuple[float, float]]) -> tuple[float, float]:
    """Component-wise median of (yaw, pitch) samples."""
    yaws = [s[0] for s in samples]
    pitches = [s[1] for s in samples]
    return (statistics.median(yaws), statistics.median(pitches))


class Controller:
    def __init__(
        self,
        config: Config,
        calibration: Calibration,
        emitter: Emitter | None = None,
    ) -> None:
        self.config = config
        self.calibration = calibration
        self._grid = Grid(rows=config.grid_rows, cols=config.grid_cols)
        self._dwell = DwellMachine(
            grid=self._grid,
            emitter=emitter or LoggingEmitter(),
            dwell_ms=config.dwell_ms,
            hysteresis_margin=config.hysteresis_margin,
        )
        self._filter_yaw = OneEuroFilter(config.one_euro_min_cutoff, config.one_euro_beta)
        self._filter_pitch = OneEuroFilter(config.one_euro_min_cutoff, config.one_euro_beta)

        self._lock = threading.Lock()
        self.state = State.DISARMED
        self._prior_state = State.DISARMED  # to restore after calibration
        self._recent: deque[tuple[float, float] | None] = deque(maxlen=15)
        self._last_terminal_s = 0.0
        self._terminal_foreground = False
        # Latest mapped gaze point (normalized screen [0,1]^2) for the GUI patch.
        self._latest_dot = (0.5, 0.5)
        self._dot_detected = False

        self._slot = FrameSlot()
        self._camera = None
        self._tracker = None
        self._reader_thread: threading.Thread | None = None
        self._camera_on = False
        self._running = False

        self._server = ControlServer(self._dispatch, port=config.control_port)
        self._hotkey = HotkeyListener(config.hotkey, self.toggle)

    # -- lifecycle ---------------------------------------------------------

    def run(self) -> None:
        # The detached daemon's stdout/stderr are redirected to the log file by
        # service.start(); configure logging so logger.* actually lands there.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        window.set_dpi_awareness()
        self._running = True
        self._server.start()
        self._hotkey.start()
        write_runtime(os.getpid(), self._server.port)
        logger.info("daemon up (pid=%s, control port=%s)", os.getpid(), self._server.port)
        try:
            self._loop()
        finally:
            self._shutdown()

    def _loop(self) -> None:
        while self._running:
            if self._camera_on:
                frame = self._slot.get()
                if frame is not None:
                    self._process(frame)
                time.sleep(0.005)
            else:
                time.sleep(0.02)

    def _shutdown(self) -> None:
        self._stop_camera()
        self._hotkey.stop()
        self._server.stop()
        clear_runtime()

    # -- arming ------------------------------------------------------------

    def toggle(self) -> None:
        with self._lock:
            if self.state is State.DISARMED:
                self._arm()
            elif self.state is State.ARMED:
                self._disarm()
            # ignore the hotkey mid-calibration

    def _arm(self) -> None:
        self.state = State.ARMED
        self._last_terminal_s = time.monotonic()
        self._start_camera()

    def _disarm(self) -> None:
        self.state = State.DISARMED
        self._stop_camera()

    def _start_camera(self) -> None:
        if self._camera_on:
            return
        # Lazy import keeps cv2/mediapipe out of the import path for pure code.
        from camcontrol.camera import CameraSource
        from camcontrol.tracker.base import TrackerSettings
        from camcontrol.tracker.mediapipe_tracker import MediaPipeTracker

        self._camera = CameraSource()
        if not self._camera.open():
            logger.error("camera failed to open; disarming")
            self.state = State.DISARMED
            self._camera = None
            return
        self._tracker = MediaPipeTracker()
        self._tracker.start(TrackerSettings(max_inference_dim=self.config.max_inference_dim))
        self._filter_yaw.reset()
        self._filter_pitch.reset()
        self._camera_on = True
        self._reader_thread = threading.Thread(target=self._read_frames, daemon=True)
        self._reader_thread.start()

    def _stop_camera(self) -> None:
        self._camera_on = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        if self._tracker is not None:
            self._tracker.stop()
            self._tracker = None
        if self._camera is not None:
            self._camera.close()
            self._camera = None

    def _read_frames(self) -> None:
        while self._camera_on and self._camera is not None:
            ok, frame = self._camera.read()
            if ok:
                self._slot.set(frame)

    # -- pipeline ----------------------------------------------------------

    def _process(self, frame) -> None:
        ts_ms = int(time.monotonic() * 1000)
        result = self._tracker.step(frame, ts_ms)
        if not result.detected:
            self._dot_detected = False
            with self._lock:
                self._recent.append(None)
            return
        now = time.monotonic()
        yaw = self._filter_yaw(result.angles.yaw, now)
        pitch = self._filter_pitch(result.angles.pitch, now)
        # Expose the live mapped dot (normalized over the screen) for the GUI.
        px, py = self.calibration.to_screen_px(yaw, pitch)
        self._latest_dot = (px / self.calibration.screen_w, py / self.calibration.screen_h)
        self._dot_detected = True
        with self._lock:
            self._recent.append((yaw, pitch))
            state = self.state
        if state is State.ARMED:
            self._select(yaw, pitch, now)

    def _select(self, yaw: float, pitch: float, now: float) -> None:
        px, py = self.calibration.to_screen_px(yaw, pitch)
        rect = window.terminal_rect(self.config.terminal_processes)
        if rect is None:
            self._terminal_foreground = False
            if now - self._last_terminal_s >= self.config.idle_timeout_s:
                logger.info("terminal not foreground for %ss; auto-disarming",
                            self.config.idle_timeout_s)
                with self._lock:
                    self._disarm()
            return
        self._terminal_foreground = True
        self._last_terminal_s = now
        x, y = rect.normalize(px, py)
        self._dwell.update(x, y, now * 1000.0)

    # -- control commands --------------------------------------------------

    def _dispatch(self, req: dict) -> dict:
        cmd = req.get("cmd")
        handlers = {
            "status": self._cmd_status,
            "get_dot": self._cmd_get_dot,
            "begin_calibration": self._cmd_begin_calibration,
            "sample": self._cmd_sample,
            "commit_calibration": self._cmd_commit_calibration,
            "cancel_calibration": self._cmd_cancel_calibration,
            "shutdown": self._cmd_shutdown,
        }
        handler = handlers.get(cmd)
        if handler is None:
            return {"ok": False, "error": f"unknown command: {cmd!r}"}
        return handler(req)

    def _cmd_status(self, req: dict) -> dict:
        return {
            "ok": True,
            "state": self.state.value,
            "armed": self.state is State.ARMED,
            "calibrated": not self.calibration.is_default,
            "terminal_foreground": self._terminal_foreground,
            "port": self._server.port,
            "pid": os.getpid(),
        }

    def _cmd_get_dot(self, req: dict) -> dict:
        x, y = self._latest_dot
        return {"ok": True, "detected": self._dot_detected, "x": x, "y": y}

    def _cmd_begin_calibration(self, req: dict) -> dict:
        with self._lock:
            self._prior_state = self.state
            self.state = State.CALIBRATING
            self._recent.clear()
            self._start_camera()
        return {"ok": True}

    def _cmd_sample(self, req: dict) -> dict:
        deadline = time.monotonic() + req.get("timeout", _SAMPLE_WAIT_S)
        while True:
            with self._lock:
                detected = [a for a in self._recent if a is not None]
            if len(detected) >= _MIN_SAMPLE_FRAMES:
                yaw, pitch = median_angles(detected[-_MIN_SAMPLE_FRAMES:])
                return {"ok": True, "detected": True, "yaw": yaw, "pitch": pitch}
            if time.monotonic() >= deadline:
                return {"ok": True, "detected": False}
            time.sleep(_SAMPLE_POLL_S)

    def _cmd_commit_calibration(self, req: dict) -> dict:
        c = req["corners"]
        w, h = req["screen"]
        try:
            corners = Corners(
                tl=tuple(c["tl"]), tr=tuple(c["tr"]), bl=tuple(c["bl"]), br=tuple(c["br"])
            )
            calibration = Calibration.fit_from_corners(corners, screen_w=w, screen_h=h)
        except (KeyError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        calibration.save(calibration_path())
        with self._lock:
            self.calibration = calibration
            self._restore_after_calibration()
        return {"ok": True}

    def _cmd_cancel_calibration(self, req: dict) -> dict:
        with self._lock:
            self._restore_after_calibration()
        return {"ok": True}

    def _cmd_shutdown(self, req: dict) -> dict:
        self._running = False
        return {"ok": True}

    def _restore_after_calibration(self) -> None:
        """Leave CALIBRATING, returning to whatever state we interrupted."""
        if self._prior_state is State.ARMED:
            self.state = State.ARMED
        else:
            self.state = State.DISARMED
            self._stop_camera()
