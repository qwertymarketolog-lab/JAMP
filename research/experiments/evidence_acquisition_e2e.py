from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import urllib.request
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from jamp.evidence import (
    AtomicObservation,
    EvidenceLedger,
    ExecutionEnvelope,
    FrozenInput,
    RawOutput,
    persist_bundle,
)
from jamp.evidence.checker import (
    CHECKER_CONTRACT,
    CHECKER_ID,
    CHECKER_VERSION,
    check,
    checker_digest,
    replay_check,
)

REPO_API = "https://api.github.com/repos/qwertymarketolog-lab/JAMP"
OUT = Path("artifacts/evidence_acquisition/e2e-1")
PROBE_ID = "evidence-acquisition-e2e-1"
FROZEN_SPEC_HASH = "9ea3ea4e57545b55ee29bb5709fe834b3363c6a9"
FROZEN_CRITERION_SET_HASH = checker_digest()
CONCRETE_ENVIRONMENT_RECORD = "environment-record-v1"
WORKFLOW_PATH = ".github/workflows/test.yml"
CHECKER_CONTRACT_MARKERS = (
    "checker_digest",
    "input_schema_version",
    "canonicalization_rules",
    "acceptance_predicate",
    "rejection_predicate",
    "inconclusive_predicate",
    "self_test_fixtures",
)


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def digest(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def dependency_set_digest() -> str:
    records = sorted(
        (dist.metadata["Name"], dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    )
    return digest(records)


def capture_environment() -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "executable": sys.executable,
        "dependency_set_digest": dependency_set_digest(),
        "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
    }


def verify_manifest(bundle: Path) -> dict[str, object]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    stored = manifest.pop("bundle_digest", None)
    if stored != digest(manifest):
        raise ValueError("manifest bundle_digest mismatch")
    return manifest


def verify_referenced_digests(bundle: Path, manifest: dict[str, object]) -> None:
    raw = json.loads((bundle / "raw_output.json").read_text(encoding="utf-8"))
    response = (bundle / "raw_response.bin").read_bytes()
    if raw["raw_response_digest"] != manifest["raw_response_digest"]:
        raise ValueError("raw_response_digest mismatch")
    if hashlib.sha256(response).hexdigest() != manifest["raw_response_digest"]:
        raise ValueError("raw response bytes mismatch")
    checker = json.loads((bundle / "checker.json").read_text(encoding="utf-8"))
    if digest(checker) != manifest["checker_output_digest"]:
        raise ValueError("checker_output_digest mismatch")
    contract = json.loads((bundle / "checker_contract.json").read_text(encoding="utf-8"))
    if digest(contract) != manifest["checker_digest"]:
        raise ValueError("checker_digest mismatch")


def verify_atomic_observation(bundle: Path, manifest: dict[str, object]) -> None:
    observation = json.loads((bundle / "atomic_observation.json").read_text(encoding="utf-8"))
    if observation["observation_id"] not in manifest["atomic_observation_ids"]:
        raise ValueError("atomic_observation_id mismatch")
    preimage = {
        "execution_id": observation["execution_id"],
        "frozen_input_digest": observation["frozen_input_digest"],
        "raw_output_digest": observation["raw_output_digest"],
        "probe_id": observation["probe_id"],
        "operator_id": observation["operator_id"],
        "operator_version": observation["operator_version"],
    }
    if digest(preimage) != observation["observation_id"]:
        raise ValueError("atomic observation identity mismatch")


def load_declared_checker(bundle: Path) -> dict[str, object]:
    contract = json.loads((bundle / "checker_contract.json").read_text(encoding="utf-8"))
    if contract["checker_id"] != CHECKER_ID:
        raise ValueError("unknown checker")
    if contract["checker_version"] != CHECKER_VERSION:
        raise RuntimeError("version mismatch")
    return contract


def regenerate_checker_output(bundle: Path, manifest: dict[str, object]) -> dict[str, object]:
    checker_input = json.loads((bundle / "checker_input.json").read_text(encoding="utf-8"))
    result = replay_check(
        raw_response=bytes.fromhex(checker_input["raw_response"]),
        raw_response_digest=checker_input["raw_response_digest"],
        http_status=checker_input["http_status"],
        declared_checker_version=manifest["checker_version"],
    )
    if result.get("status") == "REPLAY_INCONCLUSIVE":
        raise RuntimeError(result["reason"])
    return result


def replay_bundle(bundle: Path) -> str:
    try:
        manifest = verify_manifest(bundle)
        verify_referenced_digests(bundle, manifest)
        verify_atomic_observation(bundle, manifest)
        load_declared_checker(bundle)
        regenerated = regenerate_checker_output(bundle, manifest)
        stored = json.loads((bundle / "checker.json").read_text(encoding="utf-8"))
        if regenerated != stored:
            raise ValueError("regenerated checker output mismatch")
        return "REPLAY_VERIFIED"
    except RuntimeError as exc:
        if "version mismatch" in str(exc).lower():
            return "REPLAY_INCONCLUSIVE"
        raise
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return "REPLAY_INCONCLUSIVE"


def main() -> None:
    execution_id = f"e2e-{uuid.uuid4().hex}"
    created = now()
    git_sha = os.environ["GITHUB_SHA"]
    workflow_sha = os.environ["GITHUB_WORKFLOW_SHA"]
    target_ref = os.environ.get("GITHUB_REF_NAME", "")
    if not workflow_sha:
        raise SystemExit("INCONCLUSIVE: missing workflow definition identity")
    runtime = f"{platform.python_implementation()} {platform.python_version()}"
    environment_record = capture_environment()
    environment_digest = digest(environment_record)
    environment_ref = f"{CONCRETE_ENVIRONMENT_RECORD}:{environment_digest}"

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
        environment_digest=environment_digest,
        argv_digest=digest(sys.argv),
        input_digest=frozen.input_digest,
        spec_hash=FROZEN_SPEC_HASH,
        criterion_set_hash=FROZEN_CRITERION_SET_HASH,
        implementation_ref=f"{git_sha}:research/experiments/evidence_acquisition_e2e.py:{PROBE_ID}",
        environment_ref=environment_ref,
        status="EXECUTING",
    )

    request = urllib.request.Request(
        REPO_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "JAMP-evidence-acquisition-e2e-1",
        },
    )
    started = datetime.now(UTC)
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
        datetime.now(UTC) - started
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

    checker_result = check(
        raw_response=raw_response,
        raw_response_digest=raw.raw_response_digest,
        http_status=status,
    )
    checker_output = checker_result.as_dict()
    final_status = checker_output["status"]

    bundle = persist_bundle(
        OUT / "bundle",
        envelope=ExecutionEnvelope(
            **{
                **asdict(envelope),
                "execution_finished_at": finished,
                "status": final_status,
            }
        ),
        frozen_input=frozen,
        raw_output=raw,
        observation=observation,
        ledger_entry=entry,
        checker_contract=CHECKER_CONTRACT,
        checker_output=checker_output,
        created_at=finished,
    )

    replay_status = replay_bundle(bundle)
    if replay_status != "REPLAY_VERIFIED":
        print(json.dumps({"replay": replay_status}))
        raise SystemExit(replay_status)

    summary = {
        "execution_id": execution_id,
        "git_sha": git_sha,
        "workflow_sha": workflow_sha,
        "probe_id": PROBE_ID,
        "http_status": status,
        "raw_response_digest": raw.raw_response_digest,
        "observation_id": observation.observation_id,
        "checker": checker_output,
        "checker_digest": checker_digest(),
        "bundle": str(bundle),
        "replay": replay_status,
        "state": "REPLAY_VERIFIED",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
