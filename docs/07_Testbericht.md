# Testbericht – tatsächlich ausgeführt

Ausgeführt **am 12.10.2026 ab 22:30 Uhr bis 13.10.2026, 00:10 Uhr (Europe/Berlin)**; der letzte vollständige Gesamtlauf endete am 13.10.2026 um 00:10 Uhr in der Entwicklungsumgebung. Alle Zahlen unten stammen aus diesen Läufen. Was dort nicht prüfbar war, steht ausdrücklich im Abschnitt „Nicht geprüft“ – es gilt als offen, nicht als bestanden.

## Umgebung

| | |
|---|---|
| Rechner | Linux-Container, 2 vCPU (Intel Xeon 2,1 GHz), 8 GB RAM |
| Python | 3.13.16 (numpy 2.5.3, pandas 3.0.5, PyYAML 6.0.3, cryptography 50.0.1, requests 2.34.2, pdfplumber 0.11.10, pypdf 5.9.0) |
| Node.js / TypeScript | 22.22.0 / 6.0.3 |
| Browser-Tests | Playwright 1.56.0 mit Chromium 141.0.7390.37 |
| Netz | Nur lokale Verbindungen. TR-Liste, OpenFIGI, Yahoo, PyPI und npm-Registry waren gesperrt (Belege unten). |
| Daten | Ausschließlich klar gekennzeichnete synthetische Testdaten (DEMO: Namen beginnen mit „DEMO“, ISINs mit „ZZ“) und erzeugte Testreihen. Keine Livekurse. |

Die Workflows in GitHub Actions verwenden dieselbe Python-Version (3.13) und Node 22.

## 1. Gesamtlauf aller Python-Tests

```bash
PYTHONPATH=backend LOG_LEVEL=WARNING python -W always::ResourceWarning -m unittest discover -s tests -t . -v
```

**Ergebnis: 177 Tests, 169 bestanden, 8 übersprungen, 0 Fehler, Dauer 110,1 s, keine Ressourcenwarnung.**

| Modul | Tests | Inhalt |
|---|---:|---|
| `tests/unit/test_metrics.py` | 13 | Rendite, OLS, R², Steigung, Rauschen, MDD, Referenz mit exakter Bruchrechnung und `numpy.polyfit` |
| `tests/unit/test_windows.py` | 11 | Kalenderfenster 1–90, Startsitzung, fehlende Endkurse, Feiertage, Stichtag |
| `tests/unit/test_quality.py` | 19 | Zulassung (V/U), 98-%-/80-%-Grenzen, Splits, Einheiten, Sprünge, Kursbewegung ohne Umsatz |
| `tests/unit/test_ranking.py` | 16 | Perzentile, Gleichstände, alle elf Gewichtungen, native/common_trend, Untergruppen |
| `tests/unit/test_frequency.py` | 16 | Top-1/3/10-Häufigkeiten, Nenner, Invarianten, Renditesieger, Gesamtmaximum |
| `tests/unit/test_engine_coverage.py` | 5 | Abdeckungsbilanz, Reproduzierbarkeit |
| `tests/unit/test_providers.py` | 29 | TR-PDF-Parser (erzeugte PDFs), Yahoo-/EODHD-Antwortformate, OpenFIGI-Zuordnung, Drosselung, Stichtag, Sommerzeit, Verschlüsselung, Schwärzung |
| `tests/unit/test_workflows.py` | 8 | GitHub-Workflows: Auslöser, Rechte, Secrets, Bereitstellung nur nach bestandener Prüfung, Zeitplan = Konfiguration |
| `tests/integration/test_pipeline.py` | 15 | Täglicher Lauf mit DEMO-Quelle: Veröffentlichung, Doppelstart, Checkpoint, Ausfall, Parserfehler, atomares Schreiben, Tickerwechsel, Sicherung |
| `tests/integration/test_ci_flow.py` | 5 | Kompletter Ablauf `traktien ci` gegen nachgebildete GitHub-REST-API auf frischen Runnern; lückenloser Austausch der Sicherung |
| `tests/integration/test_app_contract.py` | 1 | Startet die 6 Datenvertragstests der App (Node) gegen echte DEMO-Dateien, unverschlüsselt und verschlüsselt |
| `tests/e2e/test_mobile_app.py` | 31 | Gebaute App im Browser auf simuliertem Galaxy S25+ |
| `tests/live/…` | 8 | **übersprungen** (siehe „Nicht geprüft“) |

