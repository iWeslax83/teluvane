# TELUVANE detection evals

Synthetic labeled sessions for the EU AI Act pack, and a runner that scores a detector on them.

## What this measures, and what it does not

- The sessions are written by hand by the maintainers in `evals/scenarios.py`. They are not
  customer data.
- The offline detectors were written by the same people who wrote the sessions. High scores
  show the rules separate the cases we thought of. They say nothing yet about cases we did
  not think of. Independent scenarios (see `CONTRIBUTING.md`) are how that gap closes.
- Sessions marked `hard` are look-alikes we already know the offline detector gets wrong.
  They stay in the set on purpose so the numbers include them.
- A session is one label set: the rules a reasonable reviewer would say it violates.

## Run

From the repo root:

```bash
python -m evals.run_eval --detector legacy    # the old whole-log keyword match, as a baseline
python -m evals.run_eval --detector offline   # structural detectors, no API key needed
ANTHROPIC_API_KEY=... python -m evals.run_eval --detector live
```

`live` makes one model call per scenario, per rule, per lens, and spends real API credit.
Check current pricing first. Never run it in CI.

Each run prints a per-rule table and writes `evals/results/<detector>.json`, including every
miss, so a regression shows up as a named scenario, not just a lower number.

`pytest tests/test_evals.py` checks the dataset is well formed and that the structural
detectors beat the legacy baseline. It does not pin exact scores.
