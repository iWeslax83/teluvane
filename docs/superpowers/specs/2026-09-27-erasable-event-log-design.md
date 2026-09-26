# Erasable Event Log: Design

**Status:** proposed, 2026-09-27. **Implements:** `docs/superpowers/plans/2026-09-27-plan-3-erasable-event-log.md`.
This document describes engineering choices. It is not legal advice and makes no claim of legal
compliance.

## 1. Problem

Each event is chained by `sha256(canonical(prev, event))`, where the canonical form includes the
plaintext `intent`, `args`, `output` and `approved_by` (`teluvane/store.py`, `_event_canonical`,
frozen: "changing this invalidates every stored chain"). Consequences:

1. Removing personal data from an event changes its canonical form, so its hash and every later
   hash in the session stop verifying.
2. Anchored chain heads on Avalanche (`docs/onchain-anchoring.md`) then commit to data that no
   longer exists.
3. `GET /verify/public/{session_id}` returns the canonical strings of a public session, which for
   version 1 events contain the full plaintext. Publishing a session publishes its content.
4. There is no way to honor an erasure request (GDPR Art. 17), a storage limitation policy
   (Art. 5(1)(e)) or a Turkish KVKK deletion request without either lying about integrity or
   destroying the evidence.

## 2. Goals and non-goals

Goals: erase the personal content of recorded events on request or on a schedule while every
chain hash and every anchor stays valid; keep tamper evidence for content that has not been
erased; make silent deletion visible; keep old sessions verifiable; roll out without downtime.

Non-goals: deciding what the law requires of any customer; erasing data already exported or held
by processors and backups; identifying data subjects inside events (agents do not tag them);
masking personal data at ingest (see 4E); a dashboard UI (API first).

## 3. Decision

Hash a **commitment** to the personal content instead of the content (hash version 2).

- Payload: `{"intent", "args", "output", "approved_by"}` serialized as compact, key-sorted JSON
  (`commitments.canonical_payload`). The exact string is stored, so verification never depends on
  a database round trip preserving number formats or key order.
- Commitment: `sha256(salt_bytes || payload_utf8)` with a fresh random 32-byte salt per event
  (`commitments.commit`). The salt makes low-entropy content (a name, a short SSN field) safe
  against guessing once the payload row is gone.
- v2 canonical form: `{"v": 2, "prev", "org_id", "agent_id", "session_id", "kind", "tool", "ts",
  "payload_commitment"}`, key-sorted. Personal content is not in it.
- Storage: table `event_payloads(seq, org_id, salt, payload)`. The `events` row of a v2 event
  keeps blanks in `intent`, `args`, `output`, `approved_by`. Erasure deletes the
  `event_payloads` row.
- Versioning: `events.hash_version` (default 1). v1 events keep the frozen canonical form.
  `_event_canonical` dispatches on the event's own version, so one session can hold both, which
  happens for any session in flight during deploy.
- Verification: recompute each digest and check the link to the previous event (per session).
  For a v2 event whose payload still exists, also recompute the commitment from salt and payload
  and compare it to `events.payload_commitment`. Without this second check, editing
  `event_payloads` would not be noticed, which would weaken tamper evidence compared to v1.

Erasure (`Store.erase_payloads`), in one transaction: delete the payload rows for the chosen v2
events; insert an `erasure_log` row (event numbers, requester id, reason, time; never content);
replace the rationale of every verdict in the session with a fixed redaction notice, because
verdict rationales quote the log. v1 events are counted and reported, never silently skipped.

Accountability: `Store.verify_report` returns `chain_intact`, `erased_events`, and
`unexplained_erasures`, the number of v2 events with no payload that no `erasure_log` entry
covers.

Retention and hold: `org_retention(org_id, retention_days, legal_hold)`. An hourly job in the
scheduler erases payloads older than the window for orgs without a hold, with the same log
entries. A hold blocks both the job and manual erasure.

Public verification improves as a side effect: for v2 sessions `/verify/public` exposes
commitments, not content.

## 4. Alternatives considered

- **A. Commitments (chosen).** Works without knowing who the data subject is. Chain and anchors
  are untouched by erasure. Cost: one extra table, a version field, and a second check in verify.
- **B. Per-subject encryption keys (crypto-shredding).** Erase by destroying a key. Needs each
  event tagged with a data subject, which agents do not provide, plus key management. Revisit if
  customers can tag subjects.
- **C. Redact in place, re-hash, re-anchor.** Rewrites history: every later hash changes and old
  anchors no longer match. Defeats the point of the log.
- **D. Store only hashes, never content.** Removes the problem and the product: the tribunal
  audits content.
- **E. Mask personal data at ingest.** Cheap, but it blinds the `pii_mishandling` detector,
  because masked data is not detected as personal data. Revisit as detect-then-mask (record that
  a pattern was seen, store the masked text).

## 5. Limits, stated plainly

1. **Erased and deleted look identical.** Someone with database write access can delete a payload
   row and claim it was a lawful erasure. `unexplained_erasures` catches deletions that bypass
   the endpoint. It does not catch someone who also writes an `erasure_log` row, because that log
   is not tamper-evident yet (open question 1).
2. **Clear fields remain.** `org_id`, `agent_id`, `session_id`, `kind`, `tool`, `ts`, token
   counts and cost are not erased. Documentation tells users not to put personal data in them.
3. **Copies outside the system.** Exported evidence packs and PDFs, webhook deliveries,
   provider backups until they rotate (retention period not verified here), and text sent to a
   model provider by the live tribunal.
4. **v1 events** cannot be erased. Old demo data can simply be deleted; real v1 data would need
   the customer to accept the limitation.
5. **Verdict rationale redaction is per session**, not per event, because the verdict does not
   record which sentence quotes which event.
6. **Legal interplay.** Duties to keep records (for example logging obligations under the EU AI
   Act) and duties to erase can pull in opposite directions. TELUVANE provides a window, a
   hold and an erasure log. Which applies is the customer's decision with counsel. Site and
   sales copy must say "designed to support", never "compliant".

## 6. Rollout and rollback

Migration `0014` is additive (new columns with defaults, new tables). The API does not apply
migrations on boot (`DEPLOY.md`), so the migration must run against production before the new
API version starts, or every insert fails. Rollback: set `TELUVANE_EVENT_HASH_VERSION=1` and
redeploy. New events are then written as v1 again, and v2 events already written keep verifying.
No down migration.

## 7. Testing strategy

Unit: commitment determinism and salt sensitivity. Store, against real Postgres: v2 rows hold no
plaintext; canonical v2 strings contain none either; payload and clear-field tampering fail
verification; mixed v1 and v2 sessions verify; multi-session `verify_chain`; erasure leaves every
canonical string and hash identical; partial erasure and idempotence; silent deletion reported;
tenant isolation; v1 reported. API: owner-only, 404, legal hold 409, retention validation and
expiry, malformed legacy `ts` cannot break the retention job. Cross-language: a v2 chain vector
generated in Python is verified by the browser `verifyChain`.

## 8. Open questions

1. Chain or anchor the erasure log so erasures become tamper-evident too?
2. Per-org opt-in for v2 versus default for everyone (this design: default, with the env switch).
3. Dashboard UI for erase, retention and hold.
4. How long the hosting provider keeps backups, and whether that belongs in the customer docs.
5. Detect-then-mask at ingest (4E).