## 2. App (TypeScript)

```bash
cd app && npm run typecheck && npm test && npm run build
```

- Typprüfung: **ohne Fehler**.
- `npm test`: 16 Tests, **10 bestanden**, 6 übersprungen – die 6 Datenvertragstests brauchen erzeugte Datendateien und laufen über `tests/integration/test_app_contract.py`. Dort: **6 von 6 bestanden, 0 übersprungen** (der Python-Test verlangt ausdrücklich `# fail 0` und `# skipped 0`).
- Datenvertrag: Die App berechnet Perzentile und Scores aller elf Gewichtungen **bitgleich** zur Serverberechnung; Renditesieger (90 Zeilen) und Häufigkeiten stimmen mit der Serverreferenz überein; Untergruppenranking stimmt mit `traktien.analytics.ranking.rank_subgroup` überein; verschlüsselte Dateien: richtige Passphrase entschlüsselt, falsche Passphrase und vertauschte Dateien scheitern.
- Build: `1.0.0+58c89471`, 13 Dateien. JavaScript 417 KB (gzip 133 KB), CSS 33 KB (gzip 7 KB). Der Build ergibt in drei verschiedenen Verzeichnissen byte-gleiche Dateien (Voraussetzung für die Prüfung „app/dist ist aktuell“ in GitHub Actions).

## 3. Browser-Tests (Emulation, kein echtes Gerät)

Chromium mit 384 × 832 CSS-Pixeln, Pixelverhältnis 2,8125, Touch, Sprache de-DE, Zeitzone Europe/Berlin – das entspricht der Bildschirmgröße des S25+, ersetzt aber **keinen Test auf dem Gerät**. 31 Tests, alle bestanden (52 s). Geprüft unter anderem:

- Start mit echtem Kursstand-Datum und DEMO-Kennzeichen in jeder Ansicht (11 Ansichten), Rendite-Leiter mit 90 Balken.
- „Höchste Rendite 1–90 Tage“ mit genau 90 Zeilen; jeder Zeitraum mit einem Tippen erreichbar.
- Ranking: Zeitraum (Lineal, Tastatur, Plus/Minus, Schnellwahl), alle elf Gewichtungen per Schieberegler, Leerzustand mit Grund (1 Tag + Gleichmäßigkeit), Top 50.
- Jede genannte ISIN öffnet den Chart genau dieser Aktie (Ranking, Rendite-Liste, Häufigkeitsliste, Raster, Gesamtverzeichnis); Aktie ohne Kurse zeigt einen Leerzustand statt eines erfundenen Verlaufs.
- Einzelchart: Tooltip, Pos1/Ende ohne Seitensprung, Zoom per Knopf und per Zwei-Finger-Geste, Antippen, Zurück mit wiederhergestellter Scrollposition; 1-Tages-Fenster ohne erfundenen Tagesverlauf.
- Tooltip, Kurstabelle, Kennzahl und PNG-Export beruhen auf denselben Kursen; der PNG-Export enthält Kursstand, Snapshot, DEMO-Hinweis und „keine Liveansicht“.
- Chart-Raster: gleicher Zeitraum, mehrere Zeiträume (jede Zelle = angefragter Zeitraum, alle Dateien aus einem Snapshot), gemeinsamer Indexvergleich; Originalkurse mit Währung je Kachel; Skalenwahl bleibt nach Neuladen erhalten; große Auswahl seitenweise, nur sichtbare Kacheln laden Kurse (höchstens 12 je Seite).
- Ranking, CSV-Export und Raster verwenden dieselbe Auswahl, dasselbe Vergleichsfeld und denselben Snapshot; CSV ist gegen Formel-Injection geschützt.
- Häufigkeitsliste stimmt mit der Serverberechnung überein; Treffermatrix 90 × 11 öffnet Details.
- Offline nach erstem Besuch mit Hinweis „Offline – gespeicherter Stand“; neue App-Version behält Watchlist und Einstellungen.
- Verschlüsselte Website: falscher Schlüssel abgewiesen, richtiger Schlüssel öffnet; nach Neuladen weiter entsperrt.
- Alle Bedienelemente mindestens 44 × 44 Pixel und beschriftet; Querformat/Desktop mit Seitenleiste; Dunkelmodus.

