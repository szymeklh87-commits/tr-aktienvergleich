# TR-Aktienvergleich

Persönliche Handy-App (installierbare Web-App für das Galaxy S25+), die jeden Morgen auf einem Server neu berechnet zeigt, **welche Aktien gerade die stärksten Signale haben – kurzfristig und langfristig, mit Kurszielen der Analysten, erwarteter Steigerung, Ampel und Erklärung** – und welche Aktien aus der öffentlichen Trade-Republic-Instrumentenliste in den letzten **1 bis 90 Kalendertagen** am stärksten und am gleichmäßigsten gestiegen sind – in **elf Gewichtungen** von „nur Kursrendite“ bis „nur Gleichmäßigkeit“, jeweils für **alle Aktien (Gruppe A)** und für **Aktien ab 10 Mio. USD Tagesumsatz (Gruppe B)**, dazu **zwei reine Rendite-Ranglisten** (alle Aktien sowie nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD, die vorderen Plätze mit einem zweiten Börsenplatz abgeglichen), mit ISIN, Kurscharts, Chart-Raster, Häufigkeitsliste und ehrlicher Abdeckung. Dazu eine **Umschichtungs-Regel** zum Ausprobieren (Tagesvorschlag und Rückblick nach Kosten und Steuern).

> Kein Produkt von Trade Republic, keine Anlageberatung, keine Kaufempfehlung, keine Orders, kein Depotzugriff. Die Ranglisten beschreiben die Vergangenheit; Kursziele und Prognosen sind Einschätzungen Dritter (Analysten), die App fasst sie nur nach offengelegten Regeln zusammen.

## Stand (14.10.2026, Version 1.6.0)

| | |
|---|---|
| Code, Tests, Anleitungen | vollständig; 315 Python-Tests (305 bestanden, 10 Live- und Kalendertests ohne Netz übersprungen – in GitHub Actions ausgeführt), 38 App-Tests (davon 14 Datenvertragstests über Python, alle bestanden), 49 Browser-Tests auf simuliertem S25+ – siehe [Testbericht](docs/07_Testbericht.md) |
| Neu in 1.5 | Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“: **feste Schnellwahl 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Tage** (dazu frei 1–90) in Ranglisten, Charts und Raster; **Sieger nach Zeitraum** (zehn Zeiträume, A und B nebeneinander, alle Gewichtungen); **Matrix 1–90**; **Häufigste Aktien** mit Filtern und „Meiste Top-10-Nennungen“; Startseite mit Auswahl; Watchlist-Import/-Export nach ISIN; Exporte; Tageslauf 07:00. Methode **tr-methode-1.7.0** übernimmt die dokumentierten Regeln des Ausgangsmodells TR-90D-11W-two-universes-v1.1 und vergleicht jeden Lauf mit den bisherigen Regeln |
| Neu in 1.5.1 | Methode **tr-methode-1.8.0**: ein einzelner fehlender Börsentag beim Kursanbieter schließt einen Zeitraum nicht mehr aus (höchstens 20 % fehlende Tage, nichts wird aufgefüllt); der Abgleich mit einem zweiten Börsenplatz vergleicht nur noch Kurse desselben Tages; Teilstände nennen die fehlenden Börsen mit Namen |
| Neu in 1.6.0 | Auftrag vom 14.10.: **Potenzial**. Jede Aktie hat zwei Urteile mit Ampel – **kurzfristig** (relatives Volumen, Schwung, Steigetage, Trendlage, Ausbruch, RSI, Nachrichten, Community) und **langfristig** (Kursziele der Analysten mit erwarteter Steigerung, Bewertung, Wachstum und Finanzen, langfristiger Trend, Richtung der Analysten); **Trefferquote der Vergangenheit** je Punktebereich aus der eigenen Kurshistorie (jede handelbare Aktie, jeder Tag – nachprüfbar statt geschätzt); **Prognose-Grafik** (Kursziel-Spanne und übliche Schwankung 12 Monate voraus). **Startseite beginnt mit „Kandidaten mit Potenzial“**, neue Ansicht **Potenzial** mit Listen und Filtern, Einzelansicht mit Reitern Überblick/Analysten/Kennzahlen/Rendite und **Kursverlauf 1W–Max**. Neue Struktur: **Start · Rendite · Potenzial · Aktien · Analyse**, Erklärung zu jedem Signal und jeder Kennzahl (ⓘ). Quellen: Yahoo Finance (weltweit: Kursziele, Empfehlungen, Kennzahlen; Nachrichten), bei US-Aktien zusätzlich Trading Central (Bewertung), Nasdaq (zweiter Kursziel-Konsens), Stocktwits (Community). Kennzahlen werden täglich rotierend und auf Knopfdruck erneuert |
| Neu in 1.5.4 | Fehlt bei Yahoo nach Börsenschluss der Schlusskurs der Tageskerze (so am 12. und 13.10. für ganz Europa), gilt die letzte Kursmeldung der Sitzung – gekennzeichnet und automatisch ersetzt, sobald die Tageskerze kommt (Abweichung im Test: 0,0 Basispunkte) |
| Neu in 1.5.2 | Abgleich mit einem zweiten Börsenplatz (`boersenplatz-v3`): nur Kurse mit Umsatz, Schwelle nach der üblichen Tagesschwankung der Aktie (mindestens 10 %, ab Faktor 2 immer auffällig); jeder Lauf zeigt, was nach der alten festen 10-%-Regel auffällig gewesen wäre |
| Historischer Prüffall | **Reproduktion nicht durchgeführt** – `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` lag nicht vor ([Lücken](docs/09_Bekannte_Luecken.md), Abschnitt D) |
| Bereitstellung | **erfolgt**: GitHub Actions und GitHub Pages, App unter https://szymeklh87-commits.github.io/tr-aktienvergleich/ |
| Echte Datenquellen | am 13.10.2026 geprüft (TR-Liste mit 11.560 ISINs, OpenFIGI, Yahoo, Börsenkalender). **Erster vollständiger Datenstand seit 13.10.2026, 21:50 Uhr** (Stichtag 12.10., alle Börsen; Yahoo hatte die Schlusskurse vom 12.10. für Europa und Asien erst am Abend nachgeliefert, um 20:37 Uhr gab es deshalb zunächst einen Teilstand mit den USA, Australien und Neuseeland). Nächster planmäßiger Lauf 14.10.2026, 07:00 Uhr (Stichtag 13.10.) |
| Echtes Gerät | Passphrase auf dem Galaxy S25+ eingegeben; Ansichten mit Daten folgen mit dem ersten Datenstand |

