"""Offline contract tests for the AnyModel transport probe."""
from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from unittest.mock import patch

_PROBE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "the-hunt"
    / "v0.3"
    / "transport_probe_v3.py"
)
_SPEC = importlib.util.spec_from_file_location("transport_probe_v3", _PROBE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_PROBE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROBE)


def test_dns_failure_is_recorded_without_tls_or_http() -> None:
    with patch.object(
        _PROBE.socket, "getaddrinfo", side_effect=socket.gaierror("name lookup failed")
    ):
        report = _PROBE.run_probe("https://anymodel.org/v1", "test-secret")

    assert report["dns_resolved"] is False
    assert report["tls_handshake"] == "not_attempted"
    assert report["http_status"] is None
    assert report["error"]["stage"] == "dns"
    assert report["probe_completed"] is True


def test_tls_failure_is_recorded_without_http_request() -> None:
    with (
        patch.object(
            _PROBE.socket,
            "getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))
            ],
        ),
        patch.object(
            _PROBE.socket,
            "create_connection",
            side_effect=TimeoutError("connect timed out"),
        ),
    ):
        report = _PROBE.run_probe("https://anymodel.org/v1", "test-secret")

    assert report["dns_resolved"] is True
    assert report["tls_handshake"] == "fail"
    assert report["http_status"] is None
    assert report["error"]["stage"] == "tls"
    assert report["probe_completed"] is True


def test_non_https_base_url_is_rejected_before_network_access() -> None:
    try:
        _PROBE.run_probe("http://anymodel.org/v1", "test-secret")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("non-HTTPS endpoint must be rejected")
