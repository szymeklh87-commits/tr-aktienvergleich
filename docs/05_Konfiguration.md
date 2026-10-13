# Konfigurationsreferenz

Alle Einstellungen liegen als Textdateien im Ordner `config/` und in den Workflows unter `.github/workflows/`. Geheimnisse stehen nie in diesen Dateien, sondern ausschließlich in den GitHub-Secrets.

## Uhrzeit des täglichen Laufs

Die Uhrzeit steht an zwei Stellen und muss an beiden geändert werden:

1. `.github/workflows/taeglich.yml` – maßgeblich für GitHub:
   ```yaml
   schedule:
     - cron: '0 7 * * *'        # Minute Stunde – hier 07:00 (Standard ab 1.5, vorher 06:00)
       timezone: 'Europe/Berlin'
     - cron: '15 7 * * *'       # Wiederholungen 07:15, 07:45, 09:00
       timezone: 'Europe/Berlin'
   ```
2. `config/pipeline.yaml` → `zeitplan.uhrzeit` und `zeitplan.wiederholungen_minuten` – Anzeige in der App (ein Test prüft, dass beide Stellen übereinstimmen). Ob ein Lauf pünktlich war, ergibt sich aus dem Zeitplaneintrag, der ihn ausgelöst hat.

Früher als etwa 05:00 ist nicht sinnvoll: US-Schlusskurse stehen ab etwa 23:00 Uhr deutscher Zeit plus Nachlieferungsfrist fest.

## `config/pipeline.yaml` – Betrieb

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `zeitplan.uhrzeit`, `zeitplan.zeitzone` | `07:00`, `Europe/Berlin` | Anzeige in der App (Erststandard laut Auftrag vom 13.10.2026) |
| `zeitplan.wiederholungen_minuten` | `[15, 45, 120]` | Abstand der Wiederholungen |
| `zeitplan.max_versuche` | `4` | geplante Versuche je Stichtag; der letzte entscheidet über Teilstand oder Fehler (von Hand gestartete Läufe zählen nicht) |
| `stichtag.karenz_minuten_nach_schluss` | `60` | Nachlieferungsfrist nach regulärem Börsenschluss |
| `vollstaendigkeit.markt_geliefert_ab` | `0.80` | Anteil Aktien einer Börse mit Stichtagskurs, ab dem die Börse als geliefert gilt |
| `vollstaendigkeit.teilstand_mindestens_aktien` | `0.75` | ab 1.5.1: Mindestanteil der erwarteten Aktien mit Schlusskurs am Stichtag, damit der letzte geplante Versuch einen gekennzeichneten Teilstand veröffentlicht (bis 1.5.0: `teilstand_mindestens` = 90 % der Börsen) |
| `anbieter.kurse` | `yahoo` | `yahoo` (kostenlos, inoffiziell) oder `eodhd` (kostenpflichtig, Secret `EODHD_API_KEY`) |
| `abruf.erstimport_kalendertage` | `200` | Historie beim ersten Abruf einer Notierung |
| `abruf.inkrementell_ueberlappung_tage` | `10` | Überlappung bei täglichen Abrufen (erkennt nachträgliche Korrekturen) |
| `abruf.vollabgleich_alle_tage` / `vollabgleich_max_pro_lauf` | `30` / `800` | regelmäßiger vollständiger Neuabruf (Splits, Korrekturen), auf Läufe verteilt |
| `abruf.max_laufzeit_minuten` | `300` | Zeitbudget; danach Checkpoint und Fortsetzung im nächsten Lauf |
| `abruf.identitaet_max_pro_lauf`, `identitaet_max_sekunden` | `4000`, `3600` | Begrenzung der ISIN-Zuordnung je Lauf |
| `abruf.identitaet_pruefung_alle_tage` | `45` | erneute Prüfung der Zuordnung |
| `abruf.boersenplatz_max_sekunden` | `900` | Zeitbudget für den Abgleich mit dem zweiten Börsenplatz (läuft nur, wenn veröffentlicht wird) |
| `abruf.boersenplatz_pruefung_alle_tage` | `45` | so lange wird die Wahl des zweiten Börsenplatzes je ISIN wiederverwendet |
| `abruf.langhistorie_max_pro_lauf`, `langhistorie_max_sekunden` | `6000`, `2400` | Umschichtungs-Regel: Langabrufe (bis 3 Jahre Wochenwerte) je Lauf. Beim ersten Mal etwa 25–35 Minuten (2,5 Abrufe je Sekunde), danach nur neu aufgenommene Aktien und Splits; der Rest folgt im nächsten Lauf |
| `abruf.kuerzel_alternativen_max_pro_lauf`, `kuerzel_alternativen_max_sekunden`, `kuerzel_alternativen_wiederholen_tage` | `300`, `900`, `30` | Notierungen, für die der Kursanbieter keine Kurse kennt: so viele Notierungen je Lauf (und so viele Sekunden) werden mit einer anderen Schreibweise des Kürzels und über die Suche nach der ISIN an derselben Börse erneut versucht. Erfolglose Suchen werden frühestens nach 30 Tagen wiederholt (Abschnitt „Kürzel ohne Kursdaten“ in 04_Datenquellen_und_Abdeckung) |
| `universum.url` | TR-PDF | Quelle der Aktienliste |
| `universum.min_eintraege` | `1000` | weniger Einträge → neue Liste wird zurückgehalten |
| `universum.max_aenderung_ohne_pruefung` | `0.10` | mehr Änderung → Prüfung nötig |
| `universum.freigegebene_versionen` | `[]` | nach Kontrolle freigegebene Listen-IDs (aus dem Statusbericht) |
| `aufbewahrung.site_snapshots` | `5` | Datenstände auf der Website (je etwa 97 MB bei 11.500 Aktien, gemessen mit 1.1; Grenze von GitHub Pages: 1 GB) |
| `aufbewahrung.archiv_snapshots` | `60` | Archive in den Release-Assets |
| `aufbewahrung.kurs_historie_tage` | `250` | Tageskurse im Zustand (mindestens 200: die Rechnung braucht 150 Kalendertage, der Erstimport lädt 200) |
| `betrieb.heartbeat_max_stunden` | `30` | danach zeigt die App „Keine aktuelle Prüfung“ |
| `github.release_tag` | `datenstand` | Release für Zustand und Archive |

