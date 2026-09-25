# TELUVANE security overview

Written for a buyer's security or compliance reviewer, not an engineer. For implementation
detail, read the source referenced in each section.

## Data isolation
Every table in the database is scoped to an organization. The data layer enforces this at the
code level: a query missing an org filter throws before it runs, it isn't just a review
convention (`teluvane/store.py`, `_assert_scoped`). One org cannot read or write another org's
data through the API even if a query is written incorrectly upstream.

## Authentication
- Dashboard users authenticate through Supabase (email/password). Tokens are verified against Supabase's published JWKS when the project uses asymmetric signing keys, and against the project's shared JWT secret on older projects. Both paths are in teluvane/auth.py.
- Machine clients (agents posting events) authenticate with per-org API keys, separate from
  user login, so a leaked dashboard session can't be used to forge event ingestion and vice
  versa.

## Tamper evidence
Every recorded event is SHA-256 hash-chained to the previous event in its session. If a stored
row is edited or deleted after the fact, verifying the chain against its stored hash fails
visibly. This does not prevent a privileged database user from editing rows, it makes such
edits detectable rather than silent.

## Secrets and encryption
- `TELUVANE_SECRET_KEY` (Fernet symmetric key) encrypts sensitive stored values.
- No secrets are committed to source control; all credentials are injected as environment
  variables at deploy time (see `render.yaml`, `DEPLOY.md`).

## Third-party processors
- **Supabase**: auth and Postgres hosting.
- **Render**: API hosting.
- **Vercel**: frontend hosting.
- **LemonSqueezy**: billing, handles payment data, TELUVANE never stores card numbers.
- **Anthropic**: only called when a customer supplies their own API key (or uses the hosted
  Pro key) to run the live tribunal; the offline keyword detector runs with no third-party call.

## What we don't yet have
_[fill in honestly before sending to any pilot: SOC 2 status (none yet), data residency
options, backup/retention policy, incident response process, penetration test history. Do not
claim compliance you don't have; state the roadmap instead.]_

## Source of truth
This document summarizes `README.md`'s Architecture section and the code cited above. If either
changes, update this file in the same PR.
