# Avalanche on-chain anchoring for TELUVANE session integrity

Date: 2026-08-29
Status: design v2, approved 2026-08-29
Branch: `feat/avalanche-anchoring`

## Problem

TELUVANE already SHA-256 hash-chains every recorded agent event per session
(`teluvane/store.py::_event_digest`, `prev_hash`/`hash` columns, `verify_chain`).
Tampering a stored row breaks the chain visibly. But the integrity check today is
"ask TELUVANE, and trust TELUVANE's database". An auditor, regulator, or
counterparty has no way to prove a session log was not altered after the fact
without trusting the vendor.

Anchoring each session's chain head to a public blockchain removes TELUVANE from
the trust path: anyone with a copy of the event log can recompute the chain head,
recompute a Merkle root, and read the anchor from Avalanche directly.

This is the same pattern the team already shipped for the Stratos drone team
(`FlightLogRegistry.sol` on Avalanche Fuji, in-browser verification), adapted from
per-item hashes to Merkle-batched roots.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Network | Avalanche Fuji testnet now; C-Chain mainnet is a funded grant milestone |
| Anchor unit | One anchor per session **point-in-time**, collected on a schedule, Merkle-batched into one transaction per batch |
| Signer | Single hosted TELUVANE platform wallet (one Fuji key), not per-org |
| Plan gating | Anchoring is Pro-plan only (platform pays gas), consistent with scheduled tribunal runs |
| Build scope | Full vertical slice on Fuji: contract, deploy script, Python module, Merkle, scheduler pass, migration, API, dashboard verify, **public verify page**, evidence pack, tests. Everything except mainnet deploy. |
| Verification trust | Browser verifies independently via a public Fuji RPC; TELUVANE's server check is shown but labeled as the vendor's own check |
| `_event_digest` | **NOT modified by this work.** Changing it would invalidate every stored chain. The Merkle layer sits on top of the existing per-event hash. |

## Cross-language digest strategy — LOCKED: option B

The browser must recompute each event's digest to verify the chain independently.
`_event_digest` builds its input as
`json.dumps({...}, sort_keys=True, ensure_ascii=False)` over fields including
`args` (an arbitrary dict). Reproducing Python's exact JSON byte output in
TypeScript (separators, unicode escaping, number formatting) is fragile;
a single mismatch makes an honest session read as tampered.

**Recommended (option B): server exposes the canonical digest input; browser hashes it.**

- New endpoint `GET /events/{session_id}/canonical` returns, per event, the exact
  string `_event_digest` hashed, plus `seq`, `prev_hash`, `hash`.
- Browser verification: for each event, assert `sha256(canonical_string) == hash`
  and `json.loads(canonical_string)["prev"] == previous.hash`; then Merkle; then
  read the contract from a public RPC.
- **Why this is still trust-minimized:** SHA-256 preimage resistance means the
  server cannot hand the browser a canonical string that both hashes to the
  stored `hash` and decodes to different content. Any lie the server tells about
  event content breaks the `sha256 == hash` check or a downstream chain link, and
  the browser renders event content *from the canonical string it verified*, not
  from a separate field. The only power the server retains is to refuse to serve
  data, not to forge it.
- Zero risk to existing chains: nothing about `_event_digest` changes.

**Alternative (option A): RFC 8785 (JCS) canonical JSON, computed on both sides.**

- Fully client-independent (no server-provided bytes at all).
- Requires a versioned digest: add `digest_v` to `events`; existing rows stay
  `v1` (current ad-hoc form), new rows `v2` (JCS). `verify_chain` branches on
  `digest_v`. Browser implements JCS via the `canonicalize` npm package; Python
  via `rfc8785`.
- More surface area, and a migration wrinkle (mixed-version chains).
- Recommended only if grant review specifically wants "the browser touches no
  TELUVANE-served bytes during verification". Can be added as milestone 4.

**Decision: option B, confirmed 2026-08-29.** Option A is deferred to milestone 4.

