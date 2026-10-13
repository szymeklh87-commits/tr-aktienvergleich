# Einrichtung und Betrieb

Diese Anleitung bringt das Projekt einmalig auf GitHub. Danach läuft alles selbstständig: Jeden Morgen rechnet GitHub Actions die Ranglisten neu und veröffentlicht die App auf GitHub Pages. Es entstehen im Standardaufbau **keine laufenden Kosten** (Begründung unten).

## Überblick

| Baustein | Wofür | Kosten |
|---|---|---|
| GitHub-Konto (kostenlos) + öffentliches Repository | Code, Zeitplan, Speicher des verschlüsselten Zustands | 0 € |
| GitHub Actions | täglicher Lauf 07:00 Europe/Berlin, Wiederholungen | 0 € (Standard-Runner in öffentlichen Repositories) |
| GitHub Pages | Adresse der App für das Handy | 0 € (öffentliche Repositories, GitHub Free) |
| Yahoo Finance (inoffiziell) | Tageskurse | 0 €, ohne Vertrag, ohne Zusage |
| OpenFIGI | ISIN → Börsennotierung | 0 €, kostenloser API-Schlüssel optional |
| EODHD (optional) | vertraglich geregelte Kurse statt Yahoo | 19,99 USD/Monat (Plan „EOD Historical All-World“) – **nur nach deiner Freigabe** |

Warum öffentlich? GitHub Pages ist im kostenlosen Tarif nur für öffentliche Repositories verfügbar. Deshalb sind alle veröffentlichten Kursdaten, die Ranglisten und die Sicherung mit deiner Passphrase verschlüsselt (AES-256-GCM). Öffentlich lesbar sind nur der Programmcode, die leere App-Hülle und drei Betriebsdateien ohne Kurse (`status.json` mit Laufstatus, `snapshots/index.json` mit Datum und Anzahl je Datenstand, `crypto.json` mit den nicht geheimen Schlüsselparametern).

## Schritt 1 – Repository anlegen

1. Bei <https://github.com> kostenlos registrieren (falls noch kein Konto).
2. Oben rechts **+** → **New repository**.
3. Name: `tr-aktienvergleich`, Sichtbarkeit **Public**, ohne README/Lizenz anlegen → **Create repository**.

## Schritt 2 – Projektdateien hochladen

Variante A (ohne Programmierkenntnisse, am PC): Das ZIP entpacken. Im neuen Repository **uploading an existing file** wählen und den **Inhalt** des entpackten Ordners (inklusive des Ordners `.github`) in das Browserfenster ziehen → **Commit changes**. Wichtig: Der Ordner `.github/workflows` muss mit hochgeladen werden; in manchen Dateiansichten ist er versteckt.

Variante B (mit Git):

```bash
git remote add origin https://github.com/<dein-name>/tr-aktienvergleich.git
git push -u origin main
```

Variante C: Claude kann das Hochladen übernehmen, sobald der Repository-Zugang in dieser Unterhaltung freigegeben ist.

## Schritt 3 – Passphrase und optionale Schlüssel hinterlegen

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Pflicht | Inhalt |
|---|---|---|
| `DATA_PASSPHRASE` | ja | Lange, zufällige Passphrase (zum Beispiel fünf bis sechs zufällige Wörter). Im Passwortmanager notieren – sie wird auf dem Handy einmal eingegeben. Ohne sie bricht der Lauf bewusst ab, damit keine Kursdaten unverschlüsselt öffentlich werden. |
| `OPENFIGI_API_KEY` | empfohlen | Kostenloser Schlüssel von <https://www.openfigi.com/api>. Beschleunigt die erste ISIN-Zuordnung stark (25 Anfragen je 6 Sekunden mit je 100 ISINs statt 25 Anfragen je Minute). |
| `EODHD_API_KEY` | nein | Nur, wenn du später auf den kostenpflichtigen Anbieter EODHD umstellst (siehe 05_Konfiguration). |

