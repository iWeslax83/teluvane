# teluvane/teluvane/migrate.py
import pathlib
from .db import get_pool

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

_LOCK_KEY = 0x7454_4C56   # "tTLV"


def apply_migrations(pool=None) -> list[str]:
    """Apply every *.sql in migrations/ in lexical order, exactly once. Returns names applied."""
    pool = pool or get_pool()
    newly_applied: list[str] = []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Session-level lock held for the whole run: if two instances boot at once,
            # the second waits here and then finds every migration already applied,
            # instead of racing on the schema_migrations INSERT.
            cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            _apply(conn, newly_applied)
        except Exception:
            conn.rollback()   # clear the aborted-txn state so the unlock below can run
            raise
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
    return newly_applied


def _apply(conn, newly_applied: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        # Deny-all RLS, matching every other public table (migrations/*.sql).
        # Idempotent: re-enabling is a no-op. The service-role pool bypasses RLS.
        cur.execute("ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY")
        cur.execute("SELECT name FROM schema_migrations")
        applied = {r[0] for r in cur.fetchall()}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        with conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations(name) VALUES(%s)", (path.name,))
        newly_applied.append(path.name)
    conn.commit()
