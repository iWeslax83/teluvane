import os

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/teluvane_test"
    ),
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("TELUVANE_SECRET_KEY", "BDUpLFAo9s1dqKy3BZFUcEvdGA7sS0rgdpUEe3Yai8I=")
import pytest

from teluvane.migrate import apply_migrations
from teluvane.schema import Event
from teluvane.store import Store


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    apply_migrations()


@pytest.fixture
def store():
    s = Store()
    with s.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, org_members, orgs, "
            "anchor_batches, session_anchors, session_anchor_public, erasure_log, org_retention "
            "RESTART IDENTITY CASCADE"
        )
        conn.commit()
    return s


import time

import jwt


@pytest.fixture
def make_jwt():
    def _make(user_id: str, *, expired: bool = False, secret: str = None):
        now = int(time.time())
        payload = {
            "sub": user_id,
            "aud": "authenticated",
            "iat": now,
            "exp": now - 10 if expired else now + 3600,
        }
        return jwt.encode(payload, secret or os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")

    return _make


@pytest.fixture
def org(store):
    """Two orgs exist (org1, org2) so tenant-isolation tests can use both; returns "org1"."""
    with store.pool.connection() as conn, conn.cursor() as cur:
        for oid in ("org1", "org2"):
            cur.execute(
                "INSERT INTO orgs(id,name,owner_user_id) VALUES(%s,'o','u') ON CONFLICT DO NOTHING",
                (oid,),
            )
        conn.commit()
    return "org1"


@pytest.fixture
def add_events(store):
    """add_events(org_id, n=3, session="s1") appends n tool_call events that carry personal data."""

    def _add(org_id, n=3, session="s1"):
        return [
            store.append(
                org_id,
                Event(
                    agent_id="a",
                    session_id=session,
                    kind="tool_call",
                    tool="t",
                    intent=f"email jane@example.com step {i}",
                    args={"ssn": "078-05-1120"},
                    output="done",
                    approved_by="human:u1",
                ),
            )
            for i in range(n)
        ]

    return _add