Die Passphrase lässt sich später nicht ändern, ohne den gespeicherten Zustand neu aufzubauen (Lauf mit „zustand_neu_aufbauen“).

## Schritt 4 – GitHub Pages einschalten

**Settings** → **Pages** → bei *Build and deployment* unter *Source* **GitHub Actions** wählen. Mehr ist nicht nötig; die Umgebung `github-pages` legt GitHub selbst an.

Falls Läufe mit „Resource not accessible by integration“ scheitern: **Settings** → **Actions** → **General** → *Workflow permissions* → **Read and write permissions** → Save.

## Schritt 5 – Datenquellen prüfen (einmalig, ca. 2 Minuten)

**Actions** → links **Datenquellen prüfen** → **Run workflow**. Der Lauf ruft die TR-Instrumentenliste, OpenFIGI und Yahoo mit wenigen Testabfragen ab und prüft die Börsenkalender. Der Bericht `datenquellen-bericht.json` liegt danach unter *Artifacts* des Laufs (Anzahl ISINs im Aktienabschnitt, erkannte Abschnitte, Beispielabrufe). Schlägt ein Teil fehl, steht der Grund im Protokoll – siehe 06_Fehlerbehebung.

## Schritt 6 – Erster vollständiger Lauf

**Actions** → **Täglicher Lauf** → **Run workflow** (ohne Häkchen). Der erste Lauf ist der aufwendigste:

- Zuordnung aller ISINs zu einer Referenzbörse (OpenFIGI, ohne Schlüssel langsam),
- 200 Kalendertage Kurshistorie für jede Notierung (Yahoo etwa 2,5 Abrufe je Sekunde),
- danach Berechnung und Veröffentlichung.

Bei rund 10.000 Aktien dauert das geschätzt mehrere Stunden (noch nicht gemessen: die Datenquellen waren in der Entwicklungsumgebung gesperrt). Der Lauf speichert Zwischenstände (Checkpoints) und wird von den geplanten Läufen fortgesetzt; ein abgebrochener Lauf verliert keine bereits geladenen Kurse. Den Fortschritt zeigt das Protokoll des Laufs, später auch die App unter ☰ → Datenstand & Betrieb.

Wenn der Lauf grün ist, steht die Adresse der App unter **Settings** → **Pages** (Form `https://<dein-name>.github.io/tr-aktienvergleich/`).

## Schritt 7 – Handy

Adresse auf dem S25+ öffnen, installieren und Passphrase eingeben – siehe 01_Kurzanleitung_Handy.

## Täglicher Betrieb

| Uhrzeit (Europe/Berlin) | Lauf |
|---|---|
| 07:00 | regulärer Lauf: neuer Börsenschluss des Vortags wird berechnet und veröffentlicht (bis 1.4: 06:00) |
| 07:15, 07:45, 09:00 | Wiederholungen: setzen einen unvollständigen Lauf fort oder bestätigen „kein neuer Börsenschluss“ |
| jederzeit | von Hand: in der App ☰ → **Jetzt aktualisieren** → „Lauf auf GitHub starten“, oder direkt Actions → Täglicher Lauf → Run workflow. Neue Schlusskurse frühestens etwa eine Stunde nach US-Börsenschluss (meist gegen 23 Uhr) |

