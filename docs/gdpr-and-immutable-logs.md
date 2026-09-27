# An unchangeable log and the right to erasure

TELUVANE records what an AI agent did in a hash-chained log, so that changing a record
afterwards is visible. Data protection law can require you to delete personal data on request.
These two goals look like they collide. This page explains how TELUVANE handles both, and where
it cannot help. It describes what the software does. It is not legal advice, and it does not
claim that using TELUVANE makes anyone compliant with the GDPR or any other law.

## The conflict

A plain hash chain digests the full content of every event. Delete or edit one event and its
hash no longer matches, so the whole chain from that point on fails verification. Any anchor
that was written to a public chain from that chain's head is also left pointing at data that no
longer exists. With such a design, erasing personal data means destroying the evidence.

## What TELUVANE does instead

Each event is split in two parts.

- **Structure**, which stays: the organization, agent id, session id, event kind, tool name,
  timestamp, and the link to the previous event.
- **Content**, which can be erased: the stated intent, the tool arguments, the output, and the
  approval field.

The chain does not digest the content. It digests a **salted commitment** to it: a SHA-256
hash over a random 32-byte salt and the content. The content and its salt are stored in a
separate table. Erasing an event deletes that row.

After erasure:

- every hash in the chain, and every anchored chain head, is unchanged, so the chain still
  verifies;
- the commitment that remains cannot be turned back into the content, because the random salt
  is gone with it;
- the event still exists as a record that something happened at that time, by that agent,
  through that tool, but what it said is gone.

Before erasure, verification also checks that the stored content still matches its commitment,
so editing the content in the database is caught exactly as it was before.

## What stays, and what goes

| Kept after erasure | Removed by erasure |
|---|---|
| Organization, agent id, session id | Intent text |
| Event kind and tool name | Tool arguments |
| Timestamp and hash links | Tool output |
| The salted commitment | Approval field (may hold a user id) |
| Token counts and cost | The salt |
| An entry in the erasure log (event numbers, who asked, why, when) | Verdict explanations for the session (replaced with a redaction notice) |

Because the kept fields are not erased, do not put personal data in agent ids, session ids or
tool names.

## Erasing

Only the organization owner can erase. Erase every event of a session, or chosen events:

```bash
curl -X POST "$TELUVANE_URL/sessions/$SESSION_ID/erase" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"reason": "data subject request 2026-10-01"}'

curl -X POST "$TELUVANE_URL/sessions/$SESSION_ID/erase" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"seqs": [41, 42], "reason": "one event only"}'
```

The response counts what happened: `erased`, `already_erased`, and `legacy_unerasable`.

Verifying afterwards:

```bash
curl "$TELUVANE_URL/verify?session_id=$SESSION_ID" -H "Authorization: Bearer $TOKEN"
# {"chain_intact": true, "erased_events": 3, "unexplained_erasures": 0}
```

`unexplained_erasures` counts events whose content is missing but that no erasure log entry
covers. A non-zero value means content was removed some other way than the erase endpoint, and
the session should be treated as suspect until someone explains it.

## Retention and legal hold

An organization can set a retention window. Content older than that many days is erased
automatically, once an hour, the same way as a manual erasure:

```bash
curl -X PUT "$TELUVANE_URL/orgs/retention" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"retention_days": 180, "legal_hold": false}'
```

A field you leave out of the request keeps its current value, so changing the window never lifts
a legal hold by accident. Setting `legal_hold` to `true` blocks both the automatic job and manual erasure for the whole
organization until it is set back to `false`. Use it when you are required to keep records, for
example during a dispute or an investigation. Deciding which duty wins (a request to erase or a
duty to keep records) is your decision with your counsel. TELUVANE only provides the switches.

## What this does not cover

- **Events recorded before this feature.** Older events (hash version 1) have their content
  inside the hash. They cannot be erased without breaking the chain, and the erase endpoint says
  so instead of skipping them silently.
- **Copies outside TELUVANE.** Evidence packs, PDFs and webhook deliveries you already exported
  or received, database backups held by the hosting provider until they rotate, and any text
  sent to a model provider when the live tribunal ran on your Anthropic key.
- **The kept fields** listed above.
- **Proof that an erasure was authorized.** Missing content looks the same whether the owner
  erased it or someone with database access deleted it. The erasure log and the
  `unexplained_erasures` counter make the second case visible, but the erasure log is not itself
  tamper-evident yet.
- **On-chain anchors.** Nothing personal is ever written on chain, only Merkle roots of chain
  heads, so there is nothing there to erase. Anchoring runs on the Avalanche Fuji testnet only.

## Checking the design

The design and its alternatives are in
`docs/superpowers/specs/2026-09-27-erasable-event-log-design.md`. The tests that pin the
properties above are `tests/test_event_commitments.py`, `tests/test_erasure.py` and
`tests/test_privacy_api.py`. You can watch the whole thing happen on a scratch database with
`python scripts/erasure_demo.py`.
