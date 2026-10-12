# Fehlerbehebung

Grundregel: Ein fehlgeschlagener oder unvollständiger Lauf ersetzt nie den letzten geprüften Stand. Die App zeigt weiter den letzten guten Datenstand mit seinem echten Datum und meldet die Störung. Den genauen Grund nennt das Protokoll des Laufs (GitHub → **Actions** → Lauf anklicken → Schritt „Täglicher Lauf“).

## Lauf und Datenquellen

| Meldung / Symptom | Ursache | Lösung |
|---|---|---|
| `Secret DATA_PASSPHRASE fehlt` (Lauf rot) | Secret nicht angelegt oder falsch geschrieben | Settings → Secrets and variables → Actions → `DATA_PASSPHRASE` anlegen. Ohne Passphrase bricht der Lauf absichtlich ab, damit nichts unverschlüsselt öffentlich wird. |
| „Die Passphrase passt nicht zum gespeicherten Datenstand.“ | Secret wurde geändert | Ursprüngliche Passphrase wieder eintragen – oder Lauf manuell mit „zustand_neu_aufbauen“ starten (alles wird neu geladen, dauert Stunden). |
| `OpenFIGI: API-Schlüssel ungültig` | `OPENFIGI_API_KEY` falsch oder abgelaufen | Schlüssel erneuern oder Secret löschen (dann ohne Schlüssel, langsamer). |
| Status „wartet auf Kursdaten“, Hinweis „Daten noch unvollständig“ | Anbieterlimit (HTTP 429) oder Zeitbudget erreicht | Nichts tun: Zwischenstände sind gespeichert, die nächste geplante Wiederholung setzt am selben Stichtag fort. Bleibt es über Tage so, drosselt Yahoo dauerhaft → siehe nächste Zeile. |
| Viele Einzelfehler „HTTP 401/403“ bei Yahoo | Yahoo blockiert inoffizielle Abfragen | Abwarten; `curl_cffi` muss installiert sein (steht in `requirements.txt`). Dauerhafte Lösung: vertraglicher Anbieter EODHD (`anbieter.kurse: eodhd`, 19,99 USD/Monat) – nur nach deiner Entscheidung. |
| `TR-Liste: HTTP 404` oder „Antwort ist kein PDF“ | Trade Republic hat die Adresse geändert | Neue Adresse der Instrumentenliste in `config/pipeline.yaml` → `universum.url` eintragen. Bis dahin rechnet der Lauf mit der zuletzt geprüften Liste weiter. |
| Statusbericht: neue Universumsliste „zur Prüfung“ zurückgehalten | Liste deutlich kleiner/größer (über 10 % Änderung), Aktienabschnitt nicht erkannt oder viele ungültige ISINs | Bericht des Laufs und „Datenquellen prüfen“ ansehen. Ist die neue Liste plausibel, ihre ID in `universum.freigegebene_versionen` eintragen. Ist der Parser schuld (geändertes PDF-Layout): `providers/tr_universe.py` anpassen. Die alte Liste bleibt bis dahin gültig. |
| Status „Teilstand“ | Für einzelne Börsen fehlten am Stichtag noch Schlusskurse | Normal kurz nach Börsenschluss. Spätere Wiederholungen ergänzen; welche Börsen fehlten, steht unter ☰ → Datenstand & Betrieb. |
| Lauf nach 330 Minuten abgebrochen; im Protokoll „Lauf ohne Abschluss beendet (Sperre beim nächsten Lauf freigegeben)“ | Zeitlimit oder abgebrochener Runner | Nichts tun: GitHub lässt nie zwei tägliche Läufe gleichzeitig zu, deshalb gibt der nächste Lauf die Sperre aus der Sicherung sofort frei, markiert den alten Lauf als „abgebrochen“ und setzt am letzten Checkpoint fort. Sofort neu starten: Actions → Täglicher Lauf → Run workflow. (Bei lokalen Läufen mit `traktien run` gilt eine Sperre erst nach 120 Minuten ohne Herzschlag als verwaist.) |
| „Anderer Lauf aktiv“ | Zwei Starts gleichzeitig | Gewollt: Der zweite Lauf beendet sich ohne Änderung (Doppelstart-Schutz). |
| Im Release „datenstand“ liegt `state.sqlite.tra.neu` | Der Austausch der Sicherung wurde unterbrochen (Netz, Abbruch) | Nichts tun: Der nächste Lauf verwendet eine vollständige Fassung (ohne Hauptfassung die `.neu`-Fassung) und räumt auf (08_Backup_und_Wiederherstellung). |

## Daten in der App

