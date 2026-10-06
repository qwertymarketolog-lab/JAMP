from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx2 as httpx


@dataclass(frozen=True)
class AdapterResult:
    """Unified result container for JAMP client transports."""

    status: str
    trace_id: str
    selected_model: str | None = None
    output: Any = None
    reason: str | None = None


class JampClientAdapter:
    """Translate client payloads to and from the JAMP Runtime API."""

    def __init__(self, api_base_url: str = "http://127.0.0.1:8000") -> None:
        self.api_base_url = api_base_url.rstrip("/")

    def execute_payload(
        self, payload: dict[str, Any], timeout: float = 10.0
    ) -> AdapterResult:
        url = f"{self.api_base_url}/v1/execute"
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Transport error connecting to Runtime API at {url}: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Runtime API returned non-JSON response ({response.status_code})"
            ) from exc

        status = data.get("status")
        if status == "EXECUTE":
            return AdapterResult(
                status="EXECUTE",
                trace_id=data["trace_id"],
                selected_model=data.get("selected_model"),
                output=data.get("output"),
            )

        if status == "REFUSE":
            return AdapterResult(
                status="REFUSE",
                trace_id=data["trace_id"],
                reason=data.get("reason", "EXECUTION_BLOCKED"),
            )

        raise RuntimeError(
            f"Runtime API returned unknown contract status: {status!r}"
        )
