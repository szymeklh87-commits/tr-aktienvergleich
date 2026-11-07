"""Protokollierung mit Schwärzung von Geheimnissen.

Werte der in ``SECRET_ENV_VARS`` genannten Umgebungsvariablen werden in jeder
Protokollzeile durch ``***`` ersetzt. Zusätzlich werden typische Schlüsselmuster in
URLs (``api_token=``, ``apikey=``) geschwärzt.

Ab 1.22 (Befund F19): Läuft ein Befehl in GitHub Actions, ist sein Protokoll öffentlich. Dann macht
:func:`set_public_mask` zusätzlich ISINs und bekannte Kürzel unkenntlich (dieselbe Regel wie im Kurzbericht).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Callable

SECRET_ENV_VARS = (
    "DATA_PASSPHRASE",
    "OPENFIGI_API_KEY",
    "EODHD_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "ANTHROPIC_API_KEY",  # ab 1.21.0: KI-Auswertung der Kaufkandidaten
)
_URL_SECRET = re.compile(r"((?:api_token|apikey|api_key|token|key)=)[^&\s\"']+", re.IGNORECASE)


_PUBLIC_MASK: Callable[[str], str] | None = None


def set_public_mask(mask: Callable[[str], str] | None) -> None:
    """Zusätzliche Schwärzung für öffentliche Protokolle (ab 1.22, F19); ``None`` schaltet sie ab."""
    global _PUBLIC_MASK
    _PUBLIC_MASK = mask


def redact(text: str) -> str:
    result = _URL_SECRET.sub(r"\1***", text)
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        if value and len(value) >= 4:
            result = result.replace(value, "***")
    if _PUBLIC_MASK is not None:
        try:
            result = _PUBLIC_MASK(result)
        except Exception:  # noqa: BLE001 - die Schwärzung darf das Protokoll nie verhindern
            result = "[Protokollzeile zurückgehalten]"
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
