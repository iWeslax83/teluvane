import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
os.environ.setdefault("LEMONSQUEEZY_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("LEMONSQUEEZY_API_KEY", "test-api-key")
os.environ.setdefault("LEMONSQUEEZY_STORE_ID", "1")

import hashlib
import hmac
import json

import httpx
import pytest

from teluvane import billing
from teluvane.orgs import create_org


def _sign(body: bytes) -> str:
    secret = os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"].encode("utf-8")
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _subscription_payload(org_id: str, *, status: str, variant_id) -> bytes:
    return json.dumps(
        {
            "meta": {"event_name": "subscription_created", "custom_data": {"org_id": org_id}},
            "data": {
                "id": "sub_1",
                "attributes": {
                    "status": status,
                    "variant_id": variant_id,
                    "renews_at": None,
                },
            },
        }
    ).encode("utf-8")


@pytest.fixture(autouse=True)
def _variant_ids(monkeypatch):
    monkeypatch.setattr(billing, "PRO_VARIANT_ID", "variant-pro")
    monkeypatch.setattr(billing, "STARTER_VARIANT_ID", "variant-starter")
    monkeypatch.setattr(
        billing, "_VARIANT_IDS", {"pro": "variant-pro", "starter": "variant-starter"}
    )


def test_webhook_sets_starter_plan_for_the_starter_variant(store):
    org = create_org("Acme", "u1")
    body = _subscription_payload(org, status="active", variant_id="variant-starter")
    billing.handle_webhook(body, _sign(body))
    assert billing.org_plan(org) == "starter"


def test_webhook_sets_pro_plan_for_the_pro_variant(store):
    org = create_org("Acme", "u1")
    body = _subscription_payload(org, status="active", variant_id="variant-pro")
    billing.handle_webhook(body, _sign(body))
    assert billing.org_plan(org) == "pro"


def test_webhook_falls_back_to_pro_for_an_unrecognized_variant(store):
    # A paying subscriber must never get silently downgraded because a variant id
    # wasn't configured in this environment.
    org = create_org("Acme", "u1")
    body = _subscription_payload(org, status="active", variant_id="variant-unknown")
    billing.handle_webhook(body, _sign(body))
    assert billing.org_plan(org) == "pro"


def test_webhook_sets_free_plan_when_subscription_is_inactive(store):
    org = create_org("Acme", "u1")
    body = _subscription_payload(org, status="cancelled", variant_id="variant-starter")
    billing.handle_webhook(body, _sign(body))
    assert billing.org_plan(org) == "free"


def test_create_checkout_session_rejects_a_plan_with_no_configured_variant(monkeypatch):
    monkeypatch.setattr(billing, "_VARIANT_IDS", {"pro": "variant-pro", "starter": ""})
    with pytest.raises(ValueError):
        billing.create_checkout_session("org1", "user@example.com", "starter")


def test_create_checkout_session_uses_the_variant_for_the_requested_plan(monkeypatch):
    calls = []

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"attributes": {"url": "https://checkout.example/session"}}}

    def _post(url, headers, json, timeout):
        calls.append(json)
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    url = billing.create_checkout_session("org1", "user@example.com", "starter")
    assert url == "https://checkout.example/session"
    variant = calls[0]["data"]["relationships"]["variant"]["data"]["id"]
    assert variant == "variant-starter"
