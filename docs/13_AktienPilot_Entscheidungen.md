# AktienPilot – Entscheidungen

Routineentscheidungen zu Modulen, Migrationen, Tests, Dateinamen und Fehlerbehebungen (Auftrag
[`13_AktienPilot.md`](13_AktienPilot.md), Abschnitt 0). Jede Zeile nennt Datum, Entscheidung und Grund. Spätere Änderungen
stehen als neue Zeile darunter, nichts wird überschrieben.

## Ablage und Arbeitsweise

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | Vollständiger Auftrag (Fassung 31.10.2026, erhalten 12:36 Uhr) byte-gleich als `docs/13_AktienPilot.md`; die abgeschnittene erste Fassung (08:38 Uhr) als `docs/13_AktienPilot_Fassung_1_unvollstaendig.md` aufbewahrt (`git mv`, Verlauf bleibt) | Abschnitt 2: „Sichere die bisherige Auftragsfassung nachvollziehbar. Ersetze docs/13_AktienPilot.md …“ |
| 31.10.2026 | Nachricht vom 31.10.2026, 12:54 Uhr („Jetzt aktualisieren“, Kurs-/Abrufzeit, Beschleunigung) ohne neue Datei: gilt als Ergänzung der Fassung von 12:36 Uhr; Umsetzung auf eigenem Branch `aktualisierung` mit eigenem Pull Request | Mit der Nachricht kam keine neue Datei an. Eigener Branch, weil die Ergänzung die bestehende App betrifft und unabhängig von AktienPilot freigegeben werden kann |
| 31.10.2026 | Weiterarbeit auf dem vorhandenen Branch `aktienpilot` (Pull Request #1 als Entwurf), vorher `main` (1.20.3) zusammengeführt (Merge-Commit, keine umgeschriebene Historie) | Abschnitt 2: „Nutze den bestehenden Entwicklungsbranch, wenn er geeignet ist … kein ungefragtes Umschreiben gemeinsamer Git-Historie“ |
| 31.10.2026 | Name der App bleibt „TR-Aktienvergleich“; AktienPilot ist ein eigener Bereich `#/pilot` | Abschnitt „Ziel“: „Erhalte ihren bestehenden Produktnamen, solange ich keine Umbenennung beauftrage“ |
| 31.10.2026 | `taeglich.yml` bleibt auf diesem Branch unverändert; der Tageslauf ruft AktienPilot über Python auf. Für den Bestätigungsweg über GitHub fehlt dem Tageslauf damit vorerst das Lese-Token (Umgebungsvariable) – die App zeigt das als „nicht eingerichtet“. Die nötige Zeile im Workflow steht als Vorschlag in der Anleitung und braucht deine Zustimmung | bestehende Vorgabe, `taeglich.yml` nicht zu ändern |

## Architektur

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | Eigenes Paket `backend/traktien/aktienpilot/` mit getrennten Modulen: `config` (Konfiguration), `markt` (Marktdaten), `indikatoren`, `zeitregel` (Ausführungsprofile), `kosten`, `buchhaltung` (Ereignisjournal, FIFO-Lose), `risiko` (zentraler Risiko-Manager, Verlustgrenzen), `ausfuehrung` (Simulator), `strategien` (Lineal, S1–S3, S4), `motor` (gemeinsamer Tagesschritt), `speicher` (SQLite), `backtest`, `kennzahlen`, `bericht` (HTML), `bestaetigung`, `bestand`, `steuern`, `export`, `freigabe`, `benachrichtigung`, `tageslauf` | Abschnitt 3: „Trenne Daten, Strategie, Portfolio, Risiko, Ausführung, Steuern und Darstellung“ |
| 31.10.2026 | Ein gemeinsamer Tagesschritt (`motor`) für Backtest, PAPER und SIGNAL; der Zustand liegt im Speicher, die Speicherung (SQLite) ist getrennt | Abschnitt 14: „Neue Regeln nicht in unabhängigen, abweichenden Backtest-Implementierungen duplizieren“ |
| 31.10.2026 | Migration `0010_aktienpilot.sql` legt nur neue Tabellen `ap_*` an, ändert keine bestehende Tabelle | Abschnitt 3: „Ergänze eigene AktienPilot-Tabellen“; Abschnitt 18: „keine ungesicherte destruktive Migration“ |
| 31.10.2026 | Konfiguration `config/aktienpilot.yaml` im vorhandenen YAML-Format mit Prüfung beim Laden (Dataclasses wie `traktien.config`), kein pydantic | Abschnitt 3: „Vorhandenes Konfigurationsformat und vorhandene Validierung erweitern; pydantic nur bei begründetem Nutzen“ |
| 31.10.2026 | Fingerabdruck (SHA-256) der Konfiguration und je Strategie (Parameter, Risiko, Kosten, Ausführung, Profil, Marktfilter) | Abschnitt 22: Freigabe an Strategieversion, Parameter, Ausführungsprofil und Risikokonfiguration binden |
| 31.10.2026 | IDs deterministisch (UUID 5 aus Depot, Tag, Art, Inhalt) | gleiche Eingaben ergeben dieselbe ID – Wiederholungsläufe erzeugen keine doppelten Signale, Orders oder Buchungen (Abschnitt 18) |
| 31.10.2026 | Geldbeträge in EUR (Depotwährung), Kurse in der Notierungswährung; Untereinheiten (GBp, ZAc, ILA) über den vorhandenen `unit_factor` | wie im bestehenden Rechenkern (`providers.exchanges.unit_info`) |
| 31.10.2026 | Ereignisjournal unveränderlich (`ap_ereignis`, fortlaufende Nummer je Depot); der Depotstand entsteht immer neu aus den Ereignissen | Abschnitt 17: „Korrekturen als nachvollziehbare Ereignisse, keine stille Umschreibung bestätigter Ausführungen“ |
| 31.10.2026 | Unbekannte Anschaffungskosten bleiben `None` (nie 0); Bewertung ohne Kurs ergibt einen gekennzeichneten Teilwert | Abschnitte 15 und 17 |

## Strategien, Zeitregeln, Kosten

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | Indikatoren: MA, ATR und RSI nach Wilder (ATR/RSI ab Index `n`), Regression von `ln(Kurs)` gegen den Sitzungsindex, annualisiert mit 252 Sitzungen; konstanter Kurs → R² = 0 | Abschnitte 8–10: Formeln, Aufwärmphase und fehlende Daten dokumentieren und testen |
| 31.10.2026 | Angenommene Veröffentlichung im Backtest: Kalendertag nach dem Datenstichtag, 07:30 Uhr Europe/Berlin (konfigurierbar) | entspricht dem Tageslauf ab 07:00 Uhr mit Bereitstellung nach etwa 2–30 Minuten |
| 31.10.2026 | FOLGETAG-SCHLUSS: Ausführung zum Schlusskurs der ersten Sitzung der Börse der Aktie, deren Ende nach der Veröffentlichung liegt; TAGESDATEN: Eröffnung der ersten Sitzung, deren Beginn nach der Veröffentlichung liegt; VERZÖGERTER-EINSTIEG mit Tageskerzen „nicht simulierbar“ | Abschnitt 13; ohne Intraday-Daten keine erfundene Ausführung |
| 31.10.2026 | Ohne Börsenkalender: konservativ die erste Sitzung mit Kurs an einem Kalendertag nach der Veröffentlichung | keine Ausführung zu einem bereits verpassten Kurs (Abschnitt 13) |
| 31.10.2026 | Kosten: Ordergebühr 1 EUR, halber Spread nach Liquiditätsklasse (Ø Tagesumsatz ≥ 50 Mio. EUR 10 bp, ≥ 2 Mio. EUR 25 bp, sonst und unbekannt 60 bp), Slippage 5 bp, Währungsaufschlag 15 bp bei Nicht-EUR, TR-Aufschlag 10 bp bei FOLGETAG-SCHLUSS | Abschnitte 13 und 14: konservative, editierbare Ausgangswerte, mit echten Bestätigungen zu messen |
| 31.10.2026 | Limitorders werden nur zum definierten Kurs (Eröffnung bzw. Schluss) ausgeführt, nie zu einem angenommenen besseren Kurs innerhalb der Tageskerze | Abschnitt 13: unklare Tagesverläufe konservativ behandeln |

## Vergleichsinstrumente

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | MSCI World: iShares Core MSCI World UCITS ETF USD (Acc), ISIN IE00B4L5Y983, Xetra EUNL, thesaurierend; Geldmarkt: Xtrackers II EUR Overnight Rate Swap UCITS ETF 1C, ISIN LU0290358497, Xetra XEON, thesaurierend – Belege (Anbieterseite, Abrufdatum) werden in dieser Datei nachgetragen, sobald geprüft | Abschnitt 1: „Auswahl anhand belegter Eigenschaften; keine erfundenen Instrumentdaten“ |

## Gesamtauftrag 31.10.2026 (Abschnitte 0–32 und 7A)

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | Gesamtfassung (14:06 Uhr, 205.918 Bytes) ersetzt `docs/13_AktienPilot.md`; Fassung 12:36 Uhr als `13_AktienPilot_Fassung_2_2026-10-31_1236.md` archiviert; die bei 128.000 Zeichen abgeschnittene Übertragung von 13:57 Uhr nicht abgelegt (sie ist Byte für Byte der Anfang der Gesamtfassung) | Abschnitt 2: „Kein abgeschnittener Auftrag … anstelle der Gesamtfassung“ |
| 31.10.2026 | Integrationsbranch `gesamtauftrag` aus `aktienpilot` mit Merge von `aktualisierung` (Merge-Commit, keine Konflikte, keine umgeschriebene Historie); beide Branches und Pull Request #1 bleiben unverändert erhalten | Abschnitte 2 und 28.2 |
| 31.10.2026 | Ein Regelmotor für alles: S1–S3, Lineal-Vorwärtsdepot und Beispielvorlagen sind Regeln im Schema `tr-regel/1` (`aktienpilot/vorlagen.py`, Parameter nur aus `config/aktienpilot.yaml`) | Abschnitt 32.1: kein zweiter Regelmotor, keine konkurrierenden Defaults |
| 31.10.2026 | Kennzahlenkatalog liest für Lineal-Werte die Felder der `SnapshotComputation` und ruft für Häufigkeiten `aggregate_frequency` auf; Indikatoren über `aktienpilot/indikatoren.py`; fehlende Werte sind NaN | Abschnitt 31.8: „dieselbe versionierte Berechnung wie Ranking, Chart und Bericht“ |
| 31.10.2026 | Dreiwertige Logik (Kleene) für Filter und Ausstiege; nur „wahr“ lässt durch bzw. löst aus. Ein fehlender Sortierwert schließt den Kandidaten als „nicht prüfbar“ aus | Abschnitt 27.4: fehlende Daten nie automatisch wahr oder 0 |
| 31.10.2026 | Gleichstände in Regelauswahlen: Sortierschlüssel der Reihe nach, danach ISIN aufsteigend; Score = gewichtete Summe von Perzentilen (Durchschnittsränge) innerhalb der gefilterten Kandidaten | Abschnitte 25.5 und 31.4: feste, dokumentierte Gleichstandsregel; keine Addition von Prozent, R² und Nennungen |
| 31.10.2026 | Gewinnmitnahme wird zum Tagesschluss geprüft und nach dem Ausführungsprofil ausgeführt; Leiter mit Bezug „ursprünglich“ über die kumulierte Zielmenge (Rundungsreste gehen in die nächste Stufe); eine Position läuft von der Eröffnung bis zum vollständigen Verkauf; die Mindesthaltedauer gilt für alle freiwilligen Ausstiege einschließlich Gewinnmitnahme | Abschnitt 31.7 |
| 31.10.2026 | Stops: Eröffnung unter dem Stop → Ausführung zur Eröffnung (Lücke); sonst Tief unter dem Stop → zum Stopniveau; ohne Eröffnung/Tief nur Schlusskurs; innerhalb einer Kerze Stop vor Gewinnmitnahme; ein zum Schluss gekaufter Bestand hat am Kauftag noch keinen wirksamen Stop; Trailing-Stop nie nach unten | Abschnitte 9, 13, 29.4 |
| 31.10.2026 | Verkäufe bleiben bis zur Ausführung bestehen (bei fehlender Kerze neu eingeplant), Käufe verfallen; ist eine Position vollständig verkauft, werden ihre übrigen offenen Verkäufe storniert | Abschnitt 13: Schutzverkäufe nicht still verfallen lassen |
| 31.10.2026 | Reservierung eines Kaufs = Stück × geschätzter Kurs × 1,02 + Gebühr; die Stückzahl wird so bemessen, dass die Reservierungen das Budget nicht überschreiten; bei der Ausführung höchstens das verfügbare Guthaben (Teilausführung) | Abschnitt 29.3: denselben Euro nicht mehrfach vergeben |
| 31.10.2026 | Auch Kern-Käufe laufen durch den zentralen Risiko-Manager (`core=True`: ohne Stop-, Einzelaktien- und Höchstorderwertgrenze, mit Guthaben- und Pausenprüfung) | Abschnitt 15; Vergleich „Welt-ETF mit identischem Startkapital“ in einem Schritt (29.6) |
| 31.10.2026 | Echtgeld technisch ausgeschlossen: Modus nur PAPER, SIGNAL oder DEMO (Konfiguration und CHECK in der Datenbank), Risiko-Manager lehnt `real_money` immer ab, Tabelle `ap_freigabe` entfällt (Abschnitt 22 bleibt reine Zukunftsspezifikation) | Abschnitt 29.1: kein Weg zu einer echten Order |
| 31.10.2026 | Migration 0010 vor der ersten Veröffentlichung neu gefasst (lief nie produktiv): Orders mit vollständigem Inhalt, neue Tabellen `ap_regel`, `ap_wert`, `ap_rang_archiv`, `ap_marktreihe`; entfallen: `ap_signal`, `ap_ausfuehrung`, `ap_stop`, `ap_freigabe` (Ausführungen und Stops stehen im Ereignisjournal bzw. Positionszustand) | Abschnitt 32.3: keine Schattenbuchhaltung neben dem Ereignisjournal |
| 31.10.2026 | Kauf-Auslöser „termin“ und „auffuellen“ füllen bis N auf; „neues_signal“ und „eintritt_top_n“ kaufen nur Aktien, die bei der vorigen Entscheidung nicht ausgewählt waren. Wiedereinstieg nach einem Verkauf: „neues_signal“ erst nach mindestens einer Entscheidung ohne Auswahl, „pause“ nach n Sitzungen, „naechste_umschichtung“ erst ab der folgenden regulären Entscheidung | Abschnitte 31.5 und 31.7: keine Endlosschleife aus Verkauf und Rückkauf |
| 31.10.2026 | Die erste Entscheidung einer Strategie fällt am ersten verarbeiteten Stichtag, danach nach Zeitplan (wöchentlich: Wochentag oder Nachholen nach einem Feiertag) | Start ohne künstliche Wartezeit |
| 31.10.2026 | Ereignisweg (E-20, Planung, vor Nutzung nachzuweisen): privates Daten-Repository; Handy-Token nur „Contents: Lesen und Schreiben“ auf diesem Repository (feingranulare Token lesen öffentliche Repositories immer mit); eine kleine feste Weiterleitung im Daten-Repository (Push auf `eingang/<art>/…`) startet mit einem dort hinterlegten Secret ausschließlich die festen Workflows des Code-Repositorys; Inhalt verschlüsselt, Prüfung und Entschlüsselung nur im Code-Repository. Abweichung von „bevorzugt ohne ausführbare Workflows“: ohne Weiterleitung kein zeitnaher Start; das Handy-Token kann Workflow-Dateien ohne die Berechtigung „Workflows“ nicht ändern | Abschnitte 4 und 7A.5; GitHub-Doku zu feingranularen Token (abgerufen 31.10.2026) |
| 31.10.2026 | Kostenrahmen des Ereignisweges: private Repositories bei GitHub Free mit 12 USD Rechenzeit je Monat (≈ 2.000 Linux-Minuten); ohne Zahlungsmittel wird die Nutzung danach gesperrt, Kosten entstehen nicht; öffentliche Repositories mit Standard-Runnern frei. Die Weiterleitung wird je Anfrage als eigene Minute gezählt und in der App begrenzt | GitHub-Doku „How use of GitHub Actions is measured“ (abgerufen 31.10.2026); Community-Diskussion 210874 (Hinweis auf gesperrte Nutzung bei 0-USD-Budget, ungeklärt) |
