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
    legal_hold: bool | None = Body(default=None),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    # A PUT is a partial update: omitting a field must leave it as it currently is, not reset
    # it to a default. That matters most for legal_hold, since a caller who PUTs only
    # retention_days (a natural update) must never silently lift an active hold. FastAPI can't
    # tell "field absent" apart from "field explicitly null" for a bare scalar Body param, so
    # both are treated the same way here: neither field changes unless the caller sends it with
    # a real value. A caller who wants to lift a hold sends legal_hold=False explicitly; there
    # is currently no way to clear an existing retention_days back to "no window" through this
    # endpoint (only to change it to another number), which is an accepted limitation of this
    # fix, not a new one.
    _owner_id(org_id, authorization)
    current = get_retention(org_id)
    new_days = retention_days if retention_days is not None else current["retention_days"]
    new_hold = legal_hold if legal_hold is not None else current["legal_hold"]
    set_retention(org_id, new_days, new_hold)
    return get_retention(org_id)
