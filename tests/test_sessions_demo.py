import os
import time

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("TELUVANE_SECRET_KEY", "BDUpLFAo9s1dqKy3BZFUcEvdGA7sS0rgdpUEe3Yai8I=")
import jwt
import pytest
from fastapi.testclient import TestClient

from teluvane.db import get_pool
from teluvane.migrate import apply_migrations
from teluvane.orgs import create_org


@pytest.fixture(autouse=True)
def _clean_db():
    apply_migrations()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, byok_secrets, org_members, orgs RESTART IDENTITY CASCADE"
        )
        conn.commit()


@pytest.fixture
def client():
    from teluvane.ingest import app

    return TestClient(app)


def _jwt(user_id):
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600},
        "test-secret",
        algorithm="HS256",
    )


def test_sessions_lists_org_sessions(client):
    # Seed via the Store directly so the test does not depend on the /events rate limit
    # (other test modules mutate EVENTS_RATE_LIMIT, which would otherwise 429 these posts).
    from teluvane.schema import Event
    from teluvane.store import Store

    org = create_org("Acme", "u1")
    s = Store()
    for sid in ("s-a", "s-a", "s-b"):
        s.append(org, Event(agent_id="a", session_id=sid, kind="tool_call", tool="t", intent="x"))
    r = client.get("/sessions", headers={"Authorization": f"Bearer {_jwt('u1')}"})
    assert r.status_code == 200
    sessions = {s["session_id"]: s for s in r.json()}
    assert set(sessions) == {"s-a", "s-b"}
    assert sessions["s-a"]["events"] == 2


def test_sessions_requires_auth(client):
    assert client.get("/sessions").status_code == 401


def test_demo_seed_creates_auditable_session(client):
    create_org("Acme", "u1")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    r = client.post("/demo/seed", headers=h)
    assert r.status_code == 200
    sess = r.json()["session_id"]
    assert sess.startswith("demo-")
    # the seeded session shows up and audits to real violations (offline detector)
    assert any(s["session_id"] == sess for s in client.get("/sessions", headers=h).json())
    verdicts = client.post(f"/audit/{sess}", headers=h).json()
    rule_ids = {v["rule_id"] for v in verdicts}
    assert "data_exfiltration" in rule_ids


def test_demo_seed_is_tenant_scoped(client):
    create_org("A", "ua")
    create_org("B", "ub")
    sess = client.post("/demo/seed", headers={"Authorization": f"Bearer {_jwt('ua')}"}).json()[
        "session_id"
    ]
    # org B cannot see org A's seeded demo session
    b_sessions = client.get("/sessions", headers={"Authorization": f"Bearer {_jwt('ub')}"}).json()
    assert all(s["session_id"] != sess for s in b_sessions)


def test_demo_seed_returns_503_on_db_failure(client, monkeypatch):
    from teluvane import ingest
    from teluvane.orgs import create_org

    create_org("Acme", "u1")

    def _boom(self, org_id, e):
        raise RuntimeError("connection pool exhausted")

    monkeypatch.setattr(ingest.store, "append", _boom.__get__(ingest.store))

    r = client.post("/demo/seed", headers={"Authorization": f"Bearer {_jwt('u1')}"})
    assert r.status_code == 503
    assert r.json()["error"] == "seed_unavailable"
