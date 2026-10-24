# Architektur

## Entscheidung in einem Satz

Ein täglicher **GitHub-Actions-Lauf** rechnet alles auf dem Server, sichert seinen Zustand verschlüsselt in einem **GitHub-Release** und veröffentlicht eine **statische, verschlüsselte Datenschnittstelle** zusammen mit der **installierbaren Web-App** auf **GitHub Pages**. Das Handy liest nur.

```
┌─── GitHub Actions – Zeitplan 07:00, 07:15, 07:45, 09:00 Europe/Berlin ────────────────────────────────────────────┐
│ 1. Zustand holen      Release „datenstand“: crypto.json, state.sqlite.tra → entschlüsseln, integrity_check        │
│ 2. Universum          TR-Instrumentenliste (PDF, Aktienabschnitt) → Prüfung auf Umfang und Plausibilität          │
│ 3. Identität          ISIN → genau eine Referenznotierung (OpenFIGI, Ersatz Yahoo-Suche), Abgleich mit Kursdaten  │
│ 4. Stichtag D         Börsenkalender: jüngster Tag, an dem alle Börsen mit Sitzung geschlossen haben (+60 min)    │
│ 5. Kurse              inkrementell mit Überlappung, Vollabgleich alle 30 Tage, Checkpoint ≥ 15 min Abstand        │
│ 6. Wechselkurse       EZB-Referenzkurse (90 Tage) → Datenbank; einmalig die ganze Reihe (ZIP) für den Rückblick │
│ 7. Rechenkern         90 Fenster × Qualitätsregeln × Kennzahlen × Ø Tagesumsatz × 24 Ranglisten                   │
│                       (Gruppe A: V und 11 Gewichtungen auf U; Gruppe B: V ∩ L und 11 Gewichtungen auf U ∩ L)      │
│ 8. Wochenwerte        Umschichtungs-Regel: Langabruf bis 3 Jahre für neu aufgenommene Aktien (Ø Umsatz ≥ 2 Mio.  │
│                       USD), jüngere Wochen aus den Tageskursen neu verdichten (Tabelle week_bar)                  │
│ 9. Börsenplätze       erste 10 Plätze beider Rendite-Ranglisten: zweiter Börsenplatz (Xetra/Frankfurt) laden,    │
│                       Wertentwicklung und Endkurs vergleichen → Hinweis bei > 10 % (nur bei Veröffentlichung)     │
│    Regel              24 Varianten im Rückblick + Tagesvorschlag (nur bei Veröffentlichung)                       │
│10. Prüfen             15 Konsistenzprüfungen (90 Fenster, 11 Gewichtungen, Bilanz = Universum, U ⊆ V,             │
│                       Ranking 2 = Ranking 1 ohne nicht aufgenommene Aktien, Gruppe B, Börsenplatz, Regel …)       │
│11. Veröffentlichen    verschlüsselte Dateien in temporären Ordner → atomar umbenennen → Archiv + Nachweis         │
│12. Sichern            Datenbank lückenlos austauschen, neue Archive hochladen, alte ausdünnen                     │
│13. Website            App-Hülle (app/dist) + neueste 3 Datenstände + status.json → GitHub Pages                   │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                    │ HTTPS, nur statische Dateien
                    ▼
┌─── Handy – Chrome oder Samsung Internet, als Web-App installiert ─────────────────────┐
│ Service Worker: App-Hülle und geladene Datendateien offline                           │
│ Schlüssel aus Passphrase (PBKDF2, einmalig), entschlüsselt lokal (Web Crypto)         │
│ Ansichten lesen genau einen Datenstand; Scores bitgleich aus veröffentlichten Rängen  │
│ Watchlist und Einstellungen nur im Gerät (localStorage, Schlüssel in IndexedDB)       │
│ „Jetzt aktualisieren“: Start auf GitHub mit eigener Anmeldung (kein Schlüssel in der  │
│ App), danach liest die App status.json jede Minute, bis sich der Lauf meldet          │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## Warum diese Architektur (Zuverlässigkeit, Kosten, Wartbarkeit)

Der Auftrag (Abschnitt 4) lässt eine einfachere gleichwertige Architektur zu, wenn Zuverlässigkeit, Kosten und Wartbarkeit begründet werden.

| Anforderung | Umsetzung | Warum |
|---|---|---|
| Rechnet täglich bei geschlossener App | Zeitplan in GitHub Actions, unabhängig vom Handy | Browser-Hintergrundsynchronisation ist vom Browser gesteuert und für Pflichtberechnungen ungeeignet |
| Zeitplan kann ausfallen | 3 Wiederholungen, Doppelstart-Schutz (`concurrency`), Checkpoints, Herzschlag in der App (> 30 h → „Keine aktuelle Prüfung“), E-Mail bei rotem Lauf | GitHub garantiert keine Pünktlichkeit; Ausfälle werden sichtbar statt verschwiegen |
| Dauerhafter Zustand trotz flüchtiger Runner | Verschlüsselte SQLite-Sicherung als Release-Asset, Austausch ohne Lücke | Kein Server, der schläft oder sein Dateisystem verliert; die Wiederherstellung läuft jeden Tag |
| Kein halbfertiger Stand sichtbar | Schreiben in temporären Ordner, Prüfungen, dann atomares Umbenennen; Website nur aus fertigen Archiven | Absturz mitten im Schreiben hinterlässt nichts Sichtbares (getestet) |
| Letzter guter Stand bleibt | Fehlgeschlagener Lauf veröffentlicht nur den Status, nie einen neuen Datenstand | Datenfehler vernichten kein gutes Ergebnis |
| Kosten | 0 € im Standardaufbau (öffentliches Repository) | keine Server, keine Datenbank-Dienste, keine Domain |
| Datenschutz trotz öffentlichem Repository | Alle Daten AES-256-GCM-verschlüsselt, Passphrase nur als Secret und auf dem Gerät | Pages ist kostenlos nur für öffentliche Repositories |
| Wartbarkeit | Ein Python-Paket, eine React-App, vier Workflows, Konfiguration als YAML | Keine weiteren Infrastrukturprodukte |

Verworfen: dauerhafter Server oder Container-Dienst (laufende Kosten, Wartung, Betriebssystem-Updates), kostenlose Hoster mit schlafenden Prozessen oder flüchtigem Dateisystem (im Auftrag ausdrücklich ausgeschlossen), Berechnung im Browser (zu viele Abrufe, keine Pflichtausführung, Schlüssel im Gerät).

## Bausteine im Repository

| Ordner | Aufgabe |
|---|---|
| `backend/traktien/analytics` | Reiner Rechenkern ohne Ein-/Ausgabe: Kalenderfenster (`windows.py`), Kennzahlen (`metrics.py`), Qualitätsregeln (`quality.py`), Ranglisten und Untergruppen (`ranking.py`), Ø Tagesumsatz (`turnover.py`), Wechselkurse (`fx.py`), Abgleich mit zweitem Börsenplatz (`venues.py`), Wochenwerte (`weekly.py`) und Umschichtungs-Regel (`rotation.py`), Häufigkeiten (`frequency.py`), Abdeckungsbilanz (`coverage.py`), Zusammenführung (`engine.py`), Status- und Hinweiscodes (`codes.py`) |
| `backend/traktien/providers` | Adapter: TR-Liste (`tr_universe.py`), OpenFIGI, Yahoo, EODHD, EZB-Referenzkurse (`ecb.py`), Börsenkalender, Börsentabelle, HTTP-Client mit Drosselung und Wiederholung, DEMO-Quelle. Ab 1.17: `YahooProvider.fetch_histories` holt die Chart-Abrufe des täglichen Laufs gleichzeitig über zwei Hosts (Auswertung immer im aufrufenden Thread, bei Drosselung zurück auf einzeln); `base.fetch_histories_sequential` für Anbieter ohne diese Möglichkeit; `fetch_recent` (Sammelabruf, abgeschaltet) |
| `backend/traktien/store` | SQLite-Schema (`migrations/0001_grundschema.sql`, `0002_wechselkurse.sql`, `0003_zeitzonen_neu_pruefen.sql`, `0004_boersenplatz.sql`, `0005_wochenwerte.sql`, `0006_kuerzel.sql`; Migrationen laufen beim Öffnen automatisch), Zugriffe (`repo.py`, nur parametrisierte Abfragen) |
| `backend/traktien/jobs` | Täglicher Lauf (`daily.py`), Stichtag (`cutoff.py`), Quellenwahl (`sources.py`), Sicherung im Release (`state.py`), Kurzbericht als GitHub-Hinweis (`summary.py`) |
| `backend/traktien/publish` | Prüfungen vor der Veröffentlichung (`checks.py`), Datenstand schreiben (`snapshot_writer.py`, Dateien der Regel in `rotation_payload.py`), Website zusammensetzen (`site.py`) |
| `backend/traktien/util` | Verschlüsselung (`crypto.py`), Zeit, JSON, ISIN-Prüfziffer, Protokoll mit Schwärzung |
| `backend/traktien/cli.py` | Befehle `demo`, `run`, `ci`, `site`, `serve`, `restore-test`, `verify-site` |
| `app/src` | Web-App: Ansichten (`views/`), Diagramme und Bedienelemente (`components/`), Datenzugriff, Entschlüsselung, Score-Rechnung, Export (`lib/`), Zustand (`state/`). Ab 1.16: Begriffe der Hilfe zentral in `lib/glossary.ts` (genutzt von `views/HelpView.tsx` und den ⓘ-Erklärungen in `components/help.tsx`), Fehlermeldungen in einfachem Deutsch in `lib/errors.ts` (unterscheidet keine Verbindung, Serverfehler, fehlende und unlesbare Datei; `lib/api.ts` meldet Serverfehler als `ServerError` statt „offline“) |
| `app/public`, `app/build.mjs` | HTML mit Content Security Policy, Manifest, Symbole, Service Worker; Build mit esbuild |
| `config/` | `methode.yaml` (versionierte Methode), `pipeline.yaml` (Betrieb), `boersen.yaml` (Referenzbörsen), `pruefungen.yaml` (manuelle Prüfentscheidungen) |
| `.github/workflows/` | `taeglich.yml` (täglicher Lauf), `nachtlauf.yml` (ab 1.17: startet den täglichen Lauf nach dem letzten Börsenschluss), `pruefung.yml`, `datenquellen.yml`, `sicherung.yml`, `app-pruefen.yml` (App mit echten Daten, unabhängige Nachrechnung); nur von Hand und nur lesend: `kursabruf-vergleich.yml`, `kursabruf-tempo.yml`, `android-pruefen.yml` (Chrome im Android-Emulator, DEMO-Stand) |
| `ops/externer-ausloeser/` | ab 1.17: optionaler externer Auslöser für den Nachtlauf (Google Apps Script; Token nur in den Skripteigenschaften); geprüft mit nachgebildeten Google-Diensten in `app/tests/ausloeser.test.ts` |
| `tests/live/` | Prüfungen mit echten Quellen und Daten: Live-Prüfung der App, unabhängige Nachrechnung, Kursabruf-Vergleich und -Tempo, Android-Emulator, Nachrechnung des Ausgangsmodells aus der HTML-Übersicht |

## Laufzustände

Ein Lauf beginnt mit `laeuft` und durchläuft dann (`wartet_auf_provider` | `teilweise_berechnet` | `vollstaendig_berechnet`) → `geprueft` → `veroeffentlicht`. (`geplant` ist im Schema für künftige Vorab-Einträge vorgesehen, wird derzeit aber nicht gesetzt.) Endzustände außerdem `keine_neuen_daten` (alles schon veröffentlicht), `fehlgeschlagen` und `abgebrochen` (verwaiste Sperre eines beendeten Runners). Jeder Zustand steht mit Zeit und Grund im Laufprotokoll und in `status.json`.

## Versionen und Reproduzierbarkeit

- Getrennt geführt: Softwareversion, Methodenversion (`tr-methode-1.9.0`), Ausgangsmodell (`TR-90D-11W-two-universes-v1.1`), Kennzahlen- (`kennzahlen-v2`), Ranking- (`ranking-11w-v2`), Häufigkeits- (`frequency-v2`), Gruppen- (`gruppen-v1`) und Umsatzversion (`umsatz-v1`), Börsenplatz-Abgleich (`boersenplatz-v2`, Regeln im Methoden-Fingerabdruck), Umschichtungs-Regel (`rotation-v1`), Kalenderversion, Universums-ID (Prüfsumme der TR-Liste), Datenrevision (Prüfsumme aller Eingaben einschließlich des Ø Tagesumsatzes in USD – ein geänderter Wechselkurs ergibt damit eine neue Revision).
- Der Idempotenzschlüssel eines Datenstands umfasst Stichtag, Universum, Eingabedaten, angezeigte Stammdaten, Versionen, Datenmodus und Vollständigkeit. Die Kurse des zweiten Börsenplatzes gehören nicht dazu: Der Abgleich läuft erst, wenn feststeht, dass ein neuer Stand veröffentlicht wird, und liefert nur Hinweise. Gleiche Eingaben ergeben keinen zweiten Stand; jede Änderung ergibt eine neue Revision mit Verweis auf den vorherigen Stand desselben Stichtags (`supersedes`).
- Veröffentlichte Stände werden nie verändert (append-only); ältere bleiben in der App wählbar.

## Sicherheit

- Geheimnisse nur als GitHub-Secrets; Protokolle schwärzen sie; schlägt `verify-site` fehl (Geheimnis in einer Datei, Datei nicht entschlüsselbar, Schema falsch), wird nichts hochgeladen und nichts bereitgestellt.
- Workflows: Der tägliche Lauf startet nur per Zeitplan oder manuell durch Berechtigte; der Workflow „Prüfung“ läuft zusätzlich bei Änderungen und Pull-Requests, aber ohne Secrets und nur mit DEMO-Daten; minimale Rechte; bereitgestellt wird nur nach bestandener `verify-site`-Prüfung (alles getestet in `tests/unit/test_workflows.py`).
- App: strikte Content Security Policy (nur eigene Skripte, keine fremden Verbindungen), keine externen Schriften oder Dienste, CSV-Export gegen Formel-Injection geschützt, Unternehmensnamen nur als Text dargestellt.
- Verschlüsselte Dateien sind an ihren Pfad gebunden (AAD); vertauschte oder veränderte Dateien werden erkannt.
- Keine Trade-Republic-Zugangsdaten, kein Depotzugriff, keine Orders.
