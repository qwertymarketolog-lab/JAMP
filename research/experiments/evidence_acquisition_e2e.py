from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import urllib.request
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from jamp.evidence import (
    AtomicObservation,
    EvidenceLedger,
    ExecutionEnvelope,
    FrozenInput,
    RawOutput,
    persist_bundle,
)

REPO_API = "https://api.github.com/repos/qwertymarketolog-lab/JAMP"
OUT = Path("artifacts/evidence_acquisition/e2e-1")
PROBE_ID = "evidence-acquisition-e2e-1"
CHECKER_ID = "http-json-repo-checker"
CHECKER_VERSION = "1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    execution_id = f"e2e-{uuid.uuid4().hex}"
    created = now()
    git_sha = os.environ["GITHUB_SHA"]
    workflow_sha = os.environ.get("GITHUB_WORKFLOW_REF", "")
    target_ref = os.environ.get("GITHUB_REF_NAME", "")
    runtime = f"{platform.python_implementation()} {platform.python_version()}"

    frozen_payload = {
        "method": "GET",
        "endpoint": REPO_API,
        "accept": "application/vnd.github+json",
    }
    frozen = FrozenInput.create(
        execution_id=execution_id,
        probe_id=PROBE_ID,
        model_id="github/public-api",
        canonical_task_input=frozen_payload,
        encoding_version="json-c14n-1",
        timestamp=created,
        contract_version="evidence-acquisition-v0",
        checker_version=CHECKER_VERSION,
    )

    envelope = ExecutionEnvelope(
        contract_version="evidence-acquisition-v0",
        execution_id=execution_id,
        execution_created_at=created,
        execution_started_at=created,
        execution_finished_at=None,
        git_sha=git_sha,
        probe_sha=git_sha,
        workflow_sha=workflow_sha,
        target_ref=target_ref,
        entrypoint="research/experiments/evidence_acquisition_e2e.py",
        pid=os.getpid(),
        process_started_at=created,
        cwd=os.getcwd(),
        runtime_identity=runtime,
        environment_digest=digest(
            {
                "platform": platform.platform(),
                "python": runtime,
                "executable": sys.executable,
            }
        ),
        argv_digest=digest(sys.argv),
        input_digest=frozen.input_digest,
        spec_hash="evidence-acquisition-e2e-1",
        criterion_set_hash="http-json-repo-checker-v1",
        implementation_ref=f"{git_sha}:research/experiments/evidence_acquisition_e2e.py",
        environment_ref="captured-in-envelope",
        status="EXECUTING",
    )

    request = urllib.request.Request(
        REPO_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "JAMP-evidence-acquisition-e2e-1",
        },
    )
    started = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_response = response.read()
            status = response.status
            headers = {
                key.lower(): value
                for key, value in response.headers.items()
                if key.lower() in {"content-type", "etag", "x-github-api-version-selected"}
            }
        transport_state = "COMPLETE"
    except Exception as exc:
        raw_response = json.dumps(
            {"error_type": type(exc).__name__, "error": str(exc)}
        ).encode()
        status = None
        headers = {}
        transport_state = "ERROR"

    finished = now()
    elapsed_ms = (
        datetime.now(timezone.utc) - started
    ).total_seconds() * 1000.0

    raw = RawOutput.create(
        execution_id=execution_id,
        input_digest=frozen.input_digest,
        provider_endpoint=REPO_API,
        http_status=status,
        allowlisted_headers=headers,
        raw_response=raw_response,
        elapsed_transport_ms=elapsed_ms,
        response_timestamp=finished,
        terminal_transport_state=transport_state,
    )

    observation = AtomicObservation(
        execution_id=execution_id,
        frozen_input_digest=frozen.digest,
        raw_output_digest=raw.digest,
        probe_id=PROBE_ID,
        operator_id="jamp-e2e",
        operator_version="1",
        observation={
            "transport_state": transport_state,
            "http_status": status,
            "raw_response_digest": raw.raw_response_digest,
        },
        observation_id=digest(
            {
                "execution_id": execution_id,
                "frozen_input_digest": frozen.digest,
                "raw_output_digest": raw.digest,
                "probe_id": PROBE_ID,
                "operator_id": "jamp-e2e",
                "operator_version": "1",
            }
        ),
    )

    ledger = EvidenceLedger(OUT / "ledger.jsonl")
    entry = ledger.append(
        observation, creation_metadata={"created_at": finished, "probe": PROBE_ID}
    )

    final_status = "FAILED"
    checker_output = {
        "checker_id": CHECKER_ID,
        "checker_version": CHECKER_VERSION,
        "input_digest": raw.raw_response_digest,
        "accepted": False,
        "reason": "transport_or_json_failure",
    }
    try:
        payload = json.loads(raw_response)
        accepted = status == 200 and payload.get("full_name") == "qwertymarketolog-lab/JAMP"
        checker_output = {
            "checker_id": CHECKER_ID,
            "checker_version": CHECKER_VERSION,
            "input_digest": raw.raw_response_digest,
            "accepted": accepted,
            "reason": "repository_identity_match" if accepted else "repository_identity_mismatch",
        }
        final_status = "CHECKED" if accepted else "FAILED"
    except (UnicodeDecodeError, json.JSONDecodeError):
        final_status = "FAILED"

    bundle = persist_bundle(
        OUT / "bundle",
        envelope=ExecutionEnvelope(
            **{**asdict(envelope), "execution_finished_at": finished, "status": final_status}
        ),
        frozen_input=frozen,
        raw_output=raw,
        observation=observation,
        ledger_entry=entry,
    )

    (bundle / "checker.json").write_text(
        json.dumps(checker_output, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    replay = json.loads((bundle / "raw_output.json").read_text(encoding="utf-8"))
    replay_ok = (
        replay["raw_response_digest"] == raw.raw_response_digest
        and json.loads((bundle / "checker.json").read_text(encoding="utf-8"))
        == checker_output
    )
    if not replay_ok:
        raise SystemExit("REPLAY_INTEGRITY_FAILURE")

    summary = {
        "execution_id": execution_id,
        "git_sha": git_sha,
        "probe_id": PROBE_ID,
        "http_status": status,
        "raw_response_digest": raw.raw_response_digest,
        "observation_id": observation.observation_id,
        "checker": checker_output,
        "bundle": str(bundle),
        "replay": "REPLAY_VERIFIED",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
