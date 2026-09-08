from copy import deepcopy
import hashlib
import json

import pytest

import jamp.p18.controlled_transfer as controlled_transfer_module
from jamp.p18.controlled_transfer import ControlledTransfer


FAMILY_A = "family-a"
FAMILY_B = "family-b"
FAMILY_C = "family-c"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source():
    return {
        "family_id": FAMILY_A,
        "task_id": "task-a",
        "pattern_id": "pattern-a",
        "payload": {"signal": "stable", "weight": 7},
    }


def _authorization(source, *, source_family=FAMILY_A, target_family=FAMILY_B):
    digest = _digest(source)
    return {
        "authorization_id": "AUTH-P18.4-001",
        "source_family": source_family,
        "target_family": target_family,
        "source_digest": digest,
        "provenance": {
            "source_digest": digest,
            "authorization_id": "AUTH-P18.4-001",
        },
        "policy_reason": "controlled ablation baseline",
    }


def _projection(source, authorization, *, shared_payload=False):
    payload = source["payload"] if shared_payload else deepcopy(source["payload"])
    return {
        "family_id": FAMILY_B,
        "task_id": "task-b",
        "pattern_id": "projection-b",
        "payload": payload,
        "provenance": {
            "source_digest": authorization["source_digest"],
            "authorization_id": authorization["authorization_id"],
            "source_ref": None,
        },
    }


class AblationHarness:
    """Test-only degradation adapter; production ControlledTransfer is unchanged."""

    def __init__(
        self,
        gateway,
        *,
        bypass_authorization=False,
        disable_deepcopy_isolation=False,
        skip_digest_validation=False,
    ):
        self.gateway = gateway
        self.bypass_authorization = bypass_authorization
        self.disable_deepcopy_isolation = disable_deepcopy_isolation
        self.skip_digest_validation = skip_digest_validation

    def transfer(self, source_pattern, authorization, projection):
        original_validate_authorization = self.gateway._validate_authorization
        original_validate_projection = self.gateway._validate_projection
        original_deepcopy = controlled_transfer_module.deepcopy

        def relaxed_authorization(source, auth):
            if self.bypass_authorization:
                return None
            if self.skip_digest_validation:
                if source.get("family_id") != auth.source_family:
                    raise PermissionError("source family mismatch")
                if auth.target_family != self.gateway.target_family:
                    raise PermissionError("target family mismatch")
                if auth.source_family == auth.target_family:
                    raise ValueError("source and target families must differ")
                return None
            return original_validate_authorization(source, auth)

        def relaxed_projection(source, auth, candidate):
            if self.disable_deepcopy_isolation:
                if candidate.get("family_id") != self.gateway.target_family:
                    raise ValueError("target family mismatch")
                provenance = candidate.get("provenance")
                if not isinstance(provenance, dict):
                    raise ValueError("projection provenance must be a mapping")
                return None
            return original_validate_projection(source, auth, candidate)

        self.gateway._validate_authorization = relaxed_authorization
        self.gateway._validate_projection = relaxed_projection
        if self.disable_deepcopy_isolation:
            controlled_transfer_module.deepcopy = lambda value: value

        try:
            return self.gateway.transfer(
                source_pattern=source_pattern,
                authorization=authorization,
                projection=projection,
            )
        finally:
            self.gateway._validate_authorization = original_validate_authorization
            self.gateway._validate_projection = original_validate_projection
            controlled_transfer_module.deepcopy = original_deepcopy


def _gateway():
    return ControlledTransfer(FAMILY_B)


def test_p18_4_baseline_authorization_enabled_blocks_foreign_authority():
    source = _source()
    authorization = _authorization(source, source_family=FAMILY_C)
    projection = _projection(source, authorization)

    with pytest.raises(PermissionError):
        _gateway().transfer(
            source_pattern=source,
            authorization=authorization,
            projection=projection,
        )


def test_p18_4_baseline_isolation_enabled_rejects_shared_payload():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization, shared_payload=True)

    with pytest.raises((ValueError, PermissionError)):
        _gateway().transfer(
            source_pattern=source,
            authorization=authorization,
            projection=projection,
        )


def test_p18_4_baseline_digest_enabled_rejects_tampered_source():
    source = _source()
    authorization = _authorization(source)
    tampered = deepcopy(source)
    tampered["payload"]["weight"] = 8
    projection = _projection(tampered, authorization)

    with pytest.raises(PermissionError):
        _gateway().transfer(
            source_pattern=tampered,
            authorization=authorization,
            projection=projection,
        )


def test_p18_4_ablation_authorization_off_accepts_foreign_authority():
    source = _source()
    authorization = _authorization(source, source_family=FAMILY_C)
    projection = _projection(source, authorization)

    transfer = AblationHarness(
        _gateway(), bypass_authorization=True
    ).transfer(source, authorization, projection)

    assert transfer["target_family"] == FAMILY_B
    assert transfer["source_family"] == FAMILY_C


def test_p18_4_ablation_isolation_off_exposes_shared_reference():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization, shared_payload=True)

    transfer = AblationHarness(
        _gateway(), disable_deepcopy_isolation=True
    ).transfer(source, authorization, projection)

    assert transfer["payload"] is source["payload"]
    assert transfer["payload"] is projection["payload"]


def test_p18_4_ablation_digest_off_accepts_tampered_source():
    source = _source()
    authorization = _authorization(source)
    tampered = deepcopy(source)
    tampered["payload"]["weight"] = 8
    projection = _projection(tampered, authorization)

    transfer = AblationHarness(
        _gateway(), skip_digest_validation=True
    ).transfer(tampered, authorization, projection)

    assert transfer["source_digest"] == authorization["source_digest"]
    assert transfer["payload"]["weight"] == 8
