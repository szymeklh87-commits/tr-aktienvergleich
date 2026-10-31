VERBINDLICHER GESAMTAUFTRAG AN CLAUDE

Aktien-App und AktienPilot – Vollständige Integration, automatischer Aktienhandel mit Spielgeld, Strategieentwicklung und kontinuierliche Optimierung

1. Übergeordnetes Ziel

Entwickle meine bestehende Aktien-App einschließlich AktienPilot zu einem vollständig integrierten, leistungsfähigen, weitgehend selbstständig arbeitenden Aktienanalyse- und Handelssimulationssystem.

Das endgültige Ziel ist nicht nur ein gewöhnlicher Robo-Advisor oder ein Regel-Baukasten.

Das System soll:

1. Möglichst alle bei Trade Republic handelbaren Aktien erfassen.
2. Die Kursentwicklung und sämtliche verfügbaren Analyseparameter systematisch untersuchen.
3. Meine bestehenden Ranglisten und Auswertungen vollständig für Handelsentscheidungen verwenden.
4. Aktien mit besonders hohen Renditen und möglichst gleichmäßigen positiven Kursentwicklungen identifizieren.
5. Verschiedene Handelsregeln automatisch entwickeln, kombinieren und testen.
6. Mit echtem historischem und aktuellem Kursmaterial handeln – ausschließlich mit virtuellem Spielgeld.
7. Aktien automatisch kaufen, verkaufen, teilweise verkaufen und umschichten.
8. Unterschiedliche Gewinnmitnahmen und Verlustbegrenzungen untersuchen.
9. Die erfolgreichsten Handelsstrategien anhand aussagekräftiger Tests erkennen.
10. Erfolgreiche Strategien kontrolliert weiterentwickeln und im Spielgeldbetrieb einsetzen.
11. Die Entwicklung der Depots, Handelsentscheidungen und erzielten Renditen vollständig dokumentieren.
12. Sich durch wiederholte Auswertung, Tests und Verbesserungen systematisch optimieren.
13. Sämtliche Funktionen übersichtlich, verständlich und ohne unnötige Doppelungen anbieten.

Oberstes Optimierungsziel: Eine möglichst hohe langfristige Rendite nach Handelskosten unter Berücksichtigung der vom Nutzer festgelegten Risikogrenzen.

Die tatsächliche Rentabilität muss durch belastbare historische Untersuchungen und unabhängige Vorwärtstests nachgewiesen werden. Hohe oder positive Renditen dürfen niemals als garantiert dargestellt werden.

---

2. Vollständige Berücksichtigung aller bisherigen Aufträge

Meine bisherigen Anweisungen an Claude und ChatGPT sind Bestandteil dieses Gesamtauftrags.

Berücksichtige insbesondere:

- Die vorhandene Aktien-App und ihre bisherigen Funktionen.
- Die Spezifikation "docs/13_AktienPilot.md" mit den Abschnitten 0–32 einschließlich 7A.
- Sämtliche bereits definierten Aktienkennzahlen.
- Die täglichen Gewinner- und Renditeranglisten.
- Die Lineal-Analysen und ihre verschiedenen Zeitfenster.
- Die Analyse der häufigsten Platz-1-Platzierungen.
- Die Häufigkeit von Top-10-Platzierungen.
- Die Erkennung gleichmäßiger Kurssteigerungen.
- Sämtliche bisherigen Anforderungen an Vor-Ausbruch-Signale, Volumensprünge und Seitwärtsbasen.
- Die vorhandenen Spielgelddepots, Handelsregeln und Gewinnmitnahmen.
- Die bisherigen Wünsche zur Bedienbarkeit, Vollständigkeit und Datenqualität.

Untersuche zunächst den tatsächlichen Repository-Stand einschließlich vorhandener Branches, Pull Requests, Tests, Dokumentation und bereits implementierter Funktionen.

Wichtig: Keine bestehende Funktion darf aufgrund einer Neustrukturierung unbeabsichtigt verloren gehen.

Erstelle eine interne Anforderungsmatrix mit vier Zuständen:

- Bereits vollständig umgesetzt und nachweislich geprüft.
- Teilweise umgesetzt.
- Noch nicht umgesetzt.
- Fehlerhaft oder überarbeitungsbedürftig.

Vermeide doppelte Implementierungen bereits vorhandener Funktionen.

Eine dokumentierte oder angekündigte Funktion gilt erst dann als erledigt, wenn sie im tatsächlichen Programm funktioniert und entsprechend getestet wurde.

---

3. Vollständiges Aktienuniversum von Trade Republic

Die Analyse darf sich nicht auf eine kleine Auswahl bekannter Aktien beschränken.

Ziel ist eine möglichst vollständige Erfassung aller bei Trade Republic handelbaren Aktien, einschließlich kleiner und internationaler Unternehmen.

Anforderungen:

- Zielgröße: vollständiges verfügbares TR-Aktienuniversum, angestrebt über 11.000 Titel, soweit tatsächlich verfügbar.
- Eindeutige Identifikation über ISIN und geeignete zusätzliche Kennungen.
- Keine mehrfachen Aktien durch verschiedene Ticker oder Börsenplätze.
- Berücksichtigung unterschiedlicher Handelswährungen.
- Korrekte Zuordnung von Unternehmen, Land, Branche und Handelsplatz.
- Erkennung nicht mehr handelbarer oder neu hinzugekommener Aktien.
- Transparente Darstellung der tatsächlich erreichten Datenabdeckung.
- Klare Unterscheidung zwischen bestätigter TR-Handelbarkeit und ungesichertem Handelsstatus.

Eine offizielle Trade-Republic-API ist nicht Voraussetzung. Es dürfen keine unzulässigen Zugriffe oder automatisierten Echtgeldtransaktionen eingerichtet werden.

Fehlende Aktien müssen in einem nachvollziehbaren Datenlückenbericht erscheinen.

Keine stillschweigende Beschränkung auf beispielsweise 500 oder 1.000 Aktien.

---

4. Zuverlässige und aktuelle Kursdaten

Die Qualität der Handelsentscheidungen hängt unmittelbar von der Qualität der Kursdaten ab.

Entwickle deshalb eine robuste, möglichst vollständige Kursdatenversorgung.

4.1 Datenquellen

