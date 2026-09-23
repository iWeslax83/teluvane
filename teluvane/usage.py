# teluvane/teluvane/usage.py
import os
from datetime import datetime, timezone

from .db import get_pool

# How many hosted-key (non-BYOK) tribunal audits a paid org gets per calendar month before
# falling back to the offline detector. Keeps a runaway org from spending unbounded amounts
# of our Anthropic budget on a flat monthly plan. Starter and Pro get separate caps; Free
# gets none (0), it never rides the hosted key.
HOSTED_AUDIT_MONTHLY_LIMIT_STARTER = int(os.environ.get("HOSTED_AUDIT_MONTHLY_LIMIT_STARTER", "15"))
HOSTED_AUDIT_MONTHLY_LIMIT_PRO = int(os.environ.get("HOSTED_AUDIT_MONTHLY_LIMIT_PRO", "50"))


def hosted_audit_limit_for_plan(plan: str) -> int:
    return {
        "starter": HOSTED_AUDIT_MONTHLY_LIMIT_STARTER,
        "pro": HOSTED_AUDIT_MONTHLY_LIMIT_PRO,
    }.get(plan, 0)


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def hosted_audit_count(org_id: str, period: str | None = None) -> int:
    period = period or current_period()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count FROM hosted_audit_usage WHERE org_id=%s AND period=%s", (org_id, period)
        )
        row = cur.fetchone()
    return row[0] if row else 0


def under_hosted_audit_limit(org_id: str, plan: str) -> bool:
    return hosted_audit_count(org_id) < hosted_audit_limit_for_plan(plan)


def increment_hosted_audit_usage(org_id: str, period: str | None = None) -> int:
    period = period or current_period()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO hosted_audit_usage(org_id,period,count) VALUES(%s,%s,1) "
            "ON CONFLICT (org_id,period) DO UPDATE SET count = hosted_audit_usage.count + 1 "
            "RETURNING count",
            (org_id, period),
        )
        new_count = cur.fetchone()[0]
        conn.commit()
    return new_count
