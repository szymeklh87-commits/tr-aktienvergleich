# Fehlende Kurstage – Regeln, Referenzfälle und Einfluss auf die Ranglisten

Stand **24.10.2026**, Software **1.18.0**, Methode **tr-methode-1.10.0** (Regeln zu fehlenden Kurstagen unverändert seit
tr-methode-1.8.0 bzw. 1.9.0; neu in 1.10.0 nur der exakte Gleichstand, Abschnitt 6). Aufträge vom 24.10.2026: „Sichere die
Behandlung fehlender Kurstage mit nachvollziehbaren Referenztests ab. Dokumentiere ihren Einfluss auf Ranglisten.“ und
(16:00 Uhr) „Behalte die Regel bei, dass ein fehlender Tag als fehlend zählt … kennzeichne unzureichende Daten
verständlich.“ – „Bei mathematisch gleichem Score entscheidet die höhere Rendite …“

**Entscheidung zu fehlenden Kurstagen (24.10.2026): Die Regel bleibt.** Ein fehlender Tag zählt als fehlend; ein Zeitraum
fällt nicht allein deshalb weg; es gibt keine Ersatzkurse, und fehlende Werte zählen nicht als null. Die Anforderungen an
ausreichende Daten (Startkurs, höchstens 20 % fehlende Börsentage, einer immer erlaubt, letzter Schlusskurs höchstens eine
Sitzung alt) bleiben. Neu ab Software 1.18: Die Aktienseite nennt bei „Startkurs fehlt“ den Tag und bei „Zu viele Börsentage
ohne Kurs“ die Zahlen des Zeitraums – für Aktie E aus Abschnitt 3 (30 Tage): „Vom 23.09.2026 bis 23.10.2026 hatte die Börse
23 Börsentage. Schlusskurse liegen für 18 vor, 5 fehlen (22 %). Erlaubt sind höchstens 20 % fehlende Börsentage (ein
einzelner fehlender Tag ist immer erlaubt). Fehlende Tage werden weder ersetzt noch als null gezählt.“ Dazu der Begriff
„Fehlende Kurstage“ in der Hilfe (`app/tests/gleichstand.test.ts`, `app/tests/hilfe.test.ts`).

## 1. Was als fehlender Kurstag gilt

Ein **fehlender Kurstag** ist eine Börsensitzung laut Kalender der Börse, an der kein gültiger Schlusskurs vorliegt. Zwei
Formen kommen beim Kursanbieter vor, beide zählen in der App gleich:

- **keine Zeile** – der Kursanbieter liefert für den Tag nichts;
- **Leerzeile** – der Tag ist da, aber ohne Kurs und Umsatz.

Ein **Feiertag** der Börse ist keine Sitzung und deshalb kein fehlender Tag. Fehlende Tage werden **nie aufgefüllt**:
nicht mit dem Vortag, nicht mit einem Mittelwert, nicht mit dem Kurs eines anderen Börsenplatzes.

## 2. Regeln

| Lage | Regel | Folge für den Zeitraum |
|---|---|---|
| Lücken zwischen Start- und Endtag | höchstens 20 % der erwarteten Sitzungen dürfen fehlen (ganzzahlig geprüft: vorhandene Kurse · 5 ≥ erwartete Sitzungen · 4); **eine** fehlende Sitzung ist immer erlaubt | sonst ausgeschlossen (Status 12 „Zu viele Börsentage ohne Kurs“, bis Software 1.17 „Zu viele fehlende Sitzungen“) |
| Starttag ohne Kurs | der Kurs am Starttag ist Pflicht | ausgeschlossen (Status 11), kein Ausweichen auf einen älteren Kurs |
| Stichtag ohne Kurs | der letzte Schlusskurs zählt, wenn die Börse seitdem höchstens eine Sitzung hatte | alle Zeiträume der Aktie enden an diesem Tag; bei zwei oder mehr verpassten Sitzungen fehlt die Aktie (Status 8) |
| Rendite | Endkurs / Startkurs − 1 | Lücken dazwischen ändern die Rendite nicht |
| Gleichmäßigkeit (R²) | Gerade durch die vorhandenen Kurse, gezählt nach ihrer Reihenfolge (1., 2., 3. Kurs …) | eine Lücke = ein Kurs weniger; die Kurse danach rücken nach |
| Volumenregeln | gelten für die vorhandenen Kurstage | eine Lücke hat kein Volumen und zählt dort nicht mit |