| Symptom | Bedeutung | Was tun |
|---|---|---|
| „Keine aktuelle Prüfung“ | Seit über 30 Stunden kein erfolgreicher Lauf | Actions-Seite prüfen. Häufige Ursachen: Zeitplan von GitHub deaktiviert (nach 60 Tagen ohne Aktivität → Actions → Täglicher Lauf → **Enable workflow**), Lauf rot (siehe oben), GitHub-Störung. |
| „Noch kein Datenstand veröffentlicht“ | Erster Lauf noch nicht fertig | Ersten Lauf abwarten bzw. starten (02_Einrichtung, Schritt 6). Es werden bewusst keine Beispielgewinner gezeigt. |
| Aktie fehlt in einer Rangliste | Sie erfüllt für diesen Zeitraum eine Bedingung nicht | ☰ → Alle Aktien & Abdeckung → Aktie suchen: Dort steht je Zeitraum der genaue Grund. „Nicht steigend“, „zu kurze Historie“ und „Daten fehlen“ sind verschiedene Zustände. |
| „Markt am Stichtag geschlossen“ | Feiertag der Heimatbörse am Kursstichtag | Kein Datenfehler; am nächsten Handelstag ist die Aktie wieder dabei. |
| „Schlusskurs am Stichtag fehlt“ | Börse war offen, Anbieter lieferte keinen Kurs | Meist am Folgetag behoben. Häuft es sich bei einer Börse, die Zuordnung (Symbol) prüfen. |
| „Kapitalmaßnahme/Datenfehler prüfen“ | Tagessprung > Faktor 3, möglicher unbereinigter Split oder starke Bewegung ohne Umsatz an Start/Ende | Mit verlässlicher Quelle prüfen (Unternehmensmitteilung, Börse) und in `config/pruefungen.yaml` freigeben oder zurückhalten. |
| Gleichmäßigkeitsliste leer bei kurzen Zeiträumen | Weniger als 15 echte Tageskurse | Erwartet bei etwa unter drei Wochen; reine Renditeliste ist verfügbar. |

## Handy

| Symptom | Lösung |
|---|---|
| „Der Zugangsschlüssel passt nicht“ | Genau die Passphrase aus dem Secret `DATA_PASSPHRASE` eingeben (Groß-/Kleinschreibung, Leerzeichen). |
| Nach Wechsel der Passphrase lädt nichts | ☰ → Einstellungen → „Schlüssel auf diesem Gerät vergessen“, neu eingeben. |
| „Neue App-Version verfügbar“ | „Aktualisieren“ tippen. Watchlist und Einstellungen bleiben erhalten. |
| „Offline nicht verfügbar“ in einer Ansicht | Diese Daten wurden auf dem Gerät noch nie geladen. Mit Netz einmal öffnen. |
| Watchlist weg | Browserdaten wurden gelöscht. Gesicherte Datei unter ☰ → Einstellungen → „Datei einlesen“ wiederherstellen. |
| Installieren wird nicht angeboten | Seite einmal neu laden; in Chrome ⋮ → „Zum Startbildschirm hinzufügen“. Die Adresse muss mit `https://` beginnen (GitHub Pages erfüllt das). |

## Veröffentlichung und Prüfung

| Meldung | Lösung |
|---|---|
| Bereitstellung: „Resource not accessible by integration“ oder fehlende Pages-Rechte | Settings → Pages → Source „GitHub Actions“; Settings → Actions → General → Workflow permissions „Read and write“. |
| Bereitstellung: Umgebung `github-pages` blockiert den Zweig | Settings → Environments → github-pages → Deployment branches: `main` erlauben. |
| Prüfung: „app/dist ist veraltet“ | `cd app && npm ci && npm run build`, danach `app/dist` einchecken. |
| Prüfung: Warnung „npm ci gescheitert“ | Die Lockdatei passt nicht zur Registry. `cd app && npm install && npm run build`, danach `app/package-lock.json` und `app/dist` einchecken. |
| Prüfung: Browser-Tests schlagen fehl | Protokoll zeigt die betroffene Ansicht; lokal mit `TR_E2E_SCREENSHOTS=bilder python -m unittest tests.e2e.test_mobile_app` Bildschirmfotos erzeugen. |
| `verify-site`: „enthält ein Geheimnis“ oder Entschlüsselungs-/Schemafehler | Bereitstellung stoppt absichtlich: Ohne bestandene Prüfung wird nichts hochgeladen, die bisherige Website bleibt. Ursache suchen (z. B. Passphrase versehentlich in einer Konfigurationsdatei) und entfernen. |
