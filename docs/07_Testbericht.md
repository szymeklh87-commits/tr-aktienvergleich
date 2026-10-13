# Testbericht – tatsächlich ausgeführt

Stand **13.10.2026, 13:45 Uhr (Europe/Berlin)**, Software **1.1.0** (zwei Rendite-Ranglisten mit Umsatzfilter). Ausgeführt wurde an zwei Orten:

- **Entwicklungsumgebung** (12.10.2026 22:30 Uhr bis 13.10.2026 13:30 Uhr): alle Tests mit synthetischen DEMO-Daten. Externe Datenquellen waren von hier aus nicht erreichbar.
- **GitHub Actions** (seit 13.10.2026): Workflow „Prüfung“ bei jeder Änderung, Workflow „Datenquellen prüfen“ mit den echten Quellen und die ersten echten täglichen Läufe (Abschnitt 7).

Alle Zahlen unten stammen aus diesen Läufen. Was nicht prüfbar war, steht ausdrücklich unter „Nicht geprüft“ (Abschnitt 8) – es gilt als offen, nicht als bestanden.

## Überblick

| Wo | Was | Ergebnis |
|---|---|---|
| Entwicklungsumgebung, 13.10.2026 | Alle Python-Tests, Version 1.1.0 | 218 Tests: **208 bestanden**, 10 übersprungen (6 Live-Tests ohne Netz, 4 Kalendertests ohne Bibliothek), 0 Fehler |
| Entwicklungsumgebung, 13.10.2026 | App: Typprüfung, 22 Tests, Build | ohne Fehler; 14 bestanden, 8 Datenvertragstests über Python (8 von 8 bestanden); Build byte-gleich |
| GitHub Actions „Prüfung“, 13.10.2026 12:39 Uhr (Version 1.0.0, Commit e3cb48e) | alle Tests auf GitHub-Rechner, echte Börsenkalender | 185 Tests bestanden, 5 Live-Tests übersprungen; Kalender 4 von 4; `npm ci` ohne Rückfall; `app/dist` identisch |
| GitHub Actions „Datenquellen prüfen“, 13.10.2026 12:02 Uhr | echte TR-Liste, OpenFIGI, Yahoo | 7 bestanden, **1 fehlgeschlagen** (Yahoo ohne Schlusskurs 12.10.2026 in Europa und Asien), 1 übersprungen (EODHD ohne Schlüssel) |
| GitHub Actions „Täglicher Lauf“, 13.10.2026 | erste echte Läufe | Website mit App online; noch **kein Datenstand** veröffentlicht (Yahoo-Lücke 12.10., Zuordnung des Universums läuft) |

Die Uhrzeiten in dieser Datei sind deutsche Zeit (MESZ); in GitHub erscheinen sie in UTC (zwei Stunden früher).

## Umgebung (Entwicklung)

| | |
|---|---|
| Rechner | Linux-Container, 2 vCPU (Intel Xeon 2,1 GHz), 8 GB RAM |
| Python | 3.13.16 (numpy 2.5.3, pandas 3.0.5, PyYAML 6.0.3, cryptography 50.0.1, requests 2.34.2, pdfplumber 0.11.10, pypdf 5.9.0) |
| Node.js / TypeScript | 22.22.0 / 6.0.3 |
| Browser-Tests | Playwright 1.56.0 mit Chromium 141.0.7390.37 |
| Netz | Nur lokale Verbindungen. TR-Liste, OpenFIGI, Yahoo, EZB, PyPI und npm-Registry waren gesperrt (z. B. EZB am 13.10.2026: „CONNECT tunnel failed, response 403“). |
| Daten | Ausschließlich klar gekennzeichnete synthetische Testdaten (DEMO: Namen beginnen mit „DEMO“, ISINs mit „ZZ“) und erzeugte Testreihen. Keine Livekurse. |

Die Workflows in GitHub Actions verwenden dieselbe Python-Version (3.13) und Node 22.

## 1. Gesamtlauf aller Python-Tests

```bash
PYTHONPATH=backend LOG_LEVEL=WARNING python -W always::ResourceWarning -m unittest discover -s tests -t . -v
```