- Mehrere geeignete Kursquellen verwenden, soweit technisch und rechtlich möglich.
- Kurse auf Plausibilität prüfen.
- Unterschiedliche Börsenplätze und Handelszeiten berücksichtigen.
- Kurswährung und Umrechnung nach Euro korrekt erfassen.
- Aktiensplits, Dividenden und Kapitalmaßnahmen berücksichtigen.
- Historische Daten ohne Zukunftsinformationen verarbeiten.
- Fehlende Kursdaten erkennen und dokumentieren.
- Auffällige Preissprünge überprüfen.
- Kein Erfinden fehlender Kurse.

Unterschiedliche Kursquellen müssen anhand vergleichbarer Kursarten, Handelsplätze und Zeitpunkte beurteilt werden.

Bei relevanten Abweichungen soll das Programm die Ursache untersuchen, statt unbemerkt beliebige Werte zu übernehmen.

4.2 Aktualität

Auf jedem Bildschirm muss nachvollziehbar sein:

- Von welchem Datum die Kursdaten stammen.
- Wann die letzte Aktualisierung erfolgreich war.
- Welche Aktien aktuell vollständig ausgewertet werden können.
- Welche Daten fehlen oder veraltet sind.

Die vorhandenen Screenshots zeigen beispielsweise einen Kursstand vom 12.10.2026. Prüfe, weshalb dieser Stand angezeigt wird und ob die aktuelle veröffentlichte Version veraltet ist.

Alte Daten dürfen nicht als aktuelle Marktdaten erscheinen.

4.3 Performance

Gestalte die Datenverarbeitung so effizient wie möglich:

- Inkrementelle Aktualisierung statt unnötigem vollständigem Neuberechnen.
- Geeignete Zwischenspeicherung.
- Wiederverwendung bereits berechneter Kennzahlen.
- Parallele Verarbeitung, wo sinnvoll.
- Keine mehrfachen Kursabrufe für dieselbe Aktie und denselben Zeitraum.
- Überwachung von Laufzeiten, Fehlern und Datenabdeckung.

---

5. Vollständige Integration meiner Renditeranglisten

Dieser Bereich ist für den Robo besonders wichtig.

Meine App untersucht bereits, welche Aktien innerhalb verschiedener Zeiträume die besten Renditen erreichen.

Diese Ergebnisse sollen eine zentrale Grundlage der automatischen Handelsstrategien bilden.

5.1 Zeiträume

Berechne und analysiere Renditeranglisten beispielsweise für:

- 1 Handelstag
- 2 Handelstage
- 3 Handelstage
- 4 bis 10 Handelstage
- 11 bis 20 Handelstage
- 21 bis 30 Handelstage
- 31 bis 60 Handelstage
- Optional bis 90 Handelstage und längere Zeiträume

Wo möglich, soll jeder einzelne Zeitraum separat auswählbar sein.

5.2 Platz-1-Analyse

Ermittle automatisch:

- Welche Aktie am häufigsten Platz 1 erreicht.
- Wie viele erste Plätze sie in den betrachteten Zeitfenstern erzielt.
- Ob sie nur kurzfristig oder über viele Zeiträume an der Spitze steht.
- Ob die Spitzenplatzierungen auf wenige extreme Kurssprünge zurückgehen.
- Ob eine Aktie über mehrere Tage wiederholt Platz 1 erreicht.
- Wie zuverlässig frühere Platz-1-Signale in nachfolgenden Zeiträumen waren.

Beispiel:

Aktie A erreicht in 30 untersuchten Ranglisten 18-mal Platz 1.

Aktie B erreicht nur 3-mal Platz 1.

Der Robo soll untersuchen, ob die häufigeren Spitzenplätze historisch und in unabhängigen Tests tatsächlich bessere nachfolgende Renditen erwarten ließen.

5.3 Top-10-Analyse

Zusätzlich untersuchen:

- Häufigkeit aller Top-10-Platzierungen.
- Häufigkeit von Top-3-Platzierungen.
- Durchschnittliche Ranglistenposition.
- Ranglistenstabilität.
- Auf- und Abstiege.
- Anzahl aufeinanderfolgender Top-10-Platzierungen.
- Zusammenhang zwischen Ranglistenstabilität und nachfolgender Rendite.

In der App sollen die zehn Aktien mit den meisten Platz-1-Platzierungen und die zehn Aktien mit den meisten Top-10-Nennungen als Standard sichtbar sein.

Eine Top-20-Auswertung bleibt optional.

5.4 Gewichtung

Der Nutzer muss frei kombinieren können, etwa:

- 50 % Anzahl erster Plätze.
- 25 % Anzahl Top-10-Platzierungen.
- 25 % Gleichmäßigkeit der Kursentwicklung.

Alle Gewichtungen müssen individuell veränderbar sein.

Der Robo soll zusätzlich automatisch überprüfen, welche Gewichtungen über unabhängige Testzeiträume die besten Ergebnisse erzielen.

---

6. Gleichmäßige Kurssteigerungen erkennen

Besonders wichtig ist meine bisherige Forderung, nicht nur Aktien mit extremen Einzelgewinnen zu finden.

Ich möchte auch Aktien erkennen, die über längere Zeit kontinuierlich steigen.

Untersuche dafür:

- Anzahl positiver Handelstage.
- Durchschnittliche tägliche Rendite.
- Median der täglichen Renditen.
- Stärke und Beständigkeit des Aufwärtstrends.
- Schwankungsbreite.
- Maximale zwischenzeitliche Verluste.
- Anzahl und Stärke von Rücksetzern.
- Gleichmäßigkeit des Kursverlaufs.
- Zusammenhang zwischen kurzfristigen und langfristigen Renditen.
- Verhältnis von Kursanstieg zu Volatilität.
- Stabilität der Ranglistenposition.
- Stärke außergewöhnlicher Einzelbewegungen.

Entwickle daraus nachvollziehbare Kennzahlen für Trendqualität, Kontinuität und Stabilität.

Beispiel:

Aktie A steigt an einem Tag um 40 % und verliert anschließend wieder deutlich.

Aktie B steigt über 20 Handelstage relativ gleichmäßig um insgesamt 25 %.

Der Robo soll solche Unterschiede erkennen und systematisch testen, welche Eigenschaften für meine unterschiedlichen Strategien besser geeignet sind.

