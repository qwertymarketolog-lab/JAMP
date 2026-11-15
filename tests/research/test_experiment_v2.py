from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import pathlib
import sys
import urllib.error

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "research"

MOEX_TEST_BYTES = json.dumps(
    {
        "marketdata": {
            "columns": ["SECID", "LAST", "BOARDID"],
            "data": [["SBER", 301.25, "TQBR"]],
        }
    },
    separators=(",", ":"),
).encode("utf-8")
COINGECKO_TEST_BYTES = b'{"bitcoin":{"usd":98765.43}}'


@pytest.fixture(scope="module")
def research_modules():
    sys.path.insert(0, str(SCRIPT_DIR))
    evidence_http = importlib.import_module("evidence_http")
    runner = importlib.import_module("run_experiment_v2")
    return evidence_http, runner


class _FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "Date": "Sun, 15 Nov 2026 17:00:00 GMT"}

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]


def test_parse_test_only_moex_and_coingecko_bytes(research_modules):
    _, runner = research_modules
    assert runner.parse_value("MOEX", MOEX_TEST_BYTES) == (301.25, "PARSED")
    assert runner.parse_value("CoinGecko", COINGECKO_TEST_BYTES) == (98765.43, "PARSED")


@pytest.mark.parametrize(
    ("source", "body", "expected_reason"),
    [
        ("MOEX", b"{", "INVALID_JSON"),
        ("CoinGecko", b'{"bitcoin":{"usd":0}}', "USD_PRICE_MISSING_OR_INVALID"),
        ("MOEX", b'{"marketdata":{"columns":["SECID"],"data":[]}}', "MOEX_REQUIRED_COLUMN_MISSING"),
    ],
)
def test_parser_fails_closed(source, body, expected_reason, research_modules):
    _, runner = research_modules
    value, status = runner.parse_value(source, body)
    assert value is None
    assert status == expected_reason


def test_capture_preserves_exact_raw_bytes_and_sha256(tmp_path, monkeypatch, research_modules):
    evidence_http, _ = research_modules
    raw = b'{"bitcoin":{"usd":123.45}}'
    monkeypatch.setattr(
        evidence_http,
        "_open_request",
        lambda _request, _timeout: _FakeResponse(raw),
    )
    record = evidence_http.capture_http(
        source="CoinGecko",
        url="https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        output_dir=tmp_path,
    )

    assert record["status_code"] == 200
    assert record["raw_body_base64"] == base64.b64encode(raw).decode("ascii")
    assert record["raw_body"] == raw.decode("utf-8")
    assert record["sha256_body"] == hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "coingecko.body").read_bytes() == raw
    persisted = json.loads((tmp_path / "coingecko.raw.json").read_text(encoding="utf-8"))
    assert persisted == record


def test_capture_records_http_error_body(tmp_path, monkeypatch, research_modules):
    evidence_http, _ = research_modules
    body = b'{"error":"rate limited"}'
    error = urllib.error.HTTPError(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        429,
        "Too Many Requests",
        {"Retry-After": "60", "Content-Type": "application/json"},
        io.BytesIO(body),
    )
    monkeypatch.setattr(
        evidence_http,
        "_open_request",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    record = evidence_http.capture_http(
        source="CoinGecko",
        url="https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        output_dir=tmp_path,
    )
    assert record["status_code"] == 429
    assert record["error_type"] == "HTTPError"
    assert record["response_headers"]["retry-after"] == "60"
    assert (tmp_path / "coingecko.body").read_bytes() == body


def test_transport_failure_is_saved_as_raw_evidence(tmp_path, monkeypatch, research_modules):
    evidence_http, _ = research_modules
    monkeypatch.setattr(
        evidence_http,
        "_open_request",
        lambda *_args: (_ for _ in ()).throw(TimeoutError("private detail")),
    )
    record = evidence_http.capture_http(
        source="MOEX",
        url=(
            "https://iss.moex.com/iss/engines/stock/markets/shares/securities/"
            "SBER.json?iss.meta=off"
        ),
        output_dir=tmp_path,
    )
    assert record["status_code"] is None
    assert record["error_type"] == "TimeoutError"
    assert record["error_message"] == "request failed before a complete HTTP response was received"
    assert record["sha256_body"] == hashlib.sha256(b"").hexdigest()
    assert (tmp_path / "moex.body").read_bytes() == b""


def test_derived_result_never_qualifies_without_claim_context(research_modules):
    _, runner = research_modules
    record = {
        "sha256_body": hashlib.sha256(COINGECKO_TEST_BYTES).hexdigest(),
        "body_complete": True,
        "status_code": 200,
    }
    result = runner.derive_result("CoinGecko", record, COINGECKO_TEST_BYTES)
    assert result["parsed_value"] == 98765.43
    assert result["parse_status"] == "PARSED"
    assert result["jamp_verdict"] == "INCONCLUSIVE"
    assert result["reason"] == "NO_CLAIM_CONTEXT"


def test_derived_result_refuses_hash_mismatch(research_modules):
    _, runner = research_modules
    record = {
        "sha256_body": "0" * 64,
        "body_complete": True,
        "status_code": 200,
    }
    result = runner.derive_result("CoinGecko", record, COINGECKO_TEST_BYTES)
    assert result["parsed_value"] is None
    assert result["jamp_verdict"] == "INCONCLUSIVE"
    assert result["reason"] == "RAW_BODY_HASH_MISMATCH"


def test_replay_reads_and_verifies_saved_raw_records(tmp_path, research_modules):
    _, runner = research_modules
    for source, body in (("MOEX", MOEX_TEST_BYTES), ("CoinGecko", COINGECKO_TEST_BYTES)):
        (tmp_path / f"{source.lower()}.body").write_bytes(body)
        record = {
            "schema": "jamp.raw-http-evidence.v1",
            "source": source,
            "status_code": 200,
            "body_complete": True,
            "sha256_body": hashlib.sha256(body).hexdigest(),
            "raw_body_base64": base64.b64encode(body).decode("ascii"),
        }
        (tmp_path / f"{source.lower()}.raw.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
    output = tmp_path / "derived"
    result = runner.run_replay(tmp_path, output)
    assert result["status"] == "OBSERVED"
    assert all(item["jamp_verdict"] == "INCONCLUSIVE" for item in result["source_results"])
    assert (output / "experiment_v2_result.json").is_file()


def test_capture_refuses_unlisted_hosts_before_network(tmp_path, monkeypatch, research_modules):
    evidence_http, _ = research_modules
    monkeypatch.setattr(
        evidence_http,
        "_open_request",
        lambda *_args: pytest.fail("network must not be called for an unlisted host"),
    )
    with pytest.raises(ValueError, match="allowlist"):
        evidence_http.capture_http(
            source="CoinGecko",
            url="https://example.com/api",
            output_dir=tmp_path,
        )


def test_live_runner_requires_explicit_confirmation(tmp_path, research_modules):
    _, runner = research_modules
    with pytest.raises(SystemExit, match="confirm-live"):
        runner.run_live(tmp_path, confirm_live=False)