## Architecture

```
events (Postgres, hash-chained, unchanged)
   -> chain head per finalized session, as of a specific seq
   -> Merkle tree of leaves (one batch)
   -> membership + proofs persisted (DB txn)      <-- BEFORE sending tx
   -> anchorBatch(root, sessionCount) tx on Avalanche Fuji
   -> reconcile: wait N confirmations -> mark mined
   -> dashboard + public page + evidence pack verify:
        recompute head (as of anchored seq) -> recompute root
        -> read anchoredAt(root) from a public Fuji RPC
```

New units, each independently testable:

- `contracts/SessionAnchorRegistry.sol` — the on-chain registry.
- `teluvane/merkle.py` — pure-Python Merkle tree + proof build/verify. No deps.
- `teluvane/anchor.py` — orchestration: find finalized sessions, batch, persist,
  sign, submit, reconcile, verify, health.
- `scripts/deploy_anchor.py` — compile + deploy the contract from Python.
- `scripts/anchor_smoke.py` — manual Fuji integration check, not in CI.
- `frontend/lib/chainVerify.ts` — verify a session from canonical strings + proof + RPC read.
- `frontend/lib/merkle.ts` — TS Merkle verify (proof -> root).
- `frontend/components/AnchorPanel.tsx` — session-detail verification UI.
- `frontend/app/verify/page.tsx` — public, no-login verification page.

## 1. Contract — `contracts/SessionAnchorRegistry.sol`

Owner-only, immutable, no upgrade path, no roles.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Binds a Merkle root (of a batch of agent-session chain heads) to a
/// block timestamp, once, irreversibly. Owner-only writes.
contract SessionAnchorRegistry {
    address public immutable owner;

    /// merkleRoot => block.timestamp it was anchored at. 0 = never anchored.
    mapping(bytes32 => uint256) public anchoredAt;

    event BatchAnchored(bytes32 indexed root, uint256 sessionCount, uint256 timestamp);

    error NotOwner();
    error AlreadyAnchored();
    error EmptyBatch();

    constructor() {
        owner = msg.sender;
    }

    function anchorBatch(bytes32 root, uint256 sessionCount) external {
        if (msg.sender != owner) revert NotOwner();
        if (sessionCount == 0) revert EmptyBatch();
        if (anchoredAt[root] != 0) revert AlreadyAnchored();
        anchoredAt[root] = block.timestamp;
        emit BatchAnchored(root, sessionCount, block.timestamp);
    }
}
```

`sessionCount` is not used for verification; it is emitted so a third party
scanning the chain can see batch sizes. Verification is a single read of
`anchoredAt(root)`.

Deploy via `scripts/deploy_anchor.py` (`web3.py` + `py-solc-x`): compiles the
contract, deploys from the platform wallet key, prints the deployed address for
`ANCHOR_CONTRACT_ADDRESS`. Steps documented in `DEPLOY.md`.

## 2. Merkle scheme — `teluvane/merkle.py`

- **Leaf value** binds tenant + session + head so a leaf is self-describing and
  two sessions cannot collide on a shared head:
  `leaf = sha256(b"teluvane-anchor-leaf-v1:" + org_id.encode() + b"|" + session_id.encode() + b"|" + chain_head_hex.encode())`
- **Internal node**: `sha256(b"teluvane-anchor-node-v1:" + lo + ro)` where
  `(lo, ro) = sorted((left, right))`. Sorted pairs make proofs order-independent
  (no left/right flags in the proof).
- **Odd node**: promoted to the next level unchanged (not duplicated).
- **Domain-separation prefixes** (`...-leaf-v1:` / `...-node-v1:`) prevent a leaf
  from being reinterpreted as an internal node (second-preimage protection). The
  `v1` in the prefix is the Merkle-scheme version, independent of `_event_digest`.
- **Proof**: ordered list of sibling hashes (hex), leaf level up to root.
- **Single-leaf batch**: root = the leaf hash, proof = `[]`.

API:

```python
def leaf_hash(org_id: str, session_id: str, chain_head_hex: str) -> bytes
def build_tree(leaves: list[tuple[str, str, str]]) -> tuple[str, dict[tuple[str, str], list[str]]]
    # leaves: (org_id, session_id, chain_head_hex)
    # returns (root_hex_0x, {(org_id, session_id): proof})
