# Gesamtauftrag – Umsetzungsstand (Fortschrittsdatei und Anforderungsmatrix)

Fortschrittsdatei zum Auftrag [`13_AktienPilot.md`](13_AktienPilot.md) (Gesamtfassung 31.10.2026, Abschnitte 0–32 und 7A).
Entscheidungen: [`13_AktienPilot_Entscheidungen.md`](13_AktienPilot_Entscheidungen.md). Kennzahlen und Doppelungen:
[`15_Kennzahlen_und_Doppelungen.md`](15_Kennzahlen_und_Doppelungen.md). Die Datei wird nach jedem Arbeitsschritt fortgeschrieben
und mit dem Code eingecheckt.

**Statuswerte (Abschnitte 2 und 28.4):** offen · in Arbeit · implementiert/ungeprüft · offline geprüft (automatische Tests mit
synthetischen bzw. DEMO-Daten) · mit echten Daten geprüft (dokumentierter Lauf mit echten Daten, der genau diese Anforderung
geprüft hat) · extern blockiert · ausdrücklich ersetzte Altvorgabe · reine Echtgeld-Zukunftsspezifikation.

## Arbeitsstand

| | |
|---|---|
| Branch | `gesamtauftrag` (Integration von `aktienpilot` und `aktualisierung`, beide erhalten; `main` unverändert, App 1.20.3) |
| Letzter Stand | 31.10.2026: Gesamtfassung abgelegt; Kennzahlenkatalog, Regel-Baukasten (Prüfung, Auswertung), Gewinnmitnahmen, Simulator, Spielgeld-Motor, Speicherung und Vorlagen S1–S3/Lineal/Beispielregeln mit 49 Tests; 649 Unit-Tests grün |
| Nächster Schritt | Motor in den täglichen Lauf (Kursreihen der Leitindizes und Kern-ETFs, Ranglistenarchiv, verschlüsselte Veröffentlichung), danach App-Bereich „Autopilot – Spielgeld“ mit Regel-Editor, dann sicherer Ereignisweg |
| Läuft im Hintergrund | nichts |

## Auftragsablage (Abschnitt 2)

| Prüfung | Ergebnis |
|---|---|
| Datei | `docs/13_AktienPilot.md`, byte-gleich mit der Anlage vom 31.10.2026, 14:06 Uhr |
| Größe | 205.918 Bytes, 201.982 Zeichen, 1.134 Zeilen |
| SHA-256 | `1ed8549ceeae0ec5cf2556632b66af37d384204635cf239b7581094cec3ebf75` |
| Abschnitte | 0–32 und 7A im Inhaltsverzeichnis und im Text vorhanden (automatisch geprüft) |
| Endmarkierung | „ENDE DES VOLLSTÄNDIGEN AUFTRAGS – HAUPTABSCHNITTE 0–32 PLUS 7A – … – FASSUNG 31.10.2026“ vorhanden |
| Erste Übertragung 13:57 Uhr | 130.502 Bytes (genau 128.000 Zeichen), SHA-256 `6036c9c3…7f11`, endete mitten in 26.10; Byte für Byte der Anfang der Gesamtfassung – nicht gesondert abgelegt, keine Auftragsgrundlage |
| Vorige Fassungen | `13_AktienPilot_Fassung_2_2026-10-31_1236.md` (50.593 Bytes, SHA-256 `811fec14…`, Abschnitte 0–23); `13_AktienPilot_Fassung_1_unvollstaendig.md` (abgeschnitten in Abschnitt 5) |

## Anforderungsmatrix (Abschnitt 28.4)

Spalten: ID · Anforderung (Abschnitt) · Status · Umsetzung · Testbeleg · offene Lücke. Grundlage: Bestandsaufnahme am
31.10.2026 (nur lesend, Integrationsstand `768277d`), danach mit jedem Schritt fortgeschrieben.

