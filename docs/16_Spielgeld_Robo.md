# Spielgeld-Robo („Pilot“) – Bedienung und Betrieb

Stand: 31.10.2026 (Gesamtauftrag, Abschnitte 29–32). Der Spielgeld-Robo handelt **nur mit Spielgeld**: virtuelle Orders mit
echten verfügbaren Kursen (PAPER) bzw. synthetischen Kursen (DEMO). Es gibt keinen Weg zu einem Broker, keine echten Orders und
keine Anlageberatung. Die App zeigt nur an und nimmt Wünsche entgegen; entschieden und gebucht wird im täglichen Lauf.

## 1. Was im täglichen Lauf passiert

Nach der Veröffentlichung der Ranglisten führt derselbe Rechenstand alle Spielgelddepots einen Datenstichtag weiter
(`aktienpilot/tageslauf.py`):

1. Kursreihen der Leitindizes (Marktfilter) und der Kern-ETFs (Welt, Geldmarkt) aktualisieren – eigener Abruf, getrennt vom
   Kursabruf der Aktien.
2. Spitzenplätze dieses Standes archivieren (Variante B „Platz an vergangenen Stichtagen“).
3. Eingänge aus der App übernehmen (eigene Regeln, Pause, Fortsetzen, offene Käufe stornieren) – je Eingang genau einmal.
4. Jedes Depot: Splits buchen, fällige Orders zum Kurs der Ausführungssitzung ausführen (erst Verkäufe, dann Käufe), Stops mit
   der fertigen Tageskerze prüfen (Kurslücke: Eröffnungskurs), Gewinnmitnahmen, Entscheidungen der Regeln mit Begründung,
   neue Orders für die nächste Sitzung (Profil „Folgetag-Schluss“).
5. Stand verschlüsselt ablegen; die Website enthält ihn als `data/pilot/<id>/pilot.bin`, `status.json` nur Kennung und Zeit.

Ein Fehler im Robo verhindert nie die Veröffentlichung der Ranglisten (Hinweis im Protokoll, nur Zählungen).

## 2. Depots

| Art | Kennung | Zweck |
|---|---|---|
| Pilotdepot | `pilot` | Robo-Kern (Welt/Geldmarkt nach Profil) plus höchstens 30 % aktive Strategien S1–S3 |
| Forschungsdepots | `f-…` | je Vorlage ein eigenes Depot mit gleichem Startkapital (Lineal, S1–S3, Platz-1-Sammler, Gleichmäßigkeit, Häufigkeit) |
| Eigene Regeln | `e-<regel>-v<version>` | aus dem Regel-Baukasten der App; jede neue Version ist ein neuer Test |
| Vergleichsdepots | `v-welt`, `v-kern` | Welt-ETF kaufen und halten; Robo-Kern ohne aktive Strategien |
| Historische Simulation | `h-…` | derselbe Motor über vergangene Tage, nachgerechnet – **kein Vorwärtstest** |

Im DEMO beginnen die Kennungen mit `demo-`. Archivierte Läufe bleiben vollständig im Zustand und stehen in der Chronik.

## 3. Die App (Bereich „Pilot“ in der unteren Leiste)

- **Automatik steuern** (wirkt im nächsten täglichen Lauf): neue Käufe pausieren bzw. fortsetzen, offene Käufe stornieren,
  aktive Positionen schließen (Verkauf in der nächsten Sitzung, Robo-Kern bleibt, Käufe pausiert), neuen Test starten (Pilot- und
  Vergleichsdepots neu mit derselben Einrichtung; der alte Lauf bleibt in der Chronik), Einrichtung ändern.
- **Übersicht:** Pilotdepot mit Gesamtwert, zeitgewichteter Rendite nach simulierten Kosten, Abstand zum Welt-ETF und zum
  Robo-Kern (in Prozentpunkten, nur bei gleichem Zeitraum), Aufteilung Kern/aktiv/frei, Rückgang, Kosten, Verluststufe;
  Wertverlauf (100 = Startkapital); alle Strategien im Vergleich; „Automatik steuern“; „Eingänge aus der App“.
