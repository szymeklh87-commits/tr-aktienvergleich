# Methodik (Methodenversion tr-methode-1.8.0)

Diese Datei beschreibt verbindlich, wie jeder Wert der App entsteht. Gerechnet wird ausschließlich auf dem Server (Python, `backend/traktien/analytics`) in Gleitkommazahlen doppelter Genauigkeit ohne Zwischenrundung. Gerundet wird nur in der Anzeige. Die App rechnet Perzentile und Scores aus veröffentlichten ganzzahligen Rängen mit derselben Operationsfolge nach; die Gleichheit wird in jedem Prüflauf Bit für Bit getestet.

Die Ranglisten beschreiben die Vergangenheit. Sie sind keine Prognose, keine Empfehlung und kein validierter Handelsvorteil.

Ab 1.7.0 gelten die im Auftrag vom 13.10.2026 dokumentierten Regeln des Ausgangsmodells **TR-90D-11W-two-universes-v1.1** (Volumen an jeder Beobachtung, positives Volumen an Start und Ende, Split im Fenster zurückgehalten, Gleichstand Score → Rendite → ISIN). Ab 1.8.0 schließt ein einzelner fehlender Börsentag beim Kursanbieter einen Zeitraum nicht mehr aus (höchstens 20 % fehlende Tage statt 2 %; Entscheidung vom 13.10.2026). Jeder Lauf vergleicht sein Ergebnis mit den Regeln der Vorversion – Abschnitte 14 und 15.

## 1. Universum und Identität

- Quelle: öffentliche Instrumentenliste von Trade Republic (PDF), nur der Aktienabschnitt. ISINs mit falscher Prüfziffer, Dubletten und Nicht-Aktien (Fonds, ETP, Bezugsrechte, Optionsscheine laut Identitätsquelle) werden mit eigenem Status geführt und nicht gerankt.
- Eine ISIN erhält genau **eine** Referenznotierung (Börse, Währung, Kalender), ausgewählt nach dokumentierter Länder- und Börsenpräferenz (`config/boersen.yaml`). Mehrere Börsenplätze derselben ISIN erzeugen keinen zweiten Rang; verschiedene Aktiengattungen (verschiedene ISINs) bleiben getrennt.
- Schutz vor fehlerhaften Listen: Weniger als 1.000 Einträge, mehr als 10 % Änderung gegenüber der Vorversion oder mehr als 2 % ungültige ISINs → die neue Liste wird zurückgehalten, die alte bleibt gültig, bis sie geprüft und freigegeben ist.
- Listung in der TR-Liste heißt nicht, dass die Aktie im eigenen Konto jederzeit handelbar ist.

## 2. Gemeinsamer Kursstichtag D

D ist der jüngste Kalendertag, an dem jede an diesem Tag geöffnete Börse des Universums ihre reguläre Sitzung beendet hat (Schlusszeit laut Börsenkalender plus 60 Minuten Nachlieferungsfrist). Alle Fenster aller Aktien enden an D. Eine Aktie ohne geprüften Schlusskurs an D erhält „Schlusskurs am Stichtag fehlt“ (Börse geöffnet) oder „Markt am Stichtag geschlossen“ (Feiertag) – sie rückt nie mit einem älteren Enddatum in die gemeinsame Rangliste.

Die Veröffentlichung ist **vollständig**, wenn alle Börsen mit Sitzung an D geliefert haben (eine Börse gilt als geliefert, wenn mindestens 80 % ihrer Aktien einen Kurs an D haben), sonst ein deutlich markierter **Teilstand** (mindestens 90 % der Börsen) oder keine Veröffentlichung.

## 3. Zeitraum h = 1 … 90 Kalendertage

- Ziel-Startdatum B = D − h (Kalendertage).
- Startsitzung S = letzte Börsensitzung der Referenzbörse am oder vor B, höchstens 7 Kalendertage vor B.
- An S muss ein echter Schlusskurs vorliegen. Es wird **nicht** auf einen älteren Kurs ausgewichen („Startkurs fehlt“).
- Verwendet werden alle echten Tagesschlusskurse von S bis D. Fehlende Sitzungen werden nicht aufgefüllt.

Beispiel: D = Montag 12.10.2026, h = 30 → B = Samstag 12.09.2026 → S = Freitag 11.09.2026. Für h = 31 (B = Freitag 11.09.) ist S derselbe Tag – benachbarte Kalenderfenster können identische tatsächliche Endpunkte haben. Jede Zeile nennt deshalb Beginn und Ende.

## 4. Kennzahlen eines Fensters

Mit den N Schlusskursen p₀ … p_(N−1) (splitbereinigt, in Notierungswährung):

| Kennzahl | Formel |
|---|---|
| Kursrendite | r = p_(N−1) / p₀ − 1 |
| Trendgerade | Kleinste Quadrate auf dem Preis mit t = 0, 1, …, N−1: Steigung m, Achsenabschnitt b |
| Gleichmäßigkeit | R² = 1 − SSE / SST, SSE = Σ(p_i − (m·t_i + b))², SST = Σ(p_i − p̄)² |
| Relative Steigung | s = 100 · m / p̄ (Prozent des Durchschnittskurses je Handelsbeobachtung) |
| Residualrauschen | q = 100 · √(SSE / N) / p̄ |
| Größter Rückgang | MDD = max_i (1 − p_i / max(p₀ … p_i)), angezeigt mit Minus |
| Volumenabdeckung | Anteil der Beobachtungen mit belegtem positivem Umsatz |
| Positive Schlusskursvergleiche (ab `kennzahlen-v2`) | Zahl der Beobachtungen mit p_i > p_(i−1), von N − 1 Vergleichen; gleichbleibende Kurse zählen nicht |

Beispiele: 100 → 120 ergibt +20 % (nicht +0,2 % und nicht +120 %). Die Reihe 100, 120, 90, 110 hat einen größten Rückgang von 25 % (120 → 90), angezeigt „−25,00 %“.

R², Steigung und Rauschen werden erst ab 15 echten Tageskursen ausgewiesen; darunter sind sie nicht belastbar (zwei Punkte liegen immer exakt auf einer Geraden). Ist die Reihe konstant (SST praktisch null), ist R² „nicht definiert“. Ein numerisch unplausibles R² (außerhalb [0, 1] über die Toleranz 10⁻⁹ hinaus) wird nicht gerundet, sondern macht nur dieses Fenster „Trend nicht definiert“ (Hinweis in der Detailansicht).

Grenzen: R² misst die Nähe zu einer geraden Linie, nicht Sicherheit und nicht die Wahrscheinlichkeit weiterer Gewinne. Eine gleichmäßig fallende Reihe hat ebenfalls ein hohes R² – deshalb gelten die Aufwärtsbedingungen in Abschnitt 6. Ein stetig, aber gekrümmt steigender Kurs (zum Beispiel immer schneller) kann ein niedrigeres R² haben, obwohl er nie gefallen ist.

## 5. Datenprüfungen

Ein Fenster erhält genau einen Hauptstatus, geprüft in dieser Reihenfolge:

| Code | Status | Bedeutung |
|---|---|---|
| 1–4 | Identität | ISIN ungültig, kein Aktieninstrument, noch nicht geprüft, unklar |
| 5–6 | Daten | Kalender fehlt, keine verwertbaren Kurse |
| 7 | Markt am Stichtag geschlossen | Feiertag an D – kein Datenfehler |
| 8 | Schlusskurs am Stichtag fehlt | Börse offen, Kurs fehlt |
| 9 | Zu kurze Historie | reicht nicht bis S zurück |
| 10 | Keine Startsitzung | keine Sitzung in den 7 Tagen vor B |
| 11 | Startkurs fehlt | Sitzung S ohne gültigen Kurs |
| 12 | Zu viele fehlende Sitzungen | ab 1.8.0: an mehr als 20 % der erwarteten Sitzungen zwischen S und D fehlt ein Kurs (geprüft als ganzzahliges Verhältnis 4/5, vor jeder Rundung); eine einzelne fehlende Sitzung ist immer erlaubt. Bis 1.7.0: weniger als 98 % (49/50). Fehlende Tage werden nie aufgefüllt |
| 13 | Kapitalmaßnahme/Datenfehler prüfen | im Fenster ein **gemeldeter Split bzw. eine Zusammenlegung** (ab 1.7.0, auch bei bereinigter Reihe; Freigabe nur nach dokumentierter Prüfung), ein Tagessprung p_t/p_(t−1) > 3 oder < 1/3, ein möglicherweise unbereinigter Split, oder an S bzw. D eine Kursbewegung über 10 % an einem Tag ohne belegten Umsatz |
| 14 | Zu wenig belegtes Handelsvolumen | ab 1.7.0: an **einer Beobachtung kein gemeldetes Volumen** (fehlend, nicht endlich oder negativ), oder an **S oder D kein positives Volumen**; außerdem weniger als 80 % der Kurstage (Beobachtungen) mit positivem Umsatz (fehlendes Volumen zählt nicht als 0 und nicht als positiv) |
| 15 | Für Gleichmäßigkeit zu wenig Tagesdaten | Rendite veröffentlicht, weniger als 15 Tageskurse |
| 16 | Nicht steigend | Rendite veröffentlicht, r ≤ 0 oder m ≤ 0 – kein Datenfehler |
| 17 | Trend nicht definiert | Rendite veröffentlicht, R² nicht berechenbar |
| 18 | Gleichmäßig steigend bewertbar | in allen elf Gewichtungen enthalten |

Zurückgehaltene Sprünge werden weder geglättet noch durch 100 geteilt. Nach Prüfung mit verlässlicher Quelle kann ein echter Sprung in `config/pruefungen.yaml` freigegeben werden (mit Quelle und Notiz). Es gibt keinen Mindestumsatz in Euro und keinen Mindestkurs; kleine und schwach gehandelte Aktien bleiben mit Hinweisen sichtbar.

## 6. Vergleichsmengen V und U

- **V(D, h):** alle Aktien mit Status 15–18 – veröffentlichte Kursrendite (mindestens zwei echte Kurse, alle Prüfungen bestanden). Negative Renditen gehören dazu.
- **U(D, h):** alle Aktien mit Status 18 – zusätzlich mindestens 15 Tageskurse, r > 0, m > 0 und R² definiert. U ist immer Teil von V.