def verify_proof(org_id: str, session_id: str, chain_head_hex: str,
                 proof: list[str], root_hex: str) -> bool
```

Root hex is `0x`-prefixed for on-chain use (`bytes32`).

## 3. Data model — `migrations/0012_onchain_anchor.sql`

```sql
-- 0012: on-chain anchoring of session integrity chains

CREATE TABLE IF NOT EXISTS anchor_batches (
    id            BIGSERIAL PRIMARY KEY,
    root          TEXT NOT NULL UNIQUE,             -- 0x-prefixed hex bytes32
    chain_id      INTEGER NOT NULL,                 -- 43113 = Fuji
    tx_hash       TEXT,                             -- null until submitted
    block_number  BIGINT,                           -- set when first seen in a block
    confirmations INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL,
    gas_used      BIGINT,
    fee_wei       NUMERIC,
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | submitted | mined | failed
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at  TIMESTAMPTZ,
    mined_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_anchors (
    org_id             TEXT NOT NULL,
    session_id         TEXT NOT NULL,
    anchored_through_seq BIGINT NOT NULL,           -- head is "as of" this event seq
    batch_id           BIGINT NOT NULL REFERENCES anchor_batches(id),
    chain_head         TEXT NOT NULL,               -- event hash at anchored_through_seq
    proof              JSONB NOT NULL DEFAULT '[]',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, session_id, anchored_through_seq)
);
CREATE INDEX IF NOT EXISTS idx_session_anchors_batch ON session_anchors (batch_id);
CREATE INDEX IF NOT EXISTS idx_session_anchors_lookup ON session_anchors (org_id, session_id);
```

Notes:

- **Point-in-time (gap #1).** `anchored_through_seq` records which event the head
  covers. A session that gains events after being anchored is eligible for a new
  anchor row at a higher seq; the old anchor stays valid for its range. The PK
  includes `anchored_through_seq` so a session can hold multiple anchors over its
  lifetime. "Latest anchor" for a session = max `anchored_through_seq`.
- `session_anchors` is org-scoped, so `Store._assert_scoped` still applies to any
  query the `Store` runs against it.
- `anchor_batches` is global: a batch may span orgs and the row holds only a root
  hash and chain metadata, nothing tenant-identifying.
- **Status lifecycle:** `pending` (membership + proofs written, tx not sent) →
  `submitted` (tx sent, `tx_hash` set) → `mined` (`confirmations >= N`) or
  `failed` (revert, or not mined within timeout).

## 4. Backend anchor module — `teluvane/anchor.py`

New runtime dependency: `web3>=7.0`. `py-solc-x` added to the `dev` extra
(deploy script only). Contract logic tests: see §11.

```python
@dataclass
class AnchorConfig:
    rpc_url: str
    contract_address: str
    signer_key: str
    chain_id: int = 43113
    min_session_age_minutes: int = 30
    batch_interval_minutes: int = 10
    confirmations: int = 5
    submit_timeout_minutes: int = 30
    low_balance_alert_avax: float = 0.05
    max_forced_runs_per_org_per_month: int = 20
    forced_run_cooldown_minutes: int = 5
    explorer_tx_url: str = "https://testnet.snowtrace.io/tx/"

def chain_config() -> AnchorConfig | None
    # None when required ANCHOR_* env vars are unset -> feature inert, no error.

def pending_leaves(pool) -> list[tuple[str, str, int, str]]
    # (org_id, session_id, through_seq, chain_head) where:
    #   - session has >= 1 event
    #   - max(ts) older than min_session_age_minutes
    #   - current max(seq) > any existing session_anchors.anchored_through_seq
    #     for that (org_id, session_id)   (covers first anchor AND re-anchor)
    #   - org is on the Pro plan (billing.org_plan)

