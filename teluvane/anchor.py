"""On-chain anchoring of session integrity chains to Avalanche Fuji.

Inert unless the ANCHOR_* env vars are set: chain_config() returns None and every
entry point is a no-op. Never raises into the API request path; RPC and wallet
failures degrade to "not yet anchored" plus a warning log.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import anchor_chain, anchor_store, merkle
from .billing import org_plan

log = logging.getLogger("teluvane.anchor")


@dataclass
class AnchorConfig:
    rpc_url: str
    contract_address: str
    # repr=False so an accidental log.info("%s", cfg) can never print the hot
    # wallet's private key.
    signer_key: str = field(repr=False)
    chain_id: int = 43113
    min_session_age_minutes: int = 30
    batch_interval_minutes: int = 10
    confirmations: int = 5
    submit_timeout_minutes: int = 30
    low_balance_alert_avax: float = 0.05
    max_forced_runs_per_org_per_month: int = 20
    forced_run_cooldown_minutes: int = 5
    explorer_tx_url: str = "https://testnet.snowtrace.io/tx/"


def chain_config() -> AnchorConfig | None:
    rpc = os.environ.get("ANCHOR_RPC_URL")
    addr = os.environ.get("ANCHOR_CONTRACT_ADDRESS")
    key = os.environ.get("ANCHOR_SIGNER_PRIVATE_KEY")
    if not (rpc and addr and key):
        return None

    def _int(name, default):
        try:
            return int(os.environ.get(name, default))
        except ValueError:
            return default

    def _float(name, default):
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return default

    return AnchorConfig(
        rpc_url=rpc, contract_address=addr, signer_key=key,
        chain_id=_int("ANCHOR_CHAIN_ID", 43113),
        min_session_age_minutes=_int("ANCHOR_MIN_SESSION_AGE_MINUTES", 30),
        batch_interval_minutes=_int("ANCHOR_BATCH_INTERVAL_MINUTES", 10),
        confirmations=_int("ANCHOR_CONFIRMATIONS", 5),
        submit_timeout_minutes=_int("ANCHOR_SUBMIT_TIMEOUT_MINUTES", 30),
        low_balance_alert_avax=_float("ANCHOR_LOW_BALANCE_ALERT_AVAX", 0.05),
        max_forced_runs_per_org_per_month=_int(
            "ANCHOR_MAX_FORCED_RUNS_PER_ORG_PER_MONTH", 20),
        forced_run_cooldown_minutes=_int("ANCHOR_FORCED_RUN_COOLDOWN_MINUTES", 5),
        explorer_tx_url=os.environ.get("ANCHOR_EXPLORER_TX_URL",
                                      "https://testnet.snowtrace.io/tx/"),
    )


_PENDING_SQL = """
SELECT e.org_id, e.session_id, MAX(e.seq) AS through_seq
FROM events e
GROUP BY e.org_id, e.session_id
HAVING MAX(e.ts) < %s
"""


def pending_leaves(pool, cfg: AnchorConfig):
    """Pro-plan sessions quiet for >= cfg.min_session_age_minutes that are not yet
    anchored through their latest seq. Returns (org_id, session_id, through_seq,
    chain_head) tuples, where chain_head is the latest event hash."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=cfg.min_session_age_minutes)).isoformat()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(_PENDING_SQL, (cutoff,))
        candidates = cur.fetchall()

    leaves = []
    for org_id, session_id, through_seq in candidates:
        if org_plan(org_id) != "pro":
            continue
        if anchor_store.max_anchored_seq(pool, org_id, session_id) >= through_seq:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT hash FROM events WHERE org_id=%s AND session_id=%s "
                        "ORDER BY seq DESC LIMIT 1", (org_id, session_id))
            chain_head = cur.fetchone()[0]
        leaves.append((org_id, session_id, int(through_seq), chain_head))
    return leaves


ADVISORY_LOCK_KEY = 0x54454C56  # "TELV"; scopes run_anchor_pass across web instances


