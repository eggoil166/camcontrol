from camcontrol.geometry import Grid


def test_1x2_left_point_maps_to_left_cell():
    grid = Grid(rows=1, cols=2)
    assert grid.cell_at(0.25, 0.5) == "r0c0"


def test_1x2_right_point_maps_to_right_cell():
    grid = Grid(rows=1, cols=2)
    assert grid.cell_at(0.75, 0.5) == "r0c1"


def test_point_outside_unit_square_returns_none():
    grid = Grid(rows=1, cols=2)
    assert grid.cell_at(1.2, 0.5) is None
    assert grid.cell_at(0.5, -0.1) is None


def test_far_corner_maps_to_last_cell_not_out_of_range():
    grid = Grid(rows=1, cols=2)
    assert grid.cell_at(1.0, 1.0) == "r0c1"


def test_cell_rect_for_left_cell_of_1x2():
    grid = Grid(rows=1, cols=2)
    assert grid.cell_rect("r0c0") == (0.0, 0.0, 0.5, 1.0)


def test_3x3_center_point():
    grid = Grid(rows=3, cols=3)
    assert grid.cell_at(0.5, 0.5) == "r1c1"
