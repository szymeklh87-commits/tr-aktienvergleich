# Testbericht – tatsächlich ausgeführt

Stand **14.10.2026, 09:55 Uhr (Europe/Berlin)**, Software **1.8.2** (Abschnitt Überblick, erste Zeilen); ältere Abschnitte: Software **1.5.2**, Methode **tr-methode-1.8.0** (1.5.2: Börsenplatz-Abgleich nur mit Kursen mit Umsatz und Schwelle nach Tagesschwankung; 1.5.1: fehlende Börsentage beim Kursanbieter, Börsenplatz-Abgleich nur mit Kursen desselben Tages, verständlicher Teilstand; 1.5.0: Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“: Regeln des Ausgangsmodells, feste Schnellwahl 7–90 Tage, Sieger nach Zeitraum, Matrix 1–90, Häufigkeit mit Filtern; dazu alles aus 1.1–1.4). Ausgeführt wurde an zwei Orten:

- **Entwicklungsumgebung** (12.10.2026 22:30 Uhr bis 13.10.2026 22:30 Uhr): alle Tests mit synthetischen DEMO-Daten. Externe Datenquellen waren von hier aus nicht erreichbar.
- **GitHub Actions** (seit 13.10.2026): Workflow „Prüfung“ bei jeder Änderung, Workflow „Datenquellen prüfen“ mit den echten Quellen und die ersten echten täglichen Läufe (Abschnitt 7).

Alle Zahlen unten stammen aus diesen Läufen. Was nicht prüfbar war, steht ausdrücklich unter „Nicht geprüft“ (Abschnitt 8) – es gilt als offen, nicht als bestanden. Die Uhrzeiten sind deutsche Zeit (MESZ); GitHub zeigt UTC (zwei Stunden früher).

## Überblick

| Wo | Was | Ergebnis |
|---|---|---|
| Entwicklungsumgebung, 14.10.2026 09:40–09:55 Uhr | **Version 1.8.2** (Gesamtwertung im Bericht 1–30) und erweiterte Live-Prüfung | Python: 270 Unit-Tests, Datenvertragstest der App; App: Typprüfung, **59 Tests** (45 bestanden, 14 Datenvertragstests über Python; neu: Gesamtwertung je ISIN nur ab `signale-v2`, kein Ersatzwert aus älteren Ständen), Build 1.8.2; **56 Browser-Tests** bestanden (Bericht-Test erweitert: Kästchen hinter dem Spitzenreiter = Gesamtwertung aus dem Signal-Stand, gerundet wie in der App). Live-Prüfung der App (`tests/live/test_app_live.py`) lokal gegen die DEMO-Website: 7 von 7 Prüfungen, 20 von 20 Ansichten ohne Fehler, Bericht 1–30 mit 4 Tabellen und 30 Matrixzeilen, Einzelansicht mit Gesamtwertung und 11 Daytrader-Punkten |
| Entwicklungsumgebung, 14.10.2026 09:10–09:35 Uhr | **Version 1.8.1** (Bericht 1–30 Tage) | Python: **270 Unit-Tests** und **50 Integrationstests** bestanden; App: Typprüfung, **58 Tests** (44 bestanden, 14 Datenvertragstests über Python; neu: 4 – Spitzenreiter 1–30 je Gruppe mit Wiederholungen je Spalte, leere kurze Zeiträume nur bei gleichem Grund in A und B zusammengefasst, Matrix mit vier Gewichtungen und Zählung über A und B, Einstieg in den Kursverlauf, Kennzahlen, CSV mit 240 Zeilen), Build 1.8.1; **56 Browser-Tests** bestanden (neu: Bericht 1–30 – Einstieg von der Startseite, vier Tabellen, jede Zelle = Platz 1 der Übersicht des Stands in A und B, zusammengefasste Zeilen nur bei wirklich leeren Zeiträumen, Kursrendite wie in der Fensterdatei, eine Gewichtung allein, Matrix A und B ohne seitliches Wischen, „Am häufigsten auf Platz 1“ = Nachzählung, Hervorheben mit der richtigen Zahl umrahmter Zellen und „Nächstes Vorkommen“, Markierung entfernen, Häufigkeit, CSV mit 240 Zeilen; Bericht auch in der Prüfung der Mindestgröße von Bedienelementen und der Beschriftungen) |
| Entwicklungsumgebung, 14.10.2026 08:45–09:05 Uhr | **Version 1.8.0** (Zwischenstand mit aktuellen Kursen) | Python: **270 Unit-Tests** (neu: 7 – begonnene Sitzungen je Börse, Wahl des Stichtags mit Mindestanteil und Lückenregel, Ø Tagesumsatz ohne den laufenden Tag bei gleicher Rendite, Archivnamen) und **50 Integrationstests** bestanden (neu: 7 – Zwischenstand mit vorläufigen Kursen, die nie gespeichert werden; US-Aktien vor Börsenbeginn „Kurs am Stichtag fehlt“; Status und Index; neuer Zwischenstand ersetzt den alten samt Archiv; offizieller Stand löst ihn ab; vor Börsenbeginn „keine neuen Daten“; zu wenige Kurse; `demo --zwischenstand`; `ci --zwischenstand` gegen die nachgebildete GitHub-API mit Aufräumen alter Archive im Release); App: Typprüfung, 54 Tests (40 bestanden, 14 Datenvertragstests über Python), Build 1.8.0; **55 Browser-Tests** bestanden (neu: 3 – Zwischenstand oben mit Kennzeichnung und Wechsel zum offiziellen Stand und zurück, Einzelansicht „(vorläufig)“, Status und Umschichtungs-Regel, Anleitung „Jetzt aktualisieren“). Dabei gefunden und behoben: beim Wechsel zwischen Ständen kurz ein 404 für die Umschichtungs-Regel des neuen Stands; eine CSS-Klasse des Daytrader-Checks überschrieb Ankreuzfelder |
| Entwicklungsumgebung, 14.10.2026 08:30–08:40 Uhr | **Version 1.7.1** (Daytrader-Check, „Was die Analysten denken“, Dafür/Dagegen) | App: 50 Tests (36 bestanden, 14 Datenvertragstests über Python; neu: Analysten-Text mit Richtung, Spanne, Quellen, Urteilen, Bewertung und Prognose; Dafür/Dagegen mit überkauftem RSI immer „dagegen“; Daytrader-Check mit Werten, Urteil je Punkt, relativer Stärke und Zählung), Build 1.7.1; Browser-Test der Einzelansicht erweitert (Daytrader-Check mit mindestens 11 Punkten und Erklärung, Analysten-Text, Dafür/Dagegen) |
| Entwicklungsumgebung, 14.10.2026 08:15–08:25 Uhr | **Version 1.7.0** (Gesamtwertung: Steig-Konstanz 30/60/90 Tage, Kursziel-Potenzial, Trefferquote der Steig-Konstanz) | Python: **262 Unit-Tests** (neu: 7 für Steig-Konstanz, Kursziel-Kurve und Gesamtwertung – stetiger Anstieg vor kurzem Schub, ohne Kursziel 0 Punkte, Zufallskurs nur mittlere Konstanz) und **43 Integrationstests** bestanden (Signal-Stand mit Gesamtwertung, Liste nach Gesamtwertung absteigend, neuer Stand bei älteren Rechenregeln); App: Typprüfung, 47 Tests (33 bestanden, 14 Datenvertragstests über Python; neu: Liste „Gesamt“ mit Rückfall für alte Stände, Steig-Konstanz je Zeile, Aufschlüsselung und Trefferquote), Build 1.7.0; **52 Browser-Tests** auf simuliertem S25+ bestanden (neu geprüft: Liste „Gesamt“ absteigend sortiert, Streifen „30 T ▲…“, Abschnitt Gesamtwertung mit vier Teilen, Tabelle und Erklärung) |
| Entwicklungsumgebung, 14.10.2026 07:40–07:50 Uhr | **Version 1.6.0** (Potenzial, Signale, neue Struktur; 1.5.4 Schlusskurs aus Kursmeldung) | Python: 255 Unit-Tests und 43 Integrationstests bestanden (darunter 14 neue Signal-Tests, 7 Ablauf-Tests für Kennzahlen und Signal-Stand, 5 Tests für den Schlusskurs aus der Kursmeldung, 6 für Kursziele/Crumb); App: Typprüfung, 45 Tests (31 bestanden, 14 Datenvertragstests über Python), Build; **52 Browser-Tests** auf simuliertem S25+ bestanden (neu: Kandidaten auf der Startseite, Einzelansicht mit Urteil und Erklärungen, Potenzial-Liste mit Filtern, Signale auf der verschlüsselten Website) |
| GitHub Actions „Datenquellen prüfen“, 14.10.2026 06:40–07:00 Uhr | Kursmeldung als Schlusskurs, Kursziele, weitere Quellen | Kursmeldung = letzte Stundenkerze bei 13 europäischen Werten ohne Tageskerze (0,0 Basispunkte), = Tageskerze bei 7 Werten mit vollständiger Kerze (0,0 Basispunkte); Kursziele bei 21 von 22 Testaktien weltweit, 50 Abrufe in 20 s ohne Drosselung; Nasdaq, Stocktwits, Trading Central (US) erreichbar; nach der Absicherung 15 Tests bestanden, 1 übersprungen (EODHD ohne Schlüssel) |
| Entwicklungsumgebung, 13.10.2026 22:12 Uhr | Alle Python-Tests, Version 1.5.2 | 315 Tests: **305 bestanden**, 10 übersprungen (6 Live-Tests ohne Netz, 4 Kalendertests ohne Bibliothek), 0 Fehler |
| Entwicklungsumgebung, 13.10.2026 | App 1.5.2: Typprüfung, 38 Tests, Build | ohne Fehler; 24 bestanden, 14 Datenvertragstests über Python (14 von 14 bestanden); Build byte-gleich |
| GitHub Actions „Prüfung“, 13.10.2026 | Versionen 1.3.0 (16:33 Uhr), 1.4.0 (16:56 Uhr), 1.4.1 (17:19 Uhr), 1.5.0 (18:41 Uhr, Commit 203d136), 1.5.1 (21:07 Uhr 75b340b, 21:17 Uhr 9902692, 21:37 Uhr 772a84e, 21:53 Uhr 7fd7552), **1.5.2 (22:13 Uhr, 62c7c5e)** | alle grün; 1.5.2: 315 Tests in 215,2 s, 6 Live-Tests übersprungen, echte Börsenkalender 4 von 4, `app/dist` identisch mit dem Build auf GitHub |
| GitHub Actions „Täglicher Lauf“ `nur_website`, 13.10.2026 18:48 Uhr | App 1.5.0 bereitstellen | grün in 37 s: „App 1.5.0+087dc246 neu zusammengesetzt“; `version.json` und `status.json` der Website zeigen 1.5.0 und den Zeitplan 07:00 |
| GitHub Actions „Prüfung“, 13.10.2026 | Version 1.1.0 (13:28 Uhr) und Folgeänderung (13:34 Uhr) | 218 bzw. 220 Tests bestanden, je 6 Live-Tests übersprungen; echte Börsenkalender 4 von 4 |
| GitHub Actions „App mit echten Daten prüfen“, 13.10.2026 22:52 Uhr (Commit 9405d65) | veröffentlichte App 1.5.2+02388482 mit dem echten Stand `2026-10-12_c3806c24`, Chromium im Format des S25+ | **alles in Ordnung:** entsperrt und geladen in 5,6 s; 17 von 17 Ansichten ohne Fehler (je 1,1–1,3 s; Rendite 90 Zeiträume, Ranking 10 Plätze, Matrix 990 Zellen); Einzelansicht der ersten Aktie mit 19 Kennzahlzeilen, Kursgrafik und zweitem Börsenplatz in 3,3 s; erneut geöffnet in 1,7 s ohne erneute Passphrase, Service Worker aktiv; keine Konsolenfehler, keine fehlgeschlagenen Abrufe. Vorläufe um 22:44 und 22:48 Uhr: Prüfskript wartete nicht auf die nachgeladene Kursreihe der Einzelansicht (behoben); einmal eine Antwort 503 ohne erkennbare Datei – im nächsten Lauf nicht wiederholt, seither werden fehlgeschlagene Abrufe mit Datei gemeldet |
| GitHub Actions „Datenquellen prüfen“, 13.10.2026 12:02 Uhr | echte TR-Liste, OpenFIGI, Yahoo | 7 bestanden, **1 fehlgeschlagen** (Yahoo ohne Schlusskurs 12.10.2026 in Europa und Asien), 1 übersprungen (EODHD ohne Schlüssel) |
| GitHub Actions „Täglicher Lauf“, 13.10.2026 | echte Läufe | **Erster echter Datenstand um 20:37 Uhr** (Teilstand: USA, Australien, Neuseeland), **erster vollständiger Stand um 21:50 Uhr** (alle 31 Börsen, nachdem Yahoo die Schlusskurse vom 12.10. nachgeliefert hatte), um 22:18 Uhr neu gerechnet mit 1.5.2 (Abgleich v3: 8 statt 75 auffällige Aktien); App 1.5.2 online. Die Läufe davor endeten mit „wartet auf Kursanbieter“ (Abschnitt 7) |

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

