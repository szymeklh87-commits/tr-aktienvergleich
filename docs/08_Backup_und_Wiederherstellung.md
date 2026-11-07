# Sicherung und Wiederherstellung

Der tägliche Lauf hat keinen dauerhaften Server: Jeder Lauf startet auf einem frischen GitHub-Runner, holt sich den Zustand aus der Sicherung, arbeitet und sichert ihn wieder. Die Wiederherstellung wird damit **jeden Tag tatsächlich ausgeführt** – zusätzlich prüft ein eigener Workflow sie monatlich.

## Was wo gesichert wird

Alles liegt als Asset im Release **„datenstand“** des Repositorys (GitHub → Releases; als Vorabversion markiert). Alle Inhalte außer `crypto.json` sind mit der Passphrase verschlüsselt (AES-256-GCM, TRA1-Container, Format in 11_Datenvertrag_API).

| Inhalt | Asset | Wann geschrieben | Aufbewahrung |
|---|---|---|---|
| Zustand: TR-Listenversionen, Identitäten und Notierungen, Tageskurse mit Revisionen, Kapitalmaßnahmen, Prüfentscheidungen, Läufe mit Protokoll, Verzeichnis der Datenstände | `state.sqlite.tra` | während des Kursabrufs in Abständen von mindestens 15 Minuten (Checkpoint), bei Drosselung durch den Anbieter sofort, und am Ende jedes Laufs | jeweils die neueste Fassung |
| Zwischenstand beim Austausch | `state.sqlite.tra.neu` | nur für Sekunden während des Austauschs | wird nach dem Umbenennen entfernt |
| Ältere Fassungen der Datenbank (ab 1.22, Befund F20) | `state-<Datum>.sqlite.tra` | beim ersten Sichern eines neuen Tages: die bisherige Fassung wird umbenannt statt gelöscht (kein zusätzlicher Upload) | die vom Vortag und je Kalenderwoche die erste der letzten 15 Tage – höchstens vier, eine davon fast immer ein bis zwei Wochen alt |
| Schlüsselparameter (Salt, Iterationen, Prüfwert – **kein Geheimnis**) | `crypto.json` | einmal beim ersten Lauf | dauerhaft |
| Veröffentlichter Datenstand (alle Dateien eines Snapshots) | `site-<snapshot>.tar` | nach jeder Veröffentlichung | die neuesten 60 (`aufbewahrung.archiv_snapshots`) |
| Prüfnachweis: alle berechneten Kennzahlen (auch nicht freigegebene), Eingangsreihen, Manifest | `evidence-<snapshot>.tra` | mit jedem Datenstand | wie die Datenstand-Archive |

Die Website auf GitHub Pages zeigt die neuesten 3 Datenstände, einen Zwischenstand mitgezählt (`aufbewahrung.site_snapshots`, bis 14.10.2026: 5); ältere bleiben als Archiv im Release.

### Austausch ohne Lücke

Die Datenbanksicherung wird nie „erst gelöscht, dann hochgeladen“. Ablauf: neue Fassung als `state.sqlite.tra.neu` hochladen → alte `state.sqlite.tra` löschen → neue umbenennen. Bricht der Upload ab, bleibt die alte Fassung unverändert; vorübergehende Serverfehler (HTTP 5xx, 429, Verbindungsabbruch) wiederholt er ab 1.15 bis zu viermal. Bricht der Vorgang nach dem Löschen ab, liegt die neue vollständige Fassung als `.neu` vor; der nächste Lauf liest sie und bringt den Namen in Ordnung. Unvollständig hochgeladene Assets (GitHub-Status ungleich `uploaded`) werden nie gelesen. `crypto.json` wird nur hochgeladen, wenn es fehlt.

### Ältere Fassungen der Datenbank (ab 1.22)

Bis 1.21 gab es nur die neueste Datenbankfassung (Befund F20). Ab 1.22 bleiben ältere Fassungen erhalten: Stammt die
bisherige Sicherung von einem früheren Tag (Berliner Zeit), wird sie beim Austausch zu `state-<Tag>.sqlite.tra` umbenannt
statt gelöscht. Aufbewahrt werden die Fassung vom Vortag und je Kalenderwoche die erste der letzten 15 Tage (höchstens vier,
je etwa 130 MB). Ist die neueste Sicherung nicht verwendbar (fehlt, beschädigt, nicht entschlüsselbar), lädt der nächste Lauf
die neueste ältere Fassung, meldet das als Warnung „Zustand aus älterer Sicherung“ und ruft die fehlenden Tage erneut ab. Beim
bewussten Neuaufbau („zustand_neu_aufbauen“) weicht er nie auf eine ältere Fassung aus.

Alle Fassungen liegen im selben Release. Eine zweite, von GitHub unabhängige Kopie bräuchte einen weiteren Speicherdienst mit
eigenem Konto – das entscheidest du; die Daten lassen sich ohnehin aus den Quellen neu aufbauen (siehe unten).

### Warum genügt das?

Die Datenbank ist im Kern ein Zwischenspeicher der Anbieterdaten (Kurse, Zuordnungen) plus Laufprotokoll. Sie lässt sich aus den Quellen vollständig neu aufbauen (Lauf mit „zustand_neu_aufbauen“, dauert Stunden). Die veröffentlichten Ergebnisse selbst sind unabhängig davon append-only in den 60 Datenstand- und Nachweisarchiven gesichert.

