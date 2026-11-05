"""Minimal JAMP server application (Stage C1 liveness endpoint)."""

from fastapi import FastAPI

from jamp.server.settings import settings

app = FastAPI(title="JAMP Server", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, bool | str]:
    """Report process liveness and whether runtime URLs are configured."""
    return {
        "status": "ok",
        "database_url_set": bool(settings.database_url),
        "redis_url_set": bool(settings.redis_url),
    }
