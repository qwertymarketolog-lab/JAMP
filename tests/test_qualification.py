from __future__ import annotations

import json

from jamp.runtime import qualification


def test_registered_benchmark_qualification_is_returned(monkeypatch):
    monkeypatch.setitem(
        qualification.QUALIFICATION_REGISTRY,
        ("fixture/model-qualified", "search_and_extraction"),
        "QUALIFIED",
    )

    assert (
        qualification.evaluate_model_qualification(
            "fixture/model-qualified", "search_and_extraction"
        )
        == "QUALIFIED"
    )


def test_measured_complete_benchmark_qualifies_exact_model(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "MEASURED",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification("z-ai/glm-5.3-flash", "search_and_extraction")
        == "QUALIFIED"
    )


def test_measured_benchmark_version_mismatch_fails_closed_to_unknown(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "MEASURED",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash",
            "search_and_extraction",
            required_benchmark_version="v2",
        )
        == "UNKNOWN"
    )


def test_measured_benchmark_v1_qualifies_when_v1_is_required(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "MEASURED",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification("z-ai/glm-5.3-flash", "search_and_extraction")
        == "QUALIFIED"
    )


def test_measured_benchmark_with_incomplete_or_wrong_model_evidence_stays_unknown(
    tmp_path, monkeypatch
):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "MEASURED",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["some-other-model"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification("z-ai/glm-5.3-flash", "search_and_extraction")
        == "UNKNOWN"
    )


def test_unverified_measurement_status_fails_closed_to_unknown(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "UNVERIFIED",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash", "search_and_extraction"
        )
        == "UNKNOWN"
    )



def test_missing_measurement_status_fails_closed_to_unknown(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                        "provenance": {
                            "run_id": 40224203624,
                            "job_id": 121262016244,
                            "artifact_id": 12609974893,
                            "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash", "search_and_extraction"
        )
        == "UNKNOWN"
    )



def test_missing_provenance_fails_closed_to_unknown(tmp_path, monkeypatch):
    measured_path = tmp_path / "measured_benchmarks.json"
    measured_path.write_text(
        json.dumps(
            {
                "z-ai/glm-5.3-flash": {
                    "search_and_extraction": {
                        "score": 1.0,
                        "benchmark_version": "v1",
                        "status": "QUALIFIED",
                        "measurement_status": "MEASURED",
                        "case_count": 5,
                        "passed_cases": 5,
                        "actual_provider_model_ids": ["z-ai/glm-5.3-flash"] * 5,
                        "all_e2_verified": True,
                        "benchmark_data_sha256": "a" * 64,
                        "timestamp": "2026-10-25T17:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qualification, "MEASURED_BENCHMARKS_PATH", measured_path)

    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash", "search_and_extraction"
        )
        == "UNKNOWN"
    )


def test_committed_glm_measurement_with_primary_artifact_provenance_qualifies():
    result = qualification._load_measured_benchmark_result(
        "z-ai/glm-5.3-flash", "search_and_extraction"
    )
    assert result is not None
    assert result["provenance"] == {
        "run_id": 40224203624,
        "job_id": 121262016244,
        "artifact_id": 12609974893,
        "artifact_sha256": "4ebab6674dba08c19c7d6b12b6896d4df18c514f1329e0c0342bd629e0254cfa",
    }
    assert (
        qualification.evaluate_model_qualification(
            "z-ai/glm-5.3-flash", "search_and_extraction"
        )
        == "QUALIFIED"
    )


def test_unknown_model_fails_closed_to_unknown():
    assert (
        qualification.evaluate_model_qualification("unknown/model", "search_and_extraction")
        == "UNKNOWN"
    )


def test_verified_glm_benchmark_with_provenance_qualifies():
    assert (
        qualification.evaluate_model_qualification("z-ai/glm-5.3-flash", "search_and_extraction")
        == "QUALIFIED"
    )


def test_invalid_model_or_task_fails_closed():
    assert qualification.evaluate_model_qualification("", "search_and_extraction") == "UNKNOWN"
    assert qualification.evaluate_model_qualification("fixture/model-qualified", "") == "UNKNOWN"


def test_execute_returns_qualification_and_records_it_in_trace(monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "qualification-test-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )

    client = TestClient(
        app_module.create_app(
            executor=lambda model, payload: {
                "provider": "openrouter",
                "model": model,
                "provider_response_id": "generation-qualification-test",
                "provider_model_id": "z-ai/glm-5.3-flash",
                "content": "reference values extracted",
            }
        )
    )
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Extract the reference values"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == "VERIFIED"
    assert body["qualification"] == "QUALIFIED"
    trace = client.get(f"/v1/provenance/{body['trace_id']}").json()
    assert trace["execution_details"]["qualification"] == "QUALIFIED"