## 7. Perzentile, Score, elf Gewichtungen

Innerhalb einer Vergleichsmenge mit M Aktien erhält jede Aktie für ein Merkmal den aufsteigenden Durchschnittsrang (exakt gleiche Werte teilen sich den Mittelwert ihrer Plätze) und daraus

  P = 100 · (Durchschnittsrang − 1) / (M − 1),  bei M = 1: P = 100.

G ist das Perzentil von R², R das Perzentil der Kursrendite. Für die Gewichtung w (Anteil Gleichmäßigkeit in Prozent, w ∈ {0, 10, …, 100}):

  Score(w) = (w/100) · G + (1 − w/100) · R.

Beispiel Perzentile: Renditen 5 %, 8 %, 8 %, 9 % → Durchschnittsränge 1; 2,5; 2,5; 4 → Perzentile 0; 50; 50; 100.

Beispiel Score mit G = 90 und R = 60: w = 0, 10, …, 100 ergibt 60, 63, 66, 69, 72, 75, 78, 81, 84, 87, 90.

Die Bezeichnung nennt immer beide Anteile, zum Beispiel „60 % Gleichmäßigkeit · 40 % Rendite“. Alte Bezeichnungen werden abgebildet: return → 0, mix40 → 40, mix50 → 50, mix60 → 60, consistency → 100.

Bei M = 1 lautet der Pflichthinweis „Einziger qualifizierter Titel – keine relative Konkurrenzbewertung“. Bei M = 0 gibt es keine Rangliste und einen konkreten Grund.

### Nativ und gleiches Vergleichsfeld

| | 0/100 | 10/90 … 100/0 |
|---|---|---|
| **nativ** (Standard) | V, Perzentil R innerhalb V | U |
| **gleiches Vergleichsfeld** (common_trend) | U | U |

Nur im gleichen Vergleichsfeld zeigt ein Vergleich zweier Gewichtungen allein die Wirkung der Gewichtung. Beide Varianten werden nie zusammengezählt.

### Reihenfolge und Gleichstände (`ranking-11w-v2`, ab 1.7.0)

Für alle elf Gewichtungen: **Score absteigend, dann Kursrendite absteigend, zuletzt ISIN aufsteigend** – mit ungerundeten Werten, gerundet wird erst nach der Sortierung. Bei 0/100 ist der Score das Renditeperzentil (Reihenfolge = Kursrendite), bei 100/0 das R²-Perzentil (Reihenfolge = R²). Exakt gleiche Scores werden als „gleichauf“ gekennzeichnet; die Kursrendite und zuletzt die ISIN legen nur die Reihenfolge der Anzeige fest. Die App nennt den Wert „Rangscore 0–100“ – keine Prognose, keine Wahrscheinlichkeit, keine erwartete Rendite.

Bis tr-methode-1.6.0 (`ranking-11w-v1`) entschied bei gemischten Gewichtungen nach der Rendite noch R², bei 100/0 nach R² die relative Steigung und das Rauschen. Das betrifft nur exakt gleiche Werte; der Methodenvergleich (Abschnitt 14) zählt jede dadurch geänderte Spitze mit.

### Untergruppen (Watchlist)

„Nur innerhalb der Watchlist“ schränkt V und U auf die gemerkten Aktien ein und berechnet die Perzentile darin neu. Die globale Rangliste bleibt unverändert; die Ansicht ist als Untergruppe beschriftet.

## 8. Höchste Rendite 1–90 Tage

Je h die Aktie mit der höchsten ungerundeten Kursrendite aus V (identisch zu Platz 1 der nativen 0/100-Liste). Exakt gleiche Rendite → Gleichstand sichtbar, alle Gleichplatzierten werden genannt. Leeres V → leere Zeile mit Grund. Sind alle Renditen negativ, steht der geringste Verlust mit Vorzeichen da.

**Gesamtmaximum:** höchste Kursrendite über alle geprüften Aktie-Zeitraum-Paare dieses Stands – ein rückblickend ausgewählter Bestwert, keine Haltedauer und keine erwartete Rendite. Dieselbe Aktie mit identischem tatsächlichem Start/Ende in mehreren h ist kein Gleichstand; die weiteren h werden genannt. Renditen werden nie addiert oder annualisiert.

### Zwei Rendite-Ranglisten (ab 1.1, `umsatz-v1`)

| Rangliste | Menge | Sortierung |
|---|---|---|
| 1. Höchste Kursrendite | V (alle Aktien mit veröffentlichter Kursrendite) | nur Kursrendite, absteigend (0 % Gleichmäßigkeit / 100 % Kursrendite) – identisch mit der nativen 0/100-Liste |
| 2. Höchste Kursrendite – Ø Tagesumsatz mindestens 10 Mio. USD | V ∩ L | dieselbe Reihenfolge wie Rangliste 1, nur ohne die Aktien außerhalb von L |

L enthält jede Aktie, deren Ø Tagesumsatz bestimmt ist und mindestens 10 Mio. USD beträgt. Der Umsatz ist ein Aufnahmefilter, kein Sortierkriterium und kein zweiter Renditewert. Beide Listen nutzen denselben Kursstichtag, dieselben Kurse, dieselbe Renditeformel und dieselben ungerundeten Werte. Eine Veröffentlichungsprüfung (`ranking2_teilmenge_gleiche_rendite`) bestätigt das für jeden Stand: Rangliste 2 ist exakt Rangliste 1 ohne die nicht aufgenommenen Aktien.

**Ø Tagesumsatz** (je Instrument, gleich für alle Zeiträume):

```
Umsatz der Sitzung t        = Schlusskurs_t × gemeldetes Volumen_t   (beide splitbereinigt, gleiche Notierung)
Ø Tagesumsatz (Landeswährung) = Mittelwert über die Sitzungen mit Daten unter den letzten 20 abgeschlossenen Sitzungen
Ø Tagesumsatz (USD)          = Mittelwert über dieselben Sitzungen von Umsatz_t × (USD je Einheit)_t
```

- Die 20 Sitzungen kommen aus dem Börsenkalender der Referenzbörse (bis einschließlich Kursstichtag), nicht aus der Kursdatei. Wochenenden und Feiertage zählen deshalb nie mit.
- Fehlt an einer Sitzung der Kurs oder das Volumen, wird sie ausgelassen – nicht als null gezählt. Ein gemeldetes Volumen von 0 zählt mit 0.
- Mindestens 16 der 20 Sitzungen brauchen ein positives Volumen; sonst „nicht bestimmbar“.
- Untereinheiten werden in die Hauptwährung umgerechnet (500 GBp = 5 GBP).
- Liegt ein Split oder eine Zusammenlegung innerhalb der 20 Sitzungen, gilt der Umsatz als nicht bestimmbar (Kapitalmaßnahmen dürfen den Wert nicht verzerren).
- USD-Umrechnung indikativ mit den EZB-Referenzkursen: USD je Einheit = (USD je EUR) / (Währung je EUR), je Sitzung der Kurs dieses Tages oder der letzte davor, höchstens 5 Kalendertage alt. Ohne Kurs für eine der Sitzungen gibt es keinen USD-Wert und damit keine Aufnahme in Rangliste 2; Rangliste 1 bleibt möglich.
- Gemessen wird der Umsatz an der Referenzbörse (bei US-Werten das zusammengefasste US-Volumen des Kursanbieters), nicht die Summe aller Handelsplätze.

**Kennzeichen „sehr niedriger Umsatz“:** bestimmter Ø Tagesumsatz unter 1 Mio. USD. Ist der Umsatz nicht bestimmbar, steht in Rangliste 1 „Umsatz nicht bestimmbar“ mit Grund.

**Übernahmemuster (Hinweis am Fenster):** größter Tagesanstieg im Fenster mindestens 15 %, danach an mindestens 3 Sitzungen bis zum Fensterende jede Tagesbewegung höchstens ±1 %. Typisch für ein Übernahmeangebot; die Rendite bleibt veröffentlicht, wird aber gekennzeichnet. Daneben bleiben die bisherigen Hinweise: Impulstag, Split im Fenster, geprüfter Kurssprung.

### Abgleich mit einem zweiten Börsenplatz (ab 1.2; seit 1.5.1 `boersenplatz-v3`)

Geprüft wird jede Aktie, die in mindestens einem Zeitraum unter den ersten 10 Plätzen von Ranking 1 oder Ranking 2 steht – dann für alle Zeiträume, in denen sie eine Kursrendite hat. Höchstens 600 Aktien je Lauf, beste Plätze zuerst.

1. **Zweiter Börsenplatz:** aus den Notierungen der Identitätsquelle (OpenFIGI) zur selben ISIN, ohne die Referenzbörse, ohne Notierungen mit demselben Anbietersymbol (z. B. NYSE und Nasdaq liefern bei Yahoo dieselbe US-Kursreihe) und ohne OTC-Märkte. Reihenfolge: Xetra, Frankfurt, dann die Standardreihenfolge. Die Wahl wird 45 Tage wiederverwendet.
2. **Kurse:** splitbereinigte Tagesschlusskurse dieses Platzes vom selben Kursanbieter. Maßgeblich ist der Börsenkalender des zweiten Platzes: Hatte er am tatsächlichen Start- bzw. Enddatum der Referenz eine Sitzung, zählt nur der Schlusskurs genau dieses Tages; hatte er keine (Feiertag dort), der Schlusskurs seiner letzten Sitzung davor, höchstens 4 Kalendertage früher. Fehlt dieser Schlusskurs beim Kursanbieter, heißt es „Vergleichskurse fehlen“ – es wird nicht auf einen älteren Kurs ausgewichen. Bis `boersenplatz-v1` galt der letzte *gelieferte* Schlusskurs bis 4 Tage vorher; am Teilstand vom 12.10.2026 wurde so mangels Xetra-Kursen vom Montag der Freitagskurs mit dem Montagskurs der USA verglichen, und 64 von 89 geprüften Aktien erschienen als auffällig. Ohne Kalender des zweiten Platzes gilt weiter die Regel von v1; ist sein Kalender nicht lesbar, bleiben die betroffenen Aktien „nicht geprüft“. Bricht der Abgleich mit einem Fehler ab, erscheint der Datenstand trotzdem – ohne Abgleich und ohne Kennzeichen, mit Hinweis (ab 1.5.1).
3. **Umrechnung:** in die Währung der Referenznotierung mit den EZB-Referenzkursen des jeweiligen Kurstags (über USD als Kreuzkurs); gleiche Währung ohne Umrechnung; Untereinheiten (Pence) in die Hauptwährung.

