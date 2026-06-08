from camcontrol import service


def test_runtime_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path))
    service.write_runtime(pid=4321, port=8765)
    assert service.read_runtime() == {"pid": 4321, "port": 8765}


def test_read_runtime_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path))
    assert service.read_runtime() is None


def test_clear_runtime_removes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMCONTROL_HOME", str(tmp_path))
    service.write_runtime(pid=1, port=2)
    service.clear_runtime()
    assert service.read_runtime() is None