## `config/methode.yaml` – Berechnung (versioniert)

Jede Änderung hier ist eine Methodenänderung: `methode_version` erhöhen und im CHANGELOG festhalten. Veröffentlichte Stände tragen ihre Methodenversion und den Fingerabdruck dieser Datei.

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `fenster.min_tage` / `max_tage` | `1` / `90` | Zeiträume (fest, Validierung verlangt genau 1–90) |
| `gruppen_version` | `gruppen-v1` | Gruppenvergleich A/B (ab 1.4): Gruppe B = Ø Tagesumsatz ≥ `umsatz.schwelle_usd`, alle elf Gewichtungen mit eigener Vergleichsmenge; Häufigkeit nach Platz 1, Top 3, Top 10, ISIN. Die Schwelle steht im Abschnitt `umsatz` |
| `anker_max_luecke_tage` | `7` | Startsitzung höchstens so weit vor dem Ziel-Startdatum |
| `gewichte_gleichmaessigkeit` | `[0, 10, …, 100]` | genau elf Gewichtungen (Validierung) |
| `qualitaet.min_beobachtungen_trend` | `15` | Mindestzahl Tageskurse für Gleichmäßigkeit |
| `qualitaet.min_beobachtungen_rendite` | `2` | Mindestzahl Tageskurse für Kursrendite |
| `qualitaet.min_sitzungsabdeckung` | `4/5` | ab Methode 1.8.0: mindestens 80 % der erwarteten Sitzungen mit Kurs (bis 1.7.0: `49/50` = 98 %) |
| `qualitaet.fehlende_sitzungen_immer_erlaubt` | `1` | so viele fehlende Sitzungen schließen nie aus, auch wenn der Anteil darunter liegt (ab 1.8.0; vorher 0) |
| `qualitaet.min_volumenabdeckung` | `4/5` | 80 % mit positivem Umsatz |
| `qualitaet.volumen_bezug` | `beobachtungen` | Bezug der Volumenschwelle: `beobachtungen` (Kurstage, wie im Ausgangsmodell) oder `sitzungen` (erwartete Börsentage) |
| `vorherige_regeln` | Regeln von 1.7.0 | Zulassungsregeln der Vorversion (gleiche Schlüssel wie oben); jeder Lauf rechnet zusätzlich danach und veröffentlicht den Unterschied (`method_comparison`) |
| `aenderungen_gegenueber_vorversion` | zwei Sätze | Texte zum Methodenwechsel, erscheinen im Manifest und in der App |
| `qualitaet.sprung_faktor` | `3.0` | Tagessprung > 3 oder < 1/3 → Prüfung |
| `qualitaet.nullumsatz_bewegung` | `0.10` | Bewegung > 10 % ohne Umsatz an Start/Ende → Prüfung |
| `qualitaet.split_pruefung_min_faktor` | `1.25` | Erkennung unbereinigter Splits |
| `qualitaet.impulstag_anteil`, `impulstag_min_rendite` | `0.5`, `0.10` | Hinweis „ein Tag erklärt mehr als die Hälfte der Bewegung“ |
| `qualitaet.duenner_handel_nullanteil`, `duenner_handel_sitzungen` | `0.2`, `20` | Hinweis „wenige aktive Handelstage“ |
| `ausgeschlossene_typen` | ETP, ETF, Fonds, Rechte, Optionsscheine, Anleihen, Zertifikate | laut Identitätsquelle kein Aktieninstrument |

