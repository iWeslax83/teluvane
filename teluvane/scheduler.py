# teluvane/teluvane/scheduler.py
"""Automated tribunal runs (Pro plan). A single in-process APScheduler ticks every minute and
re-audits any due org's sessions. This runs inside the same web process as the API, so it only
does work while that process is warm; a Render free-tier instance that's asleep or restarting
skips ticks like any other in-process timer would. That tradeoff is what "automated" can mean
without a separate worker/cron service, and is disclosed as such wherever this is documented."""

from datetime import datetime, timedelta, timezone

from . import anchor
from .auditlock import audited_run
from .billing import org_plan
from .byok import get_byok
from .custom_rules import effective_pack
from .db import get_pool
from .orgs import get_policy_framework
from .retention import run_retention

TICK_INTERVAL_SECONDS = 60

_last_anchor_run = None
_last_retention_run = None
RETENTION_INTERVAL_MINUTES = 60


def _anchor_due(interval_minutes: int) -> bool:
    """True at most once per `interval_minutes`; records the run time when it fires."""
    global _last_anchor_run
    now = datetime.now(timezone.utc)
    if (
        _last_anchor_run is None
        or (now - _last_anchor_run).total_seconds() >= interval_minutes * 60
    ):
        _last_anchor_run = now
        return True
    return False


def run_anchor_cycle() -> None:
    """One anchoring tick: reconcile in-flight batches every cycle, submit a new batch
    when the batch interval is due. No-op unless on-chain anchoring is configured."""
    cfg = anchor.chain_config()
    if not cfg:
        return
    pool = get_pool()
    anchor.reconcile_pending(pool, cfg)
    if _anchor_due(cfg.batch_interval_minutes):
        anchor.run_anchor_pass(pool, cfg)


def run_retention_cycle() -> int:
    """Erase expired event payloads, at most once per RETENTION_INTERVAL_MINUTES per process."""
    global _last_retention_run
    now = datetime.now(timezone.utc)
    if (
        _last_retention_run is not None
        and (now - _last_retention_run).total_seconds() < RETENTION_INTERVAL_MINUTES * 60
    ):
        return 0
    _last_retention_run = now
    return run_retention(get_pool())


def get_schedule(org_id: str) -> dict:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT enabled, interval_minutes, last_run_at FROM org_audit_schedule WHERE org_id=%s",
            (org_id,),
        )
        row = cur.fetchone()
    if not row:
        return {"enabled": False, "interval_minutes": 60, "last_run_at": None}
    return {
        "enabled": row[0],
        "interval_minutes": row[1],
        "last_run_at": row[2].isoformat() if row[2] else None,
    }


def set_schedule(org_id: str, enabled: bool, interval_minutes: int) -> None:
    interval_minutes = max(15, interval_minutes)  # floor: don't let a typo hammer the tribunal
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_audit_schedule(org_id,enabled,interval_minutes) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id) DO UPDATE SET enabled=EXCLUDED.enabled, "
            "interval_minutes=EXCLUDED.interval_minutes",
            (org_id, enabled, interval_minutes),
        )
        conn.commit()


def _due_orgs() -> list[str]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT org_id, interval_minutes, last_run_at FROM org_audit_schedule WHERE enabled"
        )
        rows = cur.fetchall()
    now = datetime.now(timezone.utc)
    return [
        org_id
        for org_id, interval_minutes, last_run_at in rows
        if last_run_at is None or now - last_run_at >= timedelta(minutes=interval_minutes)
    ]


def _mark_ran(org_id: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE org_audit_schedule SET last_run_at=now() WHERE org_id=%s", (org_id,))
        conn.commit()


def run_due_schedules(store, packs, hosted_api_key: str | None = None) -> dict[str, int]:
    """Re-audit every session for each org whose schedule is due. `packs` is a
    {framework_id: PolicyPack} mapping (ingest.FRAMEWORK_PACKS); each org's own
    policy_framework selects which one it's audited against. Pro-plan check is defense in
    depth (writes to the schedule are already pro-gated at the API layer), so a downgraded org's
    schedule goes dormant instead of quietly continuing to run. Returns {org_id: sessions_run}."""
    ran: dict[str, int] = {}
    for org_id in _due_orgs():
        if org_plan(org_id) != "pro":
            continue
        api_key = get_byok(org_id, "anthropic") or hosted_api_key
        base = packs.get(get_policy_framework(org_id)) or next(iter(packs.values()))
        org_pack = effective_pack(org_id, base)
        sessions = store.sessions(org_id)
        for s in sessions:
            audited_run(store, org_id, s["session_id"], org_pack, api_key)
        _mark_ran(org_id)
        ran[org_id] = len(sessions)
    return ran
