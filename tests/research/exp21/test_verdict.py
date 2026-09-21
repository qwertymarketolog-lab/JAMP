from research.exp21.verdict import derive_verdict


def test_conflict_without_resolving_evidence_is_inconclusive() -> None:
    matrix = [{"classification": "CONFLICT"}]
    assert derive_verdict(matrix) == "INCONCLUSIVE"


def test_model_agreement_does_not_auto_promote_to_supported() -> None:
    matrix = [{"classification": "AGREEMENT", "sources": ["ai-1", "ai-2"]}]
    assert derive_verdict(matrix) != "SUPPORTED"
