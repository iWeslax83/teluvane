# teluvane/teluvane/logging_filter.py
import logging
import re

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    re.compile(r"tv_live_[A-Za-z0-9_\-]+"),
]


def _redact(value):
    if isinstance(value, str):
        for p in _PATTERNS:
            value = p.sub("[REDACTED]", value)
    return value


class SecretRedactionFilter(logging.Filter):
    """Strip Anthropic keys and tv_live_ API keys from every log record, including args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(_redact(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: _redact(v) for k, v in record.args.items()}
            else:
                record.args = _redact(record.args)
        return True


def install_redaction() -> None:
    """Attach the filter to the root logger so all handlers inherit it."""
    f = SecretRedactionFilter()
    root = logging.getLogger()
    if not any(isinstance(x, SecretRedactionFilter) for x in root.filters):
        root.addFilter(f)
    for h in root.handlers:
        if not any(isinstance(x, SecretRedactionFilter) for x in h.filters):
            h.addFilter(f)