**Ergebnis (13.10.2026, 22:12 Uhr, Version 1.5.2): 315 Tests, 305 bestanden, 10 übersprungen, 0 Fehler, Dauer 322,3 s, keine Ressourcenwarnung.** Version 1.5.0 war um 18:40 Uhr mit 298 Tests grün (288 bestanden, 293,8 s); 1.5.1/1.5.2 bringen vier Einheitentests zu fehlenden Börsentagen, neun zum Börsenplatz-Abgleich (Börsenkalender, Umsatz, Schwelle nach Tagesschwankung), je einen Pipeline-Test zur Teilstand-Schwelle und zu Fehlern im Abgleich sowie zwei Browser-Tests zum Teilstand dazu.

Ein Gesamtlauf kurz davor hatte einen Fehler: Ein älterer Browser-Test erwartete einen Text nur einmal auf der Seite, die neue Häufigkeitsansicht nennt ihn zweimal (sichtbar und für Screenreader). Der Test wurde präzisiert, die App blieb unverändert; maßgeblich ist der Lauf oben.

| Modul | Tests | Inhalt |
|---|---:|---|
| `tests/unit/test_metrics.py` | 14 | Rendite, OLS, R², Steigung, Rauschen, MDD, Referenz mit exakter Bruchrechnung und `numpy.polyfit`; **1.5:** positive Schlusskursvergleiche strikt gezählt |
| `tests/unit/test_windows.py` | 11 | Kalenderfenster 1–90, Startsitzung, fehlende Endkurse, Feiertage, Stichtag |
| `tests/unit/test_quality.py` | 26 | Zulassung (V/U), 98-%-/80-%-Grenzen, Splits, Einheiten, Sprünge, Kursbewegung ohne Umsatz; **1.5 (Methode 1.7.0):** fehlendes Volumen an einer Beobachtung, kein positives Volumen an Start oder Ende, gemeldeter Split im Fenster zurückgehalten (auch bei bereinigter Reihe, Freigabe nur nach Prüfung), jeweils mit Status der Vorversion; **1.5.1 (Methode 1.8.0):** höchstens 20 % fehlende Börsentage, ein fehlender Tag immer erlaubt (exakt als Bruch), Vorversion 98 % im Vergleich, ein fehlender Tag beim Kursanbieter wie am 12.10.2026 (Zeiträume 2–90 bewertet, 1 Tag ohne Startkurs, nichts aufgefüllt, Vergleich zählt 67 neu bewertete Paare aus Status 12), größere Lücken weiter ausgeschlossen, Volumenbezug wählbar |
| `tests/unit/test_ranking.py` | 24 | Perzentile, Gleichstände, alle elf Gewichtungen, native/common_trend, Untergruppen; **1.4:** Gruppe B (Vergleichsmengen V ∩ L und U ∩ L, eigene Perzentile, 0/100 und 100/0 in der Reihenfolge der Gruppe A, gemischte Gewichtungen können abweichen, leere Gruppe); **1.5:** Reihenfolge Score → Rendite → ISIN für alle Gewichtungen, bei gleichem Score und gleicher Rendite entscheidet die ISIN (nicht R²) |
| `tests/unit/test_frequency.py` | 16 | Top-1/3/10-Häufigkeiten, Nenner, Invarianten, Renditesieger, Gesamtmaximum |
| `tests/unit/test_engine_coverage.py` | 5 | Abdeckungsbilanz, Reproduzierbarkeit |
| `tests/unit/test_turnover.py` | 22 | **1.1:** Ø Tagesumsatz (Definition, fehlende Sitzungen, 16 von 20, Untereinheiten, Wechselkurse, Split), zwei Rendite-Ranglisten, Übernahmemuster |
| `tests/unit/test_ecb.py` | 11 | **1.1:** EZB-Datei (Parser, Schutz vor XML-Angriffen, HTTP-Fehler), Ablage im Lauf, Rückfall auf gespeicherte Kurse; **1.3:** ganze EZB-Reihe als ZIP (CSV, „N/A“, Rückblickzeitraum, unerwartete Archive), einmaliges Laden, Ausfall verkürzt nur den Rückblick |
| `tests/unit/test_rotation.py` | 12 | **1.3:** Wochenwerte (letzter und erster Kurs, Lücken nicht aufgefüllt, Volumen ohne Angabe, Sprünge über das Wochenende), Kandidatenauswahl (Umsatz, Umsatztage, Abdeckung, Tagessprung), erster Freitag im Monat, Haltepuffer, Ausführung zum ersten Kurs der Folgewoche, beschlossene Umschichtung am letzten Freitag, Vergleich gleich gewichtet, Kosten, Steuer mit Pauschbetrag, Erstattung und Verlusttopf, Tagesvorschlag |
| `tests/unit/test_venues.py` | 21 | **1.2:** Wahl des zweiten Börsenplatzes (Xetra vor Frankfurt, nie Referenz, gleiche Kursreihe oder OTC), Vergleich in Referenzwährung, Schwellen, Endkursabweichung, Pence, Wochenende, fehlende Vergleichskurse und Wechselkurse; **1.5.1 (`boersenplatz-v2`):** Lieferlücke an einem Sitzungstag wird nicht mit dem Freitagskurs überbrückt (v1 zum Vergleich: alle Zeiträume auffällig), Feiertag am zweiten Platz → letzte Sitzung davor, Lücke am Start nur für diesen Zeitraum, Kurse an Tagen ohne Sitzung ignoriert; **1.5.2 (`boersenplatz-v3`):** robuste Tagesschwankung unempfindlich gegen einen einzelnen Sprung, Schwelle mindestens 10 % und höchstens Faktor 2, stark schwankende Aktie innerhalb ihrer Schwankung unauffällig (nach fester Regel auffällig), Faktor 2,2 immer auffällig, kein Umsatz am Stichtag oder Start → kein Vergleich, unbekanntes Volumen zählt als vorhanden, Auswertung nach fester 10-%-Regel |
| `tests/unit/test_update.py` | 5 | **1.2:** Startlinks auf GitHub (nur in GitHub Actions, unsichere Werte abgewiesen), nächster möglicher Kursstichtag nach derselben Regel wie der Stichtag |
| `tests/unit/test_summary.py` | 5 | Kurzbericht des Laufs als GitHub-Hinweis (Zählungen vor Beispielen, Kürzung, Börsen ohne Kursdaten mit Beispielen) |
| `tests/unit/test_symbols.py` | 11 | **1.4.1:** Kürzel ohne Kursdaten (Börsentabelle v2, Schreibweisen, Suche nach ISIN, Plausibilität, Migration 0006) |
| `tests/unit/test_providers.py` | 30 | TR-PDF-Parser (erzeugte PDFs), Yahoo-/EODHD-Antwortformate, OpenFIGI-Zuordnung, Drosselung, Stichtag, Sommerzeit, Verschlüsselung, Schwärzung; Zeitzonen mit gleicher Verschiebung nur mit bestätigendem Börsencode |
| `tests/unit/test_workflows.py` | 8 | GitHub-Workflows: Auslöser, Rechte, Secrets, Bereitstellung nur nach bestandener Prüfung, Zeitplan = Konfiguration |
| `tests/integration/test_pipeline.py` | 27 | **1.4:** Gruppe B in Fenster-, Übersichts-, Häufigkeits- und Kursreihendateien (nur Aktien aus L, Vergleichsmenge U ∩ L, Kopfdatei, Spitzenreiter, Fundstellen, Rangmatrix, Kalenderstarts); **1.3:** Umschichtungs-Regel im Lauf (alle 24 Varianten, Prüftage, Ausführung am nächsten Handelstag, Käufe nur unter den ersten N, Trend gleich der Rendite aus der Kursreihe), Langhistorie in Etappen mit Wochenwerten und Neuladen nach Split, kein Langabruf bei Drosselung; Täglicher Lauf mit DEMO-Quelle: Veröffentlichung, Doppelstart, Checkpoint, erneuter Abruf fehlender Stichtagskurse, von Hand gestartete Läufe warten nur (letzter geplanter Versuch entscheidet), Ausfall, Parserfehler, atomares Schreiben, Tickerwechsel, Sicherung; beide Rendite-Ranglisten in allen Dateien gleich; Börsenplatz-Abgleich (Kennzeichen, keine Änderung von Rendite und Rang, fehlender Platz, Abruffehler, Drosselung, gespeicherte Wahl; **1.5.1:** Fehler der Quelle oder nicht lesbarer Börsenkalender verhindern die Veröffentlichung nicht); nächster Kursstand im Status |
| `tests/integration/test_ci_flow.py` | 7 | Kompletter Ablauf `traktien ci` gegen nachgebildete GitHub-REST-API auf frischen Runnern; lückenloser Austausch der Sicherung; nur Website neu bereitstellen; neue Passphrase |
| `tests/integration/test_app_contract.py` | 1 | Startet die 14 Datenvertragstests der App (Node) gegen echte DEMO-Dateien, unverschlüsselt und verschlüsselt |
| `tests/e2e/test_mobile_app.py` | 49 | Gebaute App im Browser auf simuliertem Galaxy S25+ (dazu Querformat und Desktop) |
| `tests/live/…` | 10 | **übersprungen** (6 Quellen ohne Netz, 4 Kalender ohne Bibliothek) – in GitHub Actions ausgeführt, Abschnitt 7 |

