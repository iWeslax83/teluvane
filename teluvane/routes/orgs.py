# teluvane/teluvane/routes/orgs.py
"""Org creation, team management, API keys."""

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from ..apikeys import create_api_key, list_api_keys, revoke_api_key
from ..auth import current_org, verify_jwt, verify_jwt_claims
from ..orgs import (
    accept_invite,
    create_invite,
    create_org,
    find_pending_invite,
    list_invites,
    list_members,
    org_for_user,
    remove_member,
    require_owner,
    revoke_invite,
    set_member_role,
)

router = APIRouter()


# ---- org + key management (human auth: JWT) ------------------------------------------------
@router.post("/orgs")
def make_org(name: str = Body(embed=True), authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[len("Bearer ") :]
    user_id = verify_jwt(token)
    existing = org_for_user(user_id)
    if existing:
        return {"org_id": existing}
    # A brand-new user whose email matches a pending team invite joins that org instead of
    # getting their own — the common case for someone who was invited and is signing up for
    # the first time. No email delivery needed: the owner just shares the invited address.
    email = verify_jwt_claims(token).get("email")
    invite = find_pending_invite(email) if email else None
    if invite:
        accept_invite(invite["id"], user_id)
        return {"org_id": invite["org_id"]}
    return {"org_id": create_org(name, user_id)}


# ---- team management (human auth: JWT) ------------------------------------------------------
@router.get("/orgs/members")
def get_members(org_id: str = Depends(current_org)) -> list[dict]:
    return list_members(org_id)


@router.put("/orgs/members/{user_id}")
def put_member_role(
    user_id: str,
    role: str = Body(embed=True),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    require_owner(org_id, verify_jwt(authorization[len("Bearer ") :]))
    if role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="role must be 'owner' or 'member'")
    set_member_role(org_id, user_id, role)
    return {"user_id": user_id, "role": role}


@router.delete("/orgs/members/{user_id}")
def delete_member(
    user_id: str, org_id: str = Depends(current_org), authorization: str = Header(default=None)
) -> dict:
    require_owner(org_id, verify_jwt(authorization[len("Bearer ") :]))
    remove_member(org_id, user_id)
    return {"removed": user_id}


@router.get("/orgs/invites")
def get_invites(org_id: str = Depends(current_org)) -> list[dict]:
    return list_invites(org_id)


@router.post("/orgs/invites")
def post_invite(
    email: str = Body(...),
    role: str = Body(default="member"),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    user_id = verify_jwt(authorization[len("Bearer ") :])
    require_owner(org_id, user_id)
    if role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="role must be 'owner' or 'member'")
    create_invite(org_id, email, role, user_id)
    return {"email": email.lower(), "role": role}


@router.delete("/orgs/invites/{invite_id}")
def delete_invite(
    invite_id: int, org_id: str = Depends(current_org), authorization: str = Header(default=None)
) -> dict:
    require_owner(org_id, verify_jwt(authorization[len("Bearer ") :]))
    revoke_invite(org_id, invite_id)
    return {"revoked": invite_id}


@router.post("/keys")
def new_key(name: str = Body(embed=True), org_id: str = Depends(current_org)) -> dict:
    return {"key": create_api_key(org_id, name)}  # shown once


@router.get("/keys")
def keys(org_id: str = Depends(current_org)) -> list[dict]:
    return list_api_keys(org_id)


@router.delete("/keys/{key_id}")
def delete_key(key_id: int, org_id: str = Depends(current_org)) -> dict:
    revoke_api_key(org_id, key_id)
    return {"revoked": key_id}