- **Depot:** Positionen mit Einstand, Gewinn und Stop; offene und letzte Orders mit Grund, Datenstand und Ausführungssitzung;
  Journal je Tag – jede Entscheidung aufklappbar mit Kandidaten und Teilbedingungen („erfüllt“, „nicht erfüllt“, „nicht
  prüfbar“) und den Gründen für nicht gekaufte Aktien; Regeln als deutscher Text.
- **Bericht** (Depot → „Bericht“): Rendite, Rendite pro Jahr (erst ab einem Jahr), Schwankung, Sharpe und Sortino (risikofreier
  Zins: Geldmarkt-ETF im selben Zeitraum), größter Rückgang und Dauer, Trades, Trefferquote, Profitfaktor, Ø Gewinn und Verlust,
  Kapitalbindung, Kosten; Vergleich mit dem Welt-ETF- und dem Kern-Depot im gemeinsamen Zeitraum; Monatsrenditen;
  Hälftenvergleich; Block-Bootstrap; Prüfhürden aus Abschnitt 22 (nur Einordnung); Warnungen; Steuer-Modellrechnung. Was nicht
  berechnet werden kann, steht als „nicht definiert“ mit Grund da. Export: „Ausführungen als CSV“ (alle Käufe und Verkäufe mit
  FIFO-Losen, für Excel) und „Bericht als HTML-Datei“ (eigenständig, druckbar).
- **Regeln:** alle Regeln der Depots, „Neue Regel bauen“, je Regel „Als neue Version bearbeiten“, „Als Kopie bearbeiten“ und bei
  eigenen Regeln „Test dieser Regel beenden“; Kennzahlenkatalog mit „Als Robo-Regel verwenden“.
- **Chronik:** archivierte Läufe mit Zeitraum, Rendite und Rückgang.

## 4. Regel-Baukasten

Bausteine aus dem Kennzahlenkatalog des Laufs (63 Kennzahlen, darunter Vor-Ausbruch, Seitwärtsbasis und Volumensprung aus den
Musterbereichen unter „Potenzial“): Kandidaten (Rangliste heute oder an vergangenen Stichtagen,
Häufigkeit in den Top-Listen, alle Aktien, eigene Liste/Merkliste), Filter und Ausstieg (UND/ODER, NICHT, Zahl oder
Vergleichskennzahl), Sortierung (Reihenfolge oder Perzentil-Score), Auswahl und Kapital, Kauf-Auslöser, Verkauf (Herausfallen
mit Puffer, Haltedauer, Wiedereinstieg), Gewinnmitnahme (+30/+50/+100 % oder eigene Schwelle; alles, Anteil oder Stück; Leiter
mit bis zu sechs Stufen), Initialstop (Pflicht) und nachgezogener Stop, Zeitplan.

Die App prüft sofort mit denselben Grenzen wie der Lauf. „An den Robo senden“ schickt die Regel verschlüsselt an den Workflow
„Spielgeld-Eingang“; GitHub prüft innerhalb etwa einer Minute, die App zeigt „angenommen“ oder den Grund der Ablehnung. Der
nächste tägliche Lauf prüft noch einmal und startet die Regel in einem eigenen Forschungsdepot mit Spielgeld. Fehlende Daten
machen eine Bedingung „nicht prüfbar“ – dann wird nicht gekauft. Zentrale Risikogrenzen lassen sich nicht erhöhen.

Voraussetzung: der Zugang von „Jetzt aktualisieren“ (Einstellungen → Zugang; feingranulares Token nur „Actions: Lesen und
Schreiben“ auf dieses Repository) und die freigegebene Version auf `main` (vorher kennt GitHub den Workflow nicht).

## 5. Einrichtung (fünf Fragen)

„Automatik steuern“ → „Einrichtung ändern“: Startkapital (Spielgeld, 1.000 bis 10.000.000 EUR, Vorgabe 10.000 EUR), fünf Fragen
(Anlagehorizont, Liquiditätsbedarf, verkraftbarer Rückgang, Risikobereitschaft, Erfahrung; je 0 bis 4 Punkte) und der höchste
aktive Anteil (0, 10, 20 oder 30 %). Daraus das **Testprofil** des Robo-Kerns: 30 % Welt-Aktien-ETF plus 3,5 Prozentpunkte je
Punkt, begrenzt durch den verkraftbaren Rückgang (Szenario: Welt-ETF vorübergehend −50 %), auf 5 Prozentpunkte abgerundet,
mindestens 10 %; der Rest Geldmarkt-ETF. Die App zeigt die Herleitung vor dem Senden; die Tabelle kommt aus dem Lauf (keine
zweite Formel). Wirkung im nächsten täglichen Lauf: Pilotdepot und Vergleichsdepots starten als neuer Test mit dem neuen
Startkapital; der bisherige Lauf bleibt in der Chronik. Das Testprofil ist keine Anlageberatung.

