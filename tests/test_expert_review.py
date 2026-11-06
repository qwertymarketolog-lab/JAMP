from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "experiments" / "expert-review" / "run_expert.py"
SPEC = importlib.util.spec_from_file_location("jamp_expert_review_runner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class FakeExecutor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, model_id, payload):
        self.calls.append((model_id, payload))
        return self.result


def catalog_for(model_id):
    raw = json.dumps({"data": [{"id": model_id}]}).encode()
    return lambda _api_key: (raw, [{"id": model_id}])


def test_role_selects_pinned_model_and_correct_prompt(tmp_path):
    role = "architect"
    model_id = RUNNER.ROLE_MODELS[role]
    executor = FakeExecutor({
        "provider": "anymodel",
        "provider_model_id": "provider/claude-sonnet",
        "provider_response_id": "response-1",
        "content": "raw expert answer",
    })
    metadata = RUNNER.run_review(
        role,
        api_key="test-secret",
        output_dir=tmp_path,
        catalog_fetcher=catalog_for(model_id),
        executor=executor,
    )
    assert executor.calls[0][0] == model_id
    assert "API Architect" in executor.calls[0][1]["prompt"]
    assert metadata["requested_model_id"] == model_id
    assert metadata["provider_model_id"] == "provider/claude-sonnet"


def test_response_bytes_are_preserved_and_hash_is_of_persisted_file(tmp_path):
    text = "Точный ответ.\nSecond line — unchanged."
    model_id = RUNNER.ROLE_MODELS["ux"]
    executor = FakeExecutor({
        "provider": "anymodel",
        "provider_model_id": "provider/model-b",
        "content": text,
    })
    metadata = RUNNER.run_review(
        "ux",
        api_key="test-secret",
        output_dir=tmp_path,
        catalog_fetcher=catalog_for(model_id),
        executor=executor,
    )
    raw = (tmp_path / "ux" / "response.md").read_bytes()
    assert raw == text.encode("utf-8")
    assert metadata["response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert metadata["temperature"] == 0.0


def test_absent_provider_model_id_is_not_replaced_and_evidence_is_saved(tmp_path):
    model_id = RUNNER.ROLE_MODELS["auditor"]
    executor = FakeExecutor({"provider": "anymodel", "content": "answer without identity"})
    with pytest.raises(RUNNER.ReviewError, match="provider_model_id missing"):
        RUNNER.run_review(
            "auditor",
            api_key="test-secret",
            output_dir=tmp_path,
            catalog_fetcher=catalog_for(model_id),
            executor=executor,
        )
    metadata = json.loads((tmp_path / "auditor" / "metadata.json").read_text())
    assert metadata["requested_model_id"] == model_id
    assert metadata["provider_model_id"] is None
    assert metadata["provider_identity_status"] == "UNKNOWN"
    assert (tmp_path / "auditor" / "response.md").read_text() == "answer without identity"


def test_model_must_be_present_exactly_once_in_live_catalog(tmp_path):
    with pytest.raises(RUNNER.ReviewError, match="not uniquely present"):
        RUNNER.run_review(
            "architect",
            api_key="test-secret",
            output_dir=tmp_path,
            catalog_fetcher=lambda _key: (b'{"data":[]}', []),
            executor=FakeExecutor({"content": "unused"}),
        )


def test_missing_api_key_fails_before_catalog_or_provider_call(tmp_path):
    def forbidden(_key):
        raise AssertionError("catalog must not be called")
    with pytest.raises(RUNNER.ReviewError, match="ANYMODEL_API_KEY"):
        RUNNER.run_review(
            "ux",
            api_key="",
            output_dir=tmp_path,
            catalog_fetcher=forbidden,
            executor=FakeExecutor({"content": "unused"}),
        )


def test_provider_failure_is_sanitized_and_does_not_leak_secret(tmp_path):
    secret = "super-secret-token"

    class BrokenExecutor:
        def __call__(self, _model_id, _payload):
            raise RuntimeError(secret)

    with pytest.raises(RUNNER.ReviewError) as caught:
        RUNNER.run_review(
            "auditor",
            api_key=secret,
            output_dir=tmp_path,
            catalog_fetcher=catalog_for(RUNNER.ROLE_MODELS["auditor"]),
            executor=BrokenExecutor(),
        )
    assert secret not in str(caught.value)


def test_dispatch_expands_all_and_preserves_single_role():
    assert RUNNER.roles_for_dispatch("all") == ["architect", "ux", "auditor"]
    assert RUNNER.roles_for_dispatch("ux") == ["ux"]
    with pytest.raises(RUNNER.ReviewError, match="Unsupported role"):
        RUNNER.roles_for_dispatch("unknown")
