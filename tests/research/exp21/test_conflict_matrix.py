from research.exp21.conflict_matrix import build_conflict_matrix


def test_same_subject_event_with_different_values_is_conflict() -> None:
    matrix = build_conflict_matrix(
        [
            {"source_id": "ai-1", "subject": "s", "event": "e", "value": "A"},
            {"source_id": "ai-2", "subject": "s", "event": "e", "value": "B"},
        ]
    )
    assert matrix[0]["classification"] == "CONFLICT"


def test_missing_second_source_is_missing() -> None:
    matrix = build_conflict_matrix(
        [{"source_id": "ai-1", "subject": "s", "event": "e", "value": "A"}]
    )
    assert matrix[0]["classification"] == "MISSING"
