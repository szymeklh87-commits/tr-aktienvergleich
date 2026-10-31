# Gesamtauftrag „Aktien-App und AktienPilot“ vom 31.10.2026, 17:46 Uhr – Ablage, Bestandsaufnahme, Soll-Ist-Prüfung

Auftrag: [`17_Gesamtauftrag_Robo.md`](17_Gesamtauftrag_Robo.md). Er **ergänzt** die Spezifikation
[`13_AktienPilot.md`](13_AktienPilot.md) (Abschnitte 0–32, 7A) und ersetzt sie nicht (Abschnitt 2). Detailmatrix mit Belegen je
Anforderung: [`13_AktienPilot_Umsetzungsstand.md`](13_AktienPilot_Umsetzungsstand.md) (IDs A01–A64, Z01–Z24). Diese Datei wird mit
jedem Arbeitsschritt fortgeschrieben.

## Ablage

| Prüfung | Ergebnis |
|---|---|
| Datei | `docs/17_Gesamtauftrag_Robo.md`, byte-gleich mit der Anlage vom 31.10.2026, 17:46 Uhr |
| Größe | 41.301 Bytes, 40.564 Zeichen, 1.155 Zeilen, Abschnitte 1–28 und Schlussanweisung |
| SHA-256 | `4108d2ad2fb0a9bb42619bcd15749da5d2437ead9b8686c8e0934aba4c9f1fe0` |
| Freigabe | ausdrücklich **keine** Genehmigung für den Merge von PR #2 oder eine Veröffentlichung (Abschnitt 22) – die Freigabeanfrage für PR #2 bleibt offen |

## Bestandsaufnahme (31.10.2026, gegen 18 Uhr)

