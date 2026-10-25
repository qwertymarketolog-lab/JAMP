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
        return "INCONCLUSIVE", {"reason": "API_KEY_MISSING"}

    request = urllib.request.Request(f"{OPENROUTER_GENERATION_URL}?id={urllib.parse.quote(gen_id)}")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("User-Agent", "JAMP-Trust-Layer/1.0")

    parsed = None
    last_exc = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                parsed = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and attempt < 4:
                last_exc = exc
                time.sleep(5)
                continue
            if exc.code == 429 and attempt < 2:
                last_exc = exc
                time.sleep(2)
                continue
            error_body = exc.read().decode("utf-8", errors="replace")[:500]
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "http_status": exc.code,
                "error_body": error_body,
            }
        except urllib.error.URLError as exc:
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "network_error": str(exc.reason),
            }
        except Exception as exc:
            return "INCONCLUSIVE", {
                "reason": "API_ERROR",
                "exception_type": type(exc).__name__,
                "error_message": str(exc),
            }

    if parsed is None:
        error_body = last_exc.read().decode("utf-8", errors="replace")[:500] if last_exc else ""
        return "INCONCLUSIVE", {
            "reason": "API_ERROR",
            "http_status": getattr(last_exc, "code", 500),
            "error_body": error_body,
            "error_message": "Max retries exceeded for 404/429",
        }

    if not isinstance(parsed, dict):
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE"}

    data = parsed.get("data")
    if not isinstance(data, dict):
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE"}

    provider_model = data.get("model")
    if not isinstance(provider_model, str) or not provider_model:
        return "INCONCLUSIVE", {"reason": "MALFORMED_RESPONSE"}

    details = {
        "provider_model": provider_model,
        "provider_name": data.get("provider_name"),
        "generation_id": gen_id,
    }

    if _model_matches(jamp_model, provider_model):
        return "VERIFIED", details

    return "CONTRADICTED", {**details, "jamp_model": jamp_model}
