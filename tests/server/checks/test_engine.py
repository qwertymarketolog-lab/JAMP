"""Truth-table tests for the server-side check orchestrator."""
from __future__ import annotations

from unittest.mock import patch

from jamp.server.checks import engine


def _run(provenance: dict, signature: dict) -> dict:
    with (
        patch.object(engine, "check_provenance", return_value=provenance),
        patch.object(engine, "check_signature", return_value=signature),
    ):
        return engine.verify_code("import samplepkg\nsamplepkg.ok()", "samplepkg")


def test_not_found_is_caught_even_when_signature_is_inconclusive():
    result = _run({"status": "NOT_FOUND"}, {"status": "INCONCLUSIVE"})
    assert result["status"] == "HALLUCINATION_CAUGHT"


def test_suspicious_provenance_is_not_clean():
    result = _run({"status": "SUSPICIOUS"}, {"status": "EXISTS"})
    assert result["status"] == "SUSPICIOUS"
    assert result["reason"] == "provenance_suspicious"


def test_invalid_signature_is_caught():
    result = _run({"status": "TRUSTED"}, {"status": "INVALID_SIGNATURE"})
    assert result["status"] == "HALLUCINATION_CAUGHT"


def test_trusted_existing_signature_is_clean():
    result = _run({"status": "TRUSTED"}, {"status": "EXISTS"})
    assert result["status"] == "CLEAN"


def test_inconclusive_provenance_never_becomes_clean():
    result = _run({"status": "INCONCLUSIVE"}, {"status": "EXISTS"})
    assert result["status"] == "INCONCLUSIVE"


def test_inconclusive_signature_never_becomes_clean():
    result = _run({"status": "TRUSTED"}, {"status": "INCONCLUSIVE"})
    assert result["status"] == "INCONCLUSIVE"


def test_package_identity_is_passed_to_both_checks():
    with (
        patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}) as provenance,
        patch.object(engine, "check_signature", return_value={"status": "EXISTS"}) as signature,
    ):
        engine.verify_code("import samplepkg", "samplepkg")
    provenance.assert_called_once_with("samplepkg")
    signature.assert_called_once()
    assert signature.call_args.args == ("import samplepkg", "samplepkg")
    assert signature.call_args.kwargs["parsed_ast"].__class__.__name__ == "Module"


def test_syntax_error_is_inconclusive_before_external_checks():
    with patch.object(engine, "check_provenance") as provenance:
        result = engine.verify_code("def broken(:", "samplepkg")
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "syntax_error"
    provenance.assert_not_called()


def test_generated_source_is_parsed_once_and_shared_with_signature():
    with (
        patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}),
        patch.object(engine, "check_signature", return_value={"status": "EXISTS"}) as signature,
        patch.object(engine.ast, "parse", wraps=engine.ast.parse) as parse,
    ):
        result = engine.verify_code("import samplepkg\\nsamplepkg.ok()", "samplepkg")
    assert result["status"] == "CLEAN"
    parse.assert_called_once()
    assert signature.call_args.kwargs["parsed_ast"] is parse.return_value


def test_temporal_check_requires_explicit_sample_id(tmp_path):
    with (
        patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}),
        patch.object(engine, "load_generation_snapshot") as load_snapshot,
    ):
        result = engine.verify_code(
            "import samplepkg", "samplepkg", temporal_snapshot=tmp_path / "snapshot.json"
        )
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "missing_sample_id"
    load_snapshot.assert_not_called()
