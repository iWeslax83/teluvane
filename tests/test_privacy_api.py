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


def test_partial_retention_update_preserves_legal_hold(client, seeded):
    """Finding 2 regression: PUT /orgs/retention used to default an omitted legal_hold to
    False, so a natural partial update like {"retention_days": 90} silently lifted an active
    hold. A PUT that only mentions retention_days must never change legal_hold."""
    _, h = seeded
    assert (
        client.put(
            "/orgs/retention", json={"retention_days": 1, "legal_hold": True}, headers=h
        ).status_code
        == 200
    )
    assert client.put("/orgs/retention", json={"retention_days": 90}, headers=h).status_code == 200
    assert client.get("/orgs/retention", headers=h).json() == {
        "retention_days": 90,
        "legal_hold": True,
    }
    # And the symmetric case: a PUT that only mentions legal_hold must never change
    # retention_days.
    assert client.put("/orgs/retention", json={"legal_hold": False}, headers=h).status_code == 200
    assert client.get("/orgs/retention", headers=h).json() == {
        "retention_days": 90,
        "legal_hold": False,
    }


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


def test_ingest_rejects_naive_timestamp(client, seeded):
    """A naive timestamp (no UTC offset) passes datetime.fromisoformat but would never expire
    under any retention window, since the retention SQL compares it to timestamptz using a
    different, incomparable type. Ingest must reject it."""
    org, _ = seeded
    key = create_api_key(org, "ci3")
    r = client.post(
        "/events",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "agent_id": "a",
            "session_id": "sx",
            "kind": "llm_call",
            "ts": "2026-09-27T10:00:00",
        },
    )
    assert r.status_code == 422


def test_retention_survives_cross_tenant_bad_timestamp(client):
    """Finding 1 regression: strings like "2026-09-27T10:00:00+23:59" pass both
    datetime.fromisoformat and the retention job's old ts ~ regex guard, but make Postgres's
    ::timestamptz cast raise ("time zone displacement out of range"). Because _RETENTION_SQL
    processed every org in one query, one such row from ANY org (org B here) used to make
    run_retention() raise for every org, silently disabling retention entirely. safe_ts
    (migration 0015) makes the cast unable to raise on any input, so org A's expired payload
    is still erased and org B's payload (uncastable ts, so never "expired") is left alone."""
    org_a = create_org("TenantA", "owner-a")
    org_b = create_org("TenantB", "owner-b")
    key_a = create_api_key(org_a, "ci")
    key_b = create_api_key(org_b, "ci")
    set_retention(org_a, 1, False)
    set_retention(org_b, 1, False)

    r = client.post(
        "/events",
        headers={"Authorization": f"Bearer {key_a}"},
        json={
            "agent_id": "a",
            "session_id": "sa",
            "kind": "llm_call",
            "ts": "2020-01-01T00:00:00+00:00",
        },
    )
    assert r.status_code == 200

    for bad_ts in (
        "2026-09-27T10Z",
        "2026-09-27T10+03:00",
        "2026-09-27T10:00:00+23:59",
    ):
        r = client.post(
            "/events",
            headers={"Authorization": f"Bearer {key_b}"},
            json={"agent_id": "a", "session_id": "sb", "kind": "llm_call", "ts": bad_ts},
        )
        # These pass fromisoformat and the tz-aware check (all carry an explicit offset), so
        # ingest accepts them; the pre-fix bug lived entirely in the retention job.
        assert r.status_code == 200

    erased = run_retention()  # must not raise, even with org B's uncastable rows present
    assert erased == 1

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM event_payloads p JOIN events e ON e.seq = p.seq "
            "WHERE e.org_id=%s AND e.session_id='sa'",
            (org_a,),
        )
        assert cur.fetchone()[0] == 0  # org A's expired payload was erased
        cur.execute(
            "SELECT count(*) FROM event_payloads p JOIN events e ON e.seq = p.seq "
            "WHERE e.org_id=%s AND e.session_id='sb'",
            (org_b,),
        )
        assert cur.fetchone()[0] == 3  # org B's uncastable-ts payloads were left alone
