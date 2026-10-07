from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TelegramTransportResponse(BaseModel):
    chat_id: int
    text: str
    trace_id: str


class TelegramTransport:
    """Minimal transport boundary for Telegram updates."""

    def __init__(self, client_adapter: Any) -> None:
        self.client_adapter = client_adapter

    def handle_update(
        self, update: dict[str, Any]
    ) -> TelegramTransportResponse | None:
        if not isinstance(update, dict):
            return None

        message = update.get("message")
        if not isinstance(message, dict):
            return None

        chat = message.get("chat")
        if not isinstance(chat, dict):
            return None

        chat_id = chat.get("id")
        text = message.get("text")
        if (
            not isinstance(chat_id, int)
            or not isinstance(text, str)
            or not text.strip()
        ):
            return None

        result = self.client_adapter.execute_payload({"prompt": text})
        if getattr(result, "status", None) == "EXECUTE" or getattr(
            result, "decision", None
        ) == "EXECUTE":
            response_text = getattr(result, "output", "") or ""
        else:
            response_text = f"REFUSE: {getattr(result, 'reason', 'unknown_refusal')}"

        return TelegramTransportResponse(
            chat_id=chat_id,
            text=response_text,
            trace_id=getattr(result, "trace_id", "unknown_trace"),
        )
