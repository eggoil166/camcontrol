"""Localhost JSON-lines control channel (SPEC 7/10).

The detached daemon hosts a ``ControlServer`` on loopback; foreground CLI
commands (calibrate/status/stop) talk to it with a ``ControlClient``. One JSON
object per line, request -> response. This is the same transport SPEC 10 wants
for the driftwm era, built once and reused.
"""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from collections.abc import Callable

Handler = Callable[[dict], dict]

_HOST = "127.0.0.1"


class _RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        for raw in self.rfile:  # iterates newline-delimited lines
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.server.dispatch(req)  # type: ignore[attr-defined]
            except json.JSONDecodeError:
                resp = {"ok": False, "error": "malformed json"}
            except Exception as exc:  # handler blew up; keep the daemon alive
                resp = {"ok": False, "error": str(exc)}
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
            self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, host: str, port: int, dispatch: Handler) -> None:
        super().__init__((host, port), _RequestHandler)
        self.dispatch = dispatch


class ControlServer:
    def __init__(self, handler: Handler, host: str = _HOST, port: int = 8765) -> None:
        self._server = _Server(host, port, handler)
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        """Begin serving on a background thread. Returns the bound port."""
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def stop(self) -> None:
        # shutdown() blocks until serve_forever() acknowledges, so only call it
        # if we actually started serving; otherwise just release the socket.
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(timeout=2.0)
            self._thread = None
        self._server.server_close()


class ControlClient:
    def __init__(self, port: int, host: str = _HOST, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def request(self, obj: dict) -> dict:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
        line = buf.split(b"\n", 1)[0].decode("utf-8")
        return json.loads(line)
