import asyncio
import json

from src.jamp.api.router import _sse_not_implemented
from src.jamp.api.sse import SSEEvent, encode_sse_event, stream_sse_events


def test_encode_sse_event_contains_event_and_json_data():
    payload = {"status": "EXECUTE", "trace_id": "trace-1"}
    encoded = encode_sse_event(SSEEvent("execution.completed", payload))

    assert encoded.startswith("event: execution.completed\n")
    assert f"data: {json.dumps(payload, sort_keys=True)}\n\n" in encoded


def test_encode_sse_event_preserves_event_id():
    encoded = encode_sse_event(SSEEvent("execution.started", {}, event_id="evt-1"))

    assert encoded == "event: execution.started\nid: evt-1\ndata: {}\n\n"


def test_stream_sse_events_forwards_events_in_order():
    async def collect():
        return [item async for item in stream_sse_events(
            [
                SSEEvent("execution.started", {"execution_id": "ex-1"}),
                SSEEvent("execution.completed", {"execution_id": "ex-1", "status": "SUCCESS"}),
            ]
        )]

    chunks = asyncio.run(collect())

    assert [chunk.splitlines()[0] for chunk in chunks] == [
        "event: execution.started",
        "event: execution.completed",
    ]


def test_stream_sse_events_does_not_invent_provenance():
    async def collect():
        return [item async for item in stream_sse_events(
            [SSEEvent("execution.completed", {"status": "SUCCESS"})]
        )]

    chunk = asyncio.run(collect())[0]

    assert "provenance_hash" not in chunk
    assert "created_at" not in chunk
    assert "verified" not in chunk


def test_router_sse_refusal_is_explicit_backend_refusal():
    async def collect():
        return [item async for item in _sse_not_implemented()]

    chunk = asyncio.run(collect())[0]

    assert "event: execution.refused" in chunk
    assert "BACKEND_ORCHESTRATION_UNAVAILABLE" in chunk
    assert "provenance_hash" not in chunk


def test_sse_event_requires_named_event():
    event = SSEEvent("execution.refused", {"reason": "test"})

    assert event.event == "execution.refused"
    assert event.data["reason"] == "test"