## Wiederherstellen

### Automatisch (täglich)

Jeder Lauf lädt `crypto.json` und `state.sqlite.tra` auf den frischen Runner, prüft die Passphrase gegen den Prüfwert, entschlüsselt die Datenbank und prüft sie mit `PRAGMA integrity_check`. Schlägt etwas davon fehl, bricht der Lauf ab, ohne etwas zu überschreiben; die App zeigt weiter den letzten Stand und meldet die fehlende Prüfung.

### Monatlicher Wiederherstellungstest

Workflow **„Sicherung prüfen“** (jeden 1. des Monats, 09:30 Uhr, oder manuell: Actions → Sicherung prüfen → Run workflow). Er lädt die echte Sicherung aus dem Release, entschlüsselt sie in einem leeren Verzeichnis und prüft sie mit `PRAGMA integrity_check`. Danach sichert er sie erneut, stellt diese Sicherung in einem zweiten leeren Verzeichnis wieder her und vergleicht die Zeilenzahlen der wichtigen Tabellen. Ab 1.22 lädt und prüft er zusätzlich jede ältere Fassung (`aeltere_fassungen` im Ergebnis: Name, ok, Zahl der Läufe und Tageskurse). Rot = Sicherung nicht verwendbar → GitHub schickt eine E-Mail.

### Manuell auf dem eigenen Rechner

Voraussetzungen: Python 3.13, `pip install -r backend/requirements.txt`, ein GitHub-Token mit Lesezugriff auf das Repository (Settings → Developer settings → Fine-grained token, Berechtigung „Contents: Read“).

```bash
export GITHUB_REPOSITORY=<dein-name>/tr-aktienvergleich
export GITHUB_TOKEN=<token>
export DATA_PASSPHRASE='<deine Passphrase>'
PYTHONPATH=backend python -m traktien restore-test --state-dir wiederherstellung --aus-release
```

Danach liegt die entschlüsselte Datenbank unter `wiederherstellung/state.sqlite` (lesbar mit jedem SQLite-Programm). Der Ordner `wiederherstellung/` steht in `.gitignore` und darf nicht eingecheckt werden.

### Website wiederherstellen

Die Website wird bei jedem Lauf aus den Archiven im Release neu zusammengesetzt. Fehlt sie (z. B. Pages versehentlich abgeschaltet): Pages wieder einschalten (02_Einrichtung, Schritt 4) und „Täglicher Lauf“ manuell starten. Ein Lauf ohne neuen Börsenschluss veröffentlicht die Website trotzdem neu.

## Wenn etwas verloren geht

| Fall | Folge | Vorgehen |
|---|---|---|
| Passphrase vergessen | Sicherung und Archive sind nicht mehr lesbar (gewollt: niemand ohne Passphrase kann sie lesen) | Neue Passphrase als Secret, Lauf mit „zustand_neu_aufbauen“. Ältere Datenstände sind dann verloren. |
| Passphrase versehentlich geändert | Lauf bricht mit „Die Passphrase passt nicht zum gespeicherten Datenstand.“ ab, nichts wird überschrieben | Alte Passphrase wieder eintragen |
| Release „datenstand“ gelöscht | Zustand und Archive weg | Der nächste Lauf baut alles neu auf (Stunden) und legt neue Schlüsselparameter an. Bis ein neuer Datenstand fertig ist, zeigt die App „Noch kein Datenstand veröffentlicht“; auf dem Handy muss die Passphrase einmal neu eingegeben werden. |
| Datenbank inhaltlich falsch (z. B. fehlerhafte Anbieterkurse) | Korrekturen erkennt der Lauf beim regelmäßigen Vollabgleich (alle 30 Tage je Notierung) und legt eine neue Revision an | Bei Bedarf Lauf mit „zustand_neu_aufbauen“ |

## Prüfergebnisse (12.10.2026)

- `python -m traktien restore-test --state-dir build/demo-state` (DEMO-Zustand): **wiederherstellung_ok: true** – instrument 198/198, listing 195/195, daily_bar 26.575/26.575, run 1/1, snapshot_manifest 1/1, universe_member 198/198.
- `test_T55_backup_restores_in_clean_environment`: verschlüsselte Sicherung in einem sauberen Verzeichnis wiederhergestellt, Tabellen gleich, falscher Schlüssel abgewiesen – bestanden.
- `test_ci_flow.test_full_github_cycle_on_fresh_runners`: drei Läufe auf jeweils frischem Verzeichnis gegen eine nachgebildete GitHub-API; der zweite und dritte Lauf arbeiten ausschließlich mit dem wiederhergestellten Zustand – bestanden.
- `ReleaseReplaceTests` (5 Tests): abgebrochener Upload (nach vier Versuchen, alte Fassung bleibt), vorübergehender Serverfehler wird wiederholt, Client-Fehler wird nicht wiederholt, abgebrochenes Umbenennen, Rückgriff auf den Zwischenstand – bestanden.

Noch offen: Der Wiederherstellungstest gegen ein **echtes** GitHub-Release. Er läuft automatisch, sobald das Repository eingerichtet ist (erster Lauf von „Sicherung prüfen“ am nächsten Monatsersten oder manuell gestartet).
