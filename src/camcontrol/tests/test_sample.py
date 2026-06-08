import threading
import time

from camcontrol.calibration import Calibration
from camcontrol.config import Config
from camcontrol.controller import Controller


def make_controller():
    return Controller(Config(control_port=0), Calibration.default(1920, 1080))


def test_sample_returns_median_when_frames_already_present():
    ctrl = make_controller()
    for a in [(-10.0, 6.0), (-8.0, 4.0), (-12.0, 5.0)]:
        ctrl._recent.append(a)
    try:
        resp = ctrl._dispatch({"cmd": "sample", "timeout": 0.2})
    finally:
        ctrl._server.stop()
    assert resp == {"ok": True, "detected": True, "yaw": -10.0, "pitch": 5.0}


def test_sample_times_out_to_undetected_when_no_face():
    ctrl = make_controller()
    try:
        t0 = time.monotonic()
        resp = ctrl._dispatch({"cmd": "sample", "timeout": 0.2})
        elapsed = time.monotonic() - t0
    finally:
        ctrl._server.stop()
    assert resp == {"ok": True, "detected": False}
    assert elapsed >= 0.2  # it actually waited rather than failing instantly


def test_sample_waits_for_frames_that_arrive_during_the_window():
    ctrl = make_controller()

    def feed_later():
        time.sleep(0.1)
        for a in [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]:
            ctrl._recent.append(a)

    threading.Thread(target=feed_later, daemon=True).start()
    try:
        resp = ctrl._dispatch({"cmd": "sample", "timeout": 2.0})
    finally:
        ctrl._server.stop()
    assert resp["detected"] is True
    assert resp["yaw"] == 2.0 and resp["pitch"] == 2.0