**Ergebnis (13.10.2026, Version 1.1.0): 218 Tests, 208 bestanden, 10 übersprungen, 0 Fehler, Dauer 164,6 s, keine Ressourcenwarnung.**

| Modul | Tests | Inhalt |
|---|---:|---|
| `tests/unit/test_metrics.py` | 13 | Rendite, OLS, R², Steigung, Rauschen, MDD, Referenz mit exakter Bruchrechnung und `numpy.polyfit` |
| `tests/unit/test_windows.py` | 11 | Kalenderfenster 1–90, Startsitzung, fehlende Endkurse, Feiertage, Stichtag |
| `tests/unit/test_quality.py` | 19 | Zulassung (V/U), 98-%-/80-%-Grenzen, Splits, Einheiten, Sprünge, Kursbewegung ohne Umsatz |
| `tests/unit/test_ranking.py` | 16 | Perzentile, Gleichstände, alle elf Gewichtungen, native/common_trend, Untergruppen |
| `tests/unit/test_frequency.py` | 16 | Top-1/3/10-Häufigkeiten, Nenner, Invarianten, Renditesieger, Gesamtmaximum |
| `tests/unit/test_engine_coverage.py` | 5 | Abdeckungsbilanz, Reproduzierbarkeit |
| `tests/unit/test_turnover.py` | 22 | **neu 1.1:** Ø Tagesumsatz (Definition, fehlende Sitzungen, 16 von 20, Untereinheiten, Wechselkurse, Split), zwei Rendite-Ranglisten, Übernahmemuster |
| `tests/unit/test_ecb.py` | 6 | **neu 1.1:** EZB-Datei (Parser, Schutz vor XML-Angriffen, HTTP-Fehler), Ablage im Lauf, Rückfall auf gespeicherte Kurse |
| `tests/unit/test_summary.py` | 3 | Kurzbericht des Laufs als GitHub-Hinweis (Reihenfolge, Kürzung auf GitHubs Grenze) |
| `tests/unit/test_providers.py` | 29 | TR-PDF-Parser (erzeugte PDFs), Yahoo-/EODHD-Antwortformate, OpenFIGI-Zuordnung, Drosselung, Stichtag, Sommerzeit, Verschlüsselung, Schwärzung |
| `tests/unit/test_workflows.py` | 8 | GitHub-Workflows: Auslöser, Rechte, Secrets, Bereitstellung nur nach bestandener Prüfung, Zeitplan = Konfiguration |
| `tests/integration/test_pipeline.py` | 16 | Täglicher Lauf mit DEMO-Quelle: Veröffentlichung, Doppelstart, Checkpoint, erneuter Abruf fehlender Stichtagskurse, Ausfall, Parserfehler, atomares Schreiben, Tickerwechsel, Sicherung; beide Rendite-Ranglisten in allen Dateien gleich |
| `tests/integration/test_ci_flow.py` | 7 | Kompletter Ablauf `traktien ci` gegen nachgebildete GitHub-REST-API auf frischen Runnern; lückenloser Austausch der Sicherung; nur Website neu bereitstellen; neue Passphrase |
| `tests/integration/test_app_contract.py` | 1 | Startet die 8 Datenvertragstests der App (Node) gegen echte DEMO-Dateien, unverschlüsselt und verschlüsselt |
| `tests/e2e/test_mobile_app.py` | 36 | Gebaute App im Browser auf simuliertem Galaxy S25+ |
| `tests/live/…` | 10 | **übersprungen** (6 Quellen ohne Netz, 4 Kalender ohne Bibliothek) – in GitHub Actions ausgeführt, Abschnitt 7 |

## 2. App (TypeScript)

```bash
cd app && npm run typecheck && npm test && npm run build
```

