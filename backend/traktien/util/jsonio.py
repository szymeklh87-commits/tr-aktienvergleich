"""Strenges JSON ohne NaN/Infinity und atomare Dateischreibvorgänge."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


def _clean(value: Any) -> Any:
    """Wandelt NumPy-Typen um und ersetzt nicht endliche Zahlen durch None.

    Fehlende Werte sind im veröffentlichten JSON immer ``null`` – niemals 0.
    """
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_clean(v) for v in value.tolist()]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def dumps(value: Any, *, pretty: bool = False) -> str:
    cleaned = _clean(value)
    if pretty:
        return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=False)
    return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def canonical_bytes(value: Any) -> bytes:
    """Deterministische Darstellung für Hashes."""
    cleaned = _clean(value)
    return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_bytes(path: Path | str, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path | str, value: Any, *, pretty: bool = True) -> None:
    atomic_write_bytes(path, (dumps(value, pretty=pretty) + "\n").encode("utf-8"))


def read_json(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
