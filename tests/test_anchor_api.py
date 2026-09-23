from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from teluvane import anchor, anchor_store, merkle
from teluvane.db import get_pool
from teluvane.ingest import app
from teluvane.orgs import create_org
from teluvane.schema import Event
from teluvane.store import Store

client = TestClient(app)

CFG = anchor.AnchorConfig(
    rpc_url="http://rpc",
    contract_address="0xC0FFEE",
    signer_key="0x0",
    explorer_tx_url="https://x/tx/",
)


@pytest.fixture(autouse=True)
def _clean_db():
    from teluvane.migrate import apply_migrations

    apply_migrations()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, org_members, orgs, "
            "anchor_batches, session_anchors, session_anchor_public, "
            "anchor_forced_runs RESTART IDENTITY CASCADE"
        )
        conn.commit()


def _auth(make_jwt, *, pro=False):
    org_id = create_org("Acme", "u1")
    if pro:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org_id,))
            conn.commit()
    return org_id, {"Authorization": f"Bearer {make_jwt('u1')}"}


def _seed_anchored_session(org_id, session_id="s1"):
    s = Store()
    for i in range(3):
        s.append(org_id, Event(agent_id="a", session_id=session_id, kind="llm_call", intent=str(i)))
    head = s.events(org_id, session_id)[-1].hash
    root, proofs = merkle.build_tree([(org_id, session_id, head)])
    bid = anchor_store.insert_batch(get_pool(), root, 43113, 1)
    anchor_store.insert_session_anchor(
        get_pool(), org_id, session_id, 3, bid, head, proofs[(org_id, session_id)]
    )
    anchor_store.mark_submitted(get_pool(), bid, "0xtx")
    anchor_store.mark_mined(get_pool(), bid, 42, 90000, 1, 6)
    return root, head


def test_anchor_contract_route(make_jwt):
    _, headers = _auth(make_jwt)
    with patch.object(anchor, "chain_config", return_value=CFG):
        r = client.get("/anchor/contract", headers=headers)
    assert r.status_code == 200
    assert r.json()["contract_address"] == "0xC0FFEE"
    assert r.json()["chain_id"] == 43113


def test_anchor_contract_404_when_unconfigured(make_jwt):
    _, headers = _auth(make_jwt)
    with patch.object(anchor, "chain_config", return_value=None):
        r = client.get("/anchor/contract", headers=headers)
    assert r.status_code == 404


def test_anchor_status_route(make_jwt):
    _, headers = _auth(make_jwt)
    with patch.object(anchor, "chain_config", return_value=None):
        r = client.get("/anchor/status", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


def test_anchor_session_and_canonical_routes(make_jwt):
    org_id, headers = _auth(make_jwt)
    _seed_anchored_session(org_id, "s1")
    with (
        patch.object(anchor, "chain_config", return_value=CFG),
        patch.object(anchor.anchor_chain, "read_anchored_at", return_value=1_700_000_000),
    ):
        r = client.get("/anchor/s1", headers=headers)
    assert r.status_code == 200
    assert r.json()["anchored"] is True

    rc = client.get("/anchor/s1/canonical", headers=headers)
    assert rc.status_code == 200
    assert isinstance(rc.json(), list) and len(rc.json()) == 3


def test_public_verify_404_when_not_opted_in(make_jwt):
    r = client.get("/verify/public/never-made-public")
    assert r.status_code == 404


def test_put_public_requires_pro(make_jwt):
    org_id, headers = _auth(make_jwt, pro=False)
    _seed_anchored_session(org_id, "s1")
    r = client.put("/anchor/s1/public", headers=headers, json={"public": True})
    assert r.status_code == 403
    assert anchor_store.is_public(get_pool(), org_id, "s1") is False


def test_put_public_404_when_the_org_has_no_such_session(make_jwt):
    org_id, headers = _auth(make_jwt, pro=True)
    r = client.put("/anchor/no-such-session/public", headers=headers, json={"public": True})
    assert r.status_code == 404
    assert anchor_store.is_public(get_pool(), org_id, "no-such-session") is False


def test_put_public_toggles_and_public_verify_returns_bundle(make_jwt):
    org_id, headers = _auth(make_jwt, pro=True)
    _seed_anchored_session(org_id, "s1")

    rp = client.put("/anchor/s1/public", headers=headers, json={"public": True})
    assert rp.status_code == 200 and rp.json() == {"public": True}

    with (
        patch.object(anchor, "chain_config", return_value=CFG),
        patch.object(anchor.anchor_chain, "read_anchored_at", return_value=1_700_000_000),
    ):
        r = client.get("/verify/public/s1")
    assert r.status_code == 200
    body = r.json()
    assert body["contract_address"] == "0xC0FFEE"
    assert body["chain_id"] == 43113
    assert isinstance(body["canonical"], list)
    assert "proof" in body
    assert body["session_id"] == "s1"

    # opt back out -> 404
    client.put("/anchor/s1/public", headers=headers, json={"public": False})
    r2 = client.get("/verify/public/s1")
    assert r2.status_code == 404


def test_forced_run_requires_pro(make_jwt):
    _, headers = _auth(make_jwt, pro=False)
    with patch.object(anchor, "chain_config", return_value=CFG):
        r = client.post("/anchor/run", headers=headers)
    assert r.status_code == 403


def test_forced_run_cooldown(make_jwt):
    _, headers = _auth(make_jwt, pro=True)
    with (
        patch.object(anchor, "chain_config", return_value=CFG),
        patch.object(
            anchor,
            "run_anchor_pass",
            return_value={
                "anchored": 0,
                "root": None,
                "tx_hash": None,
                "skipped": "nothing-pending",
            },
        ),
    ):
        r1 = client.post("/anchor/run", headers=headers)
        r2 = client.post("/anchor/run", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 429
    assert "forced anchor blocked" in r2.json()["detail"]


def test_forced_run_404_when_unconfigured(make_jwt):
    _, headers = _auth(make_jwt, pro=True)
    with patch.object(anchor, "chain_config", return_value=None):
        r = client.post("/anchor/run", headers=headers)
    assert r.status_code == 404