- Typprüfung: **ohne Fehler**.
- `npm test`: 22 Tests, **14 bestanden**, 8 übersprungen – die 8 Datenvertragstests brauchen erzeugte Datendateien und laufen über `tests/integration/test_app_contract.py`. Dort: **8 von 8 bestanden, 0 übersprungen** (der Python-Test verlangt ausdrücklich `# fail 0` und `# skipped 0`).
- Datenvertrag: Die App berechnet Perzentile und Scores aller elf Gewichtungen **bitgleich** zur Serverberechnung; Renditesieger (90 Zeilen) und Häufigkeiten stimmen mit der Serverreferenz überein; Untergruppenranking stimmt mit `traktien.analytics.ranking.rank_subgroup` überein; verschlüsselte Dateien: richtige Passphrase entschlüsselt, falsche Passphrase und vertauschte Dateien scheitern. **Neu 1.1:** Ranking 2 ist in jeder Fensterdatei genau Ranking 1 ohne die nicht aufgenommenen Aktien, mit gleichen Renditen, Start- und Endkursen; Start- und Endkurs ergeben die Rendite (Endkurs / Startkurs − 1, Abweichung ≤ 10⁻¹²); die Häufigkeit mit Umsatzfilter zählt nur aufgenommene Aktien und nennt ihr Universum.
- Build: `1.1.0+a090957e`, 13 Dateien. JavaScript 442 KB (gzip 141 KB), CSS 34 KB (gzip 8 KB). Ein erneuter Build ergibt byte-gleiche Dateien (Voraussetzung für die Prüfung „app/dist ist aktuell“ in GitHub Actions).

## 3. Browser-Tests (Emulation, kein echtes Gerät)

Chromium mit 384 × 832 CSS-Pixeln, Pixelverhältnis 2,8125, Touch, Sprache de-DE, Zeitzone Europe/Berlin – das entspricht der Bildschirmgröße des S25+, ersetzt aber **keinen Test auf dem Gerät**. 36 Tests, alle bestanden (59 s). Geprüft unter anderem:

- **Neu 1.1 – zwei Rendite-Ranglisten:** zwei getrennte Reiter „Alle Aktien“ und „Ø Umsatz ≥ 10 Mio. USD“; je Zeitraum zuerst der Sieger, Antippen öffnet die Top 10, von dort die vollständige Liste mit Seiten; Standardansicht 1–7 Tage. Je Aktie Rang, Name, Ticker, ISIN, Kursrendite, Start- und Endkurs mit Datum, Börse und Währung, Ø Tagesumsatz mit Berechnungsbasis und Hinweise. Aktien mit sehr niedrigem Umsatz sind in Ranking 1 gekennzeichnet und fehlen in Ranking 2. Zählungen (TR-Instrumente, geladene Kursreihen, bewertete Aktien je Rangliste) stehen getrennt da.
- **Neu 1.1:** Startdatum nach Wochenende/Feiertag = letzter Schlusskurs davor (angezeigte Daten stimmen mit den Kalenderfenstern überein); Einzelansicht zeigt Ø Tagesumsatz und beide Rendite-Plätze; Häufigkeitsliste nennt Universum und Umsatzfilter; Passphrase lässt sich vor dem ersten Datenstand eingeben.
- Start mit echtem Kursstand-Datum und DEMO-Kennzeichen in jeder Ansicht (11 Ansichten), Rendite-Leiter mit 90 Balken.
- Ranking: Zeitraum (Lineal, Tastatur, Plus/Minus, Schnellwahl), alle elf Gewichtungen per Schieberegler, Leerzustand mit Grund (1 Tag + Gleichmäßigkeit), Top 50.
- Jede genannte ISIN öffnet den Chart genau dieser Aktie (Ranking, Rendite-Liste, Häufigkeitsliste, Raster, Gesamtverzeichnis); Aktie ohne Kurse zeigt einen Leerzustand statt eines erfundenen Verlaufs.
- Einzelchart: Tooltip, Pos1/Ende ohne Seitensprung, Zoom per Knopf und per Zwei-Finger-Geste, Antippen, Zurück mit wiederhergestellter Scrollposition; 1-Tages-Fenster ohne erfundenen Tagesverlauf.
- Tooltip, Kurstabelle, Kennzahl und PNG-Export beruhen auf denselben Kursen; der PNG-Export enthält Kursstand, Snapshot, DEMO-Hinweis und „keine Liveansicht“.
- Chart-Raster: gleicher Zeitraum, mehrere Zeiträume (jede Zelle = angefragter Zeitraum, alle Dateien aus einem Snapshot), gemeinsamer Indexvergleich (Start = 100); Originalkurse mit Währung je Kachel; Skalenwahl bleibt nach Neuladen erhalten; große Auswahl seitenweise, nur sichtbare Kacheln laden Kurse (höchstens 12 je Seite).
- Ranking, CSV-Export und Raster verwenden dieselbe Auswahl, dasselbe Vergleichsfeld und denselben Snapshot; CSV ist gegen Formel-Injection geschützt.
- Häufigkeitsliste stimmt mit der Serverberechnung überein; Treffermatrix 90 × 11 öffnet Details.
- Offline nach erstem Besuch mit Hinweis „Offline – gespeicherter Stand“; neue App-Version behält Watchlist und Einstellungen.
- Verschlüsselte Website: falscher Schlüssel abgewiesen, richtiger Schlüssel öffnet; nach Neuladen weiter entsperrt.
- Alle Bedienelemente mindestens 44 × 44 Pixel und beschriftet; Querformat/Desktop mit Seitenleiste; Dunkelmodus.

