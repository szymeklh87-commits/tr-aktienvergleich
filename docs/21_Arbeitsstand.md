# Arbeitsstand und Fortsetzung (laufend gepflegt)

Stand 07.11.2026, 17:30 Uhr. Veröffentlicht: **1.22.0** (main 3de10d6, Pages 15:45 UTC, App-Prüfung mit echten Daten bestanden).
Rückfallversion: Zweig `rueckfall-1.21.0`. Arbeitszweig: `f09-liste-zuerst` (wird 1.23.0).
Öffentliche Texte (Repo, Logs, PR, Commits) nur mit Zählwerten, Zeiten, Codes und Buchstaben – keine ISINs, Namen,
Kürzel oder Kurse aus Auswertungen.

## In Arbeit: 1.23.0 (Freigabe zur Veröffentlichung nach Tests erteilt, Aufträge 16:50–16:52)

1. **Nur Aktien ab 10 Mio. USD Ø Tagesumsatz** (dauerhaft, bisher „Gruppe B“), keine A/B-Auswahl, keine A/B-Bezeichnungen,
   Überschrift „Höchste Kursrendite“ mit „Mindestumsatz: 10 Mio. USD pro Handelstag (Durchschnitt)“, Plätze neu gezählt
   (Daten „…l“/„ul“/„v0l“/„winners_l“ des Stands; Rohdaten aller Aktien bleiben im Stand).
   - erledigt (App): `lib/universe.ts`, Standardgruppe „b“, alle Ranglisten- und Häufigkeitsansichten (auch erweiterte
     Zählung und Treffer-Matrix je Aktie), Matrix, Sieger, Bericht, Top, Musterdepots, Startseite, Einzelansicht,
     Potenzial (immer mit Mindestumsatz), Kaufkandidaten (`instruments.turnover.liquid`), Gewichtungsvergleich,
     „Deine Aktien“ (Platz in der Liste mit Mindestumsatz), Methodik, Status, Glossar, Analyse, Regel-Baukasten ohne
     Gruppenwahl (Regeln immer „B“), Texte ohne Gruppenbezeichnungen.
   - offen: Backend `tradeplan.py` (Signalregel 2: 10 Mio. USD statt 1 Mio. €), Robo: `config/aktienpilot.yaml` lineal
     `gruppe: B` (neue Version lineal-vorwaerts-2), `aktienpilot/config.py` Standard „B“, Risiko-Manager kauft nur
     Einzelaktien mit nachgewiesenem Mindestumsatz (zum jeweiligen Tag, ohne Zukunftsdaten).
   - Spitzenreiter mit ungeklärter Börsenplatzabweichung: in 1.23 als „ungeprüft“ gekennzeichnet, kein Kaufsignal;
     Ausschluss mit neu gezählten Plätzen im Rechenkern folgt mit der Börsenplatz-Überarbeitung (1.24).
   - Tests anpassen: App `tests/report.test.ts`, `pure.test.ts`, `contract.test.ts`; Browser-Tests (A/B-Auswahl entfällt).
2. **F09 „Liste zuerst“**: fertig auf diesem Zweig (Messtest `test_F09_every_main_list_starts_on_the_first_screen`).
3. **App-Update ohne Cache-Löschen**: neue Version automatisch aktivieren und einmal neu laden.
4. Danach: Prüfung, PR, Merge (Squash), `nur_website`, dann erzwungener Tageslauf (Robo-Start mit Mindestumsatz; der
   Zustand vom Vortag bleibt als Generation erhalten), App-Prüfung mit Android, Link an Simon.

## 1.24.0 – Kaufbewertung je Aktie (Aufträge 17:03, 17:06, 17:09, 17:13, 17:15)

Eine gemeinsame Bewertung je Aktie, überall gleich angezeigt (Startseite, Top 10, Ranglisten, Suche, Einzelansicht,
Potenzial, Analyse, AktienPilot, Strategielabor, Depot-Optimierer, Musterdepots); in Listen kompakt, Details aufklappbar.

