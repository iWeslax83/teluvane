# teluvane/teluvane/pii.py
"""Validated PII and secret detection for the offline tribunal. Checksum validation
(Luhn, IBAN mod-97, TC Kimlik) keeps look-alike numbers from being flagged."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiHit:
    kind: str  # "ssn" | "card" | "iban" | "tckn" | "email" | "secret"
    text: str


# Kinds that identify a person on their own. Email is deliberately not here: a recipient
# address appears in almost every legitimate send.
PERSONAL_KINDS = frozenset({"ssn", "card", "iban", "tckn"})
# Personal data plus credentials: what must not leave in an outbound call.
SENSITIVE_KINDS = PERSONAL_KINDS | {"secret"}

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
_TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
_SECRETS = re.compile(
    r"AKIA[0-9A-Z]{16}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|sk-ant-[A-Za-z0-9_-]{20,}"
    r"|\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*"
)


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _iban_ok(raw: str) -> bool:
    s = raw.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    rearranged = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in rearranged)
    return int(num) % 97 == 1


def _tckn_ok(s: str) -> bool:
    d = [int(c) for c in s]
    if d[0] == 0:
        return False
    if (sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10 != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def find_pii(text: str) -> list[PiiHit]:
    hits: list[PiiHit] = []
    for m in _EMAIL.finditer(text):
        hits.append(PiiHit("email", m.group()))
    for m in _SSN.finditer(text):
        hits.append(PiiHit("ssn", m.group()))
    for m in _CARD.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            hits.append(PiiHit("card", m.group()))
    for m in _IBAN.finditer(text):
        if _iban_ok(m.group()):
            hits.append(PiiHit("iban", m.group()))
    for m in _TCKN.finditer(text):
        if _tckn_ok(m.group()):
            hits.append(PiiHit("tckn", m.group()))
    for m in _SECRETS.finditer(text):
        hits.append(PiiHit("secret", m.group()))
    return hits


def has_sensitive(text: str) -> bool:
    return any(h.kind in SENSITIVE_KINDS for h in find_pii(text))


def has_personal(text: str) -> bool:
    return any(h.kind in PERSONAL_KINDS for h in find_pii(text))
