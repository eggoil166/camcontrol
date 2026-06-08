import pytest

from camcontrol.calibration import Calibration, Corners


def test_fit_maps_each_corner_angle_to_its_screen_corner():
    corners = Corners(
        tl=(-10.0, 6.0), tr=(10.0, 6.0), bl=(-10.0, -6.0), br=(10.0, -6.0)
    )
    cal = Calibration.fit_from_corners(corners, screen_w=1000, screen_h=500)
    assert cal.to_screen_px(-10.0, 6.0) == pytest.approx((0.0, 0.0))
    assert cal.to_screen_px(10.0, 6.0) == pytest.approx((1000.0, 0.0))
    assert cal.to_screen_px(-10.0, -6.0) == pytest.approx((0.0, 500.0))
    assert cal.to_screen_px(10.0, -6.0) == pytest.approx((1000.0, 500.0))


def test_left_edge_is_mean_of_top_left_and_bottom_left_yaw():
    corners = Corners(
        tl=(-10.0, 6.0), tr=(10.0, 6.0), bl=(-12.0, -6.0), br=(10.0, -6.0)
    )
    cal = Calibration.fit_from_corners(corners, screen_w=1000, screen_h=500)
    px, _ = cal.to_screen_px(-11.0, 0.0)  # mean(-10, -12) = -11 -> left edge
    assert px == pytest.approx(0.0)


def test_default_maps_neutral_pose_to_screen_center():
    cal = Calibration.default(screen_w=1920, screen_h=1080)
    assert cal.is_default
    assert cal.to_screen_px(0.0, 0.0) == pytest.approx((960.0, 540.0))


def test_degenerate_fit_raises():
    corners = Corners(
        tl=(5.0, 6.0), tr=(5.0, 6.0), bl=(5.0, -6.0), br=(5.0, -6.0)
    )  # left and right yaw both 5.0 -> zero horizontal span
    with pytest.raises(ValueError):
        Calibration.fit_from_corners(corners, screen_w=1000, screen_h=500)


def test_angles_beyond_corners_clamp_to_screen_edges():
    corners = Corners(
        tl=(-10.0, 6.0), tr=(10.0, 6.0), bl=(-10.0, -6.0), br=(10.0, -6.0)
    )
    cal = Calibration.fit_from_corners(corners, screen_w=1000, screen_h=500)
    assert cal.to_screen_px(-99.0, 99.0) == pytest.approx((0.0, 0.0))
    assert cal.to_screen_px(99.0, -99.0) == pytest.approx((1000.0, 500.0))


def test_json_round_trip(tmp_path):
    corners = Corners(
        tl=(-10.0, 6.0), tr=(10.0, 6.0), bl=(-10.0, -6.0), br=(10.0, -6.0)
    )
    cal = Calibration.fit_from_corners(corners, screen_w=1000, screen_h=500)
    path = tmp_path / "calibration.json"
    cal.save(path)
    loaded = Calibration.load(path)
    assert loaded.to_screen_px(0.0, 0.0) == pytest.approx(cal.to_screen_px(0.0, 0.0))
    assert loaded.is_default is False
