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

- **Übersicht:** Pilotdepot mit Gesamtwert, zeitgewichteter Rendite nach simulierten Kosten, Abstand zum Welt-ETF und zum
  Robo-Kern (in Prozentpunkten, nur bei gleichem Zeitraum), Aufteilung Kern/aktiv/frei, Rückgang, Kosten, Verluststufe;
  Wertverlauf (100 = Startkapital); alle Strategien im Vergleich; „Automatik steuern“; „Eingänge aus der App“.
- **Depot:** Positionen mit Einstand, Gewinn und Stop; offene und letzte Orders mit Grund, Datenstand und Ausführungssitzung;
  Journal je Tag – jede Entscheidung aufklappbar mit Kandidaten und Teilbedingungen („erfüllt“, „nicht erfüllt“, „nicht
  prüfbar“) und den Gründen für nicht gekaufte Aktien; Regeln als deutscher Text.
- **Regeln:** alle Regeln der Depots, „Neue Regel bauen“, je Regel „Als neue Version bearbeiten“, „Als Kopie bearbeiten“ und bei
  eigenen Regeln „Test dieser Regel beenden“; Kennzahlenkatalog mit „Als Regel verwenden“.
- **Chronik:** archivierte Läufe mit Zeitraum, Rendite und Rückgang.

## 4. Regel-Baukasten

Bausteine aus dem Kennzahlenkatalog des Laufs (58 Kennzahlen): Kandidaten (Rangliste heute oder an vergangenen Stichtagen,
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

## 5. Historische Simulation

```
python -m traktien spielgeld-simulation --state-dir state --tage 60 [--site _site] [--bericht privat.json]
python -m traktien spielgeld-simulation --demo --state-dir build/demo-state --tage 60 --site build/demo-site
```

Läuft über die letzten N Handelstage bis zum neuesten Stand; je Tag rechnet der Rechenkern die Ranglisten nur mit den Kursen bis
zu diesem Tag. Heutige Datenrevision und heutiges Universum – Rückschau-Verzerrung möglich, deshalb gekennzeichnet. Ausgabe nur
mit Zahlen; die vollständige Zusammenfassung (`--bericht`) ist privat. Eine neue Simulation archiviert die vorige.

## 6. Grenzen (Stand 31.10.2026)

- Der Vorwärtstest mit echten Kursen beginnt erst nach der Freigabe der neuen Version; vergangene Sitzungen lassen sich nicht
  nachholen (historische Simulation ist kein Ersatz).
- DEMO-Kurse reichen nur 161 Sitzungen zurück: S1–S3 brauchen 200-Tage-Durchschnitte und bleiben im DEMO „nicht prüfbar“ –
  sie kaufen dort nicht. Die echten Tageskerzen reichen etwa 296 Sitzungen zurück.
- Stops werden mit der fertigen Tageskerze geprüft, nicht während der Sitzung.
- Dividenden sind in den Werten nicht enthalten; Kosten sind simuliert (Spread, Slippage, Wechselkurs, Ordergebühr).