Kein pauschaler Ausschluss stark schwankender Aktien, solange die gewählte Strategie und ihre Risikoregeln solche Aktien zulassen.

---

7. Sämtliche vorhandenen Analyseparameter als Handelsregeln

Alle bereits vorhandenen 58 Kennzahlen und zukünftige geeignete Analyseparameter sollen im selben Regelwerk nutzbar sein.

Es darf nicht für jede neue Funktion ein eigener, unabhängiger Regel-Baukasten entstehen.

Entwickle einen einzigen zentralen Regel- und Kriterienkatalog.

Jede geeignete Kennzahl soll verwendbar sein für:

- Aktienauswahl.
- Filter.
- Ranking.
- Gewichtung.
- Kaufentscheidung.
- Verkaufentscheidung.
- Positionsgröße.
- Risikobegrenzung.
- Strategieoptimierung.

7.1 Kombinierbare Regeln

Unterstütze:

- UND
- ODER
- NICHT
- Vergleichsoperatoren
- Frei definierbare Grenzwerte
- Vergleich zwischen zwei Kennzahlen
- Verschachtelte Bedingungen
- Gewichtete Bedingungen
- Unterschiedliche Zeitfenster
- Mehrere miteinander kombinierte Ranglisten

Beispiel:

KAUFEN, wenn:

- Mindestens fünf Platz-1-Platzierungen innerhalb der ausgewählten Zeitfenster.
- Mindestens 15 Top-10-Nennungen.
- Positiver 30-Tage-Trend.
- Geringere Schwankung als der gewählte Grenzwert.
- Kein definiertes negatives Nachrichtensignal.
- Ausreichendes Handelsvolumen.

Diese Bedingungen müssen vom Nutzer frei verändert werden können.

7.2 Direkt aus den Analyseansichten

In jeder passenden Analyseansicht soll die Funktion vorhanden sein:

„Als Robo-Regel verwenden“

Beispielsweise:

Eine Aktie oder ein bestimmter Filter fällt in der Lineal-Auswertung auf.

Ich wähle die entsprechende Kennzahl aus und kann daraus unmittelbar eine Kauf-, Verkaufs- oder Filterregel erstellen.

Die App übernimmt den Parameter in den vorhandenen zentralen Regel-Baukasten.

Keine doppelte Dateneingabe.

---

8. Vor-Ausbruch, Ausbruch und Volumensprung

Die bisher geplanten Module müssen vollständig umgesetzt und in das zentrale Regelwerk integriert werden.

Modul A – Vor-Ausbruch

Suche Aktien mit möglichen bevorstehenden stärkeren Kursbewegungen.

Untersuche:

- Kursverengungen.
- Aufwärtstrend vor Widerständen.
- Abnehmende Volatilität.
- Steigendes relatives Volumen.
- Historische Widerstandsmarken.
- Relative Stärke gegenüber Vergleichsaktien.
- Wiederholte Tests von Ausbruchsniveaus.

Modul B – Ausbruch und Volumensprung

Erkenne:

- Ausbruch über definierte Widerstände.
- Handelsvolumen mindestens dreimal so hoch wie das gewählte Referenzvolumen, sofern so eingestellt.
- Ungewöhnliche Kursbeschleunigung.
- Kombination aus Ausbruch und Ranglistenstärke.
- Mögliche Fehlausbrüche.
- Abweichungen zwischen Kurs und Handelsvolumen.

Modul C – Seitwärtsbasis

Untersuche:

- Längere Seitwärtsphasen.
- Enge Handelsspannen.
- Wiederholte Unterstützungen.
- Wiederholte Widerstände.
- Abnehmende Schwankung.
- Dynamische Ausbrüche aus der Seitwärtsbasis.

Alle drei Module müssen sich mit meinen Ranglisten- und Lineal-Parametern kombinieren lassen.

US-Handelsstart

Die von mir gewünschten Zeitpunkte sind besonders zu berücksichtigen:

- 15:30 Uhr
- 15:45 Uhr
- 16:00 Uhr

Berücksichtige bei US-Aktien die tatsächlichen Börsenöffnungszeiten einschließlich der Zeitumstellungen.

Diese Uhrzeiten dienen der Signalanalyse. Sie dürfen nicht für simulierte Intraday-Ausführungen verwendet werden, wenn keine passenden historischen Intraday-Kurse vorliegen.

---

9. Vollautomatischer Spielgeldhandel

Entwickle einen eigenständig arbeitenden Autopiloten.

Ausschließlich Spielgeld. Niemals eigenständiger Handel mit echtem Geld.

Der Robo soll im Rahmen aktivierter Strategien:

1. Die verfügbaren Aktien untersuchen.
2. Geeignete Kandidaten auswählen.
3. Regeln prüfen.
4. Kaufentscheidungen treffen.
5. Positionsgrößen bestimmen.
6. Kauforders simulieren.
7. Bestehende Positionen überwachen.
8. Gewinnmitnahmen durchführen.
9. Stop-Loss-Regeln anwenden.
10. Verkaufsbedingungen überprüfen.
11. Positionen vollständig oder teilweise verkaufen.
12. Erlöse neu investieren.
13. Bei besseren Kandidaten gegebenenfalls umschichten.
14. Sämtliche Entscheidungen im Journal dokumentieren.

9.1 Handelsausführung

Behalte den bereits vorgesehenen Grundmechanismus mit Ausführung zum nächsten verfügbaren Handelstag bei, solange kein genauerer, nachweislich korrekter Simulationsmodus umgesetzt ist.

Verwende für Entscheidungen ausschließlich Informationen, die zum Entscheidungszeitpunkt tatsächlich verfügbar gewesen wären.

Berücksichtige:

- Handelskalender.
- Kurslücken.
- Gebühren.
- Spread.
- Währungsumrechnung.
- Ausführungskosten.
- Handelsunterbrechungen.
- Mangelnde Liquidität.
- Nicht ausführbare Orders.

Der Robo darf keine unrealistisch günstigen Ausführungspreise erfinden.

---

10. Frei konfigurierbare Gewinnmitnahmen

Ich möchte Gewinnmitnahmen selbst bestimmen und automatisiert testen lassen.

10.1 Feste Gewinnziele

Beispiele:

- Verkaufen bei +10 %.
- Verkaufen bei +20 %.
- Verkaufen bei +30 %.
- Verkaufen bei +50 %.
- Verkaufen bei +100 %.
- Beliebige weitere Prozentwerte.

