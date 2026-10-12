"""Protokollierung mit Schwärzung von Geheimnissen.

Werte der in ``SECRET_ENV_VARS`` genannten Umgebungsvariablen werden in jeder
Protokollzeile durch ``***`` ersetzt. Zusätzlich werden typische Schlüsselmuster in
URLs (``api_token=``, ``apikey=``) geschwärzt.
"""

from __future__ import annotations

import logging
import os
import re
import sys

SECRET_ENV_VARS = (
    "DATA_PASSPHRASE",
    "OPENFIGI_API_KEY",
    "EODHD_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
_URL_SECRET = re.compile(r"((?:api_token|apikey|api_key|token|key)=)[^&\s\"']+", re.IGNORECASE)


def redact(text: str) -> str:
    result = _URL_SECRET.sub(r"\1***", text)
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        if value and len(value) >= 4:
            result = result.replace(value, "***")
    return result


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
