# Änderungsprotokoll

Format: Version, Datum, Änderung, Begründung. Methodenänderungen (Fensterdefinition, Mindestbeobachtungen, Bereinigung, Perzentile, Gleichstandsregeln) erhöhen zusätzlich `methode_version` in `config/methode.yaml`. Veröffentlichte Datenstände tragen ihre Versionen und werden nie nachträglich verändert.

## 1.6.0 – 14.10.2026 (Potenzial: Signale kurz- und langfristig, Kursziele, Prognose, neue Struktur)

Dein Auftrag vom 14.10. (06:33–07:11 Uhr): Potenzial und Kursziel je Aktie wie in der TR-App, mehrere Quellen, Durchschnitt, Ampel, Prognose, Kursverlauf mit Zeiträumen, Ranking der Aktien mit dem besten Potenzial direkt am Anfang der Startseite, Stimmung der Community als Grafik, kurzfristige (Daytrader) und langfristige Sicht, Erklärungen zu allen Angaben, einfache und effiziente Struktur, jederzeit aktualisierbar.

**Versionen:** Software 1.6.0 · Signale `signale-v1` (neu) · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| **Zwei Urteile je Aktie mit Ampel:** *kurzfristig* aus relativem Volumen, Schwung (20 Tage im Verhältnis zur üblichen Schwankung), Steigetagen und Serie, Trendlage (20-/50-Tage-Linie), Ausbruch (20-Tage-Hoch), RSI, Nachrichten und Community; *langfristig* aus Kursziel (erwartete Steigerung, Anteil „Kaufen“, Zahl der Analysten), Bewertung, Wachstum und Finanzen, langfristigem Trend und Richtung der Analystenurteile. Jedes Signal 0–100 Punkte mit Satz, feste Ampelregeln, fehlende Daten werden nie geschätzt | „Diese Aktie hat Potenzial, weil …“ – nachvollziehbar statt Blackbox |
| **Trefferquote der Vergangenheit:** Der technische Teil des kurzfristigen Urteils wird für jede Aktie und jeden vergangenen Tag gleich berechnet; gezählt wird, wie oft der Kurs 5 bzw. 20 Handelstage später höher stand – je Punktebereich und für alle Aktien zum Vergleich | „Mit Wahrscheinlichkeiten arbeiten“ – eine gemessene Häufigkeit statt einer erfundenen Prognose |
| **Prognose-Grafik:** Kursverlauf und 12 Monate voraus – Ø Kursziel, Spanne vom tiefsten zum höchsten Ziel und die übliche Schwankung der Aktie (2 von 3 Fällen); dazu die Gewinn- und Umsatzprognosen der Analysten | Langfristige Sicht „gibt Sicherheit“, wenn es kurzfristig nicht klappt – mit ehrlicher Streuung |
| **Kursziele aus mehreren Quellen:** Yahoo-Konsens (weltweit), bei US-Aktien zusätzlich Nasdaq-Konsens und der Ø der Einzelziele der Häuser (90 Tage); Ø Kursziel der App = Mittel der Quellen. Kursziele werden ab heute täglich gespeichert (Grundlage für eine spätere Trefferquote der Kursziele) | Das TR-Kursziel selbst steht nur in der TR-App nach Login und wird nicht abgerufen |
| **Startseite beginnt mit „Kandidaten mit Potenzial“** (Beides stark · Kurzfristig · Langfristig · Kursziel), neue Ansicht **Potenzial** mit Filtern (Analysten, Branche, nur grün, Gruppe B) | Kandidaten schnell finden, ohne zu suchen |
| **Einzelansicht** mit Reitern Überblick (Urteil, Prognose, Kursverlauf **1W/1M/3M/6M/1J/Max**, Signale), Analysten (Kursziele je Quelle, Kaufen/Halten/Verkaufen über 4 Monate, Urteile der Häuser, Bewertung, Nachrichten, **Community-Grafik**), Kennzahlen (mit Erklärung je Zeile), Rendite 1–90 | Alles zu einer Aktie an einer Stelle |
| **Neue Struktur:** unten Start · Rendite · Potenzial · Aktien · Analyse; Unterreiter für Rendite (Rendite 1–90, Gleichmäßig + Rendite, Sieger) und Aktien (Alle, Watchlist); Analyse-Werkzeuge mit je einem Satz, wofür sie gut sind; ⓘ-Erklärungen an Signalen, Kennzahlen und Abschnitten | „Logisch aufgebaut, einfach zu verstehen, effizient“ |
| **Kennzahlen-Job** im täglichen Lauf *nach* der Bereitstellung der Kurse (neue Ranglisten warten nicht), rotierend mit Zeitbudget (20 Min., bei der Erstbefüllung 45 Min.); Workflow-Eingabe **„Nur Kennzahlen, Kursziele und Signale aktualisieren“** für jederzeit | Jederzeit aktualisierbar, ohne den täglichen Lauf zu verlängern |
| Kurshistorie im Zustand auf gut ein Jahr verlängert (Erstimport 400 statt 200 Tage, Aufbewahrung 430 Tage; bestehende Historien werden mit dem täglichen Abruf verlängert, höchstens 4.000 je Lauf) | Kursverlauf 1J, 200-Tage-Linie |

## 1.5.4 – 14.10.2026 (Schlusskurs aus der Kursmeldung, wenn die Tageskerze noch leer ist)

Die Live-Prüfung um 06:41 Uhr zeigte erneut: Yahoo legt die Tageskerze vom 13.10. für Xetra, Frankfurt, Paris, Zürich, London, Madrid, Brüssel, Kopenhagen, Helsinki, Oslo und Prag an, **aber ohne Schlusskurs** – wie schon am 12.10., als die Kurse erst am Abend des Folgetags kamen. Der letzte gemeldete Kurs derselben Antwort (`regularMarketPrice`, z. B. SAP um 17:39 Uhr) ist dagegen vorhanden.

