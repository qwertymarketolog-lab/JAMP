from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .telegram import TelegramTransport


TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def create_telegram_webhook_router(
    transport: TelegramTransport,
    secret_token: str,
) -> APIRouter:
    """Create the Telegram webhook endpoint with fail-closed auth."""

    router = APIRouter()

    @router.post("/webhook/telegram")
    async def telegram_webhook(request: Request) -> dict[str, str]:
        supplied_token = request.headers.get(TELEGRAM_SECRET_HEADER)
        if not secret_token or not supplied_token or not hmac.compare_digest(
            supplied_token, secret_token
        ):
            raise HTTPException(status_code=403, detail="Forbidden")

        try:
            update: Any = await request.json()
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid JSON") from None

        transport.handle_update(update)
        return {"status": "ok"}

    return router
