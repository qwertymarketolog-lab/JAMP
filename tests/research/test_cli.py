"""P21.3 CLI Interface & Lineage Inspection Layer acceptance/adversarial tests.

Test-first contract: this file is intentionally added before the CLI
implementation and defines the 40-gate public contract.
"""
from __future__ import annotations

import json
import socket
from dataclasses import replace

import pytest

from jamp.research.session import ResearchSession, SessionArtifact
from jamp.research.cli import (
    CLIError,
    ResearchCLI,
    build_parser,
    main,
)

H = {
    "question": "1" * 64,
    "plan": "2" * 64,
    "execution": "3" * 64,
    "result": "4" * 64,
    "interpretation": "5" * 64,
    "claim": "6" * 64,
    "consensus": "7" * 64,
    "revision": "8" * 64,
}


def make_session() -> ResearchSession:
    return ResearchSession.create(
        metadata={"title": "CLI test", "purpose": "inspection"},
        artifacts=[SessionArtifact(k, v) for k, v in H.items()],
        status="OPEN",
    )


def make_objects(session: ResearchSession):
    # Generic exported object graph deliberately mirrors the content-addressed
    # upstream chain while keeping the CLI independent of concrete engines.
    return {
        H["question"]: {"kind": "question", "question_hash": H["question"], "plan_hash": H["plan"]},
        H["plan"]: {"kind": "plan", "plan_hash": H["plan"], "question_hash": H["question"], "execution_hash": H["execution"]},
        H["execution"]: {"kind": "execution", "execution_hash": H["execution"], "plan_hash": H["plan"], "result_hash": H["result"]},
        H["result"]: {"kind": "result", "result_hash": H["result"], "execution_hash": H["execution"], "interpretation_hash": H["interpretation"]},
        H["interpretation"]: {"kind": "interpretation", "interpretation_hash": H["interpretation"], "result_hash": H["result"], "claim_hash": H["claim"]},
        H["claim"]: {"kind": "claim", "claim_hash": H["claim"], "interpretation_hash": H["interpretation"], "consensus_hash": H["consensus"]},
        H["consensus"]: {"kind": "consensus", "consensus_hash": H["consensus"], "claim_hash": H["claim"], "revision_hash": H["revision"]},
        H["revision"]: {"kind": "revision", "revision_hash": H["revision"], "consensus_hash": H["consensus"], "question_hash": H["question"]},
    }


@pytest.fixture
def cli():
    session = make_session()
    return ResearchCLI({session.session_hash: session}, make_objects(session)), session


# 01–10 CLI Core

def test_01_cli_schema_and_parser_valid(cli):
    parser = build_parser()
    assert parser is not None
    assert parser.prog == "jamp"


def test_02_commands_are_namespaced_under_research(cli):
    parser = build_parser()
    args = parser.parse_args(["research", "session", "inspect", "a" * 64])
    assert args.group == "research"


def test_03_session_inspect_command_exists(cli):
    obj, session = cli
    assert "session" in obj.command_names


def test_04_lineage_command_exists(cli):
    obj, _ = cli
    assert "lineage" in obj.command_names


def test_05_verify_command_exists(cli):
    obj, _ = cli
    assert "verify" in obj.command_names


def test_06_export_command_exists(cli):
    obj, _ = cli
    assert "export" in obj.command_names


def test_07_argument_parsing_is_deterministic(cli):
    parser = build_parser()
    a = parser.parse_args(["research", "verify", H["result"]])
    b = parser.parse_args(["research", "verify", H["result"]])
    assert vars(a) == vars(b)


def test_08_command_output_is_deterministic(cli):
    obj, session = cli
    assert obj.inspect(session.session_hash) == obj.inspect(session.session_hash)
    assert obj.export(session.session_hash) == obj.export(session.session_hash)


def test_09_cli_contains_no_scientific_authority(cli):
    obj, _ = cli
    assert not any(x in obj.source_semantics for x in ("truth", "infer", "decide"))


def test_10_output_is_runtime_independent(cli):
    obj, session = cli
    assert "timestamp" not in obj.inspect(session.session_hash)
    assert "pid" not in obj.inspect(session.session_hash)


# 11–20 Session Inspection

def test_11_inspect_accepts_valid_session_hash(cli):
    obj, session = cli
    assert session.session_hash in obj.inspect(session.session_hash)


def test_12_unknown_session_is_rejected(cli):
    obj, _ = cli
    with pytest.raises(CLIError, match="unknown session"):
        obj.inspect("f" * 64)


def test_13_inspection_renders_complete_metadata(cli):
    obj, session = cli
    out = obj.inspect(session.session_hash)
    assert "title" in out and "purpose" in out


def test_14_inspection_renders_status(cli):
    obj, session = cli
    assert "OPEN" in obj.inspect(session.session_hash)


def test_15_inspection_renders_question_index(cli):
    obj, session = cli
    assert H["question"] in obj.inspect(session.session_hash)


