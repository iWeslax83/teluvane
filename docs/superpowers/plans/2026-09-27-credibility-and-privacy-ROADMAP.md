# Credibility and Privacy Roadmap (2026-09-27)

> Index for three implementation plans. This is not an executable plan. Read it first, then
> execute the plans in the order below. It is written so the work can be done from a different
> computer than the one the analysis was made on.

## Ozet (Turkce)

Bu belge, projeyi topluluga (team1) sunmadan once yapilacak isleri uc plana boler.

1. **Plan 1, durustluk:** landing sayfasindaki calismayan MCP ayari, uydurma sayilar ("event #4471", "0.94"), yanlis "her okumada dogrulanir" iddiasi, eski dokumanlar ve repo kalabaligi duzeltilir. Sitedeki kart artik gercek SHA-256 zincirini tarayicida dogrular.
2. **Plan 2, guven ve dogruluk:** kelime aramaya dayali offline dedektor yerine yapisal dedektorler, gercek cok-lensli (cogunluk oylu) tribunal, ve etiketli oturumlarla olcum (evals) eklenir.
3. **Plan 3, GDPR ve degistirilemez log:** olay icerigi zincire dogrudan degil, tuzlu bir taahhut (commitment) olarak girer. Boylece icerik silinebilir, zincir ve zincir ustu (Avalanche) kayitlar bozulmaz. Silme, saklama suresi ve yasal tutma (legal hold) eklenir.

Sirayla ilerleyin: 1, 2, 3. Ayni anda birden fazla Claude oturumu calisacaksa "Working with more than one Claude session at once" bolumundeki seritlere (lane A, B, C), ayri worktree, ayri venv ve ayri test veritabani kurallarina uyun. Baska bilgisayarda kurulum icin asagidaki "Setup on the other computer" bolumunu izleyin. Gercek traction sayisi olmadigi icin hicbir yerde kullanici veya musteri sayisi yazilmaz. Karar bekleyen sorular "Decisions needed" bolumunde.

## What this is for

The maintainer is presenting to team1, a community that gives feedback and help. A grant application has been submitted. There are no real usage numbers yet. The goal of these plans is a project whose every visible claim is true and checkable, whose weakest technical spot (detection quality) is measured openly, and whose core design tension (an unchangeable log versus a right to erasure) has a real answer.

## What the planning found

Verified in the code, not assumed.

| # | Finding | Where | Fixed by |
|---|---|---|---|
| F1 | Landing MCP config uses `"url": "https://api.teluvane.com/mcp"`. The server is stdio only (`teluvane/mcp_server.py`, `transport="stdio"`) and no `/mcp` route exists, so the copied config cannot work. | `LandingBody.tsx` | Plan 1 T3 |
| F2 | Landing shows invented output: `event #4471`, `4471/4471 events valid`, `confidence 0.94`. The hero card's "tamper" toggle only flips a boolean and prints fixed fake hashes. | `LandingBody.tsx`, `EvidenceLogCard.tsx` | Plan 1 T1 to T3 |
| F3 | "Autonomous multi-agent panel" is not what runs: one prompt per rule, one model, a `judge` node that returns `{}`, and `consolidate()` that confirms on a single flag at 0.6. | `tribunal.py` | Plan 2 T3 |
| F4 | Offline detector greps the whole log for substrings, fixed confidence 0.5, evidence lists every event. `delete`, `external`, `override` flag benign sessions. | `tribunal.py:offline_audit` | Plan 2 T1 to T3 |
| F5 | Claims a reader can check and that look wrong or unsettled: "EUR 35M or 7% ... non-compliance with EU AI Act obligations" (from memory, that tier is for prohibited practices), and "Digital Omnibus" status. | `LandingBody.tsx`, blog, `llms.txt` | Plan 1 T4 (verify against primary sources) |
| F6 | "Every read re-verifies the whole chain" is untrue: only an explicit `/verify` call verifies (`frontend/app/app/page.tsx` calls it on demand). | `LandingBody.tsx` | Plan 1 T3 |
| F7 | `.env.example` says `BLACKBOX_SECRET_KEY`; the code reads `TELUVANE_SECRET_KEY` (`teluvane/crypto.py`). A new deployer gets a `KeyError`. | `.env.example` | Plan 1 T5 |
| F8 | Grant draft names `TeluvaneAnchorRegistry`, `anchor(bytes32)`, `Anchored`. The contract is `SessionAnchorRegistry` with `anchorBatch(bytes32,uint256)` and `BatchAnchored`. The application was already submitted, so the submitted text may carry the wrong names. | `docs/grants/...` | Plan 1 T5 (maintainer reconciles) |
| F9 | One-pager: old Vercel URL, "117 tests", empty traction. Security overview says JWKS only; `auth.py` also accepts the shared secret. `DEPLOY.md` names old URLs. | `docs/` | Plan 1 T5 |
| F10 | About 80 skill directories, a Vercel report and a personal checklist are tracked in git. | `.agents/`, `.claude/skills/` | Plan 1 T6 |
| F11 | `Store.verify_chain(org_id)` without a session id chains every session together and reports any org with two sessions as tampered. | `store.py` | Plan 3 T2 |
| F12 | Event `ts` is client-supplied text that stats queries cast to timestamp. One bad value breaks those queries for the org. | `routes/sessions.py` | Plan 3 T4 |
| F13 | Chain digest covers plaintext content, so personal data cannot be erased without breaking every later hash and every anchored head; public `/verify/public` also exposes that plaintext. | `store.py` | Plan 3 |

