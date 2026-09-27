# teluvane/teluvane/retention.py
"""Per-org retention window and legal hold for event payloads (GDPR storage limitation).

A retention job erases the payload of v2 events older than the org's retention_days, exactly
like a manual erasure: chain hashes and anchors stay valid, an erasure_log row records it. A
legal hold suspends both the job and manual erasure for that org."""

from .db import get_pool
from .store import REDACTED_RATIONALE

MAX_RETENTION_DAYS = 3650


def get_retention(org_id: str) -> dict:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT retention_days, legal_hold FROM org_retention WHERE org_id=%s", (org_id,)
        )
        row = cur.fetchone()
    return (
        {"retention_days": row[0], "legal_hold": row[1]}
        if row
        else {
            "retention_days": None,
            "legal_hold": False,
        }
    )


def set_retention(org_id: str, retention_days: int | None, legal_hold: bool) -> None:
    if retention_days is not None and not 1 <= retention_days <= MAX_RETENTION_DAYS:
        raise ValueError(f"retention_days must be between 1 and {MAX_RETENTION_DAYS}")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_retention(org_id,retention_days,legal_hold) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id) DO UPDATE SET retention_days=EXCLUDED.retention_days, "
            "legal_hold=EXCLUDED.legal_hold, updated_at=now()",
            (org_id, retention_days, legal_hold),
        )
        conn.commit()


# ts is client-supplied text, and one malformed row must not make this job fail for every org.
# safe_ts (migration 0015) casts to timestamptz and returns NULL on any error instead of
# raising, so a row whose ts can't be cast evaluates as NULL < ..., i.e. not expired, the same
# way an unparseable row was treated before, but now that holds for every malformed row and
# not just the ones a regex happened to reject up front.
#
# This only finds candidates; it does not delete anything, so it needs no lock. Each candidate
# session is then locked and erased on its own (see run_retention), the same way audited_run
# locks a session before writing verdicts for it, so the two can never race each other.
_RETENTION_CANDIDATES_SQL = """
SELECT p.org_id, e.session_id, array_agg(p.seq) AS seqs
FROM event_payloads p
JOIN events e ON e.seq = p.seq
JOIN org_retention r ON r.org_id = p.org_id
WHERE r.retention_days IS NOT NULL AND NOT r.legal_hold
  AND safe_ts(e.ts) < now() - make_interval(days => r.retention_days)
GROUP BY p.org_id, e.session_id
"""

# Erases one session's candidate seqs, re-checking both that they still have a payload (a
# concurrent retention run on another instance, or a manual erasure, may have already taken
# them) and that the org's retention/hold state still allows it (a hold placed after the
# candidate scan above must still block this). HAVING count(*) > 0 means an empty `gone` (this
# session had nothing left to erase) inserts nothing and returns nothing, so a session that
# was already handled contributes 0 and is not logged a second time.
_RETENTION_ERASE_SESSION_SQL = """
WITH gone AS (
    DELETE FROM event_payloads p
    USING org_retention r
    WHERE p.org_id = r.org_id AND p.org_id = %s AND p.seq = ANY(%s)
      AND r.retention_days IS NOT NULL AND NOT r.legal_hold
    RETURNING p.seq
)
INSERT INTO erasure_log(org_id, session_id, seqs, requested_by, reason)
SELECT %s, %s, jsonb_agg(seq ORDER BY seq), 'system:retention', 'retention policy'
FROM gone
HAVING count(*) > 0
RETURNING jsonb_array_length(seqs)
"""


def run_retention(pool=None) -> int:
    """Erase expired payloads for every org with a retention window and no legal hold.
    Idempotent and safe to run on several instances at once. Returns payloads erased.

    Candidates for every org are found in one query, but each (org_id, session_id) is then
    locked and erased in its own short transaction, taking the same
    pg_advisory_xact_lock(hashtext(f"{org_id}:{session_id}")) key audited_run (auditlock.py)
    takes before reading events and writing verdicts. A single batch statement covering every
    org, as this job used to be, cannot also take a per-session lock around its delete, so a
    retention pass could run concurrently with a tribunal audit for the same session; locking
    per session here closes that race the same way erase_payloads does for a manual erasure."""
    pool = pool or get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(_RETENTION_CANDIDATES_SQL)
        candidates = cur.fetchall()
    erased = 0
    for org_id, session_id, seqs in candidates:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{org_id}:{session_id}",))
            cur.execute(_RETENTION_ERASE_SESSION_SQL, (org_id, seqs, org_id, session_id))
            row = cur.fetchone()
            if row is not None:
                cur.execute(
                    "UPDATE verdicts SET rationale=%s WHERE org_id=%s AND session_id=%s",
                    (REDACTED_RATIONALE, org_id, session_id),
                )
                erased += row[0]
            conn.commit()  # release the advisory lock
    return erased
