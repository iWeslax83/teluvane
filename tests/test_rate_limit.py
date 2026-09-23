import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("TELUVANE_SECRET_KEY", "BDUpLFAo9s1dqKy3BZFUcEvdGA7sS0rgdpUEe3Yai8I=")
import importlib

from fastapi.testclient import TestClient

import teluvane.ingest as ing
from teluvane.apikeys import create_api_key
from teluvane.db import get_pool
from teluvane.migrate import apply_migrations
from teluvane.orgs import create_org


def _clean():
    apply_migrations()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, byok_secrets, org_members, orgs RESTART IDENTITY CASCADE"
        )
        conn.commit()


def test_events_rate_limited():
    _clean()
    # teluvane.ingest is a process-wide singleton (its module-level `app`/`limiter` are shared
    # with every other test file), so reload it under a tight limit only for this test's
    # duration and reload it back to the real EVENTS_RATE_LIMIT afterwards. Without the
    # restore, this test would permanently cripple every other test's rate limit for the rest
    # of the pytest process, making the whole suite's outcome depend on run order.
    original_limit = os.environ.get("EVENTS_RATE_LIMIT")
    os.environ["EVENTS_RATE_LIMIT"] = "3/minute"
    try:
        importlib.reload(ing)
        org = create_org("Acme", "u1")
        key = create_api_key(org, "ci")
        c = TestClient(ing.app)
        h = {"Authorization": f"Bearer {key}"}
        ev = {
            "agent_id": "a",
            "session_id": "s",
            "kind": "tool_call",
            "tool": "t",
            "args": {},
            "intent": "i",
        }
        codes = [c.post("/events", json=ev, headers=h).status_code for _ in range(5)]
        assert 429 in codes  # the limiter trips within the window
    finally:
        if original_limit is None:
            os.environ.pop("EVENTS_RATE_LIMIT", None)
        else:
            os.environ["EVENTS_RATE_LIMIT"] = original_limit
        importlib.reload(ing)
