"""Cooldown + monthly cap for the manual POST /anchor/run trigger, so a Pro org
cannot burn the shared signer wallet by spamming forced anchor passes.

State lives in the anchor_forced_runs table, not process memory: a restart or a
second web instance must not reset the cap."""
from datetime import datetime, timezone

from .db import get_pool


def _period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def check_and_record(org_id: str, cooldown_minutes: int, monthly_cap: int) -> str | None:
    """Return None and record a run when the org is allowed one, or a reason string
    ("cooldown" / "monthly-cap") when it is not. Serialized per org with an advisory
    xact lock so two concurrent forced runs can't both slip through."""
    now = datetime.now(timezone.utc)
    period = _period()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"anchor-forced:{org_id}",))

        cur.execute("SELECT max(last_run_at) FROM anchor_forced_runs WHERE org_id=%s", (org_id,))
        last = cur.fetchone()[0]
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < cooldown_minutes * 60:
                conn.commit()
                return "cooldown"

        cur.execute("SELECT count FROM anchor_forced_runs WHERE org_id=%s AND period=%s",
                    (org_id, period))
        row = cur.fetchone()
        if (row[0] if row else 0) >= monthly_cap:
            conn.commit()
            return "monthly-cap"

        cur.execute(
            "INSERT INTO anchor_forced_runs(org_id, period, count, last_run_at) "
            "VALUES(%s,%s,1,now()) "
            "ON CONFLICT (org_id, period) DO UPDATE SET "
            "count = anchor_forced_runs.count + 1, last_run_at = now()",
            (org_id, period))
        conn.commit()
    return None
