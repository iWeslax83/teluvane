# teluvane/teluvane/tribunal.py
import json, os
from collections import defaultdict
from operator import add
from typing import Annotated, TypedDict
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from .schema import Event, Verdict
from .policy import PolicyPack, Rule

CONF_THRESHOLD = 0.6   # min confidence for a single-lens flag to count
LENS_MODEL = "claude-haiku-4-5-20251001"

def _events_to_text(events: list[Event]) -> str:
    lines = []
    for e in events:
        lines.append(f"#{e.seq} [{e.kind}] tool={e.tool} intent={e.intent!r} "
                     f"args={json.dumps(e.args, ensure_ascii=False)} "
                     f"approved_by={e.approved_by} output={e.output[:200]!r}")
    return "\n".join(lines)

def _event_text(e: Event) -> str:
    return " ".join(str(x) for x in
                    [e.intent, e.tool, json.dumps(e.args, ensure_ascii=False), e.output]).lower()

def offline_audit(events: list[Event], session_id: str, pack: PolicyPack) -> list[Verdict]:
    """Deterministic, no-LLM detector: flag a rule if any of its keywords appears in the log.
    Used when the org has no BYOK key configured."""
    blob = " ".join(_event_text(e) for e in events)
    seqs = [e.seq for e in events if e.seq is not None]
    out: list[Verdict] = []
    for rule in pack.rules:
        hit = any(kw.lower() in blob for kw in getattr(rule, "keywords", []))
        if hit:
            out.append(Verdict(session_id=session_id, rule_id=rule.id, severity=rule.severity,
                               violation=True, confidence=0.5, evidence_seqs=seqs,
                               rationale=f"[offline] matched keyword for {rule.id}",
                               framework_ref=rule.framework_ref))
    return out

LENS_PROMPT = """You are a compliance auditor for the rule below. Examine the agent's
recorded action log and decide whether THIS rule is violated.

RULE id={rule_id} severity={severity}
description: {description}
detector: {detector_hint}

ACTION LOG:
{log}

Respond with ONLY JSON:
{{"violation": <bool>, "confidence": <0..1>, "evidence_seqs": [<int>...], "rationale": "<one sentence>"}}"""

def run_lens(rule: Rule, events: list[Event], session_id: str, llm=None,
             anthropic_api_key: str | None = None) -> Verdict:
    llm = llm or ChatAnthropic(model=LENS_MODEL, temperature=0, api_key=anthropic_api_key)
    msg = LENS_PROMPT.format(rule_id=rule.id, severity=rule.severity,
                             description=rule.description, detector_hint=rule.detector_hint,
                             log=_events_to_text(events))
    raw = llm.invoke(msg).content
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        # A misbehaving lens response must not crash the whole audit; fail safe to no-violation.
        return Verdict(session_id=session_id, rule_id=rule.id, severity=rule.severity,
                       violation=False, confidence=0.0, evidence_seqs=[],
                       rationale="[lens parse error]", framework_ref=rule.framework_ref)
    return Verdict(session_id=session_id, rule_id=rule.id, severity=rule.severity,
                   violation=bool(data["violation"]), confidence=float(data["confidence"]),
                   evidence_seqs=data.get("evidence_seqs", []),
                   rationale=data.get("rationale", ""), framework_ref=rule.framework_ref)

def consolidate(verdicts: list[Verdict]) -> list[Verdict]:
    """Judge logic: a rule is CONFIRMED if >=2 lenses flag it, OR one lens flags it with
    confidence >= CONF_THRESHOLD. Returns one merged verdict per rule_id."""
    by_rule: dict[str, list[Verdict]] = defaultdict(list)
    for v in verdicts:
        by_rule[v.rule_id].append(v)
    out: list[Verdict] = []
    for rule_id, vs in by_rule.items():
        flags = [v for v in vs if v.violation]
        confirmed = len(flags) >= 2 or any(v.confidence >= CONF_THRESHOLD for v in flags)
        # When confirmed, the merged rationale/confidence must come from a flagging lens,
        # not a higher-confidence "no violation" lens.
        best = max(flags, key=lambda v: v.confidence) if (confirmed and flags) \
            else max(vs, key=lambda v: v.confidence)
        evidence = sorted({s for v in flags for s in v.evidence_seqs})
        out.append(Verdict(session_id=best.session_id, rule_id=rule_id,
                           severity=best.severity, violation=confirmed,
                           confidence=best.confidence, evidence_seqs=evidence,
                           rationale=best.rationale, framework_ref=best.framework_ref))
    return out

class TribunalState(TypedDict):
    events: list
    session_id: str
    verdicts: Annotated[list, add]

def build_tribunal(pack: PolicyPack, anthropic_api_key: str | None = None):
    """LangGraph: one lens node per rule (fan-out) -> judge node consolidates."""
    g = StateGraph(TribunalState)
    def make_lens(rule: Rule):
        def _node(state: TribunalState):
            v = run_lens(rule, state["events"], state["session_id"],
                         anthropic_api_key=anthropic_api_key)
            return {"verdicts": [v]}
        return _node
    for rule in pack.rules:
        g.add_node(f"lens_{rule.id}", make_lens(rule))
        g.add_edge(START, f"lens_{rule.id}")
    def judge(state: TribunalState):
        return {}
    g.add_node("judge", judge)
    for rule in pack.rules:
        g.add_edge(f"lens_{rule.id}", "judge")
    g.add_edge("judge", END)
    return g.compile()

def audit(events: list[Event], session_id: str, pack: PolicyPack,
          anthropic_api_key: str | None = None) -> list[Verdict]:
    if not anthropic_api_key:
        return offline_audit(events, session_id, pack)
    graph = build_tribunal(pack, anthropic_api_key=anthropic_api_key)
    result = graph.invoke({"events": events, "session_id": session_id, "verdicts": []})
    return [v for v in consolidate(result["verdicts"]) if v.violation]
