"""Offline contract tests for the AnyModel transport probe."""
from __future__ import annotations

import importlib.util
import io
import socket
import sys
from email.message import Message
from urllib.error import HTTPError
from urllib.request import Request
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

_RUNNER_DIR = _PROBE_PATH.parent
sys.path.insert(0, str(_RUNNER_DIR))
_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_llm_v3", _RUNNER_DIR / "run_llm_v3.py"
)
assert _RUNNER_SPEC is not None and _RUNNER_SPEC.loader is not None
_RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(_RUNNER)


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



def test_unauthorized_domain_rejected_before_network_access() -> None:
    with patch.object(_PROBE.socket, "getaddrinfo") as getaddrinfo:
        try:
            _PROBE.run_probe("https://evil.com/v1", "test-secret")
        except ValueError as exc:
            assert "Only https://anymodel.org/v1 is allowed" in str(exc)
        else:
            raise AssertionError("unauthorized domain must be rejected")
        getaddrinfo.assert_not_called()


def test_anymodel_generation_rejects_unauthorized_base_url() -> None:
    try:
        _RUNNER.validate_anymodel_base_url("https://evil.com/v1")
    except ValueError as exc:
        assert "Only https://anymodel.org/v1 is allowed" in str(exc)
    else:
        raise AssertionError("unauthorized AnyModel base URL must be rejected")


def test_redirect_to_unauthorized_domain_is_blocked() -> None:
    request = Request(
        "https://anymodel.org/v1/models",
        headers={"Authorization": "Bearer test-secret"},
    )
    try:
        _PROBE.NoRedirectHandler().redirect_request(
            request,
            io.BytesIO(b""),
            302,
            "Found",
            Message(),
            "https://evil.com/steal",
        )
    except HTTPError as exc:
        assert exc.code == 302
        assert exc.url == "https://evil.com/steal"
    else:
        raise AssertionError("redirect must be blocked before forwarding credentials")
