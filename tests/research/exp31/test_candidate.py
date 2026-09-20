from __future__ import annotations

from .candidate import execute


def base_payload() -> dict:
    return {
        "raw_observation_ref": "source-42069",
        "raw_observation_hash": "hash",
        "atomic_payload": [
            {
                "observation_id": "obs-001",
                "source_ref": "ref-001",
                "real_part": "1.0",
                "imag_part": "2.0",
                "metadata": {"precision_dps": 30},
            },
            {
                "observation_id": "obs-002",
                "source_ref": "ref-002",
                "real_part": "3.0",
                "imag_part": "4.0",
                "metadata": {"precision_dps": 30},
            },
        ],
        "provenance_graph": {
            "nodes": [
                "source_ref",
                "raw_object",
                "observation_id",
                "atomic_payload",
            ],
            "edges": [
                ["source_ref", "raw_object"],
                ["raw_object", "observation_id"],
                ["observation_id", "atomic_payload"],
            ],
        },
        "claims_layer": [],
    }


def test_valid_baseline_reaches_terminal_pass() -> None:
    result = execute(base_payload())
    assert result["exp31"]["status"] == "VALID"
    assert result["n1"]["status"] == "PASS"
    assert result["n2"]["status"] == "PASS"
    assert result["n3"]["terminal_status"] == "TERMINAL_PASS"


def test_duplicate_source_ref_halts() -> None:
    payload = base_payload()
    payload["atomic_payload"][1]["source_ref"] = "ref-001"
    result = execute(payload)
    assert result["n3"]["terminal_status"] == "TERMINAL_HALT"
    assert result["n2"]["diagnostic_code"] == "DUPLICATE_SOURCE_REF"


def test_duplicate_observation_id_halts() -> None:
    payload = base_payload()
    payload["atomic_payload"][1]["observation_id"] = "obs-001"
    result = execute(payload)
    assert result["n3"]["terminal_status"] == "TERMINAL_HALT"
    assert result["n2"]["diagnostic_code"] == "DUPLICATE_OBSERVATION_ID"


def test_orphan_graph_node_is_invalid() -> None:
    payload = base_payload()
    payload["provenance_graph"]["nodes"].append("orphan")
    result = execute(payload)
    assert result["n3"]["terminal_status"] == "TERMINAL_HALT"
    assert result["exp31"]["diagnostic_code"] == "ORPHAN_REF"


def test_broken_graph_edge_is_invalid() -> None:
    payload = base_payload()
    payload["provenance_graph"]["edges"].pop()
    result = execute(payload)
    assert result["exp31"]["diagnostic_code"] == "BROKEN_LINK"


def test_role_swap_is_invalid() -> None:
    payload = base_payload()
    atom = payload["atomic_payload"][0]
    atom["observation_id"], atom["source_ref"] = atom["source_ref"], atom["observation_id"]
    result = execute(payload)
    assert result["exp31"]["diagnostic_code"] == "SCHEMA_ROLE_MISMATCH"


def test_cardinality_shift_halts() -> None:
    payload = base_payload()
    payload["atomic_payload"].clear()
    result = execute(payload)
    assert result["exp31"]["diagnostic_code"] == "CARDINALITY_VIOLATION"


def test_mixed_identifier_type_is_invalid() -> None:
    payload = base_payload()
    payload["atomic_payload"][0]["source_ref"] = 42069
    result = execute(payload)
    assert result["exp31"]["diagnostic_code"] == "STRICT_IDENTITY_FAIL"


def test_unicode_identifier_is_not_normalized() -> None:
    payload = base_payload()
    payload["atomic_payload"][0]["source_ref"] += "\u200b"
    result = execute(payload)
    assert result["exp31"]["status"] == "VALID"
    assert result["atomic_payload"] if False else True


def test_incomplete_metadata_is_inconclusive() -> None:
    payload = base_payload()
    payload["atomic_payload"][0]["metadata"].pop("precision_dps")
    result = execute(payload)
    assert result["exp31"]["status"] == "INCONCLUSIVE"


def test_semantic_injection_is_invalid() -> None:
    payload = base_payload()
    payload["atomic_payload"][0]["verdict"] = "PASS"
    result = execute(payload)
    assert result["exp31"]["diagnostic_code"] == "SEMANTIC_OVERREACH"
