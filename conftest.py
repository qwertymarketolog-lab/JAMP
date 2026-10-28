"""Project-level pytest fixtures.

Location matters: this file MUST live at the repository root, not in tests/.
pytest's default import-mode=prepend adds the directory containing each
conftest.py to sys.path. A conftest in tests/ would put 'tests' ahead of the
repo root, shadowing the real top-level 'research/' package with
'tests/research/' and breaking collection of research.exp18/exp19/exp21.
"""

import pytest

TEST_HMAC_SECRET = "test-hmac-secret-not-for-production"  # noqa: S105


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_auth: bypass disabled; test exercises the real API-key dependency",
    )


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee JAMP_API_KEY_HASH_SECRET exists for every test."""
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", TEST_HMAC_SECRET)


@pytest.fixture(autouse=True)
def _bypass_api_key_auth(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Default: inject a stub OrganizationContext so legacy tests don't need
    Authorization headers. Tests marked @pytest.mark.real_auth opt out and
    exercise the real require_api_key dependency.
    """
    if request.node.get_closest_marker("real_auth"):
        yield
        return

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from jamp.api.auth import OrganizationContext, require_api_key

    def _apply_override(app: object) -> None:
        if isinstance(app, FastAPI):
            app.dependency_overrides[require_api_key] = lambda: OrganizationContext(0, "test")

    original_init = TestClient.__init__

    def _patched_init(self, app, *args, **kwargs):
        _apply_override(app)
        original_init(self, app, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", _patched_init)
    yield
