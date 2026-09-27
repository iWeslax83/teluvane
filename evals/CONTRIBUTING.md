# Adding scenarios

New scenarios are the most useful outside contribution: they test the detectors on cases the
authors did not think of.

1. Add a `sc(...)` entry to `all_scenarios()` in `evals/scenarios.py`.
2. `sc(id, expected_rules, *events, hard=False, note="")`. `expected_rules` is the set of
   rules a reasonable reviewer says the session violates. Use `set()` for a benign session.
3. Build events with `tc(...)` (tool call), `res(...)` (tool result) and `llm(...)`.
4. One behavior per scenario. If a benign session merely looks suspicious, that is exactly
   the kind we want.
5. Set `hard=True` when you expect the current offline detector to get it wrong, and say why
   in `note`. Do not tune the detectors to make your scenario pass in the same change.
6. Use only documented test data, never real personal data: card `4111 1111 1111 1111`, SSN
   `078-05-1120`, IBAN `GB82 WEST 1234 5698 7654 32`, national id `10000000146`.
7. Run `pytest tests/test_evals.py` and `python -m evals.run_eval --detector offline`, and
   include the new per-rule table in the pull request.
