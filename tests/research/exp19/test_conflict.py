from .test_mapping import map_signal


def make_assertion(source_ref, content):
    return map_signal({"source_ref": source_ref, "payload": {"content": content}})


def resolve_signals(signals):
    groups = {}
    for signal in signals:
        groups.setdefault(signal["atoms"][0]["content"], []).append(signal["source_ref"])
    if len(groups) == 1:
        return {"status": "AGREEMENT", "sources": next(iter(groups.values()))}
    return {
        "status": "INCONCLUSIVE",
        "conflict": {
            "type": "CONTRADICTION",
            "sources": [signal["source_ref"] for signal in signals],
        },
    }


def test_agreement_preserves_both_sources():
    result = resolve_signals([make_assertion("sha256:a", "X"), make_assertion("sha256:b", "X")])
    assert result["status"] == "AGREEMENT"
    assert set(result["sources"]) == {"sha256:a", "sha256:b"}


def test_contradiction_localizes_conflict_without_supported_transition():
    result = resolve_signals([make_assertion("sha256:a", "X"), make_assertion("sha256:b", "Y")])
    assert result["status"] == "INCONCLUSIVE"
    assert result["conflict"]["type"] == "CONTRADICTION"
    assert "status" not in result or result["status"] != "SUPPORTED"


def test_conflict_retains_source_provenance():
    result = resolve_signals([make_assertion("sha256:a", "X"), make_assertion("sha256:b", "Y")])
    assert set(result["conflict"]["sources"]) == {"sha256:a", "sha256:b"}
