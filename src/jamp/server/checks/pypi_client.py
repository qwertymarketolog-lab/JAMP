"""Shared PyPI JSON client for JAMP evidence checkers."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PYPI_JSON = "https://pypi.org/pypi/{}/json"
TIMEOUT_SECONDS = 20


def fetch_pypi_json(package_name: str) -> tuple[int, dict[str, Any] | None]:
    """Fetch PyPI JSON and return its HTTP status and decoded object."""
    request = Request(
        PYPI_JSON.format(package_name),
        headers={"Accept": "application/json", "User-Agent": "JAMP-The-Hunt-v0.3"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("PyPI response is not a JSON object")
            return response.status, payload
    except HTTPError as exc:
        if exc.code == 404:
            return 404, None
        raise
