"""Fullscreen calibrate + preview GUI (tkinter).

An opaque dark fullscreen window that shows the live gaze as a light patch and
runs 4-corner calibration via a single re-clickable button. It polls the running
daemon for the dot (`get_dot`) and drives calibration over the control socket;
the daemon owns the camera. Opening the window enters the daemon's calibration/
preview mode (camera on); closing it cancels (camera off / restore).

``CalibrationFlow`` and ``corner_marker_pos`` are pure and unit-tested; the
tkinter window is a manually-verified shell.
"""

from __future__ import annotations

import contextlib

from camcontrol.calibration import CORNER_SEQUENCE
from camcontrol.control import ControlClient

_MARGIN = 80          # px inset of the corner target ring
_PATCH_RADIUS = 28    # px radius of the gaze patch
_POLL_MS = 33         # ~30 fps


class CalibrationFlow:
    """Tracks the TL -> TR -> BL -> BR capture sequence (SPEC 5 order)."""

    def __init__(self) -> None:
        self._index = 0
        self._captures: dict[str, list[float]] = {}

    def current(self) -> tuple[str, str] | None:
        if self.is_complete:
            return None
        return CORNER_SEQUENCE[self._index]

    @property
    def step_number(self) -> int:
        return self._index + 1

    @property
    def is_complete(self) -> bool:
        return self._index >= len(CORNER_SEQUENCE)

    def record(self, angles: tuple[float, float]) -> None:
        key = CORNER_SEQUENCE[self._index][0]
        self._captures[key] = [angles[0], angles[1]]
        self._index += 1

    def corners_dict(self) -> dict[str, list[float]]:
        return dict(self._captures)


def corner_marker_pos(key: str, w: int, h: int, margin: int = _MARGIN) -> tuple[int, int]:
    """Pixel center of the target ring for a corner, inset by ``margin``."""
    xs = {"tl": margin, "bl": margin, "tr": w - margin, "br": w - margin}
    ys = {"tl": margin, "tr": margin, "bl": h - margin, "br": h - margin}
    if key not in xs:
        raise ValueError(f"unknown corner: {key!r}")
    return (xs[key], ys[key])


# --- tkinter shell (manually verified) ------------------------------------


def run_gui(port: int) -> None:
    import tkinter as tk

    # Generous timeout: begin_calibration loads the camera + model (~2s cold) and
    # sample() may block waiting for frames, both longer than a polling timeout.
    client = ControlClient(port=port, timeout=10.0)
    client.request({"cmd": "begin_calibration"})  # camera on / preview

    root = tk.Tk()
    root.title("camcontrol")
    root.attributes("-fullscreen", True)
    root.configure(bg="#0a0a0a")
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    canvas = tk.Canvas(root, width=w, height=h, bg="#0a0a0a", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    state = {"flow": None, "status": "Preview — click Calibrate to begin."}

    def on_calibrate() -> None:
        flow = state["flow"]
        if flow is None:
            state["flow"] = CalibrationFlow()
            return
        resp = client.request({"cmd": "sample"})
        if not resp.get("detected"):
            state["status"] = "No face detected — hold still and try again."
            return
        flow.record((resp["yaw"], resp["pitch"]))
        if flow.is_complete:
            result = client.request(
                {"cmd": "commit_calibration", "corners": flow.corners_dict(), "screen": [w, h]}
            )
            state["status"] = "Calibration saved." if result.get("ok") else \
                f"Failed: {result.get('error')}"
            state["flow"] = None

    button = tk.Button(root, text="Calibrate", font=("Segoe UI", 16),
                       command=on_calibrate, padx=20, pady=10)
    canvas.create_window(w // 2, h - 80, window=button)
    root.bind("<space>", lambda _e: on_calibrate())
    root.bind("<Return>", lambda _e: on_calibrate())
    root.bind("<Escape>", lambda _e: _close(root, client))

    def tick() -> None:
        canvas.delete("dynamic")
        flow = state["flow"]
        if flow is not None and not flow.is_complete:
            key, label = flow.current()
            cx, cy = corner_marker_pos(key, w, h)
            canvas.create_oval(cx - 30, cy - 30, cx + 30, cy + 30,
                               outline="#ffd24a", width=4, tags="dynamic")
            state["status"] = f"Look at {label}, then click Calibrate ({flow.step_number}/4)"
        try:
            dot = client.request({"cmd": "get_dot"})
        except OSError:
            dot = None
        if dot is not None:
            color = "#eaeaea" if dot["detected"] else "#3a3a3a"
            px, py = dot["x"] * w, dot["y"] * h
            canvas.create_oval(px - _PATCH_RADIUS, py - _PATCH_RADIUS,
                               px + _PATCH_RADIUS, py + _PATCH_RADIUS,
                               fill=color, outline="", tags="dynamic")
        canvas.create_text(w // 2, 50, text=state["status"], fill="#cccccc",
                           font=("Segoe UI", 18), tags="dynamic")
        root.after(_POLL_MS, tick)

    tick()
    root.mainloop()


def _close(root, client: ControlClient) -> None:
    with contextlib.suppress(OSError):
        client.request({"cmd": "cancel_calibration"})
    root.destroy()
