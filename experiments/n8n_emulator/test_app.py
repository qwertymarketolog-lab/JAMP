"""Test-only app factory for the n8n emulator.

Wraps jamp.api.app.create_app with dependency_overrides[require_api_key]
so the emulator exercises the real HTTP flow without an API key.

Auth is covered by tests/test_api_key_auth*; do not use this factory
outside the emulator.

Pre-#463 main: jamp.api.auth is absent, try/except returns plain app.
After #463 merges, this guard becomes dead code — cleanup: issue #466.
"""

from jamp.api.app import create_app


def create_app_with_bypass():
    app = create_app()
    try:
        from jamp.api.auth import OrganizationContext, require_api_key
    except ImportError:
        return app

    app.dependency_overrides[require_api_key] = lambda: OrganizationContext("n8n-test", "n8n-test")
    return app
