from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest

from scripts.research import verdict_harness as harness

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_INPUT_HASHES = {
    "docs/experiments/jamp_audit_v1/AUDIT_PROMPT.md": "4e02860ea088d7f6c5aa4d311b35abfad18c515bd78a2b64999ea5260e405b0e",
    "docs/experiments/jamp_audit_v1/INPUT_PACK.md": "4c5aaae052429709ae06536599e22eaec039cff702b9a74cc4d14f770a5cba18",
}


def _evidence(evidence_id: str = "ev-1") -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_type": "file",
        "source_reference": "docs/README.md",
        "sha256": "a" * 64,
        "captured_at": "2026-11-14T00:00:00Z",
        "description": "A source file inspected by a human reviewer.",
    }


def _claim(status: str = "OBSERVED", evidence_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "claim_id": "local-claim-1",
        "statement": "The supplied pack records a specific repository state.",
        "status": status,
        "source_model": "model-a",
        "evidence_ids": evidence_ids or [],
    }


def _resolution(decision: str = "VERIFIED") -> dict[str, object]:
    return {
        "resolution_id": "resolution-1",
        "claim_id": "local-claim-1",
        "decision": decision,
        "evidence_ids": ["ev-1"],
        "reviewer": "human-reviewer",
        "rationale": "The cited source was independently inspected.",
        "resolved_at": "2026-11-14T00:00:00Z",
    }


def test_input_hashes_match_literal_contract():
    assert harness.hash_input_files(ROOT) == EXPECTED_INPUT_HASHES
    for relative_path, expected in EXPECTED_INPUT_HASHES.items():
        assert hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest() == expected


def test_hash_changes_when_one_byte_changes(tmp_path):
    source = tmp_path / "input.md"
    source.write_bytes(b"same")
    first = harness.sha256_bytes(source.read_bytes())
    source.write_bytes(b"samf")
    assert harness.sha256_bytes(source.read_bytes()) != first


def test_hash_stability_across_clean_clone_with_autocrlf(tmp_path):
    clone = tmp_path / "clean-clone"
    subprocess.run(
        ["git", "-c", "core.autocrlf=true", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(clone)],
        check=True,
        capture_output=True,
        text=True,
    )
    for relative_path in EXPECTED_INPUT_HASHES:
        original = (ROOT / relative_path).read_bytes()
        copied = (clone / relative_path).read_bytes()
        assert copied == original
        assert hashlib.sha256(copied).hexdigest() == hashlib.sha256(original).hexdigest()


def test_response_body_and_text_hashes_are_explicit():
    raw = '{"answer":"ok"}'.encode("utf-8")
    result = harness.hash_response_body(raw)
    assert result["response_body_bytes_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["response_text_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["reason"] is None


def test_invalid_response_encoding_preserves_body_hash():
    result = harness.hash_response_body(b"\xff", encoding="utf-8")
    assert result["response_body_bytes_sha256"] == hashlib.sha256(b"\xff").hexdigest()
    assert result["response_text_sha256"] is None
    assert result["reason"] == "RESPONSE_TEXT_DECODE_ERROR"


def test_raw_json_response_is_observed():
    payload = {
        "schema_version": "1.0",
        "model_id": "model-a",
        "task_answers": {
            "work_assessment": "assessment",
            "improvement_opportunities": "gaps",
            "six_month_plan": {"NOW": [], "NEXT": [], "LATER": []},
        },
        "claims": [_claim()],
    }
    result = harness.parse_model_response(json.dumps(payload).encode("utf-8"))
    assert result["status"] == "OBSERVED"
    assert result["reason"] is None
    assert result["payload"]["model_id"] == "model-a"


@pytest.mark.parametrize(
    "raw",
    [
        b"\x60\x60\x60json\n{\"schema_version\":\"1.0\"}\n\x60\x60\x60",
        b"not json",
        b"",
        b"[1,2,3]",
    ],
)
def test_malformed_response_including_markdown_fence_is_unknown(raw):
    result = harness.parse_model_response(raw)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "MALFORMED_RESPONSE"
    assert result["payload"] is None


def test_claim_schema_accepts_exact_six_statuses():
    schema = json.loads((harness.SCHEMA_DIR / "claim.schema.json").read_text(encoding="utf-8"))
    expected = [
        "OBSERVED", "INFERRED", "UNKNOWN", "VERIFICATION_CANDIDATE", "VERIFIED", "AMBIGUOUS"
    ]
    assert schema["properties"]["status"]["enum"] == expected
    for status in expected:
        harness.validate_schema_instance(_claim(status), schema)


def test_unknown_claim_status_fails_closed():
    with pytest.raises(ValueError, match="enum"):
        harness.validate_claim(_claim("QUALIFIED"), [])


def test_malformed_claim_record_fails_closed():
    with pytest.raises(ValueError, match="missing required"):
        harness.validate_claim({"claim_id": "x"}, [])


def test_verified_without_evidence_is_rejected():
    with pytest.raises(ValueError, match="requires at least one evidence_id"):
        harness.validate_claim(_claim("VERIFIED"), [])


def test_verified_with_evidence_without_human_resolution_is_candidate():
    result = harness.validate_claim(_claim("VERIFIED", ["ev-1"]), [_evidence()])
    assert result["status"] == "VERIFICATION_CANDIDATE"


def test_verified_with_evidence_and_human_resolution_is_verified():
    result = harness.validate_claim(_claim("VERIFIED", ["ev-1"]), [_evidence()], _resolution())
    assert result["status"] == "VERIFIED"


def test_resolution_cannot_verify_without_evidence():
    resolution = _resolution()
    resolution["evidence_ids"] = []
    with pytest.raises(ValueError, match="requires evidence"):
        harness.validate_claim(_claim("VERIFIED", ["ev-1"]), [_evidence()], resolution)


def test_model_consensus_is_not_a_verdict():
    claims = [_claim("OBSERVED"), _claim("OBSERVED")]
    assert all(harness.validate_claim(item, [])["status"] != "VERIFIED" for item in claims)


def test_claim_vs_claim_conflict_requires_human_matching():
    participants = [
        {"model": "model-a", "claim": "The check passed."},
        {"model": "model-b", "claim": "The check failed."},
    ]
    with pytest.raises(ValueError, match="Human matching"):
        harness.create_ambiguous_conflict(
            conflict_id="conflict-1", conflict_type="claim_vs_claim",
            claim_id="global-claim-1", human_matched=False, participants=participants,
        )
    result = harness.create_ambiguous_conflict(
        conflict_id="conflict-1", conflict_type="claim_vs_claim",
        claim_id="global-claim-1", human_matched=True, participants=participants,
    )
    assert result["status"] == "AMBIGUOUS"
    assert result["resolution"] is None


def test_claim_vs_evidence_conflict_is_ambiguous_unresolved():
    result = harness.create_ambiguous_conflict(
        conflict_id="conflict-2", conflict_type="claim_vs_evidence",
        claim_id="global-claim-2", human_matched=True,
        participants=[{"model": "model-a", "claim": "The check passed."}],
        evidence_id="ev-1", evidence_records=[_evidence()],
    )
    assert result["status"] == "AMBIGUOUS"
    assert result["resolution"] is None
    assert result["evidence_id"] == "ev-1"


def test_harness_path_is_offline(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: pytest.fail("network used"))
    assert harness.validate_claim(_claim(), [])["status"] == "OBSERVED"
    assert harness.hash_input_files(ROOT) == EXPECTED_INPUT_HASHES
