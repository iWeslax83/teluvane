"""On-chain anchoring of session integrity chains to Avalanche Fuji.

Inert unless the ANCHOR_* env vars are set: chain_config() returns None and every
entry point is a no-op. Never raises into the API request path; RPC and wallet
failures degrade to "not yet anchored" plus a warning log.
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import anchor_store
from .billing import org_plan

log = logging.getLogger("teluvane.anchor")


@dataclass
class AnchorConfig:
    rpc_url: str
    contract_address: str
    signer_key: str
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
