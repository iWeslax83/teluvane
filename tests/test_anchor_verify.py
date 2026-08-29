from unittest.mock import patch

from teluvane import anchor, anchor_store, merkle
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")


def _seed():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        conn.commit()
    s = Store()
    for i in range(3):
        s.append("org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=str(i)))
    head = s.events("org1", "s1")[-1].hash
    root, proofs = merkle.build_tree([("org1", "s1", head)])
    bid = anchor_store.insert_batch(get_pool(), root, 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "org1", "s1", 3, bid, head, proofs[("org1", "s1")])
    anchor_store.mark_submitted(get_pool(), bid, "0xtx")
    anchor_store.mark_mined(get_pool(), bid, 42, 90000, 1, 6)
    return root, head


def test_verify_session_ok_when_root_on_chain():
    root, head = _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", return_value=1_700_000_000):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["anchored"] and res["head_matches"] and res["proof_ok"]
    assert res["status"] == "verified"
    assert res["onchain_ts"] == 1_700_000_000
    assert res["org_id"] == "org1"
    assert res["proof"] == []
    assert res["root"] == root


def test_verify_session_mismatch_when_root_absent_on_chain():
    _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", return_value=0):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["status"] == "mismatch"
    assert res["org_id"] == "org1"
    assert res["proof"] == []


def test_verify_session_rpc_error_is_reported_not_raised():
    _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", side_effect=Exception("rpc")):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["rpc_ok"] is False and res["status"] == "rpc-unreachable"
    assert res["org_id"] == "org1"
    assert res["proof"] == []


def test_verify_session_not_anchored():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        conn.commit()
    Store().append("org1", Event(agent_id="a", session_id="s9", kind="llm_call", intent="x"))
    res = anchor.verify_session(get_pool(), "org1", "s9", cfg=CFG)
    assert res["anchored"] is False and res["status"] == "not-anchored"
    assert res["org_id"] == "org1"


def test_anchor_health_disabled_without_config():
    with patch.object(anchor, "chain_config", return_value=None):
        h = anchor.anchor_health(get_pool())
    assert h["enabled"] is False
