from camcontrol.window import ScreenRect


def test_width_and_height():
    rect = ScreenRect(left=100, top=50, right=1100, bottom=550)
    assert rect.width == 1000
    assert rect.height == 500


def test_normalize_corners_and_center():
    rect = ScreenRect(left=100, top=50, right=1100, bottom=550)
    assert rect.normalize(100, 50) == (0.0, 0.0)
    assert rect.normalize(1100, 550) == (1.0, 1.0)
    assert rect.normalize(600, 300) == (0.5, 0.5)


def test_normalize_point_left_of_rect_is_negative():
    rect = ScreenRect(left=100, top=50, right=1100, bottom=550)
    x, y = rect.normalize(50, 50)
    assert x < 0.0  # outside the terminal -> grid.cell_at will reject it
    assert y == 0.0
