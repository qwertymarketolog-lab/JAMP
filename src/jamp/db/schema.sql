CREATE TABLE IF NOT EXISTS organizations (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    api_key_hash TEXT NOT NULL UNIQUE,
    plan         TEXT NOT NULL DEFAULT 'free',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_organizations_api_key_hash
    ON organizations (api_key_hash);

CREATE TABLE IF NOT EXISTS audit_traces (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    trace_id        TEXT NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, trace_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_traces_org_trace
    ON audit_traces (organization_id, trace_id);

-- C3: PostgreSQL-backed code verification records.
CREATE TABLE IF NOT EXISTS verdicts (
    id UUID PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    code_hash CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL CHECK (status IN (
        'CLEAN', 'SUSPICIOUS', 'HALLUCINATION_CAUGHT', 'INCONCLUSIVE', 'INTEGRITY_VIOLATED'
    )),
    sample_id TEXT,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_verdicts_org_idempotency UNIQUE (organization_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_verdicts_org_status_created
    ON verdicts (organization_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence_chain (
    id UUID PRIMARY KEY,
    verdict_id UUID NOT NULL REFERENCES verdicts(id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    evidence_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    payload_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_evidence_verdict_sequence UNIQUE (verdict_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS idx_evidence_chain_verdict_sequence
    ON evidence_chain (verdict_id, sequence_no);

-- Arena execution history is tenant-scoped and separate from evidence verdicts.
CREATE TABLE IF NOT EXISTS arena_runs (
    id              UUID PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash    CHAR(64) NOT NULL,
    prompt          TEXT NOT NULL,
    status          VARCHAR(16) NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'PARTIAL')),
    results         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_arena_runs_org_idempotency UNIQUE (organization_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_arena_runs_org_created
    ON arena_runs (organization_id, created_at DESC);

CREATE TABLE IF NOT EXISTS arena_results (
    id                  UUID PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES arena_runs(id) ON DELETE CASCADE,
    model_id            TEXT NOT NULL,
    execution_status    VARCHAR(16) NOT NULL CHECK (execution_status IN ('COMPLETED', 'FAILED')),
    evidence_verdict    VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'
                        CHECK (evidence_verdict = 'UNKNOWN'),
    raw_response        TEXT,
    trace_id            TEXT NOT NULL,
    cost_estimate_rub   TEXT NOT NULL DEFAULT 'UNKNOWN',
    error               JSONB,
    result              JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_arena_results_run_model UNIQUE (run_id, model_id)
);
CREATE INDEX IF NOT EXISTS idx_arena_results_run
    ON arena_results (run_id, created_at);
