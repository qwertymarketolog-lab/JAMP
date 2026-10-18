#!/usr/bin/env python3
"""Run controlled, minimal OpenRouter chat-completion probes for catalogued free text models.

Requires OPENROUTER_API_KEY. Results deliberately omit prompts, generated content,
authorization data, and raw provider error bodies. A successful probe is not model
qualification and does not alter JAMP routing policy.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "artifacts/research/openrouter_free_model_catalog.json"
DEFAULT_OUTPUT = ROOT / "artifacts/research/openrouter_free_model_probe.json"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
USER_AGENT = "JAMP-openrouter-controlled-probe/1.0"
PROBE_MAX_TOKENS = 64


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def zero_price(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    try:
        return Decimal(str(value)) == Decimal("0")
    except (InvalidOperation, ValueError):
        return False


def is_text_output(model: dict[str, Any]) -> bool:
    architecture = model.get("architecture")
    if not isinstance(architecture, dict):
        return False
    outputs = architecture.get("output_modalities")
    return isinstance(outputs, list) and "text" in outputs


def _safe_provider_label(value: Any) -> str | int | None:
    """Keep only short, structured provider labels; never persist arbitrary text."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 999999 else None
    if (
        isinstance(value, str)
        and 0 < len(value) <= 80
        and all(char.isalnum() or char in "._:-" for char in value)
    ):
        return value
    return None


def _provider_error_diagnostics(http_status: int, raw: bytes) -> dict[str, Any]:
    """Classify provider failures without persisting their free-form message/body."""
    decoded: Any = None
    with contextlib.suppress(UnicodeDecodeError, json.JSONDecodeError):
        decoded = json.loads(raw.decode("utf-8"))

    error = decoded.get("error") if isinstance(decoded, dict) else None
    if not isinstance(error, dict):
        error = {}
    message = error.get("message")
    structured_labels = " ".join(
        value.lower().replace("_", " ").replace("-", " ")
        for value in (error.get("code"), error.get("type"))
        if isinstance(value, str)
    )
    normalized = (message.lower() if isinstance(message, str) else "") + " " + structured_labels

    if (
        "insufficient" in normalized
        and any(word in normalized for word in ("credit", "balance", "quota"))
    ) or "out of credits" in normalized:
        category = "insufficient_credits"
    elif any(term in normalized for term in ("rate limit", "too many requests", "throttl")):
        category = "rate_limited"
    elif "no available provider" in normalized or "no provider available" in normalized:
        category = "no_provider_available"
    elif "model not found" in normalized or "unknown model" in normalized:
        category = "model_not_found"
    elif "unsupported parameter" in normalized or "parameter is not supported" in normalized:
        category = "unsupported_parameter"
    elif "invalid api key" in normalized or "unauthorized" in normalized:
        category = "authentication"
    elif "forbidden" in normalized or "permission denied" in normalized:
        category = "permission_denied"
    else:
        category = {
            400: "invalid_request",
            401: "authentication",
            402: "payment_or_credit_required",
            403: "permission_denied",
            404: "model_or_endpoint_not_found",
            408: "request_timeout",
            413: "request_too_large",
            429: "rate_limit_or_provider_capacity",
        }.get(http_status, "provider_server_error" if http_status >= 500 else "provider_http_error")

    diagnostics: dict[str, Any] = {"provider_error_category": category}
    code = _safe_provider_label(error.get("code"))
    error_type = _safe_provider_label(error.get("type"))
    if code is not None:
        diagnostics["provider_error_code"] = code
    if error_type is not None:
        diagnostics["provider_error_type"] = error_type
    return diagnostics


