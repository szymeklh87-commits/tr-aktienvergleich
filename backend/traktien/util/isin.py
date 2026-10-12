"""ISIN-Normalisierung und Prüfziffernkontrolle (ISO 6166).

Ein gültiges Format mit korrekter Prüfziffer bestätigt nur die formale Richtigkeit,
nicht die Identität des Wertpapiers. Die Identität wird getrennt über einen
Identitätsanbieter belegt.
"""

from __future__ import annotations

import re

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_WS = re.compile(r"\s+")


def normalize_isin(raw: str | None) -> str:
    """Entfernt Leerraum und wandelt in Großbuchstaben um."""
    return _WS.sub("", raw or "").upper()


def isin_check_digit(first_eleven: str) -> int:
    """Berechnet die Prüfziffer aus den ersten elf Zeichen.

    Buchstaben werden zu Zahlen 10..35 erweitert, danach gilt das Luhn-Verfahren,
    beginnend mit Verdopplung der rechten Ziffer der erweiterten Zeichenkette.
    """
    if len(first_eleven) != 11 or not first_eleven.isalnum():
        raise ValueError("ISIN-Rumpf muss aus genau elf alphanumerischen Zeichen bestehen")
    expanded = "".join(str(int(ch, 36)) for ch in first_eleven.upper())
    total = 0
    for position, ch in enumerate(reversed(expanded)):
        digit = int(ch)
        if position % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - total % 10) % 10


def is_valid_isin(isin: str) -> bool:
    """True, wenn Format und Prüfziffer stimmen."""
    if not ISIN_RE.match(isin or ""):
        return False
    return isin_check_digit(isin[:11]) == int(isin[11])


def isin_country(isin: str) -> str:
    """Länderpräfix der ISIN (Emittenten-/Registrierungsland, nicht zwingend Börsenland)."""
    return (isin or "")[:2].upper()


def make_isin(prefix_and_body: str) -> str:
    """Erzeugt eine ISIN mit korrekter Prüfziffer (nur für Tests und synthetische Daten)."""
    body = normalize_isin(prefix_and_body)
    return body + str(isin_check_digit(body))
