# teluvane/teluvane/orgs.py
import secrets
import uuid
from typing import Optional

from fastapi import HTTPException

from .db import get_pool


def create_org(name: str, owner_user_id: str) -> str:
    org_id = "org_" + uuid.uuid4().hex[:12]
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orgs(id,name,owner_user_id) VALUES(%s,%s,%s)",
            (org_id, name, owner_user_id),
        )
        cur.execute(
            "INSERT INTO org_members(org_id,user_id,role) VALUES(%s,%s,'owner')",
            (org_id, owner_user_id),
        )
        conn.commit()
    return org_id


def org_for_user(user_id: str) -> Optional[str]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        # Prefer an org the user owns; "role DESC" only worked while the roles were
        # exactly {owner, member} and happened to sort that way.
        cur.execute(
            "SELECT org_id FROM org_members WHERE user_id=%s "
            "ORDER BY (role = 'owner') DESC, org_id LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def get_policy_framework(org_id: str) -> str:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT policy_framework FROM orgs WHERE id=%s", (org_id,))
        row = cur.fetchone()
    return row[0] if row else "eu_ai_act"


def set_policy_framework(org_id: str, framework: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orgs SET policy_framework=%s WHERE id=%s", (framework, org_id))
        conn.commit()


def member_role(org_id: str, user_id: str) -> Optional[str]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT role FROM org_members WHERE org_id=%s AND user_id=%s", (org_id, user_id)
        )
        row = cur.fetchone()
    return row[0] if row else None


def require_owner(org_id: str, user_id: str) -> None:
    if member_role(org_id, user_id) != "owner":
        raise HTTPException(status_code=403, detail="only the org owner can do this")


def list_members(org_id: str) -> list[dict]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT om.user_id, om.role, au.email FROM org_members om "
            "LEFT JOIN auth.users au ON au.id::text = om.user_id "
            "WHERE om.org_id=%s ORDER BY om.role, au.email",
            (org_id,),
        )
        rows = cur.fetchall()
    return [{"user_id": r[0], "role": r[1], "email": r[2]} for r in rows]


def set_member_role(org_id: str, user_id: str, role: str) -> None:
    if role == "member" and member_role(org_id, user_id) == "owner":
        owners = sum(1 for m in list_members(org_id) if m["role"] == "owner")
        if owners <= 1:
            raise HTTPException(status_code=400, detail="an org needs at least one owner")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE org_members SET role=%s WHERE org_id=%s AND user_id=%s", (role, org_id, user_id)
        )
        conn.commit()


def remove_member(org_id: str, user_id: str) -> None:
    if member_role(org_id, user_id) == "owner":
        owners = sum(1 for m in list_members(org_id) if m["role"] == "owner")
        if owners <= 1:
            raise HTTPException(status_code=400, detail="an org needs at least one owner")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM org_members WHERE org_id=%s AND user_id=%s", (org_id, user_id))
        conn.commit()


# ---- invites --------------------------------------------------------------------------------
def create_invite(org_id: str, email: str, role: str, invited_by: str) -> str:
    token = secrets.token_urlsafe(24)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_invites(org_id,email,role,token,invited_by) VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT (org_id,email) DO UPDATE SET role=EXCLUDED.role, token=EXCLUDED.token, "
            "invited_by=EXCLUDED.invited_by, created_at=now(), accepted_at=NULL",
            (org_id, email.lower(), role, token, invited_by),
        )
        conn.commit()
    return token


def list_invites(org_id: str) -> list[dict]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, role, created_at FROM org_invites "
            "WHERE org_id=%s AND accepted_at IS NULL ORDER BY created_at DESC",
            (org_id,),
        )
        rows = cur.fetchall()
    return [{"id": r[0], "email": r[1], "role": r[2], "created_at": r[3].isoformat()} for r in rows]


def revoke_invite(org_id: str, invite_id: int) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM org_invites WHERE org_id=%s AND id=%s AND accepted_at IS NULL",
            (org_id, invite_id),
        )
        conn.commit()


def find_pending_invite(email: str) -> Optional[dict]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, org_id, role FROM org_invites WHERE email=%s AND accepted_at IS NULL "
            "ORDER BY created_at LIMIT 1",
            (email.lower(),),
        )
        row = cur.fetchone()
    return {"id": row[0], "org_id": row[1], "role": row[2]} if row else None


def accept_invite(invite_id: int, user_id: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT org_id, role FROM org_invites WHERE id=%s AND accepted_at IS NULL", (invite_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="invite not found or already used")
        org_id, role = row
        cur.execute(
            "INSERT INTO org_members(org_id,user_id,role) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id,user_id) DO UPDATE SET role=EXCLUDED.role",
            (org_id, user_id, role),
        )
        cur.execute("UPDATE org_invites SET accepted_at=now() WHERE id=%s", (invite_id,))
        conn.commit()
