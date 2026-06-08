from camcontrol.controller import FrameSlot, median_angles


def test_frame_slot_empty_returns_none():
    assert FrameSlot().get() is None


def test_frame_slot_returns_latest_set_value():
    slot = FrameSlot()
    slot.set("frame-a")
    slot.set("frame-b")
    assert slot.get() == "frame-b"  # latest wins


def test_median_angles_picks_componentwise_median():
    samples = [(-10.0, 6.0), (-8.0, 4.0), (-12.0, 5.0)]
    assert median_angles(samples) == (-10.0, 5.0)


def test_median_angles_even_count_averages_middle_pair():
    samples = [(0.0, 0.0), (2.0, 4.0)]
    assert median_angles(samples) == (1.0, 2.0)