def run_anchor_pass(pool) -> AnchorResult
    # Guarded by pg_advisory_lock (gap #4). Steps:
    #   1. acquire advisory lock; if not acquired, return (another worker has it)
    #   2. rows = pending_leaves(pool); if empty -> release, return
    #      (each row: org_id, session_id, through_seq, chain_head)
    #   3. root, proofs = merkle.build_tree([(o, s, h) for o, s, _seq, h in rows])
    #   4. in ONE db transaction:                              (gap #3)
    #        INSERT anchor_batches(root, chain_id, session_count, status='pending')
    #        INSERT session_anchors rows (through_seq, chain_head, proof) for each leaf
    #      commit
    #   5. tx_hash = submit_batch(cfg, root, session_count)
    #   6. UPDATE anchor_batches SET status='submitted', tx_hash=..., submitted_at=now()
    #   7. release advisory lock
    # If step 5/6 fails after step 4 commit: batch stays 'pending' with membership
    # intact; reconcile_pending re-submits it (idempotent: same root).

def submit_batch(cfg, root_hex, session_count) -> str
    # nonce from get_transaction_count(addr, 'pending')
    # EIP-1559 fees from fee_history, capped; fixed gas limit (small static write)
    # returns tx hash

def reconcile_pending(pool) -> None
    # For status in ('pending','submitted'):
    #   - 'pending' with no tx_hash and older than a few minutes -> re-run submit
    #     for that exact root (idempotent on-chain via AlreadyAnchored)
    #   - 'submitted': fetch receipt
    #       not yet mined, submitted_at older than submit_timeout -> status='failed'
    #       mined, reverted -> status='failed'
    #       mined ok -> set block_number, gas_used, fee_wei;
    #                   confirmations = head - block_number;
    #                   if confirmations >= cfg.confirmations -> status='mined', mined_at
    #   - 'failed' -> DELETE its session_anchors rows so those sessions retry.
    #   Each call also checks signer balance and logs a warning below threshold.

def verify_session(pool, org_id, session_id, through_seq=None) -> AnchorStatus
    # through_seq defaults to the session's latest anchor.
    # recompute head from events up to through_seq; recompute root from stored
    # proof; read anchoredAt(root) via RPC. Returns:
    #   {anchored, through_seq, total_seq, root, tx_hash, block_number,
    #    confirmations, mined_at, onchain_ts,
    #    head_stored, head_recomputed, head_matches, rpc_ok}

def anchor_health(pool) -> dict
    # {enabled, last_batch_at, last_batch_tx, pending_batches, unanchored_sessions,
    #  signer_address, signer_balance_avax, low_balance, rpc_ok, chain_id}
```

**Failure isolation.** Every RPC/network call is wrapped. A dead RPC, an empty
wallet, or a failed tx degrades the feature to "not yet anchored" plus a
structured warning log; it never raises into the main API request path.

**Signer key handling (gap #6 / security).** `ANCHOR_SIGNER_PRIVATE_KEY` is a
low-value hot wallet, funded only with small amounts of test AVAX. Documented in
`DEPLOY.md`: how to generate it, fund from the Fuji faucet, and rotate it (deploy
is immutable but the owner is set at construction, so rotation = redeploy the
contract and repoint `ANCHOR_CONTRACT_ADDRESS`; historical anchors on the old
contract stay valid and readable). For the mainnet milestone: a dedicated wallet
with a low balance ceiling and a documented top-up cadence.

## 5. Scheduler integration — `teluvane/scheduler.py`

The existing in-process 60s tick gains an anchor step after the tribunal pass:

```python
cfg = anchor.chain_config()
if cfg:
    anchor.reconcile_pending(pool)          # cheap: receipt + confirmation polls
    if _anchor_due(cfg.batch_interval_minutes):
        anchor.run_anchor_pass(pool)         # itself advisory-locked
