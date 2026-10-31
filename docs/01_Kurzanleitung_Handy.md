# Kurzanleitung für das Handy

Die App zeigt jeden Tag neu berechnet, welche Aktien aus der Trade-Republic-Aktienliste in den letzten 1 bis 90 Tagen am stärksten gestiegen sind – und welche dabei am gleichmäßigsten. Gerechnet wird auf einem Server. Dein Handy muss dafür weder eingeschaltet noch die App geöffnet sein. Die App schaut nur zurück: Sie sagt nicht voraus, wie es weitergeht, und gibt keine Kaufempfehlung.

## In fünf Minuten startklar (ab 1.16)

**Installieren (Chrome auf dem Galaxy S25+)**

1. In Chrome die Adresse öffnen: **https://szymeklh87-commits.github.io/tr-aktienvergleich/**
2. Oben rechts auf ⋮ tippen und **„App installieren“** wählen. Steht dort nur „Zum Startbildschirm hinzufügen“, das wählen und danach „Installieren“.
3. Bestätigen. Das gelbe Symbol **„TR-Vergleich“** liegt dann auf dem Startbildschirm.

Ist die App schon installiert, bekommt sie die neue Version von selbst: Erscheint oben „Neue App-Version verfügbar“, auf „Aktualisieren“ tippen – sonst die App ganz schließen (aus den zuletzt benutzten Apps wegwischen) und neu öffnen. Die Version steht unter ☰ → Einstellungen.

**Erster Start**

1. App über das Symbol öffnen. Es erscheint „App entsperren“.
2. Deine **Passphrase** eingeben (das Kennwort, mit dem die Kursdaten verschlüsselt sind) und auf „Entsperren“ tippen. Tippfehler? Mit „Passphrase anzeigen“ siehst du, was du eingegeben hast.
3. Die Startseite öffnet sich mit der Karte **„Neu hier? So funktioniert die App“**. „Hilfe und Begriffe“ erklärt alles mit Beispielen, „Verstanden“ blendet die Karte aus.

**Die wichtigsten Funktionen ausprobieren**

1. **Startseite:** oben die Top 3 nach einer festen Punkteregel, darunter der Kursstand (der Börsentag, dessen Schlusskurse verwendet werden).
2. Unten **„Rendite“**: für jeden Zeitraum von 1 bis 90 Tagen die Aktie, die am stärksten gestiegen ist. Einen Zeitraum antippen öffnet die ganze Rangliste.
3. Oben **„Gleichmäßig + Rendite“**: Zeitraum wählen (zum Beispiel 30 Tage) und Gewichtung (zum Beispiel 60/40 = 60 % Gleichmäßigkeit, 40 % Kursrendite). Über der Liste steht, was die Zahlen in einer Zeile bedeuten – die unterstrichenen Wörter antippen.
4. **Eine Aktie antippen:** Kursverlauf, Kennzahlen, Einschätzung der Analysten. Mit dem Stern ☆ merken.
5. Unten **„Aktien“**: eine Aktie mit Namen, Ticker oder ISIN suchen – die Treffer erscheinen schon beim Tippen. Daneben die **Watchlist** mit deinen gemerkten Aktien.
6. Unten **„Potenzial“**: Aktien, die oft gestiegen sind und deren Kursziel über dem Kurs liegt (Gesamtwertung 0–100).
7. Rendite → **„Depots“**: Wie hätten sich die zehn häufigsten Gewinner als Depot entwickelt? Mit „Neues Depot“ eigene anlegen.
8. ☰ → **„Hilfe und Begriffe“**: alle Fachwörter mit Beispiel, ein durchgerechnetes Ranglisten-Beispiel und häufige Fragen.
9. ☰ → **„Jetzt aktualisieren“**: die Berechnung sofort starten (über GitHub, mit deiner Anmeldung). Sonst kommen neue Kurse einmal je Börsentag von selbst: ab 1.17 rechnet ein **Nachtlauf** nach dem letzten Börsenschluss (geplant 00:37 Uhr, im Winter 23:37 Uhr; GitHub startet geplante Läufe oft Stunden später), dazu morgens ab 7 Uhr. Unter dem Kursstand auf der Startseite steht, wann der nächste Stand kommt – und wenn etwas schiefging, was zu tun ist.

