# Arbeitsstand und Fortsetzung (laufend gepflegt)

Stand 07.11.2026, 22:00 Uhr. Veröffentlicht: **1.25.0** (main 7457c46, PR #10; davor 1.24.0 = 6abdee5, PR #9). Live mit
echten Daten geprüft (App-Prüfung 42413388814, S25+-Format und Android-Emulator, 13 Tests ok, Version 1.25.0+633d644e).
Signal-Stand 20261107T205236Z (Lauf „Nur Kennzahlen und Signale“ 42413113607): Signalregel 2 mit 65 Kaufsignalen und 280
„beobachten“; Rückblick 26.838 frühere Kaufsignale (25.236 ausgeführt); Wahrscheinlichkeiten 0 von 30 Horizonten
zuverlässig (bis 420.640 Testfälle je Horizont) – die App zeigt „Nicht ausreichend zuverlässig“; 45 Aktien mit eingeordneten
Meldungen, 0 Kaufwarnungen; Aufmerksamkeit 100 Plätze aus 3.609 Aktien. Erzwungener Tageslauf (Robo, Musterbereiche,
Depot-Empfehlungen) geplant für 00:20 Uhr. Rückfallversionen: 1.23.0 = b6cddfb, Zweig `rueckfall-1.21.0`, 1.22.0 = 3de10d6.
Öffentliche Texte (Repo, Logs, PR, Commits) nur mit Zählwerten, Zeiten, Codes und Buchstaben – keine ISINs, Namen,
Kürzel oder Kurse aus Auswertungen.

## Erledigt: 1.24.0 und 1.25.0

- 1.24.0: Kaufzeitpunkt am angezeigten Kurs (🟢🟡🔴⚪) in allen Listen, Kaufkandidaten und Einzelansicht; „Auf einen Blick“;
  eigene Position (Halten/Verkaufen, nur auf dem Gerät); Rückblick der Signalregel `rueckblick-1`; Risiko `risiko-1`;
  Kurschart mit Kaufzone, Limit, Stop, Ziel, Unterstützung/Widerstand, 1T/5T; geprüfte Ranglisten (`winners_lg`, Plätze
  neu gezählt, Abgleich 15 Plätze); Fehler „Abweichung am zweiten Börsenplatz bei Kaufsignalen nicht erkannt“ behoben;
  Signal-Tor zu bei Signalregel älter als 2.
- 1.25.0: Wahrscheinlichkeiten 1–30 Handelstage `wahrscheinlichkeit-1` (Walk-forward, Brier/Log-Loss/Kalibrierung,
  „Nicht ausreichend zuverlässig“), keine Tageswahrscheinlichkeit ohne Intraday-Historie; Ereignisse `ereignisse-1` mit
  Kaufwarnung (Risiko `risiko-2`), Chartmarkierungen, Kursreaktion; Analystenszenarien (12 Monate); Aufmerksamkeit
  `aufmerksamkeit-1` (onvista nur verlinkt); Gesamtbild ohne Prozentzahl; Grenzen der Daten.
- Offen aus den Plänen unten (bewusst noch nicht umgesetzt): Sortiermethoden der Top 10 nach Trefferquote vergleichen;
  Börsenplatz-Vergleich zur gleichen Uhrzeit mit Intraday-Kerzen und Ursachenliste je Aktie; Mini-Charts in Listen;
  Spread; Wikimedia-Seitenaufrufe in der Aufmerksamkeit; Einzeltag-Wahrscheinlichkeiten; Modellvergleich (Gradient
  Boosting, Mustervergleich) – derzeit nur logistische Regression; Treffsicherheit einzelner Analystenhäuser (keine
  Daten); Prüfung widersprüchlicher Fälle mit echten Daten (Ergebnis nur im Chat).

## Erledigt: 1.23.0

- Nur Aktien ab 10 Mio. USD Ø Tagesumsatz in allen Ranglisten, Top-Listen, Häufigkeiten, Matrix, Bericht, Musterdepots,
  Potenzial, Kaufkandidaten (Signalregel 2), Spielgeld-Robo (Risiko-Manager je Entscheidungstag), Labor, Vorlagen und
  Depot-Optimierer; keine A/B-Auswahl und -Bezeichnungen; ungeklärte Abweichungen „Ungeprüft – …“; F09; App-Update ohne
  Cache-Löschen (Seiten bis 1.22 sofort, ab 1.23 beim Öffnen oder im Hintergrund).
- Offen danach: erzwungener Tageslauf nach Mitternacht (geplante Erinnerung 00:20 Uhr) für Signalregel 2, Robo-Start,
  Musterbereiche und Depot-Empfehlungen; Labor- und Optimierer-Läufe neu; Spitzenplätze mit ungeklärter Abweichung bis zur
  Börsenplatz-Überarbeitung (1.24) nur gekennzeichnet, noch nicht mit neu gezählten Plätzen ausgeschlossen.

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

- **Kaufen, Halten, Verkaufen** (Auftrag 17:42): Kauf- und Verkaufsbewertung getrennt; für neue Käufer Kaufen / Abwarten /
  Kein Kaufsignal / Nicht beurteilbar, für Positionen (eigene Depots, Musterdepots, Robo) 🔵 Halten / 🔴 Verkaufen mit
  Kaufpreis, Größe, Haltedauer, Risikogrenzen; Auslöser: Ziel erreicht, Stop unterschritten, Trend lässt nach, Risiko
  steigt, schwache Zahlen, Gewinnwarnung/kritische Meldung, Analysten deutlich schlechter, Überbewertung/Trendumkehr –
  normale Schwankung von echtem Signal trennen; Gebühren, Spread, Steuer; Verkaufssignale im Chart; Rückwärtstest ohne
  Zukunftsdaten mit Trefferquote, Ø Nettorendite, größtem Verlust und Vergleich mit Kaufen-und-Halten; veraltete Signale
  nie als aktuell.
- **Risikoanalyse und Aufmerksamkeit** (Auftrag 17:39): Risiko niedrig/mittel/hoch mit zwei bis drei Gründen
  (Verschuldung, Liquidität, Umsatz/Gewinn, Schwankung, Verluste, kritische Meldungen, Analysten, Bewertung) im
  Bewertungskasten (1.24). Die Top-1000-Liste von onvista darf nicht automatisiert genutzt werden (AGB Ziffer 3.3:
  automatisierte Abfrage ohne schriftliche Einwilligung unzulässig; keine Schnittstelle/Lizenz angeboten) – nur ein Link
  dorthin. Eigene, klar anders benannte Rangliste „Aufmerksamkeit (eigene Berechnung)“ aus zulässigen Quellen
  (Wikimedia-Seitenaufrufe, Zahl der Meldungen, ungewöhnliches Volumen): Rang heute/Vortag, ↑/↓ mit Plätzen, „neu“,
  7/30 Tage, Verlauf gespeichert, belegte Gründe; Aufmerksamkeit nie als Kaufsignal (1.25).

- **Wahrscheinlichkeiten heute und 1–30 Handelstage** (Auftrag 17:58): je Aktie P(steigt)/P(fällt) (heute nur mit aktuellen
  Intraday-Kursen, sonst nächster Handelstag; Basis Vortagesschluss bzw. angezeigter Kurs getrennt) und für jeden Horizont
  1–30 (sofort sichtbar 1/5/10/20/30; Einzeltag und kumuliert getrennt): Ø Veränderung, Trefferquote, Unsicherheit;
  Modelle (logistisch, Gradient Boosting, Mustervergleich, Trend/Momentum, Fundamental, Kombination) nur nach
  Walk-forward-Test ohne Zukunftsdaten ausgewählt; Brier, Log-Loss, Kalibrierung, Fallzahl, Fehler je Horizont, steigende vs.
  fallende Märkte; ohne Kalibrierung „Nicht ausreichend zuverlässig“; höchstens drei Gründe; hohe Wahrscheinlichkeit nie
  allein Kaufsignal; Kurs- und Berechnungszeitpunkt, Quellen, Horizont immer sichtbar.

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
