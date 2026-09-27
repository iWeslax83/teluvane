# TELUVANE

**Flight recorder + compliance tribunal for AI agents.**

[![CI](https://github.com/iWeslax83/teluvane/actions/workflows/ci.yml/badge.svg)](https://github.com/iWeslax83/teluvane/actions/workflows/ci.yml)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-lightgrey.svg)](#)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)

**[teluvane.com](https://teluvane.com)**

---

## What it is

TELUVANE is a tamper-evident flight recorder and compliance tribunal for AI agents. Every LLM
call, tool invocation, and tool result gets recorded and SHA-256 hash-chained per session: tamper
any stored row and the chain breaks visibly. A tribunal then audits the session log against a
policy pack (the EU AI Act pack ships by default, plus your own custom rules on paid plans) and
produces cited verdicts, either with deterministic offline detectors or a live
LangGraph + Claude tribunal if you supply an Anthropic key.

It's a real multi-tenant product, not a demo: Supabase-authenticated orgs, API keys for machine
ingestion, LemonSqueezy billing, and a Postgres-backed store, not a single-user local script.

---

## How it works

| Piece | What it does |
|---|---|
| **Recorder** | Agents POST events (`llm_call`, `tool_call`, `tool_result`) to the API using an org's API key. Each event is SHA-256 hash-chained to the previous one within its session. |
| **Tribunal** | Runs against the merged policy pack (built-in EU AI Act rules plus any custom rules an org has added). Without an Anthropic key it runs structural detectors (tool name, approval field, checksum-validated personal data such as card, IBAN and national id numbers) and falls back to word-start keyword matching for rules that have no detector, including custom rules. With a key, three Claude lenses (auditor, skeptic, literalist) each judge every rule and a finding needs a majority. Set `TRIBUNAL_LENS_COUNT=1` to run one lens at a third of the cost. |
| **Automated runs** | Pro orgs can put the tribunal on a timer instead of clicking "Run audit" (see Settings in the dashboard). |
| **Evidence pack** | Exports a self-contained report (HTML on every plan, PDF export on Pro) with the full event log, verdict table, chain-integrity status, and framework citations. |

On Pro plans, finalized sessions are also batched into a Merkle tree and their root is written to the `SessionAnchorRegistry` contract on Avalanche Fuji (a testnet; there is no mainnet deployment). Only the root hash and a session count go on chain, never event content or personal data. Once a session is anchored, anyone can recompute its chain head and Merkle root from a copy of the event log and check it against the on-chain record at [teluvane.com/verify](https://teluvane.com/verify), with no TELUVANE account and without trusting our database.

---

## Architecture

- **Frontend**: Next.js dashboard on Vercel. Supabase handles auth (email/password); the
  dashboard talks to the API with the user's Supabase JWT.
- **API**: FastAPI on Render (`Dockerfile` at repo root), backed by Postgres (Supabase). Every
  table is org-scoped; `Store._assert_scoped` makes an un-scoped query a hard error by
  construction, not a convention.
- **Billing**: LemonSqueezy subscriptions gate the Pro-only features (custom policy rules, PDF
  export, scheduled tribunal runs, a hosted Anthropic key so you don't need your own).

```mermaid
flowchart TD
    UI[Next.js Dashboard\nVercel] -->|Supabase JWT| API[FastAPI\nRender]
    Agent[Your Agent] -->|API key: POST /events| API
    API --> DB[(Postgres\nSupabase)]
    API --> Tribunal[Tribunal\noffline detector or LangGraph + Claude]
    Tribunal --> DB
    API -->|GET /evidence| Pack[Evidence Pack\nHTML / PDF]
    API -->|anchorBatch root| Fuji[SessionAnchorRegistry\nAvalanche Fuji]
    Verify[Public /verify page] -->|read anchoredAt root| Fuji
```

---

## Local development

Backend:

```bash
git clone https://github.com/iWeslax83/teluvane.git
cd teluvane
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Needs a running Postgres. Quickest: a throwaway container.
docker run -d --name teluvane-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine

export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_JWT_SECRET=your-supabase-jwt-secret
export TELUVANE_SECRET_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
python -c "from teluvane.migrate import apply_migrations; print(apply_migrations())"
uvicorn teluvane.ingest:app --port 8900
```

Frontend (needs `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
in `frontend/.env.local`, see `frontend/.env.local.example`):

```bash
cd frontend
npm install
npm run dev
```

Full production deploy (Supabase + Render + Vercel) is documented in [DEPLOY.md](DEPLOY.md).

---

## MCP server

Any MCP-compatible agent (Claude Desktop, Claude Code, or anything else speaking the protocol)
can auto-log its actions to TELUVANE without you writing recorder calls into the agent. Point
an MCP client at `teluvane-mcp` (installed by `pip install -e .`) over stdio:

```json
{
  "mcpServers": {
    "teluvane": {
      "command": "teluvane-mcp",
      "env": { "TELUVANE_URL": "https://your-api.onrender.com", "TELUVANE_API_KEY": "tv_live_..." }
    }
  }
}
```

It exposes `record_llm_call`, `record_tool_call`, and `record_tool_result`. One MCP server
process is one recorded session by default, so a whole conversation lands in TELUVANE as a
single auditable session.

---

## SDKs

For agents that aren't MCP clients, record events directly against `/events`:

- **Python**: `teluvane.recorder.TeluvaneRecorder` (ships with `pip install -e .`, same package
  as the API and MCP server).
- **JS/TS**: `@teluvane/sdk` in [`sdk-js/`](sdk-js/), for Node and browser agents.

Both take an `agent_id`, `session_id`, API key, and record `llm_call` / `tool_call` /
`tool_result` steps. Pass `model` + input/output token counts on `llm_call` to get cost
tracking in `GET /stats/usage` (per-day tokens and USD, computed from a built-in pricing
table for known models; unknown models are recorded with no computed cost).

---

## Detection evals

`evals/` holds hand-written labeled sessions and a runner that scores each detector per rule
(`python -m evals.run_eval --detector offline`). The sessions and the detectors share authors,
so read `evals/README.md` before quoting a score, and send scenarios that prove us wrong
(`evals/CONTRIBUTING.md`).

## Tests

```bash
# backend: needs a Postgres reachable at TEST_DATABASE_URL (defaults to localhost:5432/teluvane_test)
pytest -v

# frontend
cd frontend && npm test
```

Coverage includes hash-chain integrity, tenant isolation, JWT/API-key auth, the offline and live
tribunal, billing plan gating, custom policy rule merging, the audit scheduler's due-check logic,
team invites, webhook delivery, session search/pagination, policy framework selection, and the
MCP server's tool calls.

---

## Roadmap

- A dedicated worker/cron service so scheduled tribunal runs don't depend on the API process
  staying warm

---

© 2026 iWeslax83. All rights reserved.
