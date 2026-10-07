from __future__ import annotations

from typing import Any

from .telegram import TelegramTransport, TelegramTransportResponse


class TelegramWebhookAdapter:
    """Minimal webhook entry boundary over the P31 Telegram transport."""

    def __init__(self, transport: TelegramTransport) -> None:
        self.transport = transport

    def handle_update(self, update: dict[str, Any]) -> TelegramTransportResponse | None:
        """Forward a Telegram update to the existing transport boundary."""
        if not isinstance(update, dict):
            return None
        return self.transport.handle_update(update)
