"""Demonstrate the B2B Trust Layer contract with an in-process API client.

This is a deterministic contract demonstration using FastAPI TestClient and
mocked E2/E3 boundaries. It does not contact an external JAMP deployment or
prove production-network interoperability.
"""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch

from jamp.api import create_app
from jamp.runtime.verdict import JampVerdict

PROMPT = "Извлеки данные: Выручка $1,000,000, Расходы $200,000."


def main() -> int:
    from fastapi.testclient import TestClient

    app_module = importlib.import_module("jamp.api.app")

    def deterministic_executor(model: str, payload: dict[str, object]) -> dict[str, str]:
        del payload
        return {
            "provider": "openrouter",
            "model": model,
            "provider_response_id": "b2b-client-contract-fixture",
            "provider_model_id": "fixture/b2b-contract-model",
            "content": "Выручка: $1,000,000; Расходы: $200,000.",
        }

    # Keep this experiment deterministic and offline: E2/E3 are explicit mocks.
    with (
        patch.dict(
            os.environ,
            {"JAMP_SIGNING_KEY": "b2b-client-test-signing-key", "JAMP_ENV": "test"},
        ),
        patch.object(
            app_module,
            "verify_generation",
            return_value=("VERIFIED", {"reason": "B2B_CLIENT_TEST_FIXTURE"}),
        ),
        patch.object(
            app_module,
            "evaluate_model_qualification",
            return_value="QUALIFIED",
        ),
    ):
        client = TestClient(create_app(executor=deterministic_executor))
        response = client.post(
            "/v1/execute",
            json={"intent": "search_and_extraction", "prompt": PROMPT},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"/v1/execute refused the test request: HTTP {response.status_code}"
            )

        body = response.json()
        if (
            body.get("status") != "EXECUTE"
            or body.get("evidence_status") != "VERIFIED"
            or body.get("qualification") != "QUALIFIED"
        ):
            raise RuntimeError("Execution did not satisfy the mocked E2/E3 contract")

        raw_verdict = body.get("verdict")
        if not isinstance(raw_verdict, dict):
            raise RuntimeError("Execution response did not include a verdict object")
        verdict = JampVerdict.from_dict(raw_verdict)
        print(f"[B2B CLIENT] Received verdict: {verdict.status}.")

        valid_response = client.post("/v1/verify-verdict", json=verdict.to_dict())
        if valid_response.status_code != 200 or valid_response.json() != {"valid": True}:
            raise RuntimeError("Signature validation rejected the original verdict")
        print("[B2B CLIENT] Cryptographic signature validation: VALID.")

        signature = verdict.signature
        if not isinstance(signature, str) or not signature:
            raise RuntimeError("Verdict does not contain a signature")
        changed_first_character = "0" if signature[0] != "0" else "1"
        tampered = verdict.to_dict()
        tampered["signature"] = changed_first_character + signature[1:]

        tampered_response = client.post("/v1/verify-verdict", json=tampered)
        if (
            tampered_response.status_code != 200
            or tampered_response.json() != {"valid": False}
        ):
            raise RuntimeError("Signature validator did not reject the tampered verdict")
        print("[B2B CLIENT] Tampered signature validation: INVALID.")
        print("RESULT: B2B TRUST LAYER CONTRACT FULLY VERIFIED.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
