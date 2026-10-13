# Kurzanleitung für das Handy

Die App zeigt jeden Morgen neu berechnet, welche Aktien aus der Trade-Republic-Aktienliste in den letzten 1 bis 90 Kalendertagen gestiegen sind – nach reiner Kursrendite und nach „gleichmäßig steigend“. Gerechnet wird auf dem Server. Das Handy muss dafür weder eingeschaltet noch die App geöffnet sein.

## 1. Auf dem Galaxy S25+ installieren

**Chrome**
1. Die Adresse der App öffnen (steht nach der Einrichtung in GitHub unter *Settings → Pages*, Form `https://<name>.github.io/tr-aktienvergleich/`).
2. Oben rechts auf ⋮ tippen.
3. „App installieren“ wählen (bei manchen Versionen „Zum Startbildschirm hinzufügen“ und dann „Installieren“).
4. Bestätigen. Das gelbe Symbol „TR-Vergleich“ liegt danach auf dem Startbildschirm.

**Samsung Internet**
1. Adresse öffnen.
2. Unten rechts auf ≡ tippen.
3. „Seite hinzufügen zu“ → „Startbildschirm“ (oder das Installieren-Symbol in der Adressleiste).
4. „Hinzufügen“.

Die Menünamen können je nach Browserversion leicht abweichen. In der App selbst steht die Anleitung unter ☰ → „Auf dem Startbildschirm installieren“.

## 2. Erster Start: Zugangsschlüssel

Die Daten sind verschlüsselt veröffentlicht. Beim ersten Öffnen einmal die Passphrase eingeben – das geht auch schon, bevor der erste Datenstand veröffentlicht ist (Feld unter „Noch kein Datenstand veröffentlicht“, Knopf „Prüfen und speichern“). Gemeint ist die Passphrase, die bei der Einrichtung als GitHub-Secret `DATA_PASSPHRASE` festgelegt wurde. Das Handy speichert nur einen daraus abgeleiteten, nicht auslesbaren Schlüssel, nicht die Passphrase selbst. Unter ☰ → Einstellungen lässt er sich wieder vergessen.

## 3. Die sechs Hauptansichten (unten in der Leiste)

