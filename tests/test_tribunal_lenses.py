import json

from teluvane.policy import PolicyPack, Rule
from teluvane.schema import Event, Verdict
from teluvane.tribunal import (
    LENSES,
    PARSE_ERROR,
    _events_to_text,
    audit,
    consolidate,
    lens_names,
    run_lens,
)

RULE = Rule(id="r1", description="d", severity="high", framework_ref="x", detector_hint="h")


def v(viol, conf, rationale="ok", rule="r1", seqs=(2,)):
    return Verdict(
        session_id="s",
        rule_id=rule,
        severity="high",
        violation=viol,
        confidence=conf,
        evidence_seqs=list(seqs),
        rationale=rationale,
        framework_ref="x",
    )


def test_majority_of_three_confirms():
    out = consolidate([v(True, 0.9, "a"), v(True, 0.6, "b"), v(False, 0.95, "c")])
    assert out[0].violation and out[0].rationale == "a"


def test_minority_does_not_confirm():
    out = consolidate([v(True, 0.95), v(False, 0.9), v(False, 0.9)])
    assert not out[0].violation


def test_two_lens_tie_does_not_confirm():
    assert not consolidate([v(True, 0.95), v(False, 0.5)])[0].violation


def test_single_lens_needs_threshold():
    assert consolidate([v(True, 0.6)])[0].violation
    assert not consolidate([v(True, 0.4)])[0].violation


def test_parse_errors_are_not_votes():
    out = consolidate([v(True, 0.9), v(True, 0.8), v(False, 0.0, PARSE_ERROR)])
    assert out[0].violation
    only_err = consolidate([v(False, 0.0, PARSE_ERROR)])
    assert not only_err[0].violation


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def invoke(self, msg):
        self.prompts.append(msg)

        class R:
            content = self.replies.pop(0)

        return R()


def test_run_lens_uses_stance_and_parses():
    llm = FakeLLM(
        [json.dumps({"violation": True, "confidence": 0.8, "evidence_seqs": [1], "rationale": "x"})]
    )
    got = run_lens(RULE, [], "s", llm=llm, lens="skeptic")
    assert got.violation and LENSES["skeptic"] in llm.prompts[0]


def test_run_lens_missing_key_is_parse_error():
    llm = FakeLLM(['{"confidence": 0.9}'])
    assert run_lens(RULE, [], "s", llm=llm).rationale == PARSE_ERROR


def test_lens_count_env(monkeypatch):
    monkeypatch.setenv("TRIBUNAL_LENS_COUNT", "2")
    assert lens_names() == ["auditor", "skeptic"]
    monkeypatch.setenv("TRIBUNAL_LENS_COUNT", "99")
    assert len(lens_names()) == 3
    monkeypatch.setenv("TRIBUNAL_LENS_COUNT", "nope")
    assert len(lens_names()) == 3


def test_log_window_drops_oldest_and_says_so():
    events = []
    for i in range(50):
        e = Event(agent_id="a", session_id="s", kind="llm_call", intent="x" * 100)
        e.seq = i + 1
        events.append(e)
    text = _events_to_text(events, max_chars=2000)
    assert text.startswith("[")
    assert "earlier events omitted" in text.splitlines()[0]
    assert "#50 " in text and "#1 " not in text


def test_audit_runs_lenses_per_rule(monkeypatch):
    calls = []

    def fake_run_lens(rule, events, session_id, llm=None, anthropic_api_key=None, lens="auditor"):
        calls.append((rule.id, lens))
        return v(lens != "skeptic", 0.9, f"from {lens}", rule=rule.id)

    monkeypatch.setattr("teluvane.tribunal.run_lens", fake_run_lens)
    pack = PolicyPack(framework="F", version="1", rules=[RULE])
    out = audit([], "s", pack, anthropic_api_key="k")
    assert sorted(calls) == [("r1", "auditor"), ("r1", "literalist"), ("r1", "skeptic")]
    assert len(out) == 1 and out[0].violation