| ID | Anforderung | Status | Umsetzung | Testbeleg | Offene Lücke |
|---|---|---|---|---|---|
| A01 | TR-Universum, historische Zuordnungen (5) | mit echten Daten geprüft | `providers/tr_universe.py`, `identity.py`, `openfigi.py`; Tabellen `universe_*`, `instrument_alias` | `test_providers::test_real_pdf_roundtrip`; Live `test_tr_universe_pdf` (11.596 ISINs) | Indexfilter, Universums-CSV, Historie erst ab 12.10.2026 |
| A02 | Abdeckung, Ausschlussgründe (5) | offline geprüft | `analytics/coverage.py`, `codes.py`; Ansichten Aktien, Status | `test_engine_coverage::test_T38…` | Handelsfilter (Mindestkurs/-umsatz) für den Robo; Abdeckungs-Export |
| A03 | Börsenkalender, FX (7) | mit echten Daten geprüft | `providers/calendars.py`, `ecb.py`, `analytics/fx.py` | `test_ecb`, `test_windows::test_T25…`; Live Kalender und EZB | TWD/CLP ohne EZB-Kurs; Schwesterkalender |
| A04 | Kursabgleich, Splits (28.3) | mit echten Daten geprüft | `analytics/kursabgleich.py` (kursabgleich-1.2), `jobs/kursabgleich_lauf.py` | `test_kursabgleich` (28), `test_kursabgleich_pipeline`; Prüfstatus 31.10. Nr. 2 | Platz 1 in 851/1.980 Ranglisten ohne amtlichen Abgleich (teils extern blockiert) |
| A05 | Provenienz, Quellenfehler (7) | mit echten Daten geprüft | `bar_revision`, `kurskorrektur`, `quality.py` | `test_kurse_ursachen` (52) | 95 von 141 US-Aktientagen ungeklärt |
| A06 | Lineal-Fenster 1–90 (25.2) | mit echten Daten geprüft | `analytics/windows.py`; Fensterwahl | `test_windows::test_T21…`; Nachrechnung 10.016.002 Prüfungen | – |
| A07 | Elf Gewichtungen (25.4) | mit echten Daten geprüft | `analytics/ranking.py`; Ranking, Gewichtungsvergleich | `test_ranking::test_T80…`, `test_T18…` | common_trend nicht nachgerechnet |
| A08 | Umsatzgruppen A/B (6) | mit echten Daten geprüft | `analytics/turnover.py`, `ranking.py::group_b_ranking` | `test_turnover`, Vertragstest | TWD/CLP nie in B |
| A09 | Reine Renditeranglisten (25.2) | mit echten Daten geprüft | `frequency.py::build_pure_return_winners`; Rendite-Ansicht | `test_ranking::test_T81…`, Vertragstest T94 | „Heute/Tages-Top“ mit Intradaydaten fehlt |
| A10 | Langfrist 1–10 Jahre (25.3) | offen | nur Kursverlauf bis „Max“ | – | Auswertungen 1–10 Jahre, Sitzungsmodus, Gesamt-/annualisierte Rendite |
| A11 | Häufigkeiten Platz 1/Top 3/Top 10 mit Nenner (25.5) | mit echten Daten geprüft | `frequency.py::aggregate_frequency`, `lib/frequency.ts` | `test_frequency::test_T90…`, Vertragstests T92/T93 | common_trend nicht nachgerechnet; v2 nur in TS |
| A12 | Einzelcharts (25.6) | offline geprüft | `DetailView.tsx`, `charts.tsx::PriceChart` | `test_mobile_app::test_detail_chart_tooltip_and_png` u. a. | „Als Regel verwenden“; Historie > 1 Jahr |
| A13 | Chart-Raster Modus A (25.7) | offline geprüft | `GridView.tsx` (Kacheln) | `test_mobile_app::test_chart_grid_modes_and_png` | nicht an „Jetzt aktualisieren“/sichtbare Aktien gebunden |
| A14 | Aktien × Zeiträume Modus B (25.7) | offline geprüft | `GridView.tsx` (Zeiträume) | `test_T64…`, `test_T66_T69_T70…` | höchstens 8 Spalten, kein Blättern |
| A15 | Normierter Mehraktienvergleich (25.8) | offline geprüft | `compare.tsx::CompareBlock`, `CompareChart` | `pure.test.ts` T67 | höchstens 8 statt 10 Linien |
| A16 | Gleiche vs. ursprüngliche Auswahl (25.4) | offline geprüft | Politik native/common_trend | `test_ranking::test_T16…`, `test_T84…` | common_trend nicht mit echten Daten nachgerechnet |
| A17 | Merkliste, Suche, Filter (25.9) | offline geprüft | `WatchlistView.tsx`, `lib/search.ts` | `test_watchlist_*`, `pure.test.ts` T50 | Kurzfassung je Titel, Screening-Ereignisse |
| A18 | Exporte (25.9) | offline geprüft | `lib/csv.ts`, `lib/exportpng.ts` | `pure.test.ts` T54, `test_ranking_csv_export_is_excel_safe` | echtes .xlsx; Abdeckungs-Export |
| A19 | Rückblickende Zehnerdepots (25.10) | offline geprüft | `DepotsView.tsx`, `lib/depots.ts` | `depots.test.ts` | Referenz 30.10. fehlt; nur Kursrendite |
| A20 | Vorwärts laufende Musterdepots (25.10) | in Arbeit | Vorlage `vorlagen.lineal` als Regel, Forschungsdepot im Motor | `test_aktienpilot_regeln::test_all_templates_are_valid_rules` | Tageslauf, Anzeige |
| A21 | Vergleichsdepots getrennt vom Pilotdepot (29.6) | in Arbeit | `motor.DepotDef` (pilot, forschung, vergleich), eigene Guthaben und Bezugsgrößen | `test_aktienpilot_motor::KernTests`, `SchutzTests` | Tageslauf, Anzeige |
| A22 | Spielgeld-Autopilot (29) | in Arbeit | `aktienpilot/motor.py` (Tagesschritt), `ausfuehrung.py` (Simulator), `speicher.py`; automatische Käufe/Verkäufe/Stops/Gewinnmitnahmen, Journal mit Begründung auch für „nicht gehandelt“ | `test_aktienpilot_motor` (17 Tests: Zeitregel, Kosten, Lücke, Stops, Pause, Verluststufe, Kern, Neustart, kein Echtgeld) | Tageslauf, App-Bereich, Einrichtung (fünf Fragen), Reset/neuer Test in der App |
| A23 | Vor-Ausbruch (26.2) | offen | nur Signal-Komponente „ausbruch“ | – | Screening-Modul mit Zuständen |
| A24 | Positiver Ausbruch (26.2) | offen | Katalog: `ausbruch_hoch`, `abstand_hoch` (Tagesschluss) | – | Bestätigungsregel, Zustände, Journal |
| A25 | 5-/15-Minuten-Volumensprung (26.3) | offen | Katalog: Tages-`volumenfaktor` (ausdrücklich kein Intradayfaktor) | – | Intraday-Volumenreihen (kostenlose Quelle prüfen) |
| A26 | Seitwärtsbasis (26.4) | offen | – | – | Modul |
| A27 | Nachrichten, Fundamentaldaten (26.6) | offline geprüft | `jobs/facts.py`, `signals.py` | `test_signals::test_news…` | IR-/Registerquellen, Negativfilter mit drei Zuständen |
| A28 | Analystenziele (26.8) | offline geprüft | `signals.py::target_sources`; Katalog `kursziel_abstand` (nur gleiche Währung) | `test_signals::test_pence_targets…` | Median; Beschriftung „Abstand zum Analystenziel“ statt „Prognose“ |
| A29 | Prognosehorizonte, Güteprüfung (26.9) | offen | nur `signals.py::calibrate` | – | Horizonte, Out-of-Sample gegen Baseline |
| A30 | S1 Momentum (8) | offline geprüft | Vorlage `vorlagen.s1` (Log-Regression, Perzentil-Score, MA100, Lücke, Rangpuffer, wöchentlich, 2×ATR) | Vorlagentest, Motor-Durchlauf | Backtest-Labor, echte Daten |
| A31 | S2 Breakout (9) | offline geprüft | Vorlage `vorlagen.s2` (55-Sitzungen-Hoch, Volumen 1,5×, Trailing 3×ATR, nie nach unten) | `test_trailing_stop_never_moves_down` | Backtest, echte Daten |
| A32 | S3 Mean-Reversion, Marktfilter (10) | offline geprüft | Vorlage `vorlagen.s3`; Katalog `marktfilter` (ohne Indexdaten nicht prüfbar) | `test_market_filter_without_index_is_not_checkable` | Leitindex-Kurse im Tageslauf laden |
| A33 | S4 Robo-Kern (11) | in Arbeit | `motor._kern` (Zielaufteilung, zuerst Guthaben, Schwelle 5 pp, durch den Risiko-Manager) | `KernTests` | Fragebogen, Sparplan-Rechner, ETF-Kurse im Tageslauf |
| A34 | Regel-Baukasten mit UND/ODER und Gewinnleitern (27.4, 31) | in Arbeit | `aktienpilot/regeln.py` (Schema `tr-regel/1`, Prüfung, Versionen, Kopie), `auswertung.py` (dreiwertig, Quellen, Sortierung, Score, Auswahl, Ausstiege) | `test_aktienpilot_regeln` (20 Tests) | Editor in der App, Vorschau, Historientest, Übertragung vom Handy |
| A35 | S5 kostenlose KI-Prüfung (12, 27.5) | offen | – | – | Prüfung kostenloser Modelle (P7, Standard aus) |
| A36 | Ausführungsprofile (13) | offline geprüft | `zeitregel.py`; Motor führt nur nach der Veröffentlichung aus | `test_buys_after_publication_at_next_close_with_costs` | – |
| A37 | Zentraler Risiko-Manager (15) | offline geprüft | `risiko.py::size_buy` für jeden Kauf (auch Kern), `check_sell` | `test_central_risk_limits_bind_every_buy` | – |
| A38 | Budget-, Branchen-, Positionsgrenzen (15) | offline geprüft | `size_buy`; Reservierungen depotweit (`motor._Lauf.exposure`) | Motor-Tests | Branchenquelle im Tageslauf (Stammdaten) |
| A39 | Verluststufen, Not-Aus (16) | in Arbeit | `LossLimits`; Stufe „schließen“ verkauft aktive Positionen, Kern bleibt | `test_close_stage_sells_active_positions_but_never_the_core` | Not-Aus-Aktionen in der App, Ereignisweg |
| A40 | Kosten und Währungen (14) | offline geprüft | `kosten.py`, Simulator (Spread, Slippage, FX, TR-Aufschlag, Gebühr) | Motor-Tests | 1-EUR-Gebühr gegen aktuelles TR-Preisverzeichnis belegen |
| A41 | Backtest, Walk-Forward (14) | offen | Motor ist für Backtests nutzbar (gleicher Code, Modus „historische Simulation“) | – | Labor mit Walk-Forward, Prüfzeitraum, Bericht |
| A42 | Benchmark und Berichte (29.6) | in Arbeit | Vergleichsdepot „Welt-ETF kaufen und halten“ (`KernDef`, nur Zuflüsse) | `test_buy_and_hold_benchmark_invests_once` | ETF-Kurse, Bericht, Dashboard |
| A43 | Anfangsbestand, Fremdbewegungen (17) | in Arbeit | `buchhaltung.py` (anfangsbestand, umbuchung, korrektur, extern) | – | Eingabe, Import, Tests |
| A44 | Verschlüsselter Bestätigungsweg (4, P5) | offen | Planung: privates Daten-Repository mit Weiterleitung (Entscheidung E-20) | – | Umsetzung, Nachweis der Rechte und Limits |
| A45 | Journal, Teilfüllungen, Stops (18, 19) | offline geprüft | Ereignisjournal, Teilausführung (Guthaben/Volumen), Stops mit Lücke, Journal je Entscheidung | Motor-Tests | Journal-Ansicht |
| A46 | Steuer, FIFO, CSV/Excel (21) | in Arbeit | FIFO-Lose in `buchhaltung.py` | – | Steuermodell, Export |
| A47 | ntfy (20) | offen | Konfiguration | – | Versand, Limits |
| A48 | Optionaler Dienst, Telegram, Alpaca Paper (27.3, 27.6) | offen | – | – | P7 |
| A49 | Jetzt aktualisieren für Aktie/Depot/Universum (7A) | offline geprüft | `jobs/kursaktualisierung.py`, `aktualisieren.yml`, `UpdateState.tsx` | `test_kursaktualisierung`, `test_aktualisieren_app`; Backend in GitHub Actions gemessen (Lauf 41201893346) | Handy-Zugang mit „Actions: Schreiben“ ersetzen (7A.5), keine erfundenen Prozentwerte, Wischgeste, Mehrfachtippen, nach main-Freigabe Ende-zu-Ende |
| A50 | Automatik bei geöffneter App (7A.7) | offline geprüft | `aktualisierung.ts::autoDue` | `aktualisierung.test.ts` | Börsenkalender statt grober Handelszeiten |
| A51 | Kurszeit, Abrufzeit, Verzögerung (7A.3) | offline geprüft | `lib/livekurse.ts`, `refresh.tsx` | `aktualisierung.test.ts`, `test_quote_response_reports_delay_and_market_state` | Vor-/Nachbörse, Kursart |
| A52 | Offline, Cache, Service Worker (7A.6) | mit echten Daten geprüft | `sw.ts` | `test_offline_*`; Emulator-Neustart im Flugmodus | echtes S25+ |
| A53 | Mobil/PC, Zugänglichkeit (24) | offline geprüft | Ansichten, `styles.css` | `test_touch_targets_are_at_least_44px` u. a.; 25/25 Ansichten in 3 Browsern | Bestandsaufnahme und Protokoll nach 24 |
| A54 | Sicherheit, Verschlüsselung, Schlüssel (3, 4) | mit echten Daten geprüft | `util/crypto.py`, `container.ts`, `keystore.ts` | `test_T52_no_secrets…` | Token-Rechte (A49/A44), Schlüsselrotation |
| A55 | Ausfallsicherheit, Sperren, Idempotenz (18) | in Arbeit | Ranglisten: geprüft; Robo: ein Stichtag je Depot genau einmal (`letzter_tag`, `ap_tageslauf`) | `test_same_day_is_processed_only_once`, `test_restart_from_database_gives_same_result` | Sperren im Tageslauf |
| A56 | Migration, Backup, Wiederherstellung (18) | in Arbeit | Migration 0010 neu gefasst (Echtgeld per CHECK ausgeschlossen) | `test_database_rejects_real_money_modes` | Wiederherstellung aus echtem Release |
| A57 | Messbare Effizienzverbesserung (7A.8, 24.7) | in Arbeit | Messungen `docs/14` | `test_speed` | Nachher-Messungen, Budgets |
| A58 | Tests, Golden Master, Browser (23) | in Arbeit | 649 Unit-Tests (davon 49 AktienPilot) | Lauf vom 31.10.2026 | Golden Master auf festem Stand (Referenz 30.10. fehlt) |
| A59 | start.bat, Anleitung (23) | offen | – | – | start.bat, Anleitung Spielgeld/Regeln |
| A60 | Nullkosten, vollständige Lieferung (0) | in Arbeit | `ap/config.py` sperrt kostenpflichtige Anbieter | – | EODHD im Tageslauf noch über `pipeline.yaml` aktivierbar – sperren |
| A61 | Gemeinsame Kennzahlenregistrierung (31.8, 32) | in Arbeit | `aktienpilot/katalog.py` (58 Kennzahlen, Lineal-Werte aus dem Rechenkern, Häufigkeit über dieselbe Funktion) | `test_aktienpilot_katalog` (12 Tests) | Signale/Fundamentaldaten, `app/src/generated/katalog.json`, Zuordnungsliste |
| A62 | Eigene Rang-/Rendite-/Gleichmäßigkeitsauswahl (31.2–31.4) | in Arbeit | Quellen Rangliste (Variante A), Häufigkeit, Universum, ISIN-Liste; Variante B über `ap_rang_archiv` | `test_candidate_union_counts_each_isin_once_with_its_findings` | Archiv füllen, Editor |
| A63 | Gewinnmitnahmen +30/+50/+100 %, eigener Wert, Teilverkäufe (31.7) | offline geprüft | `gewinnziel.py` (nach Kosten oder Kurs, ganz/Anteil/Stück, Leiter ursprünglich/verbleibend), Motor | `GewinnmitnahmeTests`, `test_ladder_sells_each_stage_once_from_position_gain` | Editor, Ergebnisse je Schwelle |
| A64 | Doppelungen vermeiden (32) | in Arbeit | Verzeichnis `docs/15_Kennzahlen_und_Doppelungen.md`; ein Regelmotor für Vorlagen und eigene Regeln | – | Bereinigung der offenen Punkte |

