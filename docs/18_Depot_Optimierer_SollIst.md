# Depot-Optimierer – Ablage, Bestandsaufnahme, Soll-Ist (Aufträge vom 31.10.2026, 20:10 Uhr)

Aufträge: [`18_Depot_Optimierer.md`](18_Depot_Optimierer.md) („Erweiterung des Gesamtauftrags – Intelligenter Depot-Optimierer“,
Abschnitte 1–21) und [`19_Depot_Optimierer_Alle_Informationen.md`](19_Depot_Optimierer_Alle_Informationen.md) („Verbindlicher
Zusatzauftrag – alle Informationen der Aktien-App für die Depotoptimierung nutzen“, Abschnitte 1–12). Beide **ergänzen** den
Gesamtauftrag [`17_Gesamtauftrag_Robo.md`](17_Gesamtauftrag_Robo.md) und die Spezifikation [`13_AktienPilot.md`](13_AktienPilot.md);
alle bisherigen Vorgaben bleiben. Diese Datei wird mit jedem Arbeitsschritt fortgeschrieben.

## Ablage

| Datei | Bytes | Zeichen | Zeilen | SHA-256 |
|---|---|---|---|---|
| `docs/18_Depot_Optimierer.md` | 30.298 | 29.793 | 875 | `1eacc976115919c1bb8539f7f8112c75aa03ecf8fa39751d8ec32bd190be05dc` |
| `docs/19_Depot_Optimierer_Alle_Informationen.md` | 13.843 | 13.635 | 385 | `c11543bf8d90c200a57d70348467f7244ad2a58247e42345d426444257971baa` |

Byte-gleich mit den Anlagen (UTF-8 ohne BOM, Zeilenende LF); `tests/unit/test_auftraege.py` prüft die Prüfsummen aller
abgelegten Aufträge gegen diese Tabellen. Freigabe: ausdrücklich keine pauschale Veröffentlichungsfreigabe (Auftrag 18,
Abschnitt 20) – Merge von PR #2 und Veröffentlichung bleiben bei dir.

## Bestandsaufnahme (31.10.2026, gegen 20:30 Uhr)

### Datenbasis

| Daten | Stand | Historie | Für den Optimierer |
|---|---|---|---|
| Universum | TR-Liste mit 11.596 ISINs; im Messlauf 41213451700 10.999 Aktien gerechnet (459 ohne geprüfte Identität, 141 ohne Kurse) | Liste je Abruf, keine historische Zugehörigkeit | gesamtes gerechnetes Universum; **Überlebensverzerrung**: heutiges Universum, später verschwundene Aktien fehlen in jedem Rückblick |
| Tageskerzen | 3.092.010 im Zustand (31.10.2026) | etwa 14 Monate | Grundlage aller Merkmale; begrenzt die prüfbaren Horizonte (siehe Grenzen) |
| Wechselkurse | EZB-Referenzkurse | 3 Jahre + 4 Monate | Renditen in Euro |
| Kennzahlen je Aktie („Fakten“: Kursziele, Empfehlungen, Bewertung, Wachstum, Finanzen, Branche) | rotierend abgerufen (`jobs/facts.py`) | **keine Historie** (nur Abruftag) | nur vorwärts nutzbar; ihr Prognosenutzen lässt sich erst mit gesammelten Ständen prüfen |
| Nachrichten, Community-Stimmung | nur aktuell, nur vordere Kandidaten bzw. US | keine | nur vorwärts, wenige Aktien |
| Intraday | keine kostenlose Quelle | – | nicht verfügbar |

### App-Bereiche (Auftrag 19, Abschnitte 1 und 2)

