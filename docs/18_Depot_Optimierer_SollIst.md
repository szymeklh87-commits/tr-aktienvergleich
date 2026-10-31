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
implementiert → getestet → integriert → veröffentlicht → im Vorwärtsbetrieb nachgewiesen. **Veröffentlicht ist noch nichts**
(Merge und Veröffentlichung sind freigabepflichtig); deshalb ist auch noch nichts im Vorwärtsbetrieb nachgewiesen.

Stand: 31.10.2026, abends (Branch `gesamtauftrag-weiter`).

### Auftrag 18 (Depot-Optimierer)

| Abschnitt | Anforderung | Zustand | Nachweis | Lücke / nächster Schritt |
|---|---|---|---|---|
| 2 | Empfehlungsdepot im Pilot | ✓ | Pilot → „Empfehlungen“, `tests/e2e/test_empfehlungen_app.py` | sichtbar erst nach Merge und erstem Forschungsergebnis mit echten Daten |
| 3 | Gesamtes Universum, alle Kennzahlen | ✓ | alle liquiden Aktien (Ø Umsatz ≥ 1 Mio. EUR) je Entscheidungstag; 92 Merkmale aus 58 von 76 Kennzahlen, übrige mit Grund (`test_merkmale.py`, Inventar in der App) | Kennzahlen ohne Historie (Analysten, Fakten) nur vorwärts |
| 4 | Historische Zusammenhänge, Zeiträume, Wiederholbarkeit | ✓ | Faktorprüfung je Merkmal × Horizont in Entwicklung, Validierung, Test (`test_forschung.py`) | – |
| 5 | Kombinationen automatisch testen, Parametersuche | ◐ | Zusatznutzen-Vorwärtsauswahl (Kombinationen gezählt), Redundanzprüfung, Fenstervarianten, Strategielabor mit Parametergitter | keine freie Suche über beliebige Parameter – bewusst, gegen Überanpassung |
| 6 | Prognosen 1 W – 1 J, Modelle vergleichen, Kalibrierung | ✓ | fünf Modelle inkl. Null- und Momentummodell im Walk-forward, kalibrierte Erwartung, Anteil positiv, 10–90-%-Spanne, Brier-Wert (`test_forschung.py`) | lange Horizonte meist „nicht belastbar“ (zu wenig unabhängige Zeiträume) |
| 7 | Eignungswert, Rangliste mit Begründung | ✓ | Rangliste je Horizont mit Eignung, Erwartung, Spanne, Kosten, Dafür/Dagegen (`test_optimierer.py`, e2e) | – |
| 8 | Depotebene: Anzahl, Gewichtung, Korrelationen, Varianten | ✓ | Mittelwert-Varianz mit Grenzen je Aktie/Branche, Korrelationsgrenze, sechs Varianten (`test_portfolio.py`) | Länder- und Währungsanteile nur angezeigt, nicht begrenzt |
| 9 | Depotvorschlag mit Kennzahlen darunter | ✓ | Erwartung nach Kosten, Unsicherheit, ungünstiger Fall, Kosten, Modell, historischer Test gegen Welt-ETF (e2e) | – |
| 10 | Tägliche Aktualisierung, Umschichtungsschutz | ✓ | im täglichen Lauf vor den Depots; Halteband, Mindestvorteil, Toleranz, Rhythmus täglich/wöchentlich/Signal (`test_optimierer.py`) | wirksam erst nach Merge |
| 11 | Bestes historisch getestetes Depot | ✓ | Rückblick 4/12/26 Wochen gegen Welt-ETF, Robo-Kern, Momentum, Platz 1, Top 10, Gleichmäßigkeit, alle Aktien (`test_forschung.py`) | Überlebensverzerrung ausgewiesen |
| 12 | Überanpassung verhindern | ✓ | getrennte Zeiträume, Benjamini-Hochberg, Purging, einfache Modelle zuerst, Belastbarkeit, Winsorisierung | – |
| 13 | Optimierungszyklus in einem Workflow | ◐ | `depot-optimierer.yml` (samstags und auf Anforderung, `test_workflows.py`) | Zeitplan läuft erst nach Merge in `main` – bis dahin **nicht aktiv** |
| 14 | Integration, Modus A/B/C | ◐ | A: Empfehlungen; B: Spielgeld-Musterdepot `f-empfehlung-<Variante>` folgt der Empfehlung (`test_optimierer.py`); C: Freigaberegeln des Labors am Vorwärtstest des Musterdepots in der Ansicht „Kontrolle“ (`optimierer.test.ts`, e2e) | C (automatische Übernahme in das Pilotdepot) nicht eingeschaltet – nur nach erfüllten Freigaberegeln und mit Freigabe |
| 15 | Prognosehistorie, unveränderlich, Kontrolle | ✓ | Tabellen mit Triggern gegen Ändern/Löschen, Kontrolle nach Ablauf (`test_optimierer.py`) | erste Auswertungen nach einer Woche Vorwärtsbetrieb |
| 16 | Dashboard „Depot-Empfehlungen“ | ✓ | oben Kopf, Mitte sortierbare Tabelle, unten Veränderungen; Ansichten Rangliste, Varianten, Kontrolle, Forschung, Infos, Parameter (e2e, S25+) | historische Depotentwicklung des Musterdepots erst mit Vorwärtsbetrieb |
| 17 | Depotparameter einstellbar, konsistent mit dem Pilot | ◐ | Eingang `optimierer_einstellungen` mit derselben Prüfung wie die Konfiguration, Profil und Kapital aus der Pilot-Einrichtung (e2e bis zur Server-Prüfung) | Prognosemodell nicht von Hand wählbar; Stops/Gewinnmitnahmen nur im Musterdepot (Pflichtregeln des Robos) |
| 18 | Effizienz, Transparenz der Rechnung | ✓ | ein Rechenkern-Lauf je Entscheidungstag für alle Merkmale, Zählungen und Laufzeiten in Ergebnis, App und Protokoll | – |
| 19 | Marktphasen, Ähnlichkeit, Frühwarnung, Kandidatenwechsel, Szenarien, Modellvergleich | ◐ | Musterähnlichkeit (nächste Nachbarn), Modellvergleich, Spannen als Szenarien, Kandidatenwechsel über die Veränderungen | Marktphasen-Erkennung und Frühwarnung offen |
| 20 | Erfolgskriterien | ◐ | geprüft mit synthetischen Daten und einer Messung mit echten Daten | Vorwärtsnachweis offen |

