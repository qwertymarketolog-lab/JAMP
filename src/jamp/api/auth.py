"""API key authentication (v0). See docs/architecture/adr-api-key-auth-v0.md."""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from fastapi import Header, HTTPException

_HASH_PREFIX = "v1:"
_ENV_SECRET = "JAMP_API_KEY_HASH_SECRET"
_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True)
class OrganizationContext:
    org_id: int
    org_name: str


def _get_secret() -> bytes:
    value = os.environ.get(_ENV_SECRET)
    if not value:
        raise RuntimeError(f"{_ENV_SECRET} is not set")
    return value.encode("utf-8")


def verify_auth_config() -> None:
    """Fail-fast check; wired to app startup in commit 2."""
    _get_secret()


def hash_api_key(token: str) -> str:
    if not token:
        raise ValueError("token must be non-empty")
    mac = hmac.new(_get_secret(), token.encode("utf-8"), hashlib.sha256)
    return _HASH_PREFIX + mac.hexdigest()


def _lookup_by_hash(api_key_hash: str) -> tuple[int, str, bool] | None:
    """Returns (org_id, org_name, disabled) or None.

    Commit 1: stub. Real DB query via src.jamp.db.connection in commit 3.
    """
    raise NotImplementedError("DB lookup wired in commit 3")


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    token = authorization[len(_BEARER_PREFIX):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    return token


async def require_api_key(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OrganizationContext:
    token = _parse_bearer(authorization)
    api_key_hash = hash_api_key(token)

    try:
        row = _lookup_by_hash(api_key_hash)
    except Exception:  # TODO commit 3: narrow to psycopg2 Operational/InterfaceError
        raise HTTPException(status_code=503, detail="service unavailable") from None

    if row is None:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")

    org_id, org_name, disabled = row
    if disabled:
        raise HTTPException(status_code=403, detail="forbidden")

    return OrganizationContext(org_id=org_id, org_name=org_name)
