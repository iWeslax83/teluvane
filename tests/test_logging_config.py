import io, json, logging
from teluvane.logging_config import configure_logging, JsonFormatter
from teluvane.logging_filter import SecretRedactionFilter

def test_configure_logging_installs_redaction():
    configure_logging()
    root = logging.getLogger()
    has_filter = any(isinstance(f, SecretRedactionFilter) for f in root.filters) or \
                 any(any(isinstance(f, SecretRedactionFilter) for f in h.filters) for h in root.handlers)
    assert has_filter

def test_json_formatter_includes_traceback_on_exception():
    formatter = JsonFormatter()
    record = None
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="teluvane.test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="something failed", args=(), exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert payload["msg"] == "something failed"
    assert "ValueError: boom" in payload["traceback"]

def test_json_formatter_omits_traceback_key_when_no_exception():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="teluvane.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="all good", args=(), exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert "traceback" not in payload