10.2 Teilverkäufe

Beispiel:

- Bei +30 % Gewinn 25 % verkaufen.
- Bei +50 % Gewinn weitere 25 % verkaufen.
- Bei +100 % Gewinn weitere 50 % verkaufen.

Unterstütze zusätzlich:

- Verkauf einer festen Stückzahl.
- Verkauf eines Prozentsatzes der ursprünglichen Position.
- Verkauf eines Prozentsatzes der noch vorhandenen Position.
- Vollständigen Ausstieg.
- Mehrstufige Gewinnleiter.
- Nachgezogenen Stop-Loss.
- Wiederanlage der Verkaufserlöse.

Die Berechnung muss Rundungen, Restmengen, Gebühren und bereits erfolgte Teilverkäufe korrekt berücksichtigen.

10.3 Automatischer Strategievergleich

Der Robo soll systematisch untersuchen:

- Ist ein vollständiger Verkauf bei +30 % besser?
- Ist ein vollständiger Verkauf bei +50 % besser?
- Ist ein vollständiger Verkauf bei +100 % besser?
- Sind Teilverkäufe erfolgreicher?
- Sind nachgezogene Stops besser?
- Ist längeres Halten erfolgreicher?
- Welche Kombination funktioniert bei welchen Aktienmerkmalen besser?

Vergleiche die Strategien über mehrere unabhängige Zeiträume und unter realistischen Handelskosten.

---

11. Vollständige Verkaufslogik

Verkäufe dürfen nicht ausschließlich durch Gewinnziele ausgelöst werden.

Weitere frei einstellbare Verkaufskriterien:

- Stop-Loss erreicht.
- Nachgezogener Stop erreicht.
- Vorgegebene Haltedauer überschritten.
- Aktie verliert ihre relevante Ranglistenposition.
- Trend verschlechtert sich.
- Handelsvolumen fällt unter einen Grenzwert.
- Eine andere Aktie hat nach den aktiven Regeln eine bessere Bewertung.
- Eine negative Nachricht erfüllt einen definierten Risikofilter.
- Eine technische Verkaufsbedingung tritt ein.
- Die maximale Positions- oder Depotgewichtung wird verletzt.

Bei mehreren gleichzeitig erfüllten Regeln muss eine eindeutige, dokumentierte Priorität gelten.

Der bestehende verpflichtende Initialstop bleibt bestehen, solange die verbindliche Spezifikation ihn verlangt.

---

12. Automatische Strategieentwicklung

Das ist eine der wichtigsten noch fehlenden Funktionen.

Ich möchte nicht sämtliche möglichen Strategien selbst einzeln ausprobieren müssen.

Der Robo soll eigenständig sinnvolle Varianten meiner vorhandenen Analyseparameter zusammenstellen und vergleichen.

Beispiele:

Strategie A: Aktien mit besonders vielen Platz-1-Platzierungen.

Strategie B: Aktien mit besonders vielen Top-10-Nennungen.

Strategie C: Aktien mit besonders gleichmäßigem Kursanstieg.

Strategie D: Platz-1-Häufigkeit plus Volumensprung.

Strategie E: Top-10-Stabilität plus Vor-Ausbruch-Signal.

Strategie F: Gleichmäßiger Aufwärtstrend plus Gewinnleiter.

Strategie G: Kurzfristige Spitzenreiter mit schnellem Ausstieg.

Strategie H: Längerfristige Spitzenreiter mit längerem Halten.

Der Robo soll:

1. Geeignete Regelkombinationen erzeugen.
2. Parameter systematisch variieren.
3. Historisch testen.
4. Unabhängig validieren.
5. Die Ergebnisse vergleichen.
6. Nicht robuste Kombinationen verwerfen.
7. Erfolgversprechende Kombinationen weiter untersuchen.
8. Neue Varianten entwickeln.
9. Validierte Strategien in separaten Spielgelddepots vorwärts testen.
10. Erfolgreiche Strategien als Kandidaten für die aktive Nutzung vorschlagen oder nach ausdrücklich festgelegten Freigaberegeln übernehmen.

Das gesamte Verfahren muss nachvollziehbar und reproduzierbar sein.

Keine scheinbare Selbstoptimierung durch bloßes Auswählen des besten historischen Ergebnisses.

---

13. Kontinuierliche Selbstoptimierung

Entwickle einen systematischen Optimierungsprozess.

Der Robo soll regelmäßig auswerten:

- Welche Regeln erzielten die besten Ergebnisse?
- Welche Parameter waren besonders wirksam?
- Welche Regeln verloren ihre Wirksamkeit?
- Welche Rendite wurde erzielt?
- Wie hoch waren die Verluste?
- Wie hoch waren die Transaktionskosten?
- Wie häufig wurde gehandelt?
- Wie stabil waren die Ergebnisse?
- Wie entwickelte sich die Strategie in unterschiedlichen Marktphasen?
- Wie schnitt sie gegenüber einem Welt-ETF und einfachen Vergleichsstrategien ab?

Optimierungszyklus

Analysieren → Strategie erstellen → historisch testen → unabhängig validieren → mit Spielgeld vorwärts testen → vergleichen → kontrolliert übernehmen oder verwerfen → erneut untersuchen.

Die automatische Verbesserung soll sowohl die Kaufregeln als auch Verkaufsregeln, Haltedauer, Positionsgröße und Umschichtung einbeziehen.

Eine neue Strategie darf nicht allein aufgrund eines zufällig guten Backtests produktiv übernommen werden.

Definiere hierfür nachvollziehbare Mindestanforderungen an Testdauer, Datenqualität, Stichprobengröße, Risikogrenzen und unabhängige Ergebnisse.

Der Nutzer soll entscheiden können, ob eine nachweislich besser abschneidende Strategie:

- Nur vorgeschlagen wird.
- Nach manueller Freigabe übernommen wird.
- Innerhalb zuvor ausdrücklich festgelegter Risikogrenzen und Freigaberegeln automatisch im Spielgelddepot übernommen werden darf.

---

14. Mehrere Strategien gleichzeitig vergleichen

Die vorhandenen Forschungsdepots bilden die Grundlage.

Jede Strategie erhält ein eigenes virtuelles Depot mit:

- Gleichem Startkapital.
- Gleichem Startzeitpunkt.
- Vergleichbarer Kursdatenbasis.
- Einheitlichen Kostenannahmen.
- Eigenem Orderjournal.
- Eigener Wertentwicklung.
- Eigener Risikostatistik.

Zusätzlich berücksichtigen:

- Pilotdepot.
- Robo-Kern.
- Aktive Strategien S1–S3.
- Welt-ETF-Vergleich.
- Weitere einfache Vergleichsstrategien.

Die bereits vorgesehene Begrenzung auf höchstens 30 % aktive Strategien muss entsprechend dem gewählten Risikoprofil eingehalten werden. Änderungen solcher Grenzen erfordern eine bewusste Nutzerentscheidung.

Auswertung

Zeige mindestens:

- Gesamtrendite.
- Rendite nach Kosten.
- Absolute Gewinne und Verluste.
- Maximale zwischenzeitliche Verluste.
- Volatilität.
- Trefferquote.
- Durchschnittlicher Gewinn und Verlust pro Handel.
- Profit-Faktor.
- Handelsanzahl.
- Kapitalbindung.
- Rendite gegenüber Welt-ETF.
- Rendite gegenüber Robo-Kern.
- Testdauer.
- Datenqualität und Aussagekraft der Ergebnisse.

Die beste Strategie soll anhand mehrerer objektiver Kriterien bestimmt werden, nicht allein aufgrund des höchsten Einzelgewinns.

---

15. Historische Simulation und echter Vorwärtstest

Trenne diese beiden Bereiche vollständig.

Historische Simulation

- Rechne mit tatsächlich verfügbaren historischen Daten.
- Berücksichtige Gebühren und Ausführungsvorschriften.
- Verhindere Zukunftsinformationen.
- Berücksichtige historische Veränderungen des Aktienuniversums, soweit Daten vorliegen.
- Dokumentiere mögliche Rückschau- und Überlebensverzerrungen.
- Verwende zeitlich getrennte Trainings-, Validierungs- und Testperioden.
- Implementiere Walk-forward-Analysen.
- Prüfe Strategien auch über wechselnde Marktphasen.

Vorwärtstest

Der tägliche Spielgeld-Robo soll auf Basis neuer echter Marktdaten unabhängig weiterlaufen.

Er muss zeigen:

- Welche Strategie tatsächlich welche Aktien ausgewählt hat.
- Welche Orders erzeugt wurden.
- Welche simulierten Preise verwendet wurden.
- Welche Gewinne oder Verluste nach Kosten entstanden.
- Ob ein anderes Regelwerk erfolgreicher gewesen wäre.
- Wie sich die Ergebnisse über Wochen und Monate entwickeln.

Historische Simulationen dürfen niemals als tatsächliche Vorwärtsergebnisse ausgegeben werden.

Synthetische Demo-Aktien wie die in den Screenshots sichtbaren Beispiele müssen klar von realen Wertpapieren getrennt werden.

Die Standardansicht des tatsächlichen Pilotbetriebs soll reale Aktien und reale Kursdaten verwenden, sobald dies technisch überprüft möglich ist.

---

16. Benutzeroberfläche vollständig überarbeiten

Die App soll leistungsfähig sein, ohne unnötig kompliziert zu werden.

Die Screenshots zeigen bereits zahlreiche Eingabefelder, lange Seiten und teilweise wiederholte Parameter.

Überprüfe deshalb die gesamte Bedienoberfläche.

Anforderungen

- Übersichtliche Navigation.
- Klare Kategorien.
- Einheitliche Begriffe.
- Keine doppelten Einstellungen.
- Keine mehrfach vorhandenen Regeldefinitionen.
- Keine unnötigen Untermenüs.
- Keine überlangen, unübersichtlichen Formularseiten.
- Sinnvolle Voreinstellungen.
- Einklappbare erweiterte Einstellungen.
- Suchfunktion für Kennzahlen und Regeln.
- Verständliche Erklärungen.
- Sofortige Eingabeprüfung.
- Sichtbare Auswirkungen geänderter Regeln.
- Einheitliches Design.
- Gute Darstellung auf dem Galaxy S25+.
- Geeignete Darstellung auf Tablets und Windows.
- Deutsche Sprache und Euro als Hauptwährung.

Vorgeschlagene einheitliche Bereiche

Start: Gesamtüberblick, Kursaktualität, wichtigste Renditeergebnisse und laufende Prozesse.

Rendite: Tagesgewinner, historische Ranglisten, Platz-1-Häufigkeit und Top-10-Häufigkeit.

Potenzial: Vor-Ausbruch-Signale, Volumensprünge, Seitwärtsbasen und geeignete Kandidaten.

Aktien: Vollständige Aktienübersicht mit Suche und Filtern.

Analyse: Detaillierte Kennzahlen, Vergleiche, Prognosen und historische Untersuchungen.

Pilot: Spielgelddepots, Strategien, Robo-Regeln, Journal, Ergebnisse und Optimierung.

Es sollen keine neuen Hauptbereiche entstehen, wenn dieselbe Funktion bereits sinnvoll in einem bestehenden Bereich integriert werden kann.

Robo-Startseite

Zeige auf einen Blick:

- Aktuelles Spielgeldkapital.
- Gewinn oder Verlust.
- Rendite nach Kosten.
- Vergleich zum Welt-ETF.
- Anzahl offener Positionen.
- Aktive Strategie.
- Beste Forschungsstrategie.
- Letzte Kauf- und Verkaufsentscheidung.
- Nächste geplante Ausführung.
- Letzte erfolgreiche Kursaktualisierung.
- Aktuelle Warnungen.
- Status des Optimierungsprozesses.

Von dort aus sollen die Details direkt erreichbar sein.

---

17. Automatisierung und Bedienung

Der Nutzer soll das System nach Einrichtung möglichst wenig manuell bedienen müssen.

Erforderliche Funktionen:

- Autopilot aktivieren.
- Käufe pausieren.
- Käufe fortsetzen.
- Offene Kauforders stornieren.
- Positionen im Spielgelddepot schließen.
- Strategien aktivieren oder deaktivieren.
- Regeln verändern.
- Eigenen Test starten.
- Historischen Test starten.
- Depot neu starten.
- Startkapital auswählen.
- Ergebnisse vergleichen.
- Strategien duplizieren oder bearbeiten.
- Ergebnisse exportieren.

