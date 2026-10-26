import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from jamp.provider.moex_verify import (
    E4_CONTRADICTED,
    E4_INCONCLUSIVE,
    E4_OUT_OF_SCOPE,
    E4_VERIFIED,
    verify_claim_with_moex,
)


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return MagicMock(__enter__=MagicMock(return_value=response))


def _securities(*rows):
    return {
        "securities": {
            "columns": ["secid", "shortname", "latinname", "emitent_title"],
            "data": list(rows),
        }
    }


def _marketdata(*rows):
    return {
        "marketdata": {
            "columns": ["SECID", "LAST", "BOARDID", "TRADEDATE"],
            "data": list(rows),
        }
    }


@patch("urllib.request.urlopen")
def test_fake_company_ticker_is_out_of_scope_not_contradicted(mock_urlopen):
    mock_urlopen.return_value = _response(_securities())
    status, details = verify_claim_with_moex("FAKETECH", "exists", None)
    assert status == E4_OUT_OF_SCOPE
    assert details["result"] == "OUT_OF_SCOPE"
    assert "cannot verify existence" in details["reason"]
    mock_urlopen.assert_called_once()


@patch("urllib.request.urlopen")
def test_existing_moex_ticker_is_verified(mock_urlopen):
    mock_urlopen.return_value = _response(
        _securities(["SBER", "Сбербанк", "Sberbank", "Сбербанк"])
    )
    status, details = verify_claim_with_moex("SBER", "exists", None)
    assert status == E4_VERIFIED
    assert details["security"]["secid"] == "SBER"


@patch("urllib.request.urlopen")
def test_price_within_five_percent_is_verified(mock_urlopen):
    mock_urlopen.side_effect = [
        _response(_securities(["SBER", "Сбербанк", "Sberbank", "Сбербанк"])),
        _response(_marketdata(["SBER", 292.32, "TQBR", "2026-10-26"])),
    ]
    status, details = verify_claim_with_moex("SBER", "price", 300.0)
    assert status == E4_VERIFIED
    assert details["observed_last"] == 292.32


@patch("urllib.request.urlopen")
def test_price_over_five_percent_difference_is_contradicted(mock_urlopen):
    mock_urlopen.side_effect = [
        _response(_securities(["SBER", "Сбербанк", "Sberbank", "Сбербанк"])),
        _response(_marketdata(["SBER", 292.32, "TQBR", "2026-10-26"])),
    ]
    status, details = verify_claim_with_moex("SBER", "price", 5000.0)
    assert status == E4_CONTRADICTED
    assert details["observed_last"] == 292.32
    assert details["relative_delta"] > 0.05


@patch("urllib.request.urlopen")
def test_moex_source_error_is_inconclusive(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://iss.moex.com/iss/securities.json",
        503,
        "Service Unavailable",
        hdrs=None,
        fp=io.BytesIO(b"temporary outage"),
    )
    status, details = verify_claim_with_moex("SBER", "exists", None)
    assert status == E4_INCONCLUSIVE
    assert details["reason"] == "MOEX_SOURCE_UNAVAILABLE_OR_INVALID"


def test_invalid_price_claim_is_inconclusive_without_network():
    with patch("urllib.request.urlopen") as mock_urlopen:
        status, details = verify_claim_with_moex("SBER", "price", None)
    assert status == E4_INCONCLUSIVE
    assert details["reason"] == "INVALID_CLAIMED_PRICE"
    mock_urlopen.assert_not_called()