Bildschirmfotos dieser Emulation: `docs/bilder/`.

## 4. Lauf ohne Handy, Wiederanlauf und Veröffentlichung (nachgebildetes GitHub)

`tests/integration/test_ci_flow.py` führt `python -m traktien ci` mehrfach auf jeweils frischen Arbeitsverzeichnissen gegen eine nachgebildete GitHub-REST-API aus (Release anlegen, Assets hoch-/herunterladen, löschen, umbenennen):

1. Erster Lauf: veröffentlicht, Ausgaben `deploy=true`, `status=veroeffentlicht`; Release „datenstand“ als Vorabversion mit `crypto.json`, `state.sqlite.tra`, `site-<id>.tar`, `evidence-<id>.tra`; kein Geheimnis in Assets; `verify-site` bestanden.
2. Zweiter Lauf auf neuem Runner: Zustand aus der Sicherung, Status `keine_neuen_daten`, der erste Stand bleibt veröffentlicht.
3. Mit verwaister Sperre in der Sicherung: Sperre wird freigegeben, alter Lauf als „abgebrochen“ markiert, Lauf erfolgreich.
4. Ohne `DATA_PASSPHRASE`: Abbruch, bevor irgendetwas hochgeladen oder gebaut wird.
5. Sicherung austauschen: Verbindungsabbruch beim Hochladen lässt die alte Sicherung unverändert; Abbruch beim Umbenennen hinterlässt die neueste vollständige Fassung, die der nächste Lauf übernimmt und repariert.
6. Nur Website (`--nur-website`): neue App-Hülle mit den vorhandenen Datenständen, Sicherung unverändert; zusammen mit „Zustand neu aufbauen“ entsteht in Sekunden ein neuer Schlüssel ohne Daten.

## 5. Sicherung und Wiederherstellung

```bash
PYTHONPATH=backend python -m traktien demo --fresh
PYTHONPATH=backend python -m traktien restore-test --state-dir build/demo-state
```

Ergebnis (DEMO-Zustand, 13.10.2026): `wiederherstellung_ok: true` – instrument 198/198, listing 195/195, daily_bar 26.575/26.575, run 1/1, snapshot_manifest 1/1, universe_member 198/198. Verschlüsselte Wiederherstellung in einem sauberen Verzeichnis und Abweisung eines falschen Schlüssels: `test_T55_backup_restores_in_clean_environment`. Details: 08_Backup_und_Wiederherstellung.

`python -m traktien verify-site --site build/demo-site`: 378 Datendateien, 0 Fehler.

## 6. Leistungsmessung (synthetisch)

```bash
PYTHONPATH=backend python tests/perf/perf_universe.py 11500 --encrypt
```

Gemessen am 13.10.2026 mit Version 1.1.0 (sechs Börsen in USD, EUR, GBp, HKD, AUD und JPY, synthetische Wechselkurse):

