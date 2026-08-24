# TELUVANE
Flight recorder + compliance tribunal for AI agents.

## The problem
Companies are putting AI agents into production workflows (support, ops, coding, finance) with
no audit trail. When an agent takes a bad action, there is no tamper-proof record of what it did
or why, and no automated way to check whether it violated policy (EU AI Act, internal rules,
customer contracts). Logs live in application databases where anyone with write access can
edit or delete them after the fact.

## What TELUVANE does
1. **Records** every LLM call, tool call, and tool result an agent makes, hash-chained
   (SHA-256) per session. Editing or deleting a row breaks the chain visibly, so tampering is
   detectable, not just logged.
2. **Audits** the session against a policy pack (EU AI Act ships by default, custom rules on
   paid plans) and produces cited verdicts, either from a deterministic offline detector or a
   live LangGraph + Claude tribunal.
3. **Exports evidence**: a self-contained report (HTML on every plan, PDF on Pro) with the full
   event log, verdict table, chain-integrity status, and framework citations, something you can
   hand to a regulator, auditor, or customer's security team.

## Why now
The EU AI Act's obligations are phasing in through 2026-2027 and any company shipping an AI
agent into a regulated workflow needs to show what it did and prove the record wasn't altered
after the fact. There is no established default for this yet.

## Status: this is real, not a mockup
- Multi-tenant product: Supabase-authenticated orgs, per-org API keys, LemonSqueezy billing.
- Postgres-backed store with org-scoping enforced at the code level, not by convention
  (`Store._assert_scoped` makes an unscoped query a hard error).
- 117 automated tests passing (backend + evidence export).
- Live at [blackbox-agent-accountability.vercel.app](https://blackbox-agent-accountability.vercel.app),
  API on Render, frontend on Vercel.
- MCP server for zero-code integration with Claude Desktop, Claude Code, or any MCP client.

## Traction
_[fill in: number of orgs signed up, sessions recorded, audits run, any paid conversions.
Pull from the production Supabase instance, not the local dev DB, before sharing this doc.]_

## Business model
- Pro tier (LemonSqueezy, $19.99/mo): built-in EU AI Act, ISO 42001, NIST AI RMF, and SOC 2
  policy packs, hosted dashboard, scheduled tribunal runs, PDF + HTML evidence export, custom
  policy rules.
- Enterprise tier (custom pricing): unlimited agents, SSO/SAML, on-prem deployment, custom
  policy mapping.
- See `docs/business-model/` for the full canvas.

## What we're raising / looking for
_[fill in: raise amount and use of funds for investors; ideal pilot customer profile and what
you want from a design partner, e.g. free Pro access in exchange for a case study]_

## Contact
_[fill in: name, email, calendar link]_
