from evals.run_eval import _prf, run
from evals.scenarios import RULES, all_scenarios


def _micro_f1(result: dict) -> float:
    tp = sum(c.get("tp", 0) for c in result["counts"].values())
    fp = sum(c.get("fp", 0) for c in result["counts"].values())
    fn = sum(c.get("fn", 0) for c in result["counts"].values())
    return _prf(tp, fp, fn)[2]


def test_scenario_ids_are_unique_and_labels_are_known_rules():
    scenarios = all_scenarios()
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids))
    assert all(s.expected <= set(RULES) for s in scenarios)


def test_every_rule_has_positive_and_negative_examples():
    scenarios = all_scenarios()
    for rule in RULES:
        assert any(rule in s.expected for s in scenarios), rule
        assert any(rule not in s.expected for s in scenarios), rule


def test_hard_negatives_are_marked_and_expect_no_violation():
    hard = [s for s in all_scenarios() if s.hard]
    assert hard and all(not s.expected for s in hard)


def test_structural_detectors_beat_the_legacy_baseline():
    assert _micro_f1(run("offline")) > _micro_f1(run("legacy"))


def test_prf_handles_empty_denominators():
    assert _prf(0, 0, 0) == (0.0, 0.0, 0.0)
    assert _prf(3, 1, 1) == (0.75, 0.75, 0.75)
