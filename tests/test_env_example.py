import pathlib

TEXT = (pathlib.Path(__file__).parent.parent / ".env.example").read_text(encoding="utf-8")


def test_env_example_uses_the_current_secret_key_name():
    assert "TELUVANE_SECRET_KEY=" in TEXT
    assert "BLACKBOX" not in TEXT.upper()


def test_env_example_documents_every_variable_the_api_requires():
    for name in ("DATABASE_URL", "SUPABASE_JWT_SECRET", "TELUVANE_SECRET_KEY", "FRONTEND_ORIGIN"):
        assert f"{name}=" in TEXT, name
