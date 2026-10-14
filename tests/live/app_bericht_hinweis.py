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
    intraday = stand.get("zwischenstand")
    if intraday:
        official = stand.get("offiziell")
        stand_text = (
            f"Zwischenstand {intraday.get('snapshot_id')} (Stichtag {intraday.get('stichtag') or '–'}, {intraday.get('aktien_mit_kurs', '–')} Aktien mit Kurs von heute, "
            f"Kurse bis {intraday.get('kurse_bis_utc') or '–'}); offizieller Stand {official or '–'} (Kursstand {stand.get('kursstand') or '–'}, "
            f"{'vollständig' if official and official == stand.get('neuester_vollstaendig') else 'Teilstand'})"
        )
    else:
        stand_text = (
            f"{stand.get('neuester') or '–'} (Kursstand {stand.get('kursstand') or '–'}, "
            f"{'Teilstand' if report.get('teilstand') else 'vollständig' if stand.get('neuester') and stand.get('neuester') == stand.get('neuester_vollstaendig') else 'ohne vollständigen Stand'})"
        )
    summary = [
        f"Adresse: {report.get('adresse')}",
        f"App-Version: {report.get('version') or 'nicht lesbar'}",
        f"Datenstand: {stand_text}, letzter Lauf: {stand.get('letzter_lauf') or '–'}, aufbewahrte Stände: {stand.get('aufbewahrt', '–')}",
        f"Verschlüsselt: {'ja' if report.get('verschluesselt') else 'nein'}; geöffnet in {_de(report.get('oeffnen_s'))}, "
        f"entsperrt bis zur fertigen Startseite in {_de(report.get('entsperren_s'))} (zusammen {_de(report.get('entsperren_und_laden_s'))}); "
        f"erneut geöffnet in {_de(report.get('erneut_oeffnen_s'))} {'ohne' if report.get('erneut_ohne_passphrase') else 'MIT'} erneute Passphrase; "
        f"Service Worker {'aktiv' if report.get('service_worker_aktiv') else 'nicht aktiv'} (Zeiten ab 1.14 bis zur fertigen Ansicht, ohne Ruhezeit der Prüfung)",
        f"Kopf der Startseite: {report.get('kopf') or '–'}",
        f"Ansichten ohne Fehler: {len(ok_views)} von {len(views)}",
    ]
    for name, entry in views.items():
        state = "ok" if not entry.get("probleme") else "FEHLER: " + "; ".join(entry["probleme"])
        n = entry.get("elemente")
        count = "" if n is None else f", {n} Element{'' if n == 1 else 'e'}"
        if entry.get("hinweis_zwischenstand"):
            count += " (Hinweis „im Zwischenstand nicht gerechnet“)"
        summary.append(f"  {name} ({entry.get('route')}): {state}{count}, {_de(entry.get('sekunden'))}")
    detail = report.get("einzelansicht")
    if detail:
        summary.append(
            f"Einzelansicht der ersten Aktie (30 Tage): {detail.get('kennzahlen_zeilen')} Kennzahlzeilen, Kursgrafik {'ja' if detail.get('kursgrafik') else 'nein'}, "
            f"zweiter Börsenplatz {'ja' if detail.get('zweiter_boersenplatz') else 'nein'}, nach dem Antippen fertig in {_de(detail.get('bereit_s'))} "
            f"(ganzer Schritt {_de(detail.get('sekunden'))})"
        )
    bericht = report.get("bericht")
    if bericht:
        summary.append(
            f"Bericht 1–30: {bericht.get('tabellen')} Tabellen ({bericht.get('zusammengefasste_zeilen')} zusammengefasste Zeilen), Matrix {bericht.get('matrix_zeilen')} Zeilen, "
            f"Ranglisten mit Spitzenreiter {bericht.get('ranglisten_mit_spitzenreiter') or '–'}, am häufigsten {bericht.get('am_haeufigsten')}, "
            f"Häufigkeit {bericht.get('haeufigkeit_eintraege')} Einträge, {_de(bericht.get('sekunden'))}"
        )
    depots = report.get("depots")
    if depots:
        summary.append(
            f"Musterdepots: Häufigkeit {depots.get('haeufigkeit_zeilen')} Aktien ({depots.get('gemeinsam')} gemeinsam), {depots.get('depots')} Depots, "
            f"„10 Sieger“ mit {depots.get('positionen')} Positionen, {depots.get('fenster')} Fenster, Basis {depots.get('basis') or '–'}"
            f"{' (Stand ohne Wechselkurse)' if depots.get('ohne_wechselkurse') else ''}, {_de(depots.get('sekunden'))}"
        )
    top3 = report.get("top3")
    if top3:
        summary.append(
            f"Top 3 nach Zahlen: {'oben auf der Startseite' if top3.get('zuerst_auf_startseite') else 'NICHT oben'}, {top3.get('zeilen')} Zeilen, "
            f"Punkte 0–100 {'ja' if top3.get('punkte_0_bis_100') else 'NEIN'}, absteigend {'ja' if top3.get('absteigend') else 'NEIN'}, "
            f"Teile je Zeile {'/'.join(str(n) for n in top3.get('teile_je_zeile') or []) or '–'}, mit Börsenwert {top3.get('mit_boersenwert')}, "
            f"mit Warnzeichen {top3.get('mit_warnzeichen')}, mit Trefferquote {top3.get('mit_trefferquote')}; "
            f"eigene Aktien {top3.get('eigene_aktien')} (davon mit Platz {top3.get('eigene_mit_platz')}, wenig gehandelt {top3.get('eigene_wenig_gehandelt', '–')}, "
            f"ohne Top-10-Nennung {top3.get('eigene_ohne_punkte', '–')}); Rangfolge erste Seite {top3.get('rangfolge_erste_seite')} Zeilen, "
            f"Seite „Top nach Zahlen“ fertig in {_de(top3.get('top_seite_s'))} (ganzer Schritt {_de(top3.get('sekunden'))})"
        )
    regel = report.get("regel")
    if regel:
        summary.append(
            f"Umschichtungs-Regel im offiziellen Stand (aus dem Zwischenstand geöffnet): {regel.get('zeilen')} Zeilen, "
            f"Wechsel {'ja' if regel.get('offiziell_aktiv') else 'NEIN'}, zurück zum Zwischenstand {'ja' if regel.get('zurueck_zum_zwischenstand') else 'NEIN'}, "
            f"{_de(regel.get('sekunden'))}"
        )
    signals = report.get("signale")
    if signals:
        if signals.get("hinweis"):
            summary.append(f"Signale: {signals['hinweis']}")
        else:
            summary.append(
                f"Signale (Stand {signals.get('id')}): {signals.get('aktien')} Aktien, {signals.get('mit_kursziel')} mit Kursziel, beide grün {signals.get('beide_gruen')}; "
                f"Potenzial-Liste {signals.get('zeilen_potenzial')} Zeilen, Einzelansicht {signals.get('urteile')} Urteile, {signals.get('signale')} Signale, "
                f"Prognose-Grafik {'ja' if signals.get('prognose') else 'nein'}, {_de(signals.get('sekunden'))}"
            )
            if signals.get("version"):
                summary.append(
                    f"Gesamtwertung ({signals.get('version')}): stark {signals.get('gesamt_stark', '–')}, mittel {signals.get('gesamt_mittel', '–')}; "
                    f"Einzelansicht mit Gesamtwertung {'ja' if signals.get('gesamtwertung') else 'nein'}, Daytrader-Check {signals.get('daytrader_punkte', 0)} Punkte"
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
    failed = report.get("fehlgeschlagene_abrufe") or []
    if failed:
        rows = [
            f"{f.get('schritt')}: {f.get('datei')} – " + (f"Status {f.get('status')}{' (Service Worker)' if f.get('service_worker') else ''}" if f.get("status") else f"abgebrochen: {f.get('fehler')}")
            for f in failed[:30]
        ]
        out.append(f"::warning title={_title('Fehlgeschlagene Abrufe')}::{_escape(chr(10).join(rows))}")
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
