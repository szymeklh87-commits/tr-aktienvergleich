# AktienPilot – Umsetzungsstand und Entscheidungen

Begleitdatei zum Auftrag [`13_AktienPilot.md`](13_AktienPilot.md) (Abschnitt 0: „Ergänze Umsetzungsstand und Entscheidungen in
einer separaten Datei. Änderungen am Auftrag benötigen meine Zustimmung.“). Der Auftrag selbst bleibt unverändert; hier steht,
was umgesetzt, entschieden, offen oder widersprüchlich ist.

## Stand am 31.10.2026

| Punkt | Stand |
|---|---|
| Auftrag erhalten | 31.10.2026, 08:38 Uhr (Europe/Berlin), als Textdatei im Chat |
| Auftrag abgelegt | `docs/13_AktienPilot.md`, **byte-gleich** mit der erhaltenen Datei (7.787 Zeichen, SHA-256 `4691840490c8001a9b916cb9ff65b8684ab27e411dcbf023616e1bc76396cde9`). Nummer 13 = nächste freie Nummer (12 ist `12_Fehlende_Kurstage.md`) |
| **Auftrag unvollständig** | Die Datei endet mitten im Satz in Abschnitt 5: „LIVE wird für Alpaca, eToro Public API und Interactive Brokers über ib_async und IB Gateway vorbereitet. Implementiere z“. Alles danach fehlt (Rest von Abschnitt 5 und alle folgenden Abschnitte, auch die im Text genannte Stufe P7). Der Rest ist angefragt; bis dahin wird nichts aus den fehlenden Teilen angenommen |
| Arbeitsweise | eigener Branch `aktienpilot`, Pull Request als Entwurf, kein automatisches Zusammenführen, keine Änderung an `main` und keine Veröffentlichung neuer Produktivfunktionen ohne Zustimmung (Abschnitt 0) |
| Umsetzung | noch keine Funktionen – zuerst der vollständige Auftrag und die Bestandsaufnahme (Abschnitt 2) |

## Bestandsaufnahme (Abschnitt 2) – geprüft am 31.10.2026 auf `main` (Commit `dac97f7`)

| Auftrag sagt | Tatsächlicher Stand | Ergebnis |
|---|---|---|
| Python-Paket `traktien` unter `backend/`, TypeScript-/React-PWA unter `app/`, unittest- und npm-Tests, Konfiguration unter `config/` | so vorhanden (`backend/traktien`, `app/src`, `tests/unit`, `tests/integration`, `tests/e2e`, `tests/live`, `app/tests`, `config/*.yaml`) | bestätigt |
| verschlüsselte SQLite-Sicherung in Release-Assets, verschlüsselte Veröffentlichung über GitHub Pages | Release „datenstand“ mit verschlüsseltem Zustand und Archiven je Stand; Website über `actions/deploy-pages`, Daten im Container TRA1 (AES-256-GCM) | bestätigt |
| Python 3.13 im Workflow | alle Workflows `python-version: '3.13'` | bestätigt, kein Versionswechsel |
| Zeitplan 07:00 Europe/Berlin, Wiederholungen 07:15, 07:45, 09:00; Nachtlauf Mo–Fr 22:37 UTC | `taeglich.yml`: `0 7`, `15 7`, `45 7`, `0 9` mit `timezone: 'Europe/Berlin'`; `nachtlauf.yml`: `37 22 * * 1-5` (UTC) | bestätigt |
| `AGENTS.md` lesen, falls vorhanden | keine `AGENTS.md` im Repository | – |

Noch zu prüfen, sobald der vollständige Auftrag vorliegt: Abdeckung, Konsistenz, Herzschlag, Sicherung, Veröffentlichungsprüfung,
Geheimnisschutz (Abschnitt 2), Referenztests und Golden Master (Abschnitt 3).

## Widersprüche und offene Fragen (Abschnitt 0: „Melde Widersprüche“)

1. **Name der App:** Der Auftrag nennt die bestehende App „Aktien-Kompass / Lineal-Ranking“; im Repository, in der App und in
   der Dokumentation heißt sie „TR-Aktienvergleich“ (Kurztitel „TR-Vergleich“). Bis zur Klärung bleibt der Name unverändert.
2. **Arbeit an `main`:** Der parallel laufende Auftrag „Kursabgleich“ (25.10./31.10.2026, Version 1.20.0) verlangt ausdrücklich
   Veröffentlichung und wird deshalb wie bisher auf `main` umgesetzt. Die Regel „eigener Branch, keine direkten Änderungen an
   main“ gilt hier für AktienPilot.
3. **Fehlender Teil des Auftrags:** siehe oben – Betriebsstufen nach P1 bis P7, Strategie-, Risiko- und Steuerregeln sowie
   Abnahmekriterien sind nicht bekannt.
4. **Handel:** Die Arbeit an diesem Repository führt selbst keine Käufe oder Verkäufe aus und richtet keine Broker-Zugänge ein
   (vorhandene Vorgabe). Eine LIVE-Ausführung würde erst nach ausdrücklicher Zustimmung und mit eigenen Zugangsdaten auf einem
   eigenen Rechner laufen (Stufe 2 laut Auftrag).

## Entscheidungen

| Datum | Entscheidung | Grund |
|---|---|---|
| 31.10.2026 | Auftrag nur so weit abgelegt, wie er vorliegt; kein Text ergänzt | „unverändert ablegen“; der Rest ist angefragt |
| 31.10.2026 | Umsetzung beginnt erst mit dem vollständigen Auftrag | Abschnitt 0 („Wähle bis zur Klärung eine Auslegung, die neue risikosteigernde Transaktionen verhindert“) – ohne Kenntnis der Strategie- und Risikoabschnitte keine Funktionen, die Kauf- oder Verkaufsentscheidungen berechnen |
