from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

OPENROUTER_GENERATION_URL = "https://openrouter.ai/api/v1/generation"
NOT_FOUND_BACKOFF_SECONDS = (1, 2, 4, 8, 16)


def _model_matches(jamp_model: str, provider_model: str) -> bool:
    if jamp_model == provider_model:
        return True
    if provider_model.startswith(jamp_model + "-"):
        suffix = provider_model[len(jamp_model) :]
        return bool(re.fullmatch(r"-\d+(\.\d+)*", suffix))
    return False


def verify_generation(
    execution_details: dict[str, Any],
    timeout: float = 5.0,
    api_key: str | None = None,
) -> tuple[str, dict[str, Any]]:
    gen_id = execution_details.get("provider_response_id")
    jamp_model = execution_details.get("provider_model_id")

    if not isinstance(gen_id, str) or not gen_id.strip():
        return "UNVERIFIABLE", {"reason": "PROVIDER_RESPONSE_ID_MISSING"}

    if not isinstance(jamp_model, str) or not jamp_model.strip():
        return "UNVERIFIABLE", {"reason": "PROVIDER_MODEL_ID_MISSING"}

    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return "INCONCLUSIVE", {"reason": "API_KEY_MISSING", "attempts": []}

    request = urllib.request.Request(f"{OPENROUTER_GENERATION_URL}?id={urllib.parse.quote(gen_id)}")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("User-Agent", "JAMP-Trust-Layer/1.0")

    parsed = None
    last_exc: urllib.error.HTTPError | None = None
    not_found_attempt = 0
    rate_limit_retried = False
    server_error_retried = False
    timeout_retried = False
    attempts: list[dict[str, Any]] = []
    attempt_number = 0

    while True:
        attempt_number += 1
        attempt_started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                parsed = json.load(response)
                http_status = getattr(response, "status", None)
                if not isinstance(http_status, int):
                    http_status = response.getcode()
                if not isinstance(http_status, int):
                    http_status = 200
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": http_status,
                    "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
                    "result": "success",
                }
            )
            break
        except urllib.error.HTTPError as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": exc.code,
                    "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
                }
            )
            if exc.code == 404 and not_found_attempt < len(NOT_FOUND_BACKOFF_SECONDS):
                last_exc = exc
                delay = NOT_FOUND_BACKOFF_SECONDS[not_found_attempt]
                not_found_attempt += 1
                time.sleep(delay)
                continue
            if exc.code == 429 and not rate_limit_retried:
                last_exc = exc
                rate_limit_retried = True
                time.sleep(30)
                continue
            if 500 <= exc.code <= 599 and not server_error_retried:
                last_exc = exc
                server_error_retried = True
                time.sleep(5)
                continue
            error_body = exc.read().decode("utf-8", errors="replace")[:500]
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "http_status": exc.code,
                "error_body": error_body,
                "attempts": attempts,
                "retry_count": (
                    not_found_attempt
                    + int(rate_limit_retried)
                    + int(server_error_retried)
                    + int(timeout_retried)
                ),
            }
        except TimeoutError as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": None,
                    "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
                    "error": type(exc).__name__,
                }
            )
            if not timeout_retried:
                timeout_retried = True
                time.sleep(5)
                continue
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "exception_type": type(exc).__name__,
                "error_message": str(exc),
                "attempts": attempts,
                "retry_count": (
                    not_found_attempt
                    + int(rate_limit_retried)
                    + int(server_error_retried)
                    + int(timeout_retried)
                ),
            }
        except urllib.error.URLError as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": None,
                    "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
                    "error": type(exc.reason).__name__,
                }
            )
            if isinstance(exc.reason, TimeoutError) and not timeout_retried:
                timeout_retried = True
                time.sleep(5)
                continue
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "network_error": str(exc.reason),
                "attempts": attempts,
                "retry_count": (
                    not_found_attempt
                    + int(rate_limit_retried)
                    + int(server_error_retried)
                    + int(timeout_retried)
                ),
            }
        except Exception as exc:
            attempts.append(
                {
                    "attempt": attempt_number,
                    "http_status": None,
                    "elapsed_ms": max(0, int((time.monotonic() - attempt_started) * 1000)),
                    "error": type(exc).__name__,
                }
            )
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "exception_type": type(exc).__name__,
                "error_message": str(exc),
                "attempts": attempts,
                "retry_count": (
                    not_found_attempt
                    + int(rate_limit_retried)
                    + int(server_error_retried)
                    + int(timeout_retried)
                ),
            }

    if parsed is None:
        error_body = last_exc.read().decode("utf-8", errors="replace")[:500] if last_exc else ""
        return "INCONCLUSIVE", {
            "reason": "API_ERROR",
            "http_status": getattr(last_exc, "code", 500),
            "error_body": error_body,
            "error_message": "Generation remained unavailable after retry policy was exhausted",
            "attempts": attempts,
            "retry_count": (
                not_found_attempt
                + int(rate_limit_retried)
                + int(server_error_retried)
                + int(timeout_retried)
            ),
        }

    if not isinstance(parsed, dict):
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE", "attempts": attempts}

    data = parsed.get("data")
    if not isinstance(data, dict):
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE", "attempts": attempts}

    provider_model = data.get("model")
    if not isinstance(provider_model, str) or not provider_model:
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE", "attempts": attempts}

    details = {
        "provider_model": provider_model,
        "provider_name": data.get("provider_name"),
        "generation_id": gen_id,
        "attempts": attempts,
        "retry_count": (
            not_found_attempt
            + int(rate_limit_retried)
            + int(server_error_retried)
            + int(timeout_retried)
        ),
    }

    if _model_matches(jamp_model, provider_model):
        return "VERIFIED", details

    return "CONTRADICTED", {**details, "jamp_model": jamp_model}
