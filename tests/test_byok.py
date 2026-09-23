import pytest

from teluvane.byok import clear_byok, get_byok, has_byok, set_byok
from teluvane.crypto import decrypt, encrypt
from teluvane.db import get_pool
from teluvane.orgs import create_org


def test_encrypt_roundtrip():
    ct = encrypt("sk-ant-secret123")
    assert ct != "sk-ant-secret123"
    assert decrypt(ct) == "sk-ant-secret123"


def test_wrong_key_cannot_decrypt(monkeypatch):
    ct = encrypt("sk-ant-secret123")
    monkeypatch.setenv("TELUVANE_SECRET_KEY", "ffqFvOwEiqCI8OeEdc_XU2ot3BR-Sf_oA2N2hhQlylM=")
    with pytest.raises(Exception):
        decrypt(ct)


def test_set_get_clear_byok(store):
    org = create_org("Acme", "u1")
    assert has_byok(org) is False
    set_byok(org, "anthropic", "sk-ant-live-xyz")
    assert has_byok(org) is True
    assert get_byok(org) == "sk-ant-live-xyz"
    clear_byok(org)
    assert get_byok(org) is None


def test_ciphertext_at_rest_is_not_plaintext(store):
    org = create_org("Acme", "u1")
    set_byok(org, "anthropic", "sk-ant-PLAINTEXT")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT ciphertext FROM byok_secrets WHERE org_id=%s", (org,))
        stored = cur.fetchone()[0]
    assert "sk-ant-PLAINTEXT" not in stored
