# TR-Aktienvergleich

Persönliche Handy-App (installierbare Web-App für das Galaxy S25+), die jeden Morgen auf einem Server neu berechnet zeigt, welche Aktien aus der öffentlichen Trade-Republic-Instrumentenliste in den letzten **1 bis 90 Kalendertagen** am stärksten und am gleichmäßigsten gestiegen sind – in **elf Gewichtungen** von „nur Kursrendite“ bis „nur Gleichmäßigkeit“, jeweils für **alle Aktien (Gruppe A)** und für **Aktien ab 10 Mio. USD Tagesumsatz (Gruppe B)**, dazu **zwei reine Rendite-Ranglisten** (alle Aktien sowie nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD, die vorderen Plätze mit einem zweiten Börsenplatz abgeglichen), mit ISIN, Kurscharts, Chart-Raster, Häufigkeitsliste und ehrlicher Abdeckung. Dazu eine **Umschichtungs-Regel** zum Ausprobieren (Tagesvorschlag und Rückblick nach Kosten und Steuern).

> Kein Produkt von Trade Republic, keine Anlageberatung, keine Orders, kein Depotzugriff. Die Ranglisten beschreiben die Vergangenheit und sind keine Prognose.

## Stand (13.10.2026, Version 1.5.0)

| | |
|---|---|
| Code, Tests, Anleitungen | vollständig; 298 Python-Tests (288 bestanden, 10 Live- und Kalendertests ohne Netz übersprungen – in GitHub Actions ausgeführt), 35 App-Tests (davon 14 Datenvertragstests über Python, alle bestanden), 47 Browser-Tests auf simuliertem S25+ – siehe [Testbericht](docs/07_Testbericht.md) |
| Neu in 1.5 | Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“: **feste Schnellwahl 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Tage** (dazu frei 1–90) in Ranglisten, Charts und Raster; **Sieger nach Zeitraum** (zehn Zeiträume, A und B nebeneinander, alle Gewichtungen); **Matrix 1–90**; **Häufigste Aktien** mit Filtern und „Meiste Top-10-Nennungen“; Startseite mit Auswahl; Watchlist-Import/-Export nach ISIN; Exporte; Tageslauf 07:00. Methode **tr-methode-1.7.0** übernimmt die dokumentierten Regeln des Ausgangsmodells TR-90D-11W-two-universes-v1.1 und vergleicht jeden Lauf mit den bisherigen Regeln |
| Historischer Prüffall | **Reproduktion nicht durchgeführt** – `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` lag nicht vor ([Lücken](docs/09_Bekannte_Luecken.md), Abschnitt D) |
| Bereitstellung | **erfolgt**: GitHub Actions und GitHub Pages, App unter https://szymeklh87-commits.github.io/tr-aktienvergleich/ |
| Echte Datenquellen | am 13.10.2026 geprüft (TR-Liste mit 11.560 ISINs, OpenFIGI, Yahoo, Börsenkalender). **Yahoo liefert für den 12.10.2026 in Europa und Asien keine Schlusskurse** – deshalb noch kein veröffentlichter Datenstand ([Lücken](docs/09_Bekannte_Luecken.md)); nächster planmäßiger Versuch 14.10.2026, 07:00 Uhr |
| Echtes Gerät | Passphrase auf dem Galaxy S25+ eingegeben; Ansichten mit Daten folgen mit dem ersten Datenstand |

## So funktioniert es

```
GitHub Actions (täglich 07:00 Europe/Berlin, Wiederholungen 07:15 / 07:45 / 09:00)
  └─ Python-Lauf: TR-Liste → ISIN-Zuordnung → Börsenkalender → Tageskurse → EZB-Wechselkurse
       → 90 Fenster × elf Gewichtungen × Gruppen A/B + Methodenvergleich → Prüfungen → verschlüsselte Veröffentlichung
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