**Welche Art von Angabe sehe ich? (ab 1.17)** Über jeder Liste und jedem Abschnitt steht ein Kennzeichen: **Rückblick** (Zahlen aus vergangenen Kursen), **Rangbewertung** (Platz oder Punkte nach einer festen Regel der App), **Prognose Dritter** (Kursziele und Empfehlungen von Analysten, gestrichelt) und **Angaben Dritter** (Nachrichten, Community, gepunktet). Darunter steht in ein bis zwei Sätzen, was du siehst und was du tun kannst; „So liest du die Zahlen“ klappt Bedeutung, Rechenweg und ein Rechenbeispiel auf.

**Wenn etwas nicht klappt:** Jede Meldung nennt das Problem und den nächsten Schritt (zum Beispiel „Keine Internetverbindung … Erneut versuchen“). Die häufigsten stehen in der App unter ☰ → Hilfe und Begriffe → „Wenn etwas nicht klappt“ und hier in [06_Fehlerbehebung](06_Fehlerbehebung.md).

---

Ab hier: ausführliche Beschreibung aller Bereiche.

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

## 2. Erster Start: Passphrase

Die Daten sind verschlüsselt veröffentlicht. Beim ersten Öffnen einmal die Passphrase eingeben – das geht auch schon, bevor der erste Datenstand veröffentlicht ist (Feld unter „Noch kein Datenstand veröffentlicht“, Knopf „Prüfen und speichern“). Gemeint ist die Passphrase, die bei der Einrichtung als GitHub-Secret `DATA_PASSPHRASE` festgelegt wurde. Das Handy speichert nur einen daraus abgeleiteten, nicht auslesbaren Schlüssel, nicht die Passphrase selbst. Unter ☰ → Einstellungen lässt er sich wieder vergessen.

## 3. Aufbau: fünf Bereiche unten in der Leiste (ab 1.6)

| Bereich | Was er zeigt |
|---|---|
| **Start** | Ab 1.15 die wichtigsten Zahlen zuerst: **Top 3 nach Zahlen**, der **Kursstand** in einer Zeile (mit „Kurse jetzt aktualisieren“), **Kandidaten mit Potenzial** (die drei Aktien mit den stärksten Signalen – Reiter *Gesamt*, *Kurz*, *Lang*, *Kursziel*, *Volumen*; jede Zeile mit zwei Ampeln **kurz** = Tage bis wenige Wochen, **lang** = etwa 12 Monate, und bis zu vier Gründen), **Bericht 1–30 Tage** in Kürze (die drei Aktien, die am häufigsten auf Platz 1 liegen – Antippen öffnet den Bericht mit dieser Aktie hervorgehoben), **deine Rangliste** mit Gruppe A/B, Zeitraum und Gewichtung und den ersten fünf Plätzen in einem Abschnitt, die Einstiege. Aufklappbar unter **„Mehr auf einen Blick“**: Sieger nach Zeitraum, Rendite-Leiter, höchste beobachtete Kursrendite, Umschichtungs-Regel und Abdeckung. |
| **Rendite** | Oben fünf Reiter: **Rendite 1–90** (alle 90 Zeiträume, Sieger der Gruppen A und B), **Bericht 1–30** (ab 1.8.1, siehe unten), **Depots** (ab 1.9, siehe unten), **Gleichmäßig + Rendite** (Rangliste nach Gewichtung, früher „Ranking“) und **Sieger** (zehn feste Zeiträume). |
| **Potenzial** | Vollständige Liste der Kandidaten: *Beides stark* (beide Ampeln grün zuerst), *Kurzfristig*, *Langfristig*, *Kursziel* (höchste erwartete Steigerung). „Filter“: mindestens so viele Analysten, Branche, nur grün, nur Gruppe B. |
| **Aktien** | Reiter **Alle Aktien** (Suche, Abdeckung) und **Watchlist**. Die Einzelansicht einer Aktie gehört hierher. |
| **Analyse** | Werkzeuge mit je einem Satz, wofür sie gut sind: Matrix A/B, Häufigste Aktien, Chart-Raster, Gewichtungen vergleichen, Umschichtungs-Regel. |

**Einzelansicht einer Aktie** (Antippen in einer Liste): oben Name, ISIN, Börse, Schlusskurs und die beiden Ampeln; darunter vier Reiter.