| Ansicht | Was sie zeigt |
|---|---|
| **Start** | Kursstand des Tages, Berechnungszeit, letzter Tageslauf und Abdeckung („berechnet / identifiziert – von … Einträgen der TR-Liste“). Darunter **Auswahl**: Aktiengruppe (A: alle, B: Ø Umsatz ≥ 10 Mio. USD), Zeitraum (feste Tasten 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Tage, freies Feld 1–90 und Lineal) und Gewichtung (alle elf Stufen, z. B. 60/40, 50/50, 0/100 direkt antippbar). Die App merkt sich die Auswahl; beim ersten Start 90 Tage und 60/40. Es folgen die ersten fünf dieser Auswahl, die Einstiege **Höchste Rendite**, **Gleichmäßigkeit + Rendite**, **Häufigste Aktien**, **Kursvergleich**, eine Kurzfassung „Sieger nach Zeitraum“, die Rendite-Leiter (1–90 Tage) und das höchste Einzelergebnis. |
| **Rendite** | Alle 90 Zeiträume, je Zeile der Sieger der **Gruppe A** und der **Gruppe B** nebeneinander – mit vollem Namen, ISIN, Kursrendite und tatsächlichem Start- und Enddatum. „Zu Zeitraum springen“ (7 … 90 Tage) scrollt zur Zeile. „Top 10 von A und B“ klappt beide Top 10 auf; Antippen öffnet die vollständige Rangliste des Zeitraums (seitenweise). Oben lassen sich auch die Einzellisten wählen („A: alle“ bzw. „B: Umsatz“) mit Ticker, Start- und Endkurs, Börse, Währung, Ø Umsatz und dem Vergleich mit einem zweiten Börsenplatz („Börsenplatz-Abweichung“ = dort weicht die Entwicklung stärker ab, als es die übliche Tagesschwankung der Aktie erklärt, mindestens um 10 % – Kurse prüfen; „kein Umsatz am Vergleichsplatz“ = dort wurde an dem Tag nicht gehandelt, kein Vergleich). |
| **Ranking** | Zeitraum über die festen Tasten 7 … 90 Tage, das Feld „Freier Zeitraum 1–90 Tage“ oder das Lineal; darunter Gewichtung und Aktiengruppe. Jede Zeile: Rang, Name und ISIN, Kursrendite, Rangscore 0–100, R², Schlusskurs mit Währung und Ø Tagesumsatz; „Details“ zeigt Ticker, Referenzbörse, Anfang, Zahl der Schlusskurse, Steigung, Rauschen, größten Rückgang, positive Schlusskursvergleiche, Quelle, Datenalter und Prüfstatus. Top 10, Top 50 oder alle (seitenweise); Export als CSV oder JSON. |
| **Matrix** | Gruppenvergleich: oben **A: alle Aktien** oder **B: Ø Umsatz ≥ 10 Mio. USD**. Die Matrix zeigt je Zeitraum (1–90 Tage, Spalte links und Kopfzeile bleiben stehen; Bereiche 1–30, 31–60, 61–90 wählbar; „Zu Zeitraum springen“) und Gewichtung (seitlich wischen) die erstplatzierte Aktie mit Name, ISIN, Rangscore und Rendite. Wiederkehrende Aktien tragen „↻ Anzahl“ und in beiden Gruppen dieselbe Farbe; Antippen markiert alle Vorkommen und bietet „Rangliste …“ und „Kursverlauf“. „≡ 1, 2“ = gleiches Kursfenster wie bei 1 und 2 Tagen (Wochenende). „Nicht berechenbar“ steht mit Grund da. **Liste**: dieselben Spitzenreiter kompakt; **Häufigkeit** wie unter „Häufig“. Export der Matrix als CSV oder JSON. |
| **Häufig** | **Häufigste Aktien**: Platz 1, Top 3, Top 10 und zugelassene Kombinationen je Aktie. Filter: Gruppe A, B oder beide (Treffer getrennt ausgewiesen – B ist eine Teilmenge von A), alle elf Gewichtungen, nur mit Gleichmäßigkeitsanteil oder eine; alle Zeiträume, 1–30, 31–60, 61–90 oder frei; „Identische Kursfenster nur einmal zählen“. Sortierung „Gewinnt am häufigsten“ (Platz 1 zuerst) oder „Meiste Top-10-Nennungen“. „↻ 14“ = 14 erste Plätze in dieser Auswahl. Export als CSV oder JSON mit allen Filtern. Die frühere, ausführlichere Zählung steht unter „Erweiterte Zählung“. |
| **Raster** | Kursverläufe mehrerer Aktien nebeneinander, standardmäßig „Start = 100“ auf gemeinsamer Skala: gleicher Zeitraum (feste Tasten 7 … 90 Tage), mehrere Zeiträume je Aktie oder alle in einem gemeinsamen Diagramm. |

**Sieger nach Zeitraum** (☰ ganz oben): zehn Zeilen für 7, 14, 21, 30, 40, 50, 60, 70, 80 und 90 Tage, Gruppe A und B nebeneinander, Gewichtung oben wählbar. Bei 0/100 der tatsächliche Renditesieger, sonst der Sieger nach Rangscore mit seiner tatsächlichen Kursrendite im selben Zeitraum. Antippen zeigt Beginn, Ende, Zahl der Schlusskurse und Referenzmarkt. Bei 7 und 14 Tagen mit Gleichmäßigkeitsanteil steht „Gleichmäßigkeit nicht berechenbar“ (zu wenige Schlusskurse). Darunter eine eigene Zählung nur über diese zehn Zeiträume.

Über ☰ oben rechts: **Sieger nach Zeitraum**, Jetzt aktualisieren, **Umschichtungs-Regel**, Gewichtungen vergleichen, alle Aktien & Abdeckung, Watchlist, Datenstand & Betrieb, „So wird gerechnet“, Einstellungen, Installieren.

### Umschichtungs-Regel (☰ → Umschichtungs-Regel, auch unten auf der Startseite)

Eine feste Rechenregel zum Ausprobieren, keine Anlageberatung: Sie hält gedanklich die 5 (oder 10) Aktien mit der höchsten Kursrendite der letzten 13 (oder 4) Wochen zu gleichen Teilen – nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD – und schichtet am ersten Freitag im Monat (oder jeden Freitag) um, umgesetzt am nächsten Handelstag.

