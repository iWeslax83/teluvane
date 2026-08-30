-- 0012: on-chain anchoring of session integrity chains

CREATE TABLE IF NOT EXISTS anchor_batches (
    id            BIGSERIAL PRIMARY KEY,
    root          TEXT NOT NULL UNIQUE,
    chain_id      INTEGER NOT NULL,
    tx_hash       TEXT,
    block_number  BIGINT,
    confirmations INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL,
    gas_used      BIGINT,
    fee_wei       NUMERIC,
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at  TIMESTAMPTZ,
    mined_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_anchors (
    org_id               TEXT NOT NULL,
    session_id           TEXT NOT NULL,
    anchored_through_seq  BIGINT NOT NULL,
    batch_id             BIGINT NOT NULL REFERENCES anchor_batches(id),
    chain_head           TEXT NOT NULL,
    proof                JSONB NOT NULL DEFAULT '[]',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, session_id, anchored_through_seq)
);
CREATE INDEX IF NOT EXISTS idx_session_anchors_batch ON session_anchors (batch_id);
CREATE INDEX IF NOT EXISTS idx_session_anchors_lookup ON session_anchors (org_id, session_id);

CREATE TABLE IF NOT EXISTS session_anchor_public (
    org_id      TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    PRIMARY KEY (org_id, session_id)
);