def run_anchor_pass(pool, cfg: AnchorConfig) -> dict:
    """Collect pending leaves, build a Merkle tree, persist the batch and every
    per-session proof to Postgres, then submit the root on-chain. Persist happens
    strictly before submit so a crash in between leaves a pending batch that
    Task 7's reconcile can pick up. A Postgres advisory lock keeps two web
    instances from running a pass at once."""
    empty = {"anchored": 0, "root": None, "tx_hash": None, "skipped": None}
    with pool.connection() as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
            got = cur.fetchone()[0]
        lock_conn.commit()
        if not got:
            return {**empty, "skipped": "locked"}
        try:
            leaves = pending_leaves(pool, cfg)
            if not leaves:
                return {**empty, "skipped": "nothing-pending"}
            root, proofs = merkle.build_tree([(o, s, h) for o, s, _seq, h in leaves])
            batch_id = anchor_store.insert_batch_with_anchors(
                pool, root, cfg.chain_id,
                [(o, s, seq, h, proofs[(o, s)]) for o, s, seq, h in leaves])

            # A quiet session's leaf never changes, so re-anchoring after a failed
            # batch rebuilds the identical root and lands on the existing row.
            status = anchor_store.batch_status(pool, batch_id)
            if status == "mined":
                log.info("anchor root %s already mined; re-linked %d sessions",
                         root, len(leaves))
                return {"anchored": len(leaves), "root": root, "tx_hash": None,
                        "skipped": None}
            if status == "failed":
                log.info("anchor root %s was failed; resetting batch %s to pending",
                         root, batch_id)
                anchor_store.reset_batch_pending(pool, batch_id)

            try:
                tx_hash = anchor_chain.submit_batch(cfg, root, len(leaves))
            except Exception:
                log.exception("anchor submit failed; batch %s stays pending", batch_id)
                return {"anchored": 0, "root": root, "tx_hash": None,
                        "skipped": "submit-failed"}
            anchor_store.mark_submitted(pool, batch_id, tx_hash)
            log.info("anchor batch submitted root=%s tx=%s sessions=%d",
                     root, tx_hash, len(leaves))
            return {"anchored": len(leaves), "root": root, "tx_hash": tx_hash,
                    "skipped": None}
        except Exception:
            # A DB error here must not propagate out through run_anchor_cycle and
            # kill the scheduler tick for every other job.
            log.exception("anchor pass failed")
            return {**empty, "skipped": "pass-error"}
        finally:
            try:
                with lock_conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
                lock_conn.commit()
            except Exception:
                log.exception("anchor advisory unlock failed")


def reconcile_pending(pool, cfg: AnchorConfig) -> None:
    """Poll submitted batches: mark them mined once confirmations reach
    cfg.confirmations, mark them failed on revert or submit timeout (dropping
    their session_anchors so those sessions re-anchor), and re-submit pending
    batches whose membership persisted but whose submit never landed. Warn when
    the signer balance falls below cfg.low_balance_alert_avax."""
    open_batches = anchor_store.batches_by_status(pool, "pending", "submitted")
    if not open_batches:
        # Nothing to reconcile: skip the balance + block_number RPC round trips
        # that would otherwise run on every idle tick.
        return

    try:
        bal = anchor_chain.balance_avax(cfg)
        if bal < cfg.low_balance_alert_avax:
            log.warning("anchor signer balance low: %.4f AVAX (threshold %.4f)",
                        bal, cfg.low_balance_alert_avax)
    except Exception:
        log.exception("anchor balance check failed")

    try:
        head = anchor_chain.block_number(cfg)
    except Exception:
        log.exception("anchor block_number failed; skipping reconcile")
        return

    for b in open_batches:
        if b["status"] == "pending" and not b["tx_hash"]:
            # membership persisted but submit never happened; retry it (idempotent on-chain)
            try:
                txh = anchor_chain.submit_batch(cfg, b["root"], b["session_count"])
                anchor_store.mark_submitted(pool, b["id"], txh)
            except Exception:
                log.exception("anchor resubmit failed for batch %s", b["id"])
            continue

        try:
            r = anchor_chain.receipt(cfg, b["tx_hash"])
        except Exception:
            log.exception("anchor receipt fetch failed for batch %s", b["id"])
            continue

        if r is None:
            submitted_at = b["submitted_at"]
            if submitted_at and submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - submitted_at).total_seconds() / 60 \
                if submitted_at else 0
            if age_min > cfg.submit_timeout_minutes:
                log.warning("anchor batch %s timed out unmined; marking failed", b["id"])
                anchor_store.mark_failed(pool, b["id"])
            continue

        if r["status"] == 0:
            log.warning("anchor batch %s reverted on chain; marking failed", b["id"])
            anchor_store.mark_failed(pool, b["id"])
            continue

        confirmations = max(0, head - r["block_number"] + 1)
        if confirmations >= cfg.confirmations:
            fee = r["gas_used"] * r["effective_gas_price"]
            anchor_store.mark_mined(pool, b["id"], r["block_number"], r["gas_used"],
                                    fee, confirmations)
            log.info("anchor batch %s mined root=%s block=%d gas=%d",
                     b["id"], b["root"], r["block_number"], r["gas_used"])
        else:
            anchor_store.update_confirmations(pool, b["id"], r["block_number"], confirmations)


