# TELUVANE — Blockchain Trust Layer: Design Spec

> **For agentic workers:** This spec covers *why* and *what*. The buildable part (Phase 1) has
> a standalone TDD implementation plan: `docs/superpowers/plans/2026-08-23-plan-1-chain-tip-anchoring.md`.
> Phase 2 (ERC-8004) is deliberately left at design-level only — see §11 and §13.

## 1. Goal

TELUVANE's tamper-evidence claim ("tamper one row and the chain breaks visibly") is currently
only verifiable by trusting TELUVANE's own Postgres database — the same system being audited is
the only witness to its own integrity. This spec adds an independent witness: periodically
commit the hash chain's current state to Avalanche C-Chain (a public, permissionless ledger
neither TELUVANE nor its customers control), so `verify(chain) → INTACT` becomes something a
third party (an auditor, a customer's security team, a regulator) can check without an account,
an API key, or trust in TELUVANE at all.

A second, lower-certainty goal: publish Tribunal verdicts as attestations against **ERC-8004**
("Trustless Agents"), a draft Ethereum standard giving AI agents portable, cross-platform
identity/reputation/validation records, already live on Avalanche C-Chain. If TELUVANE becomes
the entity that issues an agent's on-chain "did this agent behave" record, that record is useful
to platforms that never visit teluvane.com — a distribution channel, not just a feature.

Both are pursued in parallel with an **Avalanche Foundation infraBUIDL(AI) grant application**
(§10) — the grant isn't the reason to build this, but the build is real enough to be a credible
application, and the timing (ERC-8004 is brand new, ecosystem still forming) is favorable.

## 2. Locked decisions

- **Chain: Avalanche C-Chain** (chain id 43114), not a dedicated L1/subnet. C-Chain is where
  ERC-8004's IdentityRegistry and ReputationRegistry are already deployed, gas is
  sub-$0.10/write under normal conditions (Octane/ACP-176 dynamic fee model), and no project
  doing AI-agent audit work has moved to a dedicated L1 as of this research — running our own
  validator set for a feature this size would be pure overhead.
- **What goes on-chain: hashes and scores only, never log content.** A session's event log
  (agent I/O, tool args, outputs) can contain customer data; putting it on a public,
  permanent ledger would be a straightforward GDPR/data-protection problem for a compliance
  product to have. Only a 32-byte root hash (anchoring) or a 0–100 score + a `keccak256` digest
  of an off-chain evidence pack (ERC-8004 validation) ever leaves our database.
- **No new Merkle tree per session.** TELUVANE's existing hash chain (`teluvane/store.py`,
  `_event_digest`) already has the property that the latest event's `hash` commits to the
  entire session history (`hash = SHA256(prev_hash + event fields)`, chained). The "root" to
  anchor for one session is simply that session's current chain-tip hash — no separate
  Merkle-tree construction needed at the single-session level.
- **Batch anchoring across sessions, not one transaction per session.** Anchoring every active
  session's tip individually would multiply gas cost linearly with session count for no
  benefit. Instead: build a small Merkle tree whose leaves are `(org_id, session_id, tip_hash)`
  for every session touched since the last anchor, write only that tree's root on-chain, and
  store each session's Merkle proof in Postgres so any one session's inclusion is independently
  checkable without trusting our DB for the rest.
- **A funded backend hot wallet, not per-customer wallets.** Customers never sign anything or
  hold keys. TELUVANE holds one (or a small number of) Avalanche private keys, encrypted at
  rest with the existing `teluvane/crypto.py` Fernet helper (the same mechanism already used
  for BYOK Anthropic keys) — no new secret-storage pattern introduced.
- **web3.py over a custom SDK.** No Avalanche-specific Python SDK exists (their official SDK is
  TS/JS, viem-based); Avalanche C-Chain is a standard EVM JSON-RPC endpoint, so generic
  web3.py against a public or dedicated RPC endpoint is the correct, boring choice.
- **Anchoring is a paid-plan feature; verifying an anchor is free and public.** TELUVANE pays
  real gas to write; anyone should be able to read for free. This mirrors the existing
  Pro-gating pattern (`org_plan(org_id) != "pro"` gates PDF export, custom rules, scheduled
  runs in `teluvane/ingest.py`) and directly serves the trust-building goal — a prospect
  should be able to verify a *sample* anchored chain before ever creating an account.

## 3. What stays vs. what changes

