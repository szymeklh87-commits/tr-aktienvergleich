"""Bericht der Live-Prüfung der App als GitHub-Hinweise (Annotations) ausgeben.

Aufruf im Workflow „App mit echten Daten prüfen“ nach ``tests/live/test_app_live.py``:

    python tests/live/app_bericht_hinweis.py app-bericht.json

Der Bericht enthält nur Version, Datum des Kursstands, Zählungen, Zeiten und Fehlermeldungen –
keine Kurse, Namen oder Ranglisteninhalte und keine Passphrase.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _title(text: str) -> str:
    return _escape(text).replace(":", "%3A").replace(",", "%2C")


def _de(seconds) -> str:
    return "–" if seconds is None else f"{seconds:.1f}".replace(".", ",") + " s"


def lines(report: dict) -> list[str]:
    out: list[str] = []
    stand = report.get("datenstand") or {}
    views = report.get("ansichten") or {}
    ok_views = [name for name, entry in views.items() if not entry.get("probleme")]
    summary = [
        f"Adresse: {report.get('adresse')}",
        f"App-Version: {report.get('version') or 'nicht lesbar'}",
        f"Datenstand: {stand.get('neuester') or '–'} (Kursstand {stand.get('kursstand') or '–'}, "
        f"{'Teilstand' if report.get('teilstand') else 'vollständig' if stand.get('neuester') and stand.get('neuester') == stand.get('neuester_vollstaendig') else 'ohne vollständigen Stand'}), "
        f"letzter Lauf: {stand.get('letzter_lauf') or '–'}, aufbewahrte Stände: {stand.get('aufbewahrt', '–')}",
        f"Verschlüsselt: {'ja' if report.get('verschluesselt') else 'nein'}; entsperrt und geladen in {_de(report.get('entsperren_und_laden_s'))}; "
        f"erneut geöffnet in {_de(report.get('erneut_oeffnen_s'))} {'ohne' if report.get('erneut_ohne_passphrase') else 'MIT'} erneute Passphrase; "
        f"Service Worker {'aktiv' if report.get('service_worker_aktiv') else 'nicht aktiv'}",
        f"Kopf der Startseite: {report.get('kopf') or '–'}",
        f"Ansichten ohne Fehler: {len(ok_views)} von {len(views)}",
    ]
    for name, entry in views.items():
        state = "ok" if not entry.get("probleme") else "FEHLER: " + "; ".join(entry["probleme"])
        count = f", {entry['elemente']} Elemente" if entry.get("elemente") is not None else ""
        summary.append(f"  {name} ({entry.get('route')}): {state}{count}, {_de(entry.get('sekunden'))}")
    detail = report.get("einzelansicht")
    if detail:
        summary.append(
            f"Einzelansicht der ersten Aktie (30 Tage): {detail.get('kennzahlen_zeilen')} Kennzahlzeilen, Kursgrafik {'ja' if detail.get('kursgrafik') else 'nein'}, "
            f"zweiter Börsenplatz {'ja' if detail.get('zweiter_boersenplatz') else 'nein'}, {_de(detail.get('sekunden'))}"
        )
    errors = report.get("fehler") or []
    console = report.get("konsolenfehler") or []
    level = "error" if errors or console else "notice"
    title = "App mit echten Daten: " + ("Fehler gefunden" if errors or console else "alles in Ordnung")
    out.append(f"::{level} title={_title(title)}::{_escape(chr(10).join(summary))}")
    if errors:
        out.append(f"::error title={_title('Gefundene Fehler')}::{_escape(chr(10).join(errors))}")
    if console:
        out.append(f"::error title={_title('Browser-Konsole')}::{_escape(chr(10).join(console[:20]))}")
    return out


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else "app-bericht.json")
    if not path.exists():
        print(f"::error title={_title('App-Prüfung')}::Kein Bericht ({path}) – die Prüfung ist vorher abgebrochen; siehe Protokoll")
        return 0
    for line in lines(json.loads(path.read_text(encoding="utf-8"))):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