## 2. App (TypeScript)

```bash
cd app && npm run typecheck && npm test && npm run build
```

- Typprüfung: **ohne Fehler**.
- `npm test`: 38 Tests, **24 bestanden**, 14 übersprungen – die 14 Datenvertragstests brauchen erzeugte Datendateien und laufen über `tests/integration/test_app_contract.py`. Dort: **14 von 14 bestanden, 0 übersprungen** (der Python-Test verlangt ausdrücklich `# fail 0` und `# skipped 0`).
- **1.5 im Datenvertrag:** *Prüfung 20* – für jede der elf Gewichtungen und beide Gruppen ist jede Zeile von „Sieger nach Zeitraum“ (7 … 90 Tage) Platz 1 der vollständigen Rangliste desselben Fensters (Instrument, Rangscore bitgleich, Kursrendite, tatsächlicher Anfang, Zahl der Schlusskurse); die Zählung über die zehn Zeiträume stimmt mit einer unabhängigen Nachzählung überein und bleibt von der 90-Fenster-Zählung getrennt. *Identische Kursfenster:* `same_set` stimmt für V, U, V ∩ L und U ∩ L mit einer Nachrechnung aus den Fensterdateien (ISIN und tatsächliches Startdatum) überein; identische Bestände haben identische Ranglisten; „nur einmal zählen“ ergibt nie mehr Nennungen und als Nenner genau die Zahl verschiedener Fenster. *Methode 1.7.0:* Methodenvergleich im Manifest passt zu den Fenstern (V und U nach neuen Regeln = Summen der Fensterdateien, Wegfall mit Grund), positive Schlusskursvergleiche zwischen 0 und n − 1 und passend zum Vorzeichen der Rendite.
- Datenvertrag: Die App berechnet Perzentile und Scores aller elf Gewichtungen **bitgleich** zur Serverberechnung; Renditesieger (90 Zeilen) und Häufigkeiten stimmen mit der Serverreferenz überein; Untergruppenranking stimmt mit `traktien.analytics.ranking.rank_subgroup` überein; verschlüsselte Dateien: richtige Passphrase entschlüsselt, falsche Passphrase und vertauschte Dateien scheitern. **1.1:** Ranking 2 ist in jeder Fensterdatei genau Ranking 1 ohne die nicht aufgenommenen Aktien, mit gleichen Renditen, Start- und Endkursen; Start- und Endkurs ergeben die Rendite (Abweichung ≤ 10⁻¹²); die Häufigkeit mit Umsatzfilter zählt nur aufgenommene Aktien und nennt ihr Universum. **1.2:** Geprüft sind genau die ersten 10 Plätze beider Ranglisten; das Kennzeichen „Börsenplatz-Abweichung“ steht genau bei den auffälligen Vergleichen.
- **1.4 – Gruppe B im Datenvertrag:** Scores aller elf Gewichtungen der Gruppe B bitgleich zum Server (Fundstellen und Spitzenreiter, über 500 Vergleiche); Zählung der App (Platz 1, Top 3, Top 10, auswertbare Kombinationen) gleich der Serverreferenz für Gruppe A und B; Matrixzellen der Gruppe B nur Aktien aus L; „≡“ nur bei gleicher Aktie mit gleichem Start. Reine Funktionstests: identische Kursfenster, Leerzustände, Kennzeichnung (Anzahl über beide Gruppen, Farbplätze nach Anzahl, einmal ist keine Wiederholung), Häufigkeit nach Platz 1, dann Top 3, Top 10, ISIN; „nur einmal zählen“; A und B getrennt.
- **1.3 – Umschichtungs-Regel im Datenvertrag:** alle 24 Varianten lesbar, Standardvariante aus leerer Adresse, Orders je Entscheidungstag mit Ausführung am nächsten Handelstag, Aufteilung heute und nach den Änderungen jeweils 100 %, Käufe nur unter den ersten N, Verkäufe vor Käufen, beschlossene Umschichtung noch nicht im Rückblick; verschlüsselt an den eigenen Pfad gebunden. Reine Funktionstests: Variante aus der Adresse (unbekannte Werte → Standard), Eurobeträge, Begründungstexte, Aufteilung mit gleichmäßig gekürzten Käufen, Texte „beschlossen“/„nach heutigem Stand“.
- Reine Funktionstests 1.2: Texte zum zweiten Börsenplatz (Umrechnung, kein Ergebnis → keine Aussage, ältere Stände), Erkennen des Laufergebnisses beim Aktualisieren (neuer Stand, keine neuen Kurse, anderer Status, Zeitüberschreitung), „heute/morgen ab 23:00 Uhr“.
- Build: `1.5.0+087dc246`, 13 Dateien, zusammen 636 KiB. Ein erneuter Build ergibt byte-gleiche Dateien (geprüft mit SHA-256; Voraussetzung für die Prüfung „app/dist ist aktuell“ in GitHub Actions).

