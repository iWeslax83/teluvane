import os
import time

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
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


def _jwt(user_id, email=None):
    now = int(time.time())
    payload = {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600}
    if email:
        payload["email"] = email
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def test_invite_then_new_signup_auto_joins_the_team(client):
    org = create_org("Acme", "owner-1")
    owner_h = {"Authorization": f"Bearer {_jwt('owner-1')}"}

    r = client.post(
        "/orgs/invites", json={"email": "New.Hire@acme.com", "role": "member"}, headers=owner_h
    )
    assert r.status_code == 200 and r.json()["email"] == "new.hire@acme.com"

    invitee_h = {"Authorization": f"Bearer {_jwt('invitee-1', email='new.hire@acme.com')}"}
    r2 = client.post("/orgs", json={"name": "should be ignored"}, headers=invitee_h)
    assert r2.status_code == 200 and r2.json()["org_id"] == org  # joined the team, not a new org

    members = {m["user_id"]: m["role"] for m in client.get("/orgs/members", headers=owner_h).json()}
    assert members.get("invitee-1") == "member"
    assert client.get("/orgs/invites", headers=owner_h).json() == []  # consumed


def test_non_owner_cannot_invite_or_manage_members(client):
    create_org("Acme", "owner-1")
    invitee_h = {"Authorization": f"Bearer {_jwt('invitee-1', email='m@acme.com')}"}
    client.post(
        "/orgs/invites",
        json={"email": "m@acme.com", "role": "member"},
        headers={"Authorization": f"Bearer {_jwt('owner-1')}"},
    )
    client.post("/orgs", json={"name": "x"}, headers=invitee_h)  # invitee-1 joins as member

    r = client.post("/orgs/invites", json={"email": "another@acme.com"}, headers=invitee_h)
    assert r.status_code == 403
    r2 = client.delete("/orgs/members/owner-1", headers=invitee_h)
    assert r2.status_code == 403
    r3 = client.put("/orgs/members/owner-1", json={"role": "member"}, headers=invitee_h)
    assert r3.status_code == 403


def test_owner_can_remove_a_member(client):
    create_org("Acme", "owner-1")
    owner_h = {"Authorization": f"Bearer {_jwt('owner-1')}"}
    client.post("/orgs/invites", json={"email": "m@acme.com"}, headers=owner_h)
    client.post(
        "/orgs",
        json={"name": "x"},
        headers={"Authorization": f"Bearer {_jwt('invitee-1', email='m@acme.com')}"},
    )

    r = client.delete("/orgs/members/invitee-1", headers=owner_h)
    assert r.status_code == 200
    assert all(
        m["user_id"] != "invitee-1" for m in client.get("/orgs/members", headers=owner_h).json()
    )


def test_cannot_remove_the_last_owner_via_api(client):
    create_org("Acme", "owner-1")
    owner_h = {"Authorization": f"Bearer {_jwt('owner-1')}"}
    r = client.delete("/orgs/members/owner-1", headers=owner_h)
    assert r.status_code == 400
