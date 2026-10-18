#!/usr/bin/env python3
"""Snapshot OpenRouter's public zero-price model catalog for JAMP discovery.

This is discovery evidence only. A zero catalog price does not prove that a
model is callable, capable, reliable, or qualified by JAMP. No API key is used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_OUTPUT = ROOT / "artifacts/research/openrouter_free_model_catalog.json"
USER_AGENT = "JAMP-openrouter-free-catalog/1.0"


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def zero_price(value: Any) -> bool:
    """Accept explicit numeric/string zero only; missing or malformed prices are not free."""
    if isinstance(value, bool) or value is None:
        return False
    try:
        return Decimal(str(value)) == Decimal("0")
    except (InvalidOperation, ValueError):
        return False


def fetch_payload(url: str, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"OpenRouter catalog HTTP {status}; snapshot not trusted")
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenRouter catalog HTTP {exc.code}; snapshot not trusted") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"OpenRouter catalog transport failed: {type(exc).__name__}") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("OpenRouter catalog returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError("OpenRouter catalog response must contain a data list")
    return payload


def build_snapshot(
    payload: dict[str, Any],
    retrieved_at: str | None = None,
    endpoint: str = DEFAULT_URL,
) -> dict[str, Any]:
    rows = payload["data"]
    if any(
        not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]
        for row in rows
    ):
        raise RuntimeError("OpenRouter catalog contains a malformed model row")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("OpenRouter catalog contains duplicate model IDs")

    zero_price_rows = [
        row
        for row in rows
        if isinstance(row.get("pricing"), dict)
        and zero_price(row["pricing"].get("prompt"))
        and zero_price(row["pricing"].get("completion"))
    ]
    free_router_rows = [row for row in zero_price_rows if row["id"] == "openrouter/free"]
    free_models = [row for row in zero_price_rows if row["id"] != "openrouter/free"]

    return {
        "artifact_version": "openrouter-free-model-catalog-v1",
        "evidence_class": "PUBLIC_CATALOG_OBSERVATION_ONLY",
        "retrieved_at": retrieved_at or utc_now(),
        "source": {
            "endpoint": endpoint,
            "http_status": 200,
            "catalog_model_count": len(rows),
            "zero_price_entry_count": len(zero_price_rows),
            "zero_price_model_count": len(free_models),
            "free_router_entry_count": len(free_router_rows),
        },
        "free_router": {
            "present": bool(free_router_rows),
            "entries": free_router_rows,
            "note": "The free router is a routing endpoint, not a specific model.",
        },
        "qualification": {
            "jamp_execution_approved": False,
            "model_quality_verified": False,
            "live_chat_completion_tested": False,
            "note": (
                "Zero listed prompt/completion prices are catalog metadata only. "
                "Availability, modality compatibility, rate limits, and JAMP evidence "
                "gates must be evaluated separately."
            ),
        },
        "models": sorted(free_models, key=lambda row: row["id"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Public OpenRouter models endpoint")
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        payload = fetch_payload(args.url, args.timeout)
        snapshot = build_snapshot(payload, endpoint=args.url)
        output = args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("HTTP: 200")
    print(f"CATALOG_MODELS: {snapshot['source']['catalog_model_count']}")
    print(f"ZERO_PRICE_ENTRIES: {snapshot['source']['zero_price_entry_count']}")
    print(f"ZERO_PRICE_MODELS: {snapshot['source']['zero_price_model_count']}")
    print(f"FREE_ROUTER_PRESENT: {snapshot['free_router']['present']}")
    print(f"EVIDENCE: {snapshot['evidence_class']} (not qualification)")
    print(f"OUTPUT: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