## 3. Browser-Tests (Emulation, kein echtes Gerät)

Chromium mit 384 × 832 CSS-Pixeln, Pixelverhältnis 2,8125, Touch, Sprache de-DE, Zeitzone Europe/Berlin – das entspricht der Bildschirmgröße des S25+, ersetzt aber **keinen Test auf dem Gerät** und ist als automatisierter DOM-Test auch **kein visueller Browsercheck**. Ein Test prüft zusätzlich 832 × 384 (Querformat) und 1280 × 800 (Desktop). 48 Tests, alle bestanden. Geprüft unter anderem:

- **1.5.1/1.5.2 – Börsenplatz-Abgleich `boersenplatz-v2`/`v3`:** „Datenstand & Betrieb“ (Zeilen „Vergleichskurs“, „Auffällig“ mit der Schwelle der Aktie, „Nach fester 10-%-Regel“ mit der Auswertung, „Verglichene Zeiträume“, Börsen mit Namen) und „So wird gerechnet“ nennen die Regel aus der Version im Datenstand; ältere Stände (v1, v2) behalten ihren Text (App-Test). Einzelansicht: „Schwelle 40 % (übliche Tagesschwankung dieser Aktie 8,0 %)“ (App-Test).
- **1.5.1 – Teilstand:** „Teilstand“ im Kopf jeder Ansicht; die Startseite nennt die Börsen ohne Stichtagskurse mit Namen (London, Xetra) und den Grund (fehlende Daten, nicht Kursentwicklung); „Datenstand & Betrieb“ zählt Börsen und Aktien mit Stichtagskurs. Fehlen wie am 12.10. 28 von 31 Börsen, nennt die Startseite die 3 enthaltenen (Australien, Neuseeland und USA), ohne Seitwärtsverschiebung auf 384 px; die vollständige Liste steht unter „Datenstand & Betrieb“. „So wird gerechnet“ zeigt den Methodenwechsel 1.7.0 → 1.8.0 mit den Regeln zu fehlenden Börsentagen.