* **Überblick:** *Urteil der Signale* (kurz- und langfristig, Punkte 0–100 und ein Satz, warum), *Prognose (12 Monate)* mit erwarteter Steigerung, Kursziel-Spanne und Grafik (Kurs bisher, Ø Kursziel, Spanne, übliche Schwankung), *Trefferquote der Vergangenheit* („Aktien mit ähnlichem Bild stiegen in 5 Handelstagen in 56 % der Fälle …“), *Kursverlauf* mit 1W / 1M / 3M / 6M / 1J / Max, *Signale im Einzelnen* mit Balken und Begründung.
* **Analysten:** Kursziele je Quelle, Kaufen/Halten/Verkaufen heute und in den drei Monaten davor, neueste Urteile der Analystenhäuser (US), Bewertung von Trading Central (US), Nachrichten mit Tendenz (▲ ▼ ●), Stimmung der Community als Balken.
* **Kennzahlen:** Bewertung, Wachstum, Finanzen, Risiko und nächster Zahlentermin – jede Zeile mit Erklärung.
* **Rendite 1–90:** die bisherigen Angaben (Kennzahlen eines Zeitraums, Kursgrafik, Ränge in allen Gewichtungen, Stammdaten).

Überall gilt: **ⓘ antippen** zeigt in einem Satz, was die Zahl bedeutet und wie sie entsteht. Die Ampeln sind eine Zusammenfassung nach festen Regeln – keine Kaufempfehlung. Grün heißt „die meisten Signale sind positiv“, nicht „wird steigen“.

**Bericht 1–30** (Rendite → Bericht 1–30, auf der Startseite der erste Einstieg): der Bericht „1–30 Tage · Rendite und Gleichmäßigkeit“ zum Durchscrollen – täglich mit den neuen Kursen, im Zwischenstand mit den vorläufigen Kursen.

- Oben vier Kennzahlen (ISINs im TR-Verzeichnis, geladene Kursreihen, Aktien in mindestens einem 1–30-Tage-Fenster, Ranglisten mit Spitzenreiter von 240) und **Am häufigsten auf Platz 1** (fünf Aktien, gezählt über alle Ranglisten des Berichts).
- **Spitzenreiter je Zeitraum:** vier Tabellen untereinander (0/100, 40/60, 50/50, 60/40), je Zeile ein Zeitraum von 1 bis 30 Tagen, links Gruppe A (alle Aktien), rechts Gruppe B (Ø Tagesumsatz ab 10 Mio. USD). Jede Zelle: Name, ISIN, Kursrendite, Zeitraum, Währung, bei gemischten Gewichtungen der Score; ↻ 5 = dieselbe Aktie liegt in fünf Zeiträumen dieser Spalte vorne. Kurze Zeiträume ohne 15 Schlusskurse stehen zusammengefasst in einer schraffierten Zeile („1–19 · Nicht berechenbar …“). Oben lässt sich auch nur eine Gewichtung zeigen. Antippen öffnet Kursverlauf und Kennzahlen.
- **Alle vier Gewichtungen nebeneinander:** dieselben Sieger als Matrix für Gruppe A oder B; gleiche Farbe und ↻ = dieselbe Aktie mehrfach vorne.
- **Welche Aktie erscheint am häufigsten?** wie in der Datei mit Filtern (A und B, nur A, nur B; alle vier Gewichtungen oder nur 40/60, 50/50, 60/40; nach ersten Plätzen oder Top-10-Nennungen; gleiche Kursfenster einmal) – Spalten Platz 1, Top 3, Top 10.
- **Kästchen hinter dem Namen** (ab 1.8.2): die Gesamtwertung 0–100 der Aktie (grün ab 65, gelb ab 50, sonst grau) – so siehst du neben dem Rückblick, welche der häufigen Sieger auch nach vorn stark bewertet sind.
- **Hervorheben:** eine Aktie in der Matrix oder in den Häufigkeitslisten antippen → alle ihre Fundstellen auf der Seite sind umrahmt, die Leiste unten nennt die ersten Plätze (A und B); „Nächstes Vorkommen“ springt weiter, „Kursverlauf“ öffnet die Aktie, ✕ hebt die Markierung auf.
- Unten: vollständige Rangliste, Kursverläufe im Raster, Abdeckung, Rechenvorschrift und **Bericht herunterladen (CSV)** mit allen 240 Spitzenreitern.

**Depots** (Rendite → Depots, ☰ → Musterdepots; ab 1.9) – der „Aktien-Kompass“ aus deiner Datei „Zwei Zehnerdepots“:

- **Welche Aktien erscheinen am häufigsten?** Gezählt wird, wie oft eine Aktie auf Platz 1 stand („erste Plätze“) und wie oft unter den ersten zehn („Top-10-Nennungen“). **Standard (ab 1.10): die Gewichtungen 40/60, 50/50 und 60/40**, 1–30 Tage, Gruppe A und B. Im Auswahlfeld „Gewichtungen“ als Optionen: **Ausführlich – alle 11 Gewichtungen** (0/100 bis 100/0, wie in der Datei v3), **Bericht** (0/100, 40/60, 50/50, 60/40) oder eine einzelne Gewichtung; daneben 1–30 oder 1–90 Tage und **Top 20** (Standard) oder Top 10.
- Oben drei Zahlen (häufigste erste Plätze, häufigste Top-10-Nennungen, beide Listen zusammen mit den gemeinsamen). Darunter die Liste – „Beide Top 20“, „Nur gemeinsame“, „Erste Plätze“ oder „Top-10-Nennungen“; grün hinterlegt = in beiden Top-20-Listen; rechts die Zählungen mit Rang (grau = außerhalb der Top 20). „Kurzfassung kopieren“ legt den Text in die Zwischenablage.
- Drei Erklärblöcke zum Aufklappen: **Wer gewinnt bei welcher Gewichtung am häufigsten?** (je Gewichtung der Sieger mit „Siege / gültige Ranglisten“), **Wie werden 0/100 bis 100/0 berechnet?** (Formel und ein echtes 30-Tage-Beispiel: Sieger, Score, Rendite, R² je Gewichtung) und **Was ändert sich mit allen elf Gewichtungen?** (Rang und Nennungen Standard → alle elf).
- **Depot wählen:** „10 Sieger“ (die zehn mit den meisten ersten Plätzen; ab 1.14 immer zehn – haben weniger Aktien einen ersten Platz, füllen die nächsten nach Top 3, dann Top 10 auf, gekennzeichnet „Aufgefüllt“) und „10 Top-10“ (die zehn mit den meisten Top-10-Nennungen) – beide immer aus der Standardauswahl –, dein Dreier- und Viererdepot oder eigene Depots. Darunter **Kalendertage** (1, 7, 14, 21, 30 oder mit − und + jeder Tag), **Rechenbasis** (USD wie in der Datei, EUR oder Originalwährung) und **Startkapital**.
- Oben die **Depotrendite**, der **Endwert** aus dem Startkapital und der **größte Beitrag**; darunter jede Aktie mit Balken und **Beitrag in Prozentpunkten** (PP), Aktienrendite, Start- und Endgewicht, Endwert sowie Start- und Endkurs. † = Hinweis zu Umsatz oder Kurs.
- **Eigenes Depot:** in der Häufigkeitsliste Häkchen setzen → unten Namen eingeben → „Als Depot speichern“. Oder „Neues Depot“ und ISINs eintragen. „… bearbeiten“ ändert oder löscht ein eigenes Depot. Gespeichert nur auf diesem Handy (auch im Export unter Einstellungen).
- **Alle Depots · 1–30 Tage:** Grafik mit einer Linie je Depot (antippen zeigt die Werte) und Tabelle – 30 getrennte Rückblicke, kein Verlauf. **Kurse im direkten Vergleich:** die Aktien des Depots, die gemeinsamen der beiden Top-20-Listen, beide Listen zusammen oder eine der beiden Listen, Start = 100.

**Sieger nach Zeitraum** (Rendite → Sieger): zehn Zeilen für 7, 14, 21, 30, 40, 50, 60, 70, 80 und 90 Tage, Gruppe A und B nebeneinander, Gewichtung oben wählbar. Bei 0/100 der tatsächliche Renditesieger, sonst der Sieger nach Rangscore mit seiner tatsächlichen Kursrendite im selben Zeitraum. Antippen zeigt Beginn, Ende, Zahl der Schlusskurse und Referenzmarkt. Bei 7 und 14 Tagen mit Gleichmäßigkeitsanteil steht „Gleichmäßigkeit nicht berechenbar“ (zu wenige Schlusskurse). Darunter eine eigene Zählung nur über diese zehn Zeiträume.

Über ☰ oben rechts (ab 1.15 in zwei Gruppen): oben Jetzt aktualisieren, Top nach Zahlen, Bericht 1–30 Tage, Musterdepots, Watchlist; darunter die App – Datenstand & Betrieb, „So wird gerechnet“, Einstellungen, Installieren. Kandidaten und Analyse-Werkzeuge stehen unten in der Leiste (Potenzial, Analyse).

