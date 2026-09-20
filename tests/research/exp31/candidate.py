"""Executable EXP-31 / N1-N3 research candidate.

Research-only.  This module is intentionally independent of src/jamp.
It implements the frozen gate semantics needed by the external S1 harness.
"""

from __future__ import annotations

from typing import Any


VERIFIER_VERSION = "exp31-contract-v0"
REQUIRED_NODES = {
    "source_ref",
    "raw_object",
    "observation_id",
    "atomic_payload",
}
REQUIRED_EDGES = {
    ("source_ref", "raw_object"),
    ("raw_object", "observation_id"),
    ("observation_id", "atomic_payload"),
}


def _halt(stage: str, code: str) -> dict[str, str]:
    return {"stage": stage, "diagnostic_code": code}


def exp31_verify(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the EXP-31 provenance verdict without semantic interpretation."""

    required = {
        "raw_observation_ref",
        "raw_observation_hash",
        "atomic_payload",
        "provenance_graph",
    }
    if not required.issubset(payload):
        return {
            "status": "INCONCLUSIVE",
            "diagnostic_code": "META_INCOMPLETE",
            "scope_metrics": {},
            "verifier_version": VERIFIER_VERSION,
        }

    raw_ref = payload["raw_observation_ref"]
    raw_hash = payload["raw_observation_hash"]
    atoms = payload["atomic_payload"]
    graph = payload["provenance_graph"]

    if not isinstance(raw_ref, str) or not isinstance(raw_hash, str):
        return {
            "status": "INVALID",
            "diagnostic_code": "META_INCOMPLETE",
            "scope_metrics": {},
            "verifier_version": VERIFIER_VERSION,
        }

    if not isinstance(atoms, list) or not isinstance(graph, dict):
        return {
            "status": "INVALID",
            "diagnostic_code": "META_INCOMPLETE",
            "scope_metrics": {},
            "verifier_version": VERIFIER_VERSION,
        }

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {
            "status": "INVALID",
            "diagnostic_code": "META_INCOMPLETE",
            "scope_metrics": {},
            "verifier_version": VERIFIER_VERSION,
        }

    if set(nodes) != REQUIRED_NODES:
        return {
            "status": "INVALID",
            "diagnostic_code": "ORPHAN_REF",
            "scope_metrics": {"atomic_count": len(atoms)},
            "verifier_version": VERIFIER_VERSION,
        }

    if not REQUIRED_EDGES.issubset({tuple(edge) for edge in edges}):
        return {
            "status": "INVALID",
            "diagnostic_code": "BROKEN_LINK",
            "scope_metrics": {"atomic_count": len(atoms)},
            "verifier_version": VERIFIER_VERSION,
        }

    if not atoms:
        return {
            "status": "INVALID",
            "diagnostic_code": "CARDINALITY_VIOLATION",
            "scope_metrics": {"atomic_count": 0},
            "verifier_version": VERIFIER_VERSION,
        }

    observation_ids: list[Any] = []
    source_refs: list[Any] = []

    for atom in atoms:
        if not isinstance(atom, dict):
            return {
                "status": "INVALID",
                "diagnostic_code": "META_INCOMPLETE",
                "scope_metrics": {"atomic_count": len(atoms)},
                "verifier_version": VERIFIER_VERSION,
            }

        observation_id = atom.get("observation_id")
        source_ref = atom.get("source_ref")
        metadata = atom.get("metadata")

        if type(observation_id) is not str or type(source_ref) is not str:
            return {
                "status": "INVALID",
                "diagnostic_code": "STRICT_IDENTITY_FAIL",
                "scope_metrics": {"atomic_count": len(atoms)},
                "verifier_version": VERIFIER_VERSION,
            }

        # Schema-role check is deliberately syntactic and does not normalize
        # Unicode or otherwise transform identifiers.
        if not observation_id.startswith("obs-") or not source_ref.startswith("ref-"):
            return {
                "status": "INVALID",
                "diagnostic_code": "SCHEMA_ROLE_MISMATCH",
                "scope_metrics": {"atomic_count": len(atoms)},
                "verifier_version": VERIFIER_VERSION,
            }

        if not isinstance(metadata, dict) or "precision_dps" not in metadata:
            return {
                "status": "INCONCLUSIVE",
                "diagnostic_code": "META_INCOMPLETE",
                "scope_metrics": {"atomic_count": len(atoms)},
                "verifier_version": VERIFIER_VERSION,
            }

        observation_ids.append(observation_id)
        source_refs.append(source_ref)

        if "verdict" in atom or "claim" in atom or "interpretation" in atom:
            return {
                "status": "INVALID",
                "diagnostic_code": "SEMANTIC_OVERREACH",
                "scope_metrics": {"atomic_count": len(atoms)},
                "verifier_version": VERIFIER_VERSION,
            }

    return {
        "status": "VALID",
        "diagnostic_code": "PROV_OK",
        "scope_metrics": {
            "atomic_count": len(atoms),
            "source_ref_count": len(set(source_refs)),
            "observation_id_count": len(set(observation_ids)),
        },
        "verifier_version": VERIFIER_VERSION,
    }


def n1_gate(
    exp31: dict[str, Any],
    *,
    target_scope: str = "atomic_payload",
    max_cardinality: int | None = None,
) -> dict[str, Any]:
    """N1: scope/cardinality gate; EXP-31 uncertainty or failure halts."""

    if exp31.get("status") != "VALID":
        return {
            "status": "FAIL",
            "diagnostic_code": exp31.get("diagnostic_code", "EXP31_NOT_VALID"),
        }

    count = int(exp31.get("scope_metrics", {}).get("atomic_count", 0))
    if count < 1 or (max_cardinality is not None and count > max_cardinality):
        return {
            "status": "FAIL",
            "diagnostic_code": "CARDINALITY_VIOLATION",
        }

    if target_scope != "atomic_payload":
        return {
            "status": "FAIL",
            "diagnostic_code": "SCOPE_VIOLATION",
        }

    return {
        "status": "PASS",
        "diagnostic_code": "N1_OK",
        "target_scope": target_scope,
        "cardinality": count,
    }


def n2_gate(payload: dict[str, Any], n1: dict[str, Any]) -> dict[str, Any]:
    """N2: deterministic uniqueness/homogeneity/criteria gate."""

    if n1.get("status") != "PASS":
        return {"status": "FAIL", "diagnostic_code": "N1_NOT_PASS"}

    atoms = payload["atomic_payload"]
    if not isinstance(atoms, list) or not atoms:
        return {"status": "FAIL", "diagnostic_code": "CARDINALITY_VIOLATION"}

    types = {(type(a.get("source_ref")), type(a.get("observation_id"))) for a in atoms}
    if len(types) != 1:
        return {"status": "FAIL", "diagnostic_code": "HOMOGENEITY_VIOLATION"}

    if len({a["source_ref"] for a in atoms}) != len(atoms):
        return {"status": "FAIL", "diagnostic_code": "UNIQUENESS_VIOLATION"}

    if len({a["observation_id"] for a in atoms}) != len(atoms):
        return {"status": "FAIL", "diagnostic_code": "DUPLICATE_OBSERVATION_ID"}

    return {
        "status": "PASS",
        "diagnostic_code": "N2_OK",
        "aggregation": "identity",
        "failure_policy": "FAIL_CLOSED",
    }


def n3_gate(
    exp31: dict[str, Any],
    n1: dict[str, Any],
    n2: dict[str, Any],
) -> dict[str, Any]:
    """N3: strict cascade; never repairs or reinterprets upstream output."""

    halt_reasons: list[dict[str, str]] = []

    if exp31.get("status") != "VALID":
        halt_reasons.append(_halt("EXP31", exp31.get("diagnostic_code", "EXP31_NOT_VALID")))
    elif n1.get("status") != "PASS":
        halt_reasons.append(_halt("N1", n1.get("diagnostic_code", "N1_NOT_PASS")))
    elif n2.get("status") != "PASS":
        halt_reasons.append(_halt("N2", n2.get("diagnostic_code", "N2_NOT_PASS")))

    if halt_reasons:
        return {
            "terminal_status": "TERMINAL_HALT",
            "halt_reasons": halt_reasons,
        }

    return {
        "terminal_status": "TERMINAL_PASS",
        "halt_reasons": [],
    }


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    """Executable candidate entrypoint consumed by the external harness."""

    exp31 = exp31_verify(payload)
    n1 = n1_gate(exp31)
    n2 = n2_gate(payload, n1)
    n3 = n3_gate(exp31, n1, n2)

    return {
        "exp31": exp31,
        "n1": n1,
        "n2": n2,
        "n3": n3,
    }
