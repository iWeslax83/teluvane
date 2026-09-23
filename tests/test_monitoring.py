import pytest
import sentry_sdk

from teluvane.monitoring import configure_sentry


@pytest.fixture
def _restore_sentry_client():
    original = sentry_sdk.get_client()
    yield
    sentry_sdk.get_global_scope().set_client(original)


def test_configure_sentry_is_noop_without_dsn(monkeypatch, _restore_sentry_client):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    configure_sentry()
    assert sentry_sdk.is_initialized() is False


def test_configure_sentry_initializes_with_dsn(monkeypatch, _restore_sentry_client):
    monkeypatch.setenv("SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    configure_sentry()
    assert sentry_sdk.is_initialized() is True
