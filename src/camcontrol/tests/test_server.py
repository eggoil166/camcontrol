import json
import socket
import time

from camcontrol.server import EventServer


def _wait(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def _recv_line(sock):
    sock.settimeout(2.0)
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


def test_broadcast_reaches_connected_client():
    server = EventServer(port=0)
    port = server.start()
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        assert _wait(lambda: server.client_count == 1)
        server.broadcast({"detected": True, "x": 0.5})
        assert json.loads(_recv_line(client)) == {"detected": True, "x": 0.5}
    finally:
        client.close()
        server.stop()


def test_broadcast_reaches_all_clients():
    server = EventServer(port=0)
    port = server.start()
    a = socket.create_connection(("127.0.0.1", port), timeout=2)
    b = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        assert _wait(lambda: server.client_count == 2)
        server.broadcast({"n": 7})
        assert json.loads(_recv_line(a)) == {"n": 7}
        assert json.loads(_recv_line(b)) == {"n": 7}
    finally:
        a.close()
        b.close()
        server.stop()


def test_dropped_client_is_pruned_without_killing_server():
    server = EventServer(port=0)
    port = server.start()
    live = socket.create_connection(("127.0.0.1", port), timeout=2)
    dead = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        assert _wait(lambda: server.client_count == 2)
        dead.close()
        # A couple of broadcasts so the failed send to `dead` is observed.
        server.broadcast({"i": 1})
        server.broadcast({"i": 2})
        assert _wait(lambda: server.client_count == 1)
        # The live client still receives.
        assert json.loads(_recv_line(live))["i"] in (1, 2)
    finally:
        live.close()
        server.stop()
