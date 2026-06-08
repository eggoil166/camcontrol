"""CLI entry point (SPEC 11).

Subcommands: start / stop / status (manage the detached daemon), run (daemon in
the foreground for debugging), calibrate (drive the running daemon's 4-corner
sequence over the control socket).
"""

from __future__ import annotations

import argparse

from camcontrol import service, window
from camcontrol.calibration import CORNER_SEQUENCE, Calibration
from camcontrol.config import Config, calibration_path, config_path
from camcontrol.control import ControlClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="camcontrol", description="Head-pointer terminal control.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("start", help="start the detached daemon")
    sub.add_parser("stop", help="stop the daemon")
    sub.add_parser("status", help="show daemon status")
    sub.add_parser("calibrate", help="run the 4-corner calibration (headless)")
    sub.add_parser("gui", help="open the fullscreen calibrate + preview window")
    sub.add_parser("run", help="run the daemon in the foreground (debug)")
    return parser


def _load_config() -> Config:
    return Config.load_or_default(config_path())


def _load_calibration() -> Calibration:
    path = calibration_path()
    if path.exists():
        return Calibration.load(path)
    w, h = window.screen_size()
    return Calibration.default(w, h)


def _running_daemon() -> dict | None:
    """Runtime info of the live daemon, or None (with a message) if it isn't up."""
    rt = service.read_runtime()
    if rt is None or not service.is_running():
        print("Daemon not running. Start it first: camcontrol start")
        return None
    return rt


def _run_foreground(config: Config) -> None:
    if service.is_running():
        print("A camcontrol daemon is already running. Stop it first: camcontrol stop")
        return
    from camcontrol.controller import Controller  # lazy: pulls cv2/mediapipe

    Controller(config, _load_calibration()).run()


def _gui() -> None:
    rt = _running_daemon()
    if rt is None:
        return
    from camcontrol.gui import run_gui  # lazy: pulls in tkinter

    run_gui(port=rt["port"])


def _calibrate() -> None:
    rt = _running_daemon()
    if rt is None:
        return
    client = ControlClient(port=rt["port"], timeout=10.0)
    client.request({"cmd": "begin_calibration"})
    print("Calibration: look at each corner, then press ENTER.\n")
    try:
        corners: dict[str, list[float]] = {}
        for key, label in CORNER_SEQUENCE:
            corners[key] = _capture_corner(client, label)
        w, h = window.screen_size()
        resp = client.request({"cmd": "commit_calibration", "corners": corners, "screen": [w, h]})
        if resp.get("ok"):
            print("\nCalibration saved.")
        else:
            print(f"\nCalibration failed: {resp.get('error')}")
    except KeyboardInterrupt:
        client.request({"cmd": "cancel_calibration"})
        print("\nCalibration cancelled.")


def _capture_corner(client: ControlClient, label: str) -> list[float]:
    while True:
        input(f"  Look at the {label} corner and press ENTER...")
        resp = client.request({"cmd": "sample"})
        if resp.get("detected"):
            return [resp["yaw"], resp["pitch"]]
        print("  No face detected — hold still and try again.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "start":
        service.start(_load_config())
    elif args.cmd == "stop":
        service.stop()
    elif args.cmd == "status":
        service.status()
    elif args.cmd == "calibrate":
        _calibrate()
    elif args.cmd == "gui":
        _gui()
    elif args.cmd == "run":
        _run_foreground(_load_config())
    else:
        parser.print_help()
    return 0