| Bereich | Inhalt | Im zentralen Katalog (Regelwerk) | Historisch berechenbar |
|---|---|---|---|
| Start | Überblick, Datenstand, Kopf der Ranglisten | über die Ranglisten (Lineal, Häufigkeit) | ja |
| Rendite | Renditeranglisten 1–90 Tage, elf Gewichtungen, Gruppen A/B, Bericht 1–30, Musterdepots (Zehnerdepots rückblickend und vorwärts), Gleichmäßig + Rendite, Sieger | Lineal (10), Häufigkeit (6), Rangverlauf (4), Trendqualität (9) | ja (Rechenkern je Stichtag; „späterer Sieger“ ist rückblickend und bleibt ausgeschlossen) |
| Potenzial | Kandidaten mit Signalen (kurzfristig, langfristig, Gesamtwertung, Steig-Konstanz, Kursziel-Potenzial, Qualität, Nachrichten, Community, kalibrierte Trefferquote), Muster und Volumen (Vor-Ausbruch, Seitwärtsbasis, Volumensprung) | Muster und Volumen (5), Kurs und Technik (16); **Signalwerte selbst fehlen im Katalog** | technische Teile ja, Analysten/Nachrichten nein |
| Aktien | Liste, Watchlist, Einzelansicht mit Kurs, Kennzahlen, Signalen, Analystenzielen | Stammdaten (4), Analysten (2: Abstand zum Kursziel, Zahl der Analysten) | Stammdaten teils, Analysten nein |
| Analyse | Matrix, Häufigste Aktien (beide Standardlisten), Gewichtungsvergleich, Rotation | Häufigkeit, Lineal | ja |
| Pilot | Spielgeld-Robo, Forschungsdepots, Regel-Baukasten, Strategielabor, Bericht | Depot (6) – depotabhängig, für die Aktienbewertung nicht geeignet | ja |

Der Katalog (`aktienpilot/katalog.py`) hat 76 Kennzahlen in elf Bereichen mit Quelle, Methode, Aufwärmphase, Fehlwert,
Rückblick-Eignung (`backtest`: ja / nur vorwärts / nein) und Ansicht der App. Er ist die einzige Quelle für Regeln, Labor und
App (Vertragstest). **Fehlt** für Auftrag 19: Signalwerte der Potenzial-Ansicht, Bewertungs- und Wachstumskennzahlen,
relative Stärke gegenüber Markt und Branche, Trendbeschleunigung, Marktphase sowie je Kennzahl Abdeckung und Datenalter am
Stichtag.

### Was schon vorhanden ist und wiederverwendet wird

- **Rechenkern je Stichtag** (`comp`) und **Kontextquelle** für vergangene Stichtage (Rechenkern mit den Kursen bis zu diesem
  Tag, etwa 33 s je Tag mit echten Daten) – kein zweiter Weg zu denselben Kennzahlen.
- **Strategielabor**: Varianten, Entwicklung/Validierung/Test, Walk-forward, Signalprüfung, laufende Strategien, Ablage und
  Übernahme im täglichen Lauf, Workflow auf Anforderung.
- **Signale** (Potenzial) mit Kalibrierung der Trefferquote je Punktebereich (5/20 bzw. 20/60 Sitzungen).
- **Spielgeld-Robo**: Motor, Forschungsdepots, Vergleichsdepots (Welt-ETF, Robo-Kern), Risiko-Manager, Eingangsweg aus der App.

## Grenzen, die das Ergebnis bestimmen

1. **Historie etwa 14 Monate.** Nach der Aufwärmphase der Ranglisten (bis 90 Kalendertage) bleiben rund 200 Handelstage mit
   Merkmalen. Prüfbar sind Horizonte von 1 Woche bis etwa 3 Monate; **6 Monate und 1 Jahr lassen sich nicht unabhängig
   prüfen** – dafür zeigt die App keine Zahl, sondern „nicht belastbar“ (Auftrag 19, Abschnitt 6: keine scheinbar exakten
   Werte).
2. **Überlappende Folgezeiträume.** Tägliche 3-Monats-Renditen überlappen; Teststatistiken rechnen deshalb mit der Zahl
   unabhängiger Zeiträume, nicht mit der Zahl der Tage.
3. **Überlebensverzerrung** (heutiges Universum) und **heutige Datenrevision** in jedem Rückblick – ausgewiesen.
4. **Analysten, Nachrichten, Fundamentaldaten ohne Historie**: ihr Prognosenutzen wird erst mit gesammelten Ständen prüfbar;
   bis dahin gehen sie nicht in trainierte Modelle ein, werden aber angezeigt und als „nur vorwärts“ gekennzeichnet.

## Soll-Ist-Matrix

**✓** umgesetzt und nachweislich geprüft · **◐** teilweise · **○** offen · **✗** fehlerhaft. Kette wie im Gesamtauftrag:
implementiert → getestet → integriert → veröffentlicht → im Vorwärtsbetrieb nachgewiesen.

