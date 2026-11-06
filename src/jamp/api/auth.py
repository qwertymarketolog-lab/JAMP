"""API key authentication and short-lived browser sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request
from psycopg2 import InterfaceError, OperationalError

_HASH_PREFIX = "v1:"
_ENV_SECRET = "JAMP_API_KEY_HASH_SECRET"
_BEARER_PREFIX = "Bearer "
DASHBOARD_SESSION_COOKIE = "jamp_dashboard_session"
DASHBOARD_SESSION_TTL_SECONDS = 3600


@dataclass(frozen=True)
class OrganizationContext:
    org_id: str
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


def _lookup_by_hash(api_key_hash: str) -> tuple[str, str, bool] | None:
    """Return (org_id, org_name, disabled) or None."""
    from jamp.db.connection import get_connection, release_connection

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, disabled FROM organizations WHERE api_key_hash = %s",
                (api_key_hash,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1]), bool(row[2])
    finally:
        if conn is not None:
            release_connection(conn)


def _lookup_by_id(org_id: str) -> tuple[str, str, bool] | None:
    """Return current organization state for a signed dashboard session."""
    from jamp.db.connection import get_connection, release_connection

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, disabled FROM organizations WHERE id = %s",
                (org_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1]), bool(row[2])
    finally:
        if conn is not None:
            release_connection(conn)


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    token = authorization[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    return token


def authenticate_api_key(token: str) -> OrganizationContext:
    """Resolve a bearer token to an enabled organization."""
    if not token:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    api_key_hash = hash_api_key(token)
    try:
        row = _lookup_by_hash(api_key_hash)
    except (OperationalError, InterfaceError):
        raise HTTPException(status_code=503, detail="service unavailable") from None

    if row is None:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    org_id, org_name, disabled = row
    if disabled:
        raise HTTPException(status_code=403, detail="forbidden")
    return OrganizationContext(org_id=org_id, org_name=org_name)


def create_dashboard_session(org_id: str) -> str:
    """Create a signed, one-hour browser session without storing the API key."""
    payload = json.dumps(
        {"org_id": org_id, "exp": int(time.time()) + DASHBOARD_SESSION_TTL_SECONDS},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(_get_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _organization_from_dashboard_session(value: str) -> OrganizationContext:
    try:
        encoded, supplied_signature = value.split(".", maxsplit=1)
        expected_signature = hmac.new(
            _get_secret(),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid session payload")
        org_id = payload.get("org_id")
        expires_at = payload.get("exp")
        if (
            not isinstance(org_id, str)
            or not org_id
            or not isinstance(expires_at, int)
            or expires_at <= int(time.time())
        ):
            raise ValueError("expired or invalid session")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="missing or invalid credentials") from None

    try:
        row = _lookup_by_id(org_id)
    except (OperationalError, InterfaceError):
        raise HTTPException(status_code=503, detail="service unavailable") from None
    if row is None:
        raise HTTPException(status_code=401, detail="missing or invalid credentials")
    current_org_id, org_name, disabled = row
    if disabled:
        raise HTTPException(status_code=403, detail="forbidden")
    return OrganizationContext(org_id=current_org_id, org_name=org_name)


def dashboard_cookie_secure() -> bool:
    """Enable Secure cookies in production; allow loopback HTTP development."""
    explicit = os.environ.get("JAMP_COOKIE_SECURE", "").lower()
    if explicit in {"1", "true", "yes"}:
        return True
    return os.environ.get("JAMP_ENV", "development").lower() in {"production", "prod"}


async def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OrganizationContext:
    """Authenticate a bearer API key or a signed, short-lived dashboard cookie."""
    if authorization is not None:
        return authenticate_api_key(_parse_bearer(authorization))

    session = request.cookies.get(DASHBOARD_SESSION_COOKIE)
    if session:
        return _organization_from_dashboard_session(session)
    raise HTTPException(status_code=401, detail="missing or invalid credentials")
