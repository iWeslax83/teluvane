# teluvane/teluvane/schema.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


EventKind = Literal["llm_call", "tool_call", "tool_result", "approval", "error"]


class Event(BaseModel):
    """One recorded agent step. `seq` and `hash` are assigned by the store."""

    agent_id: str
    session_id: str
    kind: EventKind
    intent: str = ""  # model's stated reason for the step
    tool: Optional[str] = None
    args: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    approved_by: Optional[str] = None  # "human:<id>" | "auto" | None
    model: Optional[str] = None  # llm_call only: model id, for cost tracking
    input_tokens: Optional[int] = None  # llm_call only
    output_tokens: Optional[int] = None  # llm_call only
    cost_usd: Optional[float] = None  # computed by the store if omitted and model is known
    ts: str = Field(default_factory=utcnow_iso)
    # assigned on persist:
    hash_version: Optional[int] = None  # 1 = plaintext in the hash, 2 = payload commitment
    payload_commitment: Optional[str] = None  # v2 only
    erased: bool = False  # v2 only: the payload was erased, the chain hash still verifies
    seq: Optional[int] = None
    prev_hash: Optional[str] = None
    hash: Optional[str] = None
    org_id: Optional[str] = None  # tenant; assigned by the store on persist


class Verdict(BaseModel):
    session_id: str
    org_id: Optional[str] = None  # tenant; assigned by the store on persist
    rule_id: str
    severity: Literal["low", "medium", "high", "critical"]
    violation: bool
    confidence: float  # 0..1
    evidence_seqs: list[int] = Field(default_factory=list)
    rationale: str = ""
    framework_ref: str = ""
    ts: str = Field(default_factory=utcnow_iso)