| Bereich | Tatsächlicher Stand |
|---|---|
| Branches | `main` (veröffentlicht); `aktienpilot` (PR #1, Entwurf); `aktualisierung`; `gesamtauftrag` (PR #2 nach `main`, Entwurf, Stand `8497b09`, zur Freigabe vorgelegt); `gesamtauftrag-weiter` (Fortsetzung, auf `gesamtauftrag` aufbauend); `spielgeld-probe` (Messbranch, siehe unten) |
| Veröffentlichte Version | `status.json` vom 31.10.2026, 14:34 UTC: Kursstand **30.10.2026** (Freitag), letzte erfolgreiche Prüfung 31.10.2026, 14:25 UTC („kein neuer abgeschlossener Börsentag“ – Samstag), nächste Sitzung 02.11.2026; `app_mode: produktiv`; kein Spielgeld-Stand veröffentlicht (Robo erst nach Freigabe) |
| „Kursstand 12.10.2026“ in den Screenshots | Das waren Aufnahmen der **DEMO** (synthetische Kurse, fester Stichtag 12.10.2026), nicht der veröffentlichten App. **Fehler gefunden:** Im S25+-Format blendete die Kopfzeile das DEMO-Kennzeichen aus Platzgründen aus – das Datum sah wie ein echter Kursstand aus. Behoben: Die Beschriftung lautet in der DEMO „DEMO-Stand“; ein Browsertest prüft das sichtbar auf 12 Ansichten |
| `spielgeld-probe` | ein Commit `4678f61`, nur `.github/workflows/spielgeld-probe.yml` (Messlauf 41213451700, ausgewertet und dokumentiert), nicht geschützt, nirgends sonst gebraucht. Löschen aus dieser Umgebung zweimal abgelehnt (Berechtigung). **Manueller Schritt:** https://github.com/szymeklh87-commits/tr-aktienvergleich/branches → Zeile `spielgeld-probe` → Papierkorb „Delete branch“ (oder am PC `git push origin --delete spielgeld-probe`). Der Workflow startet nur bei einem Push auf genau diesen Branch |
| Läuft im Hintergrund | nur die bestehenden GitHub-Workflows auf `main` (täglicher Lauf wie bisher). Geplante Aufgaben dieses Kontos: keine aktive (die vier Erinnerungen vom 13.–27.10. sind ausgelöst und beendet). Die Weiterentwicklung läuft nur, solange diese Sitzung arbeitet |

## Soll-Ist-Matrix (vier Zustände)

**✓** vollständig umgesetzt und nachweislich geprüft · **◐** teilweise umgesetzt · **○** noch nicht umgesetzt · **✗** fehlerhaft
oder überarbeitungsbedürftig. Kette je Funktion (Abschnitt 25): implementiert → getestet → integriert → veröffentlicht → im
Vorwärtsbetrieb nachgewiesen. „Veröffentlicht“ heißt auf `main`; alles aus dem Gesamtauftrag liegt bis zur Freigabe nur auf
den Branches.

| Nr. | Anforderung (Abschnitt) | Zustand | Nachweis | Lücke / nächster Schritt |
|---|---|---|---|---|
| 3 | Vollständiges TR-Aktienuniversum, Identität, Lückenbericht | ◐ | A01: 11.596 ISINs aus der TR-Liste, Identitätsprüfung, mit echten Daten geprüft und veröffentlicht; A02 Abdeckung mit Ausschlussgründen | Lückenbericht als Export; Unterscheidung „bestätigt handelbar“ / „nur gelistet“ in jeder Liste |
| 4.1 | Kursquellen, Plausibilität, Splits, Währungen, keine erfundenen Kurse | ◐ | A03–A05 mit echten Daten (Kursabgleich, Splits, EZB-Kurse, Revisionen) | 95 von 141 US-Aktientagen ohne geklärte Ursache; Dividenden nicht in den Renditen |
| 4.2 | Aktualität auf jedem Bildschirm | ✗→◐ | Kopfzeile, Statusseite, Herzschlag (Z02); veröffentlichte Version aktuell (30.10.) | DEMO-Kennzeichen in der Kopfzeile fehlte auf dem Handy – behoben, noch nicht veröffentlicht |
| 4.3 | Performance, inkrementell, keine Doppelabrufe | ◐ | A57 Messungen; Robo und Ranglisten nutzen denselben Rechenstand | Kursreihen werden für Robo und Musterbereiche zweimal geladen → gemeinsam laden; Messungen fortschreiben |
| 5.1 | Zeiträume einzeln wählbar | ◐ | 1–90 **Kalendertage** einzeln (Lineal, Renditelisten) | Handelstage statt Kalendertage wäre eine Änderung der Methodik – nicht stillschweigend; als zusätzliche Option zur Entscheidung vorgelegt |
| 5.2 | Platz-1-Analyse | ◐ | A11 Häufigkeiten mit Nenner, verschiedene Zeiträume, Einzelsprung-Kennzeichen; Kennzahl `haeufigkeit` k=1 im Regelwerk | Wiederholung über Tage (Archiv füllt sich erst im Vorwärtsbetrieb); **Zuverlässigkeit früherer Platz-1-Signale** (Folgerendite) ○ |
| 5.3 | Top-10-Analyse, Standardlisten | ◐ | Top-10/Top-3/Platz-1 je Aktie | Ø Position, Stabilität, Auf-/Abstiege, Serien, Zusammenhang mit Folgerendite ○; beide Standardlisten (meiste Platz 1, meiste Top 10) gleichzeitig ○ |
| 5.4 | Freie Gewichtung, automatische Prüfung | ◐ | Score-Sortierung im Baukasten mit frei gewichteten Kennzahlen | automatische Prüfung der Gewichtungen über unabhängige Zeiträume ○ (Strategielabor) |
| 6 | Gleichmäßige Kurssteigerungen | ◐ | R², Steigung, Schwankung um die Gerade, größter Rückgang, Anteil steigender Tage, Einzelsprung, Volatilität im Katalog | Median/Ø Tagesrendite, Rücksetzer (Zahl, Stärke), Rendite je Schwankung, Trendqualität ○ |
| 7 | Ein zentraler Katalog und Baukasten | ✓ | A61/A34: 63 Kennzahlen (58 plus 5 Musterkennzahlen), feste Wertelisten für Kategorien, UND/ODER/NICHT, Vergleichskennzahl, Verschachtelung, Score-Gewichte, mehrere Quellen; Prüfung in App und Lauf gleich (Vertragstest) | – |
| 7.2 | „Als Robo-Regel verwenden“ | ◐ | Katalog, Lineal-Rangliste, Renditeliste, Häufigkeiten, Merkliste, Musterbereiche (Vertragstest, Browsertest bis zur Server-Prüfung) | Einzelaktie, Matrix, Kandidaten mit Potenzial |
| 8 | Module A/B/C | ◐ | implementiert, getestet (DEMO), integriert: Erkennung im täglichen Lauf (Kerzen einmal für Robo und Muster geladen), Ansicht „Potenzial → Muster und Volumen“, Journal, fünf Kennzahlen im zentralen Regelwerk, „Als Robo-Regel verwenden“ | mit echten Daten erst nach Freigabe; Intraday 15:30/15:45/16:00 ohne kostenlose Intraday-Kurse „nicht prüfbar“; relative Stärke, Zahl der Widerstandstests |
| 9 | Automatischer Spielgeldhandel | ◐ | Motor im täglichen Lauf (DEMO), historische Simulation mit echten Daten (Lauf 41213451700) | Vorwärtsbetrieb mit echten Kursen erst nach Freigabe von PR #2 |
| 10 | Gewinnmitnahmen, Teilverkäufe | ◐ | A63: Schwellen, Leiter bis 6 Stufen, Anteil/Stück, ursprünglich/verbleibend, Trailing-Stop | automatischer Vergleich der Varianten (10.3) ○ |
| 11 | Verkaufslogik mit Priorität | ◐ | Stops, Trailing, Haltedauer, Herausfallen mit Puffer, Ausstieg mit jeder Kennzahl, Umschichten | Priorität bei gleichzeitigen Regeln in der Anleitung offenlegen |
| 12 | Automatische Strategieentwicklung | ○ | – | Strategielabor: Varianten erzeugen, zeitlich getrennt prüfen, verwerfen, vorwärts testen |
| 13 | Kontinuierliche Selbstoptimierung, Übernahmeregel | ○ | Kennzahlen je Depot vorhanden (Bericht) | Zyklus, Mindestanforderungen, Wahl „nur vorschlagen / nach Freigabe / automatisch im Spielgeld“ |
| 14 | Strategien vergleichen | ◐ | Forschungsdepots je Vorlage und eigener Regel, Vergleichstabelle, **Bericht je Depot** (alle Kennzahlen aus 14, Prüfhürden, Datenqualität) | Auswahl der besten Strategie nach mehreren Kriterien; Robo-Kern-Vergleich auch für Forschungsdepots |
| 15 | Historisch vs. vorwärts, Walk-forward | ◐ | strikt getrennt und gekennzeichnet; kein Blick in die Zukunft (Tests) | Entwicklungs-/Validierungs-/Testzeiträume, Walk-forward über die verfügbare Historie (etwa 14 Monate) |
| 16 | Oberfläche, Robo-Startseite | ◐ | sechs Bereiche, S25+-Tests, Bericht, Baukasten | Startseite: beste Forschungsstrategie, nächste Ausführung, letzte Kursaktualisierung, Warnungen, Optimierungsstatus; Musterbereiche unter „Potenzial“ |
| 17 | Bedienung und Rückmeldung | ◐ | pausieren, fortsetzen, stornieren, schließen, neuer Test, Einrichtung, Regeln, Export – je mit Status (verschlüsselter Weg, Ende-zu-Ende-Test) | Strategien aktivieren/deaktivieren; historischen Test aus der App starten |
| 18 | Nachrichten, Analysten, Horizonte | ◐ | A27/A28 | Negativfilter mit drei Zuständen im Regelwerk; Horizonte 1 W – 1 J (A29) |
| 19 | Risikosteuerung | ◐ | A37–A39 offline geprüft, für jeden Kauf | Vorwärtsbetrieb |
| 20 | Performance der gesamten App | ◐ | A57 | gemeinsames Laden, Messungen vorher/nachher |
| 21 | Qualitätssicherung | ◐ | Unit-, App-, Vertrags-, Integrations- und Browsertests (Zahlen siehe Arbeitsstand) | Walk-forward-, Strategiewechsel- und Vorwärtstests |

## Fertigstellungskriterien (Abschnitt 26)

Keines der 26 Kriterien ist vollständig erfüllt, solange der Vorwärtsbetrieb mit echten Kursen fehlt (Freigabe von PR #2) und das
Strategielabor (12, 13, 15) nicht umgesetzt ist. Stand je Kriterium in der Matrix oben; erfüllt erst mit Nachweis.

## Priorisierte nächste Schritte

1. Musterbereiche A/B/C fertig integrieren: Katalog (Regeln), täglicher Lauf mit gemeinsam geladenen Kursreihen, Ansicht unter
   „Potenzial“, Journal, „Als Robo-Regel verwenden“.
2. Kennzahlen für Trendqualität (Abschnitt 6) und Top-10-Stabilität in den zentralen Katalog; beide Standardlisten (meiste Platz 1,
   meiste Top 10).
3. Strategielabor (12, 13, 15): Varianten aus Vorlagen und Parametergittern, zeitlich getrennte Entwicklung/Validierung/Test,
   Robustheitsregeln, Vorwärtstest der validierten Varianten in eigenen Spielgelddepots, wählbare Übernahmeregel.
4. Robo-Startseite nach Abschnitt 16, Strategien aktivieren/deaktivieren, historischen Test aus der App.
5. Performance und Vereinfachung (20) mit Messungen.
