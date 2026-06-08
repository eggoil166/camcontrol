"""Detached daemon process management (SPEC 3/11).

A lightweight detached background process (not a true Windows Service): `start`
spawns it with ``DETACHED_PROCESS`` and logs to a file; the daemon records its
pid + bound control port to a runtime file; `stop`/`status` use it. Liveness is
confirmed by actually talking to the control port, so a stale file reads as
"not running".

The runtime-file helpers are pure and unit-tested; spawn/stop/status are an I/O
shell verified manually.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from camcontrol.config import Config, daemon_runtime_path, log_path
from camcontrol.control import ControlClient

# Windows process-creation flags (ignored on other platforms; see
# _detached_popen_args for the per-OS dispatch).
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


def _detached_popen_args(executable: str, platform: str) -> tuple[str, dict]:
    """Choose interpreter + Popen kwargs for a windowless, terminal-independent
    daemon, per OS. Pure (platform passed in) so both branches are testable.

    Windows: launch ``pythonw.exe`` (no console window) detached from the parent
    console, so closing the launching terminal can't kill it. If pythonw is
    missing, fall back to python.exe with CREATE_NO_WINDOW.
    POSIX (the penguin): start a new session (setsid) so SIGHUP on terminal close
    doesn't reach the daemon.
    """
    if platform == "win32":
        pythonw = Path(executable).with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw), {"creationflags": _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP}
        return executable, {"creationflags": _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP}
    return executable, {"start_new_session": True}


def write_runtime(pid: int, port: int) -> None:
    path = daemon_runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "port": port}), encoding="utf-8")


def read_runtime() -> dict | None:
    path = daemon_runtime_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_runtime() -> None:
    daemon_runtime_path().unlink(missing_ok=True)


def _status_over_socket() -> dict | None:
    rt = read_runtime()
    if rt is None:
        return None
    try:
        return ControlClient(port=rt["port"], timeout=1.0).request({"cmd": "status"})
    except OSError:
        return None  # stale runtime file


def is_running() -> bool:
    return _status_over_socket() is not None


def start(config: Config) -> None:
    if is_running():
        print("camcontrol daemon already running.")
        return
    clear_runtime()  # drop any stale file
    src_root = Path(__file__).resolve().parent.parent  # dir containing the package
    env = dict(os.environ, PYTHONPATH=str(src_root))
    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    logfile = open(log, "a", encoding="utf-8")  # noqa: SIM115 (handed to the child)
    executable, popen_kwargs = _detached_popen_args(sys.executable, sys.platform)
    subprocess.Popen(
        [executable, "-m", "camcontrol", "run"],
        cwd=str(src_root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=logfile,
        stderr=logfile,
        close_fds=True,
        **popen_kwargs,
    )
    print(f"camcontrol daemon started (control port {config.control_port}). Logs: {log}")


def stop() -> None:
    rt = read_runtime()
    if not is_running():
        print("camcontrol daemon not running.")
        clear_runtime()
        return
    try:
        ControlClient(port=rt["port"], timeout=2.0).request({"cmd": "shutdown"})
    except OSError:
        _kill_pid(rt.get("pid"))
    clear_runtime()
    print("camcontrol daemon stopped.")


def status() -> None:
    st = _status_over_socket()
    if st is None:
        print("camcontrol daemon not running.")
        return
    print(
        f"state={st['state']} calibrated={st['calibrated']} "
        f"terminal_foreground={st['terminal_foreground']} "
        f"pid={st['pid']} port={st['port']}"
    )


def _kill_pid(pid: int | None) -> None:
    if pid is None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