- Kursstichtag ist der jüngste Handelstag, dessen Schlusskurse an allen an diesem Tag geöffneten Börsen feststehen (plus 60 Minuten Nachlieferungsfrist). Um 07:00 ist das der Vortag; Tokio und Sydney handeln zu dieser Zeit schon den neuen Tag und werden dafür nicht abgewartet.
- Fehlen Kurse einzelner Börsen noch, wartet der Lauf auf die nächste Wiederholung. Erst der letzte geplante Versuch (09:00) entscheidet: deutlich markierter **Teilstand** (ab 1.5.1: mindestens 75 % der erwarteten Aktien mit Schlusskurs am Stichtag; bis 1.5.0: 90 % der Börsen) oder Fehlschlag mit E-Mail von GitHub. Einen Teilstand sofort erzwingen: Actions → Täglicher Lauf → Run workflow mit „erzwingen“. Von Hand gestartete Läufe („Jetzt aktualisieren“) warten in diesem Fall nur weiter – sie zählen nicht als Wiederholung und erzeugen keinen roten Lauf.
- GitHub kann geplante Läufe verzögern oder bei hoher Last verwerfen. Deshalb gibt es Wiederholungen und eine Herzschlag-Prüfung: Meldet sich der Lauf länger als 30 Stunden nicht, zeigt die App „Keine aktuelle Prüfung“.
- GitHub deaktiviert Zeitpläne in öffentlichen Repositories nach 60 Tagen ohne Aktivität. Der Lauf schreibt deshalb spätestens alle 45 Tage einen Aktivitätsnachweis (`ops/letzte-aktivitaet.txt`).
- Bei einem fehlgeschlagenen geplanten Lauf schickt GitHub eine E-Mail an das Konto, das den Zeitplan zuletzt geändert hat.

## Laufzeiten und Größen (gemessen, siehe 07_Testbericht)

Lasttest mit 11.500 synthetischen Aktien (2 vCPU): Rechenkern 43 s, verschlüsselte Veröffentlichung 57 s, 74 MB je Datenstand, 411 MB Arbeitsspeicher. Täglich dominiert der Kursabruf (eine Anfrage je Notierung, gedrosselt auf 2,5 je Sekunde, also gut eine Stunde bei 10.000 Notierungen). Die Website behält fünf Datenstände (unter der 1-GB-Grenze von GitHub Pages), die Release-Assets 60 Archive.

Ab 1.3 lädt der erste Lauf zusätzlich die Wochenwerte für die Umschichtungs-Regel (bis 3 Jahre je Aktie mit Ø Tagesumsatz ab 2 Mio. USD; höchstens 40 Minuten, der Rest im nächsten Lauf). Danach kommen täglich nur neu aufgenommene Aktien und Aktien nach einem Split dazu. Die gesicherte Datenbank wächst dadurch um die Wochenwerte (einige Zehntausend Zeilen je 100 Aktien).

## Monatliche Kostenannahmen

| Posten | Annahme | Monatlich |
|---|---|---|
| GitHub Actions | öffentliches Repository, Standard-Runner | 0 € |
| GitHub Pages | öffentliches Repository, < 1 GB, < 100 GB Datenverkehr | 0 € |
| Release-Assets (verschlüsselter Zustand, Archive) | öffentliches Repository | 0 € |
| Yahoo Finance | inoffiziell, kein Vertrag | 0 € |
| OpenFIGI | kostenloser Schlüssel | 0 € |
| **Summe Standardaufbau** | | **0 €** |
| optional EODHD „EOD Historical All-World“ | 100.000 Abrufe/Tag, nur nach Freigabe | 19,99 USD (199 USD jährlich) |

Die kostenlose Lösung hat Grenzen: Yahoo ist keine vertraglich zugesicherte Quelle und kann Abrufe drosseln oder sperren. Es gibt keine erfundene kostenlose Vollabdeckung – welche Aktien tatsächlich berechnet wurden, zeigt jede Veröffentlichung in der Abdeckungsbilanz.

## Änderungen am Projekt

Jede Änderung im Repository startet den Workflow **Prüfung** (alle Tests, App-Build, Browser-Tests). Nach Änderungen an der App `cd app && npm ci && npm run build` ausführen und `app/dist` mit einchecken – die Prüfung meldet sonst „app/dist ist veraltet“.

## Abschalten

**Actions** → **Täglicher Lauf** → **⋯** → **Disable workflow**. Die zuletzt veröffentlichte App bleibt bis zum Löschen des Repositorys erreichbar.