- **1.5 – Prüfung 19 (feste Schnellwahl):** genau zehn Tasten 7 … 90 Tage; jede wählt exakt ihr Kalenderfenster (Adresse, aktive Taste, Anzeige, Ziel-Startdatum = Stichtag − h Kalendertage aus der Fensterdatei); Platz 1 und seine Kursrendite stimmen je Fenster mit der Fensterdatei des Stands überein, Gewichtung und Gruppe bleiben beim Wechsel erhalten (auch Gruppe B mit 0/100); bei 7 und 14 Tagen mit 60/40 der Leerzustand mit Grund; freie Eingabe 37 Tage ohne aktive Taste; im Einzelchart zeigt die Grafik für jede der zehn Tasten genau Anfangstag, Endtag, Zahl der Schlusskurse und Veränderung des Fensters dieser Aktie; Kursraster mit derselben Schnellwahl.
- **1.5 – „Sieger nach Zeitraum“ (Prüfung 20 in der Oberfläche):** zehn Zeilen ohne seitliches Scrollen; für 60/40, 0/100, 50/50, 100/0 und 10/90 ist jede Zelle (A und B) Platz 1 der Fensterdatei mit derselben Kursrendite; „Gleichmäßigkeit nicht berechenbar“ bei 7 und 14 Tagen ohne Ersatzaktie; Antippen zeigt Beginn, Ende, Schlusskurse und Referenzmarkt, „Ganze Rangliste“ öffnet dieselbe Aktie auf Platz 1; eigene Zählung über die zehn Zeiträume = Nachzählung.
- **1.5 – Häufigste Aktien:** Spalten Rang, Unternehmen/ISIN, Platz 1, Top 3, Top 10, Zugelassen; Platz 1, Top 3 und Top 10 jeder Zeile und der Nenner „berechenbare Kombinationen“ stimmen mit einer Nachzählung aus den Serverdaten überein – für alle Gewichtungen 1–90 Tage, für „nur mit Gleichmäßigkeitsanteil“ 31–60 Tage und für 50/50 mit A und B in der freien Spanne 21–45 Tage; Sortierung „Gewinnt am häufigsten“ und „Meiste Top-10-Nennungen“; „nur einmal zählen“ senkt nie eine Zahl über den vorherigen Wert hinaus; CSV und JSON enthalten Gruppen, Gewichtungen, Zeiträume, Zählweise und Snapshot; die Tabelle passt (auch mit A- und B-Beiträgen) ohne seitliches Blättern auf 384 px. Zusätzlich mit einem eigenen Skript bei 360 und 412 px Breite gemessen: kein seitliches Blättern in Häufigkeit und Zehn-Fenster-Zählung.
- **1.5 – Matrix 1–90:** Sprung zu 70 Tagen; JSON-Export mit 990 Zellen (Stichprobe = Spitzenreiter der Übersicht, leere Zellen mit Grund), CSV mit 990 Datenzeilen.
- **1.5 – Start, Watchlist, Datenstand:** Erststandard 90 Tage und 60/40, Auswahl 30 Tage / 50/50 / Gruppe B bleibt nach Neuladen erhalten und bestimmt die ersten fünf (= Fensterdatei); vier direkte Einstiege; ISIN-Import mit Zusammenführung doppelter und Meldung ungültiger ISINs, Export als Liste und CSV; Methodenwechsel 1.6.0 → 1.7.0 mit Ausgangsmodell, Metadaten-Export ohne Schlüssel oder Passphrase, frühere Stände mit Methodenversion.

- **1.4 – Matrix A/B** (ab 1.5 mit 90 Zeilen): sechster Reiter „Matrix“; Zeilen × 11 Gewichtungen, „nicht berechenbar“ bei kurzen Zeiträumen, „≡“ bei gleichem Kursfenster; Zeitraumspalte bleibt beim seitlichen Wischen stehen, nur die Matrix verschiebt sich; Antippen markiert alle Vorkommen derselben ISIN (Anzahl markierter Zellen = Zellen mit dieser ISIN), Kennzeichnung in Gruppe B gleich; „Rangliste …“ öffnet die Rangliste der Gruppe B mit der Aktie auf Platz 1; kompakte Liste mit 30 Zeilen; Häufigkeit absteigend nach Platz 1, A und B getrennt, „Identische Kursfenster nur einmal zählen“ fasst zusammen.

- **1.3 – Umschichtungs-Regel:** Startseite → „Regel ansehen“; gelbes Depot-Lineal, „Keine Änderung“ bei der Standardvariante, 5 Positionen, nächste Entscheidung, Rückblick-Diagramm mit drei Linien, keine Seitwärtsverschiebung; Wechsel auf 10 Aktien; wöchentliche Variante mit beschlossener Umschichtung („Was die Regel jetzt umsetzt“, zwei Lineale, Verkaufen zuerst); eigener Depotwert (ungültige Eingabe abgewiesen, 25.000 € übernommen, gleiche Anteile, nach Neuladen erhalten, zurücksetzbar); Variantentabelle wählt per Antippen; Orders je Entscheidungstag aufklappbar; Abschnitt „Was die Rechnung nicht zeigt“.

- **1.2 – Aktualisieren auf Wunsch:** ☰ → „Jetzt aktualisieren“ (auch ohne Datenstand erreichbar); Knopf „Lauf auf GitHub starten“ öffnet die Seite des Workflows in einem neuen Fenster; die App wartet, zeigt in allen Ansichten „Aktualisierung angefordert“, das Warten übersteht einen Neustart; meldet sich der Lauf („keine neuen Daten“), erscheint das Ergebnis mit Grund, bis es ausgeblendet wird; der nächste mögliche Kursstand („Dienstag, 13. Oktober 2026 … ab 23:00 Uhr“) steht vor dem Start da.
- **1.2 – zweiter Börsenplatz:** gelbes Kennzeichen „Börsenplatz-Abweichung“ beim Sieger mit abweichendem Frankfurter Kurs, Zeile „Vergleich mit Börse Frankfurt (S194.F): auffällige Abweichung – dort …, Endkurs …“; unauffällige Plätze mit Rendite dort; Einzelansicht mit Börse, Symbol, Umrechnung, Rendite dort und Abweichungen (auffällig nur in den längeren Zeiträumen, wo die Testkurse abweichen); Abschnitt in „Datenstand & Betrieb“.
- **1.1 – zwei Rendite-Ranglisten:** zwei getrennte Reiter „Alle Aktien“ und „Ø Umsatz ≥ 10 Mio. USD“; je Zeitraum zuerst der Sieger, Antippen öffnet die Top 10, von dort die vollständige Liste mit Seiten; Standardansicht 1–7 Tage. Je Aktie Rang, Name, Ticker, ISIN, Kursrendite, Start- und Endkurs mit Datum, Börse und Währung, Ø Tagesumsatz mit Berechnungsbasis und Hinweise. Aktien mit sehr niedrigem Umsatz sind in Ranking 1 gekennzeichnet und fehlen in Ranking 2. Zählungen stehen getrennt da. Startdatum nach Wochenende = letzter Schlusskurs davor; Einzelansicht zeigt Ø Tagesumsatz und beide Rendite-Plätze; Häufigkeitsliste nennt Universum und Umsatzfilter; Passphrase lässt sich vor dem ersten Datenstand eingeben.
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

Gemessen am 13.10.2026 mit Version 1.1.0 (sechs Börsen in USD, EUR, GBp, HKD, AUD und JPY, synthetische Wechselkurse). Der Börsenplatz-Abgleich aus 1.2 ist nicht enthalten: Er besteht aus Abrufen beim Kursanbieter (höchstens 600 Aktien, Zeitbudget 15 Minuten) und rechnet nur wenig.

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

**Wiederholt am 13.10.2026, 21:30 Uhr, mit Version 1.5.1** (gleiches Skript, 11.500 Instrumente, verschlüsselt): Rechenkern 62,0 s, Veröffentlichung 76,3 s, 11.684 Dateien, zusammen 103,7 MB (Fenster 71,1, Kursreihen 31,3, Übrige 1,3), höchster Arbeitsspeicher 490 MB. Was das Handy beim Öffnen lädt, bleibt klein: `manifest.bin` 0,50 MB, `instruments.bin` 0,48 MB, `frequency.bin` 0,25 MB, `overview.bin` 0,03 MB, Kopf einer Rangliste höchstens 19 KB. Vollständige Ranglisten eines Zeitraums (im Mittel 0,77 MB, höchstens 0,86 MB) lädt die App nur für den gewählten Zeitraum und nur bei Bedarf, Kursreihen je Aktie (höchstens 4 KB) erst in der Einzelansicht. Zum Vergleich der echte Lauf: Kursabruf, Zuordnung und Abgleich brauchten am 13.10. zusammen 86 Minuten.

Nicht enthalten ist der Kursabruf über das Netz (eine Anfrage je Notierung, gedrosselt auf 2,5 je Sekunde, rechnerisch gut eine Stunde für 10.000 Notierungen) – er war hier nicht messbar.

Hochrechnung (nicht gemessen): Die DEMO-Datenbank belegt rund 110 Byte je Tageskurs einschließlich Indizes. Bei 11.500 Notierungen und 250 Tagen Aufbewahrung (≈ 175 Börsentage) wären das etwa 220 MB, komprimiert und verschlüsselt etwa 80 MB je Sicherung.

## 7. In GitHub Actions ausgeführt (13.10.2026)

Ergebnisse stehen als Hinweise in der Übersicht des jeweiligen Laufs (Actions → Lauf öffnen).

