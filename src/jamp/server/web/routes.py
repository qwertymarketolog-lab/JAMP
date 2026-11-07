"""GitHub OAuth dashboard routes and static assets."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from jamp.api.auth import (
    DASHBOARD_SESSION_COOKIE,
    DASHBOARD_SESSION_TTL_SECONDS,
    OrganizationContext,
    authenticate_organization_id,
    create_dashboard_session,
    dashboard_cookie_secure,
    require_api_key,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))
STATIC_DIR = WEB_DIR / "static"
OAUTH_STATE_COOKIE = "jamp_github_oauth_state"
OAUTH_STATE_TTL_SECONDS = 600

router = APIRouter()


def _oauth_config() -> dict[str, str]:
    names = {
        "client_id": "JAMP_GITHUB_OAUTH_CLIENT_ID",
        "client_secret": "JAMP_GITHUB_OAUTH_CLIENT_SECRET",
        "redirect_uri": "JAMP_GITHUB_OAUTH_REDIRECT_URI",
        "allowed_user_id": "JAMP_GITHUB_ALLOWED_USER_ID",
        "organization_id": "JAMP_GITHUB_OAUTH_ORG_ID",
    }
    config = {key: os.environ.get(name, "").strip() for key, name in names.items()}
    if any(not value for value in config.values()):
        raise HTTPException(status_code=503, detail="GitHub login is not configured")
    if not config["allowed_user_id"].isdigit():
        raise HTTPException(status_code=503, detail="GitHub login is not configured")
    if not config["redirect_uri"].startswith(("https://", "http://localhost")):
        raise HTTPException(status_code=503, detail="GitHub login is not configured")
    return config


def _github_json_request(
    url: str,
    *,
    data: bytes | None = None,
    access_token: str | None = None,
) -> dict[str, object]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "JAMP-Dashboard",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if access_token is not None:
        headers["Authorization"] = f"Bearer {access_token}"
    request = UrlRequest(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="GitHub authentication failed") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="GitHub authentication failed")
    return payload


def _exchange_github_code(code: str, config: dict[str, str]) -> str:
    body = urlencode(
        {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": config["redirect_uri"],
        }
    ).encode("utf-8")
    payload = _github_json_request("https://github.com/login/oauth/access_token", data=body)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=401, detail="GitHub authentication failed")
    return token


def _fetch_github_user(access_token: str) -> dict[str, object]:
    return _github_json_request("https://api.github.com/user", access_token=access_token)


@router.get("/dashboard/login", response_class=HTMLResponse)
def dashboard_login_page(request: Request) -> HTMLResponse:
    """Render the GitHub-only browser login page."""
    return TEMPLATES.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


@router.get("/dashboard/oauth/start")
def dashboard_oauth_start() -> RedirectResponse:
    """Start OAuth with a one-time CSRF state value held in an HttpOnly cookie."""
    config = _oauth_config()
    state = secrets.token_urlsafe(32)
    query = urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": "read:user",
            "state": state,
        }
    )
    response = RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?{query}",
        status_code=303,
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=dashboard_cookie_secure(),
        samesite="lax",
        path="/dashboard/oauth",
    )
    return response


@router.get("/dashboard/oauth/callback")
def dashboard_oauth_callback(request: Request) -> RedirectResponse:
    """Validate GitHub identity and exchange it for a tenant-scoped dashboard session."""
    config = _oauth_config()
    supplied_state = request.query_params.get("state", "")
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE, "")
    if (
        not supplied_state
        or not cookie_state
        or not secrets.compare_digest(supplied_state, cookie_state)
    ):
        raise HTTPException(status_code=400, detail="invalid OAuth state")

    if request.query_params.get("error"):
        raise HTTPException(status_code=401, detail="GitHub authorization was not granted")
    code = request.query_params.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="missing OAuth code")

    access_token = _exchange_github_code(code, config)
    github_user = _fetch_github_user(access_token)
    github_user_id = github_user.get("id")
    if (
        not isinstance(github_user_id, int)
        or isinstance(github_user_id, bool)
        or github_user_id != int(config["allowed_user_id"])
    ):
        raise HTTPException(status_code=403, detail="GitHub account is not authorized")

    organization = authenticate_organization_id(config["organization_id"])
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=DASHBOARD_SESSION_COOKIE,
        value=create_dashboard_session(organization.org_id),
        max_age=DASHBOARD_SESSION_TTL_SECONDS,
        httponly=True,
        secure=dashboard_cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        path="/dashboard/oauth",
        httponly=True,
        secure=dashboard_cookie_secure(),
        samesite="lax",
    )
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    organization: Annotated[OrganizationContext, Depends(require_api_key)],
) -> HTMLResponse:
    """Render the dashboard only for an authenticated tenant session."""
    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"organization_name": organization.org_name},
    )


@router.post("/dashboard/logout")
def dashboard_logout() -> RedirectResponse:
    """Clear the browser session cookie."""
    response = RedirectResponse(url="/dashboard/login", status_code=303)
    response.delete_cookie(
        key=DASHBOARD_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=dashboard_cookie_secure(),
        samesite="strict",
    )
    return response


def register_dashboard(app: FastAPI) -> None:
    """Mount dashboard routes and their non-secret static assets."""
    app.include_router(router)
    app.mount(
        "/dashboard-static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="dashboard-static",
    )