Bildschirmfotos dieser Emulation: `docs/bilder/`.

## 4. Lauf ohne Handy, Wiederanlauf und Veröffentlichung (nachgebildetes GitHub)

`tests/integration/test_ci_flow.py` führt `python -m traktien ci` dreimal auf jeweils frischen Arbeitsverzeichnissen gegen eine nachgebildete GitHub-REST-API aus (Release anlegen, Assets hoch-/herunterladen, löschen, umbenennen):

1. Erster Lauf: veröffentlicht, Ausgaben `deploy=true`, `status=veroeffentlicht`; Release „datenstand“ als Vorabversion mit `crypto.json`, `state.sqlite.tra`, `site-<id>.tar`, `evidence-<id>.tra`; kein Geheimnis in Assets; `verify-site` bestanden (378 Dateien entschlüsselt und geprüft).
2. Zweiter Lauf auf neuem Runner: Zustand aus der Sicherung, Status `keine_neuen_daten`, der erste Stand bleibt veröffentlicht.
3. Mit verwaister Sperre in der Sicherung: Sperre wird freigegeben, alter Lauf als „abgebrochen“ markiert, Lauf erfolgreich.
4. Ohne `DATA_PASSPHRASE`: Abbruch, bevor irgendetwas hochgeladen oder gebaut wird.
5. Sicherung austauschen: Verbindungsabbruch beim Hochladen lässt die alte Sicherung unverändert; Abbruch beim Umbenennen hinterlässt die neueste vollständige Fassung, die der nächste Lauf übernimmt und repariert.

## 5. Sicherung und Wiederherstellung

```bash
PYTHONPATH=backend python -m traktien demo --fresh
PYTHONPATH=backend python -m traktien restore-test --state-dir build/demo-state
```

Ergebnis (DEMO-Zustand): `wiederherstellung_ok: true` – instrument 198/198, listing 195/195, daily_bar 26.575/26.575, run 1/1, snapshot_manifest 1/1, universe_member 198/198. Verschlüsselte Wiederherstellung in einem sauberen Verzeichnis und Abweisung eines falschen Schlüssels: `test_T55_backup_restores_in_clean_environment`. Details: 08_Backup_und_Wiederherstellung.

`python -m traktien verify-site --site build/demo-site`: 378 Datendateien, 0 Fehler.

## 6. Leistungsmessung (synthetisch)

```bash
PYTHONPATH=backend python tests/perf/perf_universe.py 11500 --encrypt
```

| Messgröße | Wert |
|---|---|
| Instrumente × Zeiträume | 11.500 × 90 = 1.035.000 |
| Rechenkern (alle Fenster, elf Gewichtungen, Häufigkeiten) | 42,6 s |
| Veröffentlichung (verschlüsselt) | 56,5 s, 11.684 Dateien |
| Größe eines Datenstands | 74,0 MB (Fenster 44,7, Kursreihen 28,3, Übrige 1,0) |
| Höchster Arbeitsspeicher | 411 MB |
| Vergleichsfelder bei 30 Tagen | V = 10.804, U = 5.240 |
| Gesamtdauer des Skripts | 101 s |