def test_16_inspection_renders_plan_index(cli):
    obj, session = cli
    assert H["plan"] in obj.inspect(session.session_hash)


def test_17_inspection_renders_execution_index(cli):
    obj, session = cli
    assert H["execution"] in obj.inspect(session.session_hash)


def test_18_inspection_renders_remaining_indexes(cli):
    obj, session = cli
    out = obj.inspect(session.session_hash)
    assert all(H[k] in out for k in ("result", "interpretation", "claim", "consensus", "revision"))


def test_19_inspection_is_non_mutating(cli):
    obj, session = cli
    before = session.export()
    obj.inspect(session.session_hash)
    assert session.export() == before


def test_20_inspection_preserves_canonical_identity(cli):
    obj, session = cli
    assert obj.verify(session.session_hash) is True
    assert session.compute_session_hash() == session.session_hash


# 21–28 Lineage

def test_21_lineage_accepts_content_addressed_identifier(cli):
    obj, _ = cli
    assert H["result"] in obj.lineage(H["result"])


def test_22_lineage_reconstructs_upstream(cli):
    obj, _ = cli
    out = obj.lineage(H["revision"])
    assert H["question"] in out and H["execution"] in out


def test_23_lineage_reconstructs_downstream_membership(cli):
    obj, _ = cli
    out = obj.lineage(H["question"])
    assert H["revision"] in out


def test_24_full_p19_p20_p21_provenance_is_visible(cli):
    obj, _ = cli
    out = obj.lineage(H["result"])
    assert all(H[k] in out for k in H)


def test_25_causal_order_is_preserved(cli):
    obj, _ = cli
    out = obj.lineage(H["question"])
    assert out.index(H["question"]) < out.index(H["plan"]) < out.index(H["execution"]) < out.index(H["result"])


def test_26_revision_lineage_is_preserved(cli):
    obj, _ = cli
    out = obj.lineage(H["revision"])
    assert H["consensus"] in out and H["revision"] in out


def test_27_equivalent_lineage_has_deterministic_output(cli):
    obj, _ = cli
    assert obj.lineage(H["result"]) == obj.lineage(H["result"])


def test_28_cyclic_lineage_is_rejected(cli):
    obj, _ = cli
    obj.objects[H["revision"]]["question_hash"] = H["revision"]
    with pytest.raises(CLIError, match="cycle"):
        obj.lineage(H["revision"])


# 29–34 Verification & Export

def test_29_verify_checks_session_identity(cli):
    obj, session = cli
    assert obj.verify(session.session_hash) is True


def test_30_verify_checks_every_referenced_artifact(cli):
    obj, session = cli
    assert obj.verify(session.session_hash, require_objects=True) is True


def test_31_verify_detects_artifact_substitution(cli):
    obj, session = cli
    obj.objects[H["result"]]["result_hash"] = "9" * 64
    with pytest.raises(CLIError, match="substitution"):
        obj.verify(session.session_hash, require_objects=True)


def test_32_verify_detects_artifact_tampering(cli):
    obj, session = cli
    obj.objects[H["result"]]["payload"] = "tampered"
    with pytest.raises(CLIError, match="tamper"):
        obj.verify(session.session_hash, require_objects=True)


def test_33_export_is_canonical(cli):
    obj, session = cli
    exported = obj.export(session.session_hash)
    assert exported == obj.export(session.session_hash)
    assert json.loads(exported)["session_hash"] == session.session_hash


def test_34_export_round_trip_preserves_session_hash(cli):
    obj, session = cli
    restored = ResearchSession.import_(obj.export(session.session_hash))
    assert restored.session_hash == session.session_hash
    assert restored.compute_session_hash() == session.session_hash


# 35–40 Adversarial & Isolation

def test_35_invalid_hash_injection_is_rejected(cli):
    obj, _ = cli
    with pytest.raises(CLIError):
        obj.verify("../../etc/passwd")


def test_36_path_injection_is_rejected_without_filesystem_access(cli, monkeypatch):
    obj, _ = cli
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("filesystem access")))
    with pytest.raises(CLIError):
        obj.export("../session")


def test_37_runtime_metadata_injection_is_rejected(cli):
    obj, _ = cli
    with pytest.raises(CLIError, match="runtime"):
        obj.render_metadata({"timestamp": "2026-09-09T00:00:00Z"})


def test_38_network_access_is_prohibited(cli, monkeypatch):
    obj, session = cli
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access")))
    assert obj.verify(session.session_hash) is True


def test_39_domain_contamination_is_prohibited(cli):
    obj, _ = cli
    assert "jamp.domain" not in obj.imports


def test_40_cli_cannot_mutate_p21_core(cli):
    obj, session = cli
    before = session.export()
    obj.inspect(session.session_hash)
    obj.lineage(H["result"])
    obj.verify(session.session_hash)
    obj.export(session.session_hash)
    assert session.export() == before


def test_meta_exactly_40_gate_tests():
    tests = [name for name, value in globals().items() if name.startswith("test_") and name[5:7].isdigit()]
    assert len(tests) == 40