```
Abweichung Wertentwicklung = (1 + r_zweiter Platz) / (1 + r_Referenz) − 1
Abweichung Endkurs         = Endkurs_zweiter Platz (umgerechnet) / Endkurs_Referenz − 1

bis boersenplatz-v2: auffällig, wenn |ln(1 + Abweichung)| > ln(1,10)   (Wertentwicklung oder Endkurs)

ab boersenplatz-v3:
σ          = 1,4826 × Median |d − Median(d)|,  d = ln(P_t / P_t−1) der Referenz, letzte 20 Tagesrenditen
Schwelle_W = min( max( ln(1,10); 3 · σ · √2 ); ln 2 )      Wertentwicklung: Start- und Endkurs betroffen
Schwelle_E = min( max( ln(1,10); 3 · σ ); ln 2 )           Endkurs
auffällig, wenn |ln(1 + Abweichung Wertentwicklung)| > Schwelle_W  oder  |ln(1 + Abweichung Endkurs)| > Schwelle_E
verglichen wird nur, wenn der zweite Platz am Start- und am Enddatum Umsatz hatte (Volumen > 0; unbekannt zählt als vorhanden)
```

Warum v3: Im ersten vollständigen Stand (12.10.2026, `boersenplatz-v2`) waren 75 von 102 geprüften Spitzenaktien in 3.080 von 8.492 Zeiträumen „auffällig“. Geprüft werden nur die ersten Plätze der Rendite-Ranglisten – meist stark schwankende kleine Werte. Für sie ist eine feste 10-%-Schwelle zu eng: Xetra schließt um 17:30 Uhr, New York um 22:00 Uhr deutscher Zeit, und auch zwischen anderen Plätzen liegen die Schlusszeiten oft Stunden auseinander; bei einer Aktie, die sich üblicherweise um 8 % am Tag bewegt, erklären diese Stunden allein Abweichungen weit über 10 %. Kurse ohne Umsatz sind nur fortgeschrieben. Die Schwelle bleibt für ruhige Aktien bei 10 % (3 · σ · √2 < 10 % für σ unter 2,4 %), Abweichungen ab Faktor 2 (etwa ein nicht bereinigter Split) sind immer auffällig. Jeder Lauf weist aus, was nach der festen 10-%-Regel auffällig gewesen wäre und warum es das nicht mehr ist (ohne Umsatz am Vergleichsplatz, innerhalb der üblichen Schwankung) – unter ☰ → Datenstand & Betrieb und im Kurzbericht des Laufs. Auswertung des ersten Laufs mit v3 (13.10.2026, 22:13 Uhr, gleiche Kurse): Von den 3.080 nach fester Regel auffälligen Zeiträumen (75 Aktien) beruhten 2.934 auf Kursen ohne Umsatz am Vergleichsplatz und 95 lagen innerhalb der üblichen Schwankung; 51 Zeiträume (8 Aktien) bleiben auffällig. Die Kehrseite: Für viele Spitzenwerte gibt es am zweiten Platz an Start- oder Enddatum keinen Umsatz, dann entfällt der Vergleich (in der App mit Grund).

Eine Abweichung des Endkurses betrifft alle Zeiträume der Aktie (alle enden mit demselben Kurs). Auffällige Zeiträume tragen den Fensterhinweis 5 „Auffällige Kursabweichung zwischen Börsenplätzen“; die App zeigt zusätzlich Börse, Symbol, Rendite dort und die Abweichungen. Der Abgleich ist nur ein Hinweis: Rendite, Rang und Aufnahme in beide Ranglisten bleiben die der Referenzbörse. Eine Veröffentlichungsprüfung (`boersenplatz_kennzeichen`) bestätigt, dass der Hinweis genau bei den auffälligen Vergleichen gesetzt ist.

## 9. Häufigste Aktien

Eine **Zelle** ist (Snapshot, Vergleichsfeld, h, w); höchstens 90 × 11 = 990 je Vergleichsfeld. Gültig ist eine Zelle mit veröffentlichter Rangliste (M ≥ 1).

| Größe | Bedeutung |
|---|---|
| N1, N3, N10 | Zellen mit Platz 1, Platz ≤ 3, Platz ≤ 10 |
| A | Zellen, in denen die Aktie überhaupt einen Rang hat |
| E | gültige Zellen der Auswahl (Nenner) |
| H_K | verschiedene Zeiträume mit mindestens einem Top-K-Treffer (≤ 90) |
| W_K | verschiedene Gewichtungen mit Top-K-Treffer (≤ 11) |
| effektive Fenster | verschiedene tatsächliche Start/End-Paare hinter den Treffern |

Es gilt N1 ≤ N3 ≤ N10 ≤ A ≤ E. Sortierung bei einer Gewichtung: Top 10 → N10, N3, N1, ISIN; Top 3 → N3, N1, N10, ISIN; Platz 1 → N1, N3, N10, ISIN. Bei allen Gewichtungen zusätzlich H_K an zweiter Stelle. Schalter „Meiste verschiedene Zeiträume“: H_K, N_K, N1, ISIN.

Beispiel: Eine Aktie ist bei 30 Tagen in allen elf Gewichtungen unter den Top 10 → 11 Treffer, aber 1 Zeitraum. Eine andere ist bei einer Gewichtung in elf verschiedenen Zeiträumen unter den Top 10 → ebenfalls 11 Treffer, aber 11 Zeiträume.

Jede Häufigkeitsliste nennt ihr Universum. Ohne Auswahl wird über alle Aktien mit veröffentlichter Kursrendite bzw. die gleichmäßig gestiegenen Aktien gezählt (ohne Umsatzfilter). Bei „Nur Rendite“ lässt sich der Umsatzfilter wählen; dann zählen nur die Fundstellen der Rangliste 2 (Menge V ∩ L, Nenner aus deren Feldgrößen). Beide Varianten werden nie gemischt.

Anteile N_K/E („Anteil aller gültigen Listen“) und N_K/A („Anteil, wenn auswertbar“) sind Zusatzinformationen, keine Gewinnwahrscheinlichkeiten. Benachbarte Zeiträume und ähnliche Gewichtungen nutzen fast dieselben Kurse; viele Treffer sind keine unabhängigen Bestätigungen. Fundstellen mit weniger Kandidaten als K werden als kleines Vergleichsfeld markiert. Gezählt wird nur der gewählte Datenstand; Tagesupdates addieren nichts.

## 10. Charts

Charts zeigen die tatsächlich verwendeten, splitbereinigten Tagesschlusskurse. Linien verbinden Beobachtungen; erwartete Sitzungen ohne Kurs bleiben als markierte Lücke sichtbar. Tooltips zeigen nur echte Datenpunkte. Die optionale „Anpassung an vergangene Kurse“ ist die OLS-Gerade des Fensters, endet am Stichtag und wird nur gezeigt, wenn ihre Steigung mit der veröffentlichten Kennzahl übereinstimmt. Vergleiche mehrerer Aktien sind auf 100 am gemeinsamen echten Basistag indexiert (Index = 100 · p(t) / p(Basis)); verschiebt sich der Beginn wegen gemeinsamer Datenverfügbarkeit, wird das genannt. 100 ist kein Eurobetrag.

## 11. Bewusste Vereinfachungen

- Ranglisten: keine Dividenden, keine Gebühren und Steuern, keine Euro-Umrechnung – Kursrendite in Notierungswährung. Die USD-Umrechnung gilt nur für den Umsatzfilter. Ausnahme ist allein das gedachte Regeldepot der Umschichtungs-Regel (Abschnitt 12), das in Euro mit Kosten und Steuern rechnet.
- Abgleich mit einem zweiten Börsenplatz nur für die ersten Plätze der Rendite-Ranglisten; alle übrigen Aktien werden nur an ihrer Referenzbörse betrachtet (09_Bekannte_Luecken).
- Nur Tagesschlusskurse, kein Intraday.
- Die Schwellen (15 Tageskurse, höchstens 20 % fehlende Börsentage, 80 % Kurstage mit Umsatz, Faktor 3, 10 % ohne Umsatz) sind transparente Startregeln, kein nachgewiesener Prognosevorteil. Jede Änderung ist eine neue Methodenversion.

## 12. Umschichtungs-Regel (ab 1.3, `rotation-v1`)

Eine feste, mechanische Regel zum Ausprobieren – keine Anlageberatung, keine Prognose, kein Signal mit nachgewiesenem Vorteil. Sie beantwortet: *Was wäre passiert, wenn man immer die N Aktien mit dem stärksten Kursanstieg der letzten Wochen zu gleichen Teilen gehalten und zu festen Terminen umgeschichtet hätte – und was würde diese Regel heute tun?* Die Rendite-Ranglisten (Abschnitte 3–9) bleiben davon unberührt.

### Wochenwerte

Gerechnet wird mit Wochenwerten je Aktie (Woche = Montag bis Freitag, Schlüssel ist der Freitag):

| Wert | Bedeutung |
|---|---|
| close | letzter splitbereinigter Schlusskurs der Woche (fehlt, wenn die Woche keinen Kurs hat – nichts wird aufgefüllt) |
| first_close, first_day | Schlusskurs und Tag der ersten Sitzung der Woche mit Kurs (Ausführungskurs) |
| turnover | Summe Schlusskurs × Volumen über die Sitzungen mit Kurs und Volumen |
| with_data, positive | Sitzungen mit Volumenangabe bzw. mit Volumen > 0 |
| observed, sessions | Sitzungen mit Kurs bzw. Sitzungen laut Börsenkalender |
| jump | größte Tagesbewegung \|ln(Kurs / Vorkurs)\| der Woche, einschließlich des Übergangs von der Vorwoche |

Ältere Wochen stammen aus einem einmaligen Langabruf (bis 3 Jahre, Tabelle `week_bar`), jüngere werden in jedem Lauf aus den geprüften Tageskursen neu verdichtet. Eine Langhistorie bekommen Aktien mit einem heutigen Ø Tagesumsatz ab 2 Mio. USD; einmal aufgenommen, bleiben sie. Nach einem neuen Split wird die Langhistorie zuerst neu geladen.

### Regel

