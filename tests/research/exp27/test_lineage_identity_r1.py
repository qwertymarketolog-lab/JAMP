"""EXP-27-R1: empirical test of lineage sensitivity in execution identity.

Research-only. This test must not modify src/jamp.
Hypothesis: identical execution content under different upstream lineage
contexts currently produces the same execution_hash.
"""

from jamp.research.execution import make_execution


def test_same_content_different_lineage_context_has_same_execution_identity():
    content_parameters = {"question": "Q", "value": 42}
    observations = [{"value": "same"}]

    lineage_a = {
        "plans": {
            "plan": {
                "plan_hash": "plan",
                "question_hash": "question",
                "provenance": {"parent_ref": "LINEAGE_A"},
            }
        },
        "questions": {"question": {"question_hash": "question"}},
    }
    lineage_b = {
        "plans": {
            "plan": {
                "plan_hash": "plan",
                "question_hash": "question",
                "provenance": {"parent_ref": "LINEAGE_B"},
            }
        },
        "questions": {"question": {"question_hash": "question"}},
    }

    execution_a = make_execution(
        "plan", "question", content_parameters, observations, registry=lineage_a
    )
    execution_b = make_execution(
        "plan", "question", content_parameters, observations, registry=lineage_b
    )

    assert execution_a.compute_hash() == execution_b.compute_hash()
    assert execution_a.execution_hash == execution_b.execution_hash
    assert execution_a.upstream_provenance != execution_b.upstream_provenance
