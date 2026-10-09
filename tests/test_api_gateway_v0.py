import pytest
from pydantic import ValidationError

from src.jamp.api.dto import (
    AttachmentUploadRequest,
    ChatCompletionRequest,
    ChatMessage,
    ExecutionRequest,
    ExecutionResult,
)


def test_attachment_upload_dto_validation():
    req = AttachmentUploadRequest(
        filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    assert req.filename == "photo.jpg"

    with pytest.raises(ValidationError):
        AttachmentUploadRequest(
            filename="photo.jpg",
            content_type="image/jpeg",
            size_bytes=0,
        )


def test_chat_completion_dto_defaults():
    req = ChatCompletionRequest(
        model="capability/marketplace-router",
        messages=[ChatMessage(role="user", content="Test prompt")],
    )
    assert req.stream is False
    assert req.options.require_evidence is True
    assert req.options.adapters == ["default"]


def test_execution_request_schema():
    req = ExecutionRequest(
        capability="marketplace.search",
        input_payload={"query": "Sony WH-1000XM5"},
    )
    assert req.capability == "marketplace.search"
    assert req.context == {}


def test_execution_result_status_constraint():
    res = ExecutionResult(
        execution_id="exec_123",
        status="SUCCESS",
        result={"found": True},
        evidence_hash="sha256_mock_hash",
    )
    assert res.status == "SUCCESS"

    with pytest.raises(ValidationError):
        ExecutionResult(
            execution_id="exec_123",
            status="UNKNOWN_STATUS",
            result={},
            evidence_hash="hash",
        )
