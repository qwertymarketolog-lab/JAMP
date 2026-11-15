"""Research-only bounded HTTP capture preserving original response bytes."""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_BODY_BYTES = 1024 * 1024
ALLOWED_ENDPOINTS = {
    ("iss.moex.com", "/iss/engines/stock/markets/shares/securities/SBER.json"),
    ("api.coingecko.com", "/api/v3/simple/price"),
}
SAFE_RESPONSE_HEADERS = {
    "content-type",
    "date",
    "cache-control",
    "etag",
    "last-modified",
    "retry-after",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _open_request(request: urllib.request.Request, timeout: float):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _safe_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() in SAFE_RESPONSE_HEADERS
    }


def _read_bounded(stream: Any, max_bytes: int) -> tuple[bytes, bool]:
    body = stream.read(max_bytes + 1)
    complete = len(body) <= max_bytes
    return body[:max_bytes], complete


def capture_http(
    *,
    source: str,
    url: str,
    output_dir: str | Path,
    timeout: float = 5.0,
    max_bytes: int = MAX_BODY_BYTES,
) -> dict[str, Any]:
    """Make one allowlisted GET and persist raw metadata plus exact captured bytes.

    Transport and HTTP failures are returned as evidence records, not raised.
    Invalid local configuration is rejected before any network request.
    """
    if source not in {"MOEX", "CoinGecko"}:
        raise ValueError("unsupported evidence source")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or (parsed.hostname, parsed.path) not in ALLOWED_ENDPOINTS:
        raise ValueError("URL is outside the experiment endpoint allowlist")
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError("timeout and max_bytes must be positive")

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    body_path = target / f"{source.lower()}.body"
    record_path = target / f"{source.lower()}.raw.json"
    requested_at = _utc_now()
    status_code: int | None = None
    headers: dict[str, str] = {}
    body = b""
    body_complete = True
    error_type: str | None = None
    error_message: str | None = None

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JAMP-Research-Experiment/2.0",
        },
        method="GET",
    )
    try:
        with _open_request(request, timeout) as response:
            status_code = int(response.status)
            headers = _safe_headers(response.headers)
            body, body_complete = _read_bounded(response, max_bytes)
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        headers = _safe_headers(exc.headers)
        try:
            body, body_complete = _read_bounded(exc, max_bytes)
        except OSError as read_exc:
            error_type = type(read_exc).__name__
            error_message = "failed to read HTTP error response body"
        finally:
            exc.close()
        if error_type is None:
            error_type = "HTTPError"
            error_message = f"HTTP response status {status_code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        error_type = type(exc).__name__
        error_message = "request failed before a complete HTTP response was received"

    if not body_complete:
        error_type = "RESPONSE_TOO_LARGE"
        error_message = f"response exceeded capture limit of {max_bytes} bytes"

    body_path.write_bytes(body)
    try:
        raw_body: str | None = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raw_body = None

    record: dict[str, Any] = {
        "schema": "jamp.raw-http-evidence.v1",
        "source": source,
        "url": url,
        "timestamp_utc": requested_at,
        "captured_at_utc": _utc_now(),
        "status_code": status_code,
        "response_headers": headers,
        "body_file": body_path.name,
        "body_complete": body_complete,
        "sha256_body": hashlib.sha256(body).hexdigest(),
        "raw_body_base64": base64.b64encode(body).decode("ascii"),
        "raw_body": raw_body,
        "error_type": error_type,
        "error_message": error_message,
    }
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return record
