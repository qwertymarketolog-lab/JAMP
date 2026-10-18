#!/usr/bin/env python3
"""Run controlled, minimal OpenRouter chat-completion probes for catalogued free text models.

Requires OPENROUTER_API_KEY. Results deliberately omit prompts, generated content,
authorization data, and raw provider error bodies. A successful probe is not model
qualification and does not alter JAMP routing policy.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "artifacts/research/openrouter_free_model_catalog.json"
DEFAULT_OUTPUT = ROOT / "artifacts/research/openrouter_free_model_probe.json"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
USER_AGENT = "JAMP-openrouter-controlled-probe/1.0"


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def is_text_output(model: dict[str, Any]) -> bool:
    architecture = model.get("architecture")
    if not isinstance(architecture, dict):
        return False
    outputs = architecture.get("output_modalities")
    return isinstance(outputs, list) and "text" in outputs


def probe_model(api_key: str, model_id: str, timeout: float) -> dict[str, Any]:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
        "temperature": 0,
        "max_tokens": 8,
    }
    request = urllib.request.Request(
        CHAT_URL,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    started = time.monotonic()
    base: dict[str, Any] = {"model_id": model_id, "endpoint": CHAT_URL}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            raw = response.read()
        elapsed_ms = round((time.monotonic() - started) * 1000)
        decoded = json.loads(raw.decode("utf-8"))
        if status != 200:
            return {**base, "status": "HTTP_ERROR", "http_status": status, "elapsed_ms": elapsed_ms}
        if not isinstance(decoded, dict):
            return {**base, "status": "INVALID_RESPONSE", "http_status": status, "elapsed_ms": elapsed_ms}
        choices = decoded.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return {
                **base,
                "status": "NO_TEXT_COMPLETION",
                "http_status": status,
                "elapsed_ms": elapsed_ms,
                "provider_response_id": decoded.get("id") if isinstance(decoded.get("id"), str) else None,
            }
        usage = decoded.get("usage")
        return {
            **base,
            "status": "CHAT_COMPLETION_OK",
            "http_status": status,
            "elapsed_ms": elapsed_ms,
            "provider_response_id": decoded.get("id") if isinstance(decoded.get("id"), str) else None,
            "response_model": decoded.get("model") if isinstance(decoded.get("model"), str) else None,
            "usage": usage if isinstance(usage, dict) else None,
            "content_nonempty": True,
        }
    except urllib.error.HTTPError as exc:
        return {
            **base,
            "status": "HTTP_ERROR",
            "http_status": exc.code,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    except (urllib.error.URLError, TimeoutError, OSError):
        return {
            **base,
            "status": "TRANSPORT_ERROR",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            **base,
            "status": "INVALID_RESPONSE",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=pathlib.Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=5, help="Maximum models to probe; 0 means all eligible models")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    args = parser.parse_args(argv)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is required; no requests were sent", file=sys.stderr)
        return 2
    if args.limit < 0 or args.timeout <= 0 or args.delay < 0:
        parser.error("--limit must be >= 0, --timeout > 0, and --delay >= 0")
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("ERROR: catalog file is missing or invalid JSON; no requests were sent", file=sys.stderr)
        return 2
    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(models, list):
        print("ERROR: catalog does not contain a models list; no requests were sent", file=sys.stderr)
        return 2
    eligible = [
        row for row in models
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and isinstance(row.get("pricing"), dict)
        and str(row["pricing"].get("prompt")) == "0"
        and str(row["pricing"].get("completion")) == "0"
        and is_text_output(row)
    ]
    eligible.sort(key=lambda row: row["id"])
    selected = eligible if args.limit == 0 else eligible[:args.limit]
    if not selected:
        print("ERROR: no zero-price text-output models found; no requests were sent", file=sys.stderr)
        return 2

    results = []
    for index, model in enumerate(selected):
        results.append(probe_model(api_key, model["id"], args.timeout))
        if index + 1 < len(selected) and args.delay:
            time.sleep(args.delay)

    artifact = {
        "artifact_version": "openrouter-free-model-probe-v1",
        "evidence_class": "CONTROLLED_LIVE_API_PROBE",
        "tested_at": utc_now(),
        "catalog_path": str(args.catalog),
        "endpoint": CHAT_URL,
        "selection": {
            "eligible_zero_price_text_models": len(eligible),
            "selected_count": len(selected),
            "limit": args.limit,
            "request_per_model": 1,
            "prompt": "Reply with the single word: OK",
            "max_tokens": 8,
        },
        "results": results,
        "summary": {
            "chat_completion_ok": sum(item["status"] == "CHAT_COMPLETION_OK" for item in results),
            "http_error": sum(item["status"] == "HTTP_ERROR" for item in results),
            "no_text_completion": sum(item["status"] == "NO_TEXT_COMPLETION" for item in results),
            "transport_error": sum(item["status"] == "TRANSPORT_ERROR" for item in results),
            "invalid_response": sum(item["status"] == "INVALID_RESPONSE" for item in results),
        },
        "qualification": {
            "jamp_execution_approved": False,
            "note": "A successful probe proves only that one minimal request returned text at tested_at. It does not qualify the model or change routing policy.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ELIGIBLE_TEXT_MODELS: {len(eligible)}")
    print(f"PROBED: {len(results)}")
    print(f"CHAT_COMPLETION_OK: {artifact['summary']['chat_completion_ok']}")
    print(f"HTTP_ERROR: {artifact['summary']['http_error']}")
    print(f"OUTPUT: {args.output}")
    print("QUALIFICATION: NOT_GRANTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