1. **Kandidaten am Prüftag t** (Freitag): Ø Tagesumsatz der letzten 4 Wochen ≥ 10 Mio. USD (Σ turnover ÷ Σ with_data, mit dem EZB-Referenzkurs des Prüftags in USD umgerechnet), positives Volumen an ≥ 80 % der Sitzungen dieser 4 Wochen, Kurse an ≥ 90 % der Sitzungen im Trendzeitraum, kein Tagessprung über Faktor 3 im Trendzeitraum, Wechselkurs vorhanden.
2. **Trend:** `Trend = close(t) / close(t − L) − 1` mit L = 13 Wochen (91 Tage) oder 4 Wochen (28 Tage), in Notierungswährung. Rangfolge: höherer Trend zuerst, bei exakt gleichem Trend nach ISIN.
3. **Termine:** Entscheidung nach Börsenschluss am ersten Freitag des Monats (Variante: jeden Freitag) mit den Kandidaten und Rängen dieses Tages. **Ausführung zum Schlusskurs der ersten Sitzung danach** (first_close der Folgewoche, je Börse; fehlt er, der Wochenschluss, sonst der letzte bekannte Kurs) – so, wie man die Entscheidung frühestens umsetzen kann. Bewertet wird zu den Freitagsschlusskursen.
4. **Halten und Tauschen:** Eine gehaltene Aktie bleibt, solange ihr Rang ≤ 2·N ist (Haltepuffer gegen ständiges Tauschen); sonst wird sie ganz verkauft. Freie Plätze bekommen die bestplatzierten nicht gehaltenen Kandidaten (Rang ≤ N, das folgt aus der Regel). Neue Positionen erhalten 1/N des Depotwerts. Gehaltene werden nur angeglichen, wenn ihr Anteil mehr als 5 Prozentpunkte von 1/N abweicht (erst Teilverkäufe, dann Aufstockungen). Reicht das Geld nicht für alle Käufe, werden sie gleichmäßig gekürzt; übriges Geld bleibt Bargeld.
5. **Kosten:** je Order 1 € und 0,1 % Kursabschlag (Kauf zu Kurs × 1,001, Verkaufserlös × 0,999). Gehandelt wird mit Bruchteilen.
6. **Steuer** (wie bei der Bank beim Verkauf): realisierter Gewinn = Erlös nach Kosten − Anschaffungskosten einschließlich Kosten. Gewinne werden zuerst mit dem Verlusttopf verrechnet, dann mit dem Sparerpauschbetrag (1.000 € je Kalenderjahr), der Rest mit 26,375 % (Abgeltungsteuer + Solidaritätszuschlag, ohne Kirchensteuer) besteuert. Ein Verlust erstattet zuerst Steuer auf Gewinne desselben Jahres, gibt dann in diesem Jahr verbrauchten Pauschbetrag frei und geht im Übrigen in den Verlusttopf (Vortrag).
7. **Euro:** Kurse × EUR je Kurseinheit (EZB-Referenzkurs des Tages oder der letzten 5 Tage; Untereinheiten wie Pence in die Hauptwährung). Die EZB-Reihe für den Rückblick wird einmal als ZIP-Datei geladen und gespeichert.

### Varianten und Vergleich

Gerechnet werden alle 24 Kombinationen aus N ∈ {5, 10}, Rhythmus ∈ {monatlich, wöchentlich}, L ∈ {13, 4} Wochen und Startkapital ∈ {5.000, 10.000, 25.000 €}; Standard ist 5 Aktien, monatlich, 13 Wochen, 10.000 €. Zu jeder Variante gibt es zwei Vergleichslinien: dieselbe Regel ohne Kosten und Steuern sowie „alle Kandidaten zu gleichen Teilen“ (an jedem Termin neu aufgeteilt, ohne Kosten). Kennzahlen: Endwert, Rendite, Rendite pro Jahr (erst ab 365 Tagen Rückblick), größter Rückgang der Freitagswerte, Zahl der Termine und Orders, Kosten, Steuern, Verlusttopf.

### Tagesvorschlag

Ausgangspunkt ist das Regeldepot nach der letzten im Rückblick ausgeführten Umschichtung, bewertet zu den Kursen des Kursstichtags D.

- War der letzte Freitag ein Prüftag und ist die Ausführung im Rückblick noch nicht enthalten, zeigt die App diese **beschlossenen** Änderungen („Was die Regel jetzt umsetzt“, Ausführung zum Schlusskurs des nächsten Handelstags).
- Sonst wendet sie dieselbe Regel auf den neuesten Stand an – Wochen rückwärts ab D statt ab Freitag – und zeigt, was die Regel **nach heutigem Stand** am nächsten Prüftag ändern würde.

Beträge in Euro sind Anteil × Depotwert; die App kann sie auf einen selbst eingegebenen Depotwert umrechnen (gleiche Anteile, gespeichert nur auf dem Gerät).

### Grenzen

- **Überlebende:** Der Rückblick kennt nur Aktien, die heute in der TR-Liste stehen und heute mindestens 2 Mio. USD am Tag umsetzen. Inzwischen insolvente, übernommene oder abgestürzte Aktien fehlen; das Ergebnis ist dadurch eher zu gut.
- Kein Handel zum genauen Kurs: Spanne, Uhrzeit und Kosten weichen in Wirklichkeit ab; Bruchteile sind nicht überall handelbar.
- Keine Dividenden, keine Quellensteuer, keine Kirchensteuer, keine Teilfreistellung, keine Umtauschkosten.
- Trendregeln können lange schlechter laufen als der Vergleich; ein gutes Ergebnis im Rückblick ist keine Vorhersage.

Eine Veröffentlichungsprüfung (`umschichtung_regel_eingehalten`) bestätigt für jeden Stand: alle Varianten gerechnet, Verläufe vollständig und positiv, Käufe nur unter den ersten N Plätzen, höchstens N Positionen, kein negatives Bargeld, Gebühren = Orders × 1 €, Orders nur an Prüftagen.

## 13. Gruppenvergleich A/B (ab 1.4, `gruppen-v1`)

Zwei Aktiengruppen über dieselben Zeiträume, mit demselben Kursstichtag D, denselben Zeitregeln (Abschnitt 3), derselben Renditeformel `Kursrendite = (Endkurs / Startkurs − 1) × 100` und derselben Gleichmäßigkeitsberechnung (Abschnitt 4):

| Gruppe | Ausgangsmenge | Vergleichsfeld 0/100 (nativ) | Vergleichsfeld 10/90 … 100/0 |
|---|---|---|---|
| A – ohne zusätzlichen Mindestumsatz | alle Aktien der TR-Liste mit ausreichender Datenqualität | V | U |
| B – höherer Handelsumsatz | dieselbe Menge, zusätzlich Ø Tagesumsatz ≥ 10 Mio. USD über 20 abgeschlossene Sitzungen (Abschnitt 8, Menge L) | V ∩ L | U ∩ L |

Alle Prüfungen für Identität, ISIN, Kurse, Volumen, Kapitalmaßnahmen und indikative Währungsumrechnung gelten unverändert; Gruppe B fügt nur den Umsatzfilter hinzu.

**Normalisierung und Score.** Rendite und R² werden je Gruppe und Zeitraum in Perzentile 0–100 umgerechnet (Abschnitt 7: `P = 100 · (Durchschnittsrang − 1) / (M − 1)`), **innerhalb der Vergleichsmenge der Gruppe**. Roh-Renditeprozente werden nie mit R² vermischt. Score = `w/100 · G + (1 − w/100) · R` mit den Gewichten als Anteile zwischen 0 und 1. Für 0/100 (nur Rendite) und 100/0 (nur Gleichmäßigkeit) ergibt das in Gruppe B dieselbe Reihenfolge wie Gruppe A ohne die übrigen Aktien; gemischte Gewichtungen können abweichen, weil die Perzentile sich auf eine kleinere Menge beziehen. Scores der Gruppe B sind deshalb nicht mit Scores der Gruppe A vergleichbar. Gleichstandsregeln wie in Abschnitt 7, zuletzt nach ISIN.

**Gleichmäßig steigend.** In U (bzw. U ∩ L) sind nur Aktien mit positiver Rendite, positiver Steigung und mindestens 15 echten Tageskursen; ein gleichmäßiger Abwärtstrend erhält deshalb keinen Wert für „gleichmäßig steigend“. Bei kurzen Zeiträumen (weniger als 15 Tageskurse, also etwa unter drei Wochen) ist die Gleichmäßigkeit nicht berechenbar: Ranglisten mit Gleichmäßigkeitsanteil bleiben leer mit Grund „nicht berechenbar“, die reine Renditeliste erscheint trotzdem. Es werden keine Scores zum Füllen erzeugt.

**Umfang.** Je Gruppe 90 Zeiträume × 11 Gewichtungen, also höchstens 2 × 90 × 11 = 1.980 Ranglisten je Kursstichtag (der Vergleich vom 13.10.2026 für 1–30 Tage: 660). Nicht berechenbare Kombinationen bleiben mit Grund sichtbar, zählen aber nicht als ausgeführte Rangliste. Die separate Ansicht „Höchste Kursrendite“ ist dieselbe Berechnung wie 0/100 und wird nirgends doppelt gezählt.

**Matrix.** Zeile = Zeitraum, Spalte = Gewichtung, Zelle = erstplatzierte Aktie mit vollständigem Namen, ISIN, Score und tatsächlicher Kursrendite (Gleichstand an der Spitze wird gekennzeichnet). Wiederkehrende Aktien: Grundlage sind die Platz-1-Zellen beider Gruppen im gewählten Bereich; jede ISIN mit mindestens zwei solchen Zellen trägt in beiden Gruppen und allen drei Ansichten (Matrix, Liste, Häufigkeit) dieselbe Kennzeichnung – das Zeichen „↻ 7“ (ausführlich „↻ 7 erste Plätze“) und, für die acht häufigsten (bei Gleichstand nach ISIN), eine feste Farbe. Identität ausschließlich über die ISIN; gleiche Namen oder ähnliche Ticker werden nie zusammengefasst, Aktiengattungen und ADRs haben eigene ISINs.