**Stays untouched:** the hash-chain algorithm itself (`_event_digest`), the Tribunal
(`teluvane/tribunal.py`), the Store's `org_id` scoping guard, the evidence pack HTML/PDF
renderer's existing content, billing, auth. This is an additive layer, not a rewrite.

**Changes:**
- `teluvane/store.py` gains read methods for anchor status (no changes to `append`/`verify_chain`).
- `teluvane/evidence.py`'s evidence pack gains an "on-chain anchor" section when one exists for
  the session (tx hash, block explorer link, Merkle proof, plain-language verification steps).
- `teluvane/scheduler.py` gains a sibling periodic job (same in-process-APScheduler shape,
  same "only ticks while the process is warm" caveat already disclosed for tribunal scheduling
  — the README's existing roadmap item, "a dedicated worker/cron service," fixes both at once
  if it's ever built).
- `teluvane/ingest.py` gains one new public (no-auth) read endpoint and one new Pro-gated
  action.

## 4. Architecture

```mermaid
flowchart TD
    Store[Postgres: events, verdicts] -->|tip hash per active session| Batcher[Anchor batcher\nteluvane/anchor.py]
    Batcher -->|Merkle tree over session tips| Tree[merkle root]
    Tree -->|anchor(root)| Contract[TeluvaneAnchorRegistry.sol\nAvalanche C-Chain]
    Contract -->|tx hash, block number| Store
    Anyone[Anyone: no account] -->|GET /verify/onchain/session_id| API[FastAPI]
    API -->|recompute tip hash + check Merkle proof against on-chain root| Contract
    Tribunal[Tribunal verdicts] -.Phase 2, design-only.-> ERC8004[ERC-8004 Validation Registry]
```

`teluvane/anchor.py` is new: a client wrapping web3.py (connect, build tx, sign with the
Fernet-decrypted hot-wallet key, send, poll for receipt) plus the pure Merkle-tree helper
(`build_merkle_tree`, `merkle_proof`) that has no blockchain dependency and is unit-testable
without a live chain.

## 5. Data model (Postgres)

New migration `0012_chain_anchors.sql`:

```sql
CREATE TABLE IF NOT EXISTS chain_anchors (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,              -- groups all sessions anchored in one tx
    org_id          TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    tip_seq         BIGINT NOT NULL,             -- events.seq this anchor covers up to
    tip_hash        TEXT NOT NULL,
    merkle_proof    JSONB NOT NULL,              -- sibling hashes to reconstruct the batch root
    merkle_root     TEXT NOT NULL,
    tx_hash         TEXT NOT NULL,
    block_number    BIGINT,
    chain_id        INTEGER NOT NULL DEFAULT 43114,
    anchored_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chain_anchors_org_session ON chain_anchors (org_id, session_id, tip_seq DESC);
```

One row per `(session, batch)` — a session anchored twice (two different batches, as new
events accrue) gets two rows; the most recent by `tip_seq` is the one that matters for "is the
chain currently anchored." `merkle_proof` is a JSON array of sibling hashes + left/right flags,
enough to recompute the batch root client-side from `tip_hash` alone, without trusting our DB.

## 6. Key flows

**Anchoring (scheduled, Pro-plan orgs only):**
1. Batcher lists every session with new events since the last anchor, across all Pro orgs.
2. For each, take the current tip (`events.hash` at the latest `seq`).
3. Build a Merkle tree over `(org_id, session_id, tip_hash)` leaves; compute the root.
4. Sign and send one `anchor(bytes32 root)` transaction to `TeluvaneAnchorRegistry` on C-Chain.
5. On receipt, write one `chain_anchors` row per session with that session's proof + the shared
   `tx_hash`/`block_number`/`merkle_root`.

**Independent verification (public, no auth, no plan gate):**
1. `GET /verify/onchain/{org_id}/{session_id}` recomputes the session's current tip hash the
   normal way (`store.verify_chain`), fetches its latest `chain_anchors` row, recomputes the
   Merkle root from `tip_hash` + `merkle_proof`, and reads the on-chain root at `block_number`
   from the contract via a public C-Chain RPC.
2. Returns `{chain_intact, anchored, merkle_root_matches, tx_hash, block_explorer_url}`. A
   caller with zero trust in TELUVANE can re-derive every step themselves from the response.

**Evidence pack:** when a session has an anchor, `build_evidence_pack` adds a section with the
tx hash, a Snowtrace (Avalanche's block explorer) link, and the proof — turning "trust our
report" into "here's how to not have to."

## 7. API surface

| Method | Path | Auth | Plan | Notes |
|---|---|---|---|---|
| GET | `/verify/onchain/{session_id}` | none | any (read-only) | New. Public verifier. |
| POST | `/anchor/run` | JWT | Pro | New. Manual "anchor now" trigger, mirrors the existing manual-audit pattern (`POST /audit/{session_id}`). |
| GET | `/anchor/status` | JWT | any | New. Last batch time, next scheduled tick, org's anchored-session count. |

## 8. Smart contract

`TeluvaneAnchorRegistry.sol` — deliberately minimal for v1, no upgradability, no access control
beyond `onlyOwner` (the hot wallet address) on the single write function:

```solidity
// SPDX-License-Identifier: AGPL-3.0-or-later
pragma solidity ^0.8.24;

contract TeluvaneAnchorRegistry {
    address public immutable owner;
    event Anchored(bytes32 indexed root, uint256 timestamp);

    constructor() { owner = msg.sender; }

    function anchor(bytes32 root) external {
        require(msg.sender == owner, "not authorized");
        emit Anchored(root, block.timestamp);
    }
}
```

No on-chain storage beyond the event log (events are cheaper than storage writes and are all a
public verifier needs — `getPastLogs` against the contract address). Deploy to **Fuji testnet**
first for development/CI, then Avalanche C-Chain mainnet once Phase 1's plan is green.

## 9. Hardening & risks (security)

- **Hot wallet key handling.** Same threat model as the existing `TELUVANE_SECRET_KEY`-encrypted
  BYOK Anthropic keys: encrypted at rest via `crypto.py`, never logged (the existing
  `logging_filter.py` secret-redaction pattern should gain the wallet key's prefix). Fund it
  with a small, replenished-as-needed AVAX balance, not a large reserve — the contract can't
  move funds, but a leaked key could still drain whatever balance sits in that address for gas.
- **RPC dependency.** A public Avalanche C-Chain RPC endpoint is a new external dependency the
  anchoring job can fail against (rate limits, downtime). Anchor job failures must not fail the
  underlying audit/tribunal flow — anchoring is additive, and a missed anchor tick just means
  the next one covers a longer span, not a broken product.
- **Nonce/gas management.** A single hot wallet sending periodic transactions needs correct
  nonce sequencing; a stuck/underpriced transaction shouldn't block the next batch. Phase 1's
  plan should keep this simple (one anchor at a time, wait for confirmation before the next)
  given TELUVANE's actual anchor frequency is nowhere near needing concurrent submission; revisit
  with OpenZeppelin Relayer (confirmed to support Avalanche C-Chain + Fuji) only if this becomes
  a real operational problem.

## 10. Grant strategy (infraBUIDL(AI))

Research confirms **infraBUIDL(AI)** (Avalanche Foundation, avax.network) is the correct target,
not the other names originally floated:

- **Program shape:** rolling application at infrabuidl.com, no fixed deadline. Tiered sizing:
  Small ≤ $20K, Medium $20K–$100K, Large case-by-case. Grantees are fast-tracked into Aethir's
  $100M compute-credit fund.
- **Realistic ask:** Small–Medium tier ($20K–$100K), framed around Phase 1 (anchoring
  infrastructure, live and testable) plus Phase 2 as the roadmap, not around Phase 2 alone —
  application against a moving-spec, undeployed registry (ERC-8004 Validation Registry has no
  confirmed Avalanche C-Chain address as of this research) is a weaker ask than application
  against something already running.
- **Pitch as infrastructure contribution, not app-layer consumption.** The committee has already
  funded **Codatta** (a data-provenance/verification marketplace) — a close precedent for "we
  verify things and put the proof where anyone can check it." **Kite AI** (Avalanche-native,
  $18M Series A, PayPal Ventures-backed, "Agent Passport" identity + policy enforcement) sits on
  the infraBUIDL(AI) committee and is the nearest neighbor in the ecosystem — but does agent
  identity/policy enforcement, not regulatory-framework verdicts (EU AI Act / ISO 42001 / NIST
  AI RMF / SOC2). Naming this distinction explicitly in the application is stronger than
  pretending Kite doesn't exist.
- **Programs ruled out:** Retro9000 (a $40M pool but purely AVAX-burn-leaderboard mechanics —
  designed for DeFi/gaming-scale transaction volume; TELUVANE's periodic-anchor pattern would
  never crack the top 40). The "Avalanche AI Innovation Grants (NVIDIA/GenAI Fund)" name from
  the initial search pass **does not check out** — the underlying program (FastTrack AI
  Accelerator, run by GenAI Fund) is Vietnam/ASEAN-focused with Avalabs as one listed partner
  among several, no confirmed blockchain-native cohort member, and no accessible general-purpose
  application channel found. Do not build a strategy around it until Ava Labs confirms it
  directly.
- **Backup/secondary channel:** Avalanche Community Grants via Gitcoin (quadratic + retroactive,
  requires Gitcoin Passport/Civic identity verification, forum proposal + community vote) — smaller,
  faster, worth running in parallel rather than instead of infraBUIDL(AI).
- **Concrete next action:** submit at infrabuidl.com; post to the official forum thread
  (forum.avax.network/t/infrabuidl-ai-program/3666) for early Foundation feedback before/alongside
  the formal application; join the Avalanche Discord and request 1:1 developer support. No live
  2026 hackathon was found at time of research (build.avax.network/hackathons empty); Team1's
  Telegram is the channel to watch for the next one.

## 11. Testing strategy

Same strict TDD convention as the rest of the repo (failing test → minimal implementation →
green → commit). `build_merkle_tree`/`merkle_proof` are pure functions, fully testable without
any network access. The web3.py-touching client (`AnchorClient.anchor_batch`) gets a thin
interface so tests inject a mock/fake provider (matching how `run_lens` in `tribunal.py` already
accepts an injectable `llm` for testability) — no real Avalanche transaction should ever run in
CI. A single live-network smoke test against Fuji testnet, gated behind an env var (mirroring
how `DEPLOY.md`'s live-verification step is optional/creds-gated), is enough for manual
pre-deploy confidence.

## 12. Out of scope (YAGNI)

- Per-customer wallets or any customer-facing wallet-connect flow — customers never touch chain
  interaction directly.
- Anchoring raw event content, evidence-pack files, or anything beyond hashes/scores on-chain.
- A dedicated Avalanche L1/subnet — no justification found for the transaction volume this
  feature actually produces.
- Token issuance, NFTs, DAO governance, on-chain billing — no product reason for any of these;
  see the marketing-council discussion (§13) on why these would actively hurt the core
  enterprise-compliance buyer's trust.
- ERC-8004 Reputation Registry integration — Validation is the relevant registry for "did this
  agent comply," Reputation is a separate feedback-signal concept not needed for v1.

## 13. Phase 2 risk note (ERC-8004 — design-only, no implementation plan yet)

ERC-8004 is a **draft EIP** (not Final), created 2025-08-13; its own reference-implementation
repo flags the Validation Registry specifically as "still under active update and discussion."
Confirmed on Avalanche C-Chain (43114): `IdentityRegistry` at
`0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` and `ReputationRegistry` at
`0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`. **No Validation Registry address is confirmed live
on Avalanche C-Chain** as of this research — meaning Phase 2 likely means deploying our *own*
instance (via the `erc-8004/erc-8004-contracts` reference) rather than calling an existing
canonical one, which is itself a defensible "infrastructure contribution" framing for the grant
application (§10), but is real, non-trivial, spec-volatile work that shouldn't be task-broken
into a TDD plan until the registry interface stabilizes or we've committed to running our own
instance regardless. Confirmed shape to design against when that happens: `validationRequest(address
validatorAddress, uint256 agentId, string requestURI, bytes32 requestHash)` /
`validationResponse(bytes32 requestHash, uint8 response, string responseURI, bytes32
responseHash, string tag)` — permissionless (no validator staking/registration required),
`response` is a 0–100 score (maps naturally onto verdict confidence), `responseURI` would point
at the evidence pack, `responseHash` a `keccak256` commitment to it.

## 14. Marketing council note (from prior session)

A simulated marketing-council review (April Dunford, Byron Sharp, Alex Hormozi, Seth Godin —
see the earlier TELUVANE Vaka Dosyası artifact) converged on: this must ship as a distinct
surface ("Web3 Trust Layer" docs/page), not blended into the EU AI Act / enterprise-compliance
landing page — the crypto-native ERC-8004/Avalanche builder audience and the compliance-officer
audience are different people with different trust triggers, and mixing the pitches weakens
both. Distribution for this feature specifically should target Avalanche/ERC-8004 developer
channels (Discord, forum, Team1), not the general compliance-buyer channels the rest of the
product targets.
