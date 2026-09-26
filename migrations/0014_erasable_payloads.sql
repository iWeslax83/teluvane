-- 0014: erasable event payloads (hash version 2).
-- v2 events hash a salted commitment to (intent, args, output, approved_by) instead of the
-- plaintext, and keep that plaintext in event_payloads. Deleting the payload row erases the
-- personal data while every hash in the chain, and every anchored chain head, stays valid.
-- v1 events (hash_version = 1) keep their plaintext in events and cannot be erased.
ALTER TABLE events ADD COLUMN IF NOT EXISTS hash_version SMALLINT NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS payload_commitment TEXT;

CREATE TABLE IF NOT EXISTS event_payloads (
    seq     BIGINT PRIMARY KEY REFERENCES events(seq) ON DELETE CASCADE,
    org_id  TEXT NOT NULL,
    salt    TEXT NOT NULL,   -- 32 random bytes, hex. Deleted with the payload.
    payload TEXT NOT NULL    -- the exact canonical JSON string that was committed to
);
CREATE INDEX IF NOT EXISTS idx_event_payloads_org ON event_payloads (org_id);
ALTER TABLE event_payloads ENABLE ROW LEVEL SECURITY;

-- Accountability record of every erasure. Holds seq numbers and a reason, never content.
CREATE TABLE IF NOT EXISTS erasure_log (
    id           BIGSERIAL PRIMARY KEY,
    org_id       TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    seqs         JSONB NOT NULL,
    requested_by TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_erasure_log_org_session ON erasure_log (org_id, session_id);
ALTER TABLE erasure_log ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS org_retention (
    org_id         TEXT PRIMARY KEY REFERENCES orgs(id) ON DELETE CASCADE,
    retention_days INT CHECK (retention_days IS NULL OR retention_days >= 1),
    legal_hold     BOOLEAN NOT NULL DEFAULT false,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE org_retention ENABLE ROW LEVEL SECURITY;
