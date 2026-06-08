import json

from camcontrol.config import Config, config_dir


def test_defaults_match_spec():
    cfg = Config()
    assert (cfg.grid_rows, cfg.grid_cols) == (1, 2)
    assert cfg.dwell_ms == 400
    assert cfg.hysteresis_margin == 0.04
    assert cfg.idle_timeout_s == 30
    assert cfg.hotkey == "ctrl+alt+h"
    assert cfg.terminal_processes == ["WindowsTerminal.exe"]
    assert cfg.control_port == 8765


def test_save_load_round_trip(tmp_path):
    cfg = Config(grid_rows=3, grid_cols=3, control_port=9000)
    path = tmp_path / "config.json"
    cfg.save(path)
    assert Config.load(path) == cfg


def test_load_merges_partial_onto_defaults_and_ignores_unknown(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"dwell_ms": 250, "bogus_key": 7}), encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.dwell_ms == 250          # overridden
    assert cfg.control_port == 8765     # default preserved
    assert not hasattr(cfg, "bogus_key")  # unknown ignored


def test_load_or_default_returns_defaults_when_missing(tmp_path):
    assert Config.load_or_default(tmp_path / "nope.json") == Config()


def test_config_dir_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path / "cc"))
    assert config_dir() == tmp_path / "cc"
