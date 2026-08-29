# Blockchain Trust Layer — Implementation Roadmap

> **For agentic workers:** This is an **index**, not an executable plan. As of 2026-08-24, all
> three plans are now fully detailed and executable — Plan 1 (code, TDD), Plan 2 (code, TDD, its
> two previously-open design questions are now resolved decisions — see its §0), and Plan 3
> (growth/marketing execution, checkbox-tracked). See §"Cross-phase execution timeline" below for
> how they fit together in time, not just in dependency order.

**Spec:** `docs/superpowers/specs/2026-08-23-blockchain-trust-layer-design.md`

**Goal:** Give TELUVANE's tamper-evidence claim an independent, publicly-checkable witness
(Avalanche C-Chain) instead of only trusting TELUVANE's own database, and use that as the
technical core of an Avalanche Foundation infraBUIDL(AI) grant application.

**Why sequenced this way:** Plan 1 has zero dependency on anything outside our control (no
external spec to stabilize, no registry to wait on) and is valuable on its own regardless of
grant outcome — it directly strengthens the product's core existing claim. Plan 2 depends on an
externally-controlled draft spec (ERC-8004) that isn't fully deployed on our target chain yet.
Ship Plan 1, apply for the grant with it, revisit Plan 2 once the Validation Registry situation
resolves one way or the other.

---

## Plan 1 — Chain-tip anchoring (buildable now)
**File:** `2026-08-23-plan-1-chain-tip-anchoring.md`
Merkle-batch every Pro-plan org's active session tip hashes, anchor the batch root to a minimal
`TeluvaneAnchorRegistry` contract on Avalanche C-Chain (Fuji testnet first) on a scheduled tick,
store per-session Merkle proofs, and expose a public, no-auth `/verify/onchain/{session_id}`
endpoint plus an evidence-pack section so anyone can independently confirm a session's chain
hasn't been altered since it was anchored.
**Produces:** a live, independently verifiable anchor for real customer data, and the concrete
artifact the infraBUIDL(AI) application points to.

## Plan 2 — ERC-8004 Validation Registry attestations
**File:** `2026-08-24-plan-2-erc8004-validation-registry.md`
Both design questions the earlier version of this roadmap left open are now resolved (decisions
recorded in that plan's §0, and mirrored into spec §13):
- **Deploy our own `ValidationRegistry` instance** rather than wait for a canonical one on
  Avalanche C-Chain — no canonical instance is confirmed deployed there, and self-deploying is
  itself a defensible "infrastructure contribution" for the grant pitch (spec §10), not a
  workaround.
- **Register each org's audited agent against the existing canonical `IdentityRegistry`**
  (already confirmed live on C-Chain) rather than deferring identity — Validation responses are
  keyed by `agentId`, so an agent needs an on-chain identity before its first Tribunal verdict can
  be attested.
Publishes each Tribunal verdict batch as a 0–100 validation score (deterministic function of
verdict severity/confidence, unit-tested independent of any chain interaction) plus a
`keccak256` commitment to the evidence pack, submitted to the self-deployed `ValidationRegistry`.
**Hard prerequisite before executing this plan's contract-touching tasks:** re-verify the exact
current `IdentityRegistry`/`ValidationRegistry` interface against live sources — ERC-8004 is a
fast-moving draft spec and the plan's own §0 flags exactly what to check before trusting any
ABI written into it.

## Plan 3 — Grant application, "Web3 Trust Layer" page, and distribution
**File:** `2026-08-24-plan-3-grant-and-positioning.md`
Growth/marketing execution work, not a code TDD plan, but checkbox-tracked the same way so
progress stays visible across sessions. Covers: drafting and submitting the infraBUIDL(AI)
application (gated on Plan 1 being live and independently verifiable), forum/Discord outreach,
a standalone `/trust-layer` frontend page (deliberately not blended into the compliance-buyer
landing page — spec §14), a technical distribution blog post, and the secondary Avalanche
Community Grants (Gitcoin) channel. Has its own internal dependency-ordered timeline table since
there's no external grant deadline to anchor to.

---

## Cross-phase execution timeline

Dependency-ordered (no calendar dates — infraBUIDL(AI) is rolling, and Plan 1's actual build
speed depends on who's implementing it), so read this as "what can start when," not a schedule:

1. **Now, in parallel:** Plan 1 implementation (Tasks 1–7, no external dependency) *and* Plan 3's
   drafting-only steps (A1 grant narrative draft, B1/C1 content outlines) — neither blocks the
   other, and starting the grant narrative early means it's ready the moment there's something
   live to point it at.
2. **Plan 1 Task 8, Step 3 (Fuji anchor verified live):** this is the real unlock point. It clears
   Plan 3's decision gate (§0 of that plan) for everything downstream, and it's also the natural
   moment to start Plan 2 — Plan 2 doesn't strictly require Plan 1 to be done, but attesting
   Tribunal verdicts on-chain is a stronger pitch once the anchoring half is demonstrably working,
   and reuses the same `AnchorClient`/wallet/RPC plumbing Plan 1 already built.
3. **Plan 1 Task 8, Step 4 (mainnet deploy) + Plan 3 B1/C1 (Web3 Trust Layer page + blog post
   live):** now the infraBUIDL(AI) application (Plan 3 A4) has real links to point at instead of
   a design doc — submit here, not before.
4. **Plan 2, once its own §0 interface re-verification and contract deployment are done:** revise
   the already-submitted grant application (or, if not yet submitted, fold Plan 2 in as a second
   proof point) — Plan 2 was *pitched* as the funded roadmap item in Plan 3's A1 narrative, so its
   actual completion is evidence for a progress update to the committee, not a blocker on A4.
5. **Ongoing:** Plan 3's Section success metrics (forum/Discord engagement, referral traffic,
   grant outcome) get checked periodically — these aren't one-time tasks, they're what tells
   whether this whole initiative is working, independent of whether every checkbox above is
   ticked.

## Cross-cutting conventions (Plans 1 and 2)

- **TDD always:** failing test → run (see it fail) → minimal code → run (see it pass) → commit.
- **No real network calls in tests.** `AnchorClient` (Plan 1) and the Plan 2 registry clients
  take an injectable provider; CI never sends an actual Avalanche transaction.
- **Secrets only via env, encrypted at rest via the existing `teluvane/crypto.py` Fernet
  helper** — no new secret-storage mechanism. Plan 2 reuses Plan 1's wallet unless its own plan
  says otherwise.
- **Commits are small and frequent**, conventional-commit style (`feat:`, `test:`, `fix:`).
- Chain-touching failures (anchoring or validation attestation) must never break the underlying
  audit/tribunal flow (spec §9) — both are additive layers, not load-bearing for the core product.
