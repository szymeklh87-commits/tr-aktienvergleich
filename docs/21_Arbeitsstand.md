# Arbeitsstand und Fortsetzung (laufend gepflegt)

Stand 07.11.2026, 17:10 Uhr. Veröffentlicht: **1.22.0** (main 3de10d6, Pages 15:45 UTC, App-Prüfung mit echten Daten bestanden).
Rückfallversion: Zweig `rueckfall-1.21.0`. Arbeitszweig: `f09-liste-zuerst` (wird 1.23.0).

## In Arbeit: 1.23.0 (Freigabe zur Veröffentlichung nach Tests erteilt, Aufträge 16:50–16:52)

1. **Nur Aktien ab 10 Mio. USD Ø Tagesumsatz** (dauerhaft, bisher „Gruppe B“), keine A/B-Auswahl, keine A/B-Bezeichnungen,
   Überschrift „Höchste Kursrendite“ mit „Mindestumsatz: 10 Mio. USD pro Handelstag (Durchschnitt)“, Plätze neu gezählt
   (Daten „…l“/„ul“/„v0l“/„winners_l“ des Stands; Rohdaten aller Aktien bleiben im Stand).
   - erledigt: `lib/universe.ts`, Standardgruppe „b“ (scoring), Ranking, Rendite 1–90 und vollständige Liste, Häufigste,
     Matrix, Sieger (eine Zelle je Zeitraum), Bericht (eine Spalte, `lib/report.ts`), Top nach Zahlen und Musterdepots
     (`topLists` mit „b“), Startseiten-Kurzfassung „Sieger nach Zeitraum“, Zählung der ersten Plätze nur in „b“.
   - offen: Startseite (Auswahl a/b, Texte), Einzelansicht (nur Platz in der Liste mit Mindestumsatz), Potenzial (immer
     nur Aktien mit Mindestumsatz, Filter entfernen), Kaufkandidaten (Backend `tradeplan.py`: Schwelle 10 Mio. USD statt
     1 Mio. €; App filtert zusätzlich `instruments.turnover.liquid`), Kursabgleich-Ansicht (nur Gruppe B), Methodik,
     Status, Hilfe/Glossar, Analyse-Übersicht, Aktualisieren-Text, Musterdepots-Texte, erweiterte Häufigkeit,
     `analyseregel.ts` (Standard gruppe B), Robo: `config/aktienpilot.yaml` lineal `gruppe: B` (neue Version
     lineal-vorwaerts-2), `aktienpilot/config.py` Standard „B“, Regel-Baukasten ohne Gruppenwahl.
   - Spitzenreiter mit ungeklärter Börsenplatzabweichung: in 1.23 als „ungeprüft“ gekennzeichnet, kein Kaufsignal;
     Ausschluss mit neu gezählten Plätzen im Rechenkern folgt mit der Börsenplatz-Überarbeitung (unten).
   - Tests anpassen: App `tests/report.test.ts`, `pure.test.ts`, `contract.test.ts`; Browser-Tests (A/B-Auswahl entfällt).
2. **F09 „Liste zuerst“**: fertig auf diesem Zweig (Messtest `test_F09_every_main_list_starts_on_the_first_screen`).
3. **App-Update ohne Cache-Löschen**: neue Version automatisch aktivieren und einmal neu laden.
4. Danach: Prüfung, PR, Merge, `nur_website`, dann erzwungener Tageslauf (Robo-Start mit Mindestumsatz; der Zustand
   vom Vortag bleibt dabei als Generation erhalten), App-Prüfung mit Android, Link an Simon.

## Danach (Reihenfolge)

- **Börsenplatzabweichungen** (Auftrag 16:47): Vergleich zur gleichen Uhrzeit (Intraday-Kerzen, Wechselkurs zur selben
  Zeit), Ursachen je Aktie (Schlusszeit, Währung, Kapitalmaßnahme, veralteter Kurs, Zuordnung, Datenfehler), Korrektur
  belegter Fehler, ungeklärte Fälle aus Spitzenplätzen und Kaufsignalen mit neu gezählten Plätzen (zweiter Rechengang
  im Rechenkern), alle Aktien rollierend, Karman (KRMN) einzeln. Öffentliche Ausgaben nur mit Buchstaben/Zählwerten.
- **Aktualisieren mit einem Knopf** (Auftrag 16:55): Vermittlungsdienst (Cloudflare Worker, kostenlos) mit GitHub-Token
  als Secret, App ruft ihn mit der verschlüsselten Anfrage auf; Cron des Dienstes stößt die Tagesläufe pünktlich an
  (F06). Wartet auf Simons Secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `RELAY_GITHUB_TOKEN`. Fortschritt in
  Prozent und Stückzahl, Geschwindigkeit vorher/nachher messen.
- **Kaufkandidaten mit historischer Auswertung** (Auftrag 17:03): je Kandidat Ø Rendite nach 1/5/10/20 Handelstagen,
  Trefferquote, Zahl der Signale, Ø Verlust, größter Rückgang – nur mit damals verfügbaren Daten, mit Stop, Ziel und
  Kosten; Methodenvergleich der Sortierung; Startseite „Top 10 – durchschnittliches Kurspotenzial“; „Nicht ausreichend
  belegt“ ohne genug Daten; Schlusskursbasis kennzeichnen.
- Weitere offene Befunde: F16 (Verlauf 60 Börsentage), F14 (Ansichten zusammenlegen), F13 (Robo/Optimierer), F10, F21.
- Abnahme 10/10: geplante Kontrolle Di 10.11., 06:40 Uhr (Nachtlauf Mo 09.11.).
- Food Explorer (Simons Windows-App): wartet auf Verbindung zum PC oder ZIP; Bestandsliste der Lokale in der Sitzung.
