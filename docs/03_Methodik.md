# Methodik (Methodenversion tr-methode-1.6.0)

Diese Datei beschreibt verbindlich, wie jeder Wert der App entsteht. Gerechnet wird ausschließlich auf dem Server (Python, `backend/traktien/analytics`) in Gleitkommazahlen doppelter Genauigkeit ohne Zwischenrundung. Gerundet wird nur in der Anzeige. Die App rechnet Perzentile und Scores aus veröffentlichten ganzzahligen Rängen mit derselben Operationsfolge nach; die Gleichheit wird in jedem Prüflauf Bit für Bit getestet.

Die Ranglisten beschreiben die Vergangenheit. Sie sind keine Prognose, keine Empfehlung und kein validierter Handelsvorteil.

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
| 12 | Zu viele fehlende Sitzungen | weniger als 98 % der erwarteten Sitzungen zwischen S und D mit Kurs (geprüft als ganzzahliges Verhältnis 49/50, vor jeder Rundung) |
| 13 | Kapitalmaßnahme/Datenfehler prüfen | im Fenster ein Tagessprung p_t/p_(t−1) > 3 oder < 1/3, ein möglicherweise unbereinigter Split, oder an S bzw. D eine Kursbewegung über 10 % an einem Tag ohne belegten Umsatz |
| 14 | Zu wenig belegtes Handelsvolumen | weniger als 80 % der Beobachtungen mit positivem Umsatz (fehlendes Volumen zählt als unbekannt, nicht als 0 und nicht als positiv) |
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

### Reihenfolge und Gleichstände

| Gewichtung | Sortierung |
|---|---|
| 0/100 | Kursrendite absteigend, dann ISIN |
| 10/90 … 90/10 | Score absteigend, Kursrendite absteigend, R² absteigend, ISIN |
| 100/0 | R² absteigend, relative Steigung absteigend, Rauschen aufsteigend, ISIN |

Entschieden wird mit ungerundeten Werten. Exakt gleiche Primärwerte werden als „gleichauf“ gekennzeichnet; die ISIN legt nur die Reihenfolge der Anzeige fest.

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

### Abgleich mit einem zweiten Börsenplatz (ab 1.2, `boersenplatz-v1`)

Geprüft wird jede Aktie, die in mindestens einem Zeitraum unter den ersten 10 Plätzen von Ranking 1 oder Ranking 2 steht – dann für alle Zeiträume, in denen sie eine Kursrendite hat. Höchstens 600 Aktien je Lauf, beste Plätze zuerst.

1. **Zweiter Börsenplatz:** aus den Notierungen der Identitätsquelle (OpenFIGI) zur selben ISIN, ohne die Referenzbörse, ohne Notierungen mit demselben Anbietersymbol (z. B. NYSE und Nasdaq liefern bei Yahoo dieselbe US-Kursreihe) und ohne OTC-Märkte. Reihenfolge: Xetra, Frankfurt, dann die Standardreihenfolge. Die Wahl wird 45 Tage wiederverwendet.
2. **Kurse:** splitbereinigte Tagesschlusskurse dieses Platzes vom selben Kursanbieter. Für Start und Ende gilt der letzte Schlusskurs am oder vor dem tatsächlichen Start- bzw. Enddatum der Referenz, höchstens 4 Kalendertage früher; sonst „Vergleichskurse fehlen“ (kein Rückgriff auf ältere Kurse).
3. **Umrechnung:** in die Währung der Referenznotierung mit den EZB-Referenzkursen des jeweiligen Kurstags (über USD als Kreuzkurs); gleiche Währung ohne Umrechnung; Untereinheiten (Pence) in die Hauptwährung.

```
Abweichung Wertentwicklung = (1 + r_zweiter Platz) / (1 + r_Referenz) − 1
Abweichung Endkurs         = Endkurs_zweiter Platz (umgerechnet) / Endkurs_Referenz − 1
auffällig, wenn |ln(1 + Abweichung)| > ln(1,10)   (Wertentwicklung oder Endkurs)
```

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
- Die Schwellen (15 Tageskurse, 98 %, 80 %, Faktor 3, 10 % ohne Umsatz) sind transparente Startregeln, kein nachgewiesener Prognosevorteil. Jede Änderung ist eine neue Methodenversion.

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