### Abschnitt `umsatz` (ab 1.1) und Übernahmemuster

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `umsatz.sitzungen` | 20 | letzte vollständig abgeschlossene Sitzungen der Referenzbörse bis zum Stichtag |
| `umsatz.min_sitzungen_mit_umsatz` | 16 | davon mindestens mit positivem Volumen |
| `umsatz.schwelle_usd` | 10000000 | Aufnahme in „Höchste Kursrendite – Ø Tagesumsatz mindestens …“ |
| `umsatz.sehr_niedrig_usd` | 1000000 | Kennzeichen „sehr niedriger Umsatz“ in „Höchste Kursrendite“ |
| `umsatz.wechselkurs_max_alter_tage` | 5 | ältester zulässiger EZB-Kurs vor einer Sitzung |
| `qualitaet.uebernahme_sprung_min` | 0.15 | Übernahmemuster: Tagesanstieg ab 15 % … |
| `qualitaet.uebernahme_ruhe_max` | 0.01 | … danach jede Tagesbewegung höchstens ±1 % … |
| `qualitaet.uebernahme_ruhe_sitzungen` | 3 | … an mindestens 3 Sitzungen bis zum Fensterende |

### Abschnitt `boersenplatz` (ab 1.2)

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `boersenplatz.version` | `boersenplatz-v2` | Version des Abgleichs (steht im Manifest); v2 seit 1.5.1: Kalender des zweiten Platzes, kein Ausweichen bei Lieferlücken |
| `boersenplatz.plaetze` | 10 | geprüft werden Aktien unter den ersten 10 Plätzen von Ranking 1 oder 2 (in mindestens einem Zeitraum), dann für alle ihre Zeiträume; `0` schaltet den Abgleich ab |
| `boersenplatz.bevorzugt` | `[XETR, XFRA]` | Reihenfolge der Vergleichsbörsen; danach die Standardreihenfolge aus `boersen.yaml`, OTC-Märkte nie |
| `boersenplatz.schwelle_wertentwicklung` | 0.10 | auffällig, wenn Endkurs/Startkurs am zweiten Platz um mehr als 10 % von der Referenz abweicht |
| `boersenplatz.schwelle_endkurs` | 0.10 | auffällig, wenn der Endkurs (umgerechnet) um mehr als 10 % abweicht |
| `boersenplatz.max_abstand_tage` | 4 | Hatte der zweite Platz am Start- bzw. Enddatum keine Sitzung: Schlusskurs seiner letzten Sitzung davor, höchstens so viele Kalendertage früher; sonst „Vergleichskurse fehlen“ |
| `boersenplatz.max_aktien` | 600 | Obergrenze je Lauf (beste Plätze zuerst) |