Jede Aktion benötigt einen klaren Status und eine nachvollziehbare Rückmeldung.

Der bestehende verschlüsselte Übertragungsweg zwischen App und Robo muss zuverlässig funktionieren und entsprechend getestet werden.

Keine ungeschützte Veröffentlichung persönlicher Einstellungen oder Portfoliodaten.

---

18. Nachrichten und zusätzliche Analysen

Berücksichtige zusätzlich relevante Informationen, sofern verlässliche Quellen verfügbar sind:

- Negative Unternehmensmeldungen.
- Gewinnwarnungen.
- Kapitalerhöhungen.
- Analystenschätzungen.
- Analystenkonsens.
- Auffällige Änderungen von Prognosen.
- Wesentliche Unternehmensereignisse.
- Branchenentwicklung.
- Relative Stärke gegenüber Markt und Branche.

Negative Meldungen sollen als nachvollziehbarer, konfigurierbarer Filter nutzbar sein.

Fehlende Nachrichten dürfen nicht automatisch als positive Nachrichten gewertet werden.

Die von mir gewünschten Einschätzungen über folgende Zeiträume sollen weiterhin in der App verfügbar sein:

- 1 Woche
- 1 Monat
- 3 Monate
- 6 Monate
- 1 Jahr

Dabei müssen Prognosen, Analystenschätzungen und tatsächlich erzielte Renditen klar voneinander getrennt bleiben.

---

19. Risikosteuerung

Der Robo soll nach Rendite suchen, aber nicht unkontrolliert Risiken erhöhen.

Berücksichtige:

- Maximales Risiko pro Position.
- Maximale Positionsgröße.
- Maximale Branchengewichtung.
- Maximale Anzahl gleichzeitig gehaltener Aktien.
- Liquiditätsreserve.
- Verlustbegrenzung.
- Depotverlustgrenzen.
- Handelskosten.
- Mindestliquidität.
- Vermeidung unrealistischer Ausführungen.
- Maximal zulässige Umschichtung.
- Vorgehen bei Datenfehlern.
- Vorgehen bei ausbleibenden Kursaktualisierungen.

Das bestehende Risikoprofil soll berücksichtigt werden.

Die Risikosteuerung soll unterschiedliche Strategien ermöglichen und nicht sämtliche ertragsorientierten Ansätze pauschal blockieren.

---

20. Performance und Effizienz der gesamten App

Untersuche nicht nur die Geschwindigkeit des Robos, sondern die gesamte Anwendung.

Optimiere:

- Ladezeiten.
- Datenbankabfragen.
- Speicherbedarf.
- Rechenaufwand.
- Kursaktualisierung.
- Historische Simulationen.
- Ranglistenberechnungen.
- Strategieoptimierungen.
- Mobile Darstellung.
- Navigation.
- Datenübertragung.
- Fehlerbehandlung.

Wiederholte Berechnungen gleicher Parameter sollen vermieden werden.

Ein gemeinsam genutzter Kennzahlenkatalog muss die Grundlage für Ranglisten, Analyse, Signale und Robo sein.

Jede Kennzahl soll möglichst nur einmal zentral definiert und berechnet werden.

Untersuche auch, ob die aktuelle Architektur unnötig komplex geworden ist, und vereinfache sie, ohne bestehende Funktionen zu beschädigen.

---

21. Automatische Qualitätssicherung

Nach jeder wesentlichen Änderung:

1. Bestehende Tests ausführen.
2. Neue Funktionen testen.
3. Regressionen erkennen.
4. Fehler beheben.
5. Erneut testen.
6. Bedienoberfläche überprüfen.
7. Datenqualität überprüfen.
8. Rechen- und Ladezeiten messen.
9. Tatsächliches Verhalten des Spielgeld-Robos überprüfen.

Ergänze insbesondere Tests für:

- Korrekte Platz-1- und Top-10-Ranglisten.
- Unterschiedliche Zeitfenster.
- Ausfälle einzelner Kursquellen.
- Währungsumrechnung.
- Aktiensplits.
- Zeitumstellungen.
- Stop-Loss.
- Gewinnmitnahme.
- Mehrstufige Teilverkäufe.
- Wiederanlage.
- Gleichzeitige Kauf- und Verkaufssignale.
- Datenlücken.
- Handelskalender.
- Depotabgleiche.
- Verschlüsselung.
- Historische Simulation.
- Walk-forward-Auswertung.
- Vorwärtstest.
- Strategiewechsel.

Die bereits vorhandenen erfolgreichen Tests müssen weiterhin bestehen.

Eine grüne Testanzeige allein genügt nicht. Die Tests müssen auch die tatsächlichen fachlichen Anforderungen abdecken.

---

22. Aktuellen Entwicklungsstand berücksichtigen

Ausgangspunkt ist die gemeldete Lieferung mit:

- PR #2.
- Stand "8497b09".
- Geprüften Tests.
- Vorhandenem Spielgeld-Robo.
- Vorhandenem Regel-Baukasten.
- Forschungsdepots.
- Historischer Simulation.
- Gewinnmitnahmen.
- Journal und Orderverwaltung.
- Verschlüsselter Übermittlung.

Prüfe den tatsächlichen Stand im Repository, bevor du weitere Implementierungen beginnst.

Die aktuellen Funktionen sollen erhalten bleiben und systematisch vervollständigt werden.

Wichtig zur Freigabe: Dieser Auftrag ist keine automatische Genehmigung zum Merge von PR #2 oder zur Veröffentlichung. Vorhandene Freigabegrenzen bleiben bestehen.

Entwickle auf geeigneten separaten Branches weiter und stelle abgeschlossene, geprüfte Änderungen zur Integration bereit.

Der alte Branch "spielgeld-probe" soll geprüft und bei entsprechender Berechtigung sicher entfernt werden. Falls die Berechtigung fehlt, dokumentiere den konkreten manuellen Löschschritt.

---

23. Verbindliche Entwicklungsprioritäten

Priorität 1 – Datenqualität und Vollständigkeit

- Vollständiges TR-Aktienuniversum.
- Verlässliche aktuelle Kursdaten.
- Kursquellenabgleich.
- Historische Datenqualität.
- Eindeutige Aktienidentifikation.
- Bereinigte, korrekt berechnete Renditeranglisten.

Priorität 2 – Zentrale Integration

