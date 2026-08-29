from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from teluvane import anchor, anchor_store
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")


def _seed_pro_session(session_id, n=1):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, org_members, anchor_batches, session_anchors "
                    "RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id,plan) VALUES('org1','o','u','pro')")
        conn.commit()
    s = Store()
    for i in range(n):
        s.append("org1", Event(agent_id="a", session_id=session_id, kind="llm_call", intent=str(i)))
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts=%s", (old,))
        conn.commit()


def test_run_anchor_pass_persists_then_submits(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s1", 2)
    with patch.object(anchor.anchor_chain, "submit_batch", return_value="0xtx") as sub:
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["anchored"] == 1
    assert res["tx_hash"] == "0xtx"
    # membership existed before submit was called
    sub.assert_called_once()
    row = anchor_store.latest_anchor(get_pool(), "org1", "s1")
    assert row["status"] == "submitted"
    assert row["anchored_through_seq"] == 2
    assert row["proof"] == []  # single leaf


def test_empty_pending_is_a_noop(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        conn.commit()
    res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res == {"anchored": 0, "root": None, "tx_hash": None, "skipped": "nothing-pending"}


def test_submit_failure_leaves_batch_pending_with_membership(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s2", 1)
    with patch.object(anchor.anchor_chain, "submit_batch", side_effect=Exception("rpc down")):
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["skipped"] == "submit-failed"
    row = anchor_store.latest_anchor(get_pool(), "org1", "s2")
    assert row["status"] == "pending"          # membership persisted, tx not sent
    assert row["tx_hash"] is None