- **Kaufampel am Kurs**: 🟢 Günstiger Einstieg (alle Bedingungen erfüllt) · 🟡 Abwarten (z. B. Kurs über dem
  Einstiegslimit – mit Kursniveau, „zu spät“ bei Überdehnung) · 🔴 Kein Kaufsignal · ⚪ Nicht beurteilbar. Neu bewertet bei
  jedem neuen Kurs (auch Live-Kurse in der App), alle Bedingungen vollständig neu – ein Kursrückgang allein ergibt nie Grün.
  Prüft Kurs gegen Einstiegslimit, Stop, Ziel, 20/50-Tage-Linie, jüngste Hochs, Unterstützung/Widerstand, Trend, Momentum,
  RSI, Volumen, Schwankung, Nachrichten, Termine, CRV, Marktlage. Kurszeitpunkt, Quelle, Börsenplatz immer sichtbar;
  Schlusskurs/verzögert: „Einschätzung auf Schlusskursbasis“ bzw. „Bewertung auf verzögerter Kursbasis“, nie
  „bestätigt“; Börse geschlossen gekennzeichnet; Spread soweit verfügbar.
- **Kurz- und langfristige Ampel** (Grün/Gelb/Rot), fehlende Daten nie grün.
- **Historische Folgerenditen** gleichartiger Signale nach 1/5/10/20 Handelstagen und 1/3/6/12 Monaten: Ø Rendite,
  Trefferquote, Fallzahl, Ø Verlust, größter Rückgang; nur damals verfügbare Daten, Kosten, Stop und Ziel; „Nicht
  ausreichend belegt“ bei zu wenigen Fällen. Getrennt davon: rechnerisches Kurspotenzial (Ziel, Analysten).
- **Top 10**: Sortiermethoden nach Trefferquote, Folgerendite, Schwankung, Verlustrisiko und CRV vergleichen; Startseite
  „Top 10 – durchschnittliches Kurspotenzial“ und getrennt die historische Ø Rendite der Kaufsignale; Schlusskursbasis
  kennzeichnen.
- **Kurscharts mit Kaufzonen**: aktueller Kurs als Linie mit Zeitstempel; Zonen grün/gelb/rot/grau aus denselben
  Bedingungen; Linien Einstieg, Stop, Ziel, Unterstützung, Widerstand; Zeiträume 1T/5T/1M/3M/6M/1J, Kerzen, Volumen,
  Indikatoren optional; Antippen zeigt Kurs, Datum, Uhrzeit, Veränderung, Bewertung zu diesem Zeitpunkt; Mini-Charts in
  Listen; flüssig auf dem S25+.
- **Börsenplatzabweichungen** (Auftrag 16:47): Vergleich zur gleichen Uhrzeit (Intraday-Kerzen, Wechselkurs zur selben
  Zeit), Ursachen je Aktie (Schlusszeit, Währung, Kapitalmaßnahme, veralteter Kurs, Zuordnung, Datenfehler), Korrektur
  belegter Fehler, ungeklärte Fälle aus Spitzenplätzen und Kaufsignalen mit neu gezählten Plätzen (zweiter Rechengang),
  alle Aktien rollierend, die im Auftrag genannte Aktie einzeln (Ergebnis nur im Chat).

- **Verständliche Bewertung** (Auftrag 17:36): kompakter Kasten je Aktie (Kurs mit Handelsplatz und Zeit, Kaufzeitpunkt,
  kurz-/langfristige Ampel, Kurspotenzial aus unabhängigen Analystenzielen, historische Ø Rendite vergleichbarer Signale,
  Risiko niedrig/mittel/hoch, Nachrichtenlage mit Warnung); je Bewertung die zwei bis drei wichtigsten belegten Gründe,
  Quelle, Datum, Kennzahlen, Regel und Einschränkungen (aufklappbar); keine unerklärten Zahlen oder Abkürzungen;
  Analystenmehrheit, Trefferquote, Kurszielpotenzial und Wahrscheinlichkeit nie vermischen; fremde Gesamtratings nicht
  übernehmen und keine Begründungen dafür erfinden; „Nicht aktuell beurteilbar“ ohne aktuelle Daten; widersprüchliche
  Fälle gezielt prüfen (Ergebnis nur im Chat).

## 1.25.0 – Prognosen und Nachrichten (Aufträge 17:18/17:23, 17:22)