- Alle vorhandenen Kennzahlen zentralisieren.
- Alle bisherigen Analysefunktionen integrieren.
- Platz-1- und Top-10-Analysen vollständig nutzbar machen.
- Einheitlichen Regel-Baukasten fertigstellen.
- Doppelte Parameter entfernen.
- Direkte Übergabe von Analysen an Handelsregeln.

Priorität 3 – Vollständiger Spielgeld-Robo

- Automatischer Aktienkauf.
- Automatischer Aktienverkauf.
- Gewinnleitern.
- Stops.
- Umschichtungen.
- Wiederanlage.
- Kostenrechnung.
- Portfolioverwaltung.
- Vollständiges Journal.

Priorität 4 – Strategieentwicklung und Optimierung

- Automatische Erzeugung neuer Handelsregeln.
- Systematische Parametertests.
- Walk-forward-Untersuchungen.
- Unabhängige Validierung.
- Vergleich mehrerer Strategien.
- Kontrollierte automatische Verbesserung.
- Vorwärtstests.
- Nachvollziehbare Auswahl geeigneter Strategien.

Priorität 5 – Bedienbarkeit und Performance

- Überarbeitung der gesamten Benutzeroberfläche.
- Entfernung unnötiger Doppelungen.
- Einfachere Navigation.
- Verständliche Analyseergebnisse.
- Schnellere Berechnung.
- Schnellere Darstellung.
- Mobile und Desktop-Optimierung.

Diese Prioritäten sind miteinander zu koordinieren. Eine zentrale technische Voraussetzung darf nicht aufgeschoben werden, wenn sie für einen anderen Bereich zwingend erforderlich ist.

---

24. Fortlaufende, eigenständige Entwicklung

Ich möchte nicht nach jeder kleinen Änderung einen neuen Auftrag erteilen müssen.

Arbeite innerhalb deiner verfügbaren Entwicklungsumgebung möglichst eigenständig und in fortlaufenden, überprüfbaren Iterationen.

Der Ablauf lautet:

1. Bestehenden Zustand analysieren.
2. Fehlende Anforderungen identifizieren.
3. Wichtigste Probleme priorisieren.
4. Funktionen implementieren.
5. Tests durchführen.
6. Fehler beheben.
7. Ergebnisse überprüfen.
8. Verbesserungsmöglichkeiten untersuchen.
9. Nächste sinnvolle Entwicklungsstufe umsetzen.
10. Vorgang wiederholen, bis die definierten Anforderungen erfüllt sind.

Unterbrich die Umsetzung nicht bloß deshalb, weil eine einzelne Teilfunktion fertiggestellt ist.

Nutze verfügbare Recherchemöglichkeiten, Dokumentationen und geeignete etablierte Verfahren, um fachlich oder technisch bessere Lösungen zu entwickeln.

Ersetze vorhandene gut funktionierende Lösungen nicht ohne belegbaren Vorteil.

Baue keine unnötig komplexen Systeme, wenn dasselbe Ziel mit einer einfacheren, zuverlässigeren Lösung erreicht werden kann.

Wichtig: Melde niemals eine Hintergrundentwicklung oder einen fortgesetzten Entwicklungsprozess als aktiv, wenn technisch tatsächlich kein laufender Auftrag oder Workflow existiert.

Verwende bereits vorhandene oder tatsächlich eingerichtete tägliche Workflows für wiederkehrende Aufgaben.

---

25. Keine vorschnellen Erfolgsmeldungen

Ich möchte keine Berichte, die lediglich aufzählen, wie viele Funktionen angeblich fertig sind.

Zeige stattdessen konkret:

- Was tatsächlich implementiert wurde.
- Welche Dateien geändert wurden.
- Welche Funktionen nachweislich arbeiten.
- Welche Tests erfolgreich waren.
- Welche realen Daten verwendet wurden.
- Welche Fehler noch vorhanden sind.
- Welche Anforderungen noch fehlen.
- Welche Einschränkungen technisch bestehen.
- Welcher nächste Arbeitsschritt erforderlich ist.

Bezeichne eine Funktion nicht als vollständig fertig, wenn sie noch keine echten Kursdaten verarbeitet, nur mit Demo-Daten funktioniert oder bislang nicht unter realistischen Bedingungen getestet wurde.

Unterscheide ausdrücklich zwischen:

Implementiert – getestet – integriert – veröffentlicht – im Vorwärtsbetrieb nachgewiesen.

---

26. Messbare Fertigstellungskriterien

Der Auftrag gilt erst dann als fachlich vollständig umgesetzt, wenn mindestens Folgendes erfüllt ist:

- [ ] Das tatsächlich verfügbare TR-Aktienuniversum wird möglichst vollständig erfasst; Lücken sind nachvollziehbar.
- [ ] Die Kursdaten sind aktuell und stammen aus nachvollziehbaren Quellen.
- [ ] Abweichungen zwischen Kursquellen werden erkannt und behandelt.
- [ ] Alle bestehenden Rendite- und Ranglistenfunktionen arbeiten korrekt.
- [ ] Platz-1- und Top-10-Häufigkeiten sind für die gewünschten Zeitfenster auswertbar.
- [ ] Gleichmäßige Kursentwicklungen werden analysiert.
- [ ] Sämtliche geeigneten vorhandenen Kennzahlen können als Robo-Parameter verwendet werden.
- [ ] Der Regel-Baukasten funktioniert ohne doppelte Kennzahldefinitionen.
- [ ] Kauf- und Verkaufsregeln lassen sich frei kombinieren.
- [ ] Der Robo handelt automatisch mit Spielgeld und realen Marktdaten.
- [ ] Gewinne und Verluste werden nach simulierten Handelskosten korrekt berechnet.
- [ ] Gewinnleitern und Teilverkäufe funktionieren zuverlässig.
- [ ] Stop-Loss, Haltedauer und Umschichtungen funktionieren.
- [ ] Die Ausbruch-, Volumen- und Seitwärtsmodule sind integriert.
- [ ] Forschungsstrategien können automatisch erzeugt und getestet werden.
- [ ] Walk-forward-Auswertungen sind vorhanden.
- [ ] Neue Strategien werden unabhängig validiert.
- [ ] Mehrere Strategien laufen parallel in getrennten Depots.
- [ ] Der echte Spielgeld-Vorwärtstest ist von historischen Simulationen getrennt.
- [ ] Die beste Strategie kann nach festgelegten Regeln kontrolliert übernommen werden.
- [ ] Alle Handelsentscheidungen sind nachvollziehbar.
- [ ] Die Benutzeroberfläche ist vollständig integriert, verständlich und responsiv.
- [ ] Unnötige Doppelungen und vermeidbare Rechenvorgänge wurden entfernt.
- [ ] Alle wesentlichen fachlichen und technischen Tests sind erfolgreich.
- [ ] Die Dokumentation entspricht der tatsächlich gelieferten Software.

