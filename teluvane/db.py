# teluvane/teluvane/db.py
import os

from psycopg_pool import ConnectionPool

# Supabase free-tier Postgres has a low direct-connection ceiling. We connect through the
# transaction pooler (pgBouncer, port 6543) and keep our own pool small. The tribunal's
# LangGraph fan-out does LLM work, not DB work — DB access is one read up front and one write
# after consolidation — so pool size is deliberately decoupled from fan-out width.
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 5  # hard cap; total app connections stay well under the tier limit
POOL_TIMEOUT = 10  # seconds to wait for a free connection before erroring

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = ConnectionPool(
            conninfo=dsn,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            timeout=POOL_TIMEOUT,
            check=ConnectionPool.check_connection,  # pre-ping: drop dead conns
            kwargs={"autocommit": False},
        )
    return _pool


def reset_pool() -> None:
    """Test helper: close and forget the pool so a new DATABASE_URL takes effect."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
