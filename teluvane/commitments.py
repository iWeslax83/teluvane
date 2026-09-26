# teluvane/teluvane/commitments.py
"""Salted payload commitments for hash version 2 events.

An event's personal content (intent, args, output, approved_by) is not hashed into the chain
directly. The chain hashes commit(salt, payload) instead. The salt is random per event and is
stored next to the payload, so deleting that row leaves a commitment nobody can brute-force
back into the content, while every chain hash stays valid."""

import hashlib
import json
import os

from .schema import Event


def payload_of(e: Event) -> dict:
    return {
        "intent": e.intent,
        "args": e.args,
        "output": e.output,
        "approved_by": e.approved_by,
    }


def canonical_payload(payload: dict) -> str:
    """Compact, key-sorted JSON. The exact string is stored, so verification never depends on
    a database round trip preserving number formatting or key order."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def new_salt() -> str:
    return os.urandom(32).hex()


def commit(salt_hex: str, canonical: str) -> str:
    return hashlib.sha256(bytes.fromhex(salt_hex) + canonical.encode("utf-8")).hexdigest()