| Messgröße | Wert |
|---|---|
| Instrumente × Zeiträume | 11.500 × 90 = 1.035.000 |
| Rechenkern (alle Fenster, elf Gewichtungen, Ø Tagesumsatz, beide Rendite-Ranglisten, Häufigkeiten) | 56,0 s (1.0.0: 42,6 s) |
| Veröffentlichung (verschlüsselt) | 70,1 s, 11.684 Dateien |
| Größe eines Datenstands | 96,7 MB (Fenster 63,3, Kursreihen 32,3, Übrige 1,1); 1.0.0: 74,0 MB – mehr vor allem durch Start- und Endkurs je Aktie und Zeitraum |
| Höchster Arbeitsspeicher | 423 MB |
| Vergleichsfelder bei 30 Tagen | V = 10.804, U = 5.240, V ∩ L = 2.170 |
| Ø Tagesumsatz bestimmt / mindestens 10 Mio. USD | 11.500 / 2.315 |
| Gesamtdauer des Skripts | 129 s |

Nicht enthalten ist der Kursabruf über das Netz (eine Anfrage je Notierung, gedrosselt auf 2,5 je Sekunde, rechnerisch gut eine Stunde für 10.000 Notierungen) – er war hier nicht messbar.

Hochrechnung (nicht gemessen): Die DEMO-Datenbank belegt rund 110 Byte je Tageskurs einschließlich Indizes. Bei 11.500 Notierungen und 250 Tagen Aufbewahrung (≈ 175 Börsentage) wären das etwa 220 MB, komprimiert und verschlüsselt etwa 80 MB je Sicherung.

## 7. In GitHub Actions ausgeführt (13.10.2026)

Ergebnisse stehen als Hinweise in der Übersicht des jeweiligen Laufs (Actions → Lauf öffnen).

### Workflow „Prüfung“

13 Läufe am 13.10.2026. Die ersten beiden scheiterten, weil `reportlab` (für den PDF-Rundlauftest) in `requirements-dev.txt` fehlte; seit der Korrektur um 10:58 Uhr sind alle 11 Läufe grün. Letzter Lauf vor 1.1.0 (12:39 Uhr, Commit e3cb48e): `npm ci` ohne Rückfall, Typprüfung und App-Tests bestanden, `app/dist` identisch mit dem Build auf GitHub, **185 Tests bestanden (5 Live-Tests übersprungen)**, echte Börsenkalender `exchange_calendars`: **4 von 4 bestanden**.

### Workflow „Datenquellen prüfen“ (12:02 Uhr)

| Prüfung | Ergebnis |
|---|---|
| TR-Instrumentenliste | bestanden: 11.560 ISINs im Aktienabschnitt, 0 ungültige, 0 doppelte, 1 Fortsetzungszeile; PDF 757.736 Byte, Stand 12.10.2026 08:06 Uhr; Apple, SAP, Deutsche Telekom gefunden |
| OpenFIGI | bestanden: Apple und SAP je 8 unterstützte Notierungen |
| Yahoo Tageskurse und ISIN-Suche | bestanden: AAPL 31 Tageskurse bis 12.10.2026; ISIN-Suche findet AAPL |
| Yahoo Stichtagskurs je Börse | **fehlgeschlagen:** Schlusskurs vom 12.10.2026 fehlt bei allen 14 geprüften Börsen in Europa und Asien (Kerze vorhanden, Schlusskurs leer; beide Yahoo-Server, drei Abfragearten; Stundenkerzen vorhanden). Details: 04_Datenquellen_und_Abdeckung |
| EODHD | übersprungen (kein Schlüssel, kostenpflichtig, nicht freigegeben) |
| EZB-Referenzkurse | neu in 1.1 – läuft beim nächsten Start des Workflows |

### Workflow „Täglicher Lauf“