**Sieger nach Zeitraum (ab 1.5).** Für die zehn festen Zeiträume 7, 14, 21, 30, 40, 50, 60, 70, 80 und 90 Kalendertage stehen die Spitzenreiter der Gruppe A und B nebeneinander, für eine wählbare Gewichtung. Bei 0/100 ist das der tatsächliche Renditesieger; bei anderen Gewichtungen der Sieger nach Rangscore mit seiner tatsächlichen Kursrendite in genau diesem Fenster (er muss nicht die höchste reine Rendite haben). Jede Zelle ist Platz 1 derselben vollständigen Rangliste, die auch Matrix und Einzelrangliste zeigen; es wird nichts aus kürzeren Fenstern hochgerechnet und kein längeres Fenster eingesetzt. Ohne 15 Schlusskurse (bei 7 und 14 Tagen) steht „Gleichmäßigkeit nicht berechenbar“, der 0/100-Sieger bleibt abrufbar. Wiederholungen derselben ISIN über diese zehn Zeilen werden in einer eigenen, so benannten Zählung ausgewiesen – getrennt von der Häufigkeit über alle 90 Zeiträume.

**Identische Kursfenster (`frequency-v2`, ab 1.7.0).** Durch Wochenenden und Feiertage können verschiedene Kalenderzeiträume dieselben tatsächlichen Kurse verwenden (an einem Montag als Stichtag beginnen 1, 2 und 3 Tage am Freitag). Zwei Zeiträume gelten innerhalb derselben Gruppe und Gewichtung als identisch, wenn ihr **vollständiger Bestand aus ISIN und tatsächlichem Startdatum** übereinstimmt (das Ende ist immer der Stichtag) – dann sind auch die Ranglisten identisch. Ein Gleichstand nur beim Gewinner reicht nicht. Der Server veröffentlicht dazu je Vergleichsmenge (V, U, V ∩ L, U ∩ L) und Zeitraum den kleinsten Zeitraum mit demselben Bestand (`same_set`). Zellen identischer Fenster tragen „≡“. Bis 1.6.0 wurde stattdessen die Startsitzung je Börsenkalender verglichen.

**Häufigkeitsranking je Gruppe.** Über alle gewählten Zeiträume und Gewichtungen:

| Spalte | Bedeutung |
|---|---|
| Platz 1 | Zahl der Ranglisten, in denen die Aktie Platz 1 erreicht (primäres Kriterium, absteigend) |
| Top 3, Top 10 | Zahl der Ranglisten mit Platz ≤ 3 bzw. ≤ 10 (Gleichstandsregel 1 und 2) |
| Auswertbare Kombinationen | Zahl der Ranglisten der Auswahl, in denen die Aktie einen Rang hat |

Sortierung „gewinnt am häufigsten“ (Standard): Platz 1 absteigend, dann Top 3, Top 10, ISIN aufsteigend. Umschalter „Meiste Top-10-Nennungen“ („erscheint am häufigsten in den Top 10“): Top 10, dann Top 3, Platz 1, ISIN. Je Rangliste zählt eine Aktie höchstens einmal je Kennzahl; Platz 1 zählt zugleich zu Top 3 und Top 10, die drei Spalten werden nie addiert. Zusätzlich je Aktie: **zugelassene Kombinationen** (Ranglisten der Auswahl, in denen die Aktie überhaupt einen Rang hat) und je Auswahl der Nenner **berechenbare Kombinationen** (Ranglisten mit mindestens einer Aktie).

Filter: Gruppe A, Gruppe B oder beide zusammen (sortiert nach der Summe; die Treffer aus A und B stehen getrennt daneben – B ist eine Teilmenge von A, keine unabhängige Bestätigung); alle elf Gewichtungen, nur Gewichtungen mit Gleichmäßigkeitsanteil (10/90 … 100/0) oder eine einzelne; alle Zeiträume oder eine zusammenhängende Spanne (z. B. 1–30, 31–60, 61–90 oder frei gewählt). Normalerweise zählt jede angeforderte Kombination aus Zeitraum und Gewichtung. Mit „Identische Kursfenster nur einmal zählen“ werden Kombinationen derselben Gruppe und Gewichtung mit identischem ISIN-/Startdatumsbestand zusammengefasst (siehe oben); gleiche Ergebnisse verschiedener Gewichtungen bleiben verschiedene Gewichtungsergebnisse. Überlappende Zeiträume und ähnliche Gewichtungen bleiben trotzdem voneinander abhängig.

Häufige Nennung bedeutet Übereinstimmung dieser rückblickenden Vergleiche – keine unabhängigen Kaufsignale und keine Gewinnwahrscheinlichkeit.

Eine Veröffentlichungsprüfung (`gruppe_b_eigene_vergleichsmenge`) bestätigt für jeden Stand: Vergleichsmengen genau V ∩ L und U ∩ L, alle elf Gewichtungen, 0/100 nativ = Ranking 2, 0/100 und 100/0 in der Reihenfolge der Gruppe A, eindeutige Plätze, Sortierregeln, Scores zwischen 0 und 100. Die App rechnet Scores der Gruppe B bitgleich zum Server nach (Datenvertragstest).

## 14. Methodenwechsel 1.6.0 → 1.7.0 und Ausgangsmodell

Der Auftrag vom 13.10.2026 beschreibt das Ausgangsmodell **TR-90D-11W-two-universes-v1.1** und verlangt, dessen dokumentierte Formeln zu übernehmen und nichts stillschweigend zu ändern. Gegenüber tr-methode-1.6.0 übernimmt 1.7.0:

| Regel des Ausgangsmodells | bis 1.6.0 | ab 1.7.0 |
|---|---|---|
| Tagesvolumen an jeder Beobachtung vorhanden, endlich, nicht negativ | fehlendes Volumen zählte nur gegen die 80-%-Regel | sonst Status 14 |
| Start- und Endbeobachtung mit positivem Volumen | nur bei Kursbewegung über 10 % ohne Umsatz zurückgehalten (bleibt zusätzlich) | sonst Status 14 |
| Gemeldeter Split im Fenster zurückgestellt | nur bei möglicherweise unbereinigter Reihe zurückgehalten | immer Status 13; Freigabe nur mit dokumentierter Prüfung (`config/pruefungen.yaml`) |
| Sortierung: Score, Rendite, ISIN | zusätzlich R² bzw. Steigung/Rauschen | Abschnitt 7 |
| Zahl positiver Schlusskursvergleiche | nicht berechnet | Kennzahl je Fenster |
| Identische Fenster: gleiche ISIN-/Startdatumsbestände je Gruppe und Gewichtung | gleiche Startsitzung je Börsenkalender | Abschnitt 13 |

Unverändert und mit dem Auftrag übereinstimmend: Kalendertage 1–90, B = T − h, S höchstens 7 Tage vor B, nur abgeschlossene Sitzungen, kein Auffüllen, Rendite `100 × (P_T / P_S − 1)`, Preis-OLS ab 15 Schlusskursen mit R², relativer Steigung und Residualrauschen, Aufwärtstrend nur bei m > 0 und R > 0, größter Rückgang, Perzentile mit Durchschnittsrängen (N = 1 → 100 mit Hinweis), Score-Formel, Vergleichsmengen V und U, Gruppe B mit 20 Sitzungen, 80 % positiven Volumens, Split-Ausschluss im Umsatzfenster und EZB-Kursen mit Altersgrenze.

**Vergleich in jedem Lauf.** Der Rechenkern bestimmt zusätzlich die Status nach den Regeln der Vorversion und rechnet damit alle 1.980 Spitzenplätze nach. Das Manifest (`method_comparison`) und die App (☰ → Datenstand & Betrieb) nennen: Aktie-Zeitraum-Paare mit Rendite vorher/jetzt, nicht mehr und neu bewertete Paare mit Grund, Aktien mit mindestens einem Renditezeitraum vorher/jetzt und die Zahl der Ranglisten mit anderem Spitzenreiter samt Beispielen. Stände mit Methode 1.7.0 vergleichen mit 1.6.0, ab 1.8.0 mit 1.7.0 (Abschnitt 15).

**Bekannte Abweichungen zum Ausgangsmodell** (soweit aus dem Auftrag erkennbar; der Code des Ausgangsmodells lag nicht vor):

- Zusätzlich zum Ausgangsmodell begrenzt diese App fehlende Börsentage zwischen S und D: bis 1.7.0 auf 2 %, ab 1.8.0 auf 20 %, wobei ein einzelner fehlender Tag immer erlaubt ist (Status 12, Abschnitt 15). Das schützt R² und Steigung vor Fenstern mit großen Datenlücken; ob das Ausgangsmodell eine solche Grenze hat, lässt sich erst mit dessen Archiv prüfen.
- Der Ø Tagesumsatz ist der Mittelwert über die Sitzungen mit Daten unter den letzten 20 (mindestens 16 mit positivem Volumen); fehlende Sitzungen werden nicht als null gezählt.
- **Reproduktion des historischen Prüffalls (Stichtag 12.10.2026) nicht durchgeführt:** Das Archiv `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` lag nicht vor. Mit dem Archiv wird der unveränderte Datensatz eingelesen und jede Abweichung einzeln erklärt (09_Bekannte_Luecken).

## 15. Methodenwechsel 1.7.0 → 1.8.0: fehlende Börsentage beim Kursanbieter

Anlass: Yahoo lieferte für Montag, 12.10.2026, an allen geprüften Börsen in Europa und Asien Tageskerzen ohne Schlusskurs; die US-Werte waren vollständig. Nach der 98-%-Regel (Programmierauftrag v1.2) hätte dieser eine Tag europäische und asiatische Aktien bis etwa Weihnachten aus allen Zeiträumen von 2 bis 68 Tagen entfernt (68 Tage enthalten rund 49 Börsentage – erst ab 50 erwarteten Sitzungen sind 49 vorhandene 98 %). Am 13.10.2026 hast du dich für die Lösung „wie Ausgangsmodell“ entschieden.

| Regel | bis 1.7.0 | ab 1.8.0 |
|---|---|---|
| Fehlende Börsentage zwischen S und D (Börse offen, Kursanbieter ohne gültigen Kurs) | höchstens 2 % (49/50) | höchstens 20 % (4/5); eine einzelne fehlende Sitzung ist immer erlaubt |
| Auffüllen fehlender Tage | nie | nie – Rendite aus den echten Kursen an S und D, OLS nur über vorhandene Kurse |
| Startkurs an S und Endkurs an D | Pflicht (Status 11 bzw. 8) | unverändert Pflicht: fehlt der Kurs genau an S, gibt es für diesen Zeitraum keine Rendite und kein Ausweichen auf ältere Kurse |
| Positives Volumen | 80 % der Kurstage | unverändert 80 % der Kurstage (`volumen_bezug: beobachtungen`); wahlweise auf die erwarteten Sitzungen beziehbar |

