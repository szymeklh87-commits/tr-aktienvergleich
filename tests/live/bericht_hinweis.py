"""Datenquellen-Bericht als GitHub-Hinweise (Annotations) ausgeben.

Aufruf im Workflow „Datenquellen prüfen“ nach den Live-Tests:

    python tests/live/bericht_hinweis.py datenquellen-bericht.json

Je Quelle erscheint ein Hinweis mit den wichtigsten Zahlen (Größe der TR-Liste, gefundene
Notierungen, gelieferte Tageskurse). Der Bericht enthält keine Schlüssel – nur Adressen, Zahlen
und Börsensymbole.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _title(text: str) -> str:
    return _escape(text).replace(":", "%3A").replace(",", "%2C")


def lines(report: dict) -> list[str]:
    out: list[str] = []
    tr = report.get("tr_universum")
    if tr:
        text = (
            f"{tr.get('isins')} ISINs im Aktienabschnitt (gefunden: {'ja' if tr.get('aktienabschnitt_gefunden') else 'nein'}), "
            f"ungültige ISINs {tr.get('ungueltige_isins')}, doppelte {tr.get('doppelte')}, Fortsetzungszeilen {tr.get('fortsetzungszeilen')}\n"
            f"PDF {tr.get('bytes')} Byte, Last-Modified {tr.get('last_modified') or 'nicht gemeldet'}\n"
            f"Abschnitte: {', '.join(tr.get('abschnitte') or [])}\n"
            f"Bekannte ISINs gefunden: {', '.join(tr.get('bekannte_isins_gefunden') or []) or 'keine'}"
        )
        unparsed = tr.get("unerkannte_zeilen_beispiele") or []
        if unparsed:
            text += "\nUnerkannte Zeilen (Beispiele): " + " | ".join(str(u) for u in unparsed[:5])
        out.append(f"::notice title={_title('TR-Instrumentenliste')}::{_escape(text)}")
    figi = report.get("openfigi")
    if figi:
        text = "\n".join(f"{isin}: {len(items)} unterstützte Notierungen, z. B. {', '.join(items[:4])}" for isin, items in figi.items())
        out.append(f"::notice title=OpenFIGI::{_escape(text)}")
    yahoo = report.get("yahoo")
    if yahoo:
        text = (
            f"AAPL: {yahoo.get('aapl_tageskurse')} Tageskurse, letzter Tag {yahoo.get('letzter_tag')}\n"
            f"ISIN-Suche US0378331005: {', '.join(yahoo.get('suche_isin') or []) or 'kein Treffer'}"
        )
        out.append(f"::notice title={_title('Yahoo Finance')}::{_escape(text)}")
    cutoff = report.get("yahoo_stichtag")
    if cutoff:
        rows = [f"Stichtag {cutoff.get('stichtag')} (geprüft {cutoff.get('jetzt_utc')})"]
        for symbol, entry in (cutoff.get("werte") or {}).items():
            if entry.get("fehler"):
                rows.append(f"{symbol} ({entry.get('kalender')}): Fehler {entry['fehler']}")
                continue
            if not entry.get("sitzung_am_stichtag"):
                state = "kein Handelstag"
            else:
                state = "vorhanden" if entry.get("stichtag_vorhanden") else "FEHLT"
            bars = ", ".join(
                f"{bar.get('tag')} {str(bar.get('zeit_utc') or '')[11:16]}Z{'' if bar.get('abgeschlossen') else ' (laufend)'}"
                for bar in entry.get("letzte_kerzen") or []
            )
            rows.append(f"{symbol} ({entry.get('kalender')}, {entry.get('zeitzone')}): {state} – {bars}")
        out.append(f"::notice title={_title('Yahoo – Stichtagskurs je Börse')}::{_escape(chr(10).join(rows))}")
    eodhd = report.get("eodhd")
    if eodhd:
        bars = eodhd.get("aapl_tageskurse")
        out.append(f"::notice title=EODHD::AAPL.US: {bars} Tageskurse")
    else:
        out.append("::notice title=EODHD::Nicht geprüft (kein EODHD_API_KEY hinterlegt)")
    return out


def main(path: str) -> int:
    file = Path(path)
    if not file.exists():
        print("::warning::Kein Datenquellen-Bericht – die Live-Tests sind vor dem ersten Abruf abgebrochen")
        return 0
    print("\n".join(lines(json.loads(file.read_text(encoding="utf-8")))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "datenquellen-bericht.json"))
