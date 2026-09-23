from teluvane.schema import Event, Verdict


def test_event_has_optional_org_id_default_none():
    e = Event(agent_id="a", session_id="s", kind="llm_call")
    assert e.org_id is None  # assigned by the store on persist, like seq/hash
    e.org_id = "org1"
    assert e.model_dump()["org_id"] == "org1"


def test_verdict_has_optional_org_id():
    v = Verdict(session_id="s", rule_id="r", severity="low", violation=False, confidence=0.0)
    assert v.org_id is None
