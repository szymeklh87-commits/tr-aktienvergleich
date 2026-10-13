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

## 3. Die fünf Hauptansichten (unten in der Leiste)

| Ansicht | Was sie zeigt |
|---|---|
| **Start** | Kursstand des Tages, die „Rendite-Leiter“ (höchste Rendite je Zeitraum 1–90 Tage über einem gelben Zeitlineal), das höchste Einzelergebnis, die ersten fünf deiner Lieblingseinstellung und die häufigsten Aktien. |
| **Rendite** | Zwei Reiter: **Höchste Kursrendite** (alle vergleichbaren Aktien) und **Ø Umsatz ≥ 10 Mio. USD** (nur Aktien mit Ø Tagesumsatz von mindestens 10 Mio. USD). Je Zeitraum zuerst der Sieger mit Ticker, ISIN, Start- und Endkurs mit Datum, Börse, Währung und Ø Umsatz; „Top 10 anzeigen“ klappt die ersten zehn auf, von dort geht es zur vollständigen Rangliste. Standard sind 1–7 Tage; 8–30, 31–90 oder alle 90 lassen sich wählen. „Sehr niedriger Umsatz“ ist markiert. Bei den vorderen Plätzen steht der Vergleich mit einem zweiten Börsenplatz (meist Xetra oder Frankfurt); „Börsenplatz-Abweichung“ (gelb) heißt: dort weicht die Entwicklung um mehr als 10 % ab – Kurse prüfen. Name antippen → Kurschart. |
| **Ranking** | Zeitraum auf dem gelben Lineal wählen (jeder Tag 1–90, Schnelltasten 1, 3, 7, 14, 21, 30, 45, 60, 90), darunter die Gewichtung. Top 10, Top 50 oder alle (seitenweise). |
| **Häufig** | Welche Aktien in diesem Datenstand am häufigsten unter den Top 10 (oder Top 3 / Platz 1) liegen – über alle Zeiträume und alle elf Gewichtungen. Antippen → Treffer-Matrix 90 Zeiträume × 11 Gewichtungen. |
| **Raster** | Kursverläufe mehrerer Aktien nebeneinander: gleicher Zeitraum, mehrere Zeiträume (1, 7, 14, 30, 60, 90 Tage) oder alle in einem gemeinsamen Diagramm. |

Über ☰ oben rechts: Jetzt aktualisieren, **Umschichtungs-Regel**, Gewichtungen vergleichen, alle Aktien & Abdeckung, Watchlist, Datenstand & Betrieb, „So wird gerechnet“, Einstellungen, Installieren.

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
- **50/50**, **60/40**: deine Mischungen – Schnelltasten unter dem Schieberegler.
- **Nur Gleichmäßigkeit (100/0):** am geradesten gestiegene Aktien.

Alle elf Stufen (0, 10, 20 … 100) sind über den Schieberegler erreichbar. Mit Gleichmäßigkeitsanteil zählen nur Aktien, die im Zeitraum mindestens 15 echte Tageskurse haben und gestiegen sind (positive Rendite und positive Trendsteigung). In kurzen Zeiträumen unter etwa drei Wochen bleibt diese Liste deshalb leer; die App nennt dann den Grund und bietet die reine Renditeliste an.

## 5. Zahlen verstehen

- **Kursrendite:** Veränderung vom Startkurs bis zum Kursstand, in der Börsenwährung, ohne Dividenden und ohne Euro-Umrechnung. Immer mit Vorzeichen und Text, nicht nur farbig.
- **R²** (zum Beispiel 0,9326): wie nah die Kurse an einer geraden Linie liegen. 1 wäre exakt gerade. Sagt nichts über Sicherheit oder die Zukunft.
- **Score:** Mischung aus dem Platz bei der Gleichmäßigkeit und dem Platz bei der Rendite (0 bis 100), nur innerhalb der verglichenen Aktien.
- **Stand / Kursstand:** der Börsentag, dessen Schlusskurse verwendet wurden. Steht oben rechts in jeder Ansicht.

## 6. Jetzt aktualisieren, unterwegs und offline

**Jederzeit aktualisieren:** ☰ → **Jetzt aktualisieren** (auch unter Datenstand & Betrieb und, solange noch kein Stand da ist, auf der Startseite).

