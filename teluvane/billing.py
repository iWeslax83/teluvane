# teluvane/teluvane/billing.py
import hashlib, hmac, json, os
from typing import Optional

import httpx

from .db import get_pool

API_BASE = "https://api.lemonsqueezy.com/v1"
PRO_VARIANT_ID = os.environ.get("LEMONSQUEEZY_VARIANT_ID_PRO", "")
STARTER_VARIANT_ID = os.environ.get("LEMONSQUEEZY_VARIANT_ID_STARTER", "")
_VARIANT_IDS = {"pro": PRO_VARIANT_ID, "starter": STARTER_VARIANT_ID}


def _api_key() -> str:
    return os.environ["LEMONSQUEEZY_API_KEY"]


def _store_id() -> str:
    return os.environ["LEMONSQUEEZY_STORE_ID"]


def create_checkout_session(org_id: str, user_email: str, plan: str = "pro") -> str:
    """Create a hosted LemonSqueezy checkout for the given plan ("starter" or "pro"),
    stamped with org_id so the webhook can attribute the resulting subscription back
    to the org without a lookup table."""
    variant_id = _VARIANT_IDS.get(plan, "")
    if not variant_id:
        raise ValueError(f"no LemonSqueezy variant configured for plan '{plan}'")
    attributes: dict = {
        "checkout_data": {
            "email": user_email,
            "custom": {"org_id": org_id},
        },
    }
    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "")
    if frontend_origin:
        attributes["product_options"] = {
            "redirect_url": f"{frontend_origin}/app/billing?upgraded=true",
        }
    resp = httpx.post(
        f"{API_BASE}/checkouts",
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        },
        json={
            "data": {
                "type": "checkouts",
                "attributes": attributes,
                "relationships": {
                    "store": {"data": {"type": "stores", "id": _store_id()}},
                    "variant": {"data": {"type": "variants", "id": variant_id}},
                },
            }
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]["attributes"]["url"]


def create_portal_session(org_id: str) -> Optional[str]:
    """Customer portal link for the org's active subscription, if any."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT billing_subscription_id FROM orgs WHERE id=%s", (org_id,))
        row = cur.fetchone()
    if not row or not row[0]:
        return None
    resp = httpx.get(
        f"{API_BASE}/subscriptions/{row[0]}",
        headers={"Authorization": f"Bearer {_api_key()}", "Accept": "application/vnd.api+json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]["attributes"]["urls"]["customer_portal"]


def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    secret = os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"].encode("utf-8")
    digest = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature_header or "")


_ACTIVE_STATUSES = {"active", "on_trial"}


def _plan_for_variant(variant_id) -> str:
    """Map a LemonSqueezy variant id back to our plan name. An unrecognized or missing
    variant id falls back to "pro" rather than "free": that was the only paid tier before
    Starter existed, and a paying subscriber should never get silently downgraded because
    a variant id wasn't configured in this environment."""
    variant_str = str(variant_id) if variant_id is not None else ""
    if STARTER_VARIANT_ID and variant_str == STARTER_VARIANT_ID:
        return "starter"
    return "pro"


def handle_webhook(raw_body: bytes, signature_header: str) -> None:
    """Verify and apply a LemonSqueezy subscription webhook. Every event is logged to
    billing_events (verified or not) before any org row is touched, so a bad signature
    or a malformed payload never silently drops a billing event on the floor."""
    signature_ok = verify_signature(raw_body, signature_header)
    try:
        payload = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except ValueError:
        payload = None

    meta = payload.get("meta", {}) if payload else {}
    event_type = meta.get("event_name", "unknown")
    org_id = meta.get("custom_data", {}).get("org_id")

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO billing_events(provider,event_type,org_id,payload,signature_ok) "
            "VALUES('lemonsqueezy',%s,%s,%s,%s)",
            (event_type, org_id,
             json.dumps(payload if payload is not None
                        else {"_unparseable_raw": raw_body.decode("utf-8", "replace")}),
             signature_ok),
        )
        conn.commit()

        if not signature_ok:
            raise ValueError("invalid webhook signature")
        if payload is None:
            raise ValueError("malformed webhook body")
        if not org_id or event_type not in (
            "subscription_created", "subscription_updated", "subscription_cancelled",
            "subscription_expired", "subscription_payment_failed", "subscription_payment_success",
        ):
            return

        attrs = payload.get("data", {}).get("attributes", {})
        status = attrs.get("status", "")
        subscription_id = payload.get("data", {}).get("id")
        renews_at = attrs.get("renews_at")

        plan = _plan_for_variant(attrs.get("variant_id")) if status in _ACTIVE_STATUSES else "free"
        cur.execute(
            "UPDATE orgs SET plan=%s, plan_status=%s, billing_subscription_id=%s, "
            "plan_renews_at=%s WHERE id=%s",
            (plan, status, subscription_id, renews_at, org_id),
        )
        conn.commit()


def org_plan(org_id: str) -> str:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT plan FROM orgs WHERE id=%s", (org_id,))
        row = cur.fetchone()
    return row[0] if row else "free"
