"""Authenticated browser dashboard routes and static assets."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from jamp.api.auth import (
    DASHBOARD_SESSION_COOKIE,
    DASHBOARD_SESSION_TTL_SECONDS,
    OrganizationContext,
    authenticate_api_key,
    create_dashboard_session,
    dashboard_cookie_secure,
    require_api_key,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))
STATIC_DIR = WEB_DIR / "static"

router = APIRouter()


@router.get("/dashboard/login", response_class=HTMLResponse)
def dashboard_login_page(request: Request) -> HTMLResponse:
    """Render the login form; no credentials are embedded in the page."""
    return TEMPLATES.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


@router.post("/dashboard/login")
async def dashboard_login(request: Request) -> RedirectResponse:
    """Exchange a submitted API key for a short-lived HttpOnly browser session."""
    try:
        body = (await request.body()).decode("utf-8")
        form = parse_qs(body, keep_blank_values=True)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="invalid login form") from None

    api_key = form.get("api_key", [""])[0].strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key required")

    organization = authenticate_api_key(api_key)
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
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    organization: Annotated[OrganizationContext, Depends(require_api_key)],
) -> HTMLResponse:
    """Render the dashboard only for an authenticated organization."""
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


def register_ui_verify(
    app: FastAPI,
    verify_func: Callable[[dict[str, Any], OrganizationContext], Any],
) -> None:
    """Register a same-origin BFF route using only the server-side API key.

    The Vite /api proxy strips the /api prefix in development, so both paths
    are registered. Browser requests must carry an allowlisted Origin header.
    """
    configured_origins = os.environ.get("JAMP_UI_ALLOWED_ORIGINS")
    if configured_origins is None:
        configured_origins = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_origins = tuple(
        origin.strip() for origin in configured_origins.split(",") if origin.strip()
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["POST"],
        allow_headers=["content-type"],
        max_age=600,
    )

    @app.post("/api/ui_verify", response_model=None)
    def ui_verify(request: Request, payload: dict[str, Any]) -> Any:
        """Verify browser-submitted text without exposing server credentials."""
        if request.headers.get("origin") not in allowed_origins:
            raise HTTPException(status_code=403, detail="origin not allowed")

        api_key = os.environ.get("JAMP_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="UI verification is not configured")

        organization = authenticate_api_key(api_key)
        return verify_func(payload, organization)

    # Vite's existing dev proxy rewrites /api/ui_verify to /ui_verify.
    app.add_api_route(
        "/ui_verify",
        ui_verify,
        methods=["POST"],
        include_in_schema=False,
    )