### Workflow „Prüfung“

21 Läufe am 13.10.2026 (bis 18:41 Uhr). Die ersten beiden scheiterten, weil `reportlab` (für den PDF-Rundlauftest) in `requirements-dev.txt` fehlte; seit der Korrektur um 10:58 Uhr sind alle Läufe grün. Version 1.1.0 (13:28 Uhr, Commit 1cdc1e6): **218 Tests bestanden (6 Live-Tests übersprungen)**, `npm ci` ohne Rückfall, Typprüfung und App-Tests bestanden, `app/dist` identisch mit dem Build auf GitHub; echte Börsenkalender `exchange_calendars`: **4 von 4 bestanden**. Folgeänderung (13:34 Uhr, Commit 852d017): **220 Tests bestanden**. Danach grün: 1.2.0 (14:19 Uhr), Folgeänderung (14:44 Uhr), 1.3.0 (16:33 Uhr), 1.4.0 (16:56 Uhr), 1.4.1 (17:19 Uhr) und 1.5.0 (18:41 Uhr, Commit 203d136): **298 Tests bestanden, 6 Live-Tests übersprungen**, echte Börsenkalender 4 von 4.

### Workflow „Datenquellen prüfen“ (12:02 Uhr)

| Prüfung | Ergebnis |
|---|---|
| TR-Instrumentenliste | bestanden: 11.560 ISINs im Aktienabschnitt, 0 ungültige, 0 doppelte, 1 Fortsetzungszeile; PDF 757.736 Byte, Stand 12.10.2026 08:06 Uhr; Apple, SAP, Deutsche Telekom gefunden |
| OpenFIGI | bestanden: Apple und SAP je 8 unterstützte Notierungen (u. a. Xetra und Frankfurt – die Grundlage des Börsenplatz-Abgleichs) |
| Yahoo Tageskurse und ISIN-Suche | bestanden: AAPL 31 Tageskurse bis 12.10.2026; ISIN-Suche findet AAPL |
| Yahoo Stichtagskurs je Börse | **fehlgeschlagen:** Schlusskurs vom 12.10.2026 fehlt bei allen 14 geprüften Börsen in Europa und Asien (Kerze vorhanden, Schlusskurs leer; beide Yahoo-Server, drei Abfragearten; Stundenkerzen vorhanden). Details: 04_Datenquellen_und_Abdeckung |
| EODHD | übersprungen (kein Schlüssel, kostenpflichtig, nicht freigegeben) |
| EZB-Referenzkurse | neu in 1.1 – in diesem Workflow noch nicht gelaufen; im Tageslauf vom 13.10. abends geladen (29 Währungen, Historie ab 16.05.2023) |

### Workflow „Täglicher Lauf“

| Start | Art | Ergebnis |
|---|---|---|
| 10:58 Uhr | erster echter Lauf (manuell) | TR-Liste übernommen, Zuordnung begonnen, Kurse abgerufen; `wartet_auf_provider` (Stichtagskurse 12.10. fehlen in Europa und Asien) → kein Datenstand |
| 12:05 Uhr | Lauf mit erneutem Abruf fehlender Stichtagskurse | nach 25 Minuten von Hand abgebrochen, um die App mit Passphrase-Eingabe bereitzustellen |
| 12:39 Uhr | `nur_website` + `zustand_neu_aufbauen` (neue Passphrase) | grün in 41 s: App 1.0.0 mit neuem Schlüssel online, Zustand leer |
| 12:40 Uhr | voller Lauf mit neuem Schlüssel (44 Minuten) | `wartet_auf_provider`. Kurzbericht: Identität 3.841 verifiziert, 133 unklar (davon 83 Wiener Aktien wegen Zeitzonenangabe – in 1.1 behoben), 26 kein Aktieninstrument, 7.560 offen; Kursabruf 3.916 Notierungen: 1.193 mit Stichtagskurs, 1.478 ohne Stichtagskurs (Europa/Asien am 12.10.), **1.162 ohne Kursdaten** (Ursache noch offen; der Kurzbericht nennt ab 1.1 die betroffenen Börsen mit Beispielen) |
| 13:35 Uhr | `nur_website` | grün: App 1.1.0 online |
| 13:35 Uhr | voller Lauf (Version 1.1 mit EZB-Kursen und neuem Kurzbericht, 55 Minuten) | `wartet_auf_provider`: Stichtagskurse 12.10. nur in Australien, Neuseeland und den USA vollständig (Xetra 17 von 439, London 4 von 689, Paris 1 von 515, übrige europäische und asiatische Börsen 0) |
| 14:24 Uhr | `nur_website` | grün: App 1.2.0 online |
| 14:44 Uhr | voller Lauf (70 Minuten) | `wartet_auf_provider`, gleiches Bild: USA 3.599 von 3.604, Australien 525 von 525, Europa und Asien weiter ohne Kurs vom 12.10. Kurzbericht: Identität 11.218 verifiziert, 235 unklar, 107 kein Aktieninstrument; Kursabruf: 5.281 mit Stichtagskurs, 4.176 ohne, 1.735 ohne Kursdaten (Toronto 960, Xetra 395, Stockholm 148, Singapur 82 – Anlass für 1.4.1) |
| 18:48 Uhr | `nur_website` | grün: App 1.5.0 online, weiterhin ohne Datenstand |
| 19:02 Uhr | zwei Starts ohne „erzwingen“ | der erste von Hand abgebrochen (er hätte nur weiter auf die fehlenden Kurse gewartet), der zweite von GitHub verworfen, weil ein neuerer Lauf in der Warteschlange stand |
| 19:08 Uhr | voller Lauf mit „erzwingen“ (Software 1.5.0, Methode 1.7.0; 19:11–20:37 Uhr, 86 Minuten) | **`veroeffentlicht`: erster echter Datenstand** `2026-10-12_5092bae0`, gekennzeichnet als Teilstand; Bereitstellung 20:37 Uhr grün. Stichtagskurse 12.10.: USA 3.623 von 3.628, Australien 525 von 525, Neuseeland 18 von 18, Xetra 17 von 439, Frankfurt 4 von 219, London 5 von 713, Bangkok 3 von 39, Paris 1 von 519, übrige Börsen in Europa und Asien 0. Identität: 11.141 verifiziert, 311 unklar, 108 kein Aktieninstrument. Kursabruf: 6.222 mit Stichtagskurs, 4.434 ohne, 1.792 ohne Kursdaten (Toronto 960, Xetra 395, Stockholm 148, Singapur 82, London 63); andere Kürzel 57 geprüft, 0 gefunden. EZB: 29 Währungen bis 13.10. Umschichtungs-Regel: Wochenwerte für 5.142 Aktien vollständig, Rückblick 06.10.2023–09.10.2026. Börsenplatz-Abgleich: 89 von 98 Aktien geprüft, 64 auffällig – ohne Xetra-Kurse vom 12.10. verglich `boersenplatz-v1` den Freitagskurs mit dem Montagskurs der Referenz, sodass jede Aktie mit mehr als 10 % Bewegung am Montag auffiel (geändert in 1.5.1, `boersenplatz-v2`) |
| 21:07 Uhr | voller Lauf mit „erzwingen“ (Software 1.5.1, Methode 1.8.0, `boersenplatz-v2`; 21:07–21:50 Uhr, 42 Minuten) | **`veroeffentlicht`: erster vollständiger Stand** `2026-10-12_9820e6d9` – Yahoo hatte die Schlusskurse vom 12.10. nachgeliefert. Stichtagskurse 12.10. an allen 31 Börsen mit Sitzung zwischen 97 und 100 % (Xetra 433 von 439, Frankfurt 216 von 219, London 695 von 713, Hongkong 734 von 735, Mailand 196 von 197, USA 3.623 von 3.628, übrige 100 %). Kursabruf: 10.622 mit Stichtagskurs, 34 ohne, 1.792 ohne Kursdaten. Wochenwerte 5.143 Aktien. Börsenplatz-Abgleich (v2): 102 von 110 Aktien geprüft, 75 auffällig; Zeiträume 3.080 auffällig, 5.084 unauffällig, 328 ohne Vergleichskurse – Anlass für `boersenplatz-v3` (1.5.2). Bereitstellung 21:50 Uhr grün |
| 21:17, 21:37, 21:53 Uhr | `nur_website` (eingereiht hinter dem Lauf) | 21:17 von GitHub verworfen (neuere Bereitstellung eingereiht); 21:37 grün: App 1.5.1+1089b596; 21:53 grün: App 1.5.1+cee5b7bd – „Datenstand unverändert (2 veröffentlichte Stände)“ |
| 22:13 Uhr | Lauf mit „erzwingen“ (Software 1.5.2, `boersenplatz-v3`; 22:13–22:18 Uhr, 6 Minuten) | **`veroeffentlicht`: vollständiger Stand** `2026-10-12_c3806c24` (gleiche Kurse; neue TR-Liste mit 11.531 ISINs, 29 weniger). Börsenplatz-Abgleich: 102 von 110 Aktien geprüft, **8 auffällig**; Zeiträume 51 auffällig, 1.305 unauffällig, 328 ohne Vergleichskurse, die übrigen ohne Umsatz am Vergleichsplatz. Auswertung: nach fester 10-%-Regel 3.080 Zeiträume (75 Aktien) auffällig – davon 2.934 ohne Umsatz am Vergleichsplatz, 95 innerhalb der üblichen Schwankung, 51 weiter auffällig. Bereitstellung 22:18 Uhr grün; `version.json` 1.5.2+02388482 und `status.json` (neuester und neuester vollständiger Stand `2026-10-12_c3806c24`, drei Stände aufbewahrt) über WebFetch um 22:25 Uhr gelesen |

