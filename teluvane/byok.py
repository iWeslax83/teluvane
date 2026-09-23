# teluvane/teluvane/byok.py
from typing import Optional

from .crypto import decrypt, encrypt
from .db import get_pool


def set_byok(org_id: str, provider: str, plaintext: str) -> None:
    ct = encrypt(plaintext)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO byok_secrets(org_id,provider,ciphertext) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id,provider) DO UPDATE SET ciphertext=EXCLUDED.ciphertext, created_at=now()",
            (org_id, provider, ct),
        )
        conn.commit()


def get_byok(org_id: str, provider: str = "anthropic") -> Optional[str]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ciphertext FROM byok_secrets WHERE org_id=%s AND provider=%s",
            (org_id, provider),
        )
        row = cur.fetchone()
    return decrypt(row[0]) if row else None


def has_byok(org_id: str, provider: str = "anthropic") -> bool:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM byok_secrets WHERE org_id=%s AND provider=%s", (org_id, provider)
        )
        return cur.fetchone() is not None


def clear_byok(org_id: str, provider: str = "anthropic") -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM byok_secrets WHERE org_id=%s AND provider=%s", (org_id, provider))
        conn.commit()