## So funktioniert es

```
GitHub Actions (täglich 07:00 Europe/Berlin, Wiederholungen 07:15 / 07:45 / 09:00)
  ├─ Job 1 – Python-Lauf: TR-Liste → ISIN-Zuordnung → Börsenkalender → Tageskurse → EZB-Wechselkurse
  │    → 90 Fenster × elf Gewichtungen × Gruppen A/B + Methodenvergleich → Prüfungen → verschlüsselte Veröffentlichung
  └─ Job 2 – Kennzahlen (ab 1.6): Kursziele, Empfehlungen, Bewertung, Wachstum, Nachrichten, Community
       → Signale kurz-/langfristig, Ampeln, Trefferquote → verschlüsselter Signal-Stand → zweite Bereitstellung
           ├─ Zustand (SQLite, verschlüsselt) in den Release-Assets „datenstand“
           └─ GitHub Pages: App + verschlüsselte Datendateien
Handy (Chrome / Samsung Internet): öffnet die App, entschlüsselt lokal, liest nur
```

Das Handy rechnet nichts und muss nicht eingeschaltet sein. Fällt ein Lauf aus, bleibt der letzte geprüfte Stand sichtbar und die App meldet die Lücke. Zusätzlich lässt sich der Lauf jederzeit aus der App anstoßen (☰ → Jetzt aktualisieren; Start mit der eigenen GitHub-Anmeldung).

## Schnellstart

| Ziel | Anleitung |
|---|---|
| App auf dem Handy benutzen | [docs/01_Kurzanleitung_Handy.md](docs/01_Kurzanleitung_Handy.md) |
| Einrichten (GitHub, Passphrase, erster Lauf) | [docs/02_Einrichtung_und_Betrieb.md](docs/02_Einrichtung_und_Betrieb.md) |
| Wie gerechnet wird | [docs/03_Methodik.md](docs/03_Methodik.md) |
| Datenquellen, Abdeckung, Kosten | [docs/04_Datenquellen_und_Abdeckung.md](docs/04_Datenquellen_und_Abdeckung.md) |
| Einstellungen | [docs/05_Konfiguration.md](docs/05_Konfiguration.md) |
| Wenn etwas nicht stimmt | [docs/06_Fehlerbehebung.md](docs/06_Fehlerbehebung.md) |
| Was tatsächlich getestet wurde | [docs/07_Testbericht.md](docs/07_Testbericht.md) |
| Sicherung | [docs/08_Backup_und_Wiederherstellung.md](docs/08_Backup_und_Wiederherstellung.md) |
| Offene Punkte | [docs/09_Bekannte_Luecken.md](docs/09_Bekannte_Luecken.md) |
| Aufbau | [docs/10_Architektur.md](docs/10_Architektur.md), [docs/11_Datenvertrag_API.md](docs/11_Datenvertrag_API.md) |

## Lokal ausprobieren (DEMO mit synthetischen Testaktien)

```bash
pip install -r backend/requirements.txt        # Python 3.13; numpy, PyYAML, cryptography …
PYTHONPATH=backend python -m traktien demo --fresh
PYTHONPATH=backend python -m traktien serve --site build/demo-site --port 8080
# Browser: http://127.0.0.1:8080/   (alle Namen beginnen mit „DEMO“, alle ISINs mit „ZZ“)
```

Die App-Hülle liegt fertig gebaut in `app/dist`. Neu bauen: `cd app && npm ci && npm run build`.

Vorschau als eine einzige HTML-Datei (nur DEMO-Daten, z. B. zum Ansehen in Claude): `cd app && node scripts/build_preview.mjs` → `build/vorschau/tr-aktienvergleich.html`. Der Build bricht ab, wenn der Datenstand nicht DEMO oder verschlüsselt ist.

## Tests

```bash
PYTHONPATH=backend python -m unittest discover -s tests -t .   # Rechenkern, Pipeline, Datenvertrag, Browser
cd app && npm run typecheck && npm test                          # App
```

Die vollständigen Tests (Browser, PDF-Rundlauf) brauchen `pip install -r backend/requirements-dev.txt` und `python -m playwright install chromium`.

## Ordner

| Ordner | Inhalt |
|---|---|
| `backend/traktien` | Rechenkern (`analytics`), Datenquellen (`providers`), Zustand (`store`), täglicher Lauf (`jobs`), Veröffentlichung (`publish`), Kommandozeile (`cli.py`) |
| `app` | Handy-App (React, TypeScript), `dist` = fertige Hülle |
| `config` | Methode, Betrieb, Börsentabelle, Prüfentscheidungen |
| `tests` | `unit`, `integration`, `e2e` (Browser), `live` (echte Quellen, nur auf Anforderung), `perf` |
| `.github/workflows` | täglicher Lauf, Prüfung bei Änderungen, Datenquellen prüfen, Sicherung prüfen |
| `docs` | Anleitungen und Berichte; `docs/auftrag` = Programmierauftrag v1.2 |
