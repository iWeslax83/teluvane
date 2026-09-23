# teluvane/teluvane/auth.py
import os

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from .orgs import org_for_user

# Supabase access tokens may be signed two ways:
#  - HS256 with the shared "legacy JWT secret" (older projects; also used by the test suite), or
#  - ES256/RS256 with the project's asymmetric "JWT signing keys", verified via the public JWKS
#    endpoint at <SUPABASE_URL>/auth/v1/.well-known/jwks.json.
# We route by the token's `alg` header so both work without extra configuration.
ASYMMETRIC_ALGS = ["ES256", "RS256"]
_jwks_client: PyJWKClient | None = None


def _jwks_url() -> str:
    url = os.environ.get("SUPABASE_JWKS_URL")
    if url:
        return url
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL (or SUPABASE_JWKS_URL) must be set to verify tokens",
        )
    return f"{base}/auth/v1/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_jwks_url())
    return _jwks_client


def _decode_payload(token: str) -> dict:
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token header")
    try:
        if alg == "HS256":
            payload = jwt.decode(
                token,
                os.environ["SUPABASE_JWT_SECRET"],
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            key = _get_jwks_client().get_signing_key_from_jwt(token).key
            payload = jwt.decode(token, key, algorithms=ASYMMETRIC_ALGS, audience="authenticated")
    except HTTPException:
        raise  # propagate config errors (e.g. missing SUPABASE_URL) as-is
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="token has no subject")
    return payload


def verify_jwt(token: str) -> str:
    return _decode_payload(token)["sub"]


def verify_jwt_claims(token: str) -> dict:
    """Like verify_jwt but returns the full payload (sub, email, ...) for callers that need
    more than just the user id, e.g. matching a signup against a pending team invite by email."""
    return _decode_payload(token)


def current_org(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    user_id = verify_jwt(authorization[len("Bearer ") :])
    org_id = org_for_user(user_id)
    if not org_id:
        raise HTTPException(status_code=403, detail="user has no org")
    return org_id
