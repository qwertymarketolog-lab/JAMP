from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
REPORT_PATH = HERE / "sample_report.txt"
EXPECTED_PATH = HERE / "expected_data.json"
PROMPT = (
    "Извлеки из текста: квартал, выручку (revenue), операционные расходы "
    "(operating_expenses), чистую прибыль (net_income) и судебные издержки "
    "(legal_fees). Верни ТОЛЬКО валидный JSON без лишних слов, используя эти ключи.\n\n"
)
NUMERIC_KEYS = ("revenue", "operating_expenses", "net_income", "legal_fees")

PROVIDER_DIAGNOSTIC_FIELDS = {
    "code",
    "provider_http_status",
    "http_status",
    "error_body",
    "network_error",
    "exception_type",
    "error_message",
    "selected_model",
    "model",
    "requested_model_id",
    "provider_requested_model_id",
    "crosswalk_digest",
    "finish_reason",
    "content_len",
    "reasoning_len",
    "requested_max_tokens",
    "evidence_status",
    "reason",
    "output_provider",
    "output_response_id",
    "output_model_id",
    "fallback_history",
}


def extract_safe_provider_diagnostics(
    trace_payload: Any,
) -> dict[str, str | int | float | bool | None]:
    """Extract allowlisted scalar diagnostics and sanitized fallback history."""
    if not isinstance(trace_payload, dict):
        return {}
    refusal_details = trace_payload.get("refusal_details")
    if not isinstance(refusal_details, dict):
        return {}
    diagnostics = refusal_details.get("provider_diagnostics")
    if not isinstance(diagnostics, dict):
        return {}

    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in diagnostics.items():
        if key not in PROVIDER_DIAGNOSTIC_FIELDS:
            continue
        if isinstance(value, (str, int, float, bool, type(None))):
            safe[key] = value
            continue
        if key != "fallback_history" or not isinstance(value, list):
            continue

        # Do not dump arbitrary nested provider data; keep only the fields
        # persisted by FallbackChainExecutor and sanitize them again here.
        history: list[dict[str, str | int]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            provider = item.get("provider")
            requested_model = item.get("requested_model")
            http_status = item.get("http_status")
            error = item.get("error")
            safe_item: dict[str, str | int] = {}
            if isinstance(provider, str):
                safe_item["provider"] = provider[:80]
            if isinstance(requested_model, str):
                safe_item["requested_model"] = requested_model[:160]
            if (
                isinstance(http_status, int)
                and not isinstance(http_status, bool)
                and 100 <= http_status <= 599
            ):
                safe_item["http_status"] = http_status
            if isinstance(error, str):
                safe_item["error"] = error[:150]
            if safe_item:
                history.append(safe_item)
        safe[key] = json.dumps(history, ensure_ascii=False, sort_keys=True)
    return safe


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating surrounding prose only as a diagnostic aid."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
    if not isinstance(value, dict):
        raise ValueError("model output did not contain a JSON object")
    return value


def values_match(actual: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for key in ("quarter", *NUMERIC_KEYS):
        if key not in actual:
            mismatches.append(f"{key}: missing")
            continue
        if key == "quarter":
            if actual[key] != expected[key]:
                mismatches.append(f"{key}: expected {expected[key]!r}, got {actual[key]!r}")
            continue
        if isinstance(actual[key], bool) or not isinstance(actual[key], (int, float, str)):
            mismatches.append(f"{key}: not a numeric value")
            continue
        try:
            actual_number = Decimal(str(actual[key]).replace(",", ""))
            expected_number = Decimal(str(expected[key]))
        except InvalidOperation:
            mismatches.append(f"{key}: not a valid number")
            continue
        if not actual_number.is_finite() or actual_number != expected_number:
            mismatches.append(f"{key}: expected {expected_number}, got {actual[key]!r}")
    return not mismatches, mismatches


def main() -> int:
    report = REPORT_PATH.read_text(encoding="utf-8")
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    base_url = os.environ.get("JAMP_API_URL", "http://127.0.0.1:8000").rstrip("/")
    request_body = json.dumps(
        {"intent": "search_and_extraction", "prompt": PROMPT + report},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{base_url}/v1/execute",
        data=request_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=float(os.environ.get("JAMP_API_TIMEOUT", "90"))) as response:
            payload = json.loads(response.read().decode("utf-8"))
            http_status = response.status
    except HTTPError as exc:
        http_status = exc.code
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"error": "non-JSON HTTP error response"}
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"[DATA MATCH] UNKNOWN — JAMP API request failed: {type(exc).__name__}: {exc}")
        print("[MODEL VERIFIED] UNKNOWN — no verifiable API response")
        print("trace_id: UNKNOWN")
        return 2

    trace_id = payload.get("trace_id", "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
    evidence_status = payload.get("evidence_status") if isinstance(payload, dict) else None
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(evidence_status, str) and isinstance(output, dict):
        evidence_status = output.get("evidence_status")

    # Dump the complete API payload only when the experiment cannot establish a clean result.
    # This is diagnostic evidence; it does not change any gate or qualification decision.
    if (
        http_status < 200
        or http_status >= 300
        or not isinstance(payload, dict)
        or payload.get("status") != "EXECUTE"
        or evidence_status != "VERIFIED"
    ):
        print("\\n[DEBUG] FULL JAMP RESPONSE:")
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        print("--------------------------------------------------\\n")

    if evidence_status == "VERIFIED":
        model_line = "YES — evidence_status=VERIFIED"
    elif evidence_status == "CONTRADICTED":
        model_line = "NO — evidence_status=CONTRADICTED"
    elif evidence_status:
        model_line = f"UNKNOWN — evidence_status={evidence_status}"
    else:
        model_line = "UNKNOWN — response does not expose evidence_status"

    print(f"[MODEL VERIFIED] {model_line}")
    print(f"trace_id: {trace_id}")

    if http_status < 200 or http_status >= 300 or not isinstance(payload, dict):
        # Read the persisted trace and print only an explicit allowlist of non-secret fields.
        if trace_id != "UNKNOWN":
            try:
                trace_request = Request(
                    f"{base_url}/v1/provenance/{trace_id}",
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urlopen(trace_request, timeout=10) as trace_response:
                    trace_payload = json.loads(trace_response.read().decode("utf-8"))
                safe_diagnostics = extract_safe_provider_diagnostics(trace_payload)
                refusal = trace_payload.get("refusal_details", {})
                if not isinstance(refusal, dict):
                    refusal = {}
                diag = safe_diagnostics
                try:
                    safe_fallback_history = json.loads(diag.get("fallback_history", "[]"))
                except (TypeError, json.JSONDecodeError):
                    safe_fallback_history = []
                safe_diag = {
                    "provider": diag.get("output_provider"),
                    "provider_model_id": diag.get("output_model_id"),
                    "provider_response_id": diag.get("output_response_id"),
                    "fallback_history": safe_fallback_history,
                    "refusal_reason": refusal.get("reason"),
                    "provider_diagnostics": diag,
                }
                print(
                    "[SAFE PROVIDER DIAGNOSTICS] "
                    + json.dumps(safe_diag, sort_keys=True, ensure_ascii=False)
                )
                if safe_diagnostics:
                    print(
                        "[PROVIDER DIAGNOSTICS] "
                        + json.dumps(safe_diagnostics, sort_keys=True, ensure_ascii=False)
                    )
                else:
                    print(
                        "[PROVIDER DIAGNOSTICS] NONE — "
                        "no approved scalar diagnostics in refusal trace"
                    )
            except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
                print("[PROVIDER DIAGNOSTICS] UNAVAILABLE — trace could not be read")
        error_status = payload.get("status", "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
        error_reason = (
            payload.get("reason", payload.get("error", "UNKNOWN"))
            if isinstance(payload, dict)
            else "UNKNOWN"
        )
        print(
            "[DATA MATCH] NOT RUN — "
            f"HTTP {http_status}; status={error_status}; "
            f"reason={error_reason}"
        )
        return 1

    if payload.get("status") != "EXECUTE":
        print(
            "[DATA MATCH] NOT RUN — JAMP did not execute: "
            f"status={payload.get('status')!r}, reason={payload.get('reason')!r}"
        )
        return 1

    if not isinstance(output, dict) or not isinstance(output.get("content"), str):
        print("[DATA MATCH] FAIL — response.output.content is missing or not text")
        return 1

    try:
        extracted = parse_json_object(output["content"])
    except ValueError as exc:
        print(f"[DATA MATCH] FAIL — {exc}")
        return 1

    matched, mismatches = values_match(extracted, expected)
    print(f"[DATA MATCH] {'YES' if matched else 'NO'}")
    for mismatch in mismatches:
        print(f"  - {mismatch}")

    # E2 identity verification and extraction correctness are independent dimensions.
    if evidence_status != "VERIFIED":
        print("[RESULT] HOLD — model identity is not VERIFIED by the API response")
        return 1
    if not matched:
        print("[RESULT] FAIL — extracted data differs from the reference values")
        return 1
    print("[RESULT] PASS — reference values matched and model identity was VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
