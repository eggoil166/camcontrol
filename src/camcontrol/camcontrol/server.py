"""Localhost TCP broadcast server for head-tracking events.

Clients connect to the port and read a stream of newline-delimited JSON events
(one per processed frame). The producer calls ``broadcast(event)``; the server
fans it out to every connected client and prunes any that have disconnected.
Pure stdlib sockets — runs on any OS.
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import threading

logger = logging.getLogger(__name__)


class EventServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._accept_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> int:
        """Bind, listen, and start accepting clients. Returns the bound port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen()
        self.port = sock.getsockname()[1]
        self._sock = sock
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        logger.info("event server listening on %s:%d", self.host, self.port)
        return self.port

    def _accept_loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break  # socket closed by stop()
            with self._lock:
                self._clients.append(conn)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def broadcast(self, event: dict) -> None:
        data = (json.dumps(event) + "\n").encode("utf-8")
        with self._lock:
            survivors = []
            for client in self._clients:
                try:
                    client.sendall(data)
                    survivors.append(client)
                except OSError:
                    self._close(client)
            self._clients = survivors

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            self._sock.close()  # unblocks accept()
            self._sock = None
        with self._lock:
            for client in self._clients:
                self._close(client)
            self._clients = []
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
            self._accept_thread = None

    @staticmethod
    def _close(client: socket.socket) -> None:
        with contextlib.suppress(OSError):
            client.close()