**Umfang.** Je Gruppe 90 Zeiträume × 11 Gewichtungen (die App zeigt im Vergleich 1–30 Tage, also 2 × 30 × 11 = 660 Ranglisten, wahlweise 31–60 oder 61–90). Die separate Ansicht „Höchste Kursrendite“ ist dieselbe Berechnung wie 0/100 und wird nirgends doppelt gezählt.

**Matrix.** Zeile = Zeitraum, Spalte = Gewichtung, Zelle = erstplatzierte Aktie mit vollständigem Namen, ISIN, Score und tatsächlicher Kursrendite (Gleichstand an der Spitze wird gekennzeichnet). Wiederkehrende Aktien: Grundlage sind die Platz-1-Zellen beider Gruppen im gewählten Bereich; jede ISIN mit mindestens zwei solchen Zellen trägt in beiden Gruppen und allen drei Ansichten (Matrix, Liste, Häufigkeit) dieselbe Kennzeichnung – die Anzahl („×7“) und, für die acht häufigsten (bei Gleichstand nach ISIN), eine feste Farbe. Identität ausschließlich über die ISIN; gleiche Namen oder ähnliche Ticker werden nie zusammengefasst, Aktiengattungen und ADRs haben eigene ISINs.

**Identische Kursfenster.** Durch Wochenenden und Feiertage können verschiedene Kalenderzeiträume dieselbe Startsitzung haben (an einem Montag als Stichtag beginnen 1, 2 und 3 Tage am Freitag). Eine Zelle wird mit „≡“ gekennzeichnet, wenn ihre Spitzenaktie in derselben Spalte bei anderen Zeiträumen mit demselben tatsächlichen Start- und Endkurs vorne liegt.

**Häufigkeitsranking je Gruppe.** Über alle gewählten Zeiträume und Gewichtungen:

| Spalte | Bedeutung |
|---|---|
| Platz 1 | Zahl der Ranglisten, in denen die Aktie Platz 1 erreicht (primäres Kriterium, absteigend) |
| Top 3, Top 10 | Zahl der Ranglisten mit Platz ≤ 3 bzw. ≤ 10 (Gleichstandsregel 1 und 2) |
| Auswertbare Kombinationen | Zahl der Ranglisten der Auswahl, in denen die Aktie einen Rang hat |

Sortierung: Platz 1 absteigend, dann Top 3, Top 10, ISIN aufsteigend. Je Rangliste zählt eine Aktie höchstens einmal je Kennzahl; Platz 1 zählt zugleich zu Top 3 und Top 10, die drei Spalten werden nie addiert. Auswahl: alle elf Gewichtungen oder eine einzelne; Gruppe A, Gruppe B oder A und B nebeneinander (dann sortiert nach der Summe, Treffer getrennt ausgewiesen). Normalerweise zählt jede angeforderte Kombination aus Zeitraum und Gewichtung. Mit „Identische Kursfenster nur einmal zählen“ werden Kombinationen aus Gruppe, Gewichtung sowie tatsächlichem Start- und Enddatum (der jeweiligen Aktie, aus ihrem Börsenkalender) zusammengefasst; gleiche Ergebnisse verschiedener Gewichtungen bleiben verschiedene Gewichtungsergebnisse.

Häufige Nennung bedeutet Übereinstimmung dieser rückblickenden Vergleiche – keine unabhängigen Kaufsignale und keine Gewinnwahrscheinlichkeit.

Eine Veröffentlichungsprüfung (`gruppe_b_eigene_vergleichsmenge`) bestätigt für jeden Stand: Vergleichsmengen genau V ∩ L und U ∩ L, alle elf Gewichtungen, 0/100 nativ = Ranking 2, 0/100 und 100/0 in der Reihenfolge der Gruppe A, eindeutige Plätze, Sortierregeln, Scores zwischen 0 und 100. Die App rechnet Scores der Gruppe B bitgleich zum Server nach (Datenvertragstest).