### Umschichtungs-Regel (Analyse → Umschichtungs-Regel, auf der Startseite unter „Mehr auf einen Blick“)

Eine feste Rechenregel zum Ausprobieren, keine Anlageberatung: Sie hält gedanklich die 5 (oder 10) Aktien mit der höchsten Kursrendite der letzten 13 (oder 4) Wochen zu gleichen Teilen – nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD – und schichtet am ersten Freitag im Monat (oder jeden Freitag) um, umgesetzt am nächsten Handelstag.

- **Heute nach der Regel:** das gelbe Depot-Lineal zeigt die Aufteilung des Regeldepots (Nummer = Zeile in der Liste darunter, schraffiert = Bargeld). Darunter steht, was die Regel ändern würde – zum Beispiel „Verkaufen: …, Anteil 21 % → 0 %“ und „Kaufen: …, 0 % → 20 %, etwa 4.360 €“ – jeweils mit Grund. Nach einem Umschichtungstag heißt es „Was die Regel jetzt umsetzt“.
- **Beträge umrechnen:** eigenen Depotwert eintragen (z. B. 12.500) → alle Beträge auf diesen Wert umgerechnet, gleiche Anteile. Gespeichert nur auf diesem Handy.
- **Rückblick:** Wertverlauf des Regeldepots nach Kosten und Steuern im Vergleich zur selben Regel ohne Kosten und zu „alle Kandidaten zu gleichen Teilen“, darunter Endwert, größter Rückgang, Orders und Steuern, alle Umschichtungen mit Orders und die heutige Rangfolge.
- **Varianten:** oben Anzahl Aktien, Rhythmus, Trendzeitraum und Startkapital wählen; die Tabelle „Alle Varianten“ vergleicht sie im selben Zeitraum.

Das Regeldepot ist gedacht – die App kennt dein echtes Depot nicht und handelt nie. Der Rückblick kennt nur heute noch gelistete Aktien und ist deshalb eher zu gut.

### Auffällige ausblenden (ab 1.14)

In allen Ranglisten stehen zwei Kennzeichen: **„Kaum Umsatz“** (im Schnitt unter 1 Mio. USD am Tag gehandelt – der Kurs lässt sich leicht bewegen) und **„Einzelsprung“** (ein einzelner Handelstag erklärt mehr als die Hälfte der Kursbewegung). Der Haken **„Auffällige ausblenden“** (in den Ranglisten und unter ☰ → Einstellungen) blendet sie überall aus – auch auf der Startseite und im Chart-Raster. Die Plätze bleiben die der vollständigen Rangliste: steht dort „Platz 3“, lagen davor nur auffällige Aktien.

### Alle Aktien bewertet (ab 1.14)

Fehlt einer Aktie der Schlusskurs am Stichtag – Feiertag ihrer Börse oder Kurs nicht geliefert –, zählt sie mit ihrem letzten Schlusskurs (höchstens eine verpasste Börsensitzung). In der Zeile steht dann „Schlusskurs 12.10.“, ihre Zeiträume enden an diesem Tag. So fehlt keine Aktie mehr wegen eines einzelnen fehlenden Kurses.

### Top 3 nach Zahlen (ganz oben auf der Startseite, ab 1.11)

Die drei Aktien mit den meisten Punkten nach einer festen Regel: oft unter den ersten 10 der Standard-Ranglisten (bis 40 Punkte), stetig steigend (25), Analysten positiv (20), Volumen gestiegen (15), Abzug bei kleinem Börsenwert. Jede Zeile zeigt die Punkte je Teil, den Börsenwert, Warnzeichen (z. B. „in 20 Sitzungen mehr als verdoppelt“) und die Trefferquote der Vergangenheit. Darunter **Deine Aktien**: die Aktien aus deinen Musterdepots und der Watchlist mit ihrem Platz nach derselben Regel – so siehst du sofort, ob z. B. PDS noch vorne liegt oder wie viele Aktien davor stehen. **Alle Plätze und Regel** öffnet die ganze Rangfolge (auch „Ohne Warnzeichen“). Ab 1.14 bekommen nur **handelbare Aktien** (Ø Tagesumsatz ab 10 Mio. USD) einen Platz und damit die Chance auf die Top 3; wenig gehandelte zeigen ihre Punkte ohne Platz („–“, einblendbar mit „Auch wenig gehandelte Aktien zeigen“). Unter Potenzial gibt es außerdem die Liste **Volumen** (Aktien mit deutlich gestiegenem Umsatz), in der Einzelansicht den **Börsenwert** und unter der Kursgrafik eine **Volumen-Leiste** (blau: mehr als doppelt so viel wie üblich).

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

