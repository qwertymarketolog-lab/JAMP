from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_example_001_is_explicitly_schema_only() -> None:
    example = json.loads(
        (ROOT / "docs/research/examples/example-001.json").read_text(encoding="utf-8")
    )

    assert example["status"] == "SCHEMA_ONLY"
    assert example["reference_status"] == "PENDING_FIRST_FULL_EVIDENCE_RUN"
    assert example["evidence_refs"] == "TBD"
    assert example["historical_partial_evidence"]["classification"] == (
        "PARTIAL_ONLY_NOT_CONFORMANCE"
    )
    assert example["historical_partial_evidence"]["qualification"] == "NOT_GRANTED"


def test_example_001_declares_all_required_evidence_classes() -> None:
    example = json.loads(
        (ROOT / "docs/research/examples/example-001.json").read_text(encoding="utf-8")
    )

    expected = {
        "raw_webhook_payload",
        "jamp_runtime_log",
        "provider_request_export",
        "provider_response_export",
        "telegram_send_result",
        "execution_timing_export",
    }
    assert set(example["evidence_classes"]) == expected
    assert set(example["specification_template"]["evidence_classes"]) == expected


def test_example_001_scope_is_one_run_not_sla_or_performance() -> None:
    example = json.loads(
        (ROOT / "docs/research/examples/example-001.json").read_text(encoding="utf-8")
    )

    scope = example["scope"]
    assert scope["conformance_unit"] == "one_execution"
    assert "SLA" in scope["explicit_exclusions"]
    assert "performance qualification" in scope["explicit_exclusions"]


def test_artifact_source_resolves_exact_hypothesis_and_prediction_records() -> None:
    from jamp.research.specification_gate import ArtifactSource

    # The resolver surface is part of the ArtifactSource contract; behavior
    # and A2 failure semantics are covered in test_specification_gate.py.
    assert callable(getattr(ArtifactSource, "get_hypothesis", None))
    assert callable(getattr(ArtifactSource, "get_prediction", None))
