# teluvane/teluvane/auditlock.py
from .tribunal import audit  # imported at module scope so tests can monkeypatch it here
from .webhooks import send_webhook


def audited_run(store, org_id: str, session_id: str, pack, api_key: str | None):
    """Serialize per (org_id, session_id) with a Postgres advisory xact lock so two concurrent
    audits cannot both run the tribunal and double-spend the customer's BYOK credits."""
    lock_key = f"{org_id}:{session_id}"
    with store.pool.connection() as conn:
        with conn.cursor() as cur:
            # blocks until any concurrent holder for the same key commits/rolls back
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))
        # now inside the critical section — re-check idempotently
        existing = [v for v in store.verdicts(org_id, session_id) if v.violation]
        if existing:
            conn.commit()  # release lock
            return existing
        events = store.events(org_id, session_id)
        verdicts = audit(events, session_id, pack, anthropic_api_key=api_key)
        for v in verdicts:
            store.add_verdict(org_id, v)
        conn.commit()  # release lock, before the webhook POST so it can't hold it open
    # Only for freshly-computed verdicts, not the `existing` early-return above, so re-running
    # an audit on an already-audited session doesn't re-notify every time.
    send_webhook(org_id, session_id, verdicts)
    return verdicts
