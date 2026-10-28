import io
import urllib.error
from unittest.mock import MagicMock, patch

from jamp.provider.e2_verify import _model_matches, verify_generation


def test_model_matches():
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3") is True
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-20260826") is True
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-1.2") is True
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-flash") is False
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-1..2") is False
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-1.") is False
    assert _model_matches("z-ai/glm-5.3", "z-ai/glm-5.3-") is False


def test_verify_missing_fields():
    assert verify_generation({})[0] == "UNVERIFIABLE"
    assert verify_generation({"provider_response_id": ""})[1]["reason"] == (
        "PROVIDER_RESPONSE_ID_MISSING"
    )
    assert verify_generation({"provider_response_id": "gen-123"})[1]["reason"] == (
        "PROVIDER_MODEL_ID_MISSING"
    )
    assert (
        verify_generation({"provider_response_id": "gen-123", "provider_model_id": " "})[0]
        == "UNVERIFIABLE"
    )


@patch("urllib.request.urlopen")
def test_verify_verified(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = (
        b'{"data": {"model": "z-ai/glm-5.3-2026", "provider_name": "CoreWeave"}}'
    )
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert details["generation_id"] == "gen-1"
    request = mock_urlopen.call_args.args[0]
    assert request.get_header("User-agent") == "JAMP-Trust-Layer/1.0"


@patch("urllib.request.urlopen")
def test_verify_contradicted(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data": {"model": "openai/gpt-4"}}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "CONTRADICTED"
    assert details["jamp_model"] == "z-ai/glm-5.3"


@patch("urllib.request.urlopen")
def test_verify_http_error_diagnostics(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/generation?id=gen-1",
        403,
        "Forbidden",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"forbidden"}'),
    )
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["reason"] == "API_ERROR"
    assert details["http_status"] == 403
    assert details["error_body"] == '{"error":"forbidden"}'
    assert details["retry_count"] == 0
    assert len(details["attempts"]) == 1
    assert details["attempts"][0]["http_status"] == 403


@patch("urllib.request.urlopen")
def test_verify_url_error_diagnostics(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("name resolution failed")
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["reason"] == "API_ERROR"
    assert details["network_error"] == "name resolution failed"
    assert details["retry_count"] == 0
    assert len(details["attempts"]) == 1
    assert details["attempts"][0]["http_status"] is None


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_inconclusive_after_timeout_retry(mock_urlopen, mock_sleep):
    mock_urlopen.side_effect = [
        TimeoutError("generation request timed out"),
        TimeoutError("generation request timed out"),
    ]
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["reason"] == "API_ERROR"
    assert details["exception_type"] == "TimeoutError"
    assert details["error_message"] == "generation request timed out"
    assert details["retry_count"] == 1
    assert len(details["attempts"]) == 2
    assert [item["http_status"] for item in details["attempts"]] == [None, None]
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(5)


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_retries_404_then_succeeds(mock_urlopen, mock_sleep):
    mock_resp = MagicMock()
    mock_resp.read.return_value = (
        b'{"data": {"model": "z-ai/glm-5.3", "provider_name": "CoreWeave"}}'
    )
    mock_urlopen.side_effect = [
        urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"generation not found"}'),
        ),
        MagicMock(__enter__=MagicMock(return_value=mock_resp)),
    ]
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert details["generation_id"] == "gen-1"
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_retries_404_five_attempts_then_inconclusive(mock_urlopen, mock_sleep):
    errors = [
        urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"generation not found"}'),
        )
        for _ in range(6)
    ]
    mock_urlopen.side_effect = errors
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["http_status"] == 404
    assert mock_urlopen.call_count == 6
    assert [call.args[0] for call in mock_sleep.call_args_list] == [1, 2, 4, 8, 16]


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_retries_429(mock_urlopen, mock_sleep):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data": {"model": "z-ai/glm-5.3"}}'
    mock_urlopen.side_effect = [
        urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            429,
            "Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        ),
        MagicMock(__enter__=MagicMock(return_value=mock_resp)),
    ]
    status, _ = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(30)


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_retries_5xx_once_then_succeeds(mock_urlopen, mock_sleep):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data": {"model": "z-ai/glm-5.3"}}'
    mock_urlopen.side_effect = [
        urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"temporary"}'),
        ),
        MagicMock(__enter__=MagicMock(return_value=mock_resp)),
    ]
    status, _ = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(5)


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_retries_timeout_once_then_succeeds(mock_urlopen, mock_sleep):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data": {"model": "z-ai/glm-5.3"}}'
    mock_urlopen.side_effect = [
        TimeoutError("temporary timeout"),
        MagicMock(__enter__=MagicMock(return_value=mock_resp)),
    ]
    status, _ = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(5)


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_verify_does_not_retry_other_4xx(mock_urlopen, mock_sleep):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/generation?id=gen-1",
        403,
        "Forbidden",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"forbidden"}'),
    )
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["http_status"] == 403
    mock_urlopen.assert_called_once()
    mock_sleep.assert_not_called()



@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_e2_attempts_logged_on_success(mock_urlopen, mock_sleep):
    def http_error():
        return urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"generation not found"}'),
        )

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = (
        b'{"data": {"model": "z-ai/glm-5.3", "provider_name": "CoreWeave"}}'
    )
    mock_urlopen.side_effect = [
        http_error(),
        http_error(),
        MagicMock(__enter__=MagicMock(return_value=mock_resp)),
    ]
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "VERIFIED"
    assert len(details["attempts"]) == 3
    assert [item["http_status"] for item in details["attempts"]] == [404, 404, 200]
    assert all(isinstance(item["elapsed_ms"], int) for item in details["attempts"])
    assert details["attempts"][-1]["result"] == "success"
    assert [call.args[0] for call in mock_sleep.call_args_list] == [1, 2]


@patch("jamp.provider.e2_verify.time.sleep")
@patch("urllib.request.urlopen")
def test_e2_attempts_logged_on_failure(mock_urlopen, mock_sleep):
    errors = [
        urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/generation?id=gen-1",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"generation not found"}'),
        )
        for _ in range(6)
    ]
    mock_urlopen.side_effect = errors
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["reason"] == "API_ERROR"
    assert len(details["attempts"]) == 6
    assert [item["http_status"] for item in details["attempts"]] == [404] * 6
    assert all(isinstance(item["elapsed_ms"], int) for item in details["attempts"])
    assert [call.args[0] for call in mock_sleep.call_args_list] == [1, 2, 4, 8, 16]
