# teluvane/teluvane/routes/privacy.py
"""GDPR controls: erase a session's event payloads, set a retention window, place a legal hold."""

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..appstate import store
from ..auth import current_org, verify_jwt
from ..orgs import require_owner
from ..retention import MAX_RETENTION_DAYS, get_retention, set_retention

router = APIRouter()


class EraseRequest(BaseModel):
    seqs: list[int] | None = None  # None erases every erasable event in the session
    reason: str = Field(default="", max_length=500)


def _owner_id(org_id: str, authorization: str | None) -> str:
    user_id = verify_jwt(authorization[len("Bearer ") :])
    require_owner(org_id, user_id)
    return user_id


@router.post("/sessions/{session_id}/erase")
def erase_session(
    session_id: str,
    body: EraseRequest = Body(default_factory=EraseRequest),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    user_id = _owner_id(org_id, authorization)
    if get_retention(org_id)["legal_hold"]:
        raise HTTPException(status_code=409, detail="erasure is blocked while a legal hold is on")
    if not store.events(org_id, session_id):
        raise HTTPException(status_code=404, detail="session not found")
    result = store.erase_payloads(
        org_id, session_id, requested_by=user_id, reason=body.reason, seqs=body.seqs
    )
    if result["erased"] == 0 and result["legacy_unerasable"] > 0:
        raise HTTPException(
            status_code=409,
            detail="these events predate erasable payloads (hash version 1) and cannot be erased",
        )
    return result


@router.get("/orgs/retention")
def read_retention(org_id: str = Depends(current_org)) -> dict:
    return get_retention(org_id)


@router.put("/orgs/retention")
def write_retention(
    retention_days: int | None = Body(default=None, ge=1, le=MAX_RETENTION_DAYS),
    legal_hold: bool = Body(default=False),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    _owner_id(org_id, authorization)
    set_retention(org_id, retention_days, legal_hold)
    return get_retention(org_id)
