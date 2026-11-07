"""Eingabe aus der App für einen auf GitHub gestarteten Lauf (ab 1.22).

Die App enthält keinen GitHub-Zugang (kein Token, auch nicht verschlüsselt): Sie verschlüsselt eine Anfrage mit dem
Datenschlüssel und kopiert sie als **eine Zeile** ``<Kennung>.<verschlüsselter Text>`` in die Zwischenablage. Gestartet wird
auf GitHub mit der eigenen Anmeldung („Run workflow“, Zeile einfügen). Öffentlich sichtbar sind nur die Zufallskennung und
Chiffretext; der Lauf liest die Zeile nur aus einer Umgebungsvariablen, nie als Befehl.

Beim Einfügen auf dem Handy entstehen leicht Leerzeichen oder Zeilenumbrüche – sie werden entfernt. Alles andere, was nicht
genau dieses Format hat, wird mit einem Code abgelehnt (ohne den Inhalt zu protokollieren).
"""

from __future__ import annotations

import re

KENNUNG_RE = re.compile(r"^k[0-9a-z]{6,8}-[0-9a-z]{16}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
# GitHub erlaubt für alle Eingaben eines Laufs zusammen höchstens 65.535 Zeichen
MAX_LAENGE = 65_000


class EingabeFehler(ValueError):
    """Eingabe unbrauchbar; ``code`` ist für Protokoll und App, nie der Inhalt."""

    def __init__(self, code: str, text: str) -> None:
        super().__init__(text)
        self.code = code
        self.text = text


def eingabe_zeile(kennung: str, verschluesselt: str) -> str:
    """Zeile, wie die App sie kopiert (für Tests und Messungen)."""
    if not KENNUNG_RE.match(kennung):
        raise EingabeFehler("kennung_ungueltig", "Kennung ungültig")
    return f"{kennung}.{verschluesselt}"


def split_eingabe(text: str | None, max_laenge: int = MAX_LAENGE) -> tuple[str, str]:
    """``<Kennung>.<Base64>`` → (Kennung, Base64). Leerzeichen und Zeilenumbrüche aus dem Einfügen werden entfernt."""
    compact = "".join((text or "").split())
    if not compact:
        raise EingabeFehler("eingabe_leer", "Keine Eingabe – auf GitHub die aus der App kopierte Zeile einfügen")
    if len(compact) > max_laenge:
        raise EingabeFehler("eingabe_zu_lang", "Eingabe zu lang")
    kennung, sep, rest = compact.partition(".")
    if not sep or not KENNUNG_RE.match(kennung):
        raise EingabeFehler("kennung_ungueltig", "Keine gültige Kennung am Anfang – die ganze Zeile aus der App einfügen")
    if not rest or not _BASE64_RE.match(rest) or len(rest) % 4:
        raise EingabeFehler("eingabe_unvollstaendig", "Eingabe unvollständig – die ganze Zeile aus der App einfügen")
    return kennung, rest
