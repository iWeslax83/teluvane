"""Cooldown + monthly cap for the manual POST /anchor/run trigger, so a Pro org
cannot burn the shared signer wallet by spamming forced anchor passes."""
import time
from datetime import datetime, timezone

_last_run: dict[str, float] = {}
_month_count: dict[tuple[str, str], int] = {}


def _month_key(org_id: str) -> tuple[str, str]:
    return (org_id, datetime.now(timezone.utc).strftime("%Y-%m"))


def check_and_record(org_id: str, cooldown_minutes: int, monthly_cap: int) -> str | None:
    now = time.time()
    last = _last_run.get(org_id, 0)
    if now - last < cooldown_minutes * 60:
        return "cooldown"
    key = _month_key(org_id)
    if _month_count.get(key, 0) >= monthly_cap:
        return "monthly-cap"
    _last_run[org_id] = now
    _month_count[key] = _month_count.get(key, 0) + 1
    return None