Die Regeln stehen in `config/methode.yaml` (`min_sitzungsabdeckung`, `fehlende_sitzungen_immer_erlaubt`,
`letzter_schlusskurs_max_verpasste_sitzungen`) und sind in [03_Methodik](03_Methodik.md) §3, §5, §15 und §15a beschrieben.

## 3. Referenzfälle

`tests/unit/test_referenz_fehlende_kurstage.py`: Zehn erfundene Aktien laufen durch den **ganzen Rechenkern**
(`compute_snapshot` mit der Konfiguration des Betriebs; eigener Endtag wie im täglichen Lauf). Die erwarteten Werte
rechnet der Test **unabhängig vom Rechenkern** nach dieser Beschreibung – Renditen und R² mit exakten Brüchen, Perzentile
und Reihenfolge mit einer eigenen kurzen Rechnung. Geprüft werden Status, Starttag, Zahl der Kurse und Sitzungen,
Rendite und R² für die Zeiträume 1, 2, 3, 7, 25, 29, 30, 60 und 90 Tage sowie die Ranglisten 3, 7, 25 und 30 Tage in den
Gewichtungen 0/100, 40/60, 50/50, 60/40 und 100/0.

**Aufbau.** Stichtag Freitag, 23.10.2026. Börsenkalender Montag bis Freitag; Aktie J an einer Börse mit Feiertag am
12.10. (wie Toronto). Kurs am j-ten Börsentag ab dem 23.09. (bei G ab dem 22.09.): p = 100 + Schritt · j, dazu jeden
zweiten Tag abwechselnd eine kleine Schwankung +δ bzw. −δ. Alle Kurse mit Umsatz.

| Aktie | Fall | 30 Tage (Start 23.09.) | weitere Zeiträume |
|---|---|---|---|
| A | keine Lücke | 100,00 → 111,00 = **+11,00 %**; 23 von 23 Kursen; R² 0,99827 | – |
| B | 07.10. ohne Zeile | **zugelassen**: 22 von 23; 100,00 → 113,20 = +13,20 %; R² 0,99650 | – |
| C | 07.10. als Leerzeile | **zugelassen** wie B: 22 von 23; +12,10 %; R² 0,99691 | dieselbe Reihe mit fehlender Zeile statt Leerzeile ergibt Zahl für Zahl dieselben Werte |
| D | 4 Sitzungen ohne Kurs | **zugelassen**: 19 von 23 (17 % fehlen); +15,40 %; R² 0,99389 | 25 Tage: 16 von 20 = **genau 20 % – noch zugelassen** (+13,42 %) |
| E | 5 Sitzungen ohne Kurs | **ausgeschlossen**: 18 von 23 (22 % fehlen) | 25 Tage: 15 von 20 – ausgeschlossen; 7 Tage: ohne Lücke – zugelassen (+3,81 %) |
| F | Starttag 23.09. ohne Kurs | **ausgeschlossen**: Starttag fehlt, kein Ausweichen auf 22.09. | 29 Tage (Start 24.09.): zugelassen (+16,49 %) |
| G | Stichtag 23.10. ohne Kurs, 22.10. vorhanden | **zugelassen mit eigenem Endtag**: 22.09. 100,00 → 22.10. 114,30 = +14,30 %; 23 von 23 | alle Zeiträume enden am 22.10. |
| H | 22. und 23.10. ohne Kurs | **fehlt in allen Zeiträumen**: zwei verpasste Sitzungen | – |
| J | Feiertag 12.10. an ihrer Börse | **zugelassen**: 22 von 22 – der Feiertag ist kein fehlender Tag; +9,60 % | – |
| K | 21.10. ohne Kurs | zugelassen: 22 von 23; +6,60 % | 3 Tage: 3 von 4 (75 %) – **zugelassen, weil eine fehlende Sitzung immer erlaubt ist**; 2 Tage: Starttag 21.10. fehlt – ausgeschlossen |