```

`_anchor_due()` uses a module-level last-run timestamp, matching the tribunal
scheduler's existing pattern; no new table. The in-process limitation (no work
while the web process is asleep) is identical to the tribunal scheduler and is
documented the same way. A dedicated worker is a later milestone. The
`pg_advisory_lock` in `run_anchor_pass` makes multiple web instances safe today.

## 6. API — new routes in `teluvane/ingest.py`

| Route | Auth | Purpose |
|---|---|---|
| `GET /anchor/{session_id}` | `current_org` | `AnchorStatus` for the session's latest anchor (or `?through_seq=` for a specific one) |
| `GET /events/{session_id}/canonical` | `current_org` | Per-event `{seq, prev_hash, hash, canonical}` — the digest inputs the browser hashes (option B) |
| `GET /anchor/contract` | `current_org` | `{chain_id, contract_address, explorer_tx_url, rpc_url}` — public data the browser needs |
| `GET /anchor/status` | `current_org` | `anchor_health(pool)` for this org (Settings page) |
| `POST /anchor/run` | `current_org` + Pro + admin role | Trigger an anchor pass now. No-op if nothing pending. Per-org cooldown + monthly cap (gap #10). Rate-limited via the existing slowapi limiter. |
| `GET /verify/public/{session_id}` | **none** (unauthenticated) | Read-only verification bundle: canonical events, proof, root, tx, contract info. Only served for sessions whose org has opted the session's anchor into public verification (see §8). |

No route returns the signer key. No route lets a caller anchor anything other
than their own finalized sessions.

`GET /sessions` gains an `anchor` field per row (`none | pending | mined |
mismatch`) so the list does not N+1 (gap #9).

## 7. Config — environment variables

Backend (all optional; if a required one is missing, `chain_config()` returns
`None` and the feature is inert):

```
ANCHOR_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
ANCHOR_CONTRACT_ADDRESS=0x...
ANCHOR_SIGNER_PRIVATE_KEY=0x...              # 64 hex chars, platform Fuji hot wallet
ANCHOR_CHAIN_ID=43113
ANCHOR_MIN_SESSION_AGE_MINUTES=30
ANCHOR_BATCH_INTERVAL_MINUTES=10
ANCHOR_CONFIRMATIONS=5
ANCHOR_SUBMIT_TIMEOUT_MINUTES=30
ANCHOR_LOW_BALANCE_ALERT_AVAX=0.05
ANCHOR_EXPLORER_TX_URL=https://testnet.snowtrace.io/tx/
```

Frontend:

```
NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS=0x...
NEXT_PUBLIC_ANCHOR_RPC_URL=                  # optional; viem avalancheFuji default if unset
NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL=https://testnet.snowtrace.io/tx/
```

`frontend/.env.local.example` and `DEPLOY.md` updated. The signer key is an env
var only (single global key), never stored in the DB, unlike per-org BYOK keys.

## 8. Dashboard verify panel + public page

`frontend/components/AnchorPanel.tsx` (client component) on the session detail
page. New dependency: `viem`.

Entirely browser-side:

1. `GET /anchor/{session_id}`, `GET /events/{session_id}/canonical`,
   `GET /anchor/contract` from the TELUVANE API.
2. For each canonical event: `sha256(canonical) === hash`, and
   `JSON.parse(canonical).prev === previousEvent.hash`. Render event content
   parsed from the verified canonical string.
3. Recompute the Merkle root from `(org_id, session_id, chain_head)` + `proof`
   via `frontend/lib/merkle.ts`.
4. `createPublicClient({ chain: avalancheFuji, transport: http(rpcUrl) })`,
   `readContract` `anchoredAt(root)`.
5. Render exactly one state (colored dot + text, **no pills**, per repo UI rules):

   | State | Condition | Treatment |
   |---|---|---|
   | Not yet anchored | no anchor row, or session younger than batch window | neutral dot, plain text |
   | Pending | batch `submitted`, `confirmations < N` | amber dot, "waiting for N confirmations" |
   | Anchored and verified | chain links ok + proof valid + root non-zero on-chain + `head_recomputed === head_stored` | green dot, on-chain UTC time, Snowtrace tx link |
   | Mismatch | any of: broken chain link, digest mismatch, proof invalid, root absent on-chain, recomputed head ≠ stored head | red dot, which check failed |
   | Avalanche unreachable | RPC read threw | grey dot, "could not reach Avalanche RPC — retry" |
   | Proof missing | anchor row exists but `proof` absent/malformed | red dot, "anchor record incomplete" |

   The **independent, read-from-Avalanche** result is the visually dominant
   element. TELUVANE's own `verify_session` result is shown secondary and
   labeled "TELUVANE's check" — the point of the feature is the one the vendor
   cannot influence.

Also:
- Session list row: integrity indicator (dot + text) from the `GET /sessions`
  `anchor` field.
- Settings page: one line from `GET /anchor/status` — "N sessions anchored, last
  batch <relative time>, <tx link>", plus a low-balance warning when set.
- **Opt-in to public verification:** a per-session toggle (default off). When on,
  `GET /verify/public/{session_id}` will serve that session's verification bundle
  without auth. Nothing is published automatically.

`frontend/app/verify/page.tsx` — **public, no-login page** (gap #14). Two modes:
- Paste a session id that an org has made public → fetches
  `GET /verify/public/{id}` and runs the same browser verification as the panel.
- Paste an exported evidence-pack JSON → verifies fully offline against Avalanche
  (canonical events + proof are in the pack; only the RPC read touches the
  network).
This page is the primary grant demo artifact: a stranger can confirm an agent's
log is intact without a TELUVANE account.

## 9. Evidence pack — `teluvane/evidence.py`

`build_evidence_pack` and the HTML + PDF renderers gain an **On-chain anchor**
section:

- Merkle root, batch tx hash as a Snowtrace URL, block number and UTC time,
  confirmations, session count in the batch, `anchored_through_seq` vs total
  events.
- The session's canonical events + Merkle proof embedded, so the pack is
  self-verifying offline: a reader recomputes each digest, the chain, then the
  root, checks it matches, then checks the tx on any Fuji explorer.
- Chain-of-custody line:
  `SHA-256 event chain (through event N of M) -> Merkle root -> Avalanche Fuji tx 0x... at block B`.
- If the session is not anchored: the section says so plainly.
- **Privacy line (gap #13):** "Only hashes and a batch count are written on
  chain. No event content, tool arguments, model output, or personal data leaves
  TELUVANE."

## 10. Tamper-detection matrix (gap #11)

| Attack on stored data | Caught by | Result shown |
|---|---|---|
| Edit a field of one event | `sha256(canonical) != hash` for that event | Mismatch — digest |
| Delete an event mid-chain | next event's `prev` != previous `hash` | Mismatch — broken chain link |
| Delete the last (anchored) event | recomputed head at `through_seq` unavailable / differs | Mismatch — head |
| Insert a forged event before `through_seq` | chain link break + head differs | Mismatch — chain / head |
| Replace the whole session with a self-consistent fake chain | recomputed root != on-chain root (fake never anchored) | Mismatch — root absent on-chain |
| Re-anchor a tampered session as a new batch | new root anchors, but `head_stored` (from the tampered rows) still must match `head_recomputed`; and the *original* anchor's root no longer verifies | original anchor shows Mismatch; auditors see the session was altered after its first anchor |
| Tamper an event added *after* the last anchor | detected only at the next anchor / on a full `verify_chain`; the anchored range stays provably intact | partial: "verified through event N; events after N not yet anchored" |

The last row is an honest limitation of point-in-time anchoring and is stated as
such in the evidence pack and on the panel.

## 11. Testing

| Target | Approach |
|---|---|
| `teluvane/merkle.py` | Known vectors; single / odd / even leaf counts; leaf binding (same head, different session → different leaf); proof verify pass and tamper-fail. Pure unit. |
| `frontend/lib/merkle.ts`, `frontend/lib/chainVerify.ts` | Run against JSON vectors emitted by a Python test and committed to the repo. Includes adversarial `args` payloads (unicode, nested, numbers) to prove the canonical-string approach needs no JS JSON canonicalization. |
| `teluvane/anchor.py` | `pending_leaves` against the existing Postgres test fixtures, incl. the re-anchor case (session grows past its anchor). `run_anchor_pass` / `reconcile_pending` with `web3` mocked (fake tx hash + receipt + head number). Asserts: membership+proofs persisted before submit; advisory-lock contention returns cleanly; crash after commit / before submit is recovered by reconcile; failed batch deletes its `session_anchors`; confirmations gate; low-balance warning logged. |
| `contracts/SessionAnchorRegistry.sol` | Foundry test job in CI (`forge test`): owner-only, one-shot per root, empty-batch revert, event emission. Foundry is a single self-contained binary — lighter than pulling PyEVM/eth-tester into the Python test env. |
| Fuji integration | `scripts/anchor_smoke.py`, manual, run before deploy. Not in CI. Deploys (or reuses) the contract, anchors a real batch, verifies the read. |
| `teluvane/evidence.py` | Anchor section renders with and without an anchor; embedded proof verifies. |
| Public verify page | Component test: each of the six panel states; offline evidence-pack mode with a mocked RPC read. |

## 12. Observability (gap #15)

- One structured log line per batch: `root`, `tx_hash`, `session_count`,
  `gas_used`, `fee_wei`, `fee_usd` (best-effort), `confirmations_at_mined`.
- `GET /anchor/status` (§6) exposes `anchor_health`: last batch time + tx,
  pending batch count, unanchored Pro-session count, signer address + balance,
  `low_balance` bool, `rpc_ok` bool.
- Existing `/health` unchanged; `/ready` unchanged. Anchor health is deliberately
  a separate endpoint so a degraded RPC never fails readiness.

## 13. Grant milestone split

This build delivers milestones 1-3 (Fuji, full slice, public verify page).
Roadmap for the application:

1. Contract + Merkle + point-in-time anchoring pipeline on Fuji. *(this build)*
2. Dashboard trustless verification + session integrity indicators +
   **public `/verify` page**. *(this build)*
3. Evidence pack on-chain section, self-verifying offline. *(this build)*
4. Mainnet Avalanche C-Chain deploy: dedicated funded wallet with a balance
   ceiling, gas tuning, optional client-side JCS verification (OPEN DECISION
   option A) so the browser touches zero TELUVANE-served bytes.
5. Per-org signing wallets (customer self-attestation) + webhook on anchor
   confirmation + configurable batch cadence per org.

## 14. Out of scope (this build)

- Mainnet C-Chain deployment.
- Per-org wallets.
- A standalone anchor worker / Render cron (the in-process scheduler + advisory
  lock is sufficient for now, matching the tribunal scheduler).
- Anchoring free-plan orgs.
- Automatic public exposure of any session (public verification is strictly opt-in
  per session).
- Retroactive anchoring of pre-feature sessions (a one-off manual
  `run_anchor_pass` can pick them up if wanted).
- Client-side RFC 8785 canonicalization (OPEN DECISION option A) — deferred to
  milestone 4 unless review requires it now.

## 15. Dependencies added

| Where | Package | Why |
|---|---|---|
| backend runtime | `web3>=7.0` | RPC reads, tx signing/submit |
| backend `dev` | `py-solc-x` | compile the contract in `scripts/deploy_anchor.py` |
| CI | Foundry (`forge`) | contract unit tests |
| frontend | `viem` | browser-side contract read (same as Stratos) |
| frontend | `canonicalize` | ONLY if OPEN DECISION option A is chosen; not needed for option B |
