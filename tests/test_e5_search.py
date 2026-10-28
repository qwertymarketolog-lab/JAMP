import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from jamp.provider.e5_search import (
    E5_CONTRADICTED,
    E5_INCONCLUSIVE,
    E5_OUT_OF_SCOPE,
    E5_VERIFIED,
    verify_with_search,
)


def _response(payload, status=200):
    response = MagicMock()
    response.status = status
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return MagicMock(__enter__=MagicMock(return_value=response))


def _result(
    domain="reuters.com",
    content="SBER dividends increased due to dividend payments",
    url=None,
):
    return {
        "title": "SBER dividend report",
        "url": url or f"https://{domain}/markets/sber-dividends",
        "content": content,
        "score": 0.9,
        "published_date": "2026-10-20",
    }


def _claim(claim_text="SBER increased due to dividends", claim_type="causal", ticker="SBER"):
    return claim_text, claim_type, ticker


@patch("urllib.request.urlopen")
def test_verified_multi_source(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result("reuters.com"),
        _result("bloomberg.com", "SBER dividends increased due to dividend payments"),
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_VERIFIED
    assert evidence["verdict_basis"] == "multi_source_confirmed"
    assert evidence["unique_domains_count"] == 2


@patch("urllib.request.urlopen")
def test_verified_single_source(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [_result()]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_VERIFIED
    assert evidence["verdict_basis"] == "single_source"


@patch("urllib.request.urlopen")
def test_contradicted(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result(content="SBER dividends did not cause the increase in share price")
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_CONTRADICTED
    assert evidence["conflicting"] is False


@patch("urllib.request.urlopen")
def test_conflicting_sources(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result("reuters.com"),
        _result("bloomberg.com", "SBER dividends did not cause the increase in share price"),
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_INCONCLUSIVE
    assert evidence["verdict_basis"] == "conflicting_sources"
    assert evidence["conflicting"] is True


@patch("urllib.request.urlopen")
def test_no_authoritative_source(mock_urlopen):
    mock_urlopen.return_value = _response({"results": []})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_OUT_OF_SCOPE
    assert evidence["reason"] == "no_authoritative_source"


@patch("urllib.request.urlopen")
def test_non_whitelisted_filtered(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result("twitter.com", "SBER dividends increased due to dividend payments")
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_OUT_OF_SCOPE
    assert evidence["results"] == []
    assert evidence["results_count"] == 1


@patch("urllib.request.urlopen")
def test_api_auth_error(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://api.tavily.com/search", 401, "Unauthorized", hdrs=None, fp=io.BytesIO(b"")
    )
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_INCONCLUSIVE
    assert evidence["reason"] == "api_auth_error"
    assert evidence["http_status"] == 401


@patch("urllib.request.urlopen")
def test_rate_limit(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://api.tavily.com/search", 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b"")
    )
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_INCONCLUSIVE
    assert evidence["reason"] == "rate_limit"


@patch("urllib.request.urlopen")
def test_timeout(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError()
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_INCONCLUSIVE
    assert evidence["reason"] == "timeout"


@patch("urllib.request.urlopen")
def test_causal_with_marker(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result(content="SBER shares rose due to dividend payments")
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_VERIFIED


@patch("urllib.request.urlopen")
def test_causal_without_marker(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result(content="SBER dividend payments were announced yesterday")
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_OUT_OF_SCOPE
    assert evidence["reason"] == "facts_without_causality"


@patch("urllib.request.urlopen")
def test_prediction_future_out_of_scope(mock_urlopen):
    status, evidence = verify_with_search(
        "SBER will rise", "prediction", "SBER", api_key="test-key"
    )
    assert status == E5_OUT_OF_SCOPE
    assert evidence["reason"] == "future_prediction_not_searchable"
    mock_urlopen.assert_not_called()


@patch("urllib.request.urlopen")
def test_api_key_missing(mock_urlopen):
    with patch.dict("os.environ", {}, clear=True):
        status, evidence = verify_with_search(*_claim(), api_key=None)
    assert status == E5_INCONCLUSIVE
    assert evidence["reason"] == "api_key_missing"
    mock_urlopen.assert_not_called()


@patch("urllib.request.urlopen")
def test_same_domain_not_independent(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [
        _result(url="https://reuters.com/a"),
        _result(url="https://uk.reuters.com/b"),
    ]})
    status, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert status == E5_VERIFIED
    assert evidence["unique_domains_count"] == 1
    assert evidence["verdict_basis"] == "single_source"


@patch("urllib.request.urlopen")
def test_evidence_has_query_and_version(mock_urlopen):
    mock_urlopen.return_value = _response({"results": [_result()]})
    _, evidence = verify_with_search(*_claim(), api_key="test-key")
    assert evidence["query"]
    assert evidence["whitelist_version"] == "e5-authoritative-domains-v0"