Die Website `https://szymeklh87-commits.github.io/tr-aktienvergleich/` ist erreichbar und zeigt seit 20:37 Uhr den Teilstand vom 12.10. (`version.json`: App 1.5.0+087dc246, über WebFetch um 21:05 Uhr gelesen). Die Inhalte der Datenstände sind verschlüsselt und von hier aus nicht lesbar; Zahlen oben stammen aus dem Kurzbericht des Laufs. Auf dem echten Galaxy S25+ wurde die Passphrase eingegeben und gespeichert (Bildschirmfoto „Zugangsschlüssel gespeichert“).

## 8. Nicht geprüft (offen)

| Punkt | Grund | Was es abschließt |
|---|---|---|
| Inhalte des echten Datenstands (Ranglisten, Ranking 2, Methodenvergleich, Börsenplatz-Abgleich) im Einzelnen | verschlüsselt; die Live-Prüfung (22:52 Uhr) belegt, dass alle Ansichten mit den echten Daten laden und ohne Fehler angezeigt werden, prüft aber keine fachlichen Werte | Durchsicht auf dem S25+: ☰ → Datenstand & Betrieb (aufgenommene Aktien, Wechselkursstand, geprüfte/auffällige Aktien, Methodenwechsel) |
| Reproduktion des historischen Prüffalls vom 12.10.2026 (Auftrag, Prüfung 13) | Archiv `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` liegt nicht vor | Archiv bereitgestellt, Import und Vergleich aller 1.980 Kombinationen mit `results.json`, Abweichungen einzeln erklärt (09_Bekannte_Luecken, Abschnitt D) |
| Die 8 nach `boersenplatz-v3` auffälligen Aktien (51 Zeiträume) | Datenstand verschlüsselt, von hier aus nicht einzeln einsehbar | Einzelansicht auf dem Gerät: Kurse beider Plätze, Schwelle und Tagesschwankung; Ursache je Aktie benannt |
| Wirkung von Methode 1.8.0 auf echte Daten | Der vollständige Stand vom 12.10. ist mit 1.8.0 gerechnet; die Zählung „neu bewertet / nicht mehr bewertet“ steht verschlüsselt im Datenstand | ☰ → Datenstand & Betrieb → „Methodenwechsel“ auf dem Gerät |
| „Jetzt aktualisieren“ auf dem echten Gerät | Start über GitHub braucht die eigene Anmeldung | auf dem S25+: ☰ → Jetzt aktualisieren → Run workflow → App meldet das Ergebnis |
| EODHD | kein Schlüssel; kostenpflichtig | nur nach deiner Freigabe |
| Geplanter Lauf um 07:00 Uhr (bis 1.4: 06:00) | bisher nur manuelle Starts | Lauf mit Auslöser „schedule“ am 14.10.2026 |
| Bedienung auf dem echten Galaxy S25+ | bisher nur Passphrase-Eingabe; seit 20:37 Uhr liegt ein Datenstand vor | Installation und Durchklicken nach 01_Kurzanleitung_Handy |

## 9. Erweiterungen 1.1 bis 1.5: Prüfungen aus den Aufträgen

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
| **Auffällige Kursabweichungen zwischen Börsenplätzen (1.2, 1.5.1, 1.5.2)** | `test_venues` (21 Tests: Wahl des Platzes, Schwellen, Endkurs, Umrechnung, fehlende Kurse, Börsenkalender des zweiten Platzes, Umsatz und Schwelle nach Tagesschwankung); `test_pipeline.test_second_venue_flags_deviations_without_changing_returns_or_ranks`, `…_missing_failed_or_throttled_…`, `…_statuses_without_reuse`; Veröffentlichungsprüfung `boersenplatz_kennzeichen`; Vertrag „Zweiter Börsenplatz“; E2E `test_second_venue_deviation_in_lists_detail_and_status` |
| **Jederzeit aktualisieren (1.2, dein Wunsch vom 13.10.)** | `test_update` (5 Tests); `test_pipeline.test_status_names_next_possible_cutoff`; App-Funktionstest „Aktualisieren auf Wunsch“; E2E `test_update_on_demand_starts_on_github_and_reports_result` und `test_T59_first_use_without_snapshot_shows_setup_state` |

### Gruppenvergleich A/B (1.4, dein Auftrag „Beide Aktiengruppen über 1–30 Tage vergleichen“)

| Vorgabe (Punkt 7: „Prüfe insbesondere …“) | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Elf Gewichtungen in beiden Gruppen | Veröffentlichungsprüfungen `elf_gewichtungen` und `gruppe_b_eigene_vergleichsmenge`; `test_ranking.GroupBTests`; Vertrag „Gruppe B“ (Scores bitgleich) |
| Beide Umsatzgruppen getrennt, gleiche Formeln | `test_pipeline.test_group_b_in_windows_overview_frequency_and_series` (nur Aktien aus L, U ∩ L, 0/100 und 100/0 wie Gruppe A); `GroupBTests.test_mixed_weights_may_order_differently_than_filtering_group_a` dokumentiert die eigene Vergleichsmenge |
| Wiederholungszählung (Platz 1, Top 3, Top 10 je Rangliste höchstens einmal, nicht addiert) | App-Funktionstest „Gruppenvergleich“; Vertrag: Zählung = Serverreferenz für A und B; E2E `test_group_matrix_tabs_marks_list_frequency_and_identical_windows` |
| Wochenend-Doppelungen | Funktionstest (1 und 2 Tage mit gleichem Start → „≡“, „nur einmal zählen“ zählt einmal); Vertrag: „≡“ nur bei gleicher Aktie und gleichem Start; E2E (Hinweis zusammengefasster Fundstellen) |
| ISIN-Zuordnung | Kennzeichnung und Zählung über den Instrumentindex (= ISIN); E2E: markierte Zellen = Zellen mit derselben ISIN; Identitätsprüfungen unverändert (`test_providers`) |
| Fehlende Gleichmäßigkeitsdaten | Leerzustand `zu_wenig_tagesdaten` in Gruppe A und B (`test_pipeline`, E2E „nicht berechenbar: weniger als 15 Tageskurse“); keine Scores zum Füllen |

