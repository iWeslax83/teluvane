from datetime import datetime, timedelta, timezone

from teluvane import anchor
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store


CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0",
                          min_session_age_minutes=30)


def _mk_org(plan="pro"):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, org_members, anchor_batches, session_anchors "
                    "RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id,plan) VALUES('org1','o','u',%s)",
                    (plan,))
        conn.commit()


def _age_session(session_id, minutes):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts=%s WHERE session_id=%s", (old, session_id))
        conn.commit()


def test_quiet_pro_session_is_pending():
    _mk_org("pro")
    s = Store()
    for i in range(2):
        s.append("org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=str(i)))
    _age_session("s1", 45)
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert len(leaves) == 1
    org_id, session_id, through_seq, chain_head = leaves[0]
    assert (org_id, session_id) == ("org1", "s1")
    assert through_seq == 2
    assert len(chain_head) == 64


def test_recent_session_is_not_pending():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s2", kind="llm_call", intent="x"))
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert leaves == []


def test_free_plan_session_is_not_pending():
    _mk_org("free")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s3", kind="llm_call", intent="x"))
    _age_session("s3", 45)
    assert anchor.pending_leaves(get_pool(), CFG) == []


def test_already_anchored_through_latest_seq_is_not_pending():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s4", kind="llm_call", intent="x"))
    _age_session("s4", 45)
    from teluvane import anchor_store
    bid = anchor_store.insert_batch(get_pool(), "0xr", 43113, 1)
    head = anchor.pending_leaves(get_pool(), CFG)[0][3]
    anchor_store.insert_session_anchor(get_pool(), "org1", "s4", 1, bid, head, [])
    assert anchor.pending_leaves(get_pool(), CFG) == []


def test_session_grown_past_its_anchor_is_pending_again():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s5", kind="llm_call", intent="x"))
    _age_session("s5", 45)
    from teluvane import anchor_store
    bid = anchor_store.insert_batch(get_pool(), "0xr2", 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "org1", "s5", 1, bid, "aa", [])
    s.append("org1", Event(agent_id="a", session_id="s5", kind="llm_call", intent="y"))
    _age_session("s5", 45)
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert len(leaves) == 1
    assert leaves[0][2] == 2  # through_seq advanced
