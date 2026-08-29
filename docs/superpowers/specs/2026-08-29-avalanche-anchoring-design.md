# Avalanche on-chain anchoring for TELUVANE session integrity

Date: 2026-08-29
Status: design approved, pending spec review
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
| Anchor unit | One anchor per session, collected on a schedule, Merkle-batched into one transaction per batch |
| Signer | Single hosted TELUVANE platform wallet (one Fuji key), not per-org |
| Plan gating | Anchoring is Pro-plan only (platform pays gas), consistent with scheduled tribunal runs |
| Build scope | Full vertical slice on Fuji: contract, deploy script, Python module, Merkle, scheduler pass, migration, API, dashboard verify, evidence pack, tests. Everything except mainnet deploy. |
| Verification trust | Browser verifies independently via a public Fuji RPC; TELUVANE's server check is shown but labeled as the vendor's own check |

## Architecture

```
events (Postgres, hash-chained)
   -> chain head per finalized session
   -> Merkle tree of chain heads (one batch)
   -> anchorBatch(root, sessionCount) tx on Avalanche Fuji
   -> per-session {root, proof, tx} stored in Postgres
   -> dashboard + evidence pack verify: recompute head -> recompute root
      -> read anchoredAt(root) from public Fuji RPC
```

New units, each independently testable:

- `contracts/SessionAnchorRegistry.sol` — the on-chain registry.
- `teluvane/merkle.py` — pure-Python Merkle tree + proof build/verify. No deps.
- `teluvane/anchor.py` — orchestration: find finalized sessions, batch, sign, submit, reconcile, verify.
- `scripts/deploy_anchor.py` — compile + deploy the contract from Python.
- `scripts/anchor_smoke.py` — manual Fuji integration check, not in CI.
- `frontend/lib/chainDigest.ts` — TS port of `_event_digest`.
- `frontend/lib/merkle.ts` — TS port of `merkle.py` verify path.
- `frontend/components/AnchorPanel.tsx` — browser-side trustless verification UI.

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