Correction to the first analysis: it said to build an interactive tamper demo. The hero card already had a click-to-tamper toggle, but it was cosmetic. Plan 1 makes it real instead of building a second one.

## The plans

| Plan | Branch | Depends on | Produces |
|---|---|---|---|
| [Plan 1: honest landing and docs](2026-09-27-plan-1-honest-landing-and-docs.md) | `plan1/honest-landing` | none | a page whose every number and snippet is real; corrected docs; clean repo |
| [Plan 2: detector and tribunal trust](2026-09-27-plan-2-detector-and-tribunal-trust.md) | `plan2/detector-trust` | Plan 1 for Task 5 only | structural detectors, a majority-vote lens panel, an eval set with published per-rule scores |
| [Plan 3: erasable event log](2026-09-27-plan-3-erasable-event-log.md) | `plan3/erasable-log` | Plan 2 merged first (both edit `tribunal.py`) | hash version 2 events, erase, retention, legal hold, docs, runnable demo |

Design for Plan 3: `docs/superpowers/specs/2026-09-27-erasable-event-log-design.md`.

Order: Plan 1, then Plan 2, then Plan 3, each as its own pull request into `master` with CI green. Plan 3 Task 8 (deploy) has an order of its own: migrate production, then deploy.

## Working with more than one Claude session at once

Status when this section was written: the plans are on `master` (commit `e583761`), and Plan 1 is implemented in pull request #17 (`plan1/honest-landing`), waiting for review. Plans 2 and 3 have not been started. Check `gh pr list` and `git branch -r` before you begin, because this changes fast. Two or more sessions can now work in parallel. They must not share a working tree, a virtualenv or a test database, and they must stay in their own lane.

### Lanes

