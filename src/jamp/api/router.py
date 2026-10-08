from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .dto import (
    AttachmentResponse,
    AttachmentUploadRequest,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ExecutionRequest,
    ExecutionResult,
)

router = APIRouter(prefix="/v1", tags=["JAMP API Gateway v0"])


def _not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail="P32 transport contract is defined; backend orchestration is not configured.",
    )


async def _sse_not_implemented() -> AsyncIterator[str]:
    payload = {
        "code": "NOT_IMPLEMENTED",
        "message": "P32 transport contract is defined; backend orchestration is not configured.",
    }
    yield f"event: error\ndata: {json.dumps(payload)}\n\n"


@router.post("/attachments", response_model=AttachmentResponse, status_code=201)
def upload_attachment(request: AttachmentUploadRequest) -> AttachmentResponse:
    _not_implemented()


@router.post("/chat", response_model=ChatCompletionResponse)
def chat(request: ChatCompletionRequest):
    if request.stream:
        return StreamingResponse(_sse_not_implemented(), media_type="text/event-stream")
    _not_implemented()


@router.post("/execute", response_model=ExecutionResult)
def execute(request: ExecutionRequest) -> ExecutionResult:
    _not_implemented()
