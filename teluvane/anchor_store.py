"""Postgres helpers for the on-chain anchoring tables. These tables are global
(anchor_batches spans orgs); session_anchors is still org-scoped by column.
Kept out of Store because Store._assert_scoped rejects any SQL without an
org_id predicate, and anchor_batches has none."""
import json
from psycopg.rows import dict_row


def insert_batch(pool, root: str, chain_id: int, session_count: int) -> int:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO anchor_batches(root, chain_id, session_count) "
            "VALUES(%s,%s,%s) RETURNING id", (root, chain_id, session_count))
        bid = cur.fetchone()[0]
        conn.commit()
        return bid


def insert_session_anchor(pool, org_id: str, session_id: str, through_seq: int,
                          batch_id: int, chain_head: str, proof: list) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO session_anchors"
            "(org_id, session_id, anchored_through_seq, batch_id, chain_head, proof) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (org_id, session_id, through_seq, batch_id, chain_head, json.dumps(proof)))
        conn.commit()


def mark_submitted(pool, batch_id: int, tx_hash: str) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE anchor_batches SET status='submitted', tx_hash=%s, submitted_at=now() "
            "WHERE id=%s", (tx_hash, batch_id))
        conn.commit()


def mark_mined(pool, batch_id: int, block_number: int, gas_used: int,
               fee_wei: int, confirmations: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE anchor_batches SET status='mined', block_number=%s, gas_used=%s, "
            "fee_wei=%s, confirmations=%s, mined_at=now() WHERE id=%s",
            (block_number, gas_used, fee_wei, confirmations, batch_id))
        conn.commit()


def mark_failed(pool, batch_id: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM session_anchors WHERE batch_id=%s", (batch_id,))
        cur.execute("UPDATE anchor_batches SET status='failed' WHERE id=%s", (batch_id,))
        conn.commit()


def update_confirmations(pool, batch_id: int, block_number: int, confirmations: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE anchor_batches SET block_number=%s, confirmations=%s WHERE id=%s",
                    (block_number, confirmations, batch_id))
        conn.commit()


def batches_by_status(pool, *statuses: str) -> list:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM anchor_batches WHERE status = ANY(%s) ORDER BY id",
                    (list(statuses),))
        return cur.fetchall()


def _anchor_row(pool, sql: str, params: tuple) -> dict | None:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row) if row else None


_JOIN = ("SELECT sa.*, b.status, b.tx_hash, b.block_number, b.confirmations, "
         "b.mined_at, b.chain_id FROM session_anchors sa "
         "JOIN anchor_batches b ON b.id = sa.batch_id "
         "WHERE sa.org_id=%s AND sa.session_id=%s")


def latest_anchor(pool, org_id: str, session_id: str) -> dict | None:
    return _anchor_row(pool, _JOIN + " ORDER BY sa.anchored_through_seq DESC LIMIT 1",
                       (org_id, session_id))


def anchor_for_seq(pool, org_id: str, session_id: str, through_seq: int) -> dict | None:
    return _anchor_row(pool, _JOIN + " AND sa.anchored_through_seq=%s",
                       (org_id, session_id, through_seq))


def max_anchored_seq(pool, org_id: str, session_id: str) -> int:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(anchored_through_seq), 0) FROM session_anchors "
                    "WHERE org_id=%s AND session_id=%s", (org_id, session_id))
        return int(cur.fetchone()[0])


def set_public(pool, org_id: str, session_id: str, public: bool) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        if public:
            cur.execute("INSERT INTO session_anchor_public(org_id, session_id) VALUES(%s,%s) "
                        "ON CONFLICT DO NOTHING", (org_id, session_id))
        else:
            cur.execute("DELETE FROM session_anchor_public WHERE org_id=%s AND session_id=%s",
                        (org_id, session_id))
        conn.commit()


def is_public(pool, org_id: str, session_id: str) -> bool:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM session_anchor_public WHERE org_id=%s AND session_id=%s",
                    (org_id, session_id))
        return cur.fetchone() is not None
