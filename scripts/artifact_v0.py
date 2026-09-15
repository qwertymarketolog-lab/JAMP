"""Minimal neutral Artifact Contract v0 serializer.

This module only maps typed RunResult fields plus opaque domain payload
into the Q3b.1 artifact shape. It contains no domain-specific logic.
"""
from __future__ import annotations

from typing import Any


def serialize_run_result(
    result: Any,
    adapter: str,
    final_state: Any,
    provenance: Any,
    adapter_contract: str | None = None,
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "artifact_version": "v0",
        "adapter": adapter,
        "run_result": {
            "steps": result.steps,
            "iterations": result.iterations,
            "stop_reason": {
                "kind": result.stop_reason.kind,
                "detail": result.stop_reason.detail,
            },
        },
        "final_state": final_state,
        "provenance": provenance,
    }
    if adapter_contract is not None:
        artifact["adapter_contract"] = adapter_contract
    return artifact
