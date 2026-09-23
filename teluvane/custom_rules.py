# teluvane/teluvane/custom_rules.py
import logging

from pydantic import ValidationError

from .db import get_pool
from .policy import PolicyPack, Rule

log = logging.getLogger("teluvane.custom_rules")


def list_custom_rules(org_id: str) -> list[Rule]:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT rule_id, description, severity, framework_ref, detector_hint, keywords "
            "FROM org_policy_rules WHERE org_id=%s ORDER BY created_at",
            (org_id,),
        )
        rows = cur.fetchall()
    out: list[Rule] = []
    for r in rows:
        try:
            out.append(
                Rule(
                    id=r[0],
                    description=r[1],
                    severity=r[2],
                    framework_ref=r[3],
                    detector_hint=r[4],
                    keywords=list(r[5]),
                )
            )
        except ValidationError:
            # A malformed legacy row (e.g. an out-of-range severity written before the
            # API validated it) must not wedge every audit for this org.
            log.warning("skipping invalid custom rule %s for org %s", r[0], org_id)
    return out


def upsert_custom_rule(org_id: str, rule: Rule) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_policy_rules(org_id,rule_id,description,severity,framework_ref,"
            "detector_hint,keywords) VALUES(%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (org_id,rule_id) DO UPDATE SET description=EXCLUDED.description, "
            "severity=EXCLUDED.severity, framework_ref=EXCLUDED.framework_ref, "
            "detector_hint=EXCLUDED.detector_hint, keywords=EXCLUDED.keywords",
            (
                org_id,
                rule.id,
                rule.description,
                rule.severity,
                rule.framework_ref,
                rule.detector_hint,
                rule.keywords,
            ),
        )
        conn.commit()


def delete_custom_rule(org_id: str, rule_id: str) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM org_policy_rules WHERE org_id=%s AND rule_id=%s", (org_id, rule_id)
        )
        conn.commit()


def effective_pack(org_id: str, base: PolicyPack) -> PolicyPack:
    """Base rules plus this org's custom rules, merged for one audit run. A custom rule_id
    that collides with a base rule's id overrides it, so orgs can tighten a stock rule."""
    custom = {r.id: r for r in list_custom_rules(org_id)}
    merged = [custom.pop(r.id, r) for r in base.rules]
    merged.extend(custom.values())
    return PolicyPack(framework=base.framework, version=base.version, rules=merged)
