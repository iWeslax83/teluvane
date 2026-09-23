# teluvane/teluvane/logging_config.py
import json
import logging

from .logging_filter import _redact, install_redaction


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if record.exc_info:
            payload["traceback"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JsonFormatter())
        root.addHandler(h)
    install_redaction()  # redaction runs AFTER handlers exist so they inherit the filter
