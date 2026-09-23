from teluvane.db import get_pool
from teluvane.migrate import apply_migrations


def test_identity_tables_exist():
    apply_migrations()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('public.orgs'), to_regclass('public.org_members'), "
            "to_regclass('public.api_keys')"
        )
        orgs, members, keys = cur.fetchone()
    assert orgs == "orgs" and members == "org_members" and keys == "api_keys"
