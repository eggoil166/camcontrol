from camcontrol.service import (
    _CREATE_NEW_PROCESS_GROUP,
    _CREATE_NO_WINDOW,
    _DETACHED_PROCESS,
    _detached_popen_args,
)


def _make_exe(tmp_path, *names):
    for n in names:
        (tmp_path / n).write_text("")
    return str(tmp_path / "python.exe")


def test_windows_prefers_pythonw_and_detaches(tmp_path):
    exe = _make_exe(tmp_path, "python.exe", "pythonw.exe")
    chosen, kwargs = _detached_popen_args(exe, "win32")
    assert chosen == str(tmp_path / "pythonw.exe")
    assert kwargs["creationflags"] == _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    assert "start_new_session" not in kwargs


def test_windows_falls_back_to_python_with_no_window(tmp_path):
    exe = _make_exe(tmp_path, "python.exe")  # no pythonw.exe
    chosen, kwargs = _detached_popen_args(exe, "win32")
    assert chosen == exe
    assert kwargs["creationflags"] == _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP


def test_posix_uses_new_session_and_no_creationflags():
    chosen, kwargs = _detached_popen_args("/usr/bin/python3", "linux")
    assert chosen == "/usr/bin/python3"
    assert kwargs == {"start_new_session": True}