Beispiel mit Stichtag Dienstag, 13.10.2026, und fehlendem 12.10.: Für 1 Tag ist S = 12.10. ohne Kurs → keine Rendite. Für 2 Tage ist S = Freitag, 9.10.: drei erwartete Sitzungen, zwei Kurse – nach 1.7.0 ausgeschlossen, ab 1.8.0 bewertet (Rendite 9.10. → 13.10.). Für 30 Tage: 22 erwartete Sitzungen, 21 Kurse – nach 1.7.0 ausgeschlossen (95 %), ab 1.8.0 bewertet. Größere Lücken bleiben ausgeschlossen, zum Beispiel sieben fehlende Börsentage in einem 30-Tage-Zeitraum.

Der Vergleich in jedem Lauf zählt die neu bewerteten Paare nach ihrem früheren Status (meist 12) und die weggefallenen nach ihrem neuen Status. Getestet in `tests/unit/test_quality.py` (`test_1_8_…`, `test_T29_…`) und im Datenvertragstest.

Zur selben Methodenversion gehört der geänderte Abgleich mit einem zweiten Börsenplatz (`boersenplatz-v2`, dann `boersenplatz-v3`, Abschnitt 8): Eine Lieferlücke des Kursanbieters am zweiten Platz führt zu „Vergleichskurse fehlen“ statt zu einem Vergleich mit dem Kurs eines anderen Tages; verglichen werden nur Kurse mit Umsatz, und die Schwelle wächst mit der üblichen Tagesschwankung der Aktie. Der Abgleich ist nur ein Hinweis und ändert weder Rendite noch Rang; er ist deshalb nicht Teil der Zählung oben. Getestet in `tests/unit/test_venues.py` (`test_provider_gap_on_a_session_day_…`, `test_holiday_at_the_second_venue_…`, `test_gap_at_a_start_session_…`, `test_closes_on_days_without_a_session_…`, `test_robust_noise_…`, `test_limits_grow_with_noise_…`, `test_volatile_stock_within_its_usual_swing_…`, `test_closes_without_turnover_…`, `test_diagnostics_…`).

## 16. Signale und Potenzial (ab Software 1.6, `signale-v1`; Gesamtwertung ab 1.7, `signale-v2`)

Die Ranglisten 1–90 Tage beschreiben die Vergangenheit. Die **Signale** fassen zusätzlich zusammen, was heute öffentlich über eine Aktie bekannt ist – Kursverlauf und Umsatz der letzten Wochen, Kursziele und Empfehlungen der Analysten, Bewertung, Wachstum, Nachrichten, Stimmung der Community. Sie sind **keine Prognose der App und keine Kaufempfehlung**, sondern eine geordnete, nachrechenbare Zusammenfassung nach festen Regeln. Der Code steht in `backend/traktien/analytics/signals.py`.

### 16.1 Grundsatz

* Jedes Signal hat **0 bis 100 Punkte**; 50 ist neutral, ab 60 gilt es als positiv, bis 40 als negativ.
* Jedes Signal trägt einen **Satz in Worten** („Umsatz 2,1× des 20-Tage-Durchschnitts“).
* **Fehlen Daten, entfällt das Signal** – es wird nichts geschätzt oder aufgefüllt. Die übrigen Signale eines Horizonts werden dann mit ihren Gewichten neu gewichtet.

### 16.2 Kurzfristig (Tage bis wenige Wochen)

Aus den eigenen Tageskursen (gleiche Kurse wie in den Ranglisten) – deshalb auch rückwirkend berechenbar:

| Signal | Gewicht | Regel |
|---|---|---|
| Relatives Volumen | 20 % | Umsatz (Stück) der letzten Sitzung ÷ Ø der 20 Sitzungen davor; Punkte = 50 + 25 · log₂(Verhältnis): 1× = 50, 2× = 75, 4× = 100. Unbekannter Umsatz = kein Signal |
| Schwung | 25 % | z = ln(Kurs heute ÷ Kurs vor 20 Sitzungen) ÷ (σ · √20), σ = Standardabweichung der täglichen Log-Renditen der letzten 60 Sitzungen; Punkte = 50 + 20 · z |
| Steigetage | 15 % | 60 % Anteil Steigetage der letzten 10 Sitzungen + 40 % Serie (50 + 12,5 je Tag in Folge, Falltage negativ) |
| Trendlage | 20 % | je ein Drittel: Kurs über 20-Tage-Linie, Kurs über 50-Tage-Linie, 20- über 50-Tage-Linie |
| Ausbruch | 10 % | neues 20-Tage-Hoch = 100; darunter 75 · (Verhältnis − 0,85) ÷ 0,12 (3 % darunter ≈ 75, 15 % darunter = 0) |
| RSI (14) | 10 % | nach Wilder; 55–70 = 90–100 Punkte (kräftig, nicht überhitzt), über 70 fallend (80 = 50), unter 40 wenige Punkte |

Der **technische Wert** ist der gewichtete Mittelwert dieser sechs (mindestens vier müssen berechenbar sein). Nachrichten und Community gehen mit 15 % ins kurzfristige Urteil ein, wenn vorhanden:

* **Nachrichten:** Tendenz der Schlagzeilen der letzten 3 Tage nach offengelegten Wortlisten (Englisch und Deutsch, z. B. „upgrade“, „Rekord“ positiv; „Gewinnwarnung“, „lawsuit“ negativ) und – bei US-Aktien – Hoch-/Herabstufungen und Kursziel-Änderungen der letzten 30 Tage.
* **Community:** Anteil der als „bullish“ markierten unter allen markierten der letzten 30 Stocktwits-Beiträge, bei wenigen Beiträgen zur Mitte gezogen (Gewicht n ÷ (n + 5)).

**Ampel kurzfristig:** grün ab 65 Punkten, wenn der Kurs über 20- und 50-Tage-Linie liegt (Trendlage ≥ 66) und in 20 Sitzungen gestiegen ist; rot unter 40 Punkten oder bei fallendem Kurs unter den Durchschnittslinien; grau bei zu kurzer Historie oder unter **250.000 € Ø Tagesumsatz** (kurzfristig kaum handelbar); sonst gelb.

### 16.3 Langfristig (etwa 12 Monate)

| Signal | Gewicht | Regel |
|---|---|---|
| Kursziel | 35 % | erwartete Steigerung u = Ø Kursziel ÷ Schlusskurs − 1; Rohwert = 60 % · (50 + 100 · u) + 40 % · Empfehlung ((5 − Ø Empfehlung) ÷ 4 · 100, 1 = stark kaufen); zur Mitte gezogen mit n ÷ (n + 3) bei n Analysten (1 Analyst: ein Viertel, 3: die Hälfte, 10: drei Viertel) |
| Bewertung | 20 % | Trading Central (nur US; doppelt gewichtet): 50 + 150 · Abschlag zum fairen Wert; erwartetes KGV im Vergleich zur eigenen Branche (100 − Perzentil); PEG < 1 = 75, 1–2 = 50, > 2 = 25 |
| Wachstum & Finanzen | 20 % | Perzentile über alle Aktien mit Angaben: erwartetes Gewinn- und Umsatzwachstum nächstes Jahr, Eigenkapitalrendite, Nettomarge (höher besser), Verschuldung (niedriger besser); freier Cashflow positiv = 70, negativ = 30 |
| Langfristiger Trend | 15 % | Perzentil der 1-Jahres-Rendite, Lage zur 200-Tage-Linie (75/25), Abstand zum Jahreshoch |
| Richtung der Analysten | 10 % | Anteil „Kaufen“ heute gegenüber vor 3 Monaten; bei US-Aktien angehobene gegenüber gesenkten Kurszielen (90 Tage) |

**Kursziel-Quellen:** Yahoo Finance (Konsens aller erfassten Analysten, weltweit), bei US-Aktien zusätzlich Nasdaq (Konsens) und der Durchschnitt der jeweils letzten Einzelziele der Analystenhäuser der letzten 90 Tage (mindestens zwei Häuser). Das **Ø Kursziel der App ist der Mittelwert dieser Quellen**. Die Einheit wird geprüft (z. B. Pence gegenüber Pfund): Passt der Kurs der Quelle nicht innerhalb Faktor 1,6 zum eigenen Schlusskurs – auch nicht nach × 100 oder ÷ 100 –, entfällt das Kursziel.

**Ampel langfristig:** grün ab 62 Punkten, wenn die erwartete Steigerung mindestens +10 % beträgt, mindestens 3 Analysten ein Kursziel nennen und mindestens die Hälfte „Kaufen“ empfiehlt; ohne Kursziel oder mit weniger als 3 Analysten höchstens gelb; rot, wenn das Kursziel unter dem Kurs liegt oder unter 40 Punkten; grau bei weniger als zwei langfristigen Signalen.

### 16.3a Gesamtwertung (ab Software 1.7, `signale-v2`)

Deine Vorgaben vom 14.10.2026: Eine Aktie, die über 30, 60 und 90 Tage immer wieder steigt, ist lukrativer als eine mit nur einem kurzen Schub; kommt ein deutlich positives Kursziel hinzu (z. B. +100 %), wird sie bevorzugt – ausgewertet für **alle** Aktien der Trade-Republic-Liste, damit die Kandidaten ohne Suchen oben stehen.

**Gesamtwertung = 35 % Steig-Konstanz + 35 % Kursziel-Potenzial + 15 % Aufmerksamkeit & Schwung + 15 % Qualität** (0–100; ab 65 *stark*, ab 50 *mittel*, darunter *schwach*).

