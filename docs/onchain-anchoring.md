# On-chain anchoring

Operator and auditor reference for TELUVANE's Avalanche anchoring of session
integrity chains. For the full design rationale see
`docs/superpowers/specs/2026-08-29-avalanche-anchoring-design.md`.

## What this is

TELUVANE SHA-256 hash-chains every recorded agent event within a session. That
makes tampering visible, but only to someone who trusts TELUVANE's database. On
Pro plans, TELUVANE also batches finalized sessions into a Merkle tree and writes
the tree's root to the `SessionAnchorRegistry` contract on Avalanche Fuji. After
that, anyone with a copy of a session's event log can prove it was not altered
after the anchor, without trusting TELUVANE and without a TELUVANE account.

## What goes on chain

Only two values per batch:

- the Merkle root (a single 32-byte hash), and
- the number of sessions in the batch (an integer, emitted in the
  `BatchAnchored` event so a third party scanning the chain can see batch sizes).

Nothing else. No event content, no tool arguments, no model output, no session
ids, no org ids, no personal data. The root is a hash of hashes: it cannot be
reversed into any of the data it commits to.

## The point-in-time model

A session's anchor covers the session **as of a specific event**, recorded in
`session_anchors.anchored_through_seq`. A session that gains more events after
being anchored stays eligible for a new anchor row at a higher seq; the earlier
anchor remains valid for its own range. "Latest anchor" for a session is the row
with the highest `anchored_through_seq`.

Consequence for auditors: an anchor proves integrity through event N of the
session. Events after N are covered only once a later batch anchors them. The
evidence pack and the verification panel state this limitation explicitly ("verified
through event N; events after N not yet anchored").

## Tamper-detection matrix

| Attack on stored data | Caught by | Result shown |
|---|---|---|
| Edit a field of one event | `sha256(canonical) != hash` for that event | Mismatch: digest |
| Delete an event mid-chain | next event's `prev` != previous `hash` | Mismatch: broken chain link |
| Delete the last (anchored) event | recomputed head at `through_seq` unavailable / differs | Mismatch: head |
| Insert a forged event before `through_seq` | chain link break + head differs | Mismatch: chain / head |
| Replace the whole session with a self-consistent fake chain | recomputed root != on-chain root (fake never anchored) | Mismatch: root absent on-chain |
| Re-anchor a tampered session as a new batch | new root anchors, but `head_stored` (from the tampered rows) still must match `head_recomputed`; and the *original* anchor's root no longer verifies | original anchor shows Mismatch; auditors see the session was altered after its first anchor |
| Tamper an event added *after* the last anchor | detected only at the next anchor / on a full `verify_chain`; the anchored range stays provably intact | partial: "verified through event N; events after N not yet anchored" |

The last row is an honest limitation of point-in-time anchoring.

## How to verify manually

You need: a copy of the session's canonical events (the exact strings TELUVANE
hashed, plus `seq`, `prev_hash`, `hash`), the Merkle proof for the session, and
the batch's root. All three are in an exported evidence pack (`pack["json"]["canonical"]`,
and `pack["json"]["anchor"]`), or from `GET /anchor/{session_id}/canonical` plus
`GET /anchor/{session_id}` if you have API access.

1. **Recompute each event digest.** For every canonical event, check
   `sha256(canonical_string) == hash`. The canonical string is the byte-for-byte
   input TELUVANE's `_event_digest` hashed; you do not need to reconstruct it.

2. **Recompute the chain.** For each event after the first, check that
   `json.loads(canonical_string)["prev"]` equals the previous event's `hash`. The
   head is the `hash` of the event at `anchored_through_seq`.

3. **Recompute the Merkle root from the proof.** The tree uses domain-separated
   SHA-256:
   - Leaf: `sha256(b"teluvane-anchor-leaf-v1:" + org_id + b"|" + session_id + b"|" + chain_head_hex)`
   - Internal node: `sha256(b"teluvane-anchor-node-v1:" + lo + ro)` where
     `(lo, ro) = sorted((left, right))` (sorted pairs, so the proof carries no
     left/right flags).
   - An odd node is promoted to the next level unchanged, not duplicated.
   - A single-leaf batch: root = the leaf hash, proof = `[]`.
   Fold the leaf up through the ordered sibling hashes in the proof. The result
   must equal the batch root (`0x`-prefixed, used on chain as `bytes32`).

