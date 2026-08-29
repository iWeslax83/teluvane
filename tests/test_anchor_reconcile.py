from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from teluvane import anchor, anchor_store
from teluvane.db import get_pool

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0",
                          confirmations=5, submit_timeout_minutes=30)


def _fresh():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        conn.commit()


def _submitted_batch(age_minutes=1):
    bid = anchor_store.insert_batch(get_pool(), f"0x{age_minutes:064x}", 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "o", "s", 1, bid, "aa", [])
    anchor_store.mark_submitted(get_pool(), bid, "0xtx")
    old = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE anchor_batches SET submitted_at=%s WHERE id=%s", (old, bid))
        conn.commit()
    return bid


def test_mined_with_enough_confirmations_marks_mined():
    _fresh()
    bid = _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 1, "gas_used": 90000,
                                    "effective_gas_price": 25_000_000_000}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=110), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "mined")[0]["id"] == bid


def test_mined_but_not_enough_confirmations_stays_submitted():
    _fresh()
    _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 1, "gas_used": 1,
                                    "effective_gas_price": 1}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=102), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "submitted")
    assert anchor_store.batches_by_status(get_pool(), "submitted")[0]["confirmations"] == 3


def test_reverted_receipt_marks_failed_and_clears_anchors():
    _fresh()
    _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 0, "gas_used": 1,
                                    "effective_gas_price": 1}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=200), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "failed")
    assert anchor_store.latest_anchor(get_pool(), "o", "s") is None


def test_timed_out_unmined_batch_marks_failed():
    _fresh()
    _submitted_batch(age_minutes=45)
    with patch.object(anchor.anchor_chain, "receipt", return_value=None), \
         patch.object(anchor.anchor_chain, "block_number", return_value=200), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "failed")


def test_low_balance_logs_warning(caplog):
    _fresh()
    with patch.object(anchor.anchor_chain, "balance_avax", return_value=0.001):
        with caplog.at_level("WARNING"):
            anchor.reconcile_pending(get_pool(), CFG)
    assert any("balance" in r.message.lower() for r in caplog.records)
