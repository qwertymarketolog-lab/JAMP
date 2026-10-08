from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SSEEvent:
    event: str
    data: dict[str, Any]
    event_id: str | None = None


def encode_sse_event(event: SSEEvent) -> str:
    lines = [f"event: {event.event}"]
    if event.event_id is not None:
        lines.append(f"id: {event.event_id}")
    lines.append(f"data: {json.dumps(event.data, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines) + "\n\n"


async def stream_sse_events(events: Iterable[SSEEvent]) -> AsyncIterator[str]:
    for event in events:
        yield encode_sse_event(event)


__all__ = ["SSEEvent", "encode_sse_event", "stream_sse_events"]