Nicht enthalten ist der Kursabruf über das Netz (eine Anfrage je Notierung, gedrosselt auf 2,5 je Sekunde, rechnerisch gut eine Stunde für 10.000 Notierungen) – er war hier nicht messbar.

Hochrechnung (nicht gemessen): Die DEMO-Datenbank belegt rund 110 Byte je Tageskurs einschließlich Indizes. Bei 11.500 Notierungen und 250 Tagen Aufbewahrung (≈ 175 Börsentage) wären das etwa 220 MB, komprimiert und verschlüsselt etwa 80 MB je Sicherung.

## 7. Nicht geprüft (offen)

| Punkt | Grund | Was es abschließt |
|---|---|---|
| Echte Datenquellen (TR-PDF, OpenFIGI, Yahoo, EODHD) | Netz gesperrt. Versuch mit `TR_LIVE=1`: `ProxyError` für `assets.traderepublic.com`, `api.openfigi.com`, `query2.finance.yahoo.com` (12.10.2026, ca. 23:43 Uhr); EODHD ohne Schlüssel übersprungen | Workflow „Datenquellen prüfen“ in GitHub Actions; Bericht `datenquellen-bericht.json` |
| Börsenkalender `exchange_calendars` | Paket hier nicht installierbar (PyPI gesperrt); 4 Tests übersprungen | Workflow „Prüfung“ führt `tests.live.test_calendars_live` aus |
| `npm ci` gegen die öffentliche Registry | Registry gesperrt; Lockdatei aus der vorhandenen Installation erzeugt | Workflow „Prüfung“ (mit Rückfall auf `npm install`) |
| Täglicher Lauf in GitHub Actions, GitHub Pages | Kein Repository-Zugang in dieser Sitzung | Erster grüner Lauf „Täglicher Lauf“ und erreichbare Pages-Adresse |
| Echter Lauf über das gesamte TR-Universum | Datenquellen gesperrt | Abdeckungsbilanz des ersten produktiven Datenstands |
| Bedienung auf dem echten Galaxy S25+ | Kein Gerät | Installation und Durchklicken nach 01_Kurzanleitung_Handy |
| Python 3.13 in GitHub Actions statt lokal | gleiche Version, aber anderer Rechner | Workflow „Prüfung“ |

## 8. Abnahmetests T01–T100: Zuordnung

„E2E“ = Browser-Emulation (Abschnitt 3), „Vertrag“ = App-Datenvertragstest (Abschnitt 2). Alle genannten Tests liefen am 12.10.2026 und waren grün, sofern nicht anders vermerkt.