| Teil | Gewicht | Regel |
|---|---|---|
| Steig-Konstanz | 35 % | Für 30, 60 und 90 **Kalendertage**: Start ist – wie bei den Ranglisten – die letzte Sitzung am oder vor „heute − Zeitraum“ (höchstens 7 Tage davor). Gezählt werden alle Handelstage danach, an denen der Schlusskurs **höher als am Vortag** war (z. B. 15 von 21). Punkte je Zeitraum = (Anteil − 40 %) ÷ 25 % · 100, begrenzt auf 0–100 (40 % = 0, 52,5 % = 50, 65 % = 100). Liegt der Kurs am Ende eines Zeitraums **nicht über** dem Anfangskurs, zählt dieser Zeitraum höchstens 25 Punkte. Steig-Konstanz = Mittel der Zeiträume; 30 und 60 Tage müssen vorhanden sein (90 entfällt bei kürzerer Historie) |
| Kursziel-Potenzial | 35 % | u = Ø Kursziel aller Quellen ÷ Schlusskurs − 1. Punkte = 100 · (1 − e^(−u ÷ 0,35)): +10 % = 25, +25 % = 51, +50 % = 76, +100 % = 94, +150 % = 99 – höhere Kursziele zählen mehr, aber mit abnehmendem Zuwachs. Mit weniger als 5 Analysten anteilig (n ÷ 5: 1 Analyst = 20 %, 3 = 60 %). Ohne Kursziel oder mit Kursziel unter dem Kurs: 0 Punkte |
| Aufmerksamkeit & Schwung | 15 % | das kurzfristige Urteil (16.2) – Umsatz, Schwung, Steigetage, Trendlage, Ausbruch, RSI, Nachrichten, Community |
| Qualität | 15 % | aus dem langfristigen Urteil (16.3): Bewertung 40 %, Wachstum & Finanzen 40 %, Richtung der Analysten 20 % (fehlende Teile werden neu gewichtet); ohne jede Angabe neutral 50 |

Ohne mindestens 60 Tage Kurshistorie gibt es keine Gesamtwertung. Die Liste **Gesamt** (Startseite oben und Ansicht Potenzial) sortiert absteigend nach der Gesamtwertung, bei Gleichstand nach der erwarteten Steigerung. Jede Zeile zeigt die Steig-Konstanz als Streifen („30 T ▲15/21 · 60 T ▲31/42 · 90 T ▲45/63“; grün ab 60 % Anstiegstagen und gestiegenem Kurs, rot unter 50 % oder gefallenem Kurs), die Einzelansicht alle vier Teile mit Beitrag (Punkte × Gewicht) und eine Tabelle je Zeitraum.

**Trefferquote der Steig-Konstanz:** wie in 16.4, aber für die Steig-Konstanz und für **20 und 60 Sitzungen** danach, je Punktebereich 0–20, 20–40, 40–60, 60–80, 80–100. Kursziele, Nachrichten und Qualität lassen sich so nicht prüfen (keine Historie) – die Quote gilt nur für den Kursverlauf-Teil und steht so in der App.

Warum diese Gewichte: Steig-Konstanz und Kursziel sind die beiden Dinge, die du ausdrücklich bevorzugst; Aufmerksamkeit und Qualität ordnen innerhalb ähnlicher Kandidaten. Ein hoher Anteil Anstiegstage ist eine Beobachtung der Vergangenheit, Kursziele sind Einschätzungen Dritter und oft zu optimistisch – die Wertung ordnet, sie verspricht nichts.

### 16.4 Trefferquote der Vergangenheit

Für jede handelbare Aktie (Ø Umsatz ≥ 250.000 €) und **jeden vergangenen Tag** der gespeicherten Kurshistorie wird der technische Wert genauso berechnet wie heute – nur mit den Kursen bis zu diesem Tag. Gezählt wird, wie oft der Schlusskurs **5 und 20 Sitzungen später** höher stand, und die mittlere Veränderung (auf −90 % … +300 % begrenzt, damit Datenfehler den Mittelwert nicht kippen). Ausgewiesen je Punktebereich (0–30, 30–40, …, 80–100) und für alle Aktien zum Vergleich. Die Einzelansicht nennt den Bereich der Aktie, die Quote, die Zahl der Vergleichsfälle und den Vergleich mit allen Aktien.

Grenzen: Die Vergleichsfälle überlappen sich (aufeinanderfolgende Tage derselben Aktie) und stammen aus dem gespeicherten Zeitraum (gut ein Jahr) – die Quote beschreibt diese Marktphase, keine Zusage. Nachrichten, Community und Kursziele gehen nicht ein (ihre Vergangenheit ist erst ab dem 14.10.2026 gespeichert); für Kursziele wird eine eigene Trefferquote möglich, sobald einige Monate Kursziel-Historie vorliegen.

### 16.5 Prognose-Grafik

Links der tatsächliche Kursverlauf (bis ein Jahr), rechts 12 Monate voraus: der Punkt ist das Ø Kursziel, der Strich die Spanne vom tiefsten zum höchsten Kursziel. Das graue Band ist die **übliche Schwankung**: Kurs · e^(±σ · √252) mit derselben σ wie beim Schwung – bei gleichbleibender Schwankung landet der Kurs in etwa 2 von 3 Fällen in diesem Band; es zeigt die Streuung, keine Richtung.

### 16.6 Signal-Stand und Aktualisierung

Kennzahlen kommen aus **einem Abruf je Aktie** (Yahoo `quoteSummary`: Kursziele, Empfehlungen der letzten 4 Monate, Urteile der Häuser, Bewertung, Wachstum, Finanzen, Termine, Branche), rotierend: die vorderen Kandidaten täglich, Aktien mit Analysten alle 3 Tage, ohne Analysten alle 14 Tage, unbekannte Kürzel alle 30 Tage. Für die vorderen 150 Kandidaten zusätzlich: Bewertung (Trading Central, US), Nasdaq-Konsens (US), Nachrichten (täglich) und Community (US, höchstens 120 je Lauf). Daraus entsteht ein **Signal-Stand** (eigene verschlüsselte Dateien `data/signale/<id>/`), unabhängig vom Kurs-Datenstand – er wird nach jedem täglichen Lauf und auf Wunsch („Nur Kennzahlen, Kursziele und Signale aktualisieren“) neu geschrieben. Der Stand nennt seine Uhrzeit und den Kursstand, auf dem er beruht.

## 17. Zwischenstand (ab Software 1.8)

Dein Wunsch vom 14.10.2026: „Es muss nicht Livekurs sein. Aber kann man das nicht so einstellen, dass ich jederzeit die Kurse aktualisieren kann? Und dazu die Berechnungen jederzeit aktualisieren.“ Der **Zwischenstand** rechnet alle Ranglisten 1–90 Tage, beide Gruppen, Häufigkeit und Matrix mit den **aktuellen Kursen des laufenden Handelstags** – auf Knopfdruck (Workflow-Eingabe `zwischenstand`). Der Code steht in `backend/traktien/jobs/intraday.py`.

1. **Offizieller Stand zuerst:** Fehlt der offizielle Stand für den neuesten abgeschlossenen Börsentag (z. B. weil GitHub den Morgenlauf nicht gestartet hat), rechnet der Zwischenstand zuerst den normalen täglichen Lauf – sonst fehlten Schlusskurse zwischen offiziellem Stand und heute.
2. **Aktuelle Kurse:** Für alle Referenznotierungen, deren Börse seit dem offiziellen Stand schon gehandelt hat (Sitzungsbeginn laut Börsenkalender), holt der Lauf den zuletzt gemeldeten Kurs, Zeitpunkt, Handelstag und Tagesumsatz bis jetzt – in Sammelabfragen zu je 20 Werten (Yahoo `spark`). Die Kurse sind je nach Börse etwa 15–20 Minuten verzögert. Nach Börsenschluss ist der gemeldete Kurs der Schlusskurs dieser Sitzung (Abweichung zur Tageskerze im Test 0,0 Basispunkte), aber noch ungeprüft.
3. **Stichtag T des Zwischenstands:** der neueste Tag nach dem offiziellen Stand, an dem mindestens **20 %** der Aktien, deren Börse an T schon begonnen hat, einen Kurs mit Handelstag T haben (`zwischenstand.mindestanteil_aktien`) – und deren gespeicherte Historie lückenlos bis zur vorherigen Sitzung reicht.
4. **Vorläufige letzte Beobachtung:** Je Aktie mit Kurs an T wird dieser Kurs als letzte Beobachtung angehängt – **nur im Speicher**, nie in die gespeicherte Kurshistorie; ein vorläufiger Kurs ersetzt nie einen gespeicherten Schlusskurs. Die Kurseinheit muss zur gespeicherten passen (sonst entfällt der Kurs). Alle Prüfungen laufen wie im offiziellen Stand (Kurssprünge werden zurückgehalten, Umsatzregeln mit dem Umsatz bis jetzt).
5. **Aktien ohne Kurs an T zählen mit dem letzten Schlusskurs (ab 1.13, deine Wahl vom 14.10.: „Mit letztem Schlusskurs“):** Hat die Börse einer Aktie an T eine Sitzung, die Aktie aber keinen Kurs von T – die Börse hat noch nicht geöffnet (New York öffnet um 15:30 Uhr Berliner Zeit) oder es gab bis zum Abruf keinen Handel –, rechnet der Zwischenstand sie mit dem **Schlusskurs der Sitzung davor**: Für diese Aktie ist der Handelstag davor der Stichtag, alle ihre Fenster (1–90 Tage) enden dort. Ihre Werte sind damit Zahl für Zahl dieselben wie im Stand mit Schlusskursen dieses Tages. So steht jede Aktie in den Ranglisten, in Häufigkeit, Matrix, Top 3 und „Deine Aktien“; die App kennzeichnet sie in jeder Zeile mit „Schlusskurs 13.10.“ und nennt die noch geschlossenen Börsen im Hinweis („New York noch nicht geöffnet – mit Schlusskurs vom 13.10.“). Folge, die man beim Lesen kennen sollte: Ein Zeitraum „1 Tag“ bedeutet für diese Aktien den letzten abgeschlossenen Handelstag, für Aktien mit Kurs von heute die Bewegung seit gestern bis jetzt. Nach Börsenbeginn rechnet ein neuer Zwischenstand sie mit dem Kurs von heute. Unverändert: Ist die Börse an T geschlossen (Feiertag) oder fehlt auch der Schlusskurs davor, fehlt die Aktie wie im offiziellen Lauf („Markt am Stichtag geschlossen“ bzw. „Kurs am Stichtag fehlt“). Es wird nichts fortgeschrieben oder aufgefüllt. Im Status steht, wie viele Aktien so zählen (`aktien_mit_schlusskurs`) und welche Börsen beim Abruf noch nicht geöffnet hatten (`boersen_mit_schlusskurs`). Bis 1.12 fehlten diese Aktien im Zwischenstand.
6. **Ø Tagesumsatz (Gruppe B)** zählt den laufenden Tag nicht mit (er wäre erst ein Teil des Tages): Betrachtet werden die 20 Sitzungen bis zur vorherigen.
7. **Nicht im Zwischenstand:** Abgleich mit einem zweiten Börsenplatz, Umschichtungs-Regel (Wochenschlusskurse) und der Prüfnachweis-Archiv; Kennzahlen und Signale bleiben auf dem Stand des letzten Signal-Stands.

