# teluvane/evals/legacy.py
"""The pre-detector offline audit (whole-log substring match), frozen as a baseline so the
benchmark can show what the structural detectors changed."""

from teluvane.policy import PolicyPack
from teluvane.schema import Event, Verdict
from teluvane.tribunal import _event_text


def legacy_offline_audit(events: list[Event], session_id: str, pack: PolicyPack) -> list[Verdict]:
    blob = " ".join(_event_text(e) for e in events)
    seqs = [e.seq for e in events if e.seq is not None]
    return [
        Verdict(
            session_id=session_id,
            rule_id=r.id,
            severity=r.severity,
            violation=True,
            confidence=0.5,
            evidence_seqs=seqs,
            rationale=f"[offline] matched keyword for {r.id}",
            framework_ref=r.framework_ref,
        )
        for r in pack.rules
        if any(kw.lower() in blob for kw in r.keywords)
    ]
