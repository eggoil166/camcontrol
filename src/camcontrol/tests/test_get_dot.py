from camcontrol.calibration import Calibration
from camcontrol.config import Config
from camcontrol.controller import Controller


def make_controller():
    # control_port=0 binds an ephemeral port; no camera/threads start in __init__.
    config = Config(control_port=0)
    cal = Calibration.default(screen_w=1920, screen_h=1080)
    return Controller(config, cal)


def test_get_dot_before_any_detection_reports_center_undetected():
    ctrl = make_controller()
    try:
        resp = ctrl._dispatch({"cmd": "get_dot"})
    finally:
        ctrl._server.stop()
    assert resp == {"ok": True, "detected": False, "x": 0.5, "y": 0.5}


def test_get_dot_returns_latest_dot_when_detected():
    ctrl = make_controller()
    ctrl._latest_dot = (0.25, 0.75)
    ctrl._dot_detected = True
    try:
        resp = ctrl._dispatch({"cmd": "get_dot"})
    finally:
        ctrl._server.stop()
    assert resp == {"ok": True, "detected": True, "x": 0.25, "y": 0.75}
