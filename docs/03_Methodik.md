# Methodik (Methodenversion tr-methode-1.4.0)

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

- Keine Dividenden, keine Gebühren und Steuern, keine Euro-Umrechnung: Kursrendite in Notierungswährung. Die USD-Umrechnung gilt nur für den Umsatzfilter.
- Abgleich mit einem zweiten Börsenplatz nur für die ersten Plätze der Rendite-Ranglisten; alle übrigen Aktien werden nur an ihrer Referenzbörse betrachtet (09_Bekannte_Luecken).
- Nur Tagesschlusskurse, kein Intraday.
- Die Schwellen (15 Tageskurse, 98 %, 80 %, Faktor 3, 10 % ohne Umsatz) sind transparente Startregeln, kein nachgewiesener Prognosevorteil. Jede Änderung ist eine neue Methodenversion.
