from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapter import AdapterResult, JampClientAdapter


@dataclass(frozen=True)
class TelegramAdapterResult:
    """Transport-level Telegram response derived from a P25 AdapterResult."""

    chat_id: int
    text: str
    trace_id: str


class TelegramBotAdapter:
    """Transport-only Telegram update adapter built on the P25 client adapter."""

    def __init__(self, client: JampClientAdapter) -> None:
        self.client = client

    def handle_update(self, update: dict[str, Any]) -> TelegramAdapterResult | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None

        text = message.get("text")
        chat = message.get("chat")
        if not isinstance(text, str) or not text.strip():
            return None
        if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
            return None

        result = self.client.execute_payload({"prompt": text})
        return self._render(chat["id"], result)

    @staticmethod
    def _render(chat_id: int, result: AdapterResult) -> TelegramAdapterResult:
        if result.status == "EXECUTE":
            response_text = str(result.output)
        elif result.status == "REFUSE":
            response_text = f"REFUSE: {result.reason}"
        else:
            raise RuntimeError(f"Unknown P25 adapter status: {result.status!r}")

        return TelegramAdapterResult(
            chat_id=chat_id,
            text=response_text,
            trace_id=result.trace_id,
        )
