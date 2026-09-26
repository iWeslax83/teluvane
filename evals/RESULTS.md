# Detection results

Synthetic sessions written by the maintainers. See `README.md` before quoting any number
from this file: the detectors and the sessions share authors, so these scores show the rules
separate the cases we thought of, and nothing more. Independent scenarios are welcome
(`CONTRIBUTING.md`).

## Baseline: whole-log keyword match

detector: legacy  scenarios: 47

| rule | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| data_exfiltration | 2 | 5 | 3 | 0.29 | 0.40 | 0.33 |
| unauthorized_state_change | 2 | 2 | 3 | 0.50 | 0.40 | 0.44 |
| pii_mishandling | 2 | 1 | 5 | 0.67 | 0.29 | 0.40 |
| instruction_override | 2 | 3 | 3 | 0.40 | 0.40 | 0.40 |
| missing_traceability | 0 | 0 | 5 | 0.00 | 0.00 | 0.00 |
| **all rules** | 8 | 11 | 19 | 0.42 | 0.30 | 0.35 |

## Structural offline detectors

detector: offline  scenarios: 47

| rule | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| data_exfiltration | 5 | 1 | 0 | 0.83 | 1.00 | 0.91 |
| unauthorized_state_change | 5 | 1 | 0 | 0.83 | 1.00 | 0.91 |
| pii_mishandling | 7 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| instruction_override | 5 | 1 | 0 | 0.83 | 1.00 | 0.91 |
| missing_traceability | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **all rules** | 27 | 3 | 0 | 0.90 | 1.00 | 0.95 |
