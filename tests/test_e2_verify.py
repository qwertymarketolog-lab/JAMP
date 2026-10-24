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
    assert verify_generation(
        {"provider_response_id": "gen-123", "provider_model_id": " "}
    )[0] == "UNVERIFIABLE"


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
def test_verify_inconclusive_on_transport_error(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError
    status, details = verify_generation(
        {"provider_response_id": "gen-1", "provider_model_id": "z-ai/glm-5.3"},
        api_key="fake",
    )
    assert status == "INCONCLUSIVE"
    assert details["reason"] == "API_ERROR"
