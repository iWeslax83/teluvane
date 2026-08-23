# Blockchain Trust Layer — Implementation Roadmap

> **For agentic workers:** This is an **index**, not an executable plan. Only Plan 1 below is a
> fully-detailed, standalone TDD implementation plan ready to execute. Plan 2 and Plan 3 are
> intentionally left at outline depth — see the spec's §13 and §10 for why.

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

## Plan 2 — ERC-8004 Validation Registry attestations (design-only until the spec settles)
**Not yet written as a task plan.** ERC-8004 is a draft EIP; Avalanche C-Chain has confirmed
`IdentityRegistry`/`ReputationRegistry` deployments but no confirmed `ValidationRegistry`
address. Before writing Plan 2 as an executable TDD plan, resolve: (a) whether to deploy our own
`ValidationRegistry` instance (likely, per spec §13) or wait for a canonical one, and (b)
whether an org's agent needs its own ERC-8004 identity first (Plan 2 would then also touch
`IdentityRegistry` read/write). Revisit after Plan 1 ships and/or after infraBUIDL(AI)
application feedback.

## Plan 3 — Grant application + "Web3 Trust Layer" positioning
**Not a code plan — growth/marketing work**, tracked here only for visibility:
- Submit the infraBUIDL(AI) application at infrabuidl.com once Plan 1 is live on Fuji/mainnet
  (an application pointing at a running system beats one pointing at a design doc).
- Post to the infraBUIDL(AI) forum thread and Avalanche Discord for early feedback before/alongside
  the formal submission.
- Ship a standalone "Web3 Trust Layer" page/doc (not blended into the main EU AI Act landing
  page — see spec §14) once Plan 1's public verifier endpoint exists to link to.
- Write a technical post ("how we anchor tamper-evidence to Avalanche") for distribution in
  Avalanche/ERC-8004 developer channels specifically, not the general compliance-buyer channels.

---

## Cross-cutting conventions (Plan 1)

- **TDD always:** failing test → run (see it fail) → minimal code → run (see it pass) → commit.
- **No real network calls in tests.** `AnchorClient` takes an injectable provider; CI never
  sends an actual Avalanche transaction.
- **Secrets only via env, encrypted at rest via the existing `teluvane/crypto.py` Fernet
  helper** — no new secret-storage mechanism.
- **Commits are small and frequent**, conventional-commit style (`feat:`, `test:`, `fix:`).
- Anchoring failures must never break the underlying audit/tribunal flow (spec §9).