Weitere Prüfungen im selben Test: R² wird über die vorhandenen Kurse gerechnet – mit einem aufgefüllten Tag käme ein
anderer Wert heraus; und die Ranglisten des Rechenkerns stimmen in allen geprüften Zeiträumen und Gewichtungen mit der
unabhängigen Rechnung überein. **Gegenprobe (24.10.2026):** Mit der Grenze 19 statt 20 % in der unabhängigen Rechnung
schlägt der Grenzfall D (25 Tage) fehl, mit „eine Leerzeile schließt aus“ der Fall C (25, 29, 30, 60 und 90 Tage) – der
Test erkennt also eine Abweichung in beiden Regeln.

## 4. Wie fehlende Tage eine Rangliste verändern – Beispiel

Dieselben Daten, 30 Tage, nach der Regel der App und nach drei anderen Regeln (aus demselben Test):

| Regel | nur Rendite (0/100) |
|---|---|
| **App** (bis 20 % Lücken, eine immer erlaubt, letzter Schlusskurs) | D, G, B, C, A, J, K |
| streng: jede Lücke schließt aus | G, A, J |
| wie Ausgangsmodell: eine Leerzeile schließt aus | D, G, B, A, J, K |
| ohne letzten Schlusskurs (Regel bis tr-methode-1.8.0) | D, B, C, A, J, K |

Mit Gewichtung (App): 60/40 G, J, A, D, C, B, K · 50/50 G, D, A, J, B, C, K · 40/60 G, D, B, A, C, J, K.

Daran sieht man die zwei Wege, auf denen fehlende Tage wirken: (1) über die **Zulassung** – wer überhaupt in der
Rangliste steht (B, C, D und K hätten nach der strengen Regel keinen Platz); (2) bei gemischten Gewichtungen über die
**Perzentile**: Fällt eine Aktie weg, verschieben sich die Ränge aller anderen ein wenig. Die Rendite einer zugelassenen
Aktie ändert sich durch Lücken nie.

## 5. Einfluss im echten Stand vom 23.10.2026

Gemessen mit dem Workflow „Fehlende Kurstage auswerten“ (`tests/live/fehlende_tage.py`) am 24.10.2026, 14:47 Uhr, auf dem
veröffentlichten Stand `2026-10-23_68f9fbe5` (Software 1.17.0, 11.596 Aktien). Die Ranglisten dieses Skripts stimmen mit den
veröffentlichten überein (1.980 von 1.980).

| Größe | Wert |
|---|---|
| Aktie-Zeitraum-Paare in den Ranglisten (Gruppe A, 1–90 Tage) | 856.002 |
| davon mit mindestens einer fehlenden Sitzung | **2.864 (0,33 %)** – 2.839 mit genau einer, 4 mit zwei oder drei, 21 mit vier oder mehr; 108 Aktien |
| davon nur über „eine fehlende Sitzung ist immer erlaubt“ zugelassen | 3 |
| ausgeschlossen: Starttag ohne Kurs · mehr als 20 % fehlen · Schlusskurs zu alt | 614 · 123 · 2.610 Paare |
| mit letztem Schlusskurs (eigener Endtag) | 1.121 Paare, 30 Aktien |
| Art der Lücken beim Kursanbieter (114 Tage der 108 Aktien, nachgesehen am 24.10.) | 96 ohne Zeile, **14 Leerzeilen** (8 Aktien, 162 Paare), 4 inzwischen nachgeliefert |
| unter den ersten 10 aller 1.980 Ranglisten (16.400 Plätze) | 22 Plätze mit fehlender Sitzung, **keiner auf Platz 1**, keiner mit Leerzeile |

