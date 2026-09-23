import threading
import time

import teluvane.auditlock as auditlock
from teluvane.auditlock import audited_run
from teluvane.orgs import create_org
from teluvane.schema import Event, Verdict


def _seed(store, org, session="s1"):
    store.append(
        org,
        Event(
            agent_id="a",
            session_id=session,
            kind="tool_call",
            tool="send_email",
            args={"to": "attacker@evil.com"},
            intent="exfil",
        ),
    )


def test_concurrent_audits_run_tribunal_once(store, monkeypatch):
    org = create_org("Acme", "u1")
    _seed(store, org)
    calls = {"n": 0}

    def fake_audit(events, session_id, pack, anthropic_api_key=None):
        calls["n"] += 1
        time.sleep(0.4)  # widen the race window
        return [
            Verdict(
                session_id=session_id,
                rule_id="data_exfiltration",
                severity="critical",
                violation=True,
                confidence=0.9,
                evidence_seqs=[1],
            )
        ]

    monkeypatch.setattr(auditlock, "audit", fake_audit)

    results = []

    def go():
        results.append(audited_run(store, org, "s1", pack=object(), api_key="sk-ant-x"))

    t1, t2 = threading.Thread(target=go), threading.Thread(target=go)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert calls["n"] == 1  # tribunal ran exactly once
    assert all(len(r) == 1 for r in results)  # both callers got the verdict
