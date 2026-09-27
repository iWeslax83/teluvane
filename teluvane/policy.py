# teluvane/teluvane/policy.py
from typing import Literal

import yaml
from pydantic import BaseModel

Severity = Literal["low", "medium", "high", "critical"]


class Rule(BaseModel):
    id: str
    description: str
    severity: Severity
    framework_ref: str
    detector_hint: str
    keywords: list[str] = []  # fallback for the offline (no-LLM) detector
    detector: str | None = None  # name in teluvane.detectors.DETECTORS; wins over keywords


class PolicyPack(BaseModel):
    framework: str
    version: str
    rules: list[Rule]


def load_policy_pack(path: str) -> PolicyPack:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PolicyPack(**data)
