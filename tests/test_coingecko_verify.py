import json
import urllib.error
from unittest.mock import MagicMock, patch

from jamp.provider import coingecko_verify as cg
from jamp.provider.coingecko_verify import (
    E4_CONTRADICTED,
    E4_INCONCLUSIVE,
    E4_OUT_OF_SCOPE,
    E4_VERIFIED,
    verify_claim_with_coingecko,
)


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return MagicMock(__enter__=MagicMock(return_value=response))


def _http_error(code):
    return urllib.error.HTTPError("https://api.coingecko.com", code, "error", {}, None)


def setup_function():
    with cg._LOCK:
        cg._CACHE.clear()
        cg._REQUEST_TIMES.clear()


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_existence_found_is_verified(mock_urlopen):
    mock_urlopen.return_value = _response({"id": "bitcoin", "name": "Bitcoin", "symbol": "btc"})
    status, details = verify_claim_with_coingecko("bitcoin", "existence", None)
    assert status == E4_VERIFIED
    assert details["name"] == "Bitcoin"
    mock_urlopen.assert_called_once()


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen", side_effect=_http_error(404))
def test_existence_not_found_is_contradicted(mock_urlopen):
    status, details = verify_claim_with_coingecko("fake-token-xyz", "existence", None)
    assert status == E4_CONTRADICTED
    assert details["reason"] == "COIN_NOT_FOUND"


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen", side_effect=_http_error(503))
def test_existence_server_error_is_inconclusive(mock_urlopen):
    status, details = verify_claim_with_coingecko("bitcoin", "existence", None)
    assert status == E4_INCONCLUSIVE
    assert details["http_status"] == 503


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen", side_effect=TimeoutError)
def test_existence_timeout_is_inconclusive(mock_urlopen):
    status, _ = verify_claim_with_coingecko("bitcoin", "existence", None)
    assert status == E4_INCONCLUSIVE


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_price_within_ten_percent_is_verified(mock_urlopen):
    mock_urlopen.return_value = _response({"bitcoin": {"usd": 67200}})
    status, details = verify_claim_with_coingecko("bitcoin", "price", 67000)
    assert status == E4_VERIFIED
    assert details["threshold_pct"] == 10.0


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_price_outside_ten_percent_is_contradicted(mock_urlopen):
    mock_urlopen.return_value = _response({"bitcoin": {"usd": 67200}})
    status, details = verify_claim_with_coingecko("bitcoin", "price", 100000)
    assert status == E4_CONTRADICTED
    assert details["observed_value"] == 67200.0


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_price_missing_coin_is_out_of_scope(mock_urlopen):
    mock_urlopen.return_value = _response({})
    status, details = verify_claim_with_coingecko("not-a-listed-coin", "price", 10)
    assert status == E4_OUT_OF_SCOPE
    assert details["reason"] == "COIN_OR_VALUE_NOT_FOUND"


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen", side_effect=_http_error(429))
def test_rate_limit_is_inconclusive(mock_urlopen):
    status, details = verify_claim_with_coingecko("bitcoin", "price", 67000)
    assert status == E4_INCONCLUSIVE
    assert details["http_status"] == 429


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_cache_hit_does_not_make_second_request(mock_urlopen):
    mock_urlopen.return_value = _response({"bitcoin": {"usd": 67000}})
    first = verify_claim_with_coingecko("bitcoin", "price", 67000)
    second = verify_claim_with_coingecko("bitcoin", "price", 67000)
    assert first[0] == second[0] == E4_VERIFIED
    mock_urlopen.assert_called_once()


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen", side_effect=_http_error(404))
def test_unknown_coin_id_numeric_claim_is_out_of_scope(mock_urlopen):
    status, details = verify_claim_with_coingecko("unknown-id", "market_cap", 1000)
    assert status == E4_OUT_OF_SCOPE
    assert details["reason"] == "COIN_NOT_FOUND"


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_market_cap_uses_twenty_percent_threshold_by_default(mock_urlopen):
    mock_urlopen.return_value = _response({"id": "dogecoin", "market_data": {"market_cap": {"usd": 1000000}}})
    status, details = verify_claim_with_coingecko("dogecoin", "market_cap", 1150000)
    assert status == E4_VERIFIED
    assert details["threshold_pct"] == 20.0


def test_prediction_is_out_of_scope_without_network_call():
    with patch("jamp.provider.coingecko_verify.urllib.request.urlopen") as mock_urlopen:
        status, details = verify_claim_with_coingecko("bitcoin", "prediction", None)
    assert status == E4_OUT_OF_SCOPE
    assert details["reason"] == "PREDICTION_NOT_VERIFIABLE_BY_E4"
    mock_urlopen.assert_not_called()


def test_invalid_coin_id_is_inconclusive():
    status, details = verify_claim_with_coingecko("../bitcoin", "existence", None)
    assert status == E4_INCONCLUSIVE
    assert details["reason"] == "INVALID_COIN_ID"

@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_existence_malformed_response_is_inconclusive(mock_urlopen):
    mock_urlopen.return_value = _response({"name": "Unexpected payload"})
    status, details = verify_claim_with_coingecko("bitcoin", "existence", None)
    assert status == E4_INCONCLUSIVE
    assert details["reason"] == "COINGECKO_RESPONSE_ID_MISMATCH"


@patch("jamp.provider.coingecko_verify.urllib.request.urlopen")
def test_market_cap_missing_from_existing_coin_is_inconclusive(mock_urlopen):
    mock_urlopen.return_value = _response({"id": "dogecoin", "market_data": {}})
    status, details = verify_claim_with_coingecko("dogecoin", "market_cap", 1000000)
    assert status == E4_INCONCLUSIVE
    assert details["reason"] == "COIN_OR_VALUE_NOT_FOUND"

