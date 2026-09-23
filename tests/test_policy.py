# teluvane/tests/test_policy.py
from teluvane.policy import load_policy_pack


def test_load_policy_pack():
    pack = load_policy_pack("policies/eu_ai_act.yaml")
    assert pack.framework == "EU AI Act"
    ids = {r.id for r in pack.rules}
    assert {"data_exfiltration", "instruction_override"} <= ids
    r = next(r for r in pack.rules if r.id == "data_exfiltration")
    assert r.severity == "critical" and r.framework_ref


def test_all_built_in_packs_load_and_have_distinct_rules():
    packs = {
        name: load_policy_pack(f"policies/{name}.yaml")
        for name in ["eu_ai_act", "soc2", "nist_ai_rmf", "iso42001"]
    }
    frameworks = {p.framework for p in packs.values()}
    assert len(frameworks) == 4  # each pack names a distinct framework
    for name, pack in packs.items():
        assert len(pack.rules) >= 4, f"{name} pack looks like a stub, not a real rule set"
        for rule in pack.rules:
            assert rule.keywords, f"{name}/{rule.id} has no offline detector keywords"