Wie viele der 1.980 Ranglisten (Gruppe A und B × 90 Zeiträume × 11 Gewichtungen) sähen nach einer anderen Regel anders aus –
gemessen mit der Gleichstandsregel bis 1.9.0 (Stand `2026-10-23_68f9fbe5`, 14:47 Uhr) und mit dem exakten Gleichstand ab
1.10.0 (Stand `2026-10-23_3f7ce5f3`, dieselben Kurse, 17:03 Uhr):

| andere Regel | anderer Platz 1 (bis 1.9.0 → ab 1.10.0) | andere erste 10, Aktien | nur andere Reihenfolge der ersten 10 |
|---|---|---|---|
| streng: jede Lücke schließt aus | 7 → **1** | 38 → **31** | 75 → **34** |
| wie Ausgangsmodell: eine Leerzeile schließt aus | 7 → **0** | 7 → **3** | 41 → **3** |
| ohne letzten Schlusskurs (bis tr-methode-1.8.0) | 9 → **0** | 11 → **2** | 112 → **14** |

Bis 1.9.0 lagen **alle** diese Wechsel auf Platz 1 in Ranglisten, in denen an der Spitze zwei Aktien rechnerisch gleich
bewertet sind: Keine Aktie mit Lücke stand auf Platz 1; mit der etwas kleineren Vergleichsmenge entschied nur die letzte
Stelle des Gleitkomma-Scores zwischen zwei Gleichbewerteten neu. Mit dem exakten Gleichstand (Abschnitt 6) entscheidet dort
die Rendite, und die Spitze bleibt: Nach der Regel des Ausgangsmodells und ohne letzten Schlusskurs wäre Platz 1 in allen
1.980 Ranglisten derselbe. Nach der strengen Regel bliebe ein Wechsel; auch er liegt in einer Rangliste mit rechnerischem
Gleichstand an der Spitze (in der Rechnung mit oder ohne die Aktien mit Lücken) – ohne diese Aktien ändern sich die
Perzentile der übrigen. Zum Vergleich der Prüffall vom 13.10.
(Ausgangsmodell): Leerzeilen betrafen damals 18 Aktien und 148 Paare; 2 Ranglisten hatten einen anderen Platz 1, 24 andere
erste 10.

## 6. Gleichstand – Regel ab tr-methode-1.10.0

**Entscheidung vom 24.10.2026:** „Bei mathematisch gleichem Score entscheidet die höhere Rendite. Sind beide Werte gleich,
verwende die ISIN als eindeutiges, stabiles Sortierkriterium. Verhindere, dass Rundungsfehler die Reihenfolge bestimmen.
Unterschiedliche Scores dürfen durch pauschales Runden nicht künstlich gleichgesetzt werden.“ Umgesetzt als
`ranking-11w-v3` (Software 1.18.0; [03_Methodik](03_Methodik.md) §7 und §15b).

**Was sich geändert hat.** Bis tr-methode-1.9.0 wurde der Score w/100 · G + (1 − w/100) · R wie im Ausgangsmodell als
Gleitkommazahl verglichen. Rechnerisch gleiche Scores können sich dabei in der letzten Binärstelle unterscheiden – dann
entschied diese Stelle, nicht die höhere Rendite, und „gleichauf“ erschien nicht. Jetzt vergleicht der Server bei
gemischter Gewichtung die ganze Zahl K = w · (d_G − 2) + (100 − w) · (d_R − 2) aus den doppelten Durchschnittsrängen;
das ist exakt Score · 2 · (M − 1). Gleiches K: höhere Kursrendite vorn, dann kleinere ISIN, als gleichauf gekennzeichnet.
Verschiedene Scores unterscheiden sich mindestens um 1 / (2 · (M − 1)) und werden nie gleichgesetzt. Bei 0/100 und 100/0
ändert sich nichts. Angezeigt wird weiter der Gleitkomma-Score mit einer Nachkommastelle; über den Platz entscheidet er
nicht.