| Start | Art | Ergebnis |
|---|---|---|
| 10:58 Uhr | erster echter Lauf (manuell) | TR-Liste übernommen, Zuordnung der ISINs begonnen (höchstens 4.000 je Lauf), Kurse abgerufen; Status `wartet_auf_provider`: zum Stichtag 12.10. fehlen die Schlusskurse in Europa und Asien → kein Datenstand. Website mit Status bereitgestellt |
| 12:05 Uhr | Lauf mit erneutem Abruf fehlender Stichtagskurse | nach 25 Minuten von Hand abgebrochen, um die App mit Passphrase-Eingabe bereitzustellen |
| 12:39 Uhr | `nur_website` + `zustand_neu_aufbauen` (neue Passphrase) | grün in 41 s: App 1.0.0+0760edab mit neuem Schlüssel online, Zustand leer |
| 12:40 Uhr | voller Lauf mit neuem Schlüssel | lief beim Schreiben dieses Berichts noch (Zuordnung von vorn) |

Die Website `https://szymeklh87-commits.github.io/tr-aktienvergleich/` ist erreichbar und zeigt „Noch kein Datenstand“ mit dem Grund des letzten Laufs. Auf dem echten Galaxy S25+ wurde die Passphrase eingegeben und gespeichert (Bildschirmfoto „Zugangsschlüssel gespeichert“).

## 8. Nicht geprüft (offen)

| Punkt | Grund | Was es abschließt |
|---|---|---|
| Ein veröffentlichter echter Datenstand | Yahoo-Lücke am 12.10.2026; nach dem Schlüsselwechsel beginnt die Zuordnung der 11.560 ISINs von vorn (höchstens 4.000 je Lauf) | erster Lauf mit Status „veröffentlicht“; frühestens mit dem Stichtag 13.10.2026 |
| Beide Rendite-Ranglisten mit echten Daten | wie oben; bisher nur DEMO | erster echter Datenstand; ☰ → Datenstand & Betrieb zeigt Anzahl aufgenommener Aktien und Wechselkursstand |
| EZB-Abruf aus GitHub Actions | Quelle neu in 1.1 | Hinweis „EZB-Referenzkurse“ im Workflow „Datenquellen prüfen“; Zeile „Wechselkurse“ im Laufbericht |
| Prüfung 1.1.0 in GitHub Actions | Ergebnis nach dem Hochladen | grüner Lauf „Prüfung“ für den Commit mit 1.1.0 |
| EODHD | kein Schlüssel; kostenpflichtig | nur nach deiner Freigabe |
| Geplanter Lauf um 06:00 Uhr | bisher nur manuelle Starts | Lauf mit Auslöser „schedule“ am 14.10.2026 |
| Bedienung auf dem echten Galaxy S25+ | bisher nur Passphrase-Eingabe, noch keine Daten | Installation und Durchklicken nach 01_Kurzanleitung_Handy, sobald ein Datenstand da ist |

## 9. Erweiterung 1.1: Prüfungen aus dem Auftrag