1. „Lauf auf GitHub starten“ antippen – GitHub öffnet „Täglicher Lauf“ (falls nötig anmelden).
2. „Run workflow“ antippen und den grünen Knopf „Run workflow“ bestätigen; Felder leer lassen.
3. Zurück in die App. Sie schaut jede Minute nach und meldet „Aktualisierung fertig“ mit „Neuen Stand anzeigen“ – oder „Lauf beendet – keine neuen Kurse“ mit Grund.

Neue Schlusskurse gibt es einmal je Börsentag, frühestens etwa eine Stunde nach Handelsschluss in New York (meist gegen 23 Uhr). Die Seite nennt den genauen Zeitpunkt („Neue Schlusskurse für Dienstag … gibt es heute ab 23:00 Uhr“). Ein Lauf vorher bringt keinen neuen Kursstand, übernimmt aber nachgelieferte Kurse. Gestartet wird über GitHub, weil die App absichtlich keinen Zugangsschlüssel enthält. Läuft schon ein Lauf, wartet ein zweiter Start, bis der erste fertig ist.

**Offline:** Einmal geladene Ansichten bleiben ohne Netz lesbar; die App sagt dann „Offline – gespeicherter Stand“ und nennt das Datum. Kommt ein neuer Datenstand, erscheint „Neuer Datenstand verfügbar“ – die aktuelle Liste bleibt, bis du wechselst.

## 7. Watchlist

Stern antippen merkt eine Aktie. Die Watchlist zeigt den Platz in der gesamten Rangliste und auf Wunsch eine Rangfolge nur innerhalb der Watchlist (deutlich als Untergruppe gekennzeichnet). Sie liegt nur auf diesem Handy. Sicherung: ☰ → Einstellungen → „Als Datei sichern“. Sie hat nichts mit der Watchlist bei Trade Republic zu tun.

## 8. Was die App nicht tut

Keine Anlageberatung und keine Prognose (die Umschichtungs-Regel zeigt nur, was eine feste Rechenregel täte), keine Live-Kurse (nur Tagesschlusskurse), keine Orders, kein Zugriff auf ein Depot, keine Anmeldung bei Trade Republic. Dass eine Aktie in der TR-Liste steht, heißt nicht, dass sie im eigenen Konto jederzeit handelbar ist.

## 9. Nach der Installation kurz prüfen (5 Minuten)

Diese Prüfung auf dem echten Gerät steht noch aus (09_Bekannte_Luecken). Bitte einmal durchgehen und Auffälliges notieren:

1. App vom Startbildschirm öffnen: Sie startet ohne Browserleiste, oben steht „Kursstand“ mit Datum – und **kein** DEMO-Hinweis.
2. Passphrase eingeben, App schließen und wieder öffnen: Sie bleibt entsperrt.
3. **Rendite**: 90 Zeilen, jede mit vollem Namen, ISIN und Prozentwert; eine ISIN antippen und kopieren.
4. **Ranking**: Lineal auf 7, 30 und 90 Tage ziehen, Gewichtung 60/40 und 50/50 wählen; eine Aktie öffnen.
5. Im Kurschart mit einem Finger über den Verlauf streichen (Tageskurs erscheint) und mit zwei Fingern zoomen; mit der Zurück-Geste zur Liste zurück.
6. **Raster**: „Mehrere Zeiträume“ und „Gemeinsam“ antippen.
7. Flugmodus einschalten, App öffnen: „Offline – gespeicherter Stand“ mit Datum.
8. ☰ → Datenstand & Betrieb: letzter Lauf, Uhrzeit 06:00 und Abdeckung sind angegeben.

## So sieht es aus

Bildschirmfotos aus dem automatischen Browser-Test (S25+-Bildschirmgröße, **DEMO-Daten** mit erfundenen Firmen – keine echten Kurse):

| Start | Ranking 30 Tage, 60/40 | Kurschart |
|---|---|---|
| ![Startansicht mit Rendite-Leiter (DEMO)](bilder/start.jpg) | ![Rangliste mit ISIN, Rendite, R² und Score (DEMO)](bilder/ranking.jpg) | ![Kurschart mit Anpassungsgerade (DEMO)](bilder/aktie.jpg) |

| Höchste Rendite 1–90 Tage | Chart-Raster | Häufigste Aktien |
|---|---|---|
| ![90 Zeiträume mit Renditesieger (DEMO)](bilder/hoechste_rendite.jpg) | ![Kacheln mit Kursverläufen (DEMO)](bilder/raster.jpg) | ![Häufigkeitsliste (DEMO)](bilder/haeufigste.jpg) |
