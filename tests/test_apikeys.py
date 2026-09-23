import pytest
from fastapi import HTTPException

from teluvane.apikeys import create_api_key, list_api_keys, resolve_api_key, revoke_api_key
from teluvane.db import get_pool
from teluvane.orgs import create_org


def test_create_returns_raw_key_and_stores_only_hash(store):
    org = create_org("Acme", "u1")
    raw = create_api_key(org, "ci")
    assert raw.startswith("tv_live_")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT key_hash FROM api_keys WHERE org_id=%s", (org,))
        stored = cur.fetchone()[0]
    assert stored != raw and len(stored) == 64  # sha256 hex, not the raw key


def test_resolve_returns_org(store):
    org = create_org("Acme", "u1")
    raw = create_api_key(org, "ci")
    assert resolve_api_key(raw) == org


def test_resolve_unknown_key_rejected(store):
    with pytest.raises(HTTPException):
        resolve_api_key("tv_live_nope")


def test_revoked_key_rejected(store):
    org = create_org("Acme", "u1")
    raw = create_api_key(org, "ci")
    key_id = list_api_keys(org)[0]["id"]
    revoke_api_key(org, key_id)
    with pytest.raises(HTTPException):
        resolve_api_key(raw)


def test_revoke_is_tenant_scoped(store):
    org_a = create_org("A", "ua")
    org_b = create_org("B", "ub")
    raw = create_api_key(org_a, "ci")
    key_id = list_api_keys(org_a)[0]["id"]
    revoke_api_key(org_b, key_id)  # org B must NOT be able to revoke org A's key
    assert resolve_api_key(raw) == org_a  # still valid
