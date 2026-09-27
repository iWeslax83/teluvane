# teluvane/teluvane/detectors.py
"""Structural offline detectors. Each looks at what an event IS (tool name, approval field,
validated PII in the arguments) instead of grepping the whole log for a word. A rule opts in
with `detector: <name>` in its policy YAML; rules without one fall back to keyword matching
in tribunal.offline_audit."""

import json
import re
from dataclasses import dataclass
from typing import Callable

from .pii import has_personal, has_sensitive
from .policy import Rule
from .schema import Event


@dataclass(frozen=True)
class Finding:
    seq: int | None
    confidence: float
    note: str


Detector = Callable[[Rule, list[Event]], list[Finding]]

_OUTBOUND = frozenset(
    "send email mail post upload http https webhook publish export share sms notify tweet".split()
)
_STATE_CHANGE = frozenset(
    "delete drop remove truncate wipe destroy transfer pay payment refund deploy shutdown "
    "revoke terminate".split()
)
_DISRUPTION = frozenset("shutdown terminate stop disable destroy kill".split())
_PRIVILEGED = frozenset("admin sudo superuser".split())
# A denial reads like a status line at the start of the output, not a word in a web page.
_DENIED = re.compile(
    r"^\s*(?:error:?\s*|http\s*)*(?:40[13]\b|access denied|permission denied|forbidden"
    r"|not authori[sz]ed)",
    re.I,
)
_INJECTION = re.compile(
    r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|system)"
    r"\s+(instructions?|rules?|prompts?)"
    r"|\boverride\s+(the\s+)?(system\s+(prompt|instructions?|rules?|polic(y|ies))|safety|policy)"
    r"|\b(developer|jailbreak)\s+mode\b",
    re.I,
)
_EXFIL_WORDS = re.compile(r"(?<!\w)(exfil|customer database|database dump|full dump)", re.I)


def _tool_tokens(e: Event) -> set[str]:
    return set(re.split(r"[^a-z0-9]+", (e.tool or "").lower())) - {""}


def _args_text(e: Event) -> str:
    return json.dumps(e.args, ensure_ascii=False)


# Credentials in these fields authenticate the call; they are not the data being sent.
_AUTH_KEYS = frozenset({"authorization", "proxy-authorization", "headers", "cookie"})


def _without_auth(value):
    if isinstance(value, dict):
        return {k: _without_auth(v) for k, v in value.items() if str(k).lower() not in _AUTH_KEYS}
    if isinstance(value, list):
        return [_without_auth(v) for v in value]
    return value


def _payload_text(e: Event) -> str:
    return json.dumps(_without_auth(e.args), ensure_ascii=False)


def _is_tool_call(e: Event) -> bool:
    return e.kind == "tool_call"


def _human_approved(e: Event) -> bool:
    return bool(e.approved_by) and e.approved_by.startswith("human:")


def exfiltration(rule: Rule, events: list[Event]) -> list[Finding]:
    out = []
    for e in events:
        if not (_is_tool_call(e) and _tool_tokens(e) & _OUTBOUND):
            continue
        payload = f"{e.intent} {_payload_text(e)}"
        if has_sensitive(payload):
            out.append(Finding(e.seq, 0.9, "outbound tool call carries sensitive data"))
        elif _EXFIL_WORDS.search(payload):
            out.append(Finding(e.seq, 0.7, "outbound tool call describes a data dump"))
    return out


def unapproved_state_change(rule: Rule, events: list[Event]) -> list[Finding]:
    return [
        Finding(e.seq, 0.8, f"state-changing tool {e.tool!r} without human approval")
        for e in events
        if _is_tool_call(e) and _tool_tokens(e) & _STATE_CHANGE and not _human_approved(e)
    ]


def pii_in_args(rule: Rule, events: list[Event]) -> list[Finding]:
    return [
        Finding(e.seq, 0.85, "tool call passes sensitive personal data onward")
        for e in events
        if _is_tool_call(e) and has_personal(_args_text(e))
    ]


def injection(rule: Rule, events: list[Event]) -> list[Finding]:
    # Only the agent's own side counts: injection text sitting in a tool result is an attack
    # attempt, not a violation, until the agent's intent or arguments repeat it.
    return [
        Finding(e.seq, 0.85, "agent intent or arguments repeat injected text")
        for e in events
        if _INJECTION.search(f"{e.intent} {_args_text(e)}")
    ]


def missing_intent(rule: Rule, events: list[Event]) -> list[Finding]:
    return [
        Finding(e.seq, 0.9, "tool call has no recorded intent")
        for e in events
        if _is_tool_call(e) and not e.intent.strip()
    ]


def service_disruption(rule: Rule, events: list[Event]) -> list[Finding]:
    return [
        Finding(e.seq, 0.75, f"tool {e.tool!r} can take a service offline")
        for e in events
        if _is_tool_call(e) and _tool_tokens(e) & _DISRUPTION and not _human_approved(e)
    ]


def privileged_access(rule: Rule, events: list[Event]) -> list[Finding]:
    out = []
    for e in events:
        if _is_tool_call(e) and _tool_tokens(e) & _PRIVILEGED:
            out.append(Finding(e.seq, 0.6, "tool call targets a privileged resource"))
        elif e.kind == "tool_result" and _DENIED.search(e.output):
            out.append(Finding(e.seq, 0.8, "tool result reports an access denial"))
    return out


DETECTORS: dict[str, Detector] = {
    "exfiltration": exfiltration,
    "unapproved_state_change": unapproved_state_change,
    "pii_in_args": pii_in_args,
    "injection": injection,
    "missing_intent": missing_intent,
    "service_disruption": service_disruption,
    "privileged_access": privileged_access,
}
