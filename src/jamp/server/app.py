"""Runnable JAMP server application with the tenant-scoped API and dashboard."""

from __future__ import annotations

import os

from fastapi import FastAPI

from jamp.api.app import DEFAULT_EVIDENCE, create_app
from jamp.db import init_schema
from jamp.server.settings import settings

app: FastAPI = create_app(
    evidence_path=os.environ.get("JAMP_EVIDENCE_PATH", str(DEFAULT_EVIDENCE))
)


@app.on_event("startup")
def _initialize_database_schema() -> None:
    """Apply the idempotent schema before serving database-backed API routes."""
    if settings.database_url:
        init_schema()


@app.get("/health")
async def health() -> dict[str, bool | str]:
    """Report process liveness and whether runtime URLs are configured."""
    return {
        "status": "ok",
        "database_url_set": bool(settings.database_url),
        "redis_url_set": bool(settings.redis_url),
    }
