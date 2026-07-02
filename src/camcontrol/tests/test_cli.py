from camcontrol.cli import build_parser, make_event


def test_parser_recognizes_commands():
    parser = build_parser()
    assert parser.parse_args(["serve"]).cmd == "serve"
    assert parser.parse_args(["calibrate"]).cmd == "calibrate"
    assert parser.parse_args([]).cmd is None


def test_serve_flag_defaults_and_overrides():
    parser = build_parser()
    d = parser.parse_args(["serve"])
    assert (d.host, d.port, d.camera) == ("127.0.0.1", 8765, 0)
    o = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "9000", "--camera", "1"])
    assert (o.host, o.port, o.camera) == ("0.0.0.0", 9000, 1)


def test_make_event_detected_has_all_sections():
    e = make_event(1.5, True, raw=(-4.0, 3.0), filtered=(-3.5, 2.8), screen=(0.4, 0.6))
    assert e == {
        "t": 1.5,
        "detected": True,
        "raw": {"yaw": -4.0, "pitch": 3.0},
        "filtered": {"yaw": -3.5, "pitch": 2.8},
        "screen": {"x": 0.4, "y": 0.6},
    }


def test_make_event_undetected_is_minimal():
    assert make_event(2.0, False) == {"t": 2.0, "detected": False}
