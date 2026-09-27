import pytest

from teluvane.detectors import DETECTORS
from teluvane.policy import PolicyPack, Rule, load_policy_pack
from teluvane.schema import Event
from teluvane.tribunal import KEYWORD_CONFIDENCE, offline_audit

PACKS = ["eu_ai_act", "iso42001", "nist_ai_rmf", "soc2"]


def ev(seq, kind="tool_call", **kw):
    e = Event(agent_id="a", session_id="s", kind=kind, **kw)
    e.seq = seq
    return e


@pytest.mark.parametrize("name", PACKS)
def test_every_detector_named_in_a_shipped_pack_exists(name):
    for rule in load_policy_pack(f"policies/{name}.yaml").rules:
        assert rule.detector is None or rule.detector in DETECTORS, rule.id


def test_evidence_points_only_at_the_events_that_matched():
    pack = load_policy_pack("policies/eu_ai_act.yaml")
    events = [
        ev(1, kind="llm_call", intent="plan the day"),
        ev(2, tool="send_email", args={"body": "SSN 123-45-6789"}, intent="notify"),
        ev(3, kind="llm_call", intent="wrap up"),
    ]
    got = {v.rule_id: v for v in offline_audit(events, "s", pack)}
    assert got["data_exfiltration"].evidence_seqs == [2]
    assert got["pii_mishandling"].evidence_seqs == [2]


def test_benign_look_alikes_are_not_flagged():
    pack = load_policy_pack("policies/eu_ai_act.yaml")
    events = [
        ev(1, tool="delete_cache_entry", intent="evict stale cache", approved_by="human:u1"),
        ev(2, kind="llm_call", intent="summarize an article about external links"),
    ]
    assert offline_audit(events, "s", pack) == []


def test_rules_without_a_detector_fall_back_to_per_event_keywords():
    rule = Rule(
        id="scope",
        description="d",
        severity="low",
        framework_ref="x",
        detector_hint="h",
        keywords=["unauthorized tool"],
    )
    pack = PolicyPack(framework="F", version="1", rules=[rule])
    events = [ev(1, intent="fine"), ev(2, intent="used an unauthorized tool here")]
    (verdict,) = offline_audit(events, "s", pack)
    assert verdict.evidence_seqs == [2] and verdict.confidence == KEYWORD_CONFIDENCE


def test_keyword_match_needs_a_word_start():
    rule = Rule(
        id="k",
        description="d",
        severity="low",
        framework_ref="x",
        detector_hint="h",
        keywords=["ssn"],
    )
    pack = PolicyPack(framework="F", version="1", rules=[rule])
    assert offline_audit([ev(1, intent="a classnsn value")], "s", pack) == []
    assert len(offline_audit([ev(1, intent="store the SSN")], "s", pack)) == 1