**Mit Zugang (ab 1.21, einmal einrichten: ☰ → Einstellungen → „Zugang für ‚Jetzt aktualisieren‘“, Anleitung in
02_Einrichtung, Schritt 8):**

- **Eine Aktie:** Einzelansicht → „Kurs aktuell“ → **Jetzt aktualisieren** – aktueller Kurs und Tagesverlauf, meist nach 15–30 Sekunden.
- **Merkliste:** Merkliste → **Jetzt aktualisieren** – die ersten zehn Zeilen kommen zuerst, die übrigen kurz danach.
- **Depot:** Musterdepots → Depot wählen → „Kurse dieses Depots aktuell“ → **Jetzt aktualisieren**.
- **Alles:** ☰ → Jetzt aktualisieren → **Alles jetzt aktualisieren** – rechnet alle Ranglisten neu (2–3 Minuten).
- Unter dem Knopf steht der Fortschritt: wartet auf GitHub → Kurse werden abgerufen → Teil 1 angekommen → fertig.
- **Automatisch:** Neue Stände erscheinen beim nächsten Seitenwechsel von selbst; mit Zugang holt die App außerdem alle 15
  Minuten die Kurse der sichtbaren Aktien und der Merkliste (nur bei geöffneter App und während Börsen handeln; einstellbar).

Jeder aktualisierte Kurs zeigt **Kurszeit** (wann der Kurs an der Börse entstand), **Abrufzeit** und die **bekannte
Verzögerung** der Börse (z. B. Xetra 15 Minuten). „aktuell“ steht nur dort, wo das gerade stimmt – öffnest du die App
später wieder, steht bei demselben Kurs „nicht aktuell (Kurs 2 Std. alt)“.

**Ohne Zugang – wie bisher über GitHub:** auf der Startseite **„Kurse jetzt aktualisieren“** oder ☰ → **Jetzt aktualisieren**.

1. **„Jetzt aktualisieren“** antippen – GitHub öffnet „Täglicher Lauf“ (beim ersten Mal anmelden).
2. **„Run workflow“** antippen und den grünen Knopf **„Run workflow“** bestätigen. Nichts ändern: **„Alles aktualisieren“** ist voreingestellt (ab 1.9.1).
3. Zurück in die App. Sie schaut alle 15 Sekunden nach und meldet nach etwa 2–3 Minuten „Zwischenstand fertig“ (der offizielle Lauf mit allen Prüfungen dauert länger) bzw. „Aktualisierung fertig“ – oder „Lauf beendet – keine neuen Kurse“ mit Grund.

Ein Lauf rechnet dann alles neu: aktuelle Kurse (während des Handels als **Zwischenstand**, etwa 15–20 Minuten verzögert), alle Ranglisten 1–90 Tage, Bericht 1–30, Top-10-Listen, Häufigkeit und Musterdepots. Gibt es neue Schlusskurse (nach Börsenschluss in New York, meist ab 23 Uhr), entsteht zuerst der offizielle Stand und danach automatisch Kennzahlen, Kursziele und Gesamtwertung. Unter „Weitere Möglichkeiten“ stehen die Sonderfälle (nur Kennzahlen und Kursziele, offiziellen Stand neu rechnen).

**Zwischenstand lesen:** Oben steht „Zwischenstand 13.10. 12:15“ statt „Kursstand“, darunter ein Hinweis, welche Börsen noch keinen Kurs von heute haben (z. B. USA vor 15:30 Uhr). Deren Aktien zählen ab 1.13 mit dem letzten Schlusskurs und stehen trotzdem in allen Ranglisten und in den Top 3 – in der Zeile steht dann „Schlusskurs 13.10.“. Der Knopf „Schlusskurse 13.10.“ im Hinweis oben (auf der Startseite auch „Schlusskurse 13.10. anzeigen“) wechselt zum Stand mit den letzten Schlusskursen aller Börsen, „Anzeigen“ im Hinweis „Zwischenstand vom … verfügbar“ zurück. Am nächsten Morgen ersetzt der tägliche Lauf den Zwischenstand.

