# Plan 3 — Grant Application, Positioning & Distribution

> **For agentic workers:** This is growth/marketing execution work, not a code plan — no TDD
> cycle applies. Steps still use checkbox (`- [ ]`) syntax so progress is trackable the same way
> as the code plans. Read `docs/superpowers/plans/2026-08-23-blockchain-trust-layer-ROADMAP.md`
> first for how this fits against Plan 1 (chain-tip anchoring, code) and Plan 2 (ERC-8004, code).

**Goal:** Turn Plan 1 (and, once written, Plan 2) into (a) a funded Avalanche Foundation
infraBUIDL(AI) grant and (b) a credible "Web3 Trust Layer" positioning surface that reaches the
Avalanche/ERC-8004 developer audience — a different audience from the EU AI Act / enterprise-
compliance buyer the rest of teluvane.com targets (spec §14).

**Spec:** `docs/superpowers/specs/2026-08-23-blockchain-trust-layer-design.md` §10 (grant
strategy), §14 (marketing council note).

**Hard dependency:** Section A (grant submission specifically — not the drafting work) cannot
complete until Plan 1 is deployed and independently verifiable by a stranger (Task 8 of Plan 1:
`/verify/onchain/{session_id}` returning a real tx hash that resolves on a public block
explorer). An application pointing at a running system beats one pointing at a design doc — this
is the whole reason Plan 1 is sequenced before the grant push, not the other way around. Drafting
work (this plan's Steps A1–A3) has no such dependency and can start immediately, in parallel with
Plan 1's implementation.

---

## Section A — infraBUIDL(AI) grant application

**Target:** submit at infrabuidl.com. Rolling basis, no fixed deadline, so there's no
externally-imposed date — the schedule below is self-imposed to avoid this drifting indefinitely
now that a new collaborator (not the original solo builder) can own it in parallel with the code.

- [x] **A1. Draft the application narrative** (can start now, no dependency) — done 2026-08-24,
  see `docs/grants/infrabuidl-ai-application-draft.md`.
  Write a standalone doc (`docs/grants/infrabuidl-ai-application-draft.md` — new directory, this
  is the first grant application teluvane has written) covering, per spec §10:
  - **What we're building:** independent, publicly-checkable witness for AI agent audit trails
    (Plan 1) plus, once Plan 2 exists, ERC-8004 Validation Registry attestations of Tribunal
    verdicts — framed as *infrastructure contribution* (a public good other builders can query),
    not app-layer consumption of Avalanche.
  - **Why Avalanche specifically:** ERC-8004's IdentityRegistry/ReputationRegistry are already
    live on C-Chain (cite the confirmed addresses from spec §13); sub-$0.10/write gas makes
    periodic anchoring economically viable at teluvane's actual transaction volume, which a
    general-purpose L1 with higher gas would not.
  - **Differentiation from Kite AI** (sits on the infraBUIDL(AI) committee, nearest ecosystem
    neighbor): Kite does agent identity + policy *enforcement*; teluvane does independent,
    third-party-verifiable regulatory-framework *verdicts* (EU AI Act / ISO 42001 / NIST AI RMF /
    SOC2) anchored on-chain. Name this explicitly rather than omitting it — spec §10 flags
    pretending a near-neighbor doesn't exist as the weaker move.
  - **Precedent to cite:** Codatta (data-provenance/verification, already funded by this
    committee) as the closest prior grantee shape.
  - **Ask:** Small–Medium tier ($20K–$100K per spec §10). Frame the ask around Plan 1
    (live, testable today) with Plan 2 as the funded roadmap item — not around Plan 2 alone.
  - **Proof points to link:** the live `/verify/onchain/{session_id}` endpoint, a Snowtrace tx
    hash, and (once it exists) the "Web3 Trust Layer" page from Section B below.
  - Done when: draft doc exists, self-reviewed against the spec §10 bullets above with nothing
    contradicted.

- [ ] **A2. Get outside review before submitting**
  Run this draft through `/plan-ceo-review` or `/design-consultation`-style scrutiny is
  overkill for a grant narrative — instead, if the original author (iWeslax83 / Emir Sakarya) is
  reachable, get a sanity check from them specifically on the "why Avalanche, why us" framing,
  since a grant committee will weigh founder conviction. If not reachable, self-review against
  one question: *would this application still make sense if the ERC-8004 angle turned out to be
  a dead end?* (It should — Plan 1's anchoring alone is a real, funded-grade infrastructure
  contribution independent of ERC-8004's fate.)
  Done when: reviewed once, revised if needed.

- [ ] **A3. Post to the forum thread for early feedback**
  Post a shorter version of A1's narrative (a few paragraphs, not the full doc) to
  forum.avax.network/t/infrabuidl-ai-program/3666, asking specifically whether the committee
  would rather see the application after Plan 1 ships or is fine reviewing against a near-final
  implementation plan now. This de-risks A4 by surfacing objections before the formal submission
  uses up whatever first-impression goodwill exists.
  Done when: posted, and either a response is received or ~1 week has passed with no response
  (rolling program — don't block indefinitely on a forum reply).

- [ ] **A4. Submit the formal application** — **gated on Plan 1 Task 8 (live Fuji or mainnet
  deploy) being done.**
  Submit at infrabuidl.com using A1's narrative, updated with A2/A3 feedback and real links (the
  verify endpoint, a real tx hash, the Web3 Trust Layer page from Section B if it exists yet).
  Done when: submitted, confirmation received.

- [ ] **A5. Join Avalanche Discord for 1:1 developer support**
  discord.com/invite/avax — introduce the project, ask for feedback on the technical approach
  independent of the grant process itself (this is a distribution/credibility channel on its own,
  not just a grant-support channel). Can happen any time, ideally before or alongside A3.
  Done when: joined, one substantive conversation had (not just a join-and-lurk).

- [ ] **A6. Secondary channel: Avalanche Community Grants (Gitcoin)** — optional, parallel, not
  a blocker for anything else.
  Requires Gitcoin Passport/Civic identity verification, a forum proposal, and a community vote —
  smaller and slower-to-materialize than infraBUIDL(AI) but worth running in parallel per the
  reference memory on Avalanche grant channels. Revisit after A4 is submitted, not before —
  don't split attention across two applications simultaneously while A1–A4 are still in motion.

---

## Section B — "Web3 Trust Layer" page (frontend, standalone surface)

Per spec §14 (marketing council note): this must NOT be blended into the existing EU AI Act /
enterprise-compliance landing page. The crypto-native Avalanche/ERC-8004 builder audience and the
compliance-officer audience are different people with different trust triggers; mixing the
pitches weakens both.

- [ ] **B1. New standalone route**
  Add `frontend/app/trust-layer/page.tsx` (follow the existing app-router page pattern — read
  `frontend/app/accessibility/page.tsx` first as a same-weight standalone-page precedent before
  writing this one). NOT linked from the main nav/hero alongside the compliance-buyer CTAs;
  linked instead from the footer (`frontend/components/landing/Footer.tsx`) under a low-key
  "Developers" or "Web3" heading, and directly from grant/forum/Discord posts.
  Content: what gets anchored and why (spec §1–§2 in plain language), the public verify endpoint
  with a live example a visitor can actually query, the ERC-8004 angle once Plan 2 exists, and a
  link to the technical blog post (Section C). No pricing, no "book a demo" CTA — this page's
  job is credibility with builders, not conversion.
  Done when: page exists, builds, passes existing lint/test conventions
  (`npm run lint`, relevant `*.test.tsx` if the repo's convention is to add one per page —
  check `frontend/app/accessibility/page.tsx`'s sibling test file for precedent).

- [ ] **B2. Link from evidence pack** (small, once Plan 1 Task 7 ships)
  The evidence pack's on-chain anchor section (Plan 1 Task 7) should link to B1's page for "what
  does this mean" context, not just the raw Snowtrace link — a compliance officer opening an
  evidence pack and seeing a bare block-explorer link with no explanation is a worse experience
  than one with a plain-language landing spot to click through to.

---

## Section C — Technical distribution content

- [ ] **C1. Write the technical blog post**
  "How we anchor tamper-evidence to Avalanche" (or similar) — add to
  `frontend/lib/blogPosts.ts` following the existing three-post pattern (`slug`, `title`,
  `description`, `date`) and the corresponding post content under `frontend/app/blog/` /
  `frontend/components/blog/` (read how the three existing posts — `eu-ai-act-article-50-2026`,
  `tamper-evident-agent-logs`, `iso-42001-nist-ai-rmf-soc2` — are structured before adding a
  fourth, to match voice and format exactly). Audience is developers, not compliance buyers:
  lead with the Merkle-batching mechanism and the public verify flow, not EU AI Act framing.
  Done when: post exists, builds, appears in the blog index.

- [ ] **C2. Distribute C1 specifically to Avalanche/ERC-8004 channels**
  Per spec §14: post to the Avalanche forum, Discord, and (if active by then) Team1's Telegram —
  not teluvane's general/compliance-buyer channels. Check build.avax.network/hackathons again at
  distribution time (empty as of 2026-08-23/24 research; a live hackathon by C2's execution time
  would be a stronger distribution moment than a cold forum post).

---

## Timeline (self-imposed, no external deadline)

| When | What | Depends on |
|---|---|---|
| Now (2026-08-24) | Start A1 (draft narrative), B1/C1 outlines | nothing |
| While Plan 1 Tasks 1–7 are in progress | Finish A1, run A2, run A3, A5 | nothing (parallel to code) |
| Plan 1 Task 8 done (Fuji live) | B1 page ships with a real live example | Plan 1 |
| Shortly after Task 8 | C1 published, C2 distributed | B1 (post links to it) |
| Once B1 + C1 exist and A3 feedback (if any) is incorporated | A4: formal submission | Plan 1 live, B1, C1 |
| After A4 | A6 (Gitcoin, optional) | A4 submitted |

This is intentionally not calendar-dated (no fixed grant deadline exists to anchor to) — it's
dependency-ordered so whoever picks this plan up next can tell what's blocked on what regardless
of exactly when Plan 1's code lands.

## Success metrics

- infraBUIDL(AI) application submitted (binary — either A4 is done or it isn't).
- At least one substantive response from the forum thread (A3) or Discord (A5) — a signal the
  application isn't going into a void, independent of a funding decision.
- `/trust-layer` page live and receiving referral traffic from Discord/forum links specifically
  (distinguish this from teluvane.com's existing compliance-buyer traffic — different audience,
  should be tracked separately per the existing analytics/UTM conventions if the project has one;
  check `EduTask`/`KOBİKON`-style UTM conventions aren't assumed to exist here without checking
  teluvane's own analytics setup first).
- Grant outcome itself (funded / not funded / still pending) is not a success metric for this
  plan's *completion* — submitting a credible application is the deliverable; the funding
  decision is outside teluvane's control.

## Out of scope

- Any token issuance, NFT, or DAO-governance angle for marketing purposes — spec §12 already
  rules this out product-wise; it should not resurface here as a growth gimmick either.
- Paid ads or influencer spend targeting the Avalanche/crypto audience — this is a credibility and
  developer-relations play (content + community channels), not a paid-acquisition one, at this
  stage and budget.
