import time

import jwt
import pytest
from fastapi.testclient import TestClient

from teluvane.apikeys import create_api_key
from teluvane.db import get_pool
from teluvane.orgs import create_org
from teluvane.retention import get_retention, run_retention, set_retention


def _jwt(user_id):
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600},
        "test-secret",
        algorithm="HS256",
    )


@pytest.fixture
def client(store):
    from teluvane.ingest import app

    return TestClient(app)


@pytest.fixture
def seeded(client, store):
    org = create_org("Acme", "owner1")
    key = create_api_key(org, "ci")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_members(org_id,user_id,role) VALUES(%s,'member1','member')", (org,)
        )
        conn.commit()
    for i in range(2):
        r = client.post(
            "/events",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "agent_id": "a",
                "session_id": "sx",
                "kind": "llm_call",
                "intent": f"call jane@example.com {i}",
            },
        )
        assert r.status_code == 200
    return org, {"Authorization": f"Bearer {_jwt('owner1')}"}


def test_owner_can_erase_and_verify_still_passes(client, seeded):
    org, h = seeded
    r = client.post("/sessions/sx/erase", json={"reason": "art 17"}, headers=h)
    assert r.status_code == 200 and r.json()["erased"] == 2
    v = client.get("/verify?session_id=sx", headers=h).json()
    assert v == {"chain_intact": True, "erased_events": 2, "unexplained_erasures": 0}
    ev = client.get("/events?session_id=sx", headers=h).json()
    assert all(e["erased"] and e["intent"] == "" for e in ev)


def test_erase_without_body_erases_everything(client, seeded):
    _, h = seeded
    assert client.post("/sessions/sx/erase", headers=h).json()["erased"] == 2


def test_member_cannot_erase(client, seeded):
    _, _ = seeded
    r = client.post("/sessions/sx/erase", headers={"Authorization": f"Bearer {_jwt('member1')}"})
    assert r.status_code == 403


def test_unknown_session_404(client, seeded):
    _, h = seeded
    assert client.post("/sessions/nope/erase", headers=h).status_code == 404


def test_legal_hold_blocks_erasure_and_retention(client, seeded):
    org, h = seeded
    assert (
        client.put(
            "/orgs/retention", json={"retention_days": 1, "legal_hold": True}, headers=h
        ).status_code
        == 200
    )
    assert client.post("/sessions/sx/erase", headers=h).status_code == 409
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts='2020-01-01T00:00:00+00:00' WHERE org_id=%s", (org,))
        conn.commit()
    assert run_retention() == 0
    assert (
        client.put(
            "/orgs/retention", json={"retention_days": 1, "legal_hold": False}, headers=h
        ).status_code
        == 200
    )
    assert client.post("/sessions/sx/erase", headers=h).status_code == 200


def test_retention_validation_and_member_read_only(client, seeded):
    _, h = seeded
    assert client.put("/orgs/retention", json={"retention_days": 0}, headers=h).status_code == 422
    m = {"Authorization": f"Bearer {_jwt('member1')}"}
    assert client.put("/orgs/retention", json={"retention_days": 30}, headers=m).status_code == 403
    assert client.get("/orgs/retention", headers=m).json() == {
        "retention_days": None,
        "legal_hold": False,
    }


def test_retention_job_erases_only_expired_payloads(client, seeded):
    org, h = seeded
    set_retention(org, 30, False)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE events SET ts='2020-01-01T00:00:00+00:00' "
            "WHERE seq=(SELECT min(seq) FROM events WHERE org_id=%s)",
            (org,),
        )
        cur.execute(
            "UPDATE events SET ts='not a timestamp' "
            "WHERE seq=(SELECT max(seq) FROM events WHERE org_id=%s)",
            (org,),
        )
        conn.commit()
    assert run_retention() == 1
    assert run_retention() == 0
    ev = client.get("/events?session_id=sx", headers=h).json()
    assert [e["erased"] for e in ev] == [True, False]
    assert get_retention(org)["retention_days"] == 30


def test_ingest_rejects_unparseable_timestamp(client, seeded):
    org, _ = seeded
    key = create_api_key(org, "ci2")
    r = client.post(
        "/events",
        headers={"Authorization": f"Bearer {key}"},
        json={"agent_id": "a", "session_id": "sx", "kind": "llm_call", "ts": "yesterday"},
    )
    assert r.status_code == 422
