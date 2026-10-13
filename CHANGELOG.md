# Änderungsprotokoll

Format: Version, Datum, Änderung, Begründung. Methodenänderungen (Fensterdefinition, Mindestbeobachtungen, Bereinigung, Perzentile, Gleichstandsregeln) erhöhen zusätzlich `methode_version` in `config/methode.yaml`. Veröffentlichte Datenstände tragen ihre Versionen und werden nie nachträglich verändert.

## 1.0.0 – 12.10.2026 (erste Fassung, noch kein produktiver Datenstand)

Umsetzung des Programmierauftrags v1.2. Bisher wurde kein echter Datenstand veröffentlicht; es gibt deshalb keine älteren Stände, die von einer Methodenänderung betroffen wären.

**Versionen:** Software 1.0.0 · Methode `tr-methode-1.2.0` · Kennzahlen `kennzahlen-v1` · Ranking `ranking-11w-v1` · Häufigkeit `frequency-v1` · Schnittstelle `static-api-v1` · Börsentabelle `boersen-v1`.

### Umfang

- Täglicher Serverlauf in GitHub Actions (06:00 Europe/Berlin, Wiederholungen 06:15, 06:45, 08:00) mit Checkpoints, Doppelstart-Schutz, verschlüsselter Sicherung im Release und Veröffentlichung auf GitHub Pages.
- Universum aus der öffentlichen TR-Instrumentenliste (Aktienabschnitt), Zuordnung jeder ISIN zu genau einer Referenznotierung, Börsenkalender je Referenzbörse, gemeinsamer Kursstichtag.
- Rechenkern: 90 Kalenderfenster, Qualitätsregeln (98 % Sitzungen, 80 % Volumen, 15 Kurse für Gleichmäßigkeit), Preis-OLS mit R², Kursrendite, MDD, alle elf Gewichtungen 0/100 bis 100/0 nativ und im gleichen Vergleichsfeld, Renditesieger 1–90, Häufigkeiten Top 1/3/10, Gesamtmaximum.
- Installierbare Web-App für das Galaxy S25+: Start, Rendite 1–90, Ranking, Gewichtungsvergleich, Häufigkeit mit Treffermatrix, Chart-Raster, Einzelcharts, Watchlist, Gesamtverzeichnis mit Status je Aktie, Datenstand & Betrieb, Methodik, Export (CSV, PNG), offline lesbar.

### Änderungen während der Entwicklung (vor der ersten Veröffentlichung)

| Änderung | Begründung |
|---|---|
| Neue Prüfregel: Kursbewegung über 10 % an einem Tag **ohne belegten Umsatz** am Fensterbeginn oder -ende hält das Fenster zurück (Status 13), freigebbar über `config/pruefungen.yaml` | Einzelne Geisterkurse ohne Handel könnten sonst ungeprüft zum Tagessieger werden (Auftrag: keine ungeprüften Spitzengewinner) |
| Residuen der OLS zentriert berechnet; nahezu konstante Reihen ergeben „R² nicht stabil bestimmbar“ statt eines Laufabbruchs | Numerische Stabilität; ein einzelner Sonderfall darf den Tageslauf nicht stoppen |
| Fensterlängen außerhalb 1–90 werden auch im Rechenkern abgewiesen | Auftrag T21 |
| Gesamtmaximum zählt dieselbe Aktie mit demselben tatsächlichen Zeitraum nicht als Gleichstand mit sich selbst; gleiche Zeiträume werden genannt | Keine Scheingleichstände (T95, T97) |
| Verwaiste Sperren aus einem abgebrochenen Runner werden beim nächsten Lauf freigegeben und als „abgebrochen“ protokolliert | Ein abgestürzter Lauf darf alle folgenden nicht blockieren |
| Kein `--soft-fail` im Workflow: ein fehlgeschlagener Lauf bleibt rot, der Status wird trotzdem veröffentlicht | GitHub soll per E-Mail benachrichtigen; der letzte gute Stand bleibt sichtbar |
| Bereitstellung auf GitHub Pages nur nach bestandener `verify-site`-Prüfung | Vorher hätten die mit `always()` laufenden Schritte die Website auch nach einer fehlgeschlagenen Prüfung (z. B. Geheimnis in einer Datei) hochgeladen |
| Datenbanksicherung wird lückenlos ausgetauscht (Zwischenname, löschen, umbenennen); `crypto.json` nur noch hochgeladen, wenn es fehlt | Vorher hätte ein Abbruch zwischen Löschen und Hochladen die einzige Sicherung gekostet |
| Angezeigte Stammdaten (Name, Ticker, Börse, Identität) gehören zum Idempotenzschlüssel; frühere Ticker und Symbole bleiben als Suchbegriffe erhalten | Ein Tickerwechsel am selben Stichtag ergibt eine neue Revision statt eines veralteten Tickers (T37, T50) |
| Aufbewahrung der Tageskurse im Zustand 250 statt 400 Tage | Die Rechnung braucht 150 Tage; kleinere Sicherung, schnellere Läufe |
| Diagramme: Pos1/Ende/Pfeiltasten scrollen die Seite nicht mehr mit; Zwei-Finger-Zoom auch dort, wo der Browser `touch-action` auf SVG-Elementen nicht beachtet | Bedienbarkeit auf Android und mit Tastatur (T77) |
| Kurzer Titel „Rendite 1–90“ in der App-Leiste | Langer Titel wurde neben Datum und Kennzeichen abgeschnitten |
| Workflows und Tests auf Python 3.13 vereinheitlicht | Dieselbe Version wie in den ausgeführten Tests |
| Lockdatei der App auf die öffentliche npm-Registry umgestellt | GitHub Actions erreicht nur die öffentliche Registry |
| Offene Datenbankverbindungen in `ci` und `restore-test` werden geschlossen | Ressourcenwarnungen in Tests; sauberes Beenden |
| Rückfallwert für `aufbewahrung.site_snapshots` im Code 5 statt 7 | Gleich dem dokumentierten und konfigurierten Wert |
| App-Build: Dateinamen aus dem Inhalt statt aus esbuilds `[hash]` | esbuilds Hash hängt vom Projektpfad ab; in GitHub Actions hätte die Prüfung „app/dist ist veraltet“ sonst immer angeschlagen |
| `.gitignore`: lokale Datenordner nur im Hauptverzeichnis ausgeschlossen | Das Muster `state/` hatte den Quellordner `app/src/state` ausgeschlossen; er fehlte im ersten Commit und ZIP |
| Vorschau-Build als eine HTML-Datei mit eingebetteten DEMO-Daten (`app/scripts/build_preview.mjs`); ohne Service Worker, Downloads, Drucken und Installation; übernimmt das Farbschema des umgebenden Rahmens | Die App lässt sich vor der GitHub-Einrichtung in Claude ansehen; echte Kursdaten werden nie eingebettet |
| `reportlab` in `backend/requirements-dev.txt` | Der PDF-Rundlauftest des Universum-Parsers lief lokal nur, weil reportlab dort vorinstalliert war; im ersten Lauf „Prüfung“ auf GitHub fehlte das Paket |
| Workflow „Prüfung“ zeigt fehlgeschlagene Tests als Hinweise in der Laufübersicht | Die Ursache ist sichtbar, ohne das Protokoll herunterzuladen |
