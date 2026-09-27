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


# The CASE guards the cast: ts is client-supplied text, and one malformed legacy row must not
# make this job fail for every org. Rows that do not parse are simply never expired.
_RETENTION_SQL = """
WITH doomed AS (
    SELECT p.seq, p.org_id, e.session_id
    FROM event_payloads p
    JOIN events e ON e.seq = p.seq
    JOIN org_retention r ON r.org_id = p.org_id
    WHERE r.retention_days IS NOT NULL AND NOT r.legal_hold
      AND CASE WHEN e.ts ~ '^\\d{4}-\\d{2}-\\d{2}T[0-9:.]+(Z|[+-]\\d{2}:\\d{2})$'
               THEN e.ts::timestamptz END < now() - make_interval(days => r.retention_days)
), gone AS (
    DELETE FROM event_payloads p USING doomed d WHERE p.seq = d.seq
    RETURNING d.org_id, d.session_id, d.seq
)
INSERT INTO erasure_log(org_id, session_id, seqs, requested_by, reason)
SELECT org_id, session_id, jsonb_agg(seq ORDER BY seq), 'system:retention', 'retention policy'
FROM gone GROUP BY org_id, session_id
RETURNING org_id, session_id, jsonb_array_length(seqs)
"""


def run_retention(pool=None) -> int:
    """Erase expired payloads for every org with a retention window and no legal hold.
    Idempotent and safe to run on several instances at once. Returns payloads erased."""
    pool = pool or get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(_RETENTION_SQL)
        touched = cur.fetchall()
        for org_id, session_id, _ in touched:
            cur.execute(
                "UPDATE verdicts SET rationale=%s WHERE org_id=%s AND session_id=%s",
                (REDACTED_RATIONALE, org_id, session_id),
            )
        conn.commit()
    return sum(n for _, _, n in touched)