Jede Änderung dieser Werte ist eine Methodenänderung (neue `methode_version`, Eintrag im CHANGELOG).

### Abschnitt `umschichtung` (ab 1.3)

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `umschichtung.standard` | `{aktien: 5, rhythmus: monatlich, trend_wochen: 13, kapital: 10000}` | Variante, die die App zuerst zeigt; muss unter den Varianten sein |
| `umschichtung.varianten.aktien` | `[5, 10]` | Anzahl gehaltener Aktien N (je 1/N) |
| `umschichtung.varianten.rhythmus` | `[monatlich, woechentlich]` | Prüftag: erster Freitag im Monat bzw. jeder Freitag |
| `umschichtung.varianten.trend_wochen` | `[13, 4]` | Trendzeitraum L in Wochen |
| `umschichtung.varianten.kapital` | `[5000, 10000, 25000]` | Startkapital im Rückblick (wirkt über die festen Orderkosten und den Pauschbetrag) |
| `umschichtung.haltepuffer_faktor` | `2` | gehalten wird bis Platz 2 × N |
| `umschichtung.anteil_toleranz` | `0.05` | gehaltene Positionen nur angleichen, wenn mehr als 5 Prozentpunkte von 1/N entfernt |
| `umschichtung.kosten.order_eur` / `spanne` | `1.0` / `0.001` | Kosten je Order und Kursabschlag |
| `umschichtung.kosten.steuersatz` / `freibetrag_eur` | `0.26375` / `1000` | Abgeltungsteuer mit Solidaritätszuschlag; Sparerpauschbetrag je Kalenderjahr |
| `umschichtung.auswahl.min_umsatz_usd` / `umsatz_wochen` | `10000000` / `4` | Ø Tagesumsatz der Kandidaten über die letzten Wochen |
| `umschichtung.auswahl.min_anteil_umsatztage` | `0.8` | Anteil Sitzungen mit Umsatz in diesen Wochen |
| `umschichtung.auswahl.min_abdeckung` | `0.9` | Anteil Sitzungen mit Kurs im Trendzeitraum |
| `umschichtung.auswahl.max_sprung_faktor` | `3` | größere Tagesbewegung → Datenfehler-Verdacht, keine Aufnahme |
| `umschichtung.langhistorie.jahre` | `3` | Länge des Rückblicks |
| `umschichtung.langhistorie.vorauswahl_min_umsatz_usd` | `2000000` | Langhistorie für Aktien ab diesem heutigen Ø Umsatz |

Alle Varianten werden in jedem Lauf gerechnet (24 Kombinationen); die App wählt nur aus. Jede Änderung ist eine Methodenänderung.

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
| `nur_website` | stellt nur die Website neu bereit (z. B. nach einem App-Update): App-Hülle neu, Status und veröffentlichte Datenstände unverändert aus der Sicherung; kein Kursabruf, keine Berechnung, dauert wenige Minuten |

## App-Einstellungen

Auf dem Handy unter ☰ → Einstellungen: Farbschema („Wie das Handy“, Hell, Dunkel), Standardzeitraum, Standardgewichtung und Vergleichsfeld, Sicherung von Watchlist und Einstellungen als Datei, Offline-Speicher löschen, Zugangsschlüssel vergessen. Diese Einstellungen liegen nur im Browser des Geräts.