def _has_text_content(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        for part in content:
            if isinstance(part, str) and part.strip():
                return True
            if (
                isinstance(part, dict)
                and part.get("type") in {"text", "output_text"}
                and isinstance(part.get("text"), str)
                and part["text"].strip()
            ):
                return True
    return False


def _content_shape(content: Any) -> str:
    if content is None:
        return "missing"
    if isinstance(content, str):
        return "string"
    if isinstance(content, list):
        return "list"
    return "other"


def _response_shape(
    decoded: dict[str, Any],
    choices: Any,
    choice: Any,
    message: Any,
    content: Any,
) -> str:
    """Describe response structure without retaining provider-generated text."""
    if "choices" not in decoded:
        return "choices_missing"
    if not isinstance(choices, list):
        return "choices_invalid"
    if not choices:
        return "choices_empty"
    if not isinstance(choice, dict):
        return "choice_invalid"
    if "message" not in choice:
        return "message_missing"
    if not isinstance(message, dict):
        return "message_invalid"
    if "content" not in message:
        return "content_missing"
    if content is None:
        return "content_null"
    return f"content_{_content_shape(content)}"


def _safe_finish_reason(value: Any) -> str | None:
    if (
        isinstance(value, str)
        and 0 < len(value) <= 40
        and all(char.isalnum() or char in "._:-" for char in value)
    ):
        return value
    return None


def probe_model(api_key: str, model_id: str, timeout: float) -> dict[str, Any]:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
        "temperature": 0,
        "max_tokens": PROBE_MAX_TOKENS,
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
            return {
                **base,
                "status": "HTTP_ERROR",
                "http_status": status,
                "elapsed_ms": elapsed_ms,
                **_provider_error_diagnostics(status, raw),
            }
        if not isinstance(decoded, dict):
            return {
                **base,
                "status": "INVALID_RESPONSE",
                "http_status": status,
                "elapsed_ms": elapsed_ms,
            }
        choices = decoded.get("choices")
        choice = (
            choices[0]
            if isinstance(choices, list) and choices and isinstance(choices[0], dict)
            else None
        )
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        finish_reason = (
            _safe_finish_reason(choice.get("finish_reason")) if isinstance(choice, dict) else None
        )
        refusal = message.get("refusal") if isinstance(message, dict) else None
        common_response = {
            **base,
            "http_status": status,
            "elapsed_ms": elapsed_ms,
            "provider_response_id": (
                decoded.get("id") if isinstance(decoded.get("id"), str) else None
            ),
            "content_shape": _content_shape(content),
            "response_shape": _response_shape(decoded, choices, choice, message, content),
            "finish_reason": finish_reason,
            "refusal_present": isinstance(refusal, str) and bool(refusal.strip()),
        }
        if not _has_text_content(content):
            status = "TRUNCATED_OR_LIMITED" if finish_reason == "length" else "NO_TEXT_COMPLETION"
            return {**common_response, "status": status}
        usage = decoded.get("usage")
        return {
            **common_response,
            "status": "CHAT_COMPLETION_OK",
            "response_model": (
                decoded.get("model") if isinstance(decoded.get("model"), str) else None
            ),
            "usage": usage if isinstance(usage, dict) else None,
            "content_nonempty": True,
        }
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read(16384)
        except OSError:
            error_body = b""
        return {
            **base,
            "status": "HTTP_ERROR",
            "http_status": exc.code,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            **_provider_error_diagnostics(exc.code, error_body),
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
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum models to probe; 0 means all eligible models",
    )
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
        print(
            "ERROR: catalog file is missing or invalid JSON; no requests were sent",
            file=sys.stderr,
        )
        return 2
    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(models, list):
        print(
            "ERROR: catalog does not contain a models list; no requests were sent",
            file=sys.stderr,
        )
        return 2
    eligible = [
        row
        for row in models
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and isinstance(row.get("pricing"), dict)
        and zero_price(row["pricing"].get("prompt"))
        and zero_price(row["pricing"].get("completion"))
        and is_text_output(row)
    ]
    eligible.sort(key=lambda row: row["id"])
    selected = eligible if args.limit == 0 else eligible[: args.limit]
    if not selected:
        print(
            "ERROR: no zero-price text-output models found; no requests were sent",
            file=sys.stderr,
        )
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
            "truncated_or_limited": sum(
                item["status"] == "TRUNCATED_OR_LIMITED" for item in results
            ),
            "transport_error": sum(item["status"] == "TRANSPORT_ERROR" for item in results),
            "invalid_response": sum(item["status"] == "INVALID_RESPONSE" for item in results),
        },
        "qualification": {
            "jamp_execution_approved": False,
            "note": (
                "A successful probe proves only that one minimal request returned text at "
                "tested_at. It does not qualify the model or change routing policy."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"ELIGIBLE_TEXT_MODELS: {len(eligible)}")
    print(f"PROBED: {len(results)}")
    print(f"CHAT_COMPLETION_OK: {artifact['summary']['chat_completion_ok']}")
    print(f"HTTP_ERROR: {artifact['summary']['http_error']}")
    print(f"OUTPUT: {args.output}")
    print("QUALIFICATION: NOT_GRANTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
