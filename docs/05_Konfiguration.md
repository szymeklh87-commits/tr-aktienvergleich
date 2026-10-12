# Konfigurationsreferenz

Alle Einstellungen liegen als Textdateien im Ordner `config/` und in den Workflows unter `.github/workflows/`. Geheimnisse stehen nie in diesen Dateien, sondern ausschließlich in den GitHub-Secrets.

## Uhrzeit des täglichen Laufs

Die Uhrzeit steht an zwei Stellen und muss an beiden geändert werden:

1. `.github/workflows/taeglich.yml` – maßgeblich für GitHub:
   ```yaml
   schedule:
     - cron: '0 6 * * *'        # Minute Stunde – hier 06:00
       timezone: 'Europe/Berlin'
     - cron: '15 6 * * *'       # Wiederholungen
       timezone: 'Europe/Berlin'
   ```
2. `config/pipeline.yaml` → `zeitplan.uhrzeit` und `zeitplan.wiederholungen_minuten` – Anzeige in der App (ein Test prüft, dass beide Stellen übereinstimmen). Ob ein Lauf pünktlich war, ergibt sich aus dem Zeitplaneintrag, der ihn ausgelöst hat.

Früher als etwa 05:00 ist nicht sinnvoll: US-Schlusskurse stehen ab etwa 23:00 Uhr deutscher Zeit plus Nachlieferungsfrist fest.

## `config/pipeline.yaml` – Betrieb

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `zeitplan.uhrzeit`, `zeitplan.zeitzone` | `06:00`, `Europe/Berlin` | Anzeige in der App |
| `zeitplan.wiederholungen_minuten` | `[15, 45, 120]` | Abstand der Wiederholungen |
| `zeitplan.max_versuche` | `4` | Versuche je Stichtag, danach Teilstand oder Fehler |
| `stichtag.karenz_minuten_nach_schluss` | `60` | Nachlieferungsfrist nach regulärem Börsenschluss |
| `vollstaendigkeit.markt_geliefert_ab` | `0.80` | Anteil Aktien einer Börse mit Stichtagskurs, ab dem die Börse als geliefert gilt |
| `vollstaendigkeit.teilstand_mindestens` | `0.90` | Mindestanteil gelieferter Börsen für einen veröffentlichten Teilstand |
| `anbieter.kurse` | `yahoo` | `yahoo` (kostenlos, inoffiziell) oder `eodhd` (kostenpflichtig, Secret `EODHD_API_KEY`) |
| `abruf.erstimport_kalendertage` | `200` | Historie beim ersten Abruf einer Notierung |
| `abruf.inkrementell_ueberlappung_tage` | `10` | Überlappung bei täglichen Abrufen (erkennt nachträgliche Korrekturen) |
| `abruf.vollabgleich_alle_tage` / `vollabgleich_max_pro_lauf` | `30` / `800` | regelmäßiger vollständiger Neuabruf (Splits, Korrekturen), auf Läufe verteilt |
| `abruf.max_laufzeit_minuten` | `300` | Zeitbudget; danach Checkpoint und Fortsetzung im nächsten Lauf |
| `abruf.identitaet_max_pro_lauf`, `identitaet_max_sekunden` | `4000`, `3600` | Begrenzung der ISIN-Zuordnung je Lauf |
| `abruf.identitaet_pruefung_alle_tage` | `45` | erneute Prüfung der Zuordnung |
| `universum.url` | TR-PDF | Quelle der Aktienliste |
| `universum.min_eintraege` | `1000` | weniger Einträge → neue Liste wird zurückgehalten |
| `universum.max_aenderung_ohne_pruefung` | `0.10` | mehr Änderung → Prüfung nötig |
| `universum.freigegebene_versionen` | `[]` | nach Kontrolle freigegebene Listen-IDs (aus dem Statusbericht) |
| `aufbewahrung.site_snapshots` | `5` | Datenstände auf der Website (je etwa 75 MB bei 11.500 Aktien; Grenze von GitHub Pages: 1 GB) |
| `aufbewahrung.archiv_snapshots` | `60` | Archive in den Release-Assets |
| `aufbewahrung.kurs_historie_tage` | `250` | Tageskurse im Zustand (mindestens 200: die Rechnung braucht 150 Kalendertage, der Erstimport lädt 200) |
| `betrieb.heartbeat_max_stunden` | `30` | danach zeigt die App „Keine aktuelle Prüfung“ |
| `github.release_tag` | `datenstand` | Release für Zustand und Archive |

## `config/methode.yaml` – Berechnung (versioniert)

