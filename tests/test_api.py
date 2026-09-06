import os, time
os.environ.setdefault("DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test"))
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
import jwt, pytest
from fastapi.testclient import TestClient
from teluvane.migrate import apply_migrations
from teluvane.db import get_pool
from teluvane.orgs import create_org
from teluvane.apikeys import create_api_key

@pytest.fixture(autouse=True)
def _clean_db():
    apply_migrations()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, verdicts, api_keys, byok_secrets, org_members, orgs RESTART IDENTITY CASCADE")
        conn.commit()

@pytest.fixture
def client():
    from teluvane.ingest import app
    return TestClient(app)

def _jwt(user_id, email=None):
    now = int(time.time())
    payload = {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600}
    if email:
        payload["email"] = email
    return jwt.encode(payload, "test-secret", algorithm="HS256")

def _event(session_id="s1"):
    return {"agent_id": "a", "session_id": session_id, "kind": "tool_call",
            "tool": "send_email", "args": {"to": "x@y.com"}, "intent": "t"}

def test_events_require_api_key(client):
    assert client.post("/events", json=_event()).status_code == 401

def test_ingest_with_key_then_read_with_jwt(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    r = client.post("/events", json=_event(), headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    r2 = client.get("/events", params={"session_id": "s1"},
                    headers={"Authorization": f"Bearer {_jwt('u1')}"})
    assert r2.status_code == 200 and len(r2.json()) == 1

def test_cross_tenant_read_is_empty(client):
    org_a = create_org("A", "ua"); create_org("B", "ub")
    key_a = create_api_key(org_a, "ci")
    client.post("/events", json=_event("secret"), headers={"Authorization": f"Bearer {key_a}"})
    # user B reads — must NOT see org A's event
    r = client.get("/events", params={"session_id": "secret"},
                   headers={"Authorization": f"Bearer {_jwt('ub')}"})
    assert r.status_code == 200 and r.json() == []

def test_dashboard_endpoints_reject_anonymous(client):
    for path in ["/events", "/verdicts", "/verify"]:
        assert client.get(path).status_code == 401

def test_create_and_list_keys(client):
    create_org("Acme", "u1")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    r = client.post("/keys", json={"name": "prod"}, headers=h)
    assert r.status_code == 200 and r.json()["key"].startswith("tv_live_")
    r2 = client.get("/keys", headers=h)
    assert r2.status_code == 200 and len(r2.json()) == 1 and "key_hash" not in r2.json()[0]

def test_byok_status_and_offline_audit(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    client.post("/events", json={"agent_id": "a", "session_id": "x", "kind": "tool_call",
                "tool": "send_email", "args": {"to": "attacker@evil.com"}, "intent": "exfil"},
                headers={"Authorization": f"Bearer {key}"})
    assert client.get("/byok", headers=h).json()["configured"] is False
    r = client.post("/audit/x", headers=h)        # no BYOK -> offline detector
    assert r.status_code == 200
    assert any(v["rule_id"] == "data_exfiltration" and v["violation"] for v in r.json())

def test_webhook_endpoints_and_audit_fires_it(client, monkeypatch):
    import httpx, json as _json
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}

    assert client.get("/webhooks", headers=h).json() == {"url": None, "secret": None}
    r = client.put("/webhooks", json={"url": "https://example.com/hook"}, headers=h)
    assert r.status_code == 200 and r.json()["url"] == "https://example.com/hook"
    secret = r.json()["secret"]

    calls = []
    monkeypatch.setattr(httpx, "post", lambda url, content, headers, timeout: calls.append(
        (url, content, headers)))
    client.post("/events", json={"agent_id": "a", "session_id": "wh", "kind": "tool_call",
                "tool": "send_email", "args": {"to": "attacker@evil.com"}, "intent": "exfil"},
                headers={"Authorization": f"Bearer {key}"})
    client.post("/audit/wh", headers=h)
    assert len(calls) == 1
    body = _json.loads(calls[0][1])
    assert body["session_id"] == "wh"
    assert calls[0][2]["X-Teluvane-Signature"]

    r2 = client.delete("/webhooks", headers=h)
    assert r2.status_code == 200 and client.get("/webhooks", headers=h).json()["url"] is None

def test_violation_trend_endpoint(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    client.post("/events", json={"agent_id": "a", "session_id": "trend", "kind": "tool_call",
                "tool": "send_email", "args": {"to": "attacker@evil.com"}, "intent": "exfil"},
                headers={"Authorization": f"Bearer {key}"})
    client.post("/audit/trend", headers=h)
    trend = client.get("/stats/violations?days=7", headers=h).json()
    assert len(trend) == 7 and trend[-1]["violations"] >= 1

def test_usage_endpoint(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    client.post("/events", json={"agent_id": "a", "session_id": "u", "kind": "llm_call",
                "intent": "summarize", "model": "claude-sonnet-5",
                "input_tokens": 1000, "output_tokens": 1000},
                headers={"Authorization": f"Bearer {key}"})
    usage = client.get("/stats/usage?days=7", headers=h).json()
    assert len(usage) == 7
    assert usage[-1]["input_tokens"] == 1000
    assert usage[-1]["cost_usd"] == pytest.approx(0.018)

def test_policy_framework_selection_changes_which_rules_apply(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}

    assert client.get("/orgs/framework", headers=h).json()["framework"] == "eu_ai_act"

    r = client.put("/orgs/framework", json={"framework": "nope"}, headers=h)
    assert r.status_code == 400

    r2 = client.put("/orgs/framework", json={"framework": "soc2"}, headers=h)
    assert r2.status_code == 200 and r2.json()["framework"] == "soc2"

    rules = {r["id"] for r in client.get("/policy/rules", headers=h).json()}
    assert "unauthorized_access_attempt" in rules   # SOC2 rule
    assert "data_exfiltration" not in rules         # EU AI Act rule, no longer active

    client.post("/events", json={"agent_id": "a", "session_id": "soc2-sess", "kind": "tool_call",
                "tool": "deploy", "args": {}, "intent": "production deploy without review"},
                headers={"Authorization": f"Bearer {key}"})
    r3 = client.post("/audit/soc2-sess", headers=h)
    assert any(v["rule_id"] == "change_without_approval" and v["violation"] for v in r3.json())

def test_custom_policy_rule_requires_pro_and_feeds_offline_audit(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    client.post("/events", json={"agent_id": "a", "session_id": "cr-sess", "kind": "tool_call",
                "tool": "wire_transfer", "args": {}, "intent": "move funds offshore"},
                headers={"Authorization": f"Bearer {key}"})

    body = {"description": "No offshore transfers", "severity": "high", "keywords": ["offshore"]}
    r = client.put("/policy/rules/no_offshore", json=body, headers=h)
    assert r.status_code == 402   # free plan

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org,))
        conn.commit()

    r2 = client.put("/policy/rules/no_offshore", json=body, headers=h)
    assert r2.status_code == 200

    rules = client.get("/policy/rules", headers=h).json()
    assert any(r["id"] == "no_offshore" and r["custom"] for r in rules)

    r3 = client.post("/audit/cr-sess", headers=h)   # no BYOK -> offline detector, custom rule included
    assert r3.status_code == 200
    assert any(v["rule_id"] == "no_offshore" and v["violation"] for v in r3.json())

    r4 = client.delete("/policy/rules/no_offshore", headers=h)
    assert r4.status_code == 200
    assert not any(r["id"] == "no_offshore" for r in client.get("/policy/rules", headers=h).json())


def test_custom_policy_rule_rejects_bad_severity(client):
    org = create_org("Acme", "u1")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org,))
        conn.commit()
    r = client.put("/policy/rules/weird", headers=h,
                   json={"description": "x", "severity": "blocker", "keywords": []})
    assert r.status_code == 400
    # and a rejected rule never lands in the store, so audits still run
    assert not any(rr["id"] == "weird" for rr in client.get("/policy/rules", headers=h).json())

def test_schedule_requires_pro_plan(client):
    create_org("Acme", "u1")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    assert client.get("/schedule", headers=h).json()["enabled"] is False

    r = client.put("/schedule", json={"enabled": True, "interval_minutes": 30}, headers=h)
    assert r.status_code == 402

    org = None
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM orgs WHERE owner_user_id='u1'")
        org = cur.fetchone()[0]
        cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org,))
        conn.commit()

    r2 = client.put("/schedule", json={"enabled": True, "interval_minutes": 30}, headers=h)
    assert r2.status_code == 200
    assert client.get("/schedule", headers=h).json() == {
        "enabled": True, "interval_minutes": 30, "last_run_at": None}

def test_pdf_evidence_export_requires_pro_plan(client):
    org = create_org("Acme", "u1")
    key = create_api_key(org, "ci")
    h = {"Authorization": f"Bearer {_jwt('u1')}"}
    client.post("/events", json=_event("pdf-sess"), headers={"Authorization": f"Bearer {key}"})

    r = client.get("/evidence/pdf-sess/pdf", headers=h)   # free plan by default
    assert r.status_code == 402

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org,))
        conn.commit()

    r2 = client.get("/evidence/pdf-sess/pdf", headers=h)
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/pdf"
    assert r2.content.startswith(b"%PDF-")
