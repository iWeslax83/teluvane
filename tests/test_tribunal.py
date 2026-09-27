# teluvane/tests/test_tribunal.py
from teluvane.schema import Verdict
from teluvane.tribunal import consolidate


def v(rule, viol, conf, sev="high"):
    return Verdict(
        session_id="s1",
        rule_id=rule,
        severity=sev,
        violation=viol,
        confidence=conf,
        evidence_seqs=[2],
        framework_ref="x",
    )


def test_consolidate_requires_consensus_and_confidence():
    out = consolidate([v("data_exfiltration", True, 0.9), v("data_exfiltration", True, 0.8)])
    assert any(x.rule_id == "data_exfiltration" and x.violation for x in out)


def test_consolidate_drops_low_confidence_singletons():
    out = consolidate([v("pii_mishandling", True, 0.4)])
    assert all(not x.violation for x in out)


def test_consolidate_confirmed_uses_flagging_lens_rationale():
    # A non-flagging lens has higher confidence than the flagging ones; the merged
    # verdict must still be confirmed (2 of 3 flag) AND carry the top flagging lens's rationale.
    flag = Verdict(
        session_id="s1",
        rule_id="data_exfiltration",
        severity="critical",
        violation=True,
        confidence=0.7,
        evidence_seqs=[5],
        rationale="emailed DB externally",
        framework_ref="x",
    )
    clean = Verdict(
        session_id="s1",
        rule_id="data_exfiltration",
        severity="critical",
        violation=False,
        confidence=0.95,
        evidence_seqs=[],
        rationale="looks fine",
        framework_ref="x",
    )
    second_flag = flag.model_copy(update={"confidence": 0.65, "rationale": "agrees"})
    out = consolidate([clean, flag, second_flag])
    merged = next(x for x in out if x.rule_id == "data_exfiltration")
    assert merged.violation is True
    assert merged.rationale == "emailed DB externally"