### Auftrag 18 (Depot-Optimierer)

| Abschnitt | Anforderung | Zustand | Nachweis | Lücke / nächster Schritt |
|---|---|---|---|---|
| 2 | Empfehlungsdepot im Pilot | ○ | – | Ansicht „Depot-Empfehlungen“ |
| 3 | Gesamtes Universum, alle Kennzahlen | ◐ | Rechenkern über das ganze Universum; 76 Kennzahlen | Merkmalsmatrix aus allen geeigneten Katalogkennzahlen |
| 4 | Historische Zusammenhänge, Zeiträume, Wiederholbarkeit | ◐ | Signalprüfung im Labor (5 Signale, 5/20 Tage) | Prognosenutzen jeder Kennzahl je Horizont über getrennte Zeiträume |
| 5 | Kombinationen automatisch testen, Parametersuche | ◐ | Strategielabor (28 Varianten, Gitter, Robustheit) | Kombinationen auf Merkmalsebene mit Kontrolle der Zufallstreffer |
| 6 | Prognosen 1 W – 1 J, Modelle vergleichen, Kalibrierung | ○ | – | Modelle gegen Nullmodell und Momentum, kalibrierte Wahrscheinlichkeit, Szenarien |
| 7 | Eignungswert, Rangliste mit Begründung | ○ | – | – |
| 8 | Depotebene: Anzahl, Gewichtung, Korrelationen, Varianten | ○ | – | – |
| 9 | Depotvorschlag mit Kennzahlen darunter | ○ | – | – |
| 10 | Tägliche Aktualisierung, Umschichtungsschutz | ○ | – | – |
| 11 | Bestes historisch getestetes Depot | ○ | – | Walk-forward ohne Zukunftsdaten gegen einfache Strategien |
| 12 | Überanpassung verhindern | ◐ | Labor: Zeiträume, Walk-forward, Nachbarn, Test wählt nichts | dasselbe für Merkmale und Modelle |
| 13 | Optimierungszyklus in einem Workflow | ◐ | Laborlauf auf Anforderung | regelmäßiger Forschungslauf (wirkt erst nach Freigabe) |
| 14 | Integration, Modus A/B/C | ○ | – | – |
| 15 | Prognosehistorie, unveränderlich, Kontrolle | ○ | – | – |
| 16 | Dashboard „Depot-Empfehlungen“ | ○ | – | – |
| 17 | Depotparameter einstellbar, konsistent mit dem Pilot | ○ | – | – |
| 18 | Effizienz, Transparenz der Rechnung | ◐ | Rechenkern je Tag einmal für alle Depots des Labors | Zählungen für Optimierer |
| 19 | Marktphasen, Ähnlichkeit, Frühwarnung, Kandidatenwechsel, Szenarien, Modellvergleich | ○ | – | – |
| 20 | Erfolgskriterien | ○ | – | erst mit allen Bausteinen |

### Auftrag 19 (alle Informationen nutzen)

| Abschnitt | Anforderung | Zustand | Nachweis | Lücke / nächster Schritt |
|---|---|---|---|---|
| 2 | Alle Bereiche geprüft, zentraler Katalog | ◐ | Bestandsaufnahme oben; 76 Kennzahlen | Signalwerte, Bewertung/Wachstum, relative Stärke, Marktphase ergänzen |
| 3 | Je Kennzahl Kennung, Berechnung, Quelle, Verfügbarkeit, Aktualität, Qualität, Währung, Historie, Lücken | ◐ | Quelle, Methode, Rückblick-Eignung im Katalog | Abdeckung und Datenalter je Stichtag |
| 4 | Prognosenutzen, Redundanz, Zusatznutzen je Kennzahl | ○ | – | – |
| 5 | Kombinationen aus 2–4+ Faktoren, einfach gegen komplex | ○ | – | – |
| 6 | Zukunftsbewertung je Horizont mit Unsicherheit | ○ | – | – |
| 7 | Depot aus allen Erkenntnissen | ○ | – | – |
| 8 | Frühere Empfehlungen dokumentieren und auswerten | ○ | – | – |
| 9 | Neubewertung bei neuen Informationen | ○ | – | – |
| 10 | Begründungen aus der Rechnung, Gegenargumente | ○ | – | – |
| 11 | Prüfkriterien | ○ | – | – |