4. **Read the anchor from Avalanche.** Call `anchoredAt(root)` on the
   `SessionAnchorRegistry` contract using any Fuji RPC (for example
   `https://api.avax-test.network/ext/bc/C/rpc`) or look up the batch transaction
   on Snowtrace (`https://testnet.snowtrace.io/tx/<tx_hash>`). A non-zero return
   is the Unix timestamp of the block that anchored the root. Zero means the root
   was never anchored.

If all four pass, the session log is byte-identical to what it was when the batch
was anchored at that block timestamp.

## Environment variables

All optional. If `ANCHOR_RPC_URL`, `ANCHOR_CONTRACT_ADDRESS`, or
`ANCHOR_SIGNER_PRIVATE_KEY` is unset, `anchor.chain_config()` returns `None` and
the whole feature is inert: no batches are built, no errors are raised.

| Variable | Default | Purpose |
|---|---|---|
| `ANCHOR_RPC_URL` | (none) | Avalanche Fuji RPC endpoint(s) for reads and tx submission. Comma-separated list for fallback: `make_w3()` tries each in order and uses the first that answers a health check, so one dead provider doesn't take anchoring down. |
| `ANCHOR_CONTRACT_ADDRESS` | (none) | Deployed `SessionAnchorRegistry` address |
| `ANCHOR_SIGNER_PRIVATE_KEY` | (none) | Platform Fuji hot wallet, 64 hex chars, small test-AVAX balance only |
| `ANCHOR_CHAIN_ID` | `43113` | 43113 = Fuji testnet |
| `ANCHOR_MIN_SESSION_AGE_MINUTES` | `30` | Only anchor sessions idle at least this long |
| `ANCHOR_BATCH_INTERVAL_MINUTES` | `10` | How often the scheduler runs an anchor pass |
| `ANCHOR_CONFIRMATIONS` | `5` | Confirmations before a batch is marked mined |
| `ANCHOR_SUBMIT_TIMEOUT_MINUTES` | `30` | Mark a submitted batch failed if unmined this long |
| `ANCHOR_LOW_BALANCE_ALERT_AVAX` | `0.05` | Warn when signer balance drops below this |
| `ANCHOR_MAX_FORCED_RUNS_PER_ORG_PER_MONTH` | `20` | Cap on manual `POST /anchor/run` calls per org per calendar month |
| `ANCHOR_FORCED_RUN_COOLDOWN_MINUTES` | `5` | Minimum gap between one org's manual `POST /anchor/run` calls |
| `ANCHOR_EXPLORER_TX_URL` | `https://testnet.snowtrace.io/tx/` | Base URL for tx links |

Frontend (all optional; the `/verify` page and `AnchorPanel` normally read
contract metadata from the API):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS` | Fallback contract address for the browser client |
| `NEXT_PUBLIC_ANCHOR_RPC_URL` | Fallback RPC URL; unset uses viem's `avalancheFuji` default |
| `NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL` | Base URL for tx links in the UI |

The signer key is an env var only, never stored in the database, unlike per-org
BYOK keys. Key generation, faucet funding, and rotation are documented in
`DEPLOY.md`.

## Milestone roadmap

This build delivers milestones 1-3 (Fuji, full slice, public verify page).

1. Contract + Merkle + point-in-time anchoring pipeline on Fuji. *(done)*
2. Dashboard trustless verification + session integrity indicators + public
   `/verify` page. *(done)*
3. Evidence pack on-chain section, self-verifying offline. *(done)*
4. Mainnet Avalanche C-Chain deploy: dedicated funded wallet with a balance
   ceiling, gas tuning, optional client-side RFC 8785 (JCS) verification so the
   browser touches zero TELUVANE-served bytes during verification.
5. Per-org signing wallets (customer self-attestation) + webhook on anchor
   confirmation + configurable batch cadence per org.
