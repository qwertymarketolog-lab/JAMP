"""Record one bounded live response per source or replay saved raw records."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from evidence_http import capture_http

ROOT = Path(__file__).resolve().parents[2]
MOEX_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/securities/"
    "SBER.json?iss.meta=off"
)
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price?"
    "ids=bitcoin&vs_currencies=usd"
)
DEFAULT_OUTPUT = ROOT / "artifacts/research/experiment_v2/live"
DEFAULT_FIXTURES = ROOT / "tests/research/fixtures/live"
ENDPOINTS = (("MOEX", MOEX_URL), ("CoinGecko", COINGECKO_URL))


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def parse_value(source: str, body: bytes) -> tuple[float | None, str]:
    """Parse one supported numeric field from exact captured JSON bytes."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "INVALID_JSON"
    if not isinstance(payload, dict):
        return None, "INVALID_RESPONSE_SHAPE"

    if source == "CoinGecko":
        coin = payload.get("bitcoin")
        value = _positive_number(coin.get("usd")) if isinstance(coin, dict) else None
        return (value, "PARSED") if value is not None else (None, "USD_PRICE_MISSING_OR_INVALID")

    if source == "MOEX":
        table = payload.get("marketdata")
        if not isinstance(table, dict):
            return None, "MOEX_MARKETDATA_MISSING"
        columns = table.get("columns")
        rows = table.get("data")
        if not isinstance(columns, list) or not isinstance(rows, list):
            return None, "MOEX_MARKETDATA_SCHEMA_INVALID"
        try:
            last_index = columns.index("LAST")
            secid_index = columns.index("SECID")
            boardid_index = columns.index("BOARDID")
        except ValueError:
            return None, "MOEX_REQUIRED_COLUMN_MISSING"

        valid_rows: list[tuple[str, float]] = []
        for row in rows:
            if (
                not isinstance(row, list)
                or len(row) != len(columns)
                or row[secid_index] != "SBER"
            ):
                continue
            raw_last = row[last_index]
            if raw_last is None or raw_last == "":
                continue
            value = _positive_number(raw_last)
            if value is None:
                continue
            board_id = row[boardid_index]
            valid_rows.append((board_id if isinstance(board_id, str) else "", value))

        if not valid_rows:
            return None, "SBER_MARKETDATA_LAST_MISSING_OR_INVALID"

        for board_id, value in valid_rows:
            if board_id == "TQBR":
                return value, "PARSED"

        return valid_rows[0][1], "PARSED"

    return None, "UNSUPPORTED_SOURCE"


def derive_result(source: str, record: dict[str, Any], body: bytes) -> dict[str, Any]:
    """Create derived interpretation separately from immutable RAW evidence."""
    body_hash_ok = hashlib.sha256(body).hexdigest() == record.get("sha256_body")
    if not body_hash_ok:
        value, parse_status, reason = None, "INCONCLUSIVE", "RAW_BODY_HASH_MISMATCH"
    elif record.get("body_complete") is not True:
        value, parse_status, reason = None, "INCONCLUSIVE", "RAW_BODY_INCOMPLETE"
    elif record.get("status_code") != 200:
        value, parse_status, reason = None, "INCONCLUSIVE", "HTTP_STATUS_NOT_200"
    else:
        value, parse_status = parse_value(source, body)
        reason = "NO_CLAIM_CONTEXT" if parse_status == "PARSED" else parse_status

    return {
        "source": source,
        "raw_record_sha256": hashlib.sha256(
            json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "body_sha256_verified": body_hash_ok,
        "parsed_value": value,
        "parse_status": parse_status,
        "jamp_verdict": "INCONCLUSIVE",
        "reason": reason,
    }


def _read_record(source: str, input_dir: Path) -> tuple[dict[str, Any], bytes]:
    record_path = input_dir / f"{source.lower()}.raw.json"
    body_path = input_dir / f"{source.lower()}.body"
    if not record_path.is_file() or not body_path.is_file():
        raise FileNotFoundError(f"missing replay evidence for {source}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    body = body_path.read_bytes()
    if record.get("schema") != "jamp.raw-http-evidence.v1" or record.get("source") != source:
        raise ValueError(f"invalid replay record for {source}")
    encoded = record.get("raw_body_base64")
    if not isinstance(encoded, str) or base64.b64decode(encoded, validate=True) != body:
        raise ValueError(f"record/body byte mismatch for {source}")
    return record, body


def run_live(output_dir: Path, confirm_live: bool) -> dict[str, Any]:
    if not confirm_live:
        raise SystemExit("REFUSE: live requests require --confirm-live")
    results: list[dict[str, Any]] = []
    for source, url in ENDPOINTS:
        record = capture_http(source=source, url=url, output_dir=output_dir)
        body = base64.b64decode(record["raw_body_base64"], validate=True)
        results.append(derive_result(source, record, body))
    return _write_result(output_dir, "LIVE_RECORD", results)


def run_replay(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for source, _ in ENDPOINTS:
        record, body = _read_record(source, input_dir)
        results.append(derive_result(source, record, body))
    return _write_result(output_dir, "REPLAY", results)


def _write_result(output_dir: Path, mode: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    observed = all(
        item["parse_status"] == "PARSED" and item["body_sha256_verified"]
        for item in results
    )
    result = {
        "schema": "jamp.experiment-v2-derived-result.v1",
        "mode": mode,
        "status": "OBSERVED" if observed else "INCONCLUSIVE",
        "source_results": results,
        "interpretation": (
            "Parsed public-source observations only; no claim was supplied or verified."
        ),
    }
    (output_dir / "experiment_v2_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"mode": mode, "status": result["status"]}, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "replay"), required=True)
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args()

    if args.mode == "live":
        run_live(args.output_dir, args.confirm_live)
    else:
        run_replay(args.input_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
