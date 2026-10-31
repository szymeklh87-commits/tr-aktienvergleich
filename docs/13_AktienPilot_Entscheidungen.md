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
