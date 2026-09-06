# teluvane/teluvane/webhooks.py
import hashlib, hmac, ipaddress, json, logging, secrets, socket
from typing import Optional
from urllib.parse import urlparse
import httpx
from .db import get_pool
from .schema import Verdict

TIMEOUT_SECONDS = 5

_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


class WebhookUrlError(ValueError):
    """Raised for a webhook URL that is malformed or points somewhere it must not
    (loopback, private ranges, link-local, including the cloud metadata IP)."""


def validate_webhook_url(url: str) -> None:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        raise WebhookUrlError("webhook url is malformed")
    if parsed.scheme not in ("http", "https"):
        raise WebhookUrlError("webhook url must be http(s)")
    if not host:
        raise WebhookUrlError("webhook url has no host")
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_HOST_SUFFIXES):
        raise WebhookUrlError("webhook url host is not routable")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _ip_is_blocked(literal):
        raise WebhookUrlError("webhook url points at a non-public address")
    try:
        infos = socket.getaddrinfo(host, port or None, proto=socket.IPPROTO_TCP)
    except OSError:
        # Can't resolve right now (e.g. offline). The literal check above still stands;
        # send_webhook re-validates before every delivery.
        return
    for info in infos:
        if _ip_is_blocked(ipaddress.ip_address(info[4][0])):
            raise WebhookUrlError("webhook url resolves to a non-public address")

def set_webhook(org_id: str, url: str) -> str:
    """Create or replace the org's webhook, returning its signing secret."""
    validate_webhook_url(url)
    secret = secrets.token_hex(24)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_webhooks(org_id,url,secret) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id) DO UPDATE SET url=EXCLUDED.url, secret=EXCLUDED.secret, "
            "created_at=now()", (org_id, url, secret))
        conn.commit()
    return secret

def get_webhook(org_id: str) -> Optional[dict]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT url, secret FROM org_webhooks WHERE org_id=%s", (org_id,))
        row = cur.fetchone()
    return {"url": row[0], "secret": row[1]} if row else None

def delete_webhook(org_id: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM org_webhooks WHERE org_id=%s", (org_id,))
        conn.commit()

def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

def _slack_payload(org_id: str, session_id: str, verdicts: list[Verdict]) -> dict:
    lines = [f"*{v.rule_id}* ({v.severity}) — {v.rationale}" for v in verdicts]
    return {"text": f"TELUVANE: {len(verdicts)} violation(s) in session `{session_id}`\n" + "\n".join(lines)}

def send_webhook(org_id: str, session_id: str, verdicts: list[Verdict]) -> None:
    """Fire-and-forget: a broken or slow receiving endpoint must never fail the audit that
    triggered it, so every failure mode here is caught and only logged."""
    if not verdicts:
        return
    hook = get_webhook(org_id)
    if not hook:
        return
    try:
        validate_webhook_url(hook["url"])
    except WebhookUrlError:
        logging.warning("refusing webhook delivery for org %s: url no longer routable", org_id)
        return
    is_slack = "hooks.slack.com" in hook["url"]
    payload = _slack_payload(org_id, session_id, verdicts) if is_slack else {
        "org_id": org_id, "session_id": session_id,
        "verdicts": [v.model_dump() for v in verdicts],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if not is_slack:
        headers["X-Teluvane-Signature"] = _sign(hook["secret"], body)
    try:
        httpx.post(hook["url"], content=body, headers=headers, timeout=TIMEOUT_SECONDS)
    except Exception:
        logging.exception("webhook delivery failed for org %s", org_id)