## 6. Historische Simulation

```
python -m traktien spielgeld-simulation --state-dir state --tage 60 [--site _site] [--bericht privat.json]
python -m traktien spielgeld-simulation --demo --state-dir build/demo-state --tage 60 --site build/demo-site
```

Läuft über die letzten N Handelstage bis zum neuesten Stand; je Tag rechnet der Rechenkern die Ranglisten nur mit den Kursen bis
zu diesem Tag. Heutige Datenrevision und heutiges Universum – Rückschau-Verzerrung möglich, deshalb gekennzeichnet. Ausgabe nur
mit Zahlen; die vollständige Zusammenfassung (`--bericht`) ist privat. Eine neue Simulation archiviert die vorige.

## 7. Bericht: Formeln und Annahmen

Eine Rechnung im täglichen Lauf (`aktienpilot/bericht.py`) für App, CSV und HTML – die App rechnet nichts nach.

| Kennzahl | Formel bzw. Regel |
|---|---|
| Tagesrendite | (Wert − Zufluss am Tag) / Wert am Vortag − 1, nur zwischen vollständig bewerteten Tagen |
| Rendite | Produkt aller (1 + Tagesrendite) − 1 (zeitgewichtet) |
| Rendite pro Jahr | (1 + Rendite)^(365,25 / Kalendertage) − 1, erst ab 365 Kalendertagen |
| Schwankung | Standardabweichung der Tagesrenditen × √252, ab 20 Tagesrenditen |
| Sharpe / Sortino | Mittel der Überschussrendite (gegenüber dem Geldmarkt-ETF) geteilt durch ihre Standardabweichung bzw. die Abwärtsabweichung, × √252 |
| Größter Rückgang | vom bisherigen Höchststand des Renditeindex |
| Trades | Verkäufe (auch Teilverkäufe) der aktiven Strategien mit FIFO-Ergebnis nach Kosten; der Robo-Kern zählt nicht |
| Profitfaktor | Summe der Gewinne / Betrag der Summe der Verluste; ohne Verlusttrade nicht definiert |
| Kapitalbindung | Ø Anteil (Gesamtwert − Guthaben) am Gesamtwert |
| Block-Bootstrap | 1.000 Pfade aus Blöcken von 5 Tagesrenditen, Startwert aus der Depotkennung – Verlaufsrisiko, kein Nachweis eines Vorteils |

Steuer-Modellrechnung (keine Steuerabrechnung): je Kalenderjahr Aktienverluste nur mit Aktiengewinnen, Fondsergebnisse nach
Teilfreistellung im allgemeinen Topf, Verlustvorträge, Sparerpauschbetrag 1.000 EUR je Jahr für das Depot, 25 % plus
Solidaritätszuschlag; die angenommene Veräußerung am Ende steht getrennt. Ohne hinterlegten Basiszins keine Vorabpauschale und
keine Nachsteuer-Rendite. Walk-Forward nach Abschnitt 14 (drei Jahre Entwicklung, ein Testjahr) gibt die Historie nicht her –
das steht im Bericht; der Hälftenvergleich ersetzt ihn nicht.

## 8. Grenzen (Stand 31.10.2026)

- Der Vorwärtstest mit echten Kursen beginnt erst nach der Freigabe der neuen Version; vergangene Sitzungen lassen sich nicht
  nachholen (historische Simulation ist kein Ersatz).
- DEMO-Kurse reichen nur 161 Sitzungen zurück: S1–S3 brauchen 200-Tage-Durchschnitte und bleiben im DEMO „nicht prüfbar“ –
  sie kaufen dort nicht. Die echten Tageskerzen reichen etwa 296 Sitzungen zurück.
- Stops werden mit der fertigen Tageskerze geprüft, nicht während der Sitzung.
- Dividenden sind in den Werten nicht enthalten; Kosten sind simuliert (Spread, Slippage, Wechselkurs, Ordergebühr).
