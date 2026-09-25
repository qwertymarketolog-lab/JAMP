from ci_zero_job_lineage import CIObservation, investigate_lineage

WORKFLOW = ".github/workflows/import-historical.yml"
START = "a" * 40
ZERO = "b" * 40
NORMAL = "c" * 40


def obs(sha, *, jobs=0, conclusion="failure"):
    return CIObservation(
        sha=sha,
        workflow=WORKFLOW,
        run_id=123 if sha != NORMAL else 122,
        event="push",
        branch="main",
        status="completed",
        conclusion=conclusion,
        jobs_count=jobs,
    )


def test_finds_first_normal_to_zero_job_failure_boundary():
    parents = {START: ZERO, ZERO: NORMAL}
    observations = {
        START: obs(START),
        ZERO: obs(ZERO),
        NORMAL: obs(NORMAL, jobs=1, conclusion="success"),
    }

    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda sha: parents.get(sha),
        observe=lambda sha, workflow: observations.get(sha),
    )

    assert result.state == "VERIFIED"
    assert result.boundary is not None
    assert result.boundary.normal_sha == NORMAL
    assert result.boundary.failure_sha == ZERO
    assert result.boundary.failure_run_id == 123


def test_boundary_direction_is_failure_to_normal():
    parents = {START: ZERO, ZERO: NORMAL}
    observations = {
        START: obs(START),
        ZERO: obs(ZERO),
        NORMAL: obs(NORMAL, jobs=1, conclusion="success"),
    }

    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda sha: parents.get(sha),
        observe=lambda sha, workflow: observations.get(sha),
    )

    assert result.boundary is not None
    assert result.boundary.failure_sha == ZERO
    assert result.boundary.normal_sha == NORMAL


def test_missing_jobs_is_inconclusive_not_pass():
    item = CIObservation(
        sha=START,
        workflow=WORKFLOW,
        run_id=123,
        event="push",
        branch="main",
        status="completed",
        conclusion="failure",
        jobs_count=None,
    )
    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda _: None,
        observe=lambda _, __: item,
    )
    assert result.state == "INCONCLUSIVE"
    assert result.boundary is None


def test_workflow_identity_mismatch_is_inconclusive():
    item = obs(START)
    wrong = CIObservation(**{**item.__dict__, "workflow": "other.yml"})
    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda _: None,
        observe=lambda _, __: wrong,
    )
    assert result.state == "INCONCLUSIVE"


def test_nonterminal_run_is_inconclusive():
    item = CIObservation(
        sha=START,
        workflow=WORKFLOW,
        run_id=123,
        event="push",
        branch="main",
        status="in_progress",
        conclusion="",
        jobs_count=0,
    )
    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda _: None,
        observe=lambda _, __: item,
    )
    assert result.state == "INCONCLUSIVE"


def test_cycle_is_inconclusive():
    parents = {START: ZERO, ZERO: START}
    observations = {START: obs(START), ZERO: obs(ZERO)}
    result = investigate_lineage(
        start_sha=START,
        workflow=WORKFLOW,
        parent_of=lambda sha: parents.get(sha),
        observe=lambda sha, workflow: observations.get(sha),
    )
    assert result.state == "INCONCLUSIVE"