Neue Schlusskurse gibt es einmal je Börsentag, frühestens etwa eine Stunde nach Handelsschluss in New York (meist gegen 23 Uhr). Die Seite nennt den genauen Zeitpunkt („Neue Schlusskurse für Dienstag … gibt es heute ab 23:00 Uhr“). Ein Lauf vorher bringt keinen neuen Kursstand, übernimmt aber nachgelieferte Kurse. Gestartet wird über GitHub, weil die App absichtlich keinen Zugangsschlüssel enthält. Läuft schon ein Lauf, wartet ein zweiter Start, bis der erste fertig ist.

**Offline:** Einmal geladene Ansichten bleiben ohne Netz lesbar; die App sagt dann „Offline – gespeicherter Stand“ und nennt das Datum. Kommt ein neuer Datenstand, erscheint „Neuer Datenstand verfügbar“ – die aktuelle Liste bleibt, bis du wechselst.

## 7. Watchlist

Stern antippen merkt eine Aktie. Die Watchlist zeigt den Platz in der gesamten Rangliste und auf Wunsch eine Rangfolge nur innerhalb der Watchlist (deutlich als Untergruppe gekennzeichnet). **ISINs importieren und exportieren:** ISINs einfügen (eine je Zeile oder mit Komma) → „In die Watchlist übernehmen“; doppelte werden zusammengeführt, ungültige (falsche Prüfziffer) genannt, Namen oder Ticker nie zugeordnet. „ISIN-Liste exportieren“ bzw. „Mit Namen als CSV“ sichern die Liste. Sie liegt nur auf diesem Handy (Sicherung auch unter ☰ → Einstellungen → „Als Datei sichern“) und hat nichts mit der Watchlist oder dem Depot bei Trade Republic zu tun.

## 8. Was die App nicht tut

Keine Anlageberatung und keine Prognose (die Umschichtungs-Regel zeigt nur, was eine feste Rechenregel täte), keine Live-Kurse in Echtzeit (Tagesschlusskurse; auf Wunsch ein Zwischenstand mit verzögerten Kursen), keine Orders, kein Zugriff auf ein Depot, keine Anmeldung bei Trade Republic. Dass eine Aktie in der TR-Liste steht, heißt nicht, dass sie im eigenen Konto jederzeit handelbar ist.

## 9. Nach der Installation kurz prüfen (5 Minuten)

Diese Prüfung auf dem echten Gerät steht noch aus (09_Bekannte_Luecken). Bitte einmal durchgehen und Auffälliges notieren:

1. App vom Startbildschirm öffnen: Sie startet ohne Browserleiste, oben steht „Kursstand“ mit Datum – und **kein** DEMO-Hinweis.
2. Passphrase eingeben, App schließen und wieder öffnen: Sie bleibt entsperrt.
3. **Rendite**: 90 Zeilen, jede mit vollem Namen, ISIN und Prozentwert; eine ISIN antippen und kopieren.
4. **Ranking**: die Tasten 7, 30 und 90 Tage antippen, im Feld „Freier Zeitraum“ 37 eingeben, Gewichtung 60/40 und 50/50 wählen; eine Aktie öffnen.
5. Im Kurschart mit einem Finger über den Verlauf streichen (Tageskurs erscheint) und mit zwei Fingern zoomen; mit der Zurück-Geste zur Liste zurück.
6. **Raster**: „Mehrere Zeiträume“ und „Gemeinsam“ antippen. Rendite → **Sieger**: zehn Zeilen, Gewichtung 50/50 wählen, eine Zelle antippen.
7. Flugmodus einschalten, App öffnen: „Offline – gespeicherter Stand“ mit Datum.
8. ☰ → Datenstand & Betrieb: „Wie aktuell sind die Daten?“ nennt den Kursstand und wann neue Schlusskurse kommen (ab 1.17 mit Nachtlauf); darunter letzter Lauf und Abdeckung.
9. Die Schrift einmal größer stellen (in den Einstellungen des Handys oder in Chrome unter den Bedienungshilfen) und Start, Ranking und Matrix ansehen: nichts abgeschnitten, keine Seite seitlich verschiebbar. Unter **Aktien** ins Suchfeld tippen: Die Tastatur verdeckt das Feld nicht.

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