| Lane | Work | Branch | Owns these paths (no other lane edits them) |
|---|---|---|---|
| A: landing and docs sync | Plan 1 (done, PR #17). Then Plan 2 Task 5 and Plan 3 Task 7, once their prerequisites are merged. | `plan1/honest-landing`, then `plan2/landing-sync`, then `plan3/docs` | `frontend/components/landing/`, `frontend/lib/demoSession*`, `frontend/public/llms.txt`, `README.md`, `DEPLOY.md`, `.env.example`, `.gitignore`, `docs/investor/`, `docs/grants/`, `docs/claims-sources.md`, `docs/gdpr-and-immutable-logs.md`, `scripts/erasure_demo.py`, `tests/test_env_example.py`, `tests/test_demo_session.py` |
| B: Plan 2 backend | Plan 2 Tasks 1 to 4 (Task 6 only with the maintainer's approval). Not Task 5. | `plan2/detector-trust` | `teluvane/pii.py`, `teluvane/detectors.py`, `teluvane/tribunal.py`, `teluvane/policy.py`, `policies/`, `evals/`, `tests/test_pii.py`, `tests/test_detectors.py`, `tests/test_offline_audit.py`, `tests/test_tribunal_lenses.py`, `tests/test_tribunal.py`, `tests/test_evals.py` |
| C: Plan 3 backend | Plan 3 Tasks 1 to 4 and 6 first. Task 5 only after lane B is merged. Task 8 is run by the maintainer. Not Task 7. | `plan3/erasable-log` (split into two pull requests: 3a is Tasks 1 to 4 and 6, 3b is Task 5 after Plan 2 merges) | `migrations/`, `teluvane/commitments.py`, `teluvane/schema.py`, `teluvane/store.py`, `teluvane/retention.py`, `teluvane/scheduler.py`, `teluvane/ingest.py`, `teluvane/evidence.py`, `teluvane/routes/`, `tests/conftest.py`, the new Plan 3 test files, `tests/test_store_canonical.py`, `tests/fixtures/`, `frontend/lib/anchorVectors.test.ts`, `frontend/scripts/sync-vectors.mjs`, `frontend/lib/__fixtures__/` |

One session can hold more than one lane in sequence, but never two at the same time. If two sessions start, the natural split is: one takes lane B, the other takes lane C, and whichever finishes first takes lane A's remaining work.

The only file both B and C ever touch is `teluvane/tribunal.py` (Plan 3 Task 5 changes `_events_to_text`). That is why Task 5 waits for Plan 2 to merge. If a lane needs a file that another lane owns, stop and tell the maintainer instead of editing it. Sessions cannot reliably message each other; coordinate through pull requests and the maintainer.

### Order and hand-offs

1. Now, in parallel: lane B starts Plan 2, lane C starts Plan 3 (3a). Plan 1 is already out for review.
2. Lane A's remaining work waits: Plan 2 Task 5 needs pull request #17 and Plan 2 (Tasks 1 to 4) merged; Plan 3 Task 7 needs Plan 3 Tasks 1 to 5 merged (it runs `scripts/erasure_demo.py` against a database).
3. Merge order into `master`: #17 any time; Plan 2 backend; Plan 3a; Plan 3b; then lane A's two follow-ups. After any merge, every other lane runs `git fetch origin && git rebase origin/master` before it opens or updates its pull request.
4. Production: only the maintainer runs Plan 3 Task 8 (migrate production, then deploy).

### Isolation rules

Concurrent sessions in one checkout will overwrite each other's edits. Follow all of these.

- **One git worktree per session.** From the main checkout:

```bash
git fetch origin
git worktree add ../teluvane-lane-b -b plan2/detector-trust origin/master
cd ../teluvane-lane-b
```

- **One virtualenv per worktree.** An editable install points at a single directory, so the main checkout's `.venv` would import the wrong copy of `teluvane`. Create a new one and check it:

```bash
python3.11 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python -c "import teluvane; print(teluvane.__file__)"   # must print a path inside THIS worktree
(cd frontend && npm ci)
```

- **One test database per session.** `tests/conftest.py` truncates tables, so two sessions on one database corrupt each other's runs. One Postgres container can serve both:

```bash
docker exec teluvane-db psql -U postgres -c "CREATE DATABASE teluvane_test_b"   # lane C uses teluvane_test_c, lane A teluvane_test_a
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/teluvane_test_b
export DATABASE_URL=$TEST_DATABASE_URL SUPABASE_JWT_SECRET=test-secret
export TELUVANE_SECRET_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
```

- **Different dev-server ports** when running `next dev` or `next start` (for example 3117 for lane A, 3127 for lane B, 3137 for lane C).
- **Stage explicit paths only.** Never run `git add -A` or `git add .`. The main checkout carries unrelated local edits under `.agents/skills/`, and they must not end up in a commit.
- **Migrations:** only lane C creates migrations (`0014`). If that ever changes, run `ls migrations` first and take the next free number.
- **Progress is reported in the pull request description** (a checklist of tasks), not in a shared file, so two sessions never edit the same file to report status.
- **Rebase before you push,** keep pull requests small (one plan or sub-plan each), and wait for CI before merging.

## Setup on the other computer

The first analysis ran on a machine with local state that will not exist elsewhere: gitignored `.env` and `.env.local`, a virtualenv that was missing two dependencies, and global assistant rules in `~/.claude/CLAUDE.md`. Do this on the new machine.

1. **Get the plans.** They are on `master` (commit `e583761`).

```bash
git clone git@github.com:iWeslax83/teluvane.git && cd teluvane
git checkout master && git pull
ls docs/superpowers/plans | grep 2026-09-27
```

2. **Toolchain.** Python 3.11 (CI uses 3.11), Node 20 or newer (CI uses 20; the analysis ran on 24), Docker for Postgres, `gh` and an SSH key for GitHub. Foundry is only needed for `contracts/`, which these plans do not touch.

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"      # do a fresh install: the old venv lacked sentry-sdk and web3
cd frontend && npm ci && cd ..
```

`weasyprint` needs Pango and Cairo system libraries for the PDF code path. Install them from your OS package manager if the PDF test fails to import.

3. **Postgres.** Every `pytest` run needs it, because `tests/conftest.py` applies migrations at session start. CI uses Postgres 15; the analysis validated on 16. If something passes locally and fails in CI, suspect the version first.

```bash
docker run -d --name teluvane-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=teluvane_test -p 5432:5432 postgres:15-alpine
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/teluvane_test
export DATABASE_URL=$TEST_DATABASE_URL
export SUPABASE_JWT_SECRET=test-secret
export TELUVANE_SECRET_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
```

4. **Baseline before any change.** Run both suites and write the numbers down.

```bash
pytest -q
cd frontend && npm test && cd ..
```

Known noise that is not yours to fix: `npx tsc --noEmit` reports one error in `frontend/app/app/billing/page.test.tsx`; `ruff check` reports older findings (`tests/conftest.py` E402 and a few E501). CI runs neither. `tests/test_anchor_chain.py` needs `web3`, which `pip install -e ".[dev]"` provides.

5. **Secrets.** Do not copy `.env` files through chat or email. Plans 1 and 2 need no production secrets. Plan 3 Task 8 needs the production `DATABASE_URL`, which only the maintainer should hold and type. Plan 2's optional live eval needs the maintainer's Anthropic key.

6. **Working rules for whoever executes** (the maintainer's global assistant rules, copied here because they live outside the repo):

- No em dashes anywhere (code, comments, commits, docs, site text).
- UI: flat background and exactly one accent color, no gradients, no glassmorphism, no purple, no pill status badges, no emoji, no three-icon-card rows, no fake testimonials or dashboards. One real font. Body line height 1.5 to 1.6.
- Copy: plain and concrete. No "empower", "unleash", "revolutionize", "supercharge".
- If something is unknown and not in the plan (a host, a number, a legal fact), ask the maintainer. Do not guess.
- Never put claude.ai or session links in commits, PRs or comments.
- Any scripted browser check uses Chromium only.
- `frontend/AGENTS.md`: this Next.js differs from training data; read `frontend/node_modules/next/dist/docs/` before Next-specific code.
- Design work also uses the design skills where available. Project tokens in `frontend/lib/landingTheme.ts` win over any skill.

7. **Branch per plan**, PR into `master`, wait for CI (secrets scan, backend, frontend, contracts) before merging.

## Decisions needed from the maintainer

Nothing in the plans guesses these.

1. **Live tribunal cost.** Three lenses triple the model calls per audit, and the hosted-key monthly cap (`teluvane/usage.py`) counts audits, not calls. Choose the production default for `TRIBUNAL_LENS_COUNT` (1 to 3) before Plan 2 ships to the hosted key.
2. **License.** The README badge says Proprietary, the repo is public, and the contract file is MIT. Pick one story before the presentation.
3. **API host on the landing page.** The MCP snippet reads `NEXT_PUBLIC_API_URL`. Confirm it is set on Vercel to the real API host, or the page shows `https://YOUR-API-HOST`.
4. **The grant application.** What exactly was submitted, and whether to send the program a correction for the names in F8. Nothing in this repo sends anything for you.
5. **Mainnet.** The code and docs describe Avalanche Fuji (testnet). Say plainly whether mainnet exists, in the presentation and the docs.
6. **Legal review.** The policy packs have five rules each. Before saying they cover an article of a framework, someone with compliance background should review the rule-to-article mapping. Decide who.
7. **Old checklist in git history.** `dontforgettomakeitlooklikearealwebsite.txt` names a school address and stays in history after Plan 1 T6. Decide whether that matters; removing it from history is a separate, riskier operation.
8. **Erasure UI and default.** Plan 3 is API-first and makes hash version 2 the default for everyone. Say if it should be opt-in or if the dashboard needs erase, retention and hold controls before the presentation.

## Presentation kit for team1

Frame it as early-stage with real engineering and open questions. There are no customers and no usage numbers, so the talk should not contain any.

**Five-minute flow**

1. One sentence: agents act, and today the logs that say what they did can be edited afterwards. TELUVANE makes edits visible and lets an outsider check.
2. Live: the landing hero card. Click event 3, watch `BROKEN at #3`, restore. Say that it runs the same `verifyChain` as the `/verify` page.
3. Live: `python scripts/erasure_demo.py` against a scratch database. Personal data erased, every hash identical, chain still verifies (Plan 3).
4. The table from `evals/RESULTS.md`, with the caveat spoken aloud: the same people wrote the detectors and the test sessions, so this shows the rules separate the cases we thought of.
5. What is not done (below), and what we want from the room.

**Say what is not done:** no customers, Fuji testnet only unless the maintainer says otherwise, rule packs have five rules each and are not reviewed by a compliance expert, no dashboard UI for erasure, the erasure log is not itself tamper-evident, older events cannot be erased.

**What to ask the community for**

- Scenarios that make the detectors fail (`evals/CONTRIBUTING.md`). This is the highest-value ask.
- A critique of the erasure design, especially section 5 (limits) and 8 (open questions) of the spec.
- Someone with compliance experience to review the rule packs.
- One or two design partners for a real trial.
- Feedback on the landing page: can a stranger tell in ten seconds what it does and that it is real?

**Do not say:** "GDPR compliant" or "makes you compliant" (Plan 3 forbids it in copy), any user, session or revenue number, "multi-agent" unless Plan 2 has shipped, "on mainnet" unless it is.

## Deliberately not in these plans

Backlog, roughly in order of value: expand and legally review the policy packs; an OpenTelemetry GenAI ingest endpoint; a lightweight `teluvane-sdk` split from the server package and publishing to PyPI and npm; running the scheduler and anchoring in a separate worker instead of an in-process thread; mainnet deployment with a multisig owner and key rotation; an HTTP transport for the MCP server; lint and end-to-end tests in CI; a tamper-evident erasure log; detect-then-mask at ingest; an erasure and retention UI.

## How this was validated

The code shown in the plans was run before it was written down, on a scratch copy of the repository against a real Postgres 16 container: the full backend suite (258 tests, excluding `tests/test_anchor_chain.py`, which needs `web3` that the old virtualenv lacked), the frontend suite, a webpack production build, and the server-rendered landing HTML (one `h1`, no forbidden strings). Not validated: Postgres 15 (what CI runs), the Turbopack build (the scratch copy used a symlinked `node_modules`, which Turbopack rejects), `tests/test_anchor_chain.py`, and the live tribunal against the real Anthropic API. CI on each pull request is the check for the first three. The live run is Plan 2 Task 6.
