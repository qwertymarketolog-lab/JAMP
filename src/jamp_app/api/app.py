"""Dependency-free WSGI API skeleton for the JAMP MVP."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from jamp_app.config import AppConfig

StartResponse = Callable[[str, list[tuple[str, str]]], Any]


def create_app(config: AppConfig | None = None):
    """Create the minimal application API without coupling to a web framework."""
    app_config = config or AppConfig()

    def application(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/health":
            payload = {"status": "ok", "name": app_config.name, "version": app_config.version}
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
            return [body]

        body = b'{"error":"not_found"}'
        start_response("404 Not Found", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    return application


__all__ = ["create_app"]
