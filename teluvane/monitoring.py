# teluvane/teluvane/monitoring.py
"""Optional error-monitoring wiring. Inert unless SENTRY_DSN is set, same pattern
as anchor.chain_config(): missing config means the feature does nothing rather
than raising. sentry_sdk.capture_exception() is itself always safe to call even
when sentry_sdk.init() was never run, so call sites don't need to check first."""
import os

import sentry_sdk


def configure_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        # Off by default: performance tracing on every request is not worth the
        # overhead/cost for a service this size unless someone opts in.
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
    )