**Versionen:** Software 1.5.4 · Rechenregeln unverändert (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| Fehlt nach Börsenschluss der Schlusskurs der Tageskerze, gilt der **letzte gemeldete Kurs dieser Sitzung** aus derselben Antwort – nur wenn die Sitzung laut Börsenkalender abgeschlossen ist (Schluss + 60 Minuten), die Meldung zu dieser Sitzung gehört und keine spätere Sitzung mit Kurs vorliegt. Tageshoch, -tief und Umsatz kommen ebenfalls aus der Meldung | Ohne Absicherung warten die Morgenläufe auf Kurse, die Yahoo erst einen Tag später nachliefert; der planmäßige Stand käme dann höchstens als Teilstand |
| Solche Kurse sind **gekennzeichnet** (Einzelansicht: Hinweis „Schlusskurs aus der letzten Kursmeldung …“; Datenstand & Betrieb: Anzahl der Aktien) und werden **automatisch ersetzt**, sobald die Tageskerze kommt (jeder Lauf fragt die letzten 10 Tage erneut ab) – ohne neue Kursrevision. Eine Kursmeldung überschreibt nie eine vorhandene Tageskerze | Nachvollziehbar statt stillschweigend; der endgültige Schlusskurs gewinnt immer |
| Live-Prüfung „Datenquellen prüfen“: neuer Vergleich Kursmeldung ↔ Tageskerze ↔ letzte Stundenkerze (Abweichung in Basispunkten), aktuelle Kurse in Sammelabfragen, Kursziele der Analysten und weitere Quellen (nur Verfügbarkeit, keine Werte im öffentlichen Protokoll) | Grundlage für die Absicherung und für die nächsten Funktionen (Potenzial, Zwischenstand) |

## 1.5.3 – 14.10.2026 (Markierter Zeitraum erklärt sich selbst)

**Versionen:** Software 1.5.3 · sonst wie 1.5.2 (nur die App ändert sich, keine Rechenregeln).

| Änderung | Begründung |
|---|---|
| Der Zeitraum, zu dem „Zu Zeitraum springen“ führt, trägt unter der gelben Zahl jetzt das Wort **„gewählt“** – in „Rendite 1–90“ sowie in Matrix und Liste; für Bildschirmleser als aktueller Eintrag gekennzeichnet (`aria-current`) | Deine Frage am 14.10.: „Warum ist das gelb?“ – die Markierung war ohne Erklärung nicht zu verstehen |

## 1.5.2 – 13.10.2026 (Börsenplatz-Abgleich v3, erster vollständiger Datenstand)

Um 21:07 Uhr hat ein Lauf mit 1.5.1 festgestellt, dass Yahoo die Schlusskurse vom 12.10. inzwischen nachgeliefert hat; um 21:50 Uhr war der **erste vollständige Datenstand** online (`2026-10-12_9820e6d9`, alle Börsen mit Stichtagskursen, Xetra 433 von 439, London 695 von 713, Hongkong 734 von 735, USA 3.623 von 3.628). Dabei zeigte sich: Auch mit vollständigen Kursen waren nach `boersenplatz-v2` 75 von 102 geprüften Spitzenaktien in 3.080 von 8.492 Zeiträumen „auffällig“ – die feste 10-%-Schwelle passt nicht zu den stark schwankenden Werten, die oben in den Rendite-Ranglisten stehen.

**Versionen:** Software 1.5.2 · Börsenplatz-Abgleich `boersenplatz-v3` (vorher v2) · übrige wie 1.5.1 (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| **Börsenplatz-Abgleich `boersenplatz-v3`:** verglichen werden nur Schlusskurse mit Umsatz am zweiten Platz (sonst „kein Umsatz am Vergleichsplatz“); die Schwelle wächst mit der üblichen Tagesschwankung der Aktie (robuste Standardabweichung der letzten 20 Tagesrenditen, 3-fach, bei der Wertentwicklung × √2), mindestens 10 % wie bisher, Abweichungen ab Faktor 2 immer auffällig | Schlusszeiten der Börsenplätze liegen Stunden auseinander (Xetra 17:30 Uhr, New York 22:00 Uhr); bei einer Aktie mit 8 % üblicher Tagesbewegung erklärt das allein Abweichungen weit über 10 %. Kurse ohne Umsatz sind nur fortgeschrieben. Rendite und Rang ändern sich nicht |
| Jeder Lauf weist aus, was nach der festen 10-%-Regel auffällig gewesen wäre und warum es das nicht mehr ist (ohne Umsatz am Vergleichsplatz, innerhalb der üblichen Schwankung, weiter auffällig) – im Kurzbericht des Laufs und unter ☰ → Datenstand & Betrieb (`venue_check.auswertung`) | Die Wirkung der neuen Regel bleibt nachprüfbar statt nur behauptet |
| Einzelansicht nennt die Schwelle der Aktie und ihre übliche Tagesschwankung („Schwelle 40 % (übliche Tagesschwankung dieser Aktie 8,0 %)“); „So wird gerechnet“ und „Datenstand & Betrieb“ erklären die Regel je nach Version des Datenstands | Ältere Stände (v1, v2) behalten ihren Text |
| Neuer Workflow **App mit echten Daten prüfen** (nur von Hand): öffnet die veröffentlichte App im Format des S25+, entsperrt sie mit dem Secret, ruft alle Ansichten und eine Einzelansicht auf und meldet Fehler, Ladezeiten, Konsolenfehler und fehlgeschlagene Abrufe – ohne Kurse oder Namen im öffentlichen Protokoll | Die echten Daten sind verschlüsselt und von der Entwicklungsumgebung aus nicht lesbar; so ist die fertige App mit echten Daten geprüft, ohne dass jemand die Passphrase sieht |
| **Ergebnis mit echten Daten** (Lauf um 22:13 Uhr, Stand `2026-10-12_c3806c24`, vollständig): nach der festen 10-%-Regel wären 3.080 Zeiträume (75 Aktien) auffällig gewesen – davon beruhten **2.934 auf Kursen ohne Umsatz am Vergleichsplatz**, 95 lagen innerhalb der üblichen Schwankung, **51 Zeiträume (8 Aktien) bleiben auffällig**. 1.305 Zeiträume sind unauffällig, 328 ohne Vergleichskurse | Bestätigt die Ursache: fortgeschriebene Kurse ohne Handel am zweiten Platz, nicht Fehler der Referenzkurse |

## 1.5.1 – 13.10.2026 (Fehlende Börsentage beim Kursanbieter, erster Datenstand)

Yahoo liefert für Montag, 12.10.2026, in Europa und Asien keine Schlusskurse (am 13.10. um 19:05 Uhr erneut geprüft). Nach der 98-%-Regel aus dem ersten Auftrag wären europäische und asiatische Aktien dadurch bis etwa Weihnachten aus allen Zeiträumen von 2 bis 68 Tagen herausgefallen. Deine Entscheidung vom 13.10.2026: „wie Ausgangsmodell“.

**Versionen:** Software 1.5.1 · Methode `tr-methode-1.8.0` (vorher 1.7.0) · Börsenplatz-Abgleich `boersenplatz-v2` (vorher v1) · übrige wie 1.5.0.

| Änderung | Begründung |
|---|---|
| **Methode 1.8.0:** Ein Zeitraum bleibt bewertbar, wenn höchstens 20 % der erwarteten Börsentage ohne Kurs sind; ein einzelner fehlender Tag ist immer erlaubt (vorher höchstens 2 %). Nichts wird aufgefüllt; Start- und Endkurs bleiben Pflicht; Volumenregeln unverändert (80 % der Kurstage, Volumen an jeder Beobachtung, Randvolumen, Split im Fenster) | Ein Datenloch des Kursanbieters soll Aktien nicht wochenlang aus den Ranglisten nehmen; das Ausgangsmodell kennt keine 98-%-Regel |
| Methodenvergleich jetzt allgemein: jeder Lauf rechnet nach den Zulassungsregeln der Vorversion (`vorherige_regeln` in `config/methode.yaml`) und nennt weggefallene Paare nach ihrem neuen und hinzugekommene nach ihrem alten Status; die Texte der Änderungen stehen in der Konfiguration | Transparenter Vergleich für jeden künftigen Methodenwechsel, nicht nur 1.6.0 → 1.7.0 |
| Statustexte 12 und 14 nennen die Schwellen der jeweiligen Methodenversion | Die App zeigt nur Texte aus dem Datenstand |
| **Teilstand verständlich:** Startseite nennt die Börsen ohne Stichtagskurse mit Namen („London, Xetra, …“) und sagt, dass deren Aktien wegen fehlender Daten fehlen; fehlen mehr Börsen, als geliefert haben, nennt sie stattdessen die enthaltenen („Enthalten sind nur Aktien von 3 der 31 Börsen mit Handel am Stichtag: Australien, Neuseeland und USA“). „Datenstand & Betrieb“ zählt Börsen und Aktien mit Stichtagskurs und listet alle fehlenden Börsen | Der erste echte Stand ist ein Teilstand mit 28 fehlenden Börsen – eine Liste mit 28 Namen auf der Startseite wäre unübersichtlich |
| **Erster echter Datenstand** zum Stichtag 12.10.2026 als gekennzeichneter Teilstand: Lauf mit „erzwingen“ von 19:11 bis 20:37 Uhr (noch Software 1.5.0, Methode 1.7.0), Stand `2026-10-12_5092bae0`. Schlusskurse vom 12.10.: USA 3.623 von 3.628, Australien 525 von 525, Neuseeland 18 von 18; Europa und Asien fast keine (Xetra 17 von 439, London 5 von 713) | Du wolltest die App sofort nutzen; ein gekennzeichneter Teilbericht ist laut Auftrag erlaubt |
| **Börsenplatz-Abgleich `boersenplatz-v2`:** Hatte der zweite Börsenplatz am Start- oder Enddatum eine Sitzung (Börsenkalender), zählt nur der Schlusskurs genau dieses Tages; fehlt er beim Kursanbieter, heißt es „Vergleichskurse fehlen“. An Feiertagen dort weiter die letzte Sitzung davor (höchstens 4 Tage). Vorher galt der letzte gelieferte Kurs bis 4 Tage vorher | Im ersten echten Stand fehlten die Xetra-Kurse vom 12.10.; der Abgleich verglich deshalb den Freitagskurs in Deutschland mit dem Montagskurs in den USA. Jede Aktie mit mehr als 10 % Bewegung am Montag erschien so als auffällig, auch ohne Kursfehler (64 von 89 geprüften Aktien gekennzeichnet) |
| „Datenstand & Betrieb“: Methodenwechsel nennt neu **und** nicht mehr bewertete Paare (bisher nur weggefallene – ab 1.8.0 kommen vor allem Paare hinzu); Abgleich mit zweitem Börsenplatz zählt die tatsächlich verglichenen Zeiträume und nennt die übrigen mit Grund („Vergleichskurse fehlen: …“); Börsen mit Namen statt Kalendercodes | Ohne diese Zählung hätte „0 auffällig“ im Teilstand vom 12.10. nach einem geprüften Stand ausgesehen, obwohl mangels Xetra-Kursen kaum verglichen werden konnte |
| Ein Fehler im Börsenplatz-Abgleich verhindert die Veröffentlichung nicht mehr: Der Stand erscheint ohne Abgleich und ohne Kennzeichen, mit Hinweis (`venue_check.abgebrochen`); ein nicht lesbarer Börsenkalender des zweiten Platzes macht nur die betroffenen Aktien „nicht geprüft“ | Der Abgleich ist nur ein Hinweis; vorher hätte eine Ausnahme dort den ganzen Tageslauf scheitern lassen |
| Teilstand am letzten geplanten Versuch (09:00): jetzt, wenn mindestens 75 % der erwarteten **Aktien** einen Schlusskurs am Stichtag haben (vorher 90 % der **Börsen** – Tallinn mit 15 Aktien zählte so viel wie Hongkong mit 735) | Fehlt z. B. nur Hongkong, soll der Stand mit Europa und USA erscheinen statt gar keiner |

## 1.5.0 – 13.10.2026 (Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“)

Nach deinem Programmierauftrag mit Auftragsstand 13.10.2026. Vieles bestand schon (90 Zeiträume, elf Gewichtungen, Gruppen A und B, Charts, Raster, täglicher Lauf); dieser Stand übernimmt die dokumentierten Regeln des Ausgangsmodells als neue Methodenversion und ergänzt die verlangten Ansichten. Die Dateien `TR_Rankings_1_bis_90_Tage_11_Gewichtungen.html` und `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` lagen nicht vor – die Reproduktion des historischen Prüffalls ist deshalb **nicht** durchgeführt (09_Bekannte_Luecken). Werte des Prüffalls sind nirgends fest eingebaut.

**Versionen:** Software 1.5.0 · Methode `tr-methode-1.7.0` (vorher 1.6.0) · Kennzahlen `kennzahlen-v2` · Ranking `ranking-11w-v2` · Häufigkeit `frequency-v2` · Ausgangsmodell `TR-90D-11W-two-universes-v1.1` (dokumentierte Regeln übernommen) · unverändert: Gruppen `gruppen-v1`, Umsatz `umsatz-v1`, Regel `rotation-v1`, Schnittstelle `static-api-v1` (nur neue Felder), Datenbank (keine Migration).

| Änderung | Begründung |
|---|---|
| **Regeln des Ausgangsmodells** (Methode 1.7.0): Tagesvolumen an jeder Beobachtung gemeldet (endlich, nicht negativ), positives Volumen an Start- und Endbeobachtung, gemeldeter Split bzw. Zusammenlegung im Fenster zurückgehalten (Freigabe nur mit dokumentierter Prüfung); Status 13 und 14 mit erweiterten Texten | Auftrag Abschnitt 5: Formeln des Ausgangsmodells übernehmen, nichts stillschweigend ändern |
| Gleichstand für alle Gewichtungen: Score, dann Kursrendite, dann ISIN (`ranking-11w-v2`; vorher zusätzlich R² bzw. Steigung und Rauschen) | Auftrag Abschnitt 7 |
| **Methodenvergleich in jedem Lauf**: dieselben Kurse zusätzlich nach den Regeln von 1.6.0 gerechnet; Manifest `method_comparison` mit Paaren vorher/jetzt, Wegfall je Grund und geänderten Spitzenplätzen samt Beispielen; sichtbar unter ☰ → Datenstand & Betrieb und „So wird gerechnet“ | „Ein fachlicher Fehler ist transparent mit einer neuen Version und einem Vergleich zum bisherigen Ergebnis zu beheben“ |
| Neue Kennzahl **positive Schlusskursvergleiche** je Aktie und Fenster (`m.up`, `kennzahlen-v2`); Spitzenreiter der Übersicht tragen die Zahl ihrer Schlusskurse (`n`) | Details der Einzelrangliste und der Siegerübersicht laut Auftrag |
| **Identische Kursfenster exakt**: gleicher Bestand aus ISIN und tatsächlichem Startdatum je Gruppe und Vergleichsmenge (`same_set`, `frequency-v2`) statt Näherung über die Startsitzung je Börsenkalender | Auftrag Abschnitt 8: ein Gleichstand nur beim Gewinner reicht nicht |
| **Feste Schnellwahl 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Tage** (große Tasten, aktive markiert) plus Feld „Freier Zeitraum 1–90 Tage“ und Lineal – auf Start, Ranking, Kurschart, Chart-Raster, Gewichtungsvergleich und Abdeckung; Sprungtasten in Rendite und Matrix. „30 Tage“ bleibt 30 Kalendertage | Verbindliche Ergänzung des Auftrags |
| Neue Ansicht **Sieger nach Zeitraum** (☰, Kurzfassung auf der Startseite): zehn Zeilen, Gruppe A und B nebeneinander, Gewichtung 0/100 … 100/0, Beginn/Ende/Schlusskurse/Referenzmarkt per Antippen, „Gleichmäßigkeit nicht berechenbar“ bei 7 und 14 Tagen, eigene Zählung über genau diese zehn Zeiträume | Auftrag Abschnitt 9 |
| **Startseite** neu: Kursstichtag, Berechnungszeit, Tageslauf, Abdeckung „berechnet / identifiziert“ getrennt von den TR-Einträgen; Auswahl Gruppe, Zeitraum und Gewichtung (gemerkt, Erststandard 90 Tage und 60/40, alle elf Stufen direkt antippbar); erste fünf; Einstiege „Höchste Rendite“, „Gleichmäßigkeit + Rendite“, „Häufigste Aktien“, „Kursvergleich“ | Auftrag Abschnitt 9, Startansicht |
| **Rendite**: Standard alle 90 Zeiträume mit Sieger A und B nebeneinander, Top 10 beider Gruppen aufklappbar | Ansicht „Höchste Rendite“ |
| **Ranking**: Zeile mit Rangscore, Kursrendite, R², Referenzschluss mit Währung und Ø Tagesumsatz; „Details“ mit Ticker, Referenzbörse, Anfang, Schlusskursen, Steigung, Rauschen, größtem Rückgang, positiven Schlusskursvergleichen, Datenquelle, Datenalter und Prüfstatus; Export CSV und JSON | Einzelrangliste laut Auftrag |
| **Matrix** 1–90 × 11 je Gruppe (Bereiche 1–30, 31–60, 61–90; feste Kopfzeile und Zeitraumspalte; Sprung zu einem Zeitraum); Wiederholungszeichen „↻ N“; Export CSV und JSON | Auftrag: Matrix mit Zeilen 1–90 |
| **Häufigste Aktien** (Reiter „Häufig“) neu: Gruppe A, B oder beide (Beiträge getrennt), alle Gewichtungen, nur mit Gleichmäßigkeitsanteil oder eine; alle Zeiträume, 1–30, 31–60, 61–90 oder frei; identische Fenster wahlweise einmal; Sortierung „Gewinnt am häufigsten“ oder „Meiste Top-10-Nennungen“; Nenner „berechenbare Kombinationen“; Export CSV und JSON mit allen Filtern. Die bisherige Ansicht bleibt als „Erweiterte Zählung“ | Auftrag Abschnitt 8 |
| **Watchlist**: ISINs einfügen (Prüfziffer, Doppelte zusammengeführt, Ungültige genannt, keine Zuordnung über Namen) und als ISIN-Liste oder CSV exportieren | Auftrag: Favoriten nach ISIN importieren/exportieren |
| **Datenstand & Betrieb**: Ausgangsmodell, Methodenwechsel, Berechnungsmetadaten als JSON, druckbare Zusammenfassung; frühere Stände mit Methodenversion und „eingeschränkt vergleichbar“ bei anderer Methode | Exporte und Nachvollziehbarkeit (Auftrag Abschnitte 11 und 13) |
| Täglicher Lauf um **07:00 Europe/Berlin** (Wiederholungen 07:15, 07:45, 09:00; vorher 06:00) | Auftrag: konfigurierbarer Erststandard 07:00 |
| Einstellungen v2: frühere Einstellungen werden übernommen, Zeitraum und Gewichtung einmal auf 90 Tage und 60/40 gesetzt; Gruppe und Sortierung der Häufigkeit werden gemerkt | „Letzte Auswahl lokal merken; anfänglich 90 Tage und 60/40“ |
| Fehler behoben: Rückmeldung des ISIN-Imports verschwand beim ersten Import; Wahl „Frei“ in der Häufigkeit zeigte bei einer vorgegebenen Spanne keine Eingabefelder | gefunden durch die neuen Browser-Tests |
| Häufigkeitstabelle und Zählung der zehn Zeiträume passen ohne seitliches Blättern auf 360–412 px breite Bildschirme; Hover-Hervorhebungen nur noch bei Geräten mit Maus (auf dem Handy bleibt nach dem Antippen keine Hervorhebung „hängen“) | Sichtprüfung der Bildschirmfotos; „horizontales Scrollen nur dort, wo eine Matrix es erfordert“ |

## 1.4.1 – 13.10.2026 (Kürzel ohne Kursdaten)

Der erste echte Lauf fand für 1.735 Notierungen keine Kurse, weil das Kürzel aus der Identitätsquelle nicht zum Kursanbieter passte. Ranglisten und Formeln sind unverändert.

**Versionen:** Software 1.4.1 · Börsentabelle `boersen-v2` (vorher v1) · Datenbank-Migration 0006 · übrige unverändert.

| Änderung | Begründung |
|---|---|
| Börsentabelle `boersen-v2`: die OpenFIGI-Sammelcodes CN (Kanada) und GR (Deutschland) zeigen auf keine Börse mehr | Sie führten zu Yahoo-Kürzeln ohne Kurse (TSX-Venture-Aktien als „.TO“, Frankfurter Werte als „.DE“) |
| Migration 0006: Identitäten mit Referenz Toronto oder Xetra und ohne Kursdaten werden einmal neu geprüft; neue Tabelle `symbol_alternative` | Die neue Zuordnung greift sofort, nicht erst nach 45 Tagen |
| Kennt der Kursanbieter ein Kürzel nicht: andere Schreibweise (nordische Aktiengattungen „ADDT-B.ST“) und Suche nach der ISIN, nur an derselben Börse, mit Plausibilitätsprüfung (Typ, Zeitzone, Börsencode, Währung, Name ≥ 0,25); höchstens 300 Notierungen und 15 Minuten je Lauf, Wiederholung nach 30 Tagen | Kursdaten für richtig zugeordnete Aktien, ohne fremde Kurse einzumischen |
| Ein gefundenes Kürzel bleibt auch nach der nächsten Identitätsprüfung erhalten; Übernahmen im Protokoll, Zählung im Kurzbericht | Nachvollziehbar und stabil |

## 1.4.0 – 13.10.2026 (Gruppenvergleich A/B über 1–30 Tage)

Nach deinem Auftrag „Beide Aktiengruppen über 1–30 Tage vergleichen“ (13.10.2026). Vieles davon gab es schon (90 Zeiträume, elf Gewichtungen, Ranking 2 mit Umsatzfilter, Häufigkeiten, Charts mit „Start = 100“); neu ist die Gruppe B mit allen elf Gewichtungen und die Vergleichsansicht. Bestehende Formeln sind unverändert.

**Versionen:** Software 1.4.0 · Methode `tr-methode-1.6.0` (vorher 1.5.0; neue veröffentlichte Ranglisten) · neu: Gruppenvergleich `gruppen-v1` · unverändert: Kennzahlen `kennzahlen-v1`, Ranking `ranking-11w-v1`, Häufigkeit `frequency-v1`, Umsatz `umsatz-v1`, Schnittstelle `static-api-v1` (nur neue Felder).

| Änderung | Begründung |
|---|---|
| **Gruppe B** (Ø Tagesumsatz ≥ 10 Mio. USD über 20 Sitzungen) mit allen elf Gewichtungen für alle 90 Zeiträume: Vergleichsmengen V ∩ L und U ∩ L, Perzentile und Scores innerhalb der Gruppe (`group_b_ranking`); 0/100 nativ = Ranking 2 | Auftrag: getrennte Ranglisten je Gruppe, 2 × 30 × 11 = 660 je Kursstichtag (die App zeigt 1–30, wahlweise 31–90) |
| Neue Veröffentlichungsprüfung `gruppe_b_eigene_vergleichsmenge` (jetzt 15 Prüfungen): Mengen, alle Gewichtungen, 0/100 und 100/0 in der Reihenfolge der Gruppe A, Sortierregeln, Scores 0–100 | Gleiche Regeln für beide Gruppen, nachprüfbar |
| Datenvertrag (nur Ergänzungen): `orders.ul`, `ties.ul`, `counts.UL`, `m.a_rvl/a_gul/a_rul` je Fenster; `overview.v0l/ul`; `frequency.occ.ul`, `M.ul`, `server_reference_b`, `starts` (Startsitzung je Börsenkalender); `instruments.calendar`; Rangmatrix mit 24 Spalten; `liquid` im Nachweisarchiv | Die App rechnet Scores der Gruppe B bitgleich nach und zählt ohne zusätzliche Dateien |
| App: neue Hauptansicht **Matrix** (sechster Reiter): Reiter Gruppe A / Gruppe B; **Matrix** 1–30 × 11 mit fester Zeitraumspalte und seitlich verschiebbaren Gewichtungen, Zelle = Spitzenaktie mit Name, ISIN, Score, Kursrendite; „nicht berechenbar“ mit Grund; **Liste** (kompakt, je Gewichtung); **Häufigkeit** | Auftrag Punkt 4 und 5, auf dem S25+ bedienbar |
| Wiederkehrende Aktien: dieselbe ISIN trägt in beiden Gruppen und allen Ansichten dieselbe Farbe (acht häufigste) und „×Anzahl“; Antippen markiert alle Vorkommen und öffnet auf Wunsch Rangliste (mit Gruppe) und Kursverlauf | Auftrag: Farbe plus lesbares Zeichen, Identität nur über ISIN |
| Häufigkeitsranking je Gruppe: Platz 1, dann Top 3, Top 10, ISIN; Spalten Rang, Name, ISIN, Platz-1-, Top-3-, Top-10-Vorkommen, auswertbare Kombinationen; alle oder eine Gewichtung; A und B getrennt nebeneinander | Auftrag Punkt 5; die bisherige Häufigkeitsansicht mit ihren Regeln bleibt unverändert |
| Identische Kursfenster: „≡“ in Matrix und Liste; Schalter „Identische Kursfenster nur einmal zählen“ (Gruppe, Gewichtung, tatsächlicher Start und Ende) | Auftrag Punkt 6: Wochenend-Doppelungen sichtbar und wahlweise einmal gezählt |
| Ranking und Chart-Raster mit Aktiengruppe; Einzelansicht zeigt Rang und Score in Gruppe B | Antippen in der Matrix führt zur vollständigen Rangliste der Gruppe |
| Kopf der Matrix: Kursstichtag, Rechenzeit, berechnete und nicht berechenbare Ranglisten mit Grund, Feldgrößen | Auftrag Punkt 7: Datenabdeckung und fehlende Berechnungen sichtbar |

## 1.3.0 – 13.10.2026 (Umschichtungs-Regel: Tagesvorschlag und Rückblick)

Nach deiner Frage vom 13.10.2026 („Algorithmus … Wegen Umschichtung … Tipp geben, 10, 20 % oder so vom ganzen Kapital in die Aktie zu stecken oder einen Teil zu verkaufen und umzuschichten“) und deiner Auswahl: Simulator + Tagesvorschlag, monatlich mit 3-Monats-Trend, 5 Aktien je 20 %, nur Ø Umsatz ≥ 10 Mio. USD. Eine feste Rechenregel, keine Anlageberatung. Die Ranglisten bleiben unverändert.

**Versionen:** Software 1.3.0 · Methode `tr-methode-1.5.0` (vorher 1.4.0) · neu: Regel `rotation-v1` · übrige wie 1.2.0 (Schnittstelle `static-api-v1`, nur neue Dateien und Felder).

| Änderung | Begründung |
|---|---|
| **Umschichtungs-Regel** (`analytics/rotation.py`): Kandidaten mit Ø Tagesumsatz ≥ 10 Mio. USD (4 Wochen), Kursen an ≥ 90 % der Sitzungen und ohne Tagessprung über Faktor 3; Rangfolge nach Kursrendite über 13 (oder 4) Wochen; Entscheidung am ersten Freitag im Monat (oder jeden Freitag), **Ausführung zum Schlusskurs des nächsten Handelstags**; halten bis Platz 2 × N, freie Plätze an die Besten, je 1/N, Angleichen erst ab 5 Prozentpunkten | Deine Auswahl; der Haltepuffer verhindert ständiges Hin- und Herschichten, die Ausführung am nächsten Handelstag entspricht dem frühestmöglichen echten Handeln |
| **Kosten und Steuern** wie bei der Bank: 1 € + 0,1 % Spanne je Order, Abgeltungsteuer mit Soli (26,375 %) nach Verlusttopf und Sparerpauschbetrag (1.000 € je Jahr); Verluste erstatten Steuer desselben Jahres und geben verbrauchten Pauschbetrag frei, der Rest geht in den Verlusttopf | Ein Rückblick ohne Kosten und Steuern wäre zu schön; Vergleichslinie „ohne Kosten“ zeigt, was sie ausmachen |
| **Rückblick** bis 3 Jahre für alle 24 Varianten (5/10 Aktien, monatlich/wöchentlich, 13/4 Wochen, 5.000/10.000/25.000 €) mit Vergleich „alle Kandidaten zu gleichen Teilen“; Kennzahlen Endwert, Rendite, pro Jahr (ab 1 Jahr), größter Rückgang, Orders, Kosten, Steuern | Simulator: Varianten im selben Zeitraum vergleichbar |
| **Tagesvorschlag**: Regeldepot heute mit Anteilen und Beträgen, Änderungen mit Grund („nur noch Platz 12 – gehalten wird bis Platz 10“, „Platz 3, noch nicht im Regeldepot“), nach einem Prüftag als „beschlossen“ gekennzeichnet; Beträge auf einen eigenen Depotwert umrechenbar (nur auf dem Gerät gespeichert) | Deine Frage nach „10, 20 % vom Kapital“ und „einen Teil verkaufen“ |
| **Wochenwerte** (`analytics/weekly.py`, Tabellen `week_bar` und `long_history`, Migration `0005_wochenwerte.sql`): einmaliger Langabruf bis 3 Jahre für Aktien ab 2 Mio. USD Tagesumsatz (höchstens 6.000 bzw. 40 Minuten je Lauf, Rest im nächsten Lauf), jüngere Wochen in jedem Lauf aus den geprüften Tageskursen; nach einem Split zuerst neu laden | 150 Tage Tageskurse reichen für einen Rückblick nicht; Wochenwerte halten die Sicherung klein |
| **EZB-Kurshistorie** (ZIP mit der ganzen Reihe, einmalig, gespeichert für den Rückblickzeitraum) | Euro-Bewertung des Regeldepots in früheren Wochen |
| Neue Veröffentlichungsprüfung `umschichtung_regel_eingehalten` (jetzt 14 Prüfungen): alle Varianten, vollständige positive Verläufe, Käufe nur unter den ersten N, höchstens N Positionen, kein negatives Bargeld, Gebühren = Orders × 1 €, Orders nur an Prüftagen | Die Regel wird bei jedem Stand nachgeprüft |
| Datenvertrag (nur Ergänzungen): `rotation/index.bin`, `rotation/<Variante>.bin`, Manifest `rotation`, Version `rotation` | Die App lädt nur die gewählte Variante |
| App: neue Seite ☰ → **Umschichtungs-Regel** mit gelbem Depot-Lineal (Aufteilung heute und nach den Änderungen), Änderungsliste, Bestand, Rückblick-Diagramm (100 = Startkapital), Kennzahlen, Variantentabelle, Orders je Entscheidungstag, Rangfolge heute und „Was die Rechnung nicht zeigt“; Kurzfassung auf der Startseite; Methodik-Abschnitt | Auf dem S25+ bedienbar; Grenzen (nur heutige Aktien, vereinfachte Steuer) stehen auf derselben Seite |
| Idempotenzschlüssel enthält den Stand der Langhistorie | Ein später nachgeladener Rückblick ergibt bei einem erneuten Lauf einen neuen Stand statt „nichts Neues“ |

## 1.2.0 – 13.10.2026 (Abgleich mit einem zweiten Börsenplatz, Aktualisieren auf Wunsch)

Ergänzt den letzten offenen Punkt deines Auftrags vom 13.10.2026 („auffällige Kursabweichungen zwischen Börsenplätzen“ kennzeichnen) und deinen Wunsch, jederzeit selbst aktualisieren zu können. Noch kein echter Datenstand veröffentlicht; ältere Stände sind nicht betroffen.

**Versionen:** Software 1.2.0 · Methode `tr-methode-1.4.0` · neu: Abgleich `boersenplatz-v1` · übrige wie 1.1.0.

| Änderung | Begründung |
|---|---|
| **Abgleich mit einem zweiten Börsenplatz** für jede Aktie unter den ersten 10 Plätzen von Ranking 1 oder 2 (in allen ihren Zeiträumen): zweite Notierung derselben ISIN aus OpenFIGI (Xetra, dann Frankfurt, dann weitere; nie OTC, nie dieselbe Kursreihe), Schlusskurse vom selben Anbieter, Umrechnung in die Referenzwährung mit EZB-Kursen. Auffällig bei mehr als 10 % Abweichung der Wertentwicklung oder des Endkurses → Fensterhinweis 5 „Auffällige Kursabweichung zwischen Börsenplätzen“ | Auftrag: Kursabweichungen zwischen Börsenplätzen kennzeichnen. Nur ein Hinweis – Rendite und Rang bleiben die der Referenzbörse (Methodik: eine Referenznotierung je ISIN) |
| Schritt läuft erst, wenn veröffentlicht wird; Zeitbudget 15 Minuten, höchstens 600 Aktien; Drosselung oder Zeitbudget beenden ihn, übrige Aktien „nicht geprüft“; Wahl des Platzes 45 Tage gespeichert (Tabelle `venue_listing`, Migration `0004_boersenplatz.sql`) | Keine zusätzlichen Abrufe bei Läufen ohne Veröffentlichung; ein Ausfall darf keinen Datenstand verhindern |
| Neue Veröffentlichungsprüfung `boersenplatz_kennzeichen` (jetzt 13 Prüfungen) | Hinweis genau bei den auffälligen Vergleichen |
| Datenvertrag (nur Ergänzungen): `instruments.venue`, `windows/<h>.xv`, `xv` je Siegerzeile, Manifest `venue_check`, Codes `venue_status`/`venue_pair_status` | Anzeige ohne zusätzliche Dateien |
| App: Zeile „Vergleich mit Börse … : unauffällig / auffällige Abweichung“ bei den vorderen Plätzen, gelbes Kennzeichen „Börsenplatz-Abweichung“, Einzelansicht mit Börse, Symbol, Kursen, Rendite dort und Abweichungen, Abschnitt in „Datenstand & Betrieb“ und Methodik, CSV-Spalte „Zweiter Börsenplatz“ | Auftrag: Hinweise je Aktie sichtbar |
| DEMO: synthetischer zweiter Börsenplatz Frankfurt mit zwei bewusst abweichenden Testaktien | Tests ohne Netz |
| **Jetzt aktualisieren:** neue Seite (☰, Datenstand & Betrieb, Startseite ohne Datenstand) mit „Lauf auf GitHub starten“; danach liest die App `status.json` jede Minute und meldet „Aktualisierung fertig“ (mit „Neuen Stand anzeigen“), „Lauf beendet – keine neuen Kurse“ mit Grund oder nach drei Stunden „Noch kein Ergebnis“; Warten übersteht einen Neustart der App | Dein Wunsch: jederzeit aktualisieren. Gestartet wird mit deiner GitHub-Anmeldung, weil die App keinen Schlüssel enthalten darf |
| `status.json`: `naechster_kursstand` (nächster möglicher Kursstichtag und ab wann, gleiche Regel wie der Stichtag) und `aktualisieren` (Links auf GitHub, nur in GitHub Actions) | Die App sagt vor dem Start, ob ein Lauf jetzt neue Kurse bringen kann |
| Von Hand gestartete Läufe warten bei fehlenden Stichtagskursen nur weiter; über Teilstand oder Fehlschlag entscheidet allein der vierte **geplante** Versuch eines Stichtags (bisher zählten alle Läufe) | Mit „Jetzt aktualisieren“ wären die Wiederholungen sonst schnell aufgebraucht und ein zusätzlicher Start vor 23 Uhr hätte einen roten Lauf mit E-Mail ausgelöst |
| Kurzbericht: Zählungen (Identität, Kursabruf, Börsen ohne Kursdaten) vor den Beispielen; Beispiele ohne Stichtagskurs in einer Zeile | Im Lauf vom 13.10., 13:35 Uhr verdrängten 26 Beispielzeilen die neue Zeile „Keine Kursdaten je Börse“ aus dem von GitHub gekürzten Hinweis |
| Statusdateien werden mit Zeitstempel-Parameter gelesen; der Service Worker speichert sie unter festem Namen | Sonst zeigt GitHub Pages bis zu 10 Minuten alte Angaben, und der Offline-Speicher würde mit jeder Abfrage wachsen |

## 1.1.0 – 13.10.2026 (zwei Rendite-Ranglisten mit Umsatzfilter)

Erweiterung nach deinem Auftrag vom 13.10.2026. Es gab noch keinen veröffentlichten echten Datenstand; ältere Stände sind deshalb nicht betroffen. Stände ohne die neuen Felder (DEMO-Stände aus 1.0.0) zeigt die App weiter an und nennt den fehlenden Umsatzfilter.

**Versionen:** Software 1.1.0 · Methode `tr-methode-1.3.0` (vorher 1.2.0) · neu: Umsatz `umsatz-v1` · unverändert: Kennzahlen `kennzahlen-v1`, Ranking `ranking-11w-v1`, Häufigkeit `frequency-v1`, Schnittstelle `static-api-v1` (nur neue Felder, keine geänderten).

| Änderung | Begründung |
|---|---|
| **Ranking 1 „Höchste Kursrendite“**: alle Aktien mit veröffentlichter Kursrendite (Menge V), je Zeitraum 1–90 eine eigene Liste, sortiert nur nach der ungerundeten Kursrendite (0 % Gleichmäßigkeit / 100 % Kursrendite). Keine Mindestgrenzen für Kurs, Börsenwert oder Umsatz; die bisherigen Datenqualitätsprüfungen gelten weiter | Auftrag: reine Renditeliste über das ganze TR-Angebot |
| **Ranking 2 „Höchste Kursrendite – Ø Tagesumsatz mindestens 10 Mio. USD“**: dieselben Kurse, Zeiträume, Formel und Reihenfolge wie Ranking 1, nur Aktien mit bestimmtem Ø Tagesumsatz ≥ 10 Mio. USD (Menge V ∩ L). Der Umsatz ist Aufnahmefilter, kein Sortierkriterium | Auftrag |
| **Ø Tagesumsatz** je Aktie: Schlusskurs × gemeldetes Volumen je Sitzung über die letzten 20 abgeschlossenen Sitzungen der Referenzbörse (Börsenkalender), arithmetischer Mittelwert über die Sitzungen mit Daten; mindestens 16 Sitzungen mit positivem Volumen; fehlende Daten zählen nicht als null; Split innerhalb der 20 Sitzungen → nicht bestimmbar; Untereinheiten (Pence, Agorot, Cent) in Hauptwährung | Auftrag: Kapitalmaßnahmen dürfen nicht verzerren, keine Nullen für fehlende Daten |
| **Wechselkurse:** neuer Laufschritt „wechselkurse“ mit den EZB-Referenzkursen (90-Tage-Datei, ein Abruf je Lauf), gesichert in der neuen Tabelle `fx_rate` (Migration `0002_wechselkurse.sql`, läuft automatisch); bei Ausfall gespeicherte Kurse mit Warnung; je Sitzung der Kurs des Tages oder der letzte davor, höchstens 5 Tage alt. Quelle, Abrufzeit und Kurstage stehen im Manifest und in der App | Auftrag: Wechselkursquelle und Datenzeit dokumentieren; ohne Kurs keine Aufnahme in Ranking 2 |
| Kennzeichen „sehr niedriger Umsatz“ (Ø unter 1 Mio. USD) und „Umsatz nicht bestimmbar“ mit Grund (Hinweise 14 und 15) | Auftrag: sehr niedrigen Handelsumsatz deutlich kennzeichnen |
| Neuer Fensterhinweis **Übernahmemuster** (4): größter Tagesanstieg ≥ 15 %, danach mindestens 3 Sitzungen mit höchstens ±1 % Bewegung | Auftrag: Übernahmesprünge kennzeichnen; die Rendite bleibt veröffentlicht |
| Neue Veröffentlichungsprüfung `ranking2_teilmenge_gleiche_rendite` (jetzt 12 Prüfungen): Ranking 2 ist exakt Ranking 1 ohne die nicht aufgenommenen Aktien | Auftrag: beide Ranglisten mit demselben Stichtag und derselben Formel |
| Datenvertrag (nur Ergänzungen): Ø Umsatz je Instrument (`instruments.turnover`), Start- und Endkurs je Aktie und Zeitraum (`m.p0`, `m.p1`), Reihenfolge und Gleichstände von Ranking 2 (`orders.v0l`, `ties.v0l`, `counts.L`), Sieger von Ranking 2 (`winners_l`, `overall_max_l`), Häufigkeiten mit Universumsnamen (`occ.v0l`, `M.v0l`, `universe`), Manifest-Abschnitt `turnover`, Rangmatrix mit 13. Spalte `v0l` | Anzeige von Start-/Endkurs mit Datum und Umsatzbasis ohne zusätzliche Abrufe |
| App: Bereich „Rendite“ mit zwei getrennten Reitern; je Zeitraum zuerst der Sieger, Antippen → Top 10 → vollständige Liste; Standardansicht 1–7 Tage. Je Aktie Rang, Name, Ticker, ISIN, Kursrendite, Start- und Endkurs mit Datum, Börse und Währung, Ø Tagesumsatz mit Berechnungsbasis, Hinweise. Getrennte Zählungen: TR-Instrumente, geladene Kursreihen, bewertete Aktien je Rangliste | Auftrag: auf dem S25+ bedienbar, Teiluniversum nie als vollständige Prüfung |
| App: Einzelansicht mit Ø Tagesumsatz und beiden Rendite-Plätzen; Häufigkeit nennt ihr Universum, bei „Nur Rendite“ wahlweise mit Umsatzfilter (nie gemischt); Datenstand & Betrieb mit Umsatzfilter und Wechselkursstand; Methodik-Abschnitt „Zwei Rendite-Ranglisten“ | Auftrag: Häufigkeitslisten nennen Universum und Filter |
| Kurzbericht des Laufs nennt den Wechselkursschritt; DEMO-Quelle liefert synthetische Wechselkurse | Sichtbarkeit im Betrieb; Tests ohne Netz |
| Identitätsprüfung: Zeitzonen mit ganzjährig gleicher UTC-Verschiebung gelten als passend, wenn der Börsencode des Kursanbieters die Börse bestätigt; bisher deshalb „unklare“ Identitäten werden einmalig neu geprüft (Migration `0003_zeitzonen_neu_pruefen.sql`); Notierungen mit zunächst unklarer Identität werden für denselben Stichtag erneut abgerufen | Erster voller Lauf am 13.10.2026: 83 Wiener Aktien „unklar“, weil Yahoo für Wien „Europe/Amsterdam“ meldet (gleiche Uhrzeit, Börsencode VIE) |
| Kurzbericht des Laufs: Notierungen ohne Kursdaten und mit Abruffehlern je Börse mit Beispielen und Grund | Erster voller Lauf: 1.162 von 3.916 Notierungen ohne Daten – der Bericht zeigt jetzt, welche Börsen und Symbolformate betroffen sind |
| Leistungsmessung mit sechs Währungen und Wechselkursen | Größe eines Datenstands steigt von 74 auf 97 MB (gemessen, vor allem Start- und Endkurse) |

Noch nicht enthalten: Abgleich auffälliger Kursabweichungen zwischen Börsenplätzen – folgt in 1.2.0.

## 1.0.0 – 12.10.2026 (erste Fassung, noch kein produktiver Datenstand)

Umsetzung des Programmierauftrags v1.2. Bisher wurde kein echter Datenstand veröffentlicht; es gibt deshalb keine älteren Stände, die von einer Methodenänderung betroffen wären.

**Versionen:** Software 1.0.0 · Methode `tr-methode-1.2.0` · Kennzahlen `kennzahlen-v1` · Ranking `ranking-11w-v1` · Häufigkeit `frequency-v1` · Schnittstelle `static-api-v1` · Börsentabelle `boersen-v1`.

### Umfang

- Täglicher Serverlauf in GitHub Actions (06:00 Europe/Berlin, Wiederholungen 06:15, 06:45, 08:00) mit Checkpoints, Doppelstart-Schutz, verschlüsselter Sicherung im Release und Veröffentlichung auf GitHub Pages.
- Universum aus der öffentlichen TR-Instrumentenliste (Aktienabschnitt), Zuordnung jeder ISIN zu genau einer Referenznotierung, Börsenkalender je Referenzbörse, gemeinsamer Kursstichtag.
- Rechenkern: 90 Kalenderfenster, Qualitätsregeln (98 % Sitzungen, 80 % Volumen, 15 Kurse für Gleichmäßigkeit), Preis-OLS mit R², Kursrendite, MDD, alle elf Gewichtungen 0/100 bis 100/0 nativ und im gleichen Vergleichsfeld, Renditesieger 1–90, Häufigkeiten Top 1/3/10, Gesamtmaximum.
- Installierbare Web-App für das Galaxy S25+: Start, Rendite 1–90, Ranking, Gewichtungsvergleich, Häufigkeit mit Treffermatrix, Chart-Raster, Einzelcharts, Watchlist, Gesamtverzeichnis mit Status je Aktie, Datenstand & Betrieb, Methodik, Export (CSV, PNG), offline lesbar.

### Änderungen während der Entwicklung (vor der ersten Veröffentlichung)

| Änderung | Begründung |
|---|---|
| Neue Prüfregel: Kursbewegung über 10 % an einem Tag **ohne belegten Umsatz** am Fensterbeginn oder -ende hält das Fenster zurück (Status 13), freigebbar über `config/pruefungen.yaml` | Einzelne Geisterkurse ohne Handel könnten sonst ungeprüft zum Tagessieger werden (Auftrag: keine ungeprüften Spitzengewinner) |
| Residuen der OLS zentriert berechnet; nahezu konstante Reihen ergeben „R² nicht stabil bestimmbar“ statt eines Laufabbruchs | Numerische Stabilität; ein einzelner Sonderfall darf den Tageslauf nicht stoppen |
| Fensterlängen außerhalb 1–90 werden auch im Rechenkern abgewiesen | Auftrag T21 |
| Gesamtmaximum zählt dieselbe Aktie mit demselben tatsächlichen Zeitraum nicht als Gleichstand mit sich selbst; gleiche Zeiträume werden genannt | Keine Scheingleichstände (T95, T97) |
| Verwaiste Sperren aus einem abgebrochenen Runner werden beim nächsten Lauf freigegeben und als „abgebrochen“ protokolliert | Ein abgestürzter Lauf darf alle folgenden nicht blockieren |
| Kein `--soft-fail` im Workflow: ein fehlgeschlagener Lauf bleibt rot, der Status wird trotzdem veröffentlicht | GitHub soll per E-Mail benachrichtigen; der letzte gute Stand bleibt sichtbar |
| Bereitstellung auf GitHub Pages nur nach bestandener `verify-site`-Prüfung | Vorher hätten die mit `always()` laufenden Schritte die Website auch nach einer fehlgeschlagenen Prüfung (z. B. Geheimnis in einer Datei) hochgeladen |
| Datenbanksicherung wird lückenlos ausgetauscht (Zwischenname, löschen, umbenennen); `crypto.json` nur noch hochgeladen, wenn es fehlt | Vorher hätte ein Abbruch zwischen Löschen und Hochladen die einzige Sicherung gekostet |
| Angezeigte Stammdaten (Name, Ticker, Börse, Identität) gehören zum Idempotenzschlüssel; frühere Ticker und Symbole bleiben als Suchbegriffe erhalten | Ein Tickerwechsel am selben Stichtag ergibt eine neue Revision statt eines veralteten Tickers (T37, T50) |
| Aufbewahrung der Tageskurse im Zustand 250 statt 400 Tage | Die Rechnung braucht 150 Tage; kleinere Sicherung, schnellere Läufe |
| Diagramme: Pos1/Ende/Pfeiltasten scrollen die Seite nicht mehr mit; Zwei-Finger-Zoom auch dort, wo der Browser `touch-action` auf SVG-Elementen nicht beachtet | Bedienbarkeit auf Android und mit Tastatur (T77) |
| Kurzer Titel „Rendite 1–90“ in der App-Leiste | Langer Titel wurde neben Datum und Kennzeichen abgeschnitten |
| Workflows und Tests auf Python 3.13 vereinheitlicht | Dieselbe Version wie in den ausgeführten Tests |
| Lockdatei der App auf die öffentliche npm-Registry umgestellt | GitHub Actions erreicht nur die öffentliche Registry |
| Offene Datenbankverbindungen in `ci` und `restore-test` werden geschlossen | Ressourcenwarnungen in Tests; sauberes Beenden |
| Rückfallwert für `aufbewahrung.site_snapshots` im Code 5 statt 7 | Gleich dem dokumentierten und konfigurierten Wert |
| App-Build: Dateinamen aus dem Inhalt statt aus esbuilds `[hash]` | esbuilds Hash hängt vom Projektpfad ab; in GitHub Actions hätte die Prüfung „app/dist ist veraltet“ sonst immer angeschlagen |
| `.gitignore`: lokale Datenordner nur im Hauptverzeichnis ausgeschlossen | Das Muster `state/` hatte den Quellordner `app/src/state` ausgeschlossen; er fehlte im ersten Commit und ZIP |
| Vorschau-Build als eine HTML-Datei mit eingebetteten DEMO-Daten (`app/scripts/build_preview.mjs`); ohne Service Worker, Downloads, Drucken und Installation; übernimmt das Farbschema des umgebenden Rahmens | Die App lässt sich vor der GitHub-Einrichtung in Claude ansehen; echte Kursdaten werden nie eingebettet |

### Nach der ersten Bereitstellung (13.10.2026, Builds 1.0.0)

| Änderung | Begründung |
|---|---|
| `reportlab` in `backend/requirements-dev.txt` | Der PDF-Rundlauftest des Universum-Parsers lief lokal nur, weil reportlab dort vorinstalliert war; im ersten Lauf „Prüfung“ auf GitHub fehlte das Paket |
| Workflow „Prüfung“ zeigt fehlgeschlagene Tests als Hinweise in der Laufübersicht | Die Ursache ist sichtbar, ohne das Protokoll herunterzuladen |
| Notierungen ohne Kurs am Stichtag und Abruffehler werden im nächsten Versuch für denselben Stichtag erneut abgerufen (Abrufstatus `ohne_stichtag`) | Bisher galt eine Notierung nach dem ersten Abruf als erledigt; die Wiederholungen um 06:15, 06:45 und 08:00 konnten verspätet gelieferte Schlusskurse deshalb nicht übernehmen. Anlass: erster echter Lauf am 13.10.2026 |
| Kurzbericht des täglichen Laufs als Hinweis in der GitHub-Laufübersicht: Ergebnis, Stichtag, TR-Liste, Identitätsprüfung, Kursabruf, Stichtagskurse je Markt mit Beispielen | Das Protokoll eines Laufs ist nur als Ganzes abrufbar; der Grund für „wartet auf Anbieter“ war nicht erkennbar |
| Workflow „Datenquellen prüfen“: Stichtagskurs je Börse bei Yahoo (ein liquider Wert je Börse, drei Abfragevarianten, Stundenkerzen) und Kennzahlen je Quelle als Hinweise | Prüft genau das, worauf der tägliche Lauf angewiesen ist: den Schlusskurs des gemeinsamen Stichtags |
| App: Passphrase lässt sich schon vor dem ersten Datenstand eingeben und prüfen; der Grund des letzten Laufs steht lesbar mit Uhrzeit im Leerzustand | Bisher fragte die App erst nach der Passphrase, wenn ein Datenstand existierte – nach der Einrichtung war unklar, wo sie einzugeben ist |
| Täglicher Lauf: Eingabe `nur_website` (`traktien ci --nur-website`) stellt nur die Website neu bereit – App-Hülle neu, Datenstände und Sicherung unverändert | Eine geänderte App war bisher erst nach dem nächsten vollständigen Lauf online (bis zu Stunden) |