- **Leaf**: session chain head is a hex SHA-256 digest string (the `hash` of the
  session's last event). Leaf hash = `sha256(b"leaf:" + bytes.fromhex(chain_head))`.
- **Internal node**: `sha256(b"node:" + lo + ro)` where `(lo, ro) = sorted((left, right))`.
  Sorted pairs make proofs order-independent (no left/right flags needed).
- **Odd node**: promoted to the next level unchanged (not duplicated).
- **Domain separation**: the `leaf:` / `node:` prefixes prevent a leaf value from
  being reinterpreted as an internal node (second-preimage protection).
- **Proof**: ordered list of sibling hashes (hex strings), leaf up to root.
- **Single-leaf batch**: root = leaf hash, proof = `[]`.

API:

```python
def leaf_hash(chain_head_hex: str) -> bytes
def build_tree(chain_heads: list[str]) -> tuple[str, dict[str, list[str]]]
    # returns (root_hex, {chain_head_hex: proof})
def verify_proof(chain_head_hex: str, proof: list[str], root_hex: str) -> bool
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
    block_number  BIGINT,                           -- null until mined
    session_count INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | mined | failed
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    mined_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_anchors (
    org_id      TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    batch_id    BIGINT NOT NULL REFERENCES anchor_batches(id),
    chain_head  TEXT NOT NULL,                      -- event hash that was anchored
    proof       JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_session_anchors_batch ON session_anchors (batch_id);
```

`session_anchors` is org-scoped, so `Store._assert_scoped` still applies to any
query the `Store` runs against it. `anchor_batches` is global: a batch may span
multiple orgs and the row holds only a root hash and chain metadata, nothing
tenant-identifying.

## 4. Backend anchor module — `teluvane/anchor.py`

New runtime dependency: `web3>=7.0`. `py-solc-x` added to the `dev` extra
(deploy script only). Contract logic tests use `eth-tester` / PyEVM (also `dev`).

```python
@dataclass
class AnchorConfig:
    rpc_url: str
    contract_address: str
    signer_key: str
    chain_id: int = 43113
    min_session_age_minutes: int = 30
    batch_interval_minutes: int = 10
    explorer_tx_url: str = "https://testnet.snowtrace.io/tx/"

def chain_config() -> AnchorConfig | None
    # None when ANCHOR_* env not fully set -> feature stays dark, no error.

def pending_sessions(pool) -> list[tuple[str, str, str]]
    # (org_id, session_id, chain_head) for sessions:
    #   - with >= 1 event
    #   - max(ts) older than min_session_age_minutes
    #   - no row in session_anchors
    #   - org is on the Pro plan (billing.org_plan)

def build_batch(sessions) -> tuple[str, dict[tuple[str, str], list[str]]]
    # (root_hex, {(org_id, session_id): proof}) via merkle.py

def submit_batch(cfg, root_hex, session_count) -> str
    # sign + send anchorBatch; nonce from get_transaction_count(pending);
    # EIP-1559 fees from fee_history with a hard ceiling; returns tx hash.

def run_anchor_pass(pool) -> AnchorResult
    # collect -> if empty return -> INSERT anchor_batches(status=pending)
    # -> submit_batch -> UPDATE tx_hash -> INSERT session_anchors rows w/ proofs.
    # Idempotent: anchor_batches.root UNIQUE + session_anchors PK.

def reconcile_pending(pool) -> None
    # for status=pending batches: poll receipt.
    #   mined ok -> status=mined, block_number, mined_at
    #   reverted / older than timeout -> status=failed,
    #     DELETE its session_anchors rows so sessions retry next pass.

def verify_session(pool, org_id, session_id) -> AnchorStatus
    # recompute chain head from events; recompute root from stored proof;
    # read anchoredAt(root) via RPC. Returns:
    #   {anchored, root, tx_hash, block_number, mined_at,
    #    chain_head_stored, chain_head_recomputed, chain_head_matches, onchain_ts}
```

Failure isolation: all network/RPC calls are wrapped; a dead RPC or an empty
wallet degrades the feature to "not yet anchored" and logs, never raises into the
main request path.

## 5. Scheduler integration — `teluvane/scheduler.py`

The existing in-process 60s tick gains an anchor step after the tribunal pass:

```python
cfg = anchor.chain_config()
if cfg:
    anchor.reconcile_pending(pool)          # cheap receipt polls every tick
    if _anchor_due(cfg.batch_interval_minutes):
        anchor.run_anchor_pass(pool)
```

`_anchor_due()` uses a module-level last-run timestamp, matching the tribunal
scheduler's existing pattern; no new table. The in-process limitation (no work
while the web process is asleep) is identical to the tribunal scheduler and is
documented the same way. A dedicated worker is a later milestone, not this build.

## 6. API — new routes in `teluvane/ingest.py`

| Route | Auth | Purpose |
|---|---|---|
| `GET /anchor/{session_id}` | `current_org` | `AnchorStatus` for one session: stored root, proof, tx hash, block, `verify_session` result |
| `GET /anchor/contract` | `current_org` | `{chain_id, contract_address, explorer_tx_url, rpc_url}` — the public data the browser needs to verify on its own |
| `POST /anchor/run` | `current_org` + Pro + admin role | Trigger an anchor pass immediately (demo / impatient user). Rate-limited via the existing slowapi limiter. |

No route returns the signer key. No route lets a caller anchor anything other
than their own finalized sessions.

## 7. Config — environment variables

Backend (all optional; if any required one is missing, `chain_config()` returns
`None` and the feature is inert):