Erst danach darfst du die Gesamtanforderungen als erfüllt bezeichnen.

Darüber hinaus soll das System so aufgebaut sein, dass weitere Strategietests und Verbesserungen ohne grundlegenden Umbau möglich sind.

---

27. Was du ausdrücklich vermeiden sollst

- Keine weitere isolierte Aktien-App neben der bestehenden entwickeln.
- Keine parallelen Regel-Baukästen.
- Keine mehrfachen Einstellungen für denselben Parameter.
- Keine unvollständigen Ranglisten ohne Kennzeichnung.
- Keine erfundenen oder stillschweigend ersetzten Kursdaten.
- Keine als echt dargestellten synthetischen Wertpapiere.
- Keine Vermischung von Rückrechnung und Vorwärtstest.
- Keine vermeintliche Strategieoptimierung ausschließlich anhand vergangener Gewinner.
- Keine stillschweigende Änderung meiner bestehenden Regeln.
- Keine unnötig kostenpflichtigen Dienste.
- Keine Echtgeldtransaktionen.
- Keine unerlaubten Zugriffe auf Broker-Systeme.
- Keine ungeprüften Veröffentlichungen.
- Keine Entfernung bestehender Funktionen ohne Ersatz.
- Keine Behauptung garantierter Gewinne.
- Keine Erfolgsmeldung ohne nachvollziehbaren Nachweis.

---

28. Konkretes Ergebnis, das ich erwarte

Am Ende möchte ich meine Aktien-App öffnen und beispielsweise Folgendes tun können:

Beispiel A – Regel nach Ranglisten erstellen

Ich wähle:

„Kaufe automatisch Aktien, die innerhalb der vergangenen 30 Handelstage besonders häufig Platz 1 oder einen Platz in den Top 10 meiner Renditeranglisten erreicht haben.“

Ich ergänze:

„Bevorzuge möglichst gleichmäßige Kurssteigerungen.“

Der Robo untersucht die Aktien, erstellt passende Signale und führt die vorgesehenen Käufe mit Spielgeld aus.

Beispiel B – Automatische Gewinnmitnahme

Ich wähle:

„Bei +30 % Gewinn 25 % verkaufen, bei +50 % weitere 25 % und bei +100 % den Rest verkaufen.“

Der Robo führt dies korrekt aus, sofern die simulierten Ausführungsbedingungen erfüllt werden.

Beispiel C – Strategie automatisch untersuchen

Ich wähle:

„Untersuche, ob Platz-1-Häufigkeit, Top-10-Häufigkeit oder gleichmäßige Kurssteigerungen die besseren Handelsergebnisse liefern.“

Der Robo erstellt geeignete Varianten, prüft sie und zeigt nachvollziehbare Ergebnisse.

Beispiel D – Automatische Strategieverbesserung

Ich wähle:

„Optimiere meine Strategie durch Variation der Kaufbedingungen, Haltedauer, Gewichtungen und Gewinnmitnahmen.“

Das System soll mehrere Varianten prüfen und anhand unabhängiger Ergebnisse geeignete Verbesserungen ermitteln.

Beispiel E – Gesamtergebnis

Ich öffne die Pilotübersicht und sehe sofort:

- Welche Aktien der Robo gekauft hat.
- Warum er sie gekauft hat.
- Welche Aktien verkauft wurden.
- Wie hoch die realistisch simulierten Gewinne und Verluste sind.
- Welche Strategie aktuell am besten abschneidet.
- Ob die Ergebnisse besser als beim Welt-ETF sind.
- Welche Verbesserungen getestet werden.
- Welche Strategien tatsächlich im Vorwärtstest erfolgreich waren.

Alles ohne unnötige manuelle Berechnungen oder wiederholte Dateneingaben.

---

ABSCHLIESSENDE HAUPTANWEISUNG

Entwickle nicht einfach nur eine Sammlung von Funktionen. Entwickle ein zusammenhängendes, automatisiertes, datengetriebenes und kontinuierlich überprüftes Aktienanalyse- und Spielgeld-Handelssystem.

Nutze meine bisherigen Anforderungen als verbindliche Grundlage.

Mein besonderer Schwerpunkt liegt auf:

1. Vollständigen und korrekten Aktienanalysen.

2. Meinen Platz-1-, Top-10- und Lineal-Ranglisten als zentrale Grundlage für Handelsregeln.

3. Der Erkennung dauerhaft starker und möglichst gleichmäßig steigender Aktien.

4. Automatisiertem Kauf, Verkauf und Umschichten mit Spielgeld.

5. Frei definierbaren Gewinnmitnahmen und Verkaufsbedingungen.

6. Automatischer Entwicklung, Untersuchung und kontrollierter Verbesserung von Handelsstrategien.

7. Dem Vergleich aller Strategien anhand tatsächlich aussagekräftiger Ergebnisse.

8. Einer möglichst einfachen, schnellen, übersichtlichen und vollständig integrierten Benutzeroberfläche.

Arbeite systematisch weiter, bis die beschriebenen Anforderungen vollständig implementiert und überprüft sind. Die Fertigstellung einzelner Zwischenstände ist kein Grund, noch offene Bestandteile des Gesamtauftrags zu ignorieren.

Beginne mit einer Bestandsaufnahme des tatsächlichen Repository-Stands, einer vollständigen Soll-Ist-Prüfung und der unmittelbar anschließenden Umsetzung der höchstpriorisierten offenen Anforderungen.

Das gewünschte Endergebnis ist eine möglichst leistungsfähige Aktien-App, deren Robo mit Spielgeld eigenständig Entscheidungen trifft, Handelsstrategien untersucht und sich innerhalb nachvollziehbarer Sicherheits- und Qualitätsgrenzen systematisch verbessern kann.