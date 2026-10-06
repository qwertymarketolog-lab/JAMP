from unittest.mock import MagicMock, patch

import pytest

from jamp.client.adapter import AdapterResult, JampClientAdapter
from jamp.client.cli import main as cli_main


@patch("jamp.client.adapter.httpx.post")
def test_adapter_execute_flow(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "EXECUTE",
        "trace_id": "trace_exec_123",
        "selected_model": "model_01",
        "output": "Processed search response",
    }
    mock_post.return_value = mock_response

    result = JampClientAdapter("http://testserver").execute_payload({"prompt": "test search"})

    assert isinstance(result, AdapterResult)
    assert result.status == "EXECUTE"
    assert result.trace_id == "trace_exec_123"
    assert result.selected_model == "model_01"
    assert result.output == "Processed search response"


@patch("jamp.client.adapter.httpx.post")
def test_adapter_refuse_flow(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "REFUSE",
        "trace_id": "trace_refuse_456",
        "reason": "FAIL_CLOSED_ZERO_QUALIFIED_MODELS",
    }
    mock_post.return_value = mock_response

    result = JampClientAdapter("http://testserver").execute_payload(
        {"prompt": "long context query"}
    )

    assert result.status == "REFUSE"
    assert result.trace_id == "trace_refuse_456"
    assert result.reason == "FAIL_CLOSED_ZERO_QUALIFIED_MODELS"


@patch("jamp.client.adapter.httpx.post")
def test_adapter_refuse_422_flow(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {
        "status": "REFUSE",
        "reason": "Unknown task intent",
        "trace_id": "trace_refuse_422",
    }
    mock_post.return_value = mock_response

    result = JampClientAdapter("http://testserver").execute_payload({"intent": "unknown"})

    assert result.status == "REFUSE"
    assert result.trace_id == "trace_refuse_422"
    assert result.reason == "Unknown task intent"


@patch("jamp.client.adapter.httpx.post")
def test_cli_execution_output(mock_post, capsys):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "EXECUTE",
        "trace_id": "trace_cli_789",
        "selected_model": "model_02",
        "output": "CLI Output Success",
    }
    mock_post.return_value = mock_response

    exit_code = cli_main(["execute", "hello world"])

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "status: EXECUTE" in captured
    assert "trace_id: trace_cli_789" in captured
    assert "model: model_02" in captured
    assert "output: CLI Output Success" in captured


@patch("jamp.client.adapter.httpx.post")
def test_cli_refuse_output(mock_post, capsys):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "REFUSE",
        "trace_id": "trace_cli_refuse",
        "reason": "FAIL_CLOSED_ZERO_QUALIFIED_MODELS",
    }
    mock_post.return_value = mock_response

    assert cli_main(["execute", "blocked request"]) == 0
    captured = capsys.readouterr().out
    assert "status: REFUSE" in captured
    assert "trace_id: trace_cli_refuse" in captured
    assert "reason: FAIL_CLOSED_ZERO_QUALIFIED_MODELS" in captured


@patch("jamp.client.adapter.httpx.post")
def test_adapter_rejects_unknown_status(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "UNKNOWN", "trace_id": "trace_bad"}
    mock_post.return_value = mock_response

    with pytest.raises(RuntimeError, match="unknown contract status"):
        JampClientAdapter().execute_payload({"prompt": "test"})