- **Prognosen im Chart**: durchgezogen Ist-Kurs, gestrichelt mittlere Prognose, Bereiche optimistisch/pessimistisch,
  Unsicherheitsband nur wenn belastbar; Ansatz am letzten Kurs. Analystenziele: einfacher Ø und Median unabhängiger
  Ziele (Doppelte erkennen), gewichteter Ø (Aktualität, Verlässlichkeit, frühere Treffsicherheit), eigenes Modell nur nach
  Rückwärtstest auf unabhängigen Zeiträumen; Horizonte 1/3/6/12/24/36 Monate nur, wenn Daten sie stützen (12-Monats-Ziel
  nicht umrechnen); Quellenzahl, Datenstand, Horizont, Änderung zur Vorberechnung; Prognosequalität ohne Scheingenauigkeit.
- **Nachrichtenanalyse**: alle erfassten Aktien, Vorrang für angezeigte Aktien, Kandidaten und Depotpositionen; deutsche
  und internationale zulässige Quellen; Dubletten zusammenfassen; Zuordnung über ISIN/Name/Notierung; Ereignisarten
  (Zahlen, Prognose, Aufträge, Analysten / Gewinnwarnung, Liquidität, Insolvenz, Bilanz, Ermittlungen, Kundenverlust,
  Handelsaussetzung, Verwässerung); bestätigt / Bericht / Gerücht unterscheiden; Ampel 🟢🟡🔴⚪; „Hohes
  Unternehmensrisiko – Kaufwarnung“ nur bei belegten kritischen Ereignissen (dann kein Grün); Markierungen im Chart mit
  Quelle, Zeit, Bewertung und gemessener Kursreaktion; letzte Prüfung, neueste Meldung, Zähler, Links; Fehlalarme und
  übersehene Risiken an bekannten früheren Ereignissen prüfen.

- **Risikoanalyse und Aufmerksamkeit** (Auftrag 17:39): Risiko niedrig/mittel/hoch mit zwei bis drei Gründen
  (Verschuldung, Liquidität, Umsatz/Gewinn, Schwankung, Verluste, kritische Meldungen, Analysten, Bewertung) im
  Bewertungskasten (1.24). Die Top-1000-Liste von onvista darf nicht automatisiert genutzt werden (AGB Ziffer 3.3:
  automatisierte Abfrage ohne schriftliche Einwilligung unzulässig; keine Schnittstelle/Lizenz angeboten) – nur ein Link
  dorthin. Eigene, klar anders benannte Rangliste „Aufmerksamkeit (eigene Berechnung)“ aus zulässigen Quellen
  (Wikimedia-Seitenaufrufe, Zahl der Meldungen, ungewöhnliches Volumen): Rang heute/Vortag, ↑/↓ mit Plätzen, „neu“,
  7/30 Tage, Verlauf gespeichert, belegte Gründe; Aufmerksamkeit nie als Kaufsignal (1.25).

## Außerdem

- **Aktualisieren mit einem Knopf** (Auftrag 16:55): Vermittlungsdienst (Cloudflare Worker, kostenlos) mit GitHub-Token
  als Secret; Cron des Dienstes stößt die Tagesläufe pünktlich an (F06). Wartet auf Simons Secrets
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `RELAY_GITHUB_TOKEN`. Fortschritt in Prozent und Stückzahl,
  Geschwindigkeit vorher/nachher messen.
- Weitere offene Befunde: F16 (Verlauf 60 Börsentage), F14 (Ansichten zusammenlegen), F13 (Robo/Optimierer), F10, F21.
- Abnahme 10/10: geplante Kontrolle Di 10.11., 06:40 Uhr (Nachtlauf Mo 09.11.).
- Food Explorer (Simons Windows-App): wartet auf Verbindung zum PC oder ZIP; Bestandsliste der Lokale in der Sitzung.
- Kostenlose Kurse sind meist verzögert, Nachrichten nicht im Sekundentakt: Alter von Kurs und Nachrichtenstand immer
  anzeigen, nichts als Echtzeit ausgeben; kostenpflichtige Quellen nur mit Simons Freigabe.
