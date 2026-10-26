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


def test_http_502_exports_remote_provenance_before_failing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trace_id = "trace_refused_502"
    trace = {
        "trace_id": trace_id,
        "status": "REFUSE",
        "refusal_reason": "E2_VERIFICATION_INCONCLUSIVE",
        "failure_diagnostics": {"evidence_status": "INCONCLUSIVE"},
    }
    calls: list[tuple[str, bool]] = []

    def fake_http_json(
        url: str,
        *,
        payload: dict | None = None,
        allow_http_errors: bool = False,
    ) -> tuple[int, dict]:
        calls.append((url, allow_http_errors))
        if url.endswith("/v1/execute"):
            assert allow_http_errors is True
            return 502, {
                "status": "REFUSE",
                "reason": "E2_VERIFICATION_INCONCLUSIVE",
                "trace_id": trace_id,
            }
        assert url == f"http://pilot/v1/provenance/{trace_id}"
        return 200, trace

    monkeypatch.setattr(pilot, "_http_json", fake_http_json)
    monkeypatch.setattr(
        pilot,
        "run_pilot",
        lambda: pilot._execute_with_provenance(
            "http://pilot",
            {"intent": "search_and_extraction"},
            tmp_path / "provenance_traces.jsonl",
        ),
    )

    assert pilot.main() == 1

    provenance_path = tmp_path / "provenance.json"
    assert provenance_path.is_file()
    assert __import__("json").loads(provenance_path.read_text(encoding="utf-8")) == trace
    assert calls == [
        ("http://pilot/v1/execute", True),
        (f"http://pilot/v1/provenance/{trace_id}", False),
    ]
    captured = capsys.readouterr()
    assert "[PILOT] REFUSE: E2_VERIFICATION_INCONCLUSIVE" in captured.err
    assert "Execution refused: status=502" in captured.err
