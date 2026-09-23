import json
import logging

from teluvane.logging_config import JsonFormatter, configure_logging
from teluvane.logging_filter import SecretRedactionFilter


def test_configure_logging_installs_redaction():
    configure_logging()
    root = logging.getLogger()
    has_filter = any(isinstance(f, SecretRedactionFilter) for f in root.filters) or any(
        any(isinstance(f, SecretRedactionFilter) for f in h.filters) for h in root.handlers
    )
    assert has_filter


def test_json_formatter_includes_traceback_on_exception():
    formatter = JsonFormatter()
    record = None
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="teluvane.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="something failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["msg"] == "something failed"
    assert "ValueError: boom" in payload["traceback"]


def test_json_formatter_omits_traceback_key_when_no_exception():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="teluvane.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="all good",
        args=(),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert "traceback" not in payload


def test_json_formatter_redacts_secrets_from_traceback():
    formatter = JsonFormatter()
    record = None
    try:
        raise ValueError("API key is sk-ant-abc123def456")
    except ValueError:
        record = logging.LogRecord(
            name="teluvane.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed with secret",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert "[REDACTED]" in payload["traceback"]
    assert "sk-ant-abc123def456" not in payload["traceback"]
