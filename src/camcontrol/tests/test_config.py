from camcontrol.config import Config, calibration_path, config_dir


def test_serve_defaults():
    cfg = Config()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8765
    assert cfg.camera_index == 0
    assert cfg.one_euro_min_cutoff == 1.0
    assert cfg.one_euro_beta == 0.05


def test_config_dir_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path / "cc"))
    assert config_dir() == tmp_path / "cc"


def test_calibration_path_under_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path))
    assert calibration_path() == tmp_path / "calibration.json"
