# infraBUIDL(AI) Application Draft — TELUVANE

> Status: **submitted** on `[fill in: submission date]`. Per ROADMAP finding F8, the text as
> submitted may still name the old contract (`TeluvaneAnchorRegistry`, `anchor(bytes32)`,
> `Anchored`) that this draft has since corrected below. See the reconciliation checklist at the
> bottom of this file for what only the maintainer can check against the submitted text.

**Target program:** infraBUIDL(AI), Avalanche Foundation — infrabuidl.com, rolling application,
no fixed deadline.

**Requested tier:** Small–Medium ($20K–$100K), framed around Phase 1 (live, testable today or
shortly) with Phase 2 (ERC-8004 Validation Registry) as the funded roadmap item — not around
Phase 2 alone, since Phase 2 depends on a draft spec and an undeployed registry.

---

## What we're building

TELUVANE audits AI agent behavior against regulatory frameworks (EU AI Act, ISO 42001, NIST AI
RMF, SOC2) and produces a tamper-evident audit trail for every session via a SHA-256 hash chain,
where each event commits to the full prior history.

That hash chain is currently a vendor-asserted guarantee: customers have to trust TELUVANE's own
database wasn't altered after the fact. We're removing that trust requirement by periodically
anchoring session chain-tip hashes — batched via a Merkle tree — to **Avalanche C-Chain**, so
tamper-evidence becomes independently, publicly checkable by anyone with a block explorer, not
just asserted by us. A minimal, non-upgradable contract
(`SessionAnchorRegistry.sol`: one owner-only `anchorBatch(bytes32 root, uint256 sessionCount)`
write, a public `anchoredAt(bytes32)` read, and a `BatchAnchored` event; nothing else is stored)
is the whole footprint, no raw data, no evidence-pack content, no PII ever touches the chain,
only hashes.

Once Phase 2 ships, Tribunal compliance verdicts get published as ERC-8004 Validation Registry
attestations: a 0–100 validation score (deterministic function of verdict severity/confidence)
plus a `keccak256` commitment to the underlying evidence pack, submitted against a
self-deployed `ValidationRegistry` instance and keyed to each org's agent identity in the
existing canonical `IdentityRegistry`.

**We're building infrastructure other builders can query and verify against — a public good —
not consuming Avalanche as an app-layer feature.**

## Why Avalanche specifically

- ERC-8004's `IdentityRegistry` (`0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`) and
  `ReputationRegistry` (`0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`) are already live on
  Avalanche C-Chain (43114) — this is a real, working piece of agent-identity infrastructure to
  build against today, not a bet on a future deployment.
- Sub-$0.10 gas per anchoring write on C-Chain makes periodic anchoring economically viable at
  TELUVANE's actual transaction volume (periodic batches, not per-event writes). A general-purpose
  L1 with materially higher gas would not clear this bar at the same frequency.
- No prior art found for this exact combination — AI agent regulatory-audit trails anchored to an
  EVM chain for independent verification. This is genuine white space on Avalanche, not a
  repositioning of an existing product onto a trendier stack.

## Differentiation from Kite AI

Kite AI sits on the infraBUIDL(AI) committee and is the nearest ecosystem neighbor: Avalanche-
native agent identity + policy *enforcement* ("Agent Passport"), $18M Series A, PayPal Ventures-
backed. We name this explicitly rather than pretend it doesn't exist, because the committee will
notice either way.

The distinction: Kite answers "is this agent who it says it is, and is it allowed to act." TELUVANE
answers a different question — "did this agent's actual behavior comply with a specific regulatory
framework (EU AI Act, ISO 42001, NIST AI RMF, SOC2), and can a third party independently verify that
verdict wasn't altered after the fact." Identity/policy enforcement and independent regulatory
verdicts are complementary, not competing — an agent could hold a Kite passport and still need a
TELUVANE-style compliance verdict anchored on-chain for an EU AI Act auditor.

## Precedent

**Codatta** (data-provenance/verification marketplace) is already funded by this committee and is
the closest prior grantee shape: "we verify things and put the proof where anyone can check it."
TELUVANE fits the same pattern applied to AI-agent regulatory compliance instead of data
provenance.

## What we're asking for

Small–Medium tier ($20K–$100K). Use: cover the engineering time to take Phase 1 from
Fuji-tested to mainnet-hardened (RPC redundancy, monitoring, nonce/gas handling under real load)
and to execute Phase 2 (ERC-8004 Validation Registry self-deployment and integration) once the
registry interface is stable enough to commit to.

## Proof points

*(to be filled in once live — placeholders until Plan 1 Task 8 ships; do not submit with these
still blank)*

- Live `/verify/public/{session_id}` endpoint: `TODO`
- A real anchoring transaction hash on Snowtrace (Fuji or mainnet): `TODO`
- "Web3 Trust Layer" page (Plan 3 Section B): `TODO`
- Technical blog post, "How we anchor tamper-evidence to Avalanche" (Plan 3 Section C): `TODO`

---

## Self-review checklist (Plan 3 Step A2)

Sanity question per the plan: *would this application still make sense if the ERC-8004 angle
turned out to be a dead end?* — Yes. Phase 1's anchoring alone (independent, publicly verifiable
tamper-evidence for AI-agent audit trails) is a real, funded-grade infrastructure contribution on
its own; ERC-8004 is upside, not the load-bearing part of the pitch.

- [ ] Reviewed by original author (iWeslax83 / Emir Sakarya) if reachable, focused on the
      "why Avalanche, why us" framing specifically — a grant committee weighs founder conviction.
- [ ] If not reachable: self-review against the question above completed and nothing contradicts
      the spec (`docs/superpowers/specs/2026-08-23-blockchain-trust-layer-design.md` §10, §13).
- [ ] Proof-point placeholders above are filled in with real links before submission.

## Next steps (Plan 3)

- **A2** — outside review (see checklist above).
- **A3** — post a shorter version of this narrative to
  forum.avax.network/t/infrabuidl-ai-program/3666 for early committee feedback.
- **A4** — formal submission at infrabuidl.com, gated on Plan 1 Task 8.
- **A5** — join Avalanche Discord (discord.com/invite/avax) for 1:1 developer feedback, independent
  of the grant process.
- **A6** — Avalanche Community Grants (Gitcoin), secondary channel, after A4.

## Reconciliation with the submitted application (maintainer, manual)

- [ ] Open the text as submitted in the grant portal.
- [ ] Compare it with the facts above. Note every place it names TeluvaneAnchorRegistry,
      anchor(bytes32), or an Anchored event, or claims a mainnet deployment, users,
      customers or traction that do not exist.
- [ ] Decide whether to send the program a short correction. Do not send anything until you
      have decided; nothing in this repo sends it for you.
