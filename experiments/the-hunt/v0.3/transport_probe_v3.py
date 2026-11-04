"""Read-only DNS, TLS, and model-catalog probe for the AnyModel gateway."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 1_048_576
USER_AGENT = "JAMP-The-Hunt-v0.3-Transport-Probe"


def validate_base_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "anymodel.org"
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"Security Error: Unauthorized base_url {url!r}. "
            "Only https://anymodel.org/v1 is allowed."
        )
    return "https://anymodel.org/v1"


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(
            newurl,
            code,
            "HTTP redirects are disabled for authenticated AnyModel requests",
            headers,
            fp,
        )


def _elapsed_ms(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 3)


def _redact(value: str, api_key: str) -> str:
    return value.replace(api_key, "[REDACTED]") if api_key else value


def run_probe(base_url: str, api_key: str) -> dict[str, object]:
    started = time.monotonic()
    base_url = validate_base_url(base_url)
    parsed = urlparse(base_url)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("validated AnyModel base URL has no hostname")
    port = parsed.port or 443
    dns_started = time.monotonic()
    result: dict[str, object] = {
        "schema_version": "jamp-anymodel-transport-probe-v1",
        "probe_timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url.rstrip("/"),
        "endpoint": urljoin(base_url.rstrip("/") + "/", "models"),
        "dns_resolved": False,
        "dns_elapsed_ms": None,
        "resolved_ips": [],
        "tls_handshake": "not_attempted",
        "tls_elapsed_ms": None,
        "http_status": None,
        "http_elapsed_ms": None,
        "elapsed_ms": None,
        "request_id": None,
        "response_body": None,
        "error": None,
        "probe_completed": False,
    }

    try:
        addresses = socket.getaddrinfo(
            hostname, port, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        result["dns_elapsed_ms"] = _elapsed_ms(dns_started)
        result["error"] = {
            "stage": "dns",
            "exception_type": type(exc).__name__,
            "message": _redact(str(exc), api_key)[:1000],
        }
        result["elapsed_ms"] = _elapsed_ms(started)
        result["probe_completed"] = True
        return result

    ips = list(dict.fromkeys(item[4][0] for item in addresses))
    result["dns_resolved"] = bool(ips)
    result["dns_elapsed_ms"] = _elapsed_ms(dns_started)
    result["resolved_ips"] = ips

    tls_started = time.monotonic()
    context = ssl.create_default_context()
    tls_error: OSError | ssl.SSLError | None = None
    for ip in ips:
        try:
            with (
                socket.create_connection(
                    (cast(str, ip), port), timeout=TIMEOUT_SECONDS
                ) as raw_socket,
                context.wrap_socket(
                    raw_socket, server_hostname=hostname
                ) as tls_socket,
            ):
                result["tls_version"] = tls_socket.version()
                certificate = tls_socket.getpeercert(binary_form=True)
                result["peer_certificate_sha256"] = hashlib.sha256(
                    cast(bytes, certificate)
                ).hexdigest()
            result["tls_handshake"] = "success"
            tls_error = None
            break
        except (OSError, ssl.SSLError) as exc:
            tls_error = exc

    result["tls_elapsed_ms"] = _elapsed_ms(tls_started)
    if tls_error is not None:
        result["tls_handshake"] = "fail"
        result["error"] = {
            "stage": "tls",
            "exception_type": type(tls_error).__name__,
            "message": _redact(str(tls_error), api_key)[:1000],
        }
        result["elapsed_ms"] = _elapsed_ms(started)
        result["probe_completed"] = True
        return result

    endpoint = str(result["endpoint"])
    request = Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    http_started = time.monotonic()
    try:
        opener = build_opener(NoRedirectHandler())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            result["http_status"] = response.status
            result["request_id"] = (
                response.headers.get("x-request-id")
                or response.headers.get("request-id")
            )
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        result["http_status"] = exc.code
        result["request_id"] = (
            exc.headers.get("x-request-id")
            or exc.headers.get("request-id")
        )
        raw_body = exc.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        result["error"] = {
            "stage": "http",
            "exception_type": type(exc).__name__,
            "message": _redact(str(exc), api_key)[:1000],
            "reason": _redact(str(reason), api_key)[:500] if reason else None,
        }
        raw_body = b""

    result["http_elapsed_ms"] = _elapsed_ms(http_started)
    if raw_body:
        truncated = len(raw_body) > MAX_RESPONSE_BYTES
        body = raw_body[:MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
        body = _redact(body, api_key)
        if result["http_status"] == 200:
            try:
                decoded: object = json.loads(body)
            except json.JSONDecodeError:
                decoded = body
            result["response_body"] = decoded
            if isinstance(decoded, dict):
                data = decoded.get("data")
                if isinstance(data, list):
                    result["available_model_ids"] = [
                        item["id"]
                        for item in data
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    ]
        else:
            result["error_body"] = body
        result["response_body_truncated"] = truncated

    result["elapsed_ms"] = _elapsed_ms(started)
    result["probe_completed"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="https://anymodel.org/v1",
        help="AnyModel OpenAI-compatible API base URL",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Path for the JSON evidence report",
    )
    args = parser.parse_args()
    api_key = os.environ.get("ANYMODEL_API_KEY", "")
    if not api_key:
        parser.error("ANYMODEL_API_KEY environment variable is required")

    report = run_probe(args.base_url, api_key)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
