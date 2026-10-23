import pytest

from jamp.provider.e2_provenance import verify_generation_provenance
from jamp.runtime import AuditPersistence, ProvenanceTracker


def _persisted_execution_details(tmp_path, output_overrides=None):
    output = {
        "provider": "openrouter",
        "provider_response_id": "gen-e2-test-123",
        "provider_model_id": "z-ai/glm-5.3-flash-20260826",
        "qualification": "UNKNOWN",
    }
    output.update(output_overrides or {})
    trace = ProvenanceTracker().create_trace(
        task_profile="search_and_extraction",
        required_caps=("C01",),
        action="EXECUTE",
        selected_model="z-ai/glm-5.3-flash",
        eligible_count=1,
        output=output,
    )
    persistence = AuditPersistence(tmp_path / "audit.jsonl")
    persistence.write_trace(trace)
    persisted = persistence.read_trace_by_id(trace["trace_id"])
    assert persisted is not None
    return persisted["execution_details"]


def test_provider_response_id_survives_trace_persistence(tmp_path):
    details = _persisted_execution_details(tmp_path)

    assert details["provider_response_id"] == "gen-e2-test-123"
    assert details["provider_model_id"] == "z-ai/glm-5.3-flash-20260826"
    assert details["qualification"] == "UNKNOWN"


def test_e2_verifier_accepts_matching_generation_metadata(tmp_path):
    details = _persisted_execution_details(tmp_path)
    generation = {
        "data": {
            "id": "gen-e2-test-123",
            "model": "z-ai/glm-5.3-flash-20260826",
        }
    }

    assert verify_generation_provenance(details, generation) == {
        "status": "VERIFIED",
        "reason": "GENERATION_METADATA_MATCH",
    }


@pytest.mark.parametrize(
    ("generation", "reason"),
    [
        (
            {"id": "gen-other", "model": "z-ai/glm-5.3-flash-20260826"},
            "PROVIDER_RESPONSE_ID_MISMATCH",
        ),
        (
            {"id": "gen-e2-test-123", "model": "z-ai/glm-5.3-flash"},
            "PROVIDER_MODEL_ID_MISMATCH",
        ),
    ],
)
def test_e2_verifier_contradicts_mismatched_metadata(tmp_path, generation, reason):
    details = _persisted_execution_details(tmp_path)

    result = verify_generation_provenance(details, generation)

    assert result == {"status": "CONTRADICTED", "reason": reason}


@pytest.mark.parametrize(
    ("details", "generation", "reason"),
    [
        (
            None,
            {"id": "gen-e2-test-123", "model": "z-ai/glm-5.3-flash-20260826"},
            "EXECUTION_DETAILS_INVALID",
        ),
        (
            {},
            {"id": "gen-e2-test-123", "model": "z-ai/glm-5.3-flash-20260826"},
            "REQUIRED_PROVENANCE_MISSING",
        ),
        (
            {
                "provider_response_id": "gen-e2-test-123",
                "provider_model_id": "z-ai/glm-5.3-flash-20260826",
            },
            {"data": None},
            "GENERATION_METADATA_INVALID",
        ),
        (
            {
                "provider_response_id": "gen-e2-test-123",
                "provider_model_id": "z-ai/glm-5.3-flash-20260826",
            },
            {"id": "gen-e2-test-123"},
            "REQUIRED_PROVENANCE_MISSING",
        ),
    ],
)
def test_e2_verifier_fails_closed_on_missing_or_invalid_evidence(
    details, generation, reason
):
    assert verify_generation_provenance(details, generation) == {
        "status": "INCONCLUSIVE",
        "reason": reason,
    }


def test_e2_verifier_accepts_observed_openrouter_date_suffix(tmp_path):
    details = _persisted_execution_details(
        tmp_path,
        {"provider_model_id": "z-ai/glm-5.3-flash"},
    )
    generation = {
        "data": {
            "id": "gen-e2-test-123",
            "model": "z-ai/glm-5.3-flash-20260826",
        }
    }

    assert verify_generation_provenance(details, generation) == {
        "status": "VERIFIED",
        "reason": "MODEL_DATE_SUFFIX_MATCH",
    }


def test_e2_verifier_rejects_arbitrary_model_prefix_extension(tmp_path):
    details = _persisted_execution_details(
        tmp_path,
        {"provider_model_id": "z-ai/glm-5.3-flash"},
    )
    generation = {
        "id": "gen-e2-test-123",
        "model": "z-ai/glm-5.3-flash-unexpected",
    }

    assert verify_generation_provenance(details, generation) == {
        "status": "CONTRADICTED",
        "reason": "PROVIDER_MODEL_ID_MISMATCH",
    }


def test_exact_model_identity_is_required_not_prefix_similarity(tmp_path):
    details = _persisted_execution_details(tmp_path)
    generation = {
        "id": "gen-e2-test-123",
        "model": "z-ai/glm-5.3-flash",
    }

    result = verify_generation_provenance(details, generation)

    assert result["status"] == "CONTRADICTED"
    assert result["reason"] == "PROVIDER_MODEL_ID_MISMATCH"
