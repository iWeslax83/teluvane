import os

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/teluvane_test"
    ),
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("TELUVANE_SECRET_KEY", "BDUpLFAo9s1dqKy3BZFUcEvdGA7sS0rgdpUEe3Yai8I=")
import pytest

from teluvane.migrate import apply_migrations
from teluvane.store import Store


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    apply_migrations()


@pytest.fixture
def store():
    s = Store()
    with s.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, org_members, orgs, "
            "anchor_batches, session_anchors, session_anchor_public RESTART IDENTITY CASCADE"
        )
        conn.commit()
    return s


import time

import jwt


@pytest.fixture
def make_jwt():
    def _make(user_id: str, *, expired: bool = False, secret: str = None):
        now = int(time.time())
        payload = {
            "sub": user_id,
            "aud": "authenticated",
            "iat": now,
            "exp": now - 10 if expired else now + 3600,
        }
        return jwt.encode(payload, secret or os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")

    return _make
