from teluvane import anchor_store
from teluvane.db import get_pool


def _truncate():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE anchor_batches, session_anchors, session_anchor_public RESTART IDENTITY CASCADE"
        )
        conn.commit()


def test_batch_lifecycle_and_anchor_lookup():
    _truncate()
    pool = get_pool()
    bid = anchor_store.insert_batch(pool, "0xabc", 43113, 2)
    assert isinstance(bid, int)
    anchor_store.insert_session_anchor(pool, "org1", "sess1", 5, bid, "deadbeef", ["0x11"])
    anchor_store.insert_session_anchor(pool, "org2", "sess9", 3, bid, "cafe", [])

    assert anchor_store.max_anchored_seq(pool, "org1", "sess1") == 5
    assert anchor_store.max_anchored_seq(pool, "org1", "missing") == 0
    latest = anchor_store.latest_anchor(pool, "org1", "sess1")
    assert latest["chain_head"] == "deadbeef"
    assert latest["proof"] == ["0x11"]
    assert latest["status"] == "pending"

    anchor_store.mark_submitted(pool, bid, "0xtx")
    anchor_store.mark_mined(pool, bid, 100, 21000, 1234, 6)
    latest = anchor_store.latest_anchor(pool, "org1", "sess1")
    assert latest["status"] == "mined"
    assert latest["tx_hash"] == "0xtx"
    assert latest["block_number"] == 100


def test_mark_failed_removes_session_anchors():
    _truncate()
    pool = get_pool()
    bid = anchor_store.insert_batch(pool, "0xdef", 43113, 1)
    anchor_store.insert_session_anchor(pool, "org1", "sess1", 5, bid, "aa", [])
    anchor_store.mark_failed(pool, bid)
    assert anchor_store.latest_anchor(pool, "org1", "sess1") is None
    assert anchor_store.batches_by_status(pool, "failed")[0]["root"] == "0xdef"


def test_public_toggle():
    _truncate()
    pool = get_pool()
    assert anchor_store.is_public(pool, "org1", "sess1") is False
    anchor_store.set_public(pool, "org1", "sess1", True)
    assert anchor_store.is_public(pool, "org1", "sess1") is True
    anchor_store.set_public(pool, "org1", "sess1", False)
    assert anchor_store.is_public(pool, "org1", "sess1") is False
