# AktienPilot – Umsetzungsstand (Fortschrittsdatei)

Fortschrittsdatei zum Auftrag [`13_AktienPilot.md`](13_AktienPilot.md) (Fassung 31.10.2026, KOSTENFREI). Entscheidungen stehen in
[`13_AktienPilot_Entscheidungen.md`](13_AktienPilot_Entscheidungen.md). Diese Datei wird nach jedem Arbeitsschritt aktualisiert
und mit dem Code eingecheckt.

**Statuswerte:** implementiert und getestet · implementiert, extern ungeprüft · blockiert · noch offen · optional außerhalb P1–P6

## Arbeitsstand

| | |
|---|---|
| Branch | `aktienpilot` (Pull Request #1, Entwurf); `main` unverändert |
| Letzter Stand | 31.10.2026, 13:05 Uhr: P1 begonnen – Auftrag abgelegt, Bestand geprüft, Migration, Konfiguration und erste Fachmodule (Indikatoren, Marktdaten, Zeitregeln, Kosten, Ereignisjournal) als Code, **noch ohne Tests** |
| Nächster konkreter Schritt | Tests für Konfiguration, Migration, Indikatoren, Zeitregeln, Kosten und Ereignisjournal; danach Risiko-Manager und Simulator (P2) |
| Läuft gerade im Hintergrund | nichts |

## Auftragsablage (Abschnitt 2)

| Prüfung | Ergebnis |
|---|---|
| Datei | `docs/13_AktienPilot.md`, byte-gleich mit der Anlage vom 31.10.2026, 12:36 Uhr |
| Größe | 50.593 Bytes, 304 Zeilen |
| SHA-256 | `811fec14ccf56be8588fd1b5e41e502b834107e5223c516e20aec8ab8700d4e1` |
| Abschnitte 0–23 | alle vorhanden (0 Arbeitsweise … 23 Phasen, Qualität und Abschluss) |
| Kostenfrei-Vorgabe | vorhanden (Kopf „KOSTENFREI“, Abschnitt 0, Budget 0 EUR einmalig und laufend) |
| Endmarkierung | vorhanden: „ENDE DES VOLLSTÄNDIGEN AUFTRAGS – AKTIENPILOT – ABSCHNITTE 0–23 – KOSTENFREI – FASSUNG 31.10.2026“ |
| Vorige Fassung | `docs/13_AktienPilot_Fassung_1_unvollstaendig.md` (7.787 Bytes, SHA-256 `4691840490c8…`, endet mitten in Abschnitt 5) |
| Ergänzung 31.10.2026, 12:54 Uhr | ohne neue Datei: „Jetzt aktualisieren“ mit Fortschritt, Kurs-/Abrufzeit/Verzögerung getrennt, Beschleunigung mit Messungen – eigener Branch `aktualisierung` |

## Bestandsprüfung (Abschnitt 2), 31.10.2026

| Auftrag sagt | Tatsächlich | Ergebnis |
|---|---|---|
| Python-Paket `traktien` unter `backend/`, PWA unter `app/`, unittest- und npm-Tests, `config/` | so vorhanden | bestätigt |
| verschlüsselte SQLite in Release-Assets, verschlüsselte Veröffentlichung über GitHub Pages | Release „datenstand“, Container TRA1 (AES-256-GCM, PBKDF2 600.000) | bestätigt |
| Python 3.13 | alle Workflows `python-version: '3.13'` | bestätigt |
| Lauf 07:00 Europe/Berlin, Wiederholungen 07:15, 07:45, 09:00; Nachtlauf Mo–Fr 22:37 UTC | `taeglich.yml` und `nachtlauf.yml` so eingetragen | bestätigt (GitHub startet Zeitpläne teils verspätet) |
| App 1.20.2 | **1.20.3** (Darstellung der Kurskorrekturen auf dem Handy, 31.10.2026) | abweichend, neuer |
| Kursabgleich `kursabgleich-1.1` | **`kursabgleich-1.2`** (Rundung nur an Tagen mit Rundung, Hauptquelle ohne Splitbereinigung nach näherer Basis) | abweichend, neuer; Split-, Umsatzstatus-, Basisbruch- und Sprungprüfung erhalten |
| Datenstand `2026-10-30_be3f33c4` | ja, mit Regel 1.2 gerechnet | bestätigt |
| AGENTS.md | nicht vorhanden | – |
| Branch `aktienpilot`, PR #1 | nur abgeschnittener Auftrag und Bestandsaufnahme; jetzt mit `main` 1.20.3 zusammengeführt | geeignet, weiterverwendet |
| Referenz „Zwei_Zehnerdepots… vom 30.10.2026“ | nicht vorhanden; vorhanden sind die Fassungen mit Datenstand 13.10.2026 (Modell TR-90D-11W-two-universes-v1.1) und deren Nachrechnung `tests/live/vergleich/chatgpt_2026-10-13.json` | Referenzprüfung 30.10. **fehlt** (keine Originaldaten) – nicht als bestanden gemeldet |

## Anforderungsübersicht

Spalten: Nr. · Anforderung (Abschnitt) · Status · Umsetzung · Testbeleg · Einschränkung

| Nr. | Anforderung | Status | Umsetzung | Testbeleg | Einschränkung |
|---|---|---|---|---|---|
| 0.1 | Nullbudget: kostenpflichtige Anbieter nicht aktivierbar (0) | implementiert, Test offen | `config.parse_config` (kostenpflichtig + aktiv → Fehler) | – | Kontoeinstellungen bei GitHub/ntfy prüft nur der Nutzer |
| 0.2 | Entscheidungsdatei, Fortschrittsdatei (0) | implementiert | diese Datei, `13_AktienPilot_Entscheidungen.md` | – | – |
| 1.1 | Hauptvergleich MSCI-World-ETF mit ISIN, Notierung, Währung, Ausschüttung, Quelle (1) | teilweise | `config/aktienpilot.yaml` `vergleich` | – | Belege der Eigenschaften noch nachzutragen |
| 1.2 | Messwerte, Simulationen, Annahmen, synthetische Daten unterscheiden (1) | noch offen | – | – | – |
| 2.1 | Auftragsablage mit Größe und SHA-256 (2) | implementiert und geprüft | siehe oben | `sha256sum`, Abschnittsprüfung | – |
| 2.2 | Referenztests je Methodenversion, Golden Master der aktuellen Methode (2) | noch offen | – | – | 30.10.-Referenz fehlt |
| 3.1 | Getrennte Module, eigene Tabellen, Migration (3) | teilweise | `aktienpilot/*`, `0010_aktienpilot.sql` | – | – |
| 3.2 | Sperren, Transaktionen, Sicherungen für Lauf, Bestätigung, Veröffentlichung (3, 18) | noch offen | – | – | – |
| 4.1 | SIGNAL-Standard, keine Orders an TR, Signalinhalt (4) | noch offen | – | – | – |
| 4.2 | Bestätigung von Stückzahl, Kurs, Zeit, Gebühren; Teil, Überspringen, Storno, Stop (4) | noch offen | – | – | – |
| 4.3 | PAPER-Simulator im Tageslauf (4) | noch offen | – | – | – |
| 4.4 | Broker-Schnittstelle mit gemeldeten Fähigkeiten (4) | noch offen | – | – | LIVE-Adapter erst P7 |
| 4.5 | Verschlüsselter Rückweg ohne Server, Rechteprüfung, Status (4, P5) | noch offen | – | – | – |
| 5.1 | Universum, Abdeckung, CSV-Import/-Export, Handelsfilter (5) | noch offen | – | – | – |
| 6.1 | Lineal-Ranking unverändert erhalten (6) | bestehend | Rechenkern `analytics/*` | bestehende Tests | – |
| 6.2 | Vorwärts laufendes Lineal-Musterdepot, Regel vorab versioniert (6) | noch offen | – | – | – |
| 7.1 | Datenqualität, Zeitpunkte, keine Look-Ahead-Daten (7) | teilweise | `markt`, `zeitregel` | – | – |
| 8.1 | S1 Momentum-Rotation (8) | noch offen | `indikatoren` (Regression, Perzentile, Lücken) | – | – |
| 9.1 | S2 Swing-Breakout (9) | noch offen | – | – | – |
| 10.1 | S3 Mean-Reversion, Marktfilter (10) | noch offen | – | – | – |
| 11.1 | S4 Robo-Kern, Fragebogen, Rebalancing, Sparplan-Rechner (11) | noch offen | – | – | – |
| 12.1 | S5 KI-Prüfung | optional außerhalb P1–P6 | – | – | P7 |
| 13.1 | Ausführungsprofile und Zeitregeln (13) | implementiert, Test offen | `zeitregel.py` | – | – |
| 13.2 | Limit, Stop, Kurslücken konservativ (13) | noch offen | – | – | – |
| 14.1 | Backtest-Labor mit Walk-Forward, Kosten, Monte-Carlo, Block-Bootstrap, Kennzahlen, HTML (14) | noch offen | `kosten.py` | – | – |
| 15.1 | Zentraler Risiko-Manager (15) | noch offen | – | – | – |
| 16.1 | Verlustgrenzen und Not-Aus (16) | noch offen | – | – | – |
| 17.1 | Anfangsbestand, Fremdtransaktionen, Journal (17) | teilweise | `buchhaltung.py` | – | – |
| 18.1 | Tageslauf-Integration, Wiederanlauf ohne Doppelbuchung (18) | noch offen | – | – | – |
| 19.1 | Strategie-Wettbewerb, Journal (19) | noch offen | – | – | – |
| 20.1 | App-Bereich AktienPilot (20) | noch offen | – | – | – |
| 20.2 | ntfy nur allgemein, standardmäßig aus (20) | noch offen | Konfiguration | – | – |
| 20.3 | Telegram, LIVE-Anmeldung | optional außerhalb P1–P6 | – | – | P7 |
| 21.1 | Steuerannahmen, CSV/Excel-Export mit FIFO (21) | noch offen | `config.TaxConfig.rate` | – | – |
| 22.1 | Echtgeldfreigabe-Prüfung, einmaliger Code (22) | noch offen | Tabelle `ap_freigabe` | – | 30 PAPER-Sitzungen erst im Betrieb |
| 23.1 | start.bat, Anleitung, Wiederherstellung, Integrationsprüfung, DEMO-Ablauf (23) | noch offen | – | – | – |
| 23.2 | P7 (LIVE-Dienst, Broker, Regel-Baukasten, S5) | optional außerhalb P1–P6 | – | – | nur nach Beauftragung |
