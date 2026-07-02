"""CLI: stream head-tracking events over a port, or calibrate.

Two commands, both foreground and cross-platform (no daemon, no OS-specific code):
- ``serve``     : camera -> tracker -> One Euro -> calibration -> broadcast events.
- ``calibrate`` : interactive 4-corner capture saved to ~/.camcontrol/calibration.json.
"""

from __future__ import annotations

import argparse
import logging
import statistics
import time

from camcontrol.calibration import CORNER_SEQUENCE, Calibration, Corners
from camcontrol.config import Config, calibration_path
from camcontrol.server import EventServer

logger = logging.getLogger(__name__)


def make_event(
    t: float,
    detected: bool,
    raw: tuple[float, float] | None = None,
    filtered: tuple[float, float] | None = None,
    screen: tuple[float, float] | None = None,
) -> dict:
    """Build one JSON-serializable event. Undetected frames carry only t+detected."""
    if not detected:
        return {"t": t, "detected": False}
    return {
        "t": t,
        "detected": True,
        "raw": {"yaw": raw[0], "pitch": raw[1]},
        "filtered": {"yaw": filtered[0], "pitch": filtered[1]},
        "screen": {"x": screen[0], "y": screen[1]},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="camcontrol", description="Head-tracking event stream.")
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="stream head-tracking events over a TCP port")
    serve.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost)")
    serve.add_argument("--port", type=int, default=8765, help="TCP port (default: 8765)")
    serve.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")
    cal = sub.add_parser("calibrate", help="interactive 4-corner calibration")
    cal.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")
    return parser


def _load_calibration() -> Calibration:
    path = calibration_path()
    if path.exists():
        return Calibration.load(path)
    logger.warning(
        "no calibration at %s; using a placeholder. Run `camcontrol calibrate`.", path
    )
    return Calibration.default()


def _open_pipeline(camera_index: int, cfg: Config):
    """Open camera + tracker (lazy import keeps cv2/mediapipe out of the import path)."""
    from camcontrol.camera import CameraSource
    from camcontrol.tracker.base import TrackerSettings
    from camcontrol.tracker.mediapipe_tracker import MediaPipeTracker

    cam = CameraSource(index=camera_index)
    if not cam.open():
        return None, None
    tracker = MediaPipeTracker()
    tracker.start(TrackerSettings(max_inference_dim=cfg.max_inference_dim))
    return cam, tracker


def _serve(host: str, port: int, camera_index: int) -> None:
    from camcontrol.filtering.one_euro import OneEuroFilter

    cfg = Config()
    calibration = _load_calibration()
    cam, tracker = _open_pipeline(camera_index, cfg)
    if cam is None:
        print("Could not open the camera. Is another app using it?")
        return
    f_yaw = OneEuroFilter(cfg.one_euro_min_cutoff, cfg.one_euro_beta)
    f_pitch = OneEuroFilter(cfg.one_euro_min_cutoff, cfg.one_euro_beta)
    server = EventServer(host=host, port=port)
    server.start()
    print(f"Serving head-tracking events on {host}:{server.port} (Ctrl+C to stop).")
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue
            result = tracker.step(frame, int(time.monotonic() * 1000))
            now = time.time()
            if not result.detected:
                server.broadcast(make_event(now, False))
                continue
            raw = (result.angles.yaw, result.angles.pitch)
            mono = time.monotonic()
            filtered = (f_yaw(raw[0], mono), f_pitch(raw[1], mono))
            screen = calibration.to_screen(*filtered)
            server.broadcast(make_event(now, True, raw=raw, filtered=filtered, screen=screen))
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        tracker.stop()
        cam.close()


def _median_angles(samples: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        statistics.median(s[0] for s in samples),
        statistics.median(s[1] for s in samples),
    )


def _capture_corner(cam, tracker, label: str) -> tuple[float, float]:
    while True:
        input(f"  Look at the {label} corner and press ENTER...")
        samples: list[tuple[float, float]] = []
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and len(samples) < 5:
            ok, frame = cam.read()
            if not ok:
                continue
            result = tracker.step(frame, int(time.monotonic() * 1000))
            if result.detected:
                samples.append((result.angles.yaw, result.angles.pitch))
        if len(samples) >= 3:
            return _median_angles(samples)
        print("  No face detected — hold still and try again.")


def _calibrate(camera_index: int) -> None:
    cfg = Config()
    cam, tracker = _open_pipeline(camera_index, cfg)
    if cam is None:
        print("Could not open the camera. Is another app using it?")
        return
    print("Calibration: look at each corner, then press ENTER.\n")
    try:
        captured = {key: _capture_corner(cam, tracker, label) for key, label in CORNER_SEQUENCE}
        calibration = Calibration.fit_from_corners(Corners(**captured))
        calibration.save(calibration_path())
        print(f"\nCalibration saved to {calibration_path()}.")
    except ValueError as exc:
        print(f"\nCalibration failed: {exc}")
    except KeyboardInterrupt:
        print("\nCalibration cancelled.")
    finally:
        tracker.stop()
        cam.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        _serve(args.host, args.port, args.camera)
    elif args.cmd == "calibrate":
        _calibrate(args.camera)
    else:
        parser.print_help()
    return 0
