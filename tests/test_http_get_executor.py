from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from jamp.agent.http_get import ALLOWED_HOSTS, HTTPGetExecutor, ToolError


def test_rejects_non_allowlisted_host(monkeypatch):
    def unexpected_network_call(*args, **kwargs):
        pytest.fail("non-allowlisted URL must be rejected before any network call")

    monkeypatch.setattr(socket, "create_connection", unexpected_network_call)
    executor = HTTPGetExecutor()

    assert "example.com" in ALLOWED_HOSTS
    with pytest.raises(ToolError):
        executor({"url": "https://evil.com/"})


def test_rejects_http_scheme():
    executor = HTTPGetExecutor()
    with patch("jamp.agent.http_get.socket.create_connection") as mock_conn:
        with pytest.raises(ToolError) as exc:
            executor.execute({"url": "http://example.com/"})
    assert exc.value.code == "INSECURE_SCHEME"
    mock_conn.assert_not_called()
