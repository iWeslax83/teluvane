from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from teluvane import anchor, anchor_store
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")


def _seed_pro_session(session_id, n=1):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, orgs, org_members, anchor_batches, session_anchors "
            "RESTART IDENTITY CASCADE"
        )
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


def test_failed_batch_does_not_wedge_a_reanchor_of_the_same_root(monkeypatch):
    """A quiet session's leaf never changes, so re-anchoring after mark_failed
    rebuilds the identical root. That must not raise a UniqueViolation."""
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s3", 2)
    with patch.object(anchor.anchor_chain, "submit_batch", return_value="0xtx1"):
        first = anchor.run_anchor_pass(get_pool(), CFG)
    assert first["anchored"] == 1
    bid = anchor_store.latest_anchor(get_pool(), "org1", "s3")["batch_id"]

    # tx timed out unmined: membership is dropped and the batch is failed
    anchor_store.mark_failed(get_pool(), bid)
    assert anchor_store.latest_anchor(get_pool(), "org1", "s3") is None

    with patch.object(anchor.anchor_chain, "submit_batch", return_value="0xtx2"):
        second = anchor.run_anchor_pass(get_pool(), CFG)
    assert second["skipped"] is None
    assert second["anchored"] == 1
    assert second["root"] == first["root"]
    row = anchor_store.latest_anchor(get_pool(), "org1", "s3")
    assert row is not None
    assert row["status"] == "submitted"
    assert row["batch_id"] == bid


def test_reanchor_of_a_mined_root_relinks_without_resubmitting(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s4", 1)
    with patch.object(anchor.anchor_chain, "submit_batch", return_value="0xtx1"):
        anchor.run_anchor_pass(get_pool(), CFG)
    bid = anchor_store.latest_anchor(get_pool(), "org1", "s4")["batch_id"]
    anchor_store.mark_mined(get_pool(), bid, 42, 90000, 1, 6)
    # drop membership only, leaving the mined batch in place
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM session_anchors WHERE batch_id=%s", (bid,))
        conn.commit()

    with patch.object(anchor.anchor_chain, "submit_batch") as sub:
        res = anchor.run_anchor_pass(get_pool(), CFG)
    sub.assert_not_called()
    assert res["anchored"] == 1
    assert anchor_store.latest_anchor(get_pool(), "org1", "s4")["status"] == "mined"


def test_pass_error_is_swallowed_and_reported(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s5", 1)
    with patch.object(
        anchor.anchor_store, "insert_batch_with_anchors", side_effect=Exception("db down")
    ):
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["skipped"] == "pass-error"


def test_submit_failure_leaves_batch_pending_with_membership(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s2", 1)
    with patch.object(anchor.anchor_chain, "submit_batch", side_effect=Exception("rpc down")):
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["skipped"] == "submit-failed"
    row = anchor_store.latest_anchor(get_pool(), "org1", "s2")
    assert row["status"] == "pending"  # membership persisted, tx not sent
    assert row["tx_hash"] is None
