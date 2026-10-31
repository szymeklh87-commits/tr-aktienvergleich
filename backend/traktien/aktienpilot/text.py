"""Zahlen in deutschen Texten des Spielgeld-Robos (Journal, Begründungen): Komma als Dezimal-, Punkt als Tausendertrennzeichen.

Nur für lesbare Texte – gespeicherte Werte bleiben Zahlen (JSON), die App formatiert sie selbst.
"""

from __future__ import annotations

import math


def zahl(x: float | None, nd: int = 2) -> str:
    """``zahl(1234.5) == "1.234,50"``; fehlende oder ungültige Werte als „–“."""
    if x is None:
        return "–"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "–"
    if not math.isfinite(v):
        return "–"
    return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kurs(x: float | None) -> str:
    """Kurs mit zwei Nachkommastellen, unter 1 mit vier (Pennystocks, Pence)."""
    if x is None:
        return "–"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "–"
    return zahl(v, 2 if math.isfinite(v) and abs(v) >= 1 else 4)


def prozent(x: float | None, nd: int = 1) -> str:
    """Wert in Prozent (bereits ×100) mit Komma: ``prozent(12.34) == "12,3 %"``."""
    return f"{zahl(x, nd)} %" if x is not None else "–"
