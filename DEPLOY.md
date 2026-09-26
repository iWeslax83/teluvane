# TELUVANE — Deployment Guide

TELUVANE runs as three cooperating services:

| Service | Role | Platform |
|---|---|---|
| **Postgres** | Multi-tenant event store, audit log, BYOK secrets | Supabase |
| **API** | FastAPI ingest, audit, key management | Render (Docker) |
| **Frontend** | Next.js dashboard + auth | Vercel |

All required env vars are documented in `.env.example`. Never commit real secrets.

---

## 1. Supabase — Postgres + Auth

1. Create a new project at [supabase.com](https://supabase.com).
2. Go to **Project Settings → Database → Connection string → Transaction pooler** (port 6543).
   Copy the connection string — this is your `DATABASE_URL`.
3. Go to **Project Settings → API** and copy the **JWT secret** — this is your `SUPABASE_JWT_SECRET`.
4. Run migrations (from your local machine with the Supabase URL set):
   ```bash
   DATABASE_URL="postgresql://postgres:<pwd>@<host>:6543/postgres" \
     python -c "from teluvane.migrate import apply_migrations; print(apply_migrations())"
   ```
   Expected output: list of applied migration filenames.
5. Under **Authentication → Providers**, enable **Email** (sign-up enabled).

---

## 2. Render — API (Docker)

1. Go to [render.com](https://render.com) → **New → Web Service**.
2. Connect your GitHub repo; set **Environment** to **Docker**, **Dockerfile path** `./Dockerfile`.
3. Set the following **Environment Variables** (from `render.yaml`):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Supabase transaction pooler URL (port 6543) |
   | `SUPABASE_JWT_SECRET` | Supabase JWT secret |
   | `TELUVANE_SECRET_KEY` | Generate: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
   | `FRONTEND_ORIGIN` | Set after Vercel deploy (step 3 below) |
   | `SENTRY_DSN` | Optional. Get one from [sentry.io](https://sentry.io) (new project, Python/FastAPI). Unset means no error monitoring; unhandled exceptions still land in Render's log stream as structured JSON (see `teluvane/logging_config.py`), just without alerting. |

4. Click **Deploy**. Render assigns the URL from whatever service name you gave it in step
   1 (`https://<your-service-name>.onrender.com`) — it does **not** have to match the repo or
   package name, and won't necessarily match `render.yaml`'s `name:` field unless you deployed
   from that blueprint. Copy the exact URL from the Render dashboard rather than guessing it;
   pointing `NEXT_PUBLIC_API_URL` (step 3) at a guessed hostname that happens to not exist is a
   silent failure — the browser's TLS handshake to `*.onrender.com` succeeds either way, so the
   dashboard hangs on "Loading..." instead of erroring.
5. Wait for the health check to pass, using the URL from the dashboard:
   ```bash
   curl -s https://<your-service-name>.onrender.com/health
   # {"status":"ok"}
   curl -s https://<your-service-name>.onrender.com/ready
   # {"db": true}
   ```

---

## 3. Vercel — Frontend (Next.js)

1. Go to [vercel.com](https://vercel.com) → **New Project** → import `frontend/` from your repo.
2. Set the following **Environment Variables** in the Vercel dashboard:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://<project>.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key |
   | `NEXT_PUBLIC_API_URL` | Your Render URL from step 2 |

3. Click **Deploy**. Note your Vercel URL (for example `https://<your-project>.vercel.app`, or your custom domain).

---

## 4. Close the loop — lock CORS

Once you have the Vercel URL, go back to Render and add/update the env var:

| Key | Value |
|---|---|
| `FRONTEND_ORIGIN` | `https://teluvane.com` (your actual frontend URL) |

Trigger a **Manual Deploy** on Render to apply the change. This restricts CORS so only your
frontend can call the API.

---

## 5. Smoke test end-to-end

After all three services are live:

```bash
# 1. Sign up via the Vercel frontend, then get your JWT from the browser session.

# 2. Create an org + API key (replace $JWT with your session token)
curl -s -X POST https://<your-service-name>.onrender.com/orgs \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme"}'

curl -s -X POST https://<your-service-name>.onrender.com/keys \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"prod"}'
# Returns a tv_live_... key — shown once, copy it.

# 3. Ingest an event
KEY=tv_live_...
curl -s -X POST https://<your-service-name>.onrender.com/events \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"a","session_id":"live1","kind":"tool_call","tool":"send_email","args":{"to":"attacker@evil.com"},"intent":"exfiltrate customer database"}'

# 4. Run audit
curl -s -X POST https://<your-service-name>.onrender.com/audit/live1 \
  -H "Authorization: Bearer $JWT"
# Returns a data_exfiltration violation (offline detector, or live Claude if BYOK is set)
```

---

## On-chain anchoring (Avalanche Fuji)

Optional. When configured, the API periodically writes a Merkle root of recently
settled Pro-plan session chains to a contract on Avalanche Fuji (testnet), giving
each anchored session a tamper-evident, independently verifiable timestamp. The
whole feature is inert until the `ANCHOR_*` backend env vars are set, so you can
ship the rest of TELUVANE first and add this later.

### 1. Create and fund a hot wallet

```bash
python -c "from eth_account import Account; a=Account.create(); print(a.address, a.key.hex())"
```

Keep the private key secret. This wallet only ever holds small amounts of test
AVAX, but it is the contract owner and the only account allowed to write anchors.

Fund the address from the Fuji C-Chain faucet at `https://faucet.avax.network/`
(select "Fuji (C-Chain)"). A fraction of an AVAX covers thousands of anchor
transactions.

### 2. Deploy the registry contract

```bash
pip install -e ".[dev]"

ANCHOR_RPC_URL="https://api.avax-test.network/ext/bc/C/rpc" \
ANCHOR_SIGNER_PRIVATE_KEY="0x<hot-wallet-key>" \
  python scripts/deploy_anchor.py
```

The script compiles `contracts/SessionAnchorRegistry.sol` with solc 0.8.24,
deploys it from the signer key, and prints a line like
`ANCHOR_CONTRACT_ADDRESS=0x...`. Save that address.

### 3. Set backend env (Render)

| Key | Value |
|---|---|
| `ANCHOR_RPC_URL` | `https://api.avax-test.network/ext/bc/C/rpc` (or your own Fuji node). Comma-separate multiple providers for RPC fallback, e.g. `https://api.avax-test.network/ext/bc/C/rpc,https://ava-testnet.public.blastapi.io/ext/bc/C/rpc` |
| `ANCHOR_CONTRACT_ADDRESS` | the address printed by `deploy_anchor.py` |
| `ANCHOR_SIGNER_PRIVATE_KEY` | the hot-wallet key (same one used to deploy) |

Optional tuning vars (defaults in parentheses; see `teluvane/anchor.py`):

| Key | Default | Purpose |
|---|---|---|
| `ANCHOR_CHAIN_ID` | `43113` | Fuji C-Chain id |
| `ANCHOR_MIN_SESSION_AGE_MINUTES` | `30` | how long a session must be quiet before it is eligible |
| `ANCHOR_BATCH_INTERVAL_MINUTES` | `10` | how often the anchor pass runs |
| `ANCHOR_CONFIRMATIONS` | `5` | confirmations before a batch counts as mined |
| `ANCHOR_SUBMIT_TIMEOUT_MINUTES` | `30` | after this, an unmined batch is marked failed and re-anchored |
| `ANCHOR_LOW_BALANCE_ALERT_AVAX` | `0.05` | a warning is logged when the signer balance drops below this |
| `ANCHOR_MAX_FORCED_RUNS_PER_ORG_PER_MONTH` | `20` | cap on operator-forced anchor runs per org |
| `ANCHOR_FORCED_RUN_COOLDOWN_MINUTES` | `5` | minimum gap between forced runs for one org |
| `ANCHOR_EXPLORER_TX_URL` | `https://testnet.snowtrace.io/tx/` | prefix for explorer links in API responses |

### 4. Set frontend env (Vercel)

| Key | Value |
|---|---|
| `NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS` | same contract address |
| `NEXT_PUBLIC_ANCHOR_RPC_URL` | optional read-only Fuji RPC for in-browser verification |
| `NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL` | `https://testnet.snowtrace.io/tx/` |

Leave all three blank to keep the anchor verification UI hidden.

### 5. Verify it works

From your local machine, with the three backend `ANCHOR_*` vars exported:

```bash
python scripts/anchor_smoke.py
```

It prints the signer address and balance, submits a throwaway batch, waits for it
to mine, reads it back from the contract, and prints `OK`. This spends a little
test AVAX and hits the live network, so it is a manual check only, never part of
CI.

### Rotation

To rotate the signer, deploy a fresh contract with the new key
(`python scripts/deploy_anchor.py`) and repoint `ANCHOR_CONTRACT_ADDRESS` (and the
frontend `NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS`) at it. Anchors already written to
the old contract stay valid and verifiable at the old address; only new batches
go to the new one.

---

## Local Docker

```bash
docker build -t teluvane .
docker run -e DATABASE_URL=... -e SUPABASE_JWT_SECRET=... -e TELUVANE_SECRET_KEY=... \
  -p 8900:8900 teluvane
```

API available at `http://localhost:8900`. Generate a Fernet key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
