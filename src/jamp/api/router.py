from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .sse import SSEEvent, stream_sse_events

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
    event = SSEEvent(
        event="execution.refused",
        data={
            "reason": "BACKEND_ORCHESTRATION_UNAVAILABLE",
            "message": "P32 transport contract is defined; backend orchestration is not configured.",
        },
    )
    async for chunk in stream_sse_events([event]):
        yield chunk


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
