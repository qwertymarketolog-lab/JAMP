from __future__ import annotations

import json
import socket
import urllib.error
import uuid
from pathlib import Path

import pytest

from scripts.research import jamp_audit_v1 as audit


@pytest.mark.parametrize(
    ("pricing_unknown", "accept", "expected"),
    [
        (True, False, True),
        (True, True, False),
        (False, False, False),
    ],
)
def test_should_refuse_matrix(pricing_unknown, accept, expected):
    assert audit.should_refuse(pricing_unknown, accept) is expected


@pytest.mark.parametrize(
    ("requests", "tokens", "wall_clock", "message"),
    [
        (audit.MAX_PAID_REQUESTS + 1, 0, 0, "request budget"),
        (0, audit.MAX_TOKENS_TOTAL + 1, 0, "token budget"),
        (0, 0, audit.MAX_WALL_CLOCK_SECONDS + 1, "Wall-clock budget"),
    ],
)
def test_budget_exceeded_before_transport(requests, tokens, wall_clock, message):
    calls = []

    def transport(_request, _timeout):
        calls.append("called")
        return 200, b"{}"

    with pytest.raises(ValueError, match=message):
        audit.run_paid(
            transport, object(), 1,
            requests=requests, tokens=tokens, wall_clock=wall_clock,
        )
    assert calls == []


def test_classification_distinguishes_pre_send_and_post_send():
    assert audit.classify_exception("pre_send") is audit.FinalStatus.PRE_SEND_NETWORK_ERROR
    assert audit.classify_exception("post_send") is audit.FinalStatus.POST_SEND_AMBIGUOUS


def test_run_paid_classifies_dns_failure_as_pre_send():
    def transport(_request, _timeout):
        raise urllib.error.URLError(socket.gaierror("DNS lookup failed"))

    with pytest.raises(audit.PaidTransportError) as raised:
        audit.run_paid(
            transport, object(), 1, requests=1, tokens=4096, wall_clock=0,
        )
    assert raised.value.status is audit.FinalStatus.PRE_SEND_NETWORK_ERROR


def test_run_paid_calls_transport_once_on_ambiguous_failure():
    calls = []

    def transport(_request, _timeout):
        calls.append("called")
        raise TimeoutError("connection timed out after send")

    with pytest.raises(audit.PaidTransportError) as raised:
        audit.run_paid(
            transport, object(), 1, requests=1, tokens=4096, wall_clock=0,
        )
    assert raised.value.status is audit.FinalStatus.POST_SEND_AMBIGUOUS
    assert calls == ["called"]


def test_post_send_ambiguous_stops_before_next_model(tmp_path, monkeypatch):
    experiment_id = str(uuid.uuid4())
    output_dir = tmp_path / experiment_id
    output_dir.mkdir()
    selected = ["model_001", "model_002"]
    catalog = {
        "data": [
            {"id": audit.MODEL_REGISTRY[key]["model_id"]} for key in selected
        ]
    }
    raw = json.dumps(catalog).encode("utf-8")
    snapshot = output_dir / "catalog_snapshot.json"
    snapshot.write_bytes(raw)
    (output_dir / "preflight.json").write_text(
        json.dumps({
            "experiment_id": experiment_id,
            "catalog_sha256": audit.sha256(raw),
            "selected_model_keys": selected,
            "available_models": selected,
            "skipped_models": [],
            "repository_commit_sha": "a" * 40,
            "cost_status": "UNKNOWN_PRICING",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "git_commit_sha", lambda: "a" * 40)
    monkeypatch.setattr(audit, "is_first_run", lambda *_args: False)
    monkeypatch.setenv("ANYMODEL_API_KEY", "test-key")
    calls = []

    class AmbiguousOpener:
        def open(self, _request, timeout):
            calls.append(timeout)
            raise TimeoutError("ambiguous transport failure")

    monkeypatch.setattr(
        audit.urllib.request, "build_opener", lambda *_args: AmbiguousOpener()
    )

    with pytest.raises(RuntimeError, match="POST_SEND_AMBIGUOUS"):
        audit.execute(
            selected, experiment_id, snapshot, audit.sha256(raw), 0, output_dir,
            accept_unknown_pricing=True,
        )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert manifest["executed_models"] == ["model_001"]
    assert manifest["not_started_models"] == ["model_002"]
    assert manifest["failed_models"][0]["status"] == "POST_SEND_AMBIGUOUS"


def test_execute_false_guardrail_artifact_keeps_unknown_pricing(tmp_path):
    outcome = audit.write_guardrail_preflight(tmp_path, accept_unknown_pricing=False)
    record = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))

    assert outcome == "refused"
    assert record["execution_requested"] is False
    assert record["catalog_preflight"] == "NOT_RUN"
    assert record["cost_status"] == "UNKNOWN_PRICING"
    assert record["paid_requests_sent"] == 0


def test_accept_unknown_pricing_records_success_without_paid_execution(tmp_path):
    outcome = audit.write_guardrail_preflight(tmp_path, accept_unknown_pricing=True)
    record = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))

    assert outcome == "success"
    assert record["cost_status"] == "UNKNOWN_PRICING"
    assert record["execution_requested"] is False
    assert record["paid_requests_sent"] == 0

def test_guardrails_file_is_collected_and_reports_case_count(request, capsys):
    """Expose the exact collected test-file count in the quiet full-suite CI log."""
    this_file = Path(__file__).resolve()
    collected = [
        item for item in request.session.items
        if Path(str(item.path)).resolve() == this_file
    ]
    with capsys.disabled():
        print(
            f"GUARDRAILS_FILE_EXECUTED: {this_file.name}; collected={len(collected)}"
        )
    assert collected
