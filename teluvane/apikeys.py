# teluvane/teluvane/apikeys.py
import hashlib
import secrets

from fastapi import Header, HTTPException

from .db import get_pool

KEY_PREFIX = "tv_live_"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_api_key(org_id: str, name: str) -> str:
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO api_keys(org_id,name,key_hash,prefix) VALUES(%s,%s,%s,%s)",
            (org_id, name, _hash(raw), raw[:12]),
        )
        conn.commit()
    return raw  # returned exactly once; never recoverable afterwards


def resolve_api_key(raw: str) -> str:
    h = _hash(raw)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT org_id FROM api_keys WHERE key_hash=%s AND revoked_at IS NULL", (h,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="invalid API key")
        cur.execute("UPDATE api_keys SET last_used_at=now() WHERE key_hash=%s", (h,))
        conn.commit()
    return row[0]


def list_api_keys(org_id: str) -> list[dict]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id,name,prefix,last_used_at,revoked_at,created_at "
            "FROM api_keys WHERE org_id=%s ORDER BY created_at DESC",
            (org_id,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def revoke_api_key(org_id: str, key_id: int) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE api_keys SET revoked_at=now() WHERE id=%s AND org_id=%s", (key_id, org_id)
        )
        conn.commit()


def org_from_api_key(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing API key")
    return resolve_api_key(authorization[len("Bearer ") :])
