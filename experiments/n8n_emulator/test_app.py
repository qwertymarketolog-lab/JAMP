"""Test-only app factory for the n8n emulator.

Deterministic executor + E2 fixture, by the same pattern as B2B client
(experiments/b2b_client/run_b2b_client.py). HTTP server, routes,
verdict creation, HMAC signature, and verify-verdict are real.

This factory does NOT qualify the real OpenRouter provider. Provider
behaviour is covered separately by tests/test_openrouter_telegram_mvp.py.

Pre-#463 main: jamp.api.auth is absent, try/except returns plain app.
Cleanup: issue #466.
"""

import importlib
import json
from typing import Any

from jamp.api.app import create_app


def _deterministic_executor(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "openrouter",
        "model": model,
        "provider_response_id": "stage10-n8n-fixture",
        "provider_model_id": model,
        "content": json.dumps({"result": "stage10-fixture"}),
    }


def _deterministic_e2_fixture(execution_details: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return "VERIFIED", {"reason": "STAGE10_DETERMINISTIC_FIXTURE"}


def create_app_with_bypass():
    app_module = importlib.import_module("jamp.api.app")
    app_module.verify_generation = _deterministic_e2_fixture

    app = create_app(executor=_deterministic_executor)

    try:
        from jamp.api.auth import OrganizationContext, require_api_key
    except ImportError:
        return app
    app.dependency_overrides[require_api_key] = lambda: OrganizationContext("n8n-test", "n8n-test")
    return app
