"""The landing page shows real output for one demo session. This pins that output to what the
offline tribunal actually returns, so the page cannot drift from the product."""

import json
import pathlib

from teluvane.policy import load_policy_pack
from teluvane.schema import Event
from teluvane.tribunal import offline_audit

DEMO = pathlib.Path(__file__).parent.parent / "frontend" / "lib" / "demoSession.json"


def test_landing_findings_match_the_offline_tribunal():
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    events = []
    for seq, e in enumerate(demo["events"], start=1):
        event = Event(
            agent_id=demo["agentId"],
            session_id=demo["sessionId"],
            kind=e["kind"],
            tool=e["tool"],
            intent=e["intent"],
            args=e["args"],
            output=e["output"],
            approved_by=e["approvedBy"],
            ts=e["ts"],
        )
        event.seq = seq
        events.append(event)
    got = [
        {
            "ruleId": v.rule_id,
            "severity": v.severity,
            "confidence": v.confidence,
            "evidenceSeqs": v.evidence_seqs,
            "frameworkRef": v.framework_ref,
        }
        for v in offline_audit(
            events, demo["sessionId"], load_policy_pack("policies/eu_ai_act.yaml")
        )
    ]
    assert got == demo["findings"]