### Weitere belegte Anforderungen (Programmierauftrag v1.2 und spätere Aufträge)

| ID | Anforderung | Status | Beleg / Lücke |
|---|---|---|---|
| Z01 | Täglicher Serverlauf ohne Handy, begrenzte Wiederholungen | mit echten Daten geprüft | Prüfstatus 31.10. Nr. 4; GitHub-Zeitpläne teils stark verspätet |
| Z02 | Herzschlag und Problemstatus | offline geprüft | `test_T56_stale_heartbeat_is_shown_as_gap` |
| Z03 | Frühere Stände wählbar, append-only | mit echten Daten geprüft | Website hält nur 3 Stände |
| Z04 | Datenvertrag | offline geprüft | AktienPilot-Daten noch nicht im Vertrag |
| Z05 | Alle Ansichten an einen Stand gebunden | offline geprüft | `test_T47…`, `test_T46…` |
| Z06 | Installierbare PWA | mit echten Daten geprüft | echtes S25+ offen |
| Z07 | Kein Auftritt als TR-Produkt, keine Versprechen | implementiert/ungeprüft | Hilfetext „kann keine Aktien kaufen oder verkaufen“ für den Spielgeld-Robo anpassen |
| Z08 | DEMO-Kennzeichnung | offline geprüft | Trennung PAPER/DEMO/historische Simulation in der App ergänzen |
| Z09 | Altbestand 12.10.2026 übernehmen | extern blockiert | Dateien nie geliefert |
| Z10 | Methodenvergleich mit dem Ausgangsmodell | mit echten Daten geprüft | Referenz 30.10. fehlt |
| Z11 | Anbietermatrix mit Live-Stichprobe | mit echten Daten geprüft | EODHD ungeprüft (kostenpflichtig) |
| Z12 | Abhängigkeiten festlegen | implementiert/ungeprüft | kein Python-Lock |
| Z13–Z20 | Keine Prognosen; keine Orders; keine Intraday-Alarme; FastAPI/PostgreSQL; Start 06:00; 98 %/80 %; strenger Stichtag; alte Schnellwahl | ausdrücklich ersetzte Altvorgabe | ersetzt durch 26.9, 29.1, 26.3/26.7, 24.1/27.3, 07:00-Lauf, tr-methode-1.8.0, 1.9.0, Auftrag 13.10. (80-%-Volumenregel bleibt Teil von 1.10.0 – Konflikt mit 25.1 dokumentiert, nicht still geändert) |
| Z21 | EUR-Gesamtrendite mit historischem FX | offen | – |
| Z22 | Rangänderung zum Vortag | offen | bewusst nicht angezeigt; Variante B schafft das Archiv |
| Z23 | Potenzial/Gesamtwertung, Daytrader-Check, Top nach Zahlen, Umschichtungs-Regel, Bericht 1–30, Zwischenstand (spätere Aufträge) | mit echten Daten geprüft bzw. offline geprüft | eigene Zeilen in der Endfassung |

## Externe Voraussetzungen und Grenzen

| Funktion | Grenze | Kleinster nötiger Schritt |
|---|---|---|
| Vorwärts-PAPER mit echten Kursen | läuft erst nach Freigabe des Merge in `main` im täglichen Lauf; vergangene Sitzungen lassen sich nicht nachholen | Freigabe der geprüften Lieferung |
| Regeln, Einrichtung und Pause vom Handy | sicherer Ereignisweg braucht ein privates Daten-Repository und zwei feingranulare Token (Einrichtung durch dich) | Anleitung in der App, Nachweis der Rechte |
| Referenzprüfung 30.10.2026 | Originaldaten fehlen | Datei nachreichen |