- **Heute nach der Regel:** das gelbe Depot-Lineal zeigt die Aufteilung des Regeldepots (Nummer = Zeile in der Liste darunter, schraffiert = Bargeld). Darunter steht, was die Regel ändern würde – zum Beispiel „Verkaufen: …, Anteil 21 % → 0 %“ und „Kaufen: …, 0 % → 20 %, etwa 4.360 €“ – jeweils mit Grund. Nach einem Umschichtungstag heißt es „Was die Regel jetzt umsetzt“.
- **Beträge umrechnen:** eigenen Depotwert eintragen (z. B. 12.500) → alle Beträge auf diesen Wert umgerechnet, gleiche Anteile. Gespeichert nur auf diesem Handy.
- **Rückblick:** Wertverlauf des Regeldepots nach Kosten und Steuern im Vergleich zur selben Regel ohne Kosten und zu „alle Kandidaten zu gleichen Teilen“, darunter Endwert, größter Rückgang, Orders und Steuern, alle Umschichtungen mit Orders und die heutige Rangfolge.
- **Varianten:** oben Anzahl Aktien, Rhythmus, Trendzeitraum und Startkapital wählen; die Tabelle „Alle Varianten“ vergleicht sie im selben Zeitraum.

Das Regeldepot ist gedacht – die App kennt dein echtes Depot nicht und handelt nie. Der Rückblick kennt nur heute noch gelistete Aktien und ist deshalb eher zu gut.

## 4. Gewichtung lesen

Die erste Zahl ist immer der Anteil **Gleichmäßigkeit**, die zweite der Anteil **Kursrendite**:

- **Nur Kursrendite (0/100):** reine Prozentrangliste, auch schwankende Verläufe und Verluste.
- **50/50**, **60/40**: deine Mischungen – auf der Startseite und unter „Sieger nach Zeitraum“ direkt antippbar, im Ranking als Schnelltasten unter dem Schieberegler.
- **Nur Gleichmäßigkeit (100/0):** am geradesten gestiegene Aktien.

Alle elf Stufen (0, 10, 20 … 100) sind über den Schieberegler erreichbar. Mit Gleichmäßigkeitsanteil zählen nur Aktien, die im Zeitraum mindestens 15 echte Tageskurse haben und gestiegen sind (positive Rendite und positive Trendsteigung). In kurzen Zeiträumen unter etwa drei Wochen bleibt diese Liste deshalb leer; die App nennt dann den Grund und bietet die reine Renditeliste an.

## 5. Zahlen verstehen

- **Kursrendite:** Veränderung vom Startkurs bis zum Kursstand, in der Börsenwährung, ohne Dividenden und ohne Euro-Umrechnung. Immer mit Vorzeichen und Text, nicht nur farbig.
- **R²** (zum Beispiel 0,9326): wie nah die Kurse an einer geraden Linie liegen. 1 wäre exakt gerade. Sagt nichts über Sicherheit oder die Zukunft.
- **Rangscore 0–100:** Mischung aus dem Platz bei der Gleichmäßigkeit und dem Platz bei der Rendite, nur innerhalb der verglichenen Aktien. Keine Prognose und keine Wahrscheinlichkeit.
- **30 Tage** heißt immer 30 Kalendertage zurück, nicht „ein Monat“ und nicht 30 Börsentage.
- **Stand / Kursstand:** der Börsentag, dessen Schlusskurse verwendet wurden. Steht oben rechts in jeder Ansicht.

## 6. Jetzt aktualisieren, unterwegs und offline

**Jederzeit aktualisieren:** ☰ → **Jetzt aktualisieren** (auch unter Datenstand & Betrieb und, solange noch kein Stand da ist, auf der Startseite).

1. „Lauf auf GitHub starten“ antippen – GitHub öffnet „Täglicher Lauf“ (falls nötig anmelden).
2. „Run workflow“ antippen und den grünen Knopf „Run workflow“ bestätigen; Felder leer lassen.
3. Zurück in die App. Sie schaut jede Minute nach und meldet „Aktualisierung fertig“ mit „Neuen Stand anzeigen“ – oder „Lauf beendet – keine neuen Kurse“ mit Grund.

Neue Schlusskurse gibt es einmal je Börsentag, frühestens etwa eine Stunde nach Handelsschluss in New York (meist gegen 23 Uhr). Die Seite nennt den genauen Zeitpunkt („Neue Schlusskurse für Dienstag … gibt es heute ab 23:00 Uhr“). Ein Lauf vorher bringt keinen neuen Kursstand, übernimmt aber nachgelieferte Kurse. Gestartet wird über GitHub, weil die App absichtlich keinen Zugangsschlüssel enthält. Läuft schon ein Lauf, wartet ein zweiter Start, bis der erste fertig ist.

