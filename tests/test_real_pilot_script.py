from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/b2b_client/run_real_pilot.py"
SPEC = importlib.util.spec_from_file_location("run_real_pilot", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def _valid_response() -> dict:
    return {
        "status": "EXECUTE",
        "trace_id": "trace_current",
        "evidence_status": "VERIFIED",
        "qualification": "QUALIFIED",
        "output": {
            "provider": "openrouter",
            "provider_requested_model_id": "z-ai/glm-5.3-flash",
            "provider_model_id": "z-ai/glm-5.3-flash",
            "provider_response_id": "gen_current",
            "content": "Выручка: 1000000; Расходы: 200000",
        },
        "verdict": {
            "trace_id": "trace_current",
            "status": "VERIFIED",
            "provider_model_id": "z-ai/glm-5.3-flash",
            "evidence_hash": "sha256:current-output",
            "timestamp": 1.0,
            "signature": "test-signature",
        },
    }


def test_execution_contract_requires_actual_direct_model_and_verified_evidence() -> None:
    model, verdict = pilot.validate_execution_response(_valid_response())
    assert model == "z-ai/glm-5.3-flash"
    assert verdict["trace_id"] == "trace_current"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.update(status="REFUSE"), "refused"),
        (lambda r: r.update(evidence_status="INCONCLUSIVE"), "not VERIFIED"),
        (lambda r: r["output"].update(provider_model_id="other/model"), "Unexpected actual"),
        (lambda r: r["verdict"].update(trace_id="trace_old"), "does not match"),
        (lambda r: r["verdict"].update(status="INCONCLUSIVE"), "not VERIFIED"),
        (lambda r: r["output"].update(provider_response_id=""), "response ID is missing"),
    ],
)
def test_execution_contract_fails_closed(mutate, message: str) -> None:
    response = _valid_response()
    mutate(response)
    with pytest.raises(pilot.PilotError, match=message):
        pilot.validate_execution_response(response)


def test_missing_secrets_fail_before_server_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-key")

    def forbidden_port() -> int:
        pytest.fail("server setup must not occur when the provider key is missing")

    monkeypatch.setattr(pilot, "_free_port", forbidden_port)
    with pytest.raises(pilot.PilotError, match="OPENROUTER_API_KEY"):
        pilot.run_pilot()