Es gibt **immer höchstens einen Zwischenstand**; ein neuer ersetzt den alten (auch im Release „datenstand“). Die App öffnet ihn als neuesten Stand und kennzeichnet ihn überall: „Zwischenstand 13.10. 12:15“ in der Kopfzeile, Hinweisleiste mit dem Knopf „Schlusskurse 13.10.“ (ab 1.13; nennt den Tag der letzten Schlusskurse), Börsen ohne Kurs von heute im Kopf der Startseite, „Schlusskurs 13.10.“ in jeder Zeile einer Aktie, die mit dem Schlusskurs davor zählt, „Kurs … heute 12:15 Uhr (vorläufig)“ in der Einzelansicht, „Letzter Punkt: vorläufiger Kurs“ unter den Charts. Sobald ein offizieller Stand mit gleichem oder späterem Stichtag veröffentlicht ist, verschwindet der Zwischenstand aus der App. Zwischenstände zählen nicht als Versuch des täglichen Laufs.

## 18. Musterdepots (ab Software 1.9)

Dein Auftrag vom 14.10.2026 („Implementieren“ zur Datei „Zwei Zehnerdepots · 1–30 Tage · Beiträge“). Gerechnet wird in der App (`app/src/lib/depots.ts`) aus Dateien des aktiven Datenstands: Häufigkeit (`frequency.bin`), Kursreihen (`series/<ISIN>.bin`) und Euro-Referenzkurse (`fx.bin`).

1. **Häufigkeitslisten:** Gezählt wie unter „Häufigste Aktien“ – je Rangliste höchstens einmal je Aktie, Platz 1 zählt zugleich zu Top 3 und Top 10. *Häufigste erste Plätze*: sortiert nach ersten Plätzen, dann Top 3, Top 10, ISIN (nur Aktien mit mindestens einem ersten Platz). *Häufigste Top-10-Nennungen*: sortiert nach Top-10-Nennungen, dann erste Plätze, Top 3, ISIN. Listenlänge 20 (ab 1.10, wie Datei v3) oder 10. **Standardauswahl (ab 1.10, dein Wunsch vom 14.10.): 1–30 Kalendertage, Gewichtungen 40/60, 50/50 und 60/40, Gruppe A und B** (3 × 30 × 2 = 180 mögliche Ranglisten, gültig nur ab 15 echten Schlusskursen). Optionen: alle elf Gewichtungen 0/100 bis 100/0 (660 mögliche, Datei v3), die vier des Berichts (0/100, 40/60, 50/50, 60/40; 240 mögliche), jede einzelne Gewichtung, Zeitraum 1–90 Tage.
2. **Zusammensetzung:** „10 Sieger“ = zehn häufigste erste Plätze, „10 Top-10“ = zehn häufigste Top-10-Nennungen – immer aus der Standardauswahl (ab 1.10; bis 1.9.2 aus der Auswahl „Bericht 1–30“), also jeden Tag neu aus den aktuellen Ranglisten; eine andere Auswahl der Anzeige ändert sie nicht. Eigene Depots sind feste ISIN-Listen (1–20 Aktien, höchstens 8 Depots), gespeichert nur auf dem Gerät; voreingestellt sind das Dreierdepot (US74624M1027, US50015M1099, US70465T1079) und das Viererdepot (US74624M1027, US5352191093, CA82509L1076, US70465T1079) aus deiner Datei.
3. **Fenster:** Für h = 1 … 30 Kalendertage endet jedes Fenster am Kursstichtag (im Zwischenstand mit dem vorläufigen Kurs). Start je Aktie ist der letzte echte Schlusskurs am oder vor dem Kalendertag „Stichtag − h“, höchstens 7 Kalendertage davor – dieselbe Regel wie in den Ranglisten. Ende ist der letzte Schlusskurs am oder vor dem Stichtag (höchstens 7 Tage alt). Fehlt Start- oder Endkurs, bleibt die Aktie in diesem Fenster draußen; die Gewichte verteilen sich gleich auf die übrigen. Nichts wird aufgefüllt.
4. **Rendite einer Aktie** in der gewählten Basis: r = (Endkurs × W_Ende) / (Startkurs × W_Start) − 1. W ist in USD-Basis „USD je Einheit“ = (USD je EUR) / (Einheiten je EUR), in EUR-Basis „EUR je Einheit“ = 1 / (Einheiten je EUR), jeweils der EZB-Referenzkurs des Kurstags oder der letzte davor (höchstens 5 Tage alt); fehlt er, bleibt die Aktie mit Grund draußen. In Originalwährung zählt nur die Kursänderung. Kurse sind splitbereinigte Schlusskurse; Untereinheiten (Pence) ändern die Rendite nicht.
5. **Depot:** gleiche Startbeträge (Startgewicht 1/n), danach unveränderte Stückzahlen. Beitrag einer Aktie = Startgewicht × r (in Prozentpunkten); Depotrendite R = Summe der Beiträge. Endgewicht = Startgewicht × (1 + r) / (1 + R); Endwert der Position = Startkapital × Startgewicht × (1 + r).
6. **Hinweise (†):** Start- oder Endkurs ohne gemeldeten Umsatz, Ø Tagesumsatz unter der Grenze „sehr niedrig“ (1 Mio. USD), vorläufiger Endkurs im Zwischenstand. Die Rechnung belegt keine damalige Ausführbarkeit.
7. **Erklärblöcke (ab 1.10, wie Datei v3):** *Sieger je Gewichtung* – je Gewichtung die Aktie mit den meisten ersten Plätzen über 1–30 Tage (A und B) mit „Siege / gültige Ranglisten“; *Rechenbeispiel* – 30 Kalendertage, Gruppe B: je Gewichtung der Sieger mit Score (zwei Nachkommastellen), Kursrendite und R², Score = G/100 × Rangwert(R²) + (100 − G)/100 × Rangwert(Rendite), Rangwert = 100 × (mittlerer Rang − 1)/(Anzahl − 1); *Standard → alle elf* – die Top 20 der Top-10-Nennungen mit allen elf Gewichtungen, daneben Rang und Nennungen in der Standardauswahl.
8. **Grenzen:** rückblickende Auswahl (die Aktien sind mit Kenntnis der späteren Gewinner gewählt – Rückschaufehler), keine Kosten, Spreads, Steuern, Dividenden; Schlusskurse verschiedener Börsen und Wechselkurse sind nicht gleichzeitig ausführbar. Die Zahlen können von der ChatGPT-Datei abweichen, weil die App alle geladenen Kursreihen des Datenstands auswertet (die Datei: 6.000 Aktien) und ihre eigenen Kursreihen und EZB-Kurse verwendet.

## 19. Top nach Zahlen (ab Software 1.11)

Dein Wunsch vom 14.10.2026: „nach berechenbaren Fakten ausrechnen … nach Berechnungen handeln, emotionslos“ – Aktien, die in vielen Ranglisten vorne stehen, deren Kurs steigt, bei denen die Analysten positiv sind und das Volumen steigt; Börsenwert berücksichtigen. Die App rechnet dafür jeden Tag dieselbe feste Regel über alle Aktien (auf dem Gerät, aus dem Datenstand und dem Signal-Stand):

| Teil | Punkte | Rechnung |
|---|---|---|
| Oft vorne | bis 40 | 40 × (Top-10-Nennungen ÷ gültige Standard-Ranglisten). Standard-Ranglisten: 40/60, 50/50, 60/40 über 1–30 Tage in Gruppe A und B; gültig ab 15 Schlusskursen im Zeitraum (in der Regel 11 Zeiträume × 3 Gewichtungen × 2 Gruppen = 66) |
| Steigt stetig | bis 25 | 25 × Steig-Konstanz ÷ 100 (Teil der Gesamtwertung, §16.3a: Anstiegstage über 30, 60 und 90 Tage) |
| Analysten | bis 20 | 20 × Kursziel-Punkte ÷ 100 (Teil der Gesamtwertung: Abstand zum Ø Kursziel, voll erst ab 5 Analysten) |
| Volumen | bis 15 | 15 × (Volumen der letzten Sitzung ÷ Ø der 20 Sitzungen davor − 1), höchstens 15 (ab doppelt so hoch); 0, wenn der Kurs in den letzten 5 Sitzungen nicht gestiegen ist |
| Börsenwert | Abzug | unter 300 Mio. € −10, unter 50 Mio. € −20 (Yahoo „marketCap“ mit EZB-Kurs in EUR) |

Jeder Teil wird auf eine Nachkommastelle gerundet, die Summe auf ganze Punkte (0 bis 100). Gewertet werden nur Aktien mit mindestens einer Top-10-Nennung; fehlende Angaben zählen 0 Punkte, nichts wird geschätzt. Gleichstand: mehr Top-10-Nennungen, dann mehr erste Plätze, dann höhere Gesamtwertung, dann ISIN.

Angezeigt werden außerdem **Warnzeichen** (gehen nicht in die Punkte ein): Börsenwert unter 300 bzw. 50 Mio. €, Kurs in 20 Sitzungen mehr als verdoppelt, weniger als 3 Analysten, RSI ab 75 (überkauft), unter 1 Mio. € Umsatz am Tag, keine Signal-Daten. Und die **Trefferquote** der Steig-Konstanz (§16.4): wie oft Aktien mit ähnlicher Steig-Konstanz früher 20 bzw. 60 Handelstage später höher standen, im Vergleich zu allen Aktien.

**Grenzen:** Die Regel ordnet nach vergangenen Kursen und Angaben Dritter. Sie sagt nicht voraus, wie sich ein Kurs entwickelt; starke Anstiege der letzten Wochen können sich umkehren. Keine Anlageberatung, keine Kaufempfehlung.
