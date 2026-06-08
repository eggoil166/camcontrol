from camcontrol.cli import build_parser


def test_parser_recognizes_subcommands():
    parser = build_parser()
    for cmd in ["start", "stop", "status", "calibrate", "gui", "run"]:
        assert parser.parse_args([cmd]).cmd == cmd


def test_parser_no_command_leaves_cmd_none():
    parser = build_parser()
    assert parser.parse_args([]).cmd is None
