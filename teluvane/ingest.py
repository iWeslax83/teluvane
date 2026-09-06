# teluvane/teluvane/ingest.py
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .appstate import store, limiter, FRAMEWORK_PACKS
from .logging_config import configure_logging
from .monitoring import configure_sentry
from .scheduler import run_due_schedules, run_anchor_cycle, TICK_INTERVAL_SECONDS
from .routes import sessions, anchor, policy, evidence, orgs, billing

configure_logging()
configure_sentry()

# ---- automated tribunal runs (Pro plan) ------------------------------------------------------
# One in-process background thread, ticking every minute, re-audits any org whose schedule is
# due (see scheduler.py for the tradeoffs of running this in-process rather than as a separate
# worker/cron service). Not started under pytest's plain TestClient(app) since that never fires
# the lifespan; only a `with TestClient(app) as c:` context manager would.
_scheduler_stop = threading.Event()

def _scheduler_loop() -> None:
    while not _scheduler_stop.wait(TICK_INTERVAL_SECONDS):
        try:
            run_due_schedules(store, FRAMEWORK_PACKS, hosted_api_key=os.environ.get("TELUVANE_HOSTED_ANTHROPIC_KEY"))
        except Exception:
            logging.exception("scheduled tribunal tick failed")
        try:
            run_anchor_cycle()
        except Exception:
            logging.exception("anchor tick failed")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    yield
    _scheduler_stop.set()

app = FastAPI(title="TELUVANE", lifespan=_lifespan)
_origins = [o for o in os.environ.get("FRONTEND_ORIGIN", "").split(",") if o]
# With no FRONTEND_ORIGIN configured we fall back to "*", but Starlette turns
# allow_origins=["*"] + allow_credentials=True into "reflect any Origin and allow
# credentials", i.e. every site on the internet. Only send credentialed CORS when
# the allowlist is explicit.
_allow_credentials = bool(_origins)
app.add_middleware(CORSMiddleware, allow_origins=_origins or ["*"],
                   allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=_allow_credentials)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logging.exception("unhandled exception [request_id=%s] %s %s", request_id, request.method, request.url.path)
    # This handler catching the exception stops it from ever reaching Sentry's ASGI
    # middleware, so it has to be reported explicitly. No-op if SENTRY_DSN unset.
    sentry_sdk.capture_exception(exc)
    return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": request_id})

# ---- health / readiness (no auth) ----------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/ready")
def ready():
    try:
        with store.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"db": True}
    except Exception:
        logging.exception("db readiness check failed")
        from fastapi import Response
        return Response(content='{"db": false}', media_type="application/json", status_code=503)

# Route order matters within each router (literal paths before {session_id} path params),
# preserved inside teluvane/routes/*.py; mount order across routers does not matter since
# none of their path templates collide.
app.include_router(sessions.router)
app.include_router(anchor.router)
app.include_router(policy.router)
app.include_router(evidence.router)
app.include_router(orgs.router)
app.include_router(billing.router)
