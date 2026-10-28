"""Shared test configuration."""

import pytest

TEST_HMAC_SECRET = "test-hmac-secret-not-for-production"  # noqa: S105


@pytest.fixture(autouse=True)
def _default_hmac_secret(monkeypatch):
    """All tests run with valid HMAC secret; missing-secret tests override."""
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", TEST_HMAC_SECRET)
