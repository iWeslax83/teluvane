import os

os.environ["FRONTEND_ORIGIN"] = "https://teluvane.vercel.app"
os.environ.setdefault(
    "DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/teluvane_test")
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("TELUVANE_SECRET_KEY", "BDUpLFAo9s1dqKy3BZFUcEvdGA7sS0rgdpUEe3Yai8I=")


def test_cors_allows_configured_origin_only():
    import importlib

    import teluvane.ingest as ing

    importlib.reload(ing)
    from fastapi.testclient import TestClient

    c = TestClient(ing.app)
    good = c.get("/health", headers={"Origin": "https://teluvane.vercel.app"})
    assert good.headers.get("access-control-allow-origin") == "https://teluvane.vercel.app"