Jede Änderung hier ist eine Methodenänderung: `methode_version` erhöhen und im CHANGELOG festhalten. Veröffentlichte Stände tragen ihre Methodenversion und den Fingerabdruck dieser Datei.

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `fenster.min_tage` / `max_tage` | `1` / `90` | Zeiträume (fest, Validierung verlangt genau 1–90) |
| `anker_max_luecke_tage` | `7` | Startsitzung höchstens so weit vor dem Ziel-Startdatum |
| `gewichte_gleichmaessigkeit` | `[0, 10, …, 100]` | genau elf Gewichtungen (Validierung) |
| `qualitaet.min_beobachtungen_trend` | `15` | Mindestzahl Tageskurse für Gleichmäßigkeit |
| `qualitaet.min_beobachtungen_rendite` | `2` | Mindestzahl Tageskurse für Kursrendite |
| `qualitaet.min_sitzungsabdeckung` | `49/50` | 98 % der erwarteten Sitzungen |
| `qualitaet.min_volumenabdeckung` | `4/5` | 80 % der Beobachtungen mit positivem Umsatz |
| `qualitaet.sprung_faktor` | `3.0` | Tagessprung > 3 oder < 1/3 → Prüfung |
| `qualitaet.nullumsatz_bewegung` | `0.10` | Bewegung > 10 % ohne Umsatz an Start/Ende → Prüfung |
| `qualitaet.split_pruefung_min_faktor` | `1.25` | Erkennung unbereinigter Splits |
| `qualitaet.impulstag_anteil`, `impulstag_min_rendite` | `0.5`, `0.10` | Hinweis „ein Tag erklärt mehr als die Hälfte der Bewegung“ |
| `qualitaet.duenner_handel_nullanteil`, `duenner_handel_sitzungen` | `0.2`, `20` | Hinweis „wenige aktive Handelstage“ |
| `ausgeschlossene_typen` | ETP, ETF, Fonds, Rechte, Optionsscheine, Anleihen, Zertifikate | laut Identitätsquelle kein Aktieninstrument |

## `config/boersen.yaml` – Referenzbörsen

Je Börse: Kalendercode (`exchange_calendars`), Zeitzone, Währung/Einheit, OpenFIGI-Börsencodes, Yahoo-Endung und -Codes, EODHD-Code, OTC-Kennzeichen, Ersatzkalender. Dazu `laenderpraeferenz` (ISIN-Präfix → bevorzugte Börsen) und `standard_praeferenz`. Siehe 04_Datenquellen_und_Abdeckung.

## `config/pruefungen.yaml` – manuelle Prüfentscheidungen

```yaml
kurssprung_entscheidungen:
  - isin: XX0000000000
    datum: 2026-09-15          # Sitzungstag des Sprungs bzw. der Bewegung ohne Umsatz
    entscheidung: freigegeben  # oder: zurueckhalten
    quelle: "Unternehmensmitteilung vom …"
    notiz: "Übernahmeangebot bestätigt"
```

Ohne Eintrag bleiben betroffene Fenster zurückgehalten (Status „Kapitalmaßnahme/Datenfehler prüfen“).

## Secrets und Umgebungsvariablen

| Name | Wo | Bedeutung |
|---|---|---|
| `DATA_PASSPHRASE` | GitHub-Secret (Pflicht) | Verschlüsselung von Daten, Sicherung und Veröffentlichung |
| `OPENFIGI_API_KEY` | GitHub-Secret (optional) | höheres Abfragelimit |
| `EODHD_API_KEY` | GitHub-Secret (optional) | nur mit `anbieter.kurse: eodhd` |
| `KURS_ANBIETER` | Umgebung (optional) | überschreibt `anbieter.kurse` für einen Lauf |
| `UNVERSCHLUESSELT_ERLAUBT` | Umgebung | `true` erlaubt Läufe ohne Passphrase – nur für Tests, nie für die öffentliche Website |
| `LOG_LEVEL` | Umgebung | `INFO` (Standard) oder `DEBUG`; Geheimnisse werden in Protokollen immer geschwärzt |
| `TRAKTIEN_CONFIG_DIR` | Umgebung | anderer Konfigurationsordner (Tests) |

## Workflow-Eingaben (manueller Start „Täglicher Lauf“)

| Eingabe | Wirkung |
|---|---|
| `erzwingen` | berechnet und veröffentlicht neu, auch wenn kein neuer Börsenschluss vorliegt |
| `zustand_neu_aufbauen` | verwirft den gespeicherten Zustand (Datenbank, Schlüsselparameter) und lädt alles neu – nötig nach Wechsel der Passphrase; dauert Stunden |

## App-Einstellungen

Auf dem Handy unter ☰ → Einstellungen: Farbschema („Wie das Handy“, Hell, Dunkel), Standardzeitraum, Standardgewichtung und Vergleichsfeld, Sicherung von Watchlist und Einstellungen als Datei, Offline-Speicher löschen, Zugangsschlüssel vergessen. Diese Einstellungen liegen nur im Browser des Geräts.
