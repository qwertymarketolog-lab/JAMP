from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

from scripts.research import openrouter_probe_free_models as probe


def test_probe_model_records_success_without_generated_text_or_secret(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "response-123",
                    "model": "provider/model:free",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "OK, private generated text"},
                        }
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 1},
                }
            ).encode("utf-8")

    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "CHAT_COMPLETION_OK"
    assert result["http_status"] == 200
    assert result["provider_response_id"] == "response-123"
    assert result["usage"]["completion_tokens"] == 1
    assert result["finish_reason"] == "stop"
    assert result["content_shape"] == "string"
    assert seen["url"] == probe.CHAT_URL
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"]["model"] == "provider/model:free"
    assert probe.PROBE_MAX_TOKENS == 64
    assert seen["payload"]["max_tokens"] == probe.PROBE_MAX_TOKENS
    assert "test-secret" not in repr(result)
    assert "private generated text" not in repr(result)


def test_probe_model_accepts_structured_text_content_without_storing_text(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "response-list",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": [
                                    {"type": "text", "text": "structured private output"},
                                ]
                            },
                        }
                    ],
                }
            ).encode("utf-8")

    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda request, timeout: Response())
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "CHAT_COMPLETION_OK"
    assert result["content_shape"] == "list"
    assert result["content_nonempty"] is True
    assert "structured private output" not in repr(result)


def test_probe_model_classifies_http_error_without_storing_free_form_message(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            probe.CHAT_URL,
            429,
            "rate limited",
            hdrs=None,
            fp=BytesIO(
                b'{"error":{"code":"rate_limit_exceeded","type":"rate_limit_error",'
                b'"message":"sensitive provider detail"}}'
            ),
        )

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "HTTP_ERROR"
    assert result["http_status"] == 429
    assert result["provider_error_category"] == "rate_limited"
    assert result["provider_error_code"] == "rate_limit_exceeded"
    assert result["provider_error_type"] == "rate_limit_error"
    assert "sensitive provider detail" not in repr(result)
    assert "test-secret" not in repr(result)


def test_probe_model_keeps_generic_category_when_error_body_is_unstructured(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            probe.CHAT_URL,
            429,
            "rate limited",
            hdrs=None,
            fp=BytesIO(b'{"error":"sensitive provider detail"}'),
        )

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "HTTP_ERROR"
    assert result["http_status"] == 429
    assert result["provider_error_category"] == "rate_limit_or_provider_capacity"
    assert "sensitive provider detail" not in repr(result)
    assert "test-secret" not in repr(result)


def test_probe_model_classifies_empty_length_limited_response_without_text(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"finish_reason": "length", "message": {}}]}).encode(
                "utf-8"
            )

    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda request, timeout: Response())
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "TRUNCATED_OR_LIMITED"
    assert result["finish_reason"] == "length"
    assert result["content_shape"] == "missing"
    assert result["response_shape"] == "content_missing"
    assert "test-secret" not in repr(result)


def test_probe_model_distinguishes_missing_message_without_text(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"finish_reason": "stop"}]}).encode("utf-8")

    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda request, timeout: Response())
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "NO_TEXT_COMPLETION"
    assert result["response_shape"] == "message_missing"
    assert "test-secret" not in repr(result)


def test_probe_model_distinguishes_missing_choices_without_text(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"id": "response-no-choices"}).encode("utf-8")

    monkeypatch.setattr(probe.urllib.request, "urlopen", lambda request, timeout: Response())
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "NO_TEXT_COMPLETION"
    assert result["response_shape"] == "choices_missing"
    assert "test-secret" not in repr(result)


def test_text_output_requires_explicit_text_modality():
    assert probe.is_text_output({"architecture": {"output_modalities": ["text"]}})
    assert probe.is_text_output({"architecture": {"output_modalities": ["text", "audio"]}})
    assert not probe.is_text_output({"architecture": {"output_modalities": ["audio"]}})
    assert not probe.is_text_output({"architecture": {}})


def test_probe_model_distinguishes_missing_content_from_empty_text(monkeypatch):
    class Response:
        status = 200

        def __init__(self, content_marker):
            self.content_marker = content_marker

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            message = {}
            if self.content_marker is not None:
                message["content"] = self.content_marker
            return json.dumps({"choices": [{"finish_reason": "stop", "message": message}]}).encode(
                "utf-8"
            )

    for content_marker, expected_shape, expected_status in (
        (None, "content_missing", "NO_TEXT_COMPLETION"),
        ("   ", "content_string", "NO_TEXT_COMPLETION"),
    ):
        monkeypatch.setattr(
            probe.urllib.request,
            "urlopen",
            lambda request, timeout, marker=content_marker: Response(marker),
        )
        result = probe.probe_model("test-secret", "provider/model:free", 4)
        assert result["status"] == expected_status
        assert result["response_shape"] == expected_shape
        assert result["content_shape"] == ("missing" if content_marker is None else "string")
        assert "test-secret" not in repr(result)
        assert "Reply with the single word" not in repr(result)


def test_probe_artifact_records_actual_max_tokens_and_no_generated_text(monkeypatch, tmp_path):
    catalog_path = tmp_path / "catalog.json"
    output_path = tmp_path / "probe.json"
    catalog_path.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "provider/model:free",
                        "pricing": {"prompt": "0", "completion": "0"},
                        "architecture": {"output_modalities": ["text"]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setattr(
        probe,
        "probe_model",
        lambda api_key, model_id, timeout: {
            "model_id": model_id,
            "status": "CHAT_COMPLETION_OK",
            "content_nonempty": True,
        },
    )

    assert (
        probe.main(
            [
                "--catalog",
                str(catalog_path),
                "--output",
                str(output_path),
                "--limit",
                "1",
                "--delay",
                "0",
            ]
        )
        == 0
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["selection"]["max_tokens"] == probe.PROBE_MAX_TOKENS
    assert "test-secret" not in output_path.read_text(encoding="utf-8")
    assert "content" not in artifact["results"][0]
    assert "generated_text" not in artifact["results"][0]
