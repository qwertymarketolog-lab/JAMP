from jamp_app.api import create_app


def _call(app, path="/health", method="GET"):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        app(
            {"REQUEST_METHOD": method, "PATH_INFO": path},
            start_response,
        )
    )
    return captured, body


def test_health_endpoint():
    status, body = _call(create_app())
    assert status["status"] == "200 OK"
    assert body == b'{"status":"ok","name":"JAMP","version":"0.1.0"}'


def test_unknown_route_is_not_found():
    status, body = _call(create_app(), "/missing")
    assert status["status"] == "404 Not Found"
    assert body == b'{"error":"not_found"}'