| Vorgabe | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Aktie mit hoher Rendite und niedrigem Umsatz erscheint nur in Ranking 1 | `test_turnover.TwoReturnRankingsTests.test_low_turnover_top_return_only_in_ranking_1`; E2E `test_turnover_filter_tab_and_low_turnover_flags` (Kennzeichen „sehr niedriger Umsatz“) |
| Liquide Aktie erscheint in beiden Rankings | `test_liquid_stock_appears_in_both`; Vertrag „Zwei Rendite-Ranglisten“ |
| Fehlende Volumendaten verhindern Ranking 2 (und werden nicht als null gezählt) | `test_missing_volume_or_fx_prevents_ranking_2`, `TurnoverDefinitionTests.test_missing_volume_data_prevents_a_value`, `test_missing_sessions_are_not_counted_as_zero`, `test_reported_zero_volume_counts_as_zero_but_needs_16_positive_sessions` |
| Ohne Wechselkurs keine Aufnahme in Ranking 2, Ranking 1 bleibt | `test_missing_or_stale_fx_rate_prevents_usd_value`, `test_fx_conversion_decides_admission`; Rückfall auf gespeicherte EZB-Kurse: `test_ecb.DailyRunFxTests` |
| Wochenenden und Feiertage verschieben die angezeigten Vergleichsdaten korrekt | `test_weekend_and_holiday_move_start_dates`, `test_weekend_session_uses_previous_ecb_rate`; E2E `test_weekend_start_dates_in_return_rankings` |
| Beide Rankings: gleicher Stichtag, gleiche Formel, gleiche ungerundete Werte | `test_same_cutoff_formula_and_order`; Veröffentlichungsprüfung `ranking2_teilmenge_gleiche_rendite` in jedem Lauf; `test_pipeline.test_T47_overview_windows_series_and_frequency_agree`; Vertrag |
| Bestehende Qualitätsregeln gelten weiter | `test_existing_quality_rules_still_apply_to_ranking_1` |
| Kapitalmaßnahmen verzerren den Umsatz nicht | `test_split_inside_the_20_sessions_is_not_distorting_the_value` |
| Übernahmesprünge werden gekennzeichnet | `TakeoverPatternTests` (4 Tests) |
| Darstellung: Sieger → Top 10 → vollständige Liste, getrennte Zählungen | E2E `test_return_rankings_winner_top10_and_full_list`, `test_detail_shows_turnover_and_both_return_ranks` |
| Häufigkeit nennt Universum und Umsatzfilter, keine Vermischung | E2E `test_frequency_names_universe_and_turnover_filter`; Vertrag „Häufigkeit mit Umsatzfilter“ |
| Auffällige Kursabweichungen zwischen Börsenplätzen | **noch nicht umgesetzt** (09_Bekannte_Luecken) |

## 10. Abnahmetests T01–T100: Zuordnung

„E2E“ = Browser-Emulation (Abschnitt 3), „Vertrag“ = App-Datenvertragstest (Abschnitt 2). Alle genannten Tests liefen am 12. und erneut am 13.10.2026 (Version 1.1.0) und waren grün, sofern nicht anders vermerkt.

| Test | Nachweis |
|---|---|
| T01, T02, T05, T07, T10, T11 | `test_metrics`: test_T01…, test_T02…, test_T05…, test_T07…, test_T10…, test_T11… |
| T03, T21–T24, T27, T28 | `test_windows`: je ein gleichnamiger Test; T21 zusätzlich `test_quality.test_window_lengths_above_90_are_rejected_in_core` |
| T04 | `test_quality.test_T04…`; E2E `test_ranking_window_weight_and_empty_reason` |
| T06 | `test_metrics.test_T06…` (R² ≈ 1) und `test_quality.test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings` |
| T08, T09, T29–T33, T35 | `test_quality`: gleichnamige Tests (T29 und T32 je zwei) |
| T12–T20 | `test_ranking`: gleichnamige Tests; T20 zusätzlich Vertrag (Untergruppe) und E2E Watchlist-Untergruppe |
| T25 | `test_windows.test_T25…` (Feiertage je Börse), `test_providers.DaylightSavingTests` (Sommerzeitwechsel USA/Europa); echte Kalender: `tests.live.test_calendars_live` in GitHub Actions, 4 von 4 bestanden (Abschnitt 7) |
| T26 | `test_providers.test_T26_running_session_does_not_replace_final_close`, `test_T26_session_final_checker` |
| T34 | `test_providers.test_T34_dividend_adjusted_close_is_kept_separate` |
| T36 | `test_providers.test_country_preference_and_T36_one_reference_per_isin`, `test_frequency.test_T88_duplicate_isin_listings_are_rejected_upstream` |
| T37 | `test_pipeline.test_T37_ticker_change_keeps_name_isin_and_one_ranking_entry` |
| T38, T40 | `test_engine_coverage`; T40 zusätzlich `test_pipeline.test_idempotent_rerun_creates_no_second_snapshot` |
| T39 | `test_metrics.test_T39…` (exakte Bruchrechnung, `numpy.polyfit`); Vertrag: App-Scores bitgleich |
| T41 | `test_pipeline.test_T41_T60…`, `test_ci_flow`; echte Läufe in GitHub Actions am 13.10.2026 manuell gestartet (Abschnitt 7) – der erste geplante Lauf um 06:00 steht noch aus |
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
