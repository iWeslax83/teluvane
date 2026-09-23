import time

import jwt as pyjwt
import pytest
from fastapi import HTTPException

import teluvane.auth as auth
from teluvane.auth import current_org, verify_jwt
from teluvane.orgs import create_org


def test_verify_jwt_returns_sub(make_jwt):
    assert verify_jwt(make_jwt("user-1")) == "user-1"


def test_verify_jwt_accepts_asymmetric_es256(monkeypatch):
    # Supabase's new JWT signing keys sign access tokens asymmetrically (ES256), verified via the
    # project's JWKS endpoint. Simulate it: sign with a generated EC key, serve the public key
    # through a fake JWKS client.
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "user-async", "aud": "authenticated", "iat": now, "exp": now + 3600},
        priv,
        algorithm="ES256",
    )

    class _FakeSigningKey:
        key = priv.public_key()

    class _FakeJWKS:
        def get_signing_key_from_jwt(self, _token):
            return _FakeSigningKey()

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: _FakeJWKS())
    assert verify_jwt(token) == "user-async"


def test_verify_jwt_rejects_asymmetric_with_wrong_key(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ec

    signer = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now, "exp": now + 3600},
        signer,
        algorithm="ES256",
    )

    class _FakeSigningKey:
        key = other.public_key()  # wrong public key -> signature must fail

    class _FakeJWKS:
        def get_signing_key_from_jwt(self, _token):
            return _FakeSigningKey()

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: _FakeJWKS())
    with pytest.raises(HTTPException):
        verify_jwt(token)


def test_verify_jwt_rejects_bad_signature(make_jwt):
    with pytest.raises(HTTPException):
        verify_jwt(make_jwt("user-1", secret="wrong-secret"))


def test_verify_jwt_rejects_expired(make_jwt):
    with pytest.raises(HTTPException):
        verify_jwt(make_jwt("user-1", expired=True))


def test_current_org_resolves_org(store, make_jwt):
    org_id = create_org("Acme", "user-7")
    assert current_org(authorization=f"Bearer {make_jwt('user-7')}") == org_id


def test_current_org_rejects_missing_header():
    with pytest.raises(HTTPException):
        current_org(authorization=None)


def test_current_org_rejects_user_without_org(make_jwt):
    with pytest.raises(HTTPException):
        current_org(authorization=f"Bearer {make_jwt('orphan-user')}")
