import os

os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
from teluvane.custom_rules import (
    delete_custom_rule,
    effective_pack,
    list_custom_rules,
    upsert_custom_rule,
)
from teluvane.orgs import create_org
from teluvane.policy import PolicyPack, Rule


def test_upsert_list_delete_roundtrip():
    org = create_org("Acme", "u1")
    assert list_custom_rules(org) == []

    rule = Rule(
        id="no_offshore_pii",
        description="No PII leaves the EU",
        severity="high",
        framework_ref="Custom",
        detector_hint="check destination region",
        keywords=["offshore", "non-eu"],
    )
    upsert_custom_rule(org, rule)
    got = list_custom_rules(org)
    assert (
        len(got) == 1
        and got[0].id == "no_offshore_pii"
        and got[0].keywords == ["offshore", "non-eu"]
    )

    delete_custom_rule(org, "no_offshore_pii")
    assert list_custom_rules(org) == []


def test_effective_pack_merges_and_overrides():
    org = create_org("Acme", "u2")
    base = PolicyPack(
        framework="Test",
        version="1",
        rules=[
            Rule(
                id="a",
                description="A",
                severity="low",
                framework_ref="X",
                detector_hint="",
                keywords=["x"],
            ),
        ],
    )
    upsert_custom_rule(
        org,
        Rule(
            id="b",
            description="B",
            severity="high",
            framework_ref="Custom",
            detector_hint="",
            keywords=["y"],
        ),
    )
    merged = effective_pack(org, base)
    assert {r.id for r in merged.rules} == {"a", "b"}

    # a custom rule sharing the base rule's id overrides it
    upsert_custom_rule(
        org,
        Rule(
            id="a",
            description="A tightened",
            severity="critical",
            framework_ref="Custom",
            detector_hint="",
            keywords=["x", "z"],
        ),
    )
    merged2 = effective_pack(org, base)
    a = next(r for r in merged2.rules if r.id == "a")
    assert a.severity == "critical" and a.keywords == ["x", "z"]


def test_effective_pack_is_scoped_per_org():
    org_a = create_org("A", "ua")
    org_b = create_org("B", "ub")
    base = PolicyPack(framework="Test", version="1", rules=[])
    upsert_custom_rule(
        org_a,
        Rule(
            id="only_a",
            description="d",
            severity="low",
            framework_ref="Custom",
            detector_hint="",
            keywords=[],
        ),
    )
    assert [r.id for r in effective_pack(org_a, base).rules] == ["only_a"]
    assert effective_pack(org_b, base).rules == []