**Offline:** Einmal geladene Ansichten bleiben ohne Netz lesbar; die App sagt dann „Offline – gespeicherter Stand“ und nennt das Datum. Kommt ein neuer Datenstand, erscheint „Neuer Datenstand verfügbar“ – die aktuelle Liste bleibt, bis du wechselst.

## 7. Watchlist

Stern antippen merkt eine Aktie. Die Watchlist zeigt den Platz in der gesamten Rangliste und auf Wunsch eine Rangfolge nur innerhalb der Watchlist (deutlich als Untergruppe gekennzeichnet). **ISINs importieren und exportieren:** ISINs einfügen (eine je Zeile oder mit Komma) → „In die Watchlist übernehmen“; doppelte werden zusammengeführt, ungültige (falsche Prüfziffer) genannt, Namen oder Ticker nie zugeordnet. „ISIN-Liste exportieren“ bzw. „Mit Namen als CSV“ sichern die Liste. Sie liegt nur auf diesem Handy (Sicherung auch unter ☰ → Einstellungen → „Als Datei sichern“) und hat nichts mit der Watchlist oder dem Depot bei Trade Republic zu tun.

## 8. Was die App nicht tut

Keine Anlageberatung und keine Prognose (die Umschichtungs-Regel zeigt nur, was eine feste Rechenregel täte), keine Live-Kurse (nur Tagesschlusskurse), keine Orders, kein Zugriff auf ein Depot, keine Anmeldung bei Trade Republic. Dass eine Aktie in der TR-Liste steht, heißt nicht, dass sie im eigenen Konto jederzeit handelbar ist.

## 9. Nach der Installation kurz prüfen (5 Minuten)

Diese Prüfung auf dem echten Gerät steht noch aus (09_Bekannte_Luecken). Bitte einmal durchgehen und Auffälliges notieren:

1. App vom Startbildschirm öffnen: Sie startet ohne Browserleiste, oben steht „Kursstand“ mit Datum – und **kein** DEMO-Hinweis.
2. Passphrase eingeben, App schließen und wieder öffnen: Sie bleibt entsperrt.
3. **Rendite**: 90 Zeilen, jede mit vollem Namen, ISIN und Prozentwert; eine ISIN antippen und kopieren.
4. **Ranking**: die Tasten 7, 30 und 90 Tage antippen, im Feld „Freier Zeitraum“ 37 eingeben, Gewichtung 60/40 und 50/50 wählen; eine Aktie öffnen.
5. Im Kurschart mit einem Finger über den Verlauf streichen (Tageskurs erscheint) und mit zwei Fingern zoomen; mit der Zurück-Geste zur Liste zurück.
6. **Raster**: „Mehrere Zeiträume“ und „Gemeinsam“ antippen. ☰ → **Sieger nach Zeitraum**: zehn Zeilen, Gewichtung 50/50 wählen, eine Zelle antippen.
7. Flugmodus einschalten, App öffnen: „Offline – gespeicherter Stand“ mit Datum.
8. ☰ → Datenstand & Betrieb: letzter Lauf, Uhrzeit 07:00 und Abdeckung sind angegeben.

## So sieht es aus

Bildschirmfotos aus dem automatischen Browser-Test (S25+-Bildschirmgröße in Chromium, **DEMO-Daten** mit erfundenen Firmen – keine echten Kurse; Version 1.5.0):

| Start: Auswahl | Sieger nach Zeitraum (50/50) | Ranking 30 Tage, 60/40 |
|---|---|---|
| ![Startseite mit Aktiengruppe, Schnellwahl 7–90 Tage und Gewichtung (DEMO)](bilder/start.jpg) | ![Zehn feste Zeiträume mit Sieger A und B (DEMO)](bilder/sieger.jpg) | ![Rangliste mit ISIN, Kursrendite, Rangscore und R² (DEMO)](bilder/ranking.jpg) |

| Rendite 1–90: A und B | Häufigste Aktien | Matrix A/B |
|---|---|---|
| ![90 Zeiträume mit Sieger der Gruppen A und B (DEMO)](bilder/hoechste_rendite.jpg) | ![Häufigkeitsranking mit Platz 1, Top 3, Top 10 (DEMO)](bilder/haeufigste.jpg) | ![Matrix 1–90 Tage × 11 Gewichtungen (DEMO)](bilder/matrix.jpg) |

| Kurschart | Chart-Raster |
|---|---|
| ![Kurschart mit Anpassungsgerade, nur Tagesschlusskurse (DEMO)](bilder/aktie.jpg) | ![Kacheln mit Kursverläufen, Start = 100 (DEMO)](bilder/raster.jpg) |
