import pytest

from camcontrol.gui import CalibrationFlow, corner_marker_pos


def test_flow_starts_at_top_left():
    flow = CalibrationFlow()
    assert flow.current() == ("tl", "TOP-LEFT")
    assert flow.step_number == 1
    assert not flow.is_complete


def test_flow_advances_in_tl_tr_bl_br_order():
    flow = CalibrationFlow()
    labels = []
    for angles in [(-10.0, 6.0), (10.0, 6.0), (-10.0, -6.0), (10.0, -6.0)]:
        labels.append(flow.current()[0])
        flow.record(angles)
    assert labels == ["tl", "tr", "bl", "br"]
    assert flow.is_complete


def test_flow_corners_dict_after_completion():
    flow = CalibrationFlow()
    for angles in [(-10.0, 6.0), (10.0, 6.0), (-10.0, -6.0), (10.0, -6.0)]:
        flow.record(angles)
    assert flow.corners_dict() == {
        "tl": [-10.0, 6.0],
        "tr": [10.0, 6.0],
        "bl": [-10.0, -6.0],
        "br": [10.0, -6.0],
    }


def test_current_is_none_when_complete():
    flow = CalibrationFlow()
    for angles in [(0.0, 0.0)] * 4:
        flow.record(angles)
    assert flow.current() is None


def test_corner_marker_positions():
    assert corner_marker_pos("tl", 1000, 500, margin=40) == (40, 40)
    assert corner_marker_pos("tr", 1000, 500, margin=40) == (960, 40)
    assert corner_marker_pos("bl", 1000, 500, margin=40) == (40, 460)
    assert corner_marker_pos("br", 1000, 500, margin=40) == (960, 460)


def test_corner_marker_unknown_key_raises():
    with pytest.raises(ValueError):
        corner_marker_pos("xx", 1000, 500, margin=40)