### Auftrag 19 (alle Informationen nutzen)

| Abschnitt | Anforderung | Zustand | Nachweis | Lücke / nächster Schritt |
|---|---|---|---|---|
| 2 | Alle Bereiche geprüft, zentraler Katalog | ◐ | Bestandsaufnahme oben; alle 76 Kennzahlen im Inventar (genutzt oder mit Grund) | Signalwerte der Potenzial-Ansicht, Bewertung/Wachstum, relative Stärke, Marktphase noch nicht im Katalog |
| 3 | Je Kennzahl Kennung, Berechnung, Quelle, Verfügbarkeit, Aktualität, Qualität, Währung, Historie, Lücken | ◐ | Inventar mit Quelle, Methode, Verfügbarkeit, Währung, historischer Berechenbarkeit; Merkmale ohne Wert je Tag gezählt | Datenalter und Abdeckung je Kennzahl in der App |
| 4 | Prognosenutzen, Redundanz, Zusatznutzen je Kennzahl | ✓ | Faktorprüfung, Redundanz (Rangkorrelation im Betrag ab 0,8), Zusatznutzen in der Validierung (`test_forschung.py`) | – |
| 5 | Kombinationen aus 2–4+ Faktoren, einfach gegen komplex | ✓ | Vorwärtsauswahl bis 8 Merkmale; lineares Modell gegen Nullmodell und Momentum, komplexe nur mit Vorsprung | – |
| 6 | Zukunftsbewertung je Horizont mit Unsicherheit | ✓ | kalibrierte Erwartung, Anteil positiv, Spanne; „nicht belastbar“ ohne Zahl | – |
| 7 | Depot aus allen Erkenntnissen | ✓ | Depotvarianten aus den Prognosen, Kosten, Liquidität, Kovarianz | – |
| 8 | Frühere Empfehlungen dokumentieren und auswerten | ✓ | unveränderliche Prognosen und Empfehlungen, Prognosekontrolle | Auswertungen erst im Vorwärtsbetrieb |
| 9 | Neubewertung bei neuen Informationen | ✓ | täglich mit dem neuesten Modell, wöchentlicher Forschungslauf | Zeitplan erst nach Merge |
| 10 | Begründungen aus der Rechnung, Gegenargumente | ✓ | Dafür/Dagegen aus den Modellmerkmalen (obere/untere Fünftel) | – |
| 11 | Prüfkriterien | ◐ | Zählungen in App, Bericht und Protokoll | Vorwärtsnachweis offen |
