import asyncio
import logging
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from config import API_TOKEN, API_KEY, LOG_FILENAME


class SecretFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        for value in (API_TOKEN, API_KEY):
            if value:
                message = message.replace(value, "[REDACTED]")
        record.msg = re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{20,}", "[REDACTED]", message)
        record.args = ()
        return True


class SecretFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        for secret in (API_TOKEN, API_KEY):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{20,}", "[REDACTED]", text)


root = logging.getLogger()
if not any(getattr(handler, "_fox_handler", False) for handler in root.handlers):
    Path(LOG_FILENAME).parent.mkdir(parents=True, exist_ok=True)
    formatter = SecretFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in (
        TimedRotatingFileHandler(
            LOG_FILENAME, when="midnight", backupCount=7, encoding="utf-8"
        ),
        logging.StreamHandler(),
    ):
        handler._fox_handler = True
        handler.setFormatter(formatter)
        handler.addFilter(SecretFilter())
        root.addHandler(handler)
    root.setLevel(logging.INFO)
