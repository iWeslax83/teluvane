# teluvane/evals/run_eval.py
"""Score a detector against evals.scenarios. Usage:
    python -m evals.run_eval --detector legacy|offline|live [--out evals/results]
`live` needs ANTHROPIC_API_KEY and spends real API credit (5 rules x 3 lenses x scenarios)."""

import argparse
import json
import os
import pathlib
from collections import Counter

from teluvane.policy import load_policy_pack
from teluvane.tribunal import audit, offline_audit

from .legacy import legacy_offline_audit
from .scenarios import RULES, all_scenarios

PACK = "policies/eu_ai_act.yaml"


def run(detector: str) -> dict:
    pack = load_policy_pack(PACK)
    scenarios = all_scenarios()
    counts = {r: Counter() for r in RULES}
    misses = []
    for s in scenarios:
        if detector == "legacy":
            verdicts = legacy_offline_audit(s.events, s.session_id, pack)
        elif detector == "offline":
            verdicts = offline_audit(s.events, s.session_id, pack)
        else:
            verdicts = audit(s.events, s.session_id, pack, os.environ["ANTHROPIC_API_KEY"])
        flagged = {v.rule_id for v in verdicts if v.violation}
        for r in RULES:
            exp, got = r in s.expected, r in flagged
            counts[r]["tp" if exp and got else "fn" if exp else "fp" if got else "tn"] += 1
            if exp != got:
                misses.append({"scenario": s.id, "rule": r, "expected": exp, "hard": s.hard})
    return {
        "detector": detector,
        "scenarios": len(scenarios),
        "counts": {r: dict(c) for r, c in counts.items()},
        "misses": misses,
    }


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def summarize(result: dict) -> str:
    lines = [
        f"detector: {result['detector']}  scenarios: {result['scenarios']}",
        "",
        "| rule | TP | FP | FN | precision | recall | F1 |",
        "|---|---|---|---|---|---|---|",
    ]
    tot = Counter()
    for rule, c in result["counts"].items():
        p, r, f = _prf(c.get("tp", 0), c.get("fp", 0), c.get("fn", 0))
        counts = f"{c.get('tp', 0)} | {c.get('fp', 0)} | {c.get('fn', 0)}"
        lines.append(f"| {rule} | {counts} | {p:.2f} | {r:.2f} | {f:.2f} |")
        tot.update(c)
    p, r, f = _prf(tot["tp"], tot["fp"], tot["fn"])
    lines.append(
        f"| **all rules** | {tot['tp']} | {tot['fp']} | {tot['fn']} | {p:.2f} | {r:.2f} | {f:.2f} |"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", choices=["legacy", "offline", "live"], required=True)
    ap.add_argument("--out", default="evals/results")
    a = ap.parse_args()
    result = run(a.detector)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.detector}.json").write_text(json.dumps(result, indent=2))
    print(summarize(result))
