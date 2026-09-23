import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
import json

import httpx
import pytest

from teluvane.orgs import create_org
from teluvane.schema import Verdict
from teluvane.webhooks import (
    WebhookUrlError,
    _sign,
    delete_webhook,
    get_webhook,
    send_webhook,
    set_webhook,
    validate_webhook_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8900/events",
        "http://127.0.0.1/x",
        "http://[::1]/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://foo.internal/x",
        "http://metadata.google.internal/x",
    ],
)
def test_validate_webhook_url_rejects_non_public_targets(url):
    with pytest.raises(WebhookUrlError):
        validate_webhook_url(url)


def test_set_webhook_rejects_ssrf_target(store):
    org = create_org("Acme", "u1")
    with pytest.raises(WebhookUrlError):
        set_webhook(org, "http://169.254.169.254/latest/meta-data/")
    assert get_webhook(org) is None


def test_send_webhook_skips_a_now_unroutable_url(store, monkeypatch):
    org = create_org("Acme", "u1")
    set_webhook(org, "https://example.com/hook")
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE org_webhooks SET url='http://127.0.0.1/x' WHERE org_id=%s", (org,))
        conn.commit()
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: calls.append((a, kw)))
    v = [
        Verdict(
            session_id="s1",
            rule_id="r",
            severity="high",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="x",
            framework_ref="y",
        )
    ]
    send_webhook(org, "s1", v)
    assert calls == []


def test_set_get_delete_roundtrip(store):
    org = create_org("Acme", "u1")
    assert get_webhook(org) is None
    secret = set_webhook(org, "https://example.com/hook")
    hook = get_webhook(org)
    assert hook == {"url": "https://example.com/hook", "secret": secret}
    delete_webhook(org)
    assert get_webhook(org) is None


def test_reconfiguring_rotates_the_secret(store):
    org = create_org("Acme", "u1")
    s1 = set_webhook(org, "https://example.com/a")
    s2 = set_webhook(org, "https://example.com/b")
    assert s1 != s2


def test_send_webhook_noop_without_config(store):
    org = create_org("Acme", "u1")
    v = [
        Verdict(
            session_id="s1",
            rule_id="r",
            severity="high",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="x",
            framework_ref="y",
        )
    ]
    send_webhook(org, "s1", v)  # must not raise even though nothing is configured


def test_send_webhook_noop_with_no_verdicts(store, monkeypatch):
    org = create_org("Acme", "u1")
    set_webhook(org, "https://example.com/hook")
    calls = []
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: calls.append((a, kw)))
    send_webhook(org, "s1", [])
    assert calls == []


def test_send_webhook_posts_signed_json(store, monkeypatch):
    org = create_org("Acme", "u1")
    set_webhook(org, "https://example.com/hook")
    hook = get_webhook(org)
    calls = []
    monkeypatch.setattr(
        httpx, "post", lambda url, content, headers, timeout: calls.append((url, content, headers))
    )

    v = [
        Verdict(
            session_id="s1",
            rule_id="data_exfiltration",
            severity="critical",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="leaked",
            framework_ref="Art.12",
        )
    ]
    send_webhook(org, "s1", v)

    assert len(calls) == 1
    url, content, headers = calls[0]
    assert url == "https://example.com/hook"
    assert headers["X-Teluvane-Signature"] == _sign(hook["secret"], content)
    body = json.loads(content)
    assert body["org_id"] == org and body["session_id"] == "s1"
    assert body["verdicts"][0]["rule_id"] == "data_exfiltration"


def test_send_webhook_formats_slack_when_url_is_a_slack_hook(store, monkeypatch):
    org = create_org("Acme", "u1")
    set_webhook(org, "https://hooks.slack.com/services/T00/B00/XXX")
    calls = []
    monkeypatch.setattr(
        httpx, "post", lambda url, content, headers, timeout: calls.append((url, content, headers))
    )

    v = [
        Verdict(
            session_id="s1",
            rule_id="data_exfiltration",
            severity="critical",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="leaked",
            framework_ref="Art.12",
        )
    ]
    send_webhook(org, "s1", v)

    _, content, headers = calls[0]
    assert "X-Teluvane-Signature" not in headers  # Slack verifies via its own URL secrecy
    body = json.loads(content)
    assert "text" in body and "data_exfiltration" in body["text"]


def test_send_webhook_swallows_delivery_failure(store, monkeypatch):
    org = create_org("Acme", "u1")
    set_webhook(org, "https://example.com/hook")

    def _boom(*a, **kw):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx, "post", _boom)
    v = [
        Verdict(
            session_id="s1",
            rule_id="r",
            severity="high",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="x",
            framework_ref="y",
        )
    ]
    send_webhook(org, "s1", v)  # must not raise