| Test | Nachweis |
|---|---|
| T01, T02, T05, T07, T10, T11 | `test_metrics`: test_T01…, test_T02…, test_T05…, test_T07…, test_T10…, test_T11… |
| T03, T21–T24, T27, T28 | `test_windows`: je ein gleichnamiger Test; T21 zusätzlich `test_quality.test_window_lengths_above_90_are_rejected_in_core` |
| T04 | `test_quality.test_T04…`; E2E `test_ranking_window_weight_and_empty_reason` |
| T06 | `test_metrics.test_T06…` (R² ≈ 1) und `test_quality.test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings` |
| T08, T09, T29–T33, T35 | `test_quality`: gleichnamige Tests (T29 und T32 je zwei) |
| T12–T20 | `test_ranking`: gleichnamige Tests; T20 zusätzlich Vertrag (Untergruppe) und E2E Watchlist-Untergruppe |
| T25 | `test_windows.test_T25…` (Feiertage je Börse), `test_providers.DaylightSavingTests` (Sommerzeitwechsel USA/Europa); echte Kalender: offen (Abschnitt 7) |
| T26 | `test_providers.test_T26_running_session_does_not_replace_final_close`, `test_T26_session_final_checker` |
| T34 | `test_providers.test_T34_dividend_adjusted_close_is_kept_separate` |
| T36 | `test_providers.test_country_preference_and_T36_one_reference_per_isin`, `test_frequency.test_T88_duplicate_isin_listings_are_rejected_upstream` |
| T37 | `test_pipeline.test_T37_ticker_change_keeps_name_isin_and_one_ranking_entry` |
| T38, T40 | `test_engine_coverage`; T40 zusätzlich `test_pipeline.test_idempotent_rerun_creates_no_second_snapshot` |
| T39 | `test_metrics.test_T39…` (exakte Bruchrechnung, `numpy.polyfit`); Vertrag: App-Scores bitgleich |
| T41 | `test_pipeline.test_T41_T60…`, `test_ci_flow` – echter GitHub-Zeitplan offen |
| T42 | `test_pipeline` (Doppelstart, verwaiste Sperre), `test_ci_flow`, `test_workflows.test_T42…` |
| T43, T44 | `test_pipeline.test_T43_T44…`, `test_T44_provider_outage…`; `test_providers` (Retry-After, Dauerdrosselung, Zeitüberschreitung); `test_ci_flow.ReleaseReplaceTests` |
| T45, T46, T47 | `test_pipeline` (gleichnamig); T45 zusätzlich `test_providers.test_T45_guards…`; T47 zusätzlich E2E T64/T99 |
| T48, T49 | E2E `test_offline_after_first_visit`, `test_T49…` |
| T50 | `pure.test.ts` (Name, Alias, Ticker, ISIN); `test_pipeline.test_T37…` (alter Ticker bleibt suchbar) |
| T51 | E2E 90 Zeilen, T100, T66/T69/T70, 44-px-Ziele – Emulation; Gerät offen |
| T52 | `test_pipeline.test_T52…`, `test_providers.test_T52_secrets_are_redacted_in_logs`, `test_ci_flow`, `test_workflows.test_T52…`, `verify-site` |
| T53 | `test_workflows.test_T53…` (zwei Tests): Läufe nur per Zeitplan oder durch Berechtigte; es gibt keine Server-Schnittstelle, über die Dritte einen Lauf auslösen könnten |
| T54 | `pure.test.ts` (Formel-Injection), E2E CSV-Export |
| T55 | `test_pipeline.test_T55…`, `test_ci_flow`, `restore-test` (Abschnitt 5) |
| T56, T59 | `test_pipeline` und E2E (gleichnamig) |
| T57 | `pure.test.ts` „Prozentformat“: 0 → „0,00 %“ und „unverändert“, fehlend → „–“ und „nicht berechenbar“ |
| T58, T83 | `test_ranking.test_T83_native_zero_may_show_only_negative_returns` |
| T60 | `test_pipeline.test_T41_T60…`, E2E `test_T60_demo_is_marked_in_every_view`, CSV- und PNG-Test |
| T61, T62, T64, T71, T77, T99, T100 | E2E gleichnamig (T77 nur Emulation) |
| T63 | E2E `test_one_day_window_shows_only_daily_closes` |
| T65, T67, T68 | `pure.test.ts` |
| T66, T69, T70 | E2E `test_T66_T69_T70_grid_units_scales_and_full_labels` |
| T72, T74 | E2E `test_T72_T74…`: kein Livefeed eingerichtet und so beschriftet; alle Charts laufen ohne Livevertrag |
| T73 | entfällt: Es gibt keinen Livefeed, also keine Liveupdates |
| T75, T78 | E2E `test_T75_T78…` |
| T76 | `pure.test.ts` T67/T68: kein Auffüllen fehlender Tage, Lücken unterbrechen die Linie |
| T79–T85 | `test_ranking` (gleichnamig); T79 und T80 zusätzlich `pure.test.ts` (Parameterprüfung mit alten Aliasnamen); T81 zusätzlich Vertrag |
| T86–T98 | `test_frequency` (gleichnamig; T92 im Invariantentest); T90, T92–T95 zusätzlich Vertrag; E2E Häufigkeitsliste = Serverberechnung |