**Der Referenzfall aus Abschnitt 3** (25 Tage, 50/50): A, D und J haben genau denselben Score 300/7 = 42,857…; als
Gleitkommazahl ist D eine Binärstelle kleiner. Bis 1.9.0 stand die Reihenfolge A, J, D; jetzt **D, A, J** (D hat die
höchste Rendite, dann A, dann J), alle drei als gleichauf gekennzeichnet
(`test_mathematically_equal_scores_are_decided_by_the_higher_return`).

**Eigene Referenzfälle** (`tests/unit/test_referenz_gleichstand.py`; die Erwartung rechnet der Test mit exakten Brüchen
selbst, Rang 1 = kleinster Wert):

| Fall | Aufbau | bis 1.9.0 | ab 1.10.0 |
|---|---|---|---|
| Gleichstand auf Platz 1 | 15 Aktien, 60/40. X: R²-Rang 13, Rendite-Rang 15. Y: R²-Rang 15, Rendite-Rang 12. Beide Scores 640/7 = 91,43 (K = 2.560) | Y auf Platz 1 (Gleitkomma eine Stelle größer) | **X auf Platz 1** (höhere Rendite), X und Y gleichauf |
| Grenze der ersten 10 | 20 Aktien, 60/40. Plätze 10 und 11 rechnerisch gleich; dazu Plätze 5 und 6 | unter den ersten 10 die Aktie mit Rendite-Rang 1 | **die Aktie mit Rendite-Rang 7**; Plätze 5/6 ebenfalls nach der Rendite; Platz 1 und die Plätze 1–9 als Menge unverändert |
| gleicher Score und gleiche Rendite | zwei Aktien mit gleicher Rendite und gleichem R² | kleinere ISIN vorn | unverändert kleinere ISIN vorn, gleichauf; dasselbe Ergebnis bei vertauschter Eingabe |
| knapp verschieden | 1.001 Aktien, 60/40. P (R²-Rang 900, Rendite-Rang 500) 73,90; Q (899, 501) 73,88 – der kleinste mögliche Abstand. Mit einer Stelle beide „73,9“; Q hat die höhere Rendite | P vor Q | **P vor Q**, nicht gleichauf. Pauschal auf eine Stelle gerundet stünde Q vorn |
| 60 Zufallsuniversen | 2 bis 240 Aktien, absichtlich viele gleiche Renditen und R²; alle elf Gewichtungen, Gruppe A und B | – | jede Reihenfolge und jedes Gleichstandskennzeichen wie die unabhängige Rechnung; die alte Regel weicht nur innerhalb rechnerisch gleicher Scores ab |

Dazu prüft derselbe Test die Veröffentlichungsprüfung (`sortierregeln` lehnt die Gleitkomma-Reihenfolge in einem Stand
nach v3 ab) und den Methodenvergleich (er zählt genau die unabhängig bestimmten Unterschiede). **Gegenprobe
(24.10.2026):** Mit Gleitkomma-Vergleich schlagen 15, mit einem auf eine Stelle gerundeten Score 2, mit „bei gleichem
Score die ISIN statt der Rendite“ 22 Prüfungen der beiden Referenzdateien fehl. Die App ordnet Untergruppen nach derselben
Regel (`app/tests/gleichstand.test.ts`; Vertragstest gegen den Server).

**Wirkung im Stand vom 23.10.2026** (Stand `2026-10-23_3f7ce5f3`, am 24.10. von 16:57 bis 17:01 Uhr mit Software 1.18.0
und Methode 1.10.0 neu gerechnet, 17:03 Uhr veröffentlicht; dieselben Kurse wie der bisherige Stand `2026-10-23_68f9fbe5`).
Der Methodenvergleich des Laufs und die unabhängige Nachrechnung (Workflow „App mit echten Daten prüfen“, 17:08–17:10 Uhr)
zählen dasselbe:

| von 1.640 Ranglisten mit Inhalt (Gruppe A und B × 90 Zeiträume × 11 Gewichtungen) | anders als mit der Regel bis 1.9.0 |
|---|---|
| Platz 1 | **4** |
| andere Aktien unter den ersten 10 | **4** |
| dieselben ersten 10, andere Reihenfolge | **65** |
| irgendein Platz | 1.308 (fast immer weit hinten; betroffen sind nur die 1.314 gemischten Ranglisten) |

Zulassung, Renditen, R², Perzentile und angezeigte Scores sind gleich geblieben (0 Aktie-Zeitraum-Paare neu oder nicht mehr
bewertet). In 336 gemischten Ranglisten stehen an der Spitze (Plätze 1–11) rechnerisch gleiche Scores; in **keiner** steht
dort jetzt die niedrigere Rendite vor der höheren (bis 1.9.0: in 69; Workflow „Fehlende Kurstage auswerten“, 17:03 Uhr). Die Nachrechnung bestätigt alle 1.980 Ranglisten
(9.987.000 Prüfungen, 0 Abweichungen).

**Prüffall 13.10. (Rechendaten des Ausgangsmodells, `tests/live/ausgangsmodell_nachrechnen.py`, am 24.10. neu gerechnet):**
Mit der Regel des Ausgangsmodells sind 1.971 von 1.980 Ranglisten gleich (wie in §14 dokumentiert). Mit der exakten Regel
sind 699 gleich (darunter die 380 leeren), Platz 1 ist in **4** und die ersten 10 sind in **61** der 1.980 Ranglisten
anders; in 1.220 Ranglisten liegt der erste Unterschied hinter Platz 10. Alle Unterschiede liegen innerhalb rechnerisch
gleicher Scores – das ist die bewusste Abweichung vom Ausgangsmodell.

**Historische Stände** bleiben, wie sie berechnet wurden (Methode bis 1.9.0, `versions.ranking` = `ranking-11w-v2`). Die
App zeigt sie unter „Frühere Stände“ mit ihrer Methode und „eingeschränkt vergleichbar“. Die unabhängige Nachrechnung
prüft jeden Stand nach seiner Regel: In alten Ständen bestätigt sie die Gleitkomma-Reihenfolge als damaliges Verhalten
und weist sie als bekannten Fehler `gleichstand_rundung` aus (fachlich falsch, keine Rechenabweichung).

## 7. Nachrechnen

```bash
# Referenzfälle (ohne Netz, wenige Sekunden)
PYTHONPATH=backend python -m unittest tests.unit.test_referenz_fehlende_kurstage tests.unit.test_referenz_gleichstand -v
# Werte für die Tabellen dieses Dokuments ausgeben (Hilfe, kein Test)
PYTHONPATH=backend python -m tests.unit.test_referenz_fehlende_kurstage --tabellen
```

Ab 1.18 prüft jeder Testlauf auch die Tabelle in Abschnitt 3 gegen die unabhängige Rechnung
(`DocumentedTable` im selben Test: Status, Kurse und Sitzungen, Anteil fehlender Tage, Start- und Endkurs, Rendite auf
2 und R² auf 5 Stellen, Start- und Endtag). Dabei fiel ein Rundungsfehler der Tabelle auf: R² von C ist 0,9969149…,
also auf fünf Stellen 0,99691 – in der Tabelle stand 0,99692 (aus dem schon auf sechs Stellen gerundeten Wert 0,996915
noch einmal gerundet). Die Rechnung selbst war richtig.

Echte Daten: GitHub → Actions → „Fehlende Kurstage auswerten“ → Run workflow (nur lesend; Zählwerte in der Laufübersicht).