### Umschichtungs-Regel (1.3, deine Frage vom 13.10.)

| Vorgabe | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Regel nur auf Aktien mit Ø Umsatz ≥ 10 Mio. USD, 5 Aktien je 20 %, monatlich, 3-Monats-Trend | `test_rotation.SelectionTests`, `BacktestTests.test_holds_the_best_and_keeps_within_buffer`; Standardvariante in `test_pipeline.RotationPipelineTests` |
| Tagesvorschlag: welche Aktie zu wie viel Prozent kaufen, was (teilweise) verkaufen, mit Grund | `PreviewTests`, `test_decision_on_the_last_friday_stays_pending`; App-Funktionstest „Umschichtungs-Regel“; E2E `test_rotation_rule_today_backtest_variants_and_own_amounts` |
| Kein Rechnen mit dem Kurs, der das Signal erzeugt hat | `test_trades_at_first_close_of_next_week_not_at_the_signal_close`; Vertrag: Ausführung jeder Order nach dem Entscheidungstag |
| Kosten und Steuern wie bei der Bank | `CostAndTaxTests` (Spanne, 1 €, Pauschbetrag, Erstattung im Jahr, Freigabe des Pauschbetrags, Verlusttopf) |
| Regel wird bei jedem Stand nachgeprüft | Veröffentlichungsprüfung `umschichtung_regel_eingehalten`; `test_pipeline.test_rule_files_are_complete_consistent_and_match_the_series` |
| Rückblick bei Drosselung, Split und fehlender EZB-Reihe | `test_long_history_is_loaded_in_stages_stored_weekly_and_refreshed_after_splits`, `test_T43_T44_throttling_checkpoint_and_resume_same_cutoff`, `test_ecb.test_history_outage_only_shortens_the_review` |

### Auftrag vom 13.10.2026 (1.5): die 20 verbindlichen Prüfungen

„Bestanden“ heißt: in der Entwicklungsumgebung am 13.10.2026 mit DEMO-Daten ausgeführt und grün (Abschnitte 1–3). Prüfung 13 ist **nicht ausgeführt**, Prüfung 17 nur in der Emulation.

| Nr. | Prüfung | Nachweis | Ergebnis |
|---:|---|---|---|
| 1 | 1–90 als Kalenderzeiträume, Wochenenden und Feiertage | `test_windows` (T21–T25, T27), E2E `test_weekend_start_dates_in_return_rankings`, E2E Prüfung 19 (Ziel-Start = Stichtag − h Kalendertage) | bestanden |
| 2 | Endkurs gehört zum Stichtag, keine aufgefüllten Sitzungen | `test_windows.test_T03…`, `test_T28…`; `pure.test.ts` T67/T68/T76 | bestanden |
| 3 | Renditeformel, Währungs- und Splitbasis | `test_metrics` (T01, T02), `test_quality` (T32, T33), Vertrag „Rendite = Endkurs / Startkurs − 1“ | bestanden |
| 4 | Preis-OLS, Steigung, R², Rauschen, größter Rückgang | `test_metrics` (Referenz mit exakter Bruchrechnung und `numpy.polyfit`) | bestanden |
| 5 | Zu kurze Historie: Rendite ja, Gleichmäßigkeit nein | `test_windows.test_T24…`, `test_quality.test_T04…`; E2E Prüfung 19/20 („nicht berechenbar“ bei 7 und 14 Tagen) | bestanden |
| 6 | Fallende Gerade trotz hohem R² nicht im Aufwärtsranking | `test_quality.test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings` | bestanden |
| 7 | Elf Gewichte, Perzentile, mittlere Ränge, N = 0 / N = 1, stabile Sortierung | `test_ranking` (T12–T20, T79–T85, `TieRuleTests`), Vertrag „Scores bitgleich“ | bestanden |
| 8 | Getrennte Normalisierung A/B, 20-Sitzungen-Grenze mit Währungseinheiten | `test_ranking.GroupBTests`, `test_turnover` (Pence, Wechselkurse, 16 von 20) | bestanden |
| 9 | Kein falscher B-Eintritt bei unvollständigem Volumen oder ungeklärtem Split | `test_turnover.test_missing_volume_or_fx_prevents_ranking_2`, `test_split_inside_the_20_sessions_is_not_distorting_the_value`; `test_quality.test_1_7_*` und `test_T32/T33` (Fenster zurückgehalten) | bestanden |
| 10 | Keine doppelte ISIN; 0/100 nicht doppelt gezählt | `test_frequency.test_T88…`, Veröffentlichungsprüfungen, E2E (markierte Zellen = Zellen derselben ISIN) | bestanden |
| 11 | Zähler, Nenner, Zeitfilter, Bereinigung identischer Fenster | Vertrag „frequency-v2“ und „Gruppe B“; `pure.test.ts` Gruppenvergleich; E2E `test_frequency_filters_order_counts_and_exports` | bestanden |
| 12 | Zählsummen passen zur Zahl tatsächlicher Ranglisten | `test_frequency` (T90 Invarianten), Vertrag T90/T92/T93, Vertrag „nur einmal zählen“ (Nenner = verschiedene Fenster), E2E Nenner = Nachzählung | bestanden |
| 13 | Import des historischen Prüffalls reproduziert dessen Ergebnisse | – | **nicht ausgeführt** (Archiv fehlt) |
| 14 | Wiederaufnahme nach Abbruch, Anbieterlimit, fehlgeschlagenem Lauf | `test_pipeline.test_T43_T44…`, `test_T44_provider_outage…`, `test_ci_flow` | bestanden |
| 15 | Atomare Veröffentlichung ohne vermischte Stichtage | `test_pipeline` (Absturz beim Schreiben, T45–T47), Veröffentlichungsprüfungen | bestanden |
| 16 | Keine Geheimnisse in App, Protokoll, Exporten | `test_providers.test_T52…`, `test_pipeline.test_T52…`, `test_ci_flow`, `verify-site`, E2E Metadaten-Export | bestanden |
| 17 | Mobil, Touch, Suche, Gruppen, alle 90 Fenster, Matrizen, Charts | 49 Browser-Tests (Abschnitt 3) | bestanden **nur in der Emulation** (384 × 832, 832 × 384, 1280 × 800); echtes S25+ offen |
| 18 | Chartdaten = Beobachtungen; Indexbasis und Achsen beschriftet | E2E T75/T78, T66/T69/T70, Prüfung 19 (Grafik = Fenster der Aktie) | bestanden |
| 19 | Zehn feste Tasten wählen exakt ihr Kalenderfenster; alles wechselt gemeinsam | E2E `test_spec19_fixed_chips_select_exact_calendar_window` | bestanden |
| 20 | Zehn-Fenster-Übersicht = vollständige Ranglisten je Gewichtung und Gruppe; Zählung getrennt | Vertrag „Prüfung 20“ (alle 11 Gewichtungen, A und B), E2E `test_spec20_winners_by_window_match_full_rankings` | bestanden |

## 10. Abnahmetests T01–T100: Zuordnung

„E2E“ = Browser-Emulation (Abschnitt 3), „Vertrag“ = App-Datenvertragstest (Abschnitt 2). Alle genannten Tests liefen am 12. und erneut am 13.10.2026 (zuletzt Version 1.5.0) und waren grün, sofern nicht anders vermerkt.

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
| T41 | `test_pipeline.test_T41_T60…`, `test_ci_flow`; echte Läufe in GitHub Actions am 13.10.2026 manuell gestartet (Abschnitt 7) – der erste geplante Lauf um 07:00 steht noch aus |
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
