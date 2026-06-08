from camcontrol.control import ControlClient, ControlServer


def test_request_round_trips_through_handler():
    def handler(req):
        return {"ok": True, "echo": req["cmd"]}

    server = ControlServer(handler, port=0)
    port = server.start()
    try:
        resp = ControlClient(port=port).request({"cmd": "status"})
    finally:
        server.stop()
    assert resp == {"ok": True, "echo": "status"}


def test_handler_sees_full_request_payload():
    seen = []

    def handler(req):
        seen.append(req)
        return {"ok": True}

    server = ControlServer(handler, port=0)
    port = server.start()
    try:
        ControlClient(port=port).request({"cmd": "sample", "n": 3})
    finally:
        server.stop()
    assert seen == [{"cmd": "sample", "n": 3}]


def test_sequential_requests_share_one_server():
    def handler(req):
        return {"i": req["i"]}

    server = ControlServer(handler, port=0)
    port = server.start()
    try:
        client = ControlClient(port=port)
        results = [client.request({"i": i})["i"] for i in range(3)]
    finally:
        server.stop()
    assert results == [0, 1, 2]