def verify_session(pool, org_id: str, session_id: str, through_seq: int | None = None,
                   cfg: AnchorConfig | None = None) -> dict:
    """Recompute a session's anchored chain head and Merkle root from stored data,
    read anchoredAt(root) from the chain, and classify the result. Never raises on
    RPC failure: it degrades to status "rpc-unreachable". `org_id` and `proof` are
    echoed so a browser panel can recompute the root without trusting this server.

    status is one of: not-anchored, verified, mismatch, pending, rpc-unreachable,
    no-config.
    """
    cfg = cfg if cfg is not None else chain_config()
    from .store import Store
    store = Store(pool)
    events = store.events(org_id, session_id)
    total_seq = events[-1].seq if events else 0

    row = (anchor_store.anchor_for_seq(pool, org_id, session_id, through_seq)
           if through_seq else anchor_store.latest_anchor(pool, org_id, session_id))

    base = {
        "anchored": False, "org_id": org_id, "proof": None,
        "through_seq": None, "total_seq": total_seq, "root": None,
        "tx_hash": None, "block_number": None, "confirmations": 0,
        "mined_at": None, "onchain_ts": None, "head_stored": None,
        "head_recomputed": None, "head_matches": False, "proof_ok": False,
        "rpc_ok": True, "status": "not-anchored",
        "is_public": anchor_store.is_public(pool, org_id, session_id),
    }
    if not row:
        return base

    proof = list(row["proof"] or [])
    canon = store.canonical_events(org_id, session_id)
    upto = [c for c in canon if c["seq"] <= row["anchored_through_seq"]]
    head_recomputed = upto[-1]["hash"] if upto else None
    head_matches = head_recomputed == row["chain_head"]

    implied_root = merkle.root_from_proof(org_id, session_id, row["chain_head"], proof)

    out = {
        **base,
        "anchored": True,
        "proof": proof,
        "through_seq": row["anchored_through_seq"],
        "root": implied_root,
        "tx_hash": row["tx_hash"],
        "block_number": row["block_number"],
        "confirmations": row["confirmations"] or 0,
        "mined_at": row["mined_at"].isoformat() if row["mined_at"] else None,
        "head_stored": row["chain_head"],
        "head_recomputed": head_recomputed,
        "head_matches": head_matches,
        # The proof is only "ok" if walking it from this session's leaf lands on
        # the root the batch actually recorded.
        "proof_ok": implied_root == row.get("batch_root"),
    }

    if not cfg:
        out["status"] = "no-config"
        return out

    try:
        ts = anchor_chain.read_anchored_at(cfg, implied_root)
    except Exception:
        log.exception("anchor verify RPC read failed")
        out["rpc_ok"] = False
        out["status"] = "rpc-unreachable"
        return out

    out["onchain_ts"] = ts or None
    if not head_matches:
        # A head that does not match what was anchored is a tamper hit, not a
        # pending state, even while the batch is still in flight.
        out["status"] = "mismatch"
    elif ts:
        out["status"] = "verified"
    elif row["status"] in ("pending", "submitted"):
        out["status"] = "pending"
    else:
        out["status"] = "mismatch"
    return out


def anchor_health(pool) -> dict:
    """Operator snapshot: signer address/balance, pending batch count, last mined
    batch. RPC failure degrades rpc_ok to False rather than raising."""
    cfg = chain_config()
    if not cfg:
        return {"enabled": False}

    h = {
        "enabled": True, "chain_id": cfg.chain_id, "rpc_ok": True,
        "signer_address": None, "signer_balance_avax": None, "low_balance": False,
        "pending_batches": len(anchor_store.batches_by_status(pool, "pending", "submitted")),
        "last_batch_at": None, "last_batch_tx": None,
    }
    try:
        h["signer_address"] = anchor_chain.signer_address(cfg)
        bal = anchor_chain.balance_avax(cfg)
        h["signer_balance_avax"] = round(bal, 5)
        h["low_balance"] = bal < cfg.low_balance_alert_avax
    except Exception:
        log.exception("anchor health RPC check failed")
        h["rpc_ok"] = False

    mined = anchor_store.batches_by_status(pool, "mined")
    if mined:
        last = mined[-1]
        h["last_batch_at"] = last["mined_at"].isoformat() if last["mined_at"] else None
        h["last_batch_tx"] = last["tx_hash"]
    return h
