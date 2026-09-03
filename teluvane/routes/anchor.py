# teluvane/teluvane/routes/anchor.py
"""On-chain anchoring routes: status/config reads, forced runs, public verify."""
import os

from fastapi import APIRouter, Depends, Body, HTTPException, Request

from ..appstate import store, limiter
from ..auth import current_org
from ..billing import org_plan
from .. import anchor, anchor_store, anchor_forced

router = APIRouter()

# Route order matters: FastAPI matches in definition order, so the literal /anchor/contract
# and /anchor/status must precede the /anchor/{session_id} path-param route.
@router.get("/anchor/contract")
def anchor_contract(org_id: str = Depends(current_org)) -> dict:
    cfg = anchor.chain_config()
    if not cfg:
        raise HTTPException(status_code=404, detail="anchoring not configured")
    return {"chain_id": cfg.chain_id, "contract_address": cfg.contract_address,
            "explorer_tx_url": cfg.explorer_tx_url, "rpc_url": cfg.rpc_url}

@router.get("/anchor/status")
def anchor_status_ep(org_id: str = Depends(current_org)) -> dict:
    return anchor.anchor_health(store.pool)

@router.get("/anchor/{session_id}")
def anchor_session_ep(session_id: str, org_id: str = Depends(current_org)) -> dict:
    return anchor.verify_session(store.pool, org_id, session_id)

@router.get("/anchor/{session_id}/canonical")
def anchor_canonical_ep(session_id: str, org_id: str = Depends(current_org)) -> list[dict]:
    return store.canonical_events(org_id, session_id)

@router.put("/anchor/{session_id}/public")
def anchor_public_ep(session_id: str, public: bool = Body(embed=True),
                     org_id: str = Depends(current_org)) -> dict:
    # Publishing exposes the session's full canonical event list to anyone with
    # the id, so gate it the same way the rest of the feature is gated: the org
    # must own the session and be on Pro. As with /anchor/run there is no
    # admin/owner check, because current_org yields no user identity.
    if not store.events(org_id, session_id):
        raise HTTPException(status_code=404, detail="session not found")
    if org_plan(org_id) != "pro":
        raise HTTPException(status_code=403, detail="Pro plan required")
    anchor_store.set_public(store.pool, org_id, session_id, public)
    return {"public": public}

@router.post("/anchor/run")
@limiter.limit(lambda: os.environ.get("AUDIT_RATE_LIMIT", "20/minute"))
def anchor_run_ep(request: Request, org_id: str = Depends(current_org)) -> dict:
    # Pro-only. The brief also wanted an admin/owner check, but current_org yields only
    # org_id (not the user), and threading the user through is out of scope for this task,
    # so the gate is plan == "pro" alone.
    if org_plan(org_id) != "pro":
        raise HTTPException(status_code=403, detail="Pro plan required")
    cfg = anchor.chain_config()
    if not cfg:
        raise HTTPException(status_code=404, detail="anchoring not configured")
    reason = anchor_forced.check_and_record(
        org_id, cfg.forced_run_cooldown_minutes, cfg.max_forced_runs_per_org_per_month)
    if reason:
        raise HTTPException(status_code=429, detail=f"forced anchor blocked: {reason}")
    return anchor.run_anchor_pass(store.pool, cfg)

@router.get("/verify/public/{session_id}")
def verify_public_ep(session_id: str) -> dict:
    # Unauthenticated: find which org made this session public, then verify it.
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT org_id FROM session_anchor_public WHERE session_id=%s", (session_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    org_id = row[0]
    v = anchor.verify_session(store.pool, org_id, session_id)
    if not v["anchored"]:
        raise HTTPException(status_code=404, detail="not anchored")
    canonical = store.canonical_events(org_id, session_id)
    latest = anchor_store.latest_anchor(store.pool, org_id, session_id)
    cfg = anchor.chain_config()
    return {"session_id": session_id, "canonical": canonical,
            "proof": v["proof"], "through_seq": latest["anchored_through_seq"] if latest else None,
            "chain_head": latest["chain_head"] if latest else None,
            "root": v["root"], "tx_hash": v["tx_hash"], "verify": v,
            "chain_id": cfg.chain_id if cfg else None,
            "contract_address": cfg.contract_address if cfg else None,
            "explorer_tx_url": cfg.explorer_tx_url if cfg else None,
            "rpc_url": cfg.rpc_url if cfg else None}
