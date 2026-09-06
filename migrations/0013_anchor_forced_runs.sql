-- 0013: durable cooldown + monthly cap for the manual POST /anchor/run trigger.
-- Previously tracked in per-process memory, so a restart or a second web instance
-- reset the cap and let a Pro org drain the shared signer wallet.
CREATE TABLE IF NOT EXISTS anchor_forced_runs (
    org_id      TEXT NOT NULL,
    period      TEXT NOT NULL,                 -- 'YYYY-MM' (UTC)
    count       INTEGER NOT NULL DEFAULT 0,
    last_run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, period)
);
ALTER TABLE anchor_forced_runs ENABLE ROW LEVEL SECURITY;