```
ANCHOR_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
ANCHOR_CONTRACT_ADDRESS=0x...
ANCHOR_SIGNER_PRIVATE_KEY=0x...              # 64 hex chars, platform Fuji wallet
ANCHOR_CHAIN_ID=43113
ANCHOR_MIN_SESSION_AGE_MINUTES=30
ANCHOR_BATCH_INTERVAL_MINUTES=10
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

## 8. Dashboard verify panel

`frontend/components/AnchorPanel.tsx` (client component), on the session detail
page. New dependency: `viem`.

Entirely browser-side:

1. `GET /anchor/{session_id}` and `GET /events?session_id=...` from the TELUVANE API.
2. Recompute the chain head locally from the events via `frontend/lib/chainDigest.ts`
   (TS port of `_event_digest`).
3. Recompute the Merkle root from `chain_head` + `proof` via `frontend/lib/merkle.ts`.
4. `createPublicClient({ chain: avalancheFuji, transport: http(rpcUrl) })`,
   `readContract` `anchoredAt(root)`.
5. Render exactly one state:
   - **Not yet anchored** — session younger than the batch window, or batch pending.
   - **Anchored and verified** — proof valid, root non-zero on-chain, recomputed
     head matches stored head. Shows on-chain timestamp + a Snowtrace tx link.
   - **Mismatch** (red) — stored head, recomputed head, or on-chain root disagree.

The server's `verify_session` result is shown alongside, labeled "TELUVANE's
check"; the browser result is labeled "Independent check, read from Avalanche".

Also:
- Session list row: small integrity indicator (anchored / pending / none) using a
  colored dot + text, not a pill.
- Settings page: one line, "N sessions anchored, last batch <relative time>, <tx link>".

## 9. Evidence pack — `teluvane/evidence.py`

`build_evidence_pack` and the HTML + PDF renderers gain an **On-chain anchor**
section:

- Merkle root, batch tx hash as a Snowtrace URL, block number and UTC time,
  session count in the batch.
- This session's Merkle proof, so the pack is self-verifying offline: a reader
  with the event log recomputes head then root, checks it matches, then checks
  the tx on any Fuji explorer.
- Chain-of-custody line:
  `SHA-256 event chain -> Merkle root -> Avalanche Fuji tx 0x... at block N`.
- If the session is not anchored: the section says so plainly.

## 10. Testing

| Target | Approach |
|---|---|
| `teluvane/merkle.py` | Known vectors; single / odd / even leaf counts; proof verify pass and tamper-fail. Pure unit. |
| `frontend/lib/chainDigest.ts`, `frontend/lib/merkle.ts` | Run against JSON test vectors emitted by a Python test and committed to the repo. Guards cross-language drift. |
| `teluvane/anchor.py` | `pending_sessions` against the existing Postgres test fixtures; `run_anchor_pass` / `reconcile_pending` with `web3` mocked (fake tx hash + receipt). Asserts DB rows, double-run idempotency, failed-batch cleanup. |
| `contracts/SessionAnchorRegistry.sol` | `web3` + `eth-tester` (PyEVM), in-memory. Asserts owner-only, one-shot per root, empty-batch revert, event emission. No live network in CI. |
| Fuji integration | `scripts/anchor_smoke.py`, manual, run before deploy. Not in CI. |
| `teluvane/evidence.py` | Anchor section renders correctly with and without an anchor present. |

## 11. Grant milestone split

This build delivers milestones 1-3. Roadmap for the application:

1. Contract + Merkle + anchoring pipeline on Fuji. *(this build)*
2. Dashboard trustless verification + session integrity indicators. *(this build)*
3. Evidence pack on-chain section, self-verifying offline. *(this build)*
4. Mainnet Avalanche C-Chain deploy: funded platform wallet, gas tuning, public
   verification page at `teluvane.com/verify`.
5. Per-org signing wallets (customer self-attestation) + webhook on anchor
   confirmation.

## Out of scope (this build)

- Mainnet C-Chain deployment.
- Per-org wallets.
- A standalone anchor worker / Render cron (keeps the in-process scheduler
  limitation, as the tribunal scheduler already does).
- Anchoring free-plan orgs.
- Retroactive anchoring of sessions that finalized before the feature shipped
  (they can be picked up by a one-off manual `run_anchor_pass` if wanted).
