from __future__ import annotations

import hashlib
import http.client
import io
import json
import urllib.error
from unittest.mock import patch

import pytest

import scripts.research.stage_b_benchmark as stage_b


def test_catalog_preflight_requires_exactly_one_model_and_valid_coefficients() -> None:
    rows = [
        {"id": stage_b.MODELS[0], "billing": {"coefficient": {"input": 0.5, "output": 1}}},
        {"id": stage_b.MODELS[1], "billing": {"coefficient": 2}},
        {"id": stage_b.MODELS[2], "billing": {"coefficient": {"input": 4, "output": 3}}},
    ]
    assert stage_b.preflight(rows) == {
        stage_b.MODELS[0]: (0.5, 1.0),
        stage_b.MODELS[1]: (2.0, 2.0),
        stage_b.MODELS[2]: (4.0, 3.0),
    }


@pytest.mark.parametrize(
    "billing",
    [
        {},
        {"coefficient": {"input": 0.5}},
        {"coefficient": {"input": True, "output": 1}},
        {"coefficient": {"input": float("nan"), "output": 1}},
        {"coefficient": {"input": -1, "output": 1}},
        {"coefficient": "0.5"},
    ],
)
def test_preflight_fails_closed_on_invalid_coefficient(billing: dict) -> None:
    rows = [{"id": model, "billing": billing} for model in stage_b.MODELS]
    with pytest.raises(ValueError, match="coefficient"):
        stage_b.preflight(rows)


def test_preflight_rejects_duplicate_model_ids() -> None:
    row = {"id": stage_b.MODELS[0], "billing": {"coefficient": 1}}
    with pytest.raises(ValueError, match="exact catalog match"):
        stage_b.preflight([row, row] + [
            {"id": model, "billing": {"coefficient": 1}}
            for model in stage_b.MODELS[1:]
        ])


def test_catalog_requires_data_list() -> None:
    with pytest.raises(ValueError, match="data must be a list"):
        stage_b.catalog_models(b'{"data": {}}')


@pytest.mark.parametrize("value", [0, 1, 100])
def test_usage_accepts_nonnegative_integers(value: int) -> None:
    assert stage_b.valid_usage_int(value)


@pytest.mark.parametrize("value", [True, -1, 1.5, "2", None])
def test_usage_rejects_invalid_values(value: object) -> None:
    assert not stage_b.valid_usage_int(value)


def test_worst_case_budget_covers_all_nine_requests() -> None:
    coefficients = {model: (1.0, 2.0) for model in stage_b.MODELS}
    prompts = ["a", "bb", "ccc"]
    expected_input_bound = (1 + 1024) + (2 + 1024) + (3 + 1024)
    assert stage_b.worst_case_budget(coefficients, prompts) == (
        3 * expected_input_bound + 9 * 2 * 2048
    )


def test_redirect_is_not_followed_and_only_one_http_attempt_occurs() -> None:
    class FakeOpener:
        calls = 0

        def open(self, request, timeout=120):
            self.calls += 1
            raise urllib.error.HTTPError(
                request.full_url, 302, "redirect", {}, io.BytesIO(b"redirect")
            )

    fake = FakeOpener()
    with patch("urllib.request.build_opener", return_value=fake):
        response = stage_b.request_once("POST", "https://example.invalid", "fake-key", {"x": 1})
    assert response["http_status"] == 302
    assert response["raw_body"] == b"redirect"
    assert fake.calls == 1


def test_redirect_handler_refuses_redirect() -> None:
    assert stage_b.NoRedirect().redirect_request(
        None, None, 302, "Found", {}, "https://example.invalid"
    ) is None


def test_request_once_records_incomplete_read_without_retry() -> None:
    class FakeResponse:
        status = 200
        headers = {"Transfer-Encoding": "chunked"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            raise http.client.IncompleteRead(b'{"partial":', 100)

    class FakeOpener:
        calls = 0

        def open(self, request, timeout=120):
            self.calls += 1
            return FakeResponse()

    fake = FakeOpener()
    with patch("urllib.request.build_opener", return_value=fake):
        response = stage_b.request_once("POST", "https://example.invalid", "fake-key", {"x": 1})
    assert fake.calls == 1
    assert response["transport_status"] == "INCOMPLETE_READ"
    assert response["billing_status"] == "UNKNOWN"
    assert response["raw_body"] == b'{"partial":'


def test_resume_loader_verifies_all_success_payload_hashes(tmp_path) -> None:
    rows = []
    for index, (model, task_id) in enumerate(sorted(stage_b.RESUME_EXPECTED_SUCCESS)):
        name = f"response_{index}.json"
        raw = b'{"ok":true}'
        (tmp_path / name).write_bytes(raw)
        rows.append({
            "model_id": model, "task_id": task_id, "status": "SUCCESS",
            "raw_response_file": name, "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        })
    catalog_raw = b'{"data":[]}'
    (tmp_path / "catalog_raw.json").write_bytes(catalog_raw)
    manifest = {
        "github": {"run_id": stage_b.RESUME_SOURCE_RUN_ID, "sha": stage_b.RESUME_SOURCE_SHA},
        "status": "RUNNING", "completed_requests": 7,
        "frozen_core": {"delta_zero": True, "observed_blob": stage_b.FROZEN_BLOB},
        "results": rows,
        "catalog": {
            "http_status": 200,
            "sha256": hashlib.sha256(catalog_raw).hexdigest(),
        },
    }
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _, loaded, _ = stage_b.load_resume_evidence(tmp_path)
    assert len(loaded) == 7
    (tmp_path / rows[0]["raw_response_file"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="INTEGRITY_MISMATCH"):
        stage_b.load_resume_evidence(tmp_path)


def test_default_resume_plan_only_schedules_unfinished_astra_task5() -> None:
    successes = [
        {"model_id": model, "task_id": task_id, "status": "SUCCESS"}
        for model, task_id in stage_b.RESUME_EXPECTED_SUCCESS
    ]
    assert stage_b.plan_pending_tasks(successes, retry_astra_task2=False) == [
        ("cx/gpt-6-astra", "task5")
    ]
    assert stage_b.plan_pending_tasks(successes, retry_astra_task2=True) == [
        ("cx/gpt-6-astra", "task2"),
        ("cx/gpt-6-astra", "task5"),
    ]


def _response(content: str | None, finish_reason: str) -> dict:
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
            }
        ]
    }


def test_classification_of_empty_and_truncated_responses() -> None:
    deepseek = _response("", "length")
    nemotron = _response("Partial answer", "length")

    assert stage_b.classify_response_body(deepseek) == "RESPONSE_EMPTY"
    assert stage_b.classify_response_body(nemotron) == "RESPONSE_TRUNCATED"


def test_complete_response_requires_stop_and_nonempty_content() -> None:
    assert (
        stage_b.classify_response_body(_response("Answer", "stop"))
        == "RESPONSE_COMPLETE"
    )
    assert stage_b.classify_response_body(_response(None, "stop")) == "RESPONSE_EMPTY"
    assert (
        stage_b.classify_response_body(_response("Partial", "content_filter"))
        == "RESPONSE_INCOMPLETE"
    )


def test_prompt_hash_records_exact_utf8_bytes() -> None:
    prompt = "Проверка JAMP"
    assert stage_b.prompt_sha256(prompt) == hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()
