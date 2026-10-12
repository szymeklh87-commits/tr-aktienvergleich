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

Die Daten sind verschlüsselt veröffentlicht. Beim ersten Öffnen einmal die Passphrase eingeben, die bei der Einrichtung als GitHub-Secret `DATA_PASSPHRASE` festgelegt wurde. Das Handy speichert nur einen daraus abgeleiteten, nicht auslesbaren Schlüssel, nicht die Passphrase selbst. Unter ☰ → Einstellungen lässt er sich wieder vergessen.

## 3. Die fünf Hauptansichten (unten in der Leiste)

| Ansicht | Was sie zeigt |
|---|---|
| **Start** | Kursstand des Tages, die „Rendite-Leiter“ (höchste Rendite je Zeitraum 1–90 Tage über einem gelben Zeitlineal), das höchste Einzelergebnis, die ersten fünf deiner Lieblingseinstellung und die häufigsten Aktien. |
| **Rendite** | Genau 90 Zeilen: je Zeitraum die Aktie mit der höchsten reinen Kursrendite, mit vollem Namen, ISIN, Prozent und echtem Beginn/Ende. Zeile antippen → ganze Rangliste dieses Zeitraums mit Chart. „Kurschart“ → Kursverlauf der Aktie. |
| **Ranking** | Zeitraum auf dem gelben Lineal wählen (jeder Tag 1–90, Schnelltasten 1, 3, 7, 14, 21, 30, 45, 60, 90), darunter die Gewichtung. Top 10, Top 50 oder alle (seitenweise). |
| **Häufig** | Welche Aktien in diesem Datenstand am häufigsten unter den Top 10 (oder Top 3 / Platz 1) liegen – über alle Zeiträume und alle elf Gewichtungen. Antippen → Treffer-Matrix 90 Zeiträume × 11 Gewichtungen. |
| **Raster** | Kursverläufe mehrerer Aktien nebeneinander: gleicher Zeitraum, mehrere Zeiträume (1, 7, 14, 30, 60, 90 Tage) oder alle in einem gemeinsamen Diagramm. |

Über ☰ oben rechts: Gewichtungen vergleichen, alle Aktien & Abdeckung, Watchlist, Datenstand & Betrieb, „So wird gerechnet“, Einstellungen, Installieren.

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

## 6. Unterwegs und offline

Einmal geladene Ansichten bleiben ohne Netz lesbar; die App sagt dann „Offline – gespeicherter Stand“ und nennt das Datum. Kommt ein neuer Datenstand, erscheint „Neuer Datenstand verfügbar“ – die aktuelle Liste bleibt, bis du wechselst.

## 7. Watchlist

Stern antippen merkt eine Aktie. Die Watchlist zeigt den Platz in der gesamten Rangliste und auf Wunsch eine Rangfolge nur innerhalb der Watchlist (deutlich als Untergruppe gekennzeichnet). Sie liegt nur auf diesem Handy. Sicherung: ☰ → Einstellungen → „Als Datei sichern“. Sie hat nichts mit der Watchlist bei Trade Republic zu tun.

## 8. Was die App nicht tut

Keine Kauf- oder Verkaufsempfehlung, keine Prognose, keine Live-Kurse (nur Tagesschlusskurse), keine Orders, kein Zugriff auf ein Depot, keine Anmeldung bei Trade Republic. Dass eine Aktie in der TR-Liste steht, heißt nicht, dass sie im eigenen Konto jederzeit handelbar ist.

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
