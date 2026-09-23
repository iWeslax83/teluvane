# teluvane/teluvane/routes/evidence.py
"""HTML (all plans) and PDF (Starter/Pro) evidence pack export."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse

from .. import anchor
from ..appstate import base_pack_for_org, store
from ..auth import current_org
from ..billing import org_plan
from ..evidence import build_evidence_pack, build_evidence_pdf

router = APIRouter()


def _evidence_anchor(org_id: str, session_id: str) -> dict | None:
    # A broken RPC or missing anchor config must never break evidence export.
    try:
        a = anchor.verify_session(store.pool, org_id, session_id)
        cfg = anchor.chain_config()
        if cfg is not None:
            a = {**a, "explorer_tx_url": cfg.explorer_tx_url}
        return a
    except Exception:
        logging.exception("evidence anchor lookup failed for %s", session_id)
        return None


@router.get("/evidence/{session_id}", response_class=HTMLResponse)
def evidence(session_id: str, org_id: str = Depends(current_org)) -> str:
    events = store.events(org_id, session_id)
    verdicts = store.verdicts(org_id, session_id)
    anchor_dict = _evidence_anchor(org_id, session_id)
    canon = store.canonical_events(org_id, session_id) if anchor_dict else None
    pack = build_evidence_pack(
        session_id,
        events,
        verdicts,
        framework=base_pack_for_org(org_id).framework,
        chain_intact=store.verify_chain(org_id, session_id),
        anchor=anchor_dict,
        canonical=canon,
    )
    return pack["html"]


@router.get("/evidence/{session_id}/pdf")
def evidence_pdf(session_id: str, org_id: str = Depends(current_org)) -> Response:
    # PDF export is a Starter/Pro perk (per the pricing page); free orgs get the HTML pack above.
    if org_plan(org_id) not in ("starter", "pro"):
        raise HTTPException(
            status_code=402, detail="PDF evidence export requires the Starter or Pro plan"
        )
    events = store.events(org_id, session_id)
    verdicts = store.verdicts(org_id, session_id)
    anchor_dict = _evidence_anchor(org_id, session_id)
    canon = store.canonical_events(org_id, session_id) if anchor_dict else None
    pdf = build_evidence_pdf(
        session_id,
        events,
        verdicts,
        framework=base_pack_for_org(org_id).framework,
        chain_intact=store.verify_chain(org_id, session_id),
        anchor=anchor_dict,
        canonical=canon,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{session_id}-evidence.pdf"'},
    )
