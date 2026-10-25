# Testbericht – tatsächlich ausgeführt

Stand **25.10.2026, 12:45 Uhr (Europe/Berlin, MEZ)**, Software **1.18.2**, Methode **tr-methode-1.10.0** (Prüfstatus auf einen Blick – Softwaretests, Datenbestätigung, Ursachenklärung, fachliche Abnahmen, nicht erfüllte Kriterien und Ausstehendes getrennt; Abschnitt Überblick, erste Zeilen; offene Punkte mit Grund in Abschnitt 8, die übersprungenen Tests einzeln in 8a, Nachrechnung, Kurs-Gegenprüfung und Abnahme in 8d–8f); davor 1.18.1, 1.18.0, 1.17.1 und 1.17.0; davor 1.16.0, 1.15.0 und die geplanten Läufe vom 15. und 16.10.; ältere Abschnitte: Software **1.5.2**, Methode **tr-methode-1.8.0** (1.5.2: Börsenplatz-Abgleich nur mit Kursen mit Umsatz und Schwelle nach Tagesschwankung; 1.5.1: fehlende Börsentage beim Kursanbieter, Börsenplatz-Abgleich nur mit Kursen desselben Tages, verständlicher Teilstand; 1.5.0: Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“: Regeln des Ausgangsmodells, feste Schnellwahl 7–90 Tage, Sieger nach Zeitraum, Matrix 1–90, Häufigkeit mit Filtern; dazu alles aus 1.1–1.4). Ausgeführt wurde an zwei Orten:

- **Entwicklungsumgebung** (12.10.2026 22:30 Uhr bis 13.10.2026 22:30 Uhr): alle Tests mit synthetischen DEMO-Daten. Externe Datenquellen waren von hier aus nicht erreichbar.
- **GitHub Actions** (seit 13.10.2026): Workflow „Prüfung“ bei jeder Änderung, Workflow „Datenquellen prüfen“ mit den echten Quellen und die ersten echten täglichen Läufe (Abschnitt 7).

Alle Zahlen unten stammen aus diesen Läufen. Was nicht prüfbar war, steht ausdrücklich unter „Nicht geprüft“ (Abschnitt 8) – es gilt als offen, nicht als bestanden. Die Uhrzeiten sind deutsche Zeit: bis 25.10.2026, 03:00 Uhr MESZ (GitHub zeigt UTC, zwei Stunden früher), danach MEZ (GitHub eine Stunde früher).

## Prüfstatus auf einen Blick (25.10.2026, 12:45 Uhr MEZ)

Ausgeliefert ist die App **1.18.2+3a4bd974** (Commit `fbe62ad`, bereitgestellt am 24.10.2026 um 23:10 Uhr,
[Lauf 40132945105](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132945105): „App 1.18.2+3a4bd974 neu zusammengesetzt; Datenstand unverändert“);
davor 1.18.1+7e61c801 (Commit `17c572d`, 20:57 Uhr). Datenstand unverändert `2026-10-23_3f7ce5f3` – kein neuer Börsentag;
der tägliche Lauf über den Zeitplan meldete am 25.10. „keine neuen Daten“ ([40186008825](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40186008825)),
ein Nachtlauf über den Zeitplan steht noch aus. Seitdem nur Prüfskripte, Workflow „App mit echten Daten prüfen“ und
Dokumentation geändert – die App nicht; zuletzt am 25.10. um 13:23–13:32 Uhr (MEZ) erneut als 1.18.2+3a4bd974 geprüft
([Lauf 40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763), endgültiger Code der Prüfskripte `ddb4ff1`). Sechs getrennte Fragen – ein grünes Prüfskript beantwortet keine davon:

**1. Softwaretests – bestanden**

| Was | Ergebnis | Nachweis |
|---|---|---|
| Workflow „Prüfung“ (alle Python-Tests mit DEMO-Daten, App-Build, Börsenkalender) – letzter Stand des Codes, Commit `ddb4ff1`, 25.10.2026, 13:23–13:34 Uhr (MEZ) | **748 Tests ausgeführt: 726 bestanden, 22 übersprungen, 0 fehlgeschlagen** (übersprungen sind die Live-Tests, die in eigenen Workflows mit Secrets laufen, 8a); echte Börsenkalender 4 von 4. Ebenso grün die Commits davor: `8b4b52e` 744 Tests, 722 bestanden ([40188407048](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188407048)), ebenso `bca5121` (Dokumentation, Docstring eines Unit-Tests; [40190128191](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40190128191)) und `9614cda` (Dokumentation; [40190282824](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40190282824)) mit je 744 Tests, 722 bestanden; `2fc32d3` 743 Tests, 721 bestanden ([40187555946](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40187555946)); `09bc9e1` 738, 716 ([40184592102](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40184592102)); `438b2e1` 728, 706 ([40181859911](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40181859911)) – je 22 übersprungen, 0 fehlgeschlagen; die Commits dieses Berichts nach `ddb4ff1` ändern nur Dokumentation – Prüfskripte, Workflows und App unverändert; ihre „Prüfung“ läuft beim Hochladen. Ausgelieferte App: Commit `fbe62ad`, 652 Tests, 630 bestanden, 22 übersprungen ([40132325646](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132325646)) | [40192909412](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192909412) |
| Python lokal | Ganzer Lauf zuletzt mit `09bc9e1` (25.10., 11:17–11:29 Uhr MEZ): **738 Tests, 712 bestanden, 26 übersprungen** (alle 26 Live-Tests – 22 laufen in eigenen Workflows, die 4 Kalendertests in der „Prüfung“), 0 fehlgeschlagen. Danach geändert nur die Prüfskripte der Kursursachen: mit `2fc32d3` alle 545 Unit- und 96 Integrationstests bestanden (11:50–12:05 Uhr), mit `8b4b52e` alle 546 Unit-Tests und die 12 Integrationstests der Kursursachen (12:16–12:19 Uhr); die 76 Browser-Tests lokal zuletzt mit `09bc9e1`, mit `8b4b52e` in der „Prüfung“. Für die ausgelieferte App: 652 Tests (626 bestanden, 26 übersprungen, 24.10., 22:46–22:56 Uhr) und alle 76 Browser-Tests erneut (22:58–23:01 Uhr) | Entwicklungsumgebung |
| App (TypeScript), Stand 1.18.2 | Typprüfung ohne Fehler, 104 Tests (88 bestanden, 16 Datenvertragstests über Python), lokal 24.10., 23:02 Uhr; in der „Prüfung“ ebenso, dort zusätzlich der App-Build identisch mit dem eingecheckten Build | Entwicklungsumgebung, [40132325646](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132325646) |

**2. Datenbestätigung – nicht bestätigt, nur ein Teil geprüft** (Kurse des Stands gegen unabhängige Quellen, nachträglich beschafft – keine Originaldaten)

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Kurse des Stands 23.10. gegen **abgesicherte** Vergleiche (Nasdaq-Historie, offizieller Schlusskurs NOCP, CNBC; Aktie und Gattung über die ISIN, Name, Art, Börse, Währung, Handelstag, Bereinigung, Kursniveau) | **505 von 560** ausgewählten Aktien abgesichert verglichen (404 US-Aktien und alle 156 Aktien außerhalb der USA mit Platz unter den ersten 10): **34.500 Aktientage, davon 33.434 gleich (96,9 %), 1.066 abweichend**. **Keine Vollprüfung:** 11.036 der 11.596 Aktien nicht ausgewählt, 55 ausgewählte ohne abgesicherten Vergleich; verglichen 4,6 % der Kurstage des Stands. Platz 1 bei 1.599 von 1.640 Ranglisten (97,5 %) und 14.564 von 16.400 Plätzen unter den ersten 10 (88,8 %) bei Aktien mit abgesichertem Vergleich | [40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) und [40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664), Abschnitt 8e |
| Kurs-Gegenprüfung bei Nasdaq (24.10., 307 US-Aktien, ohne Absicherung der Zuordnung) | **nicht bestätigt**: 18.182 von 18.753 Börsentagen gleich (96,96 %); die 571 abweichenden tragen den Yahoo-Kurs – kein Nachweis des Börsenkurses | [40128434473](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128434473), Abschnitt 8e |
| Wirkung, falls die Vergleichskurse stimmen (alle Vergleichskurse gemeinsam gegen denselben Stand) | offizieller Schlusskurs (b), mit CNBC (b)+(c) bzw. (b)+(c)+(d): **anderer Platz 1 in 4 von 1.640 Ranglisten**, andere Aktien unter den ersten 10 in 6, 7 bzw. 32; mit Nasdaq-Historie oder CNBC allein kein anderer Platz 1; in keiner Rangliste entsteht eine Änderung erst gemeinsam oder hebt sich auf (nur einzelne Rangänderungen von Aktien überlagern sich, z. B. (b)+(c): 782 erst gemeinsam, 5.656 aufgehoben – ohne Folge für Platz 1 und die ersten 10) | Abschnitt 8e, Punkt 1 |

**3. Ursachenklärung – nicht vollständig belegt**

| Frage | Ergebnis | Nachweis |
|---|---|---|
| Ursachen der 1.066 abweichenden Aktientage (je Aktie und Tag genau einmal) | **belegt 34** (gemeldeter Split, NOCP unbereinigt – nicht ersetzt); **ungeklärt 1.032**: mit plausibler Erklärung 74 (letzte Minutenkerze, Abstand unter einer Kursstufe, Umsatz 0 – keine belegte Ursache), ohne Erklärung 958; 341 der ungeklärten Tage betreffen Aktien der NYSE-Gruppe oder Cboe, deren offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar ist (NYSE: nur im kostenpflichtigen Produkt „TAQ NYSE Closing Prices“) – eine Prüfgrenze, keine Ursache | Abschnitt 8e, Punkt 2 |
| Die bisher als belegt gezählten 49, 56 und 2 Fälle | **keiner belegt** – alle plausible Erklärungen (45 + 40 + 2 in abgesicherten, 4 + 16 in nicht abgesicherten Vergleichen); keine unabhängigen Fälle (je Aktie und Tag 71 + 2) | Abschnitt 8e, Punkt 2 |
| Zuordnung der Vergleichskurse | abgesichert: Nasdaq-Historie 357 von 366, NOCP 177 von 185, CNBC (US) 30 von 34, CNBC (außerhalb der US-Auswahl) 118 von 126; nicht abgesicherte ersetzen und bestätigen nichts | Abschnitt 8e, Punkt 3 |
| OTC Markets „lastTradeTime“ | Bedeutung nicht dokumentiert – **Handelstag offen**; keiner der 25 Stempel genau 00:00:00 Uhr UTC; der OTC-Abschluss ist weder Vergleichskurs noch zweite Quelle | Abschnitt 8e, Punkt 4 |
| Auslöser der 4 neuen Plätze 1 | kleinste Auslösermenge {Z31} – **nachweislich** (jede einzelne ersetzte Aktie geprüft); mit der unabhängigen Rechnung bestätigt: Z31 allein → neuer Platz 1, alle übrigen Änderungen ohne Z31 → bisheriger | Abschnitt 8e, Punkt 5 |

**4. Fachliche Abnahmen – bestanden**

| Abnahme | Ergebnis | Nachweis |
|---|---|---|
| Ausgelieferte App **1.18.2+3a4bd974** mit echten Daten (Chromium 141 im Format des S25+, Desktop-Simulation) | 11 Tests: 10 bestanden, 1 übersprungen (`test_2d`, zählt nicht); 24 von 24 Ansichten; Installation bestanden; Signale mit Einzelansicht | [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565) (23:10–23:12 Uhr), ebenso [40132947135](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132947135), [40138800418](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40138800418), [40139805053](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805053), [40162120622](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622), [40181869022](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40181869022), [40184599190](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40184599190), [40187567792](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40187567792), [40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664) und zuletzt [40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) (25.10., 13:23–13:25 Uhr MEZ) |
| Firefox 142 und WebKit 26 mit echten Daten (Desktop-Simulation), App 1.18.2 | je 11 Tests: 9 bestanden, 2 übersprungen (`test_2d`; Installation nur in Chromium – zählt nicht); je 24 von 24 Ansichten | [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565) |
| Chrome 124 für Android im Emulator mit echten Daten, App 1.18.2 | 24 von 24 Ansichten; **Neustart im Flugmodus bestanden** (ohne Passphrase, Kursstand nach 1,3 s, „Offline – gespeicherter Stand“, Rangliste 10 Zeilen); 0 Konsolenfehler, 0 fehlgeschlagene Abrufe | [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565) |
| Android-Emulator (Chrome 124): Installation der veröffentlichten Website 1.18.2 und DEMO-Daten | über Chromes Menü „Install app“ als Web-App-Verknüpfung installiert, Start im eigenen Fenster mit Sperrbildschirm, Neustart ohne Netz; DEMO: installierbar ohne Hindernisse, offline mit gespeichertem Stand, hoch und quer je 10 Ansichten ohne Verschiebung; TalkBack eingeschaltet: alle bedienbaren Elemente in Chromes Barrierefreiheits-Baum mit Namen (im Android-Abbild 2 Suchfelder ohne eigenen Text – das Abbild gibt ihren Hinweistext nicht aus, 8b); Bedienung mit Gesten nicht geprüft | [40133048985](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133048985) (23:10–23:17 Uhr) |
| Unabhängige Nachrechnung Stand 23.10. | reproduziert und fachlich korrekt: 0 Abweichungen in 9.987.000 Prüfungen | [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565), zuletzt [40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) |
| Ursachen der Kursunterschiede – Abruf, Übergabe und Ausgabe (Auftrag 25.10., 09:20 Uhr) | in allen vier Prüfjobs 0 Aktien ohne jede Antwort (erste 10: 157, Plätze 11–20: 97, Zufallsstichprobe: 150, außerhalb der US-Auswahl: 156 – dort seit `ddb4ff1` gemessen, vorher fest 0; 8e Nr. 23); ohne Daten blieben die Zusatzquellen Barchart, MarketWatch, die Kurshistorie von OTC Markets und Stooq bei allen 38 US-Aktien ohne Nasdaq-Kurse (HTTP 403, 401, 404 bzw. HTML statt Daten – nicht bestanden, unter 2 als Lücke gezählt); OpenFIGI für alle 560 ISINs mit Antwort; die verschlüsselten Vergleichskurse aller vier Jobs im Job „gemeinsame Wirkung“ geöffnet (Prüfsummen in beiden Läufen und in Lauf 40184599190 gleich – gleiche Kurse); Hinweise der Prüfjobs vollständig, im gemeinsamen Job 44 von 55 Teilen – die übrigen 11 stehen nur in der Zusammenfassung des Jobs, die von hier aus nicht abrufbar ist (**nicht geprüft**, unter 6); jeder der 192 Buchstaben genau einer Aktie zugeordnet, 184 mit Fundstelle in einer Rangliste, 8 ohne (Aktien in keiner Rangliste des Stands). Gegenprobe der Auslöser mit der unabhängigen Rechnung: in allen 12 Fällen wie die Suche. Das ist Abruf und Rechnung – die Ergebnisse stehen unter 2 und 3 | [40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) und [40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664), Abschnitt 8e |
| Originalstände der App vom 12.10. (3) gegen den Prüfnachweis ihres Laufs | alle drei = damaliger Lauf, damalige Berechnung reproduziert (0 Abweichungen) | [40126000729](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126000729), Abschnitt 8c |
| Stand 13.10. | damalige Berechnung reproduziert (0 Abweichungen) | Abschnitt 8d |

**5. Nicht erfüllte Kriterien**

| Kriterium | Ist | Nachweis |
|---|---|---|
| Abnahme Kurslauf (bisher einziger Lauf mit gleichzeitigem Abruf, 40104747674) | **NICHT BESTANDEN**, 7 von 10: nicht zeitgesteuert (von Hand); nur 49 Notierungen abgefragt, 11.096 aus dem Checkpoint; Tempo: Abrufe 49 (verlangt mindestens 10.000: nicht erfüllt), Messdauer 6 s, 8,1 je Sekunde (verlangt mindestens 6: erfüllt), gleichzeitig über 2 Hosts (erfüllt) | [40126752930](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126752930), Abschnitt 8f |
| Fachlich korrekt: Stände vom 12.10. (3) und 13.10. | **nein** – je 1.280 bekannte Fehlerfälle (1.278 × Gleichstand nach Gleitkomma, 2 × Kennzeichen „Kursreihe vorhanden“); beide Ursachen in der aktuellen Version behoben, die Stände bleiben als Original unverändert | Abschnitte 8c, 8d |
| Kurse unabhängig bestätigt | **nicht bestätigt** – 1.066 abweichende Aktientage, 55 ausgewählte Aktien ohne abgesicherten Vergleich, 11.036 nicht ausgewählt (oben 2) | Abschnitt 8e |
| Ursachen der Kursunterschiede belegt | **nicht vollständig belegt** – 1.032 von 1.066 ungeklärt; alle fünf Jobs rot („UNVOLLSTÄNDIG“ bzw. „NICHT VOLLSTÄNDIG BELEGT“, oben 3) | [40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) und [40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664), Abschnitt 8e |
| Systemschrift im Android-Emulator (Chrome 124) | **wirkt nicht auf die Texte der App**; auf Kontrollseiten und einen langen Absatz in der App schon (16 → 20,8 px). In **1.18.2** soweit möglich behoben: Opt-in `<meta name="text-scale">` (Chrome ab 146) und große Schrift bis 200 % ohne Überbreite (Desktop-Simulation). Mit 1.18.2 im Emulator: „nicht prüfbar“ (Chrome 124 kennt das Opt-in nicht) – auf dem S25+ offen | [40129482881](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40129482881), [40133048985](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133048985), Abschnitt 8b |

**6. Ausstehend bzw. nicht möglich**

| Prüfung | Stand | Wann bzw. warum |
|---|---|---|
| Erster zeitgesteuerter Kurslauf (Nachtlauf Mo., 26.10., 23:37 Uhr MEZ) und seine vollständige Abnahme (zehn Kriterien, Tempo über mindestens 10.000 Abrufe) | **ausstehend** – Kontrolle „seit 26.10.“: AUSSTEHEND, 0 Läufe ([40126755036](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126755036)); ein Start von Hand ersetzt den Nachweis nicht | geplante Aufgabe am **27.10.2026, 09:30 Uhr** (Europe/Berlin), einmal angelegt, keine zweite; ihr Auftrag am 25.10., 12:33 Uhr, um die Kursursachen dieses Auftrags ergänzt |
| Ursache der 1.032 ungeklärten Aktientage | **in den geprüften Quellen nicht nachweisbar**: 341 Tage bei Aktien der NYSE-Gruppe oder Cboe – deren offizieller Schlusskurs ist in den geprüften Quellen nicht frei verfügbar (NYSE: nur kostenpflichtig, „TAQ NYSE Closing Prices“); für die Befunde „Stand ≠ offizieller Schlusskurs“ und die CNBC-Tage wären die einzelnen Abschlüsse um 16:00 Uhr bzw. des OTC-Handels und der Auslandsbörsen nötig, in den geprüften Quellen nicht frei verfügbar | nur mit einer solchen Quelle (lizenziert nur nach deiner Freigabe) |
| 55 ausgewählte Aktien ohne abgesicherten Vergleich und 11.036 nicht ausgewählte | **nicht geprüft**: 30 bei CNBC unter keiner geprüften Schreibweise gefunden (Warschau 6, Tokio 6, CSE Kanada 6, Kopenhagen 4, Zürich 3, Jakarta 2, Wien 2, Johannesburg 1) – für sie ist nur CNBC abgefragt; mit den nicht abgesicherten zusammen 1.836 Plätze unter den ersten 10 und 41 Plätze 1 ohne abgesicherten Vergleich der Aktie; 21 Zuordnung nicht ausreichend abgesichert (Befund je Aktie in 8e); 4 OTC-Aktien ohne Vergleichskurse (in keiner Rangliste) – für die 38 US-Aktien ohne Nasdaq-Kurse lieferten OTC Markets (Kurshistorie HTTP 404), Barchart (HTTP 403), MarketWatch (HTTP 401) und Stooq (ohne Schlüssel HTML statt Daten) bei keiner Aktie Daten | nur mit weiteren Quellen, die ISIN und Kurs nennen (z. B. Kursarchive der Börsen selbst – nicht angebunden, Zugang vom Prüfrechner nicht geprüft) oder einem kostenlosen Stooq-Schlüssel, den du anfordern müsstest |
| Zusammenfassungen und Protokolle der Jobs von „App mit echten Daten prüfen“ | **nicht abrufbar** – sie liegen auf einem Speicher außerhalb von GitHub, die Abfrage von hier wird verweigert; ausgewertet sind die Hinweise der Jobs. Im Job „gemeinsame Wirkung“ stehen dadurch 11 von 55 Teilen (andere Reihenfolge der ersten 10 bei gleichen Aktien, je Variante einzeln) **ungeprüft** nur in der Zusammenfassung; für (b), (c) und (b)+(c) stehen dieselben Reihenfolgen bei gleichen Prüfsummen in den Hinweisen von Lauf 40184599190 | auf der Seite des Laufs („Summary“) mit deiner Anmeldung |
| `test_2d` (Umschichtungs-Regel im echten Zwischenstand) | **ausstehend** – am Wochenende kein Zwischenstand | dieselbe Aufgabe, Schritt 4 |
| Echtes Galaxy S25+: **Samsung Internet, TalkBack (Gesten), Systemschrift, App-Installation** (WebAPK), Bedienung | **offen – nicht durchgeführt**; Emulator und Desktop-Simulation ersetzen das nicht | Prüfanleitung in Abschnitt 8b |
| Historischer Nachweis „App = Ausgangsmodell“ für den 12.10. | **nicht möglich** – Archiv an keiner zugänglichen Stelle (Fundstellen in 8c) | nur mit dem Archiv nachholbar |
| EODHD | nicht freigegeben (kostenpflichtig) | nur nach deiner Freigabe |
| Bildschirmtastatur (Suchfeld bleibt sichtbar) im Emulator | **nicht prüfbar** – die Tastatur öffnet sich über die Entwicklerschnittstelle nicht; in der Desktop-Simulation geprüft (Browser-Test) | auf dem S25+ offen (Abschnitt 8b) |

## Überblick

Zählweise: „N Tests bestanden (M übersprungen)“ in den älteren Zeilen heißt N ausgeführte Tests, davon M übersprungen –
übersprungene Tests zählen nicht als bestanden. Im Prüfstatus oben steht die Zahl der bestandenen Tests ausdrücklich.

| Wo | Was | Ergebnis |
|---|---|---|
| GitHub Actions, 25.10.2026 13:23–13:34 Uhr (MEZ) | **Ursachen – Lauf mit dem endgültigen Code** (Commit `ddb4ff1`): „App mit echten Daten prüfen“ mit „Ursachen“ und „ursachen_stand“ = `2026-10-23_3f7ce5f3` ([40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763)); „Prüfung“ des Commits ([40192909412](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192909412)) | **Prüfung:** 748 Tests, 726 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen, fachlich korrekt; 13.10. reproduziert, fachlich nein (1.280 bekannte Fälle). **Ursachen:** Hinweise aller fünf Jobs Zeile für Zeile gegen 40188406664 verglichen – **gleich**, bis auf Dauer und Zeitstempel, eine Anfrage an Nasdaq mehr im Job „erste 10“ (266 statt 265) und die neuen Texte von Nr. 23; dieselben Prüfsummen, dieselben Titel, dieselbe Zuordnung der Buchstaben; im Job „welt“ „ohne Antwort“ jetzt gemessen: 0 (9 Kursmeldungen und 126 Kerzenabrufe „ok“, keine Wiederholung nötig) |
| Entwicklungsumgebung, 25.10.2026 12:41–13:23 Uhr (MEZ) | **Unabhängige Gegenprüfung des Berichts** gegen die Hinweise von 40188406664 und den Code (8e) und Behebung von Nr. 23 | 2 widerlegte und 9 ungenaue Aussagen im Bericht berichtigt; **Fehler im Code** (Nr. 23: Job „welt“ zählte einen gescheiterten Abruf als „nicht gefunden“, „ohne Antwort“ fest 0) – behoben in `ddb4ff1`, Gegenprobe am alten Code (HTTP 503 → „nicht_gefunden“), 4 neue Tests; lokal 549 Unit-Tests und die 13 Integrationstests der Kursursachen bestanden |
| GitHub Actions, 25.10.2026 12:44–12:55 Uhr (MEZ) | „Prüfung“ der Dokumentations-Commits `bca5121` ([40190128191](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40190128191)) und `9614cda` ([40190282824](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40190282824)) | je 744 Tests, 722 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4 |
| GitHub Actions, 25.10.2026 12:19–12:31 Uhr (MEZ) | **Ursachen – Lauf mit Commit `8b4b52e`, Grundlage aller Zahlen in 8e:** „App mit echten Daten prüfen“ mit „Ursachen“ und „ursachen_stand“ = `2026-10-23_3f7ce5f3` ([40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664)), vier Prüfjobs (erste 10, Plätze 11–20, Zufallsstichprobe, außerhalb der US-Auswahl) und Job „gemeinsame Wirkung“; „Prüfung“ des Commits `8b4b52e` ([40188407048](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188407048)) | **Prüfung:** 744 Tests, 722 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten, Installation bestanden; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen, fachlich korrekt; 13.10. reproduziert, fachlich nein (1.280 bekannte Fälle). **Ursachen:** alle fünf Jobs rot („UNVOLLSTÄNDIG“ bzw. „NICHT VOLLSTÄNDIG BELEGT“) – 0 Aktien ohne Antwort (im Job „welt“ damals nicht gemessen, fest 0 – Nr. 23; im Lauf mit `ddb4ff1` gemessen 0), OpenFIGI für alle 560 ISINs; 505 von 560 abgesichert verglichen, 34.500 Aktientage, 1.066 abweichend – belegt 34, ungeklärt 1.032 (74 plausibel); gemeinsam (b), (b)+(c) und (b)+(c)+(d) Platz 1 in 4 von 1.640 Ranglisten anders, Auslöser jeweils allein Z31 (nachweislich, mit der unabhängigen Rechnung gegengeprüft); auf Ebene der Ranglisten nichts erst gemeinsam, nichts aufgehoben (Rangänderungen einzelner Aktien überlagern sich, z. B. (b)+(c): 782 erst gemeinsam, 5.656 aufgehoben); Platz 1 bei 97,5 %, Plätze unter den ersten 10 bei 88,8 % mit abgesichertem Vergleich der Aktie (8e) |
| GitHub Actions, 25.10.2026 12:07–12:18 Uhr (MEZ) | **Ursachen – dritter Lauf (Commit `2fc32d3`):** [40187567792](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40187567792); „Prüfung“ ([40187555946](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40187555946)) | **Prüfung:** 743 Tests, 721 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. **Ursachen:** Gegenprobe mit der unabhängigen Rechnung, Befunde und Aufschlüsselungen wie vorgesehen (erste 10, Plätze 11–20, außerhalb der US-Auswahl mit denselben Prüfsummen wie 40184599190); **Fehler gefunden** (8e, Nr. 22): im Job „zufall“ blieb ein Block von 100 ISINs bei OpenFIGI ohne Antwort – 100 Vergleiche „nicht abgesichert“ (abgesichert 46 statt 137). Richtig nach der Regel, aber ein einzelner Fehler kostete 100 Absicherungen – behoben in `8b4b52e`; die Zahlen dieses Laufs sind nicht verwendet |
| Entwicklungsumgebung, 25.10.2026 11:40–12:19 Uhr (MEZ) | **Durchsicht der Läufe 40184599190 und 40187567792:** Befunde Nr. 18–22 (8e) – Gegenprobe der Auslöser nicht unabhängig, „227 … nicht Nasdaq-notiert“, 1.980 statt 1.640 Ranglisten, Befunde der Lücken fehlten, OpenFIGI-Block ohne zweiten Versuch | 6 neue Tests (`2fc32d3`: 5, `8b4b52e`: 1); mit `2fc32d3` 545 Unit- und 96 Integrationstests bestanden (11:50–12:05 Uhr), mit `8b4b52e` 546 Unit-Tests und die 12 Integrationstests der Kursursachen (12:16–12:19 Uhr); Gegenprobe der Korrektur Nr. 20: ohne sie schlägt der Integrationstest fehl (1.980 > 1.640) |
| GitHub Actions, 25.10.2026 11:44–11:56 Uhr (MEZ) | **Täglicher Lauf über den Zeitplan** (Sonntag; [40186008825](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40186008825)) | **keine neuen Daten** – kein neuer abgeschlossener Börsentag seit dem 23.10., Datenstand unverändert `2026-10-23_3f7ce5f3`; TR-Liste unverändert (11.596 ISINs); Kennzahlen und Signal-Stand `20261025T104649Z` neu bereitgestellt. Nebenbefund (nicht geändert, außerhalb dieses Auftrags): die Meldung „11025 von 11006 Aktien mit Kennzahlen“ zählt im ersten Wert alle gespeicherten Kennzahlen, im zweiten nur die derzeit berücksichtigten Aktien (`backend/traktien/jobs/facts.py`) – eine Ungenauigkeit der Meldung, keine Wirkung auf Daten oder App |
| GitHub Actions, 25.10.2026 11:23–11:36 Uhr (MEZ) | **Ursachen – zweiter Lauf (Commit `09bc9e1`):** [40184599190](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40184599190); „Prüfung“ ([40184592102](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40184592102)) | **Prüfung:** 738 Tests, 716 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. **Ursachen:** alle fünf Jobs rot, Zahlen wie im endgültigen Lauf (8e); **Befunde Nr. 18–21** – behoben in `2fc32d3` |
| GitHub Actions, 25.10.2026 10:44–10:54 Uhr (MEZ) | **Ursachen – erster Lauf mit dem neuen Code (Auftrag 09:20 Uhr):** dieselbe Prüfung mit Commit `438b2e1` ([40181869022](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40181869022)); „Prüfung“ ([40181859911](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40181859911)) | **Prüfung:** 728 Tests, 706 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. **Ursachen:** alle fünf Jobs rot; **Fehler des Prüfskripts gefunden** (8e, Nr. 10–17): Plätze der Aktien außerhalb der US-Auswahl im gemeinsamen Job mit 0, Namensprüfung als „nur Hinweis“ beschriftet, Abstand zu `quoteTime` als „Abfrage minus Zeitstempel“, nordische Gattungen bei OpenFIGI als anderes Kürzel, Lücken ohne Börse und Grund, 42 von 86 Teilen der Hinweise nicht ausgegeben – behoben in `09bc9e1` |
| Entwicklungsumgebung, 25.10.2026 09:46–11:29 Uhr (MEZ) | **Auftrag 09:20 Uhr:** Ursachen streng nach Beleglage, Absicherung jeder Zuordnung (OpenFIGI, Wertpapierliste von Nasdaq Trader, Kursmeldung von CNBC), exakte Suche der kleinsten Auslösermenge, (b)+(c) gemeinsam mit Wechselwirkung, Quelle je Aktie und Tag, Job „welt“, Abdeckung des ganzen Universums; Befunde Nr. 1–17 (8e) | 40 neue Tests (`438b2e1`: 30, `09bc9e1`: 10); drei Tests der alten, zu großzügigen Einordnung durch strengere ersetzt (8e); Python-Gesamtlauf mit `09bc9e1` (11:17–11:29 Uhr): 738 Tests, 712 bestanden, 26 Live-Tests übersprungen, 0 fehlgeschlagen |
| GitHub Actions, 25.10.2026 05:30–05:42 Uhr (MEZ) | **Ursachen – Abschluss des Auftrags 03:47 Uhr:** „App mit echten Daten prüfen“ mit „Ursachen“ und „ursachen_stand“ = `2026-10-23_3f7ce5f3` ([40162120622](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622)), drei Prüfjobs und Job „gemeinsame Wirkung“; „Prüfung“ des Commits `88d2733` ([40162120203](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120203)) | **Prüfung:** 698 Tests, 676 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. **Ursachen:** alle vier Jobs „UNVOLLSTÄNDIG“ (rot) – 0 Aktien ohne Antwort, 397 von 404 verglichen (366 mit Nasdaq, 31 mit CNBC), 7 ohne Vergleichskurse; gegen die Nasdaq-Historie 630 Tage abweichend, 49 belegt, 581 ungeklärt; gemeinsam Platz 1 nur mit dem offiziellen Schlusskurs in 4 Ranglisten anders, jedes Mal allein durch Z31 über die Ränge (Score und Lage jetzt im Hinweis); der letzte Abschluss bei OTC Markets jetzt am richtigen Handelstag: gleich dem Stand bei 22, abweichend bei 3 Aktien (8e). **Einordnung überholt** (Auftrag 09:20 Uhr, 8e): die „49 belegt“ sind plausible Erklärungen, keine belegten Ursachen; der „richtige Handelstag“ des OTC-Abschlusses ist nicht belegt |
| GitHub Actions, 25.10.2026 04:28–05:27 Uhr (MEZ) | **Ursachen, vier Läufe zum Auftrag 03:47 Uhr:** [40158331688](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40158331688) (`a1bcf79`), [40159274087](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40159274087) (`0c6f17c`), [40160248028](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40160248028) (`9a76490`), [40161469772](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40161469772) (`0b7d8e8`); „Prüfung“ dieser Commits ([40158314030](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40158314030), [40159274118](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40159274118), [40160248076](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40160248076), [40161465519](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40161465519)) | „Prüfung“ jedes Mal grün (zuletzt 697 Tests, 675 bestanden, 22 übersprungen). Wirkung auf die Ranglisten in allen vier Läufen gleich, „dieselbe Wirkung“ wie 40139805053. **Fehler des Prüfskripts gefunden und behoben**, je im nächsten Commit: „Nasdaq-Historie = letzter Abschluss“ als Beleg auch dort, wo die Nasdaq-Historie der offizielle Schlusskurs ist (12 Tage), Auslöser nicht als kleinste Menge, Feldnamen der Kursmeldung von OTC Markets fehlten (→ `0c6f17c`); Suche nach der Schreibweise einer Gattung bei Nasdaq brach nach HTTP 404 ab, letzter OTC-Abschluss mit dem Zeitpunkt der Abfrage (→ `9a76490`); neuer Platz 1 ohne Score und ohne Lage des Auslösers, obwohl die Spitzenreiter ihre Werte behielten (→ `0b7d8e8`); Tag des letzten OTC-Abschlusses nach UTC statt nach dem Handelstag in New York – alle Zeitstempel 0 Uhr UTC, also 20 Uhr New York am 23.10. (→ `88d2733`) |
| Entwicklungsumgebung, 25.10.2026 03:50–05:41 Uhr (MEZ) | **Auftrag 03:47 Uhr:** drei Prüfjobs mit verschlüsselter Übergabe der Vergleichskurse, Job „gemeinsame Wirkung“ mit Gegenprobe gegen 40139805053, Zusatzquellen mit Prüfung vor jedem Vergleich, fünf Ergebnisarten (Befund getrennt von belegter Ursache), kleinste Menge der Auslöser, Score und Lage je neuem Platz 1, Handelstag nach Ortszeit New York | 31 neue Tests (29 Unit-, 2 Integrationstests), u. a.: Übergabe nur für denselben Stand und Job zu öffnen, gemeinsame Rechnung = ein Job mit allen Aktien, Befund „Nasdaq = NOCP“ ohne Beleg, Auslöser über eine dritte Aktie mit Score und Lage, Handelstag 20:30 Uhr New York. Python-Gesamtläufe: 693 Tests (`0c6f17c`, 04:43–04:54 Uhr: 667 bestanden), 697 (`0b7d8e8`, 05:19–05:29 Uhr: 671 bestanden), 698 (`88d2733`, 05:30–05:41 Uhr: 672 bestanden) – je 26 Live-Tests übersprungen, 0 fehlgeschlagen |
| GitHub Actions, 25.10.2026 00:44–00:57 Uhr | **Ursachen, sechster Lauf – Ergebnis:** „App mit echten Daten prüfen“ mit „Ursachen“ ([40139805053](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805053)), zwei Jobs; „Prüfung“ des Commits `e90bad7` ([40139805255](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805255)) | **Prüfung:** 667 Tests, 645 bestanden, 22 Live-Tests übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. **Live-Prüfung:** App `1.18.2+3a4bd974`, 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. **Ursachen:** beide Jobs „UNVOLLSTÄNDIG“ (rot) – 0 Aktien ohne Antwort, 38 ohne Vergleichskurse, 326 von 630 abweichenden Tagen ungeklärt; mit dem offiziellen Schlusskurs Platz 1 in 4 Ranglisten anders, jede ausgelöst allein durch die Kurse der Aktie Q; alle 13 bzw. 5 Teile als Hinweis ausgegeben (8e) |
| GitHub Actions, 25.10.2026 00:29–00:40 Uhr | **Ursachen, fünfter Lauf** ([40138800418](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40138800418)), erstmals in zwei Jobs; „Prüfung“ des Commits `d634391` ([40138800271](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40138800271)) | Prüfung: 666 Tests, 644 bestanden, 22 übersprungen, 0 fehlgeschlagen. Ursachen: 0 Aktien ohne Antwort (erste 20: 430 Anfragen an Nasdaq, Zufallsstichprobe: 223); **zwei Fehler der Ausgabe gefunden** – die Lage der Nasdaq-Historie hieß „ein dritter Kurs“ auch bei gleichem Stand, und im zweiten Job standen die US-Aktien unter den ersten 10 als „ohne Nasdaq-Kurse“ –, behoben in `e90bad7` (Zeile oben) |
| GitHub Actions, 24.10.2026 23:45 Uhr bis 25.10.2026 00:25 Uhr | **Ursachen, vierter Lauf** ([40135600271](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40135600271)); „Prüfung“ der Commits `c27d225` ([40135600155](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40135600155)) und `4cd1976` ([40137499223](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40137499223)) | Prüfung: 656 Tests (634 bestanden) bzw. 665 Tests (643 bestanden), je 22 übersprungen, 0 fehlgeschlagen. Ursachen: **unvollständig** – alle 121 Aktien ohne Antwort aus der Zufallsstichprobe (erste 10 und Plätze 11–20 vollständig); Nasdaq antwortete **nach 430 Anfragen nicht mehr**, auch nicht nach zwei Pausen von 180 s und mit 3 s Abstand – deshalb zwei Jobs auf zwei Rechnern (8e) |
| Entwicklungsumgebung, 24.10.2026 23:35 Uhr bis 25.10.2026 00:45 Uhr | **Ursachen-Prüfung erweitert** (Aufträge 21:23 Uhr, Punkt 2, und 23:50 Uhr): Abruf nach Bedeutung, Sperrpause, Abdeckung je Gruppe, jede Rangliste mit neuem Platz 1 einzeln mit Auslösern, Zuordnung der Buchstaben, Prüfgrenze getrennt von der Ursache, verlustfreie Hinweise (Fit-to-10 auf fünf Schritte verteilt), zwei Jobs | 15 neue Tests (12 Unit-, 3 Integrationstests), u. a.: über 50 Hinweise und Zeilen über 9.000 Zeichen – höchstens 9 je Art und Schritt, 45 je Job, jeder Teil ausgegeben oder im letzten Hinweis gezählt, ohne Textverlust geteilt, Zusammenfassung vollständig; ein neuer Platz 1, den eine dritte Aktie über die Ränge auslöst; fehlende Vergleichskurse machen das Urteil „unvollständig“; Fundstelle von A ist die Aktie A. Python-Gesamtlauf 00:11–00:20 Uhr: 665 Tests, 639 bestanden, 26 Live-Tests übersprungen, 0 fehlgeschlagen; mit dem letzten Stand (00:59–01:08 Uhr): 667 Tests, 641 bestanden, 26 übersprungen, 0 fehlgeschlagen |
| GitHub Actions, 24.10.2026 23:09–23:31 Uhr | **Ursachen, dritter Lauf** (im Lauf [40132947135](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132947135)) | **unvollständig** – 121 Aktien ohne Antwort von Nasdaq, auch nach 30 und 90 s; erste 10 vollständig; mit dem offiziellen Schlusskurs Platz 1 in 4 Ranglisten anders, ohne Angabe welcher (8e) |
| GitHub Actions, 24.10.2026 23:00–23:17 Uhr | **Abnahme der ausgelieferten Version 1.18.2** (Commit `fbe62ad`): „Prüfung“ ([40132325646](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132325646)), „Nur die Website neu bereitstellen“ ([40132945105](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132945105)), „App mit echten Daten prüfen“ mit „Weitere Browser“ und „Android“ ([40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565)), „Android-Emulator prüfen“ ([40133048985](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133048985)) | **Alle Jobs grün.** Prüfung: 652 Tests, davon 630 bestanden und 22 Live-Tests übersprungen, Kalender 4 von 4. Bereitstellung: „App 1.18.2+3a4bd974 neu zusammengesetzt; Datenstand unverändert“. Live: Chromium 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten, Installation bestanden; Firefox und WebKit je 24 von 24 Ansichten (Installation dort übersprungen); Chrome für Android im Emulator 24 von 24 Ansichten, Neustart im Flugmodus bestanden; Nachrechnung 23.10. 0 Abweichungen in 9.987.000 Prüfungen. Emulator: veröffentlichte Website installiert (Web-App-Verknüpfung), Neustart ohne Netz, DEMO ohne Verschiebung; Systemschrift „nicht prüfbar“ (Chrome 124 kennt das Opt-in nicht) |
| GitHub Actions, 24.10.2026 22:08–23:08 Uhr | **Nach den Korrekturen:** „App mit echten Daten prüfen“ mit „Kurse“ und „Ursachen“ ([40128434473](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128434473)), zweimal „Android-Emulator prüfen“ mit Kontrollseiten für die Systemschrift ([40128638092](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128638092), [40129482881](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40129482881)) | **Live-Prüfung** der ausgelieferten App `1.18.1+7e61c801`: grün (24 von 24 Ansichten). **Kurse:** „NICHT bestätigt – Abweichungen nur wie Yahoo“, Job rot (dieselben Zahlen wie um 19:59 Uhr, 8e). **Ursachen:** nach 60 Minuten von GitHub abgebrochen (Zeitgrenze des Jobs, 22:08–23:08 Uhr), **ohne Ergebnis**; der Grund ist nicht belegt (der Job schrieb bis dahin keinen Fortschritt ins Protokoll), naheliegend sind die langen Wartezeiten bei Verbindungsfehlern (bis zu 4 × 25 s je Anfrage). Deshalb in 1.18.2 (Commit `4439618`): Zeitbudget für den Abruf, kurze Zeitgrenzen, Fortschritt im Protokoll; neuer Lauf in 8e. **Emulator:** Systemschrift 130 % wirkt auf Kontrollseiten (16 → 20,8 px, auch mit `text-size-adjust: 100%` und mit kurzen Texten in Karten) und auf einen langen Absatz in der App, nicht auf die Texte der App – gefunden und in 1.18.2 behoben, soweit prüfbar (8b); sonst wie zuvor (Installation, offline, hoch und quer) |
| Entwicklungsumgebung und GitHub Actions, 24.10.2026 22:30–23:00 Uhr | **Version 1.18.2** – Systemschrift übernehmen (`<meta name="text-scale" content="scale">`) und große Schrift bis 200 % | Neuer Browser-Test `test_system_text_scale_up_to_200_percent_fits_the_phone` (Grundschrift 130/150/175/200 % in 33 Ansichten): lokal zuerst **rot** – bei 200 % Musterdepots, Alle Aktien, Umschichtungs-Regel, Hilfe und Methodik zu breit, die Einzelansicht „Überblick“ schon bei 175 % –, nach der ersten Korrektur lokal grün (76 Browser-Tests, 22:38–22:41 Uhr). **In GitHub Actions trotzdem rot** („Prüfung“ [40130897692](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40130897692), Commit `4439618`): dort löst die Systemschrift breiter auf, 8 Ansichten waren bei 200 % zu breit. Deshalb misst der Test seitdem mit der breiten Schrift „DejaVu Sans“ (auf beiden Rechnern vorhanden) – damit lokal ebenfalls rot, nach der zweiten Korrektur (Umbruch langer Wörter im ganzen Inhaltsbereich, einspaltige Raster begrenzt, Kennzeichen umbrechend; in Tabellen wie bisher) grün. Die erste Fassung war **nicht ausgeliefert**. App: Typprüfung ohne Fehler, 104 Tests (88 bestanden, 16 über Python) |
| GitHub Actions, 24.10.2026 21:32–21:52 Uhr | **Auftrag 21:23 Uhr, erste Läufe:** „App mit echten Daten prüfen“ mit „Originalstände“ ([40125726864](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40125726864), nach der Korrektur [40126000729](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126000729)) und mit „Ursachen“ ([40126582787](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126582787)), zweimal „Kurslauf kontrollieren“ mit der neuen Tempo-Anzeige ([40126752930](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126752930), [40126755036](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126755036)), „Android-Emulator prüfen“ ([40126757215](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126757215)), „App mit echten Daten prüfen“ ohne Zusätze ([40127012179](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40127012179)) | **Originalstände 12.10.:** im ersten Lauf 170 Abweichungen für `5092bae0` – Fehler der Prüfung (geduldete fehlende Sitzung auch bei Ständen bis 1.5.0), behoben; danach alle drei Stände = damaliger Lauf und reproduziert, fachlich korrekt nein (8c). **Ursachen, erster Lauf:** 71 von 404 Aktien ohne Antwort von Nasdaq (Verbindungsfehler), Job trotzdem grün – Nachholrunden eingebaut und Urteil verschärft (8e). **Kurslauf-Kontrolle:** NICHT BESTANDEN bzw. AUSSTEHEND wie erwartet, Tempo jetzt mit allen Mindestanforderungen (8f). **Emulator:** Systemschrift trotz Neustart von Chrome ohne Wirkung (8b). **Live-Prüfung:** in 40126582787 scheiterte `test_6` einmal am Netz des Rechners (`net::ERR_SOCKET_NOT_CONNECTED` beim Aufruf der Website); im nächsten Lauf 40127012179 bestanden – 11 Tests, 10 bestanden, `test_2d` übersprungen, 24 von 24 Ansichten, App `1.18.1+7e61c801` |
| Entwicklungsumgebung, 24.10.2026 21:25–22:40 Uhr | **Auftrag 21:23 Uhr** – Originaldaten vom 12.10. gesucht (8c), Ursachen-Prüfung gebaut und verschärft (8e), Prüfstatus getrennt (oben, 8f), Geräteprüfungen getrennt (8b), Nachkontrolle 27.10. geprüft (8) | Python-Gesamtlauf 21:50–22:00 Uhr: **632 Tests, 606 bestanden** (26 Live-Tests übersprungen, 0 fehlgeschlagen); danach 17 Tests ergänzt (Nachholrunden mit Gegenprobe ohne Nachholrunden – rot, Stand = NOCP, Anzeigegenauigkeit, Faktor eines Splits im NOCP, neue Urteile der Kurs-Gegenprüfung, Systemschrift-Urteil im Emulator) – Python-Gesamtlauf 22:46–22:56 Uhr: **652 Tests, 626 bestanden** (26 Live-Tests übersprungen, 0 fehlgeschlagen) |
| GitHub Actions, 24.10.2026 20:49–21:05 Uhr | **Abnahme der ausgelieferten Version 1.18.1** (Commit `17c572d`): „Prüfung“ ([40122471990](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40122471990), 611 Tests, 22 Live-Tests übersprungen, Kalender 4 von 4), „Nur die Website neu bereitstellen“ ([40123094702](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123094702): „App 1.18.1+7e61c801 neu zusammengesetzt; Datenstand unverändert“), „App mit echten Daten prüfen“ mit allen Zusätzen ([40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068)), „Android-Emulator prüfen“ ([40123184881](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123184881)) | **Alle Jobs grün.** App `1.18.1+7e61c801`, Stand `2026-10-23_3f7ce5f3`: **Chromium 141** 24 von 24 Ansichten (Breite jetzt gegen die Gerätebreite geprüft), Installation bestanden; **Firefox 142** und **WebKit 26** je 24 von 24 Ansichten, entsperrt, Einzelansichten und Signale, erneut geöffnet ohne Passphrase (Installation dort übersprungen – zählt nicht als bestanden); **Android-Emulator mit echten Daten** 24 von 24 Ansichten, **Neustart im Flugmodus bestanden** (ohne Passphrase, Kursstand nach 1,2 s, „Offline – gespeicherter Stand“, Rangliste 10 Zeilen), 0 Konsolenfehler; Emulator mit DEMO-Daten grün (installiert, offline, hoch und quer ohne Überbreite). Nachrechnung: 13.10. reproduziert ja / fachlich korrekt nein (1.280 bekannte Fälle, Ursachen behoben), 23.10. reproduziert und korrekt (0 Abweichungen in 9.987.000). Kurse: damals „bestanden mit Unterschieden zwischen den Anbietern“ (alle Abweichungen = Yahoo, Stand = Yahoo an 18.764 von 18.764 Tagen) – seit 22 Uhr „nicht bestätigt“, weil „wie Yahoo“ kein unabhängiger Nachweis ist (8e). `test_2d` in allen drei Browsern übersprungen (kein Zwischenstand am Wochenende) |
| Entwicklungsumgebung, 24.10.2026 20:02–20:50 Uhr | **Version 1.18.1 – Fehler nachgestellt, behoben, alle Tests** | **Ohne Netz nach dem ersten Besuch:** neuer Browser-Test `test_offline_restart_after_a_single_first_visit` (eigener Server, nach dem Besuch abgeschaltet, dazu offline) – mit dem ausgelieferten Build `1.18.0+134e25da` **rot**: „Keine Internetverbindung“, im Speicher des Service Workers nur `windows/30.bin` (Status, Index, Schlüsselparameter, Kerndateien und Signale fehlten); mit 1.18.1 **grün**: alle diese Dateien gespeichert, Startseite mit Kursstand, Kandidaten und Rangliste ohne Netz, keine Passphrase. **Überbreite:** neuer Browser-Test `test_status_with_an_older_stand_of_another_method_fits_the_phone` vorher **rot** (482 statt 384 px, `innerWidth` wuchs mit), danach grün; die Prüfungen messen jetzt gegen die Gerätebreite. Python-Gesamtlauf 20:08–20:18 Uhr: 606 Tests, 580 bestanden (26 Live-Tests übersprungen, 0 fehlgeschlagen); danach 428 Unit-Tests, 19 Integrationstests der Nachrechnung und **75 Browser-Tests** (20:43–20:45 Uhr, mit den strengeren Breitenprüfungen) bestanden; App: Typprüfung ohne Fehler, 104 Tests (88 bestanden, 16 Datenvertragstests über Python) |
| GitHub Actions, 24.10.2026 20:20–20:41 Uhr | **Version 1.18.1, erste Fassung** (Commit `7d29210`): „Prüfung“ ([40120262257](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40120262257), 610 Tests, 22 Live-Tests übersprungen, Kalender 4 von 4), „Nur die Website neu bereitstellen“ ([40121197416](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40121197416): „App 1.18.1+01171ab1 neu zusammengesetzt; Datenstand unverändert“), danach „App mit echten Daten prüfen“ mit Android, Kurse und Weitere Browser ([40121306096](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40121306096)) und „Android-Emulator prüfen“ ([40121308134](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40121308134)) | **Behoben und bestätigt – Neustart ohne Netz mit echten Daten im Android-Emulator:** „bestanden“ – Service Worker vorher und danach aktiv, Browser offline, **ohne erneute Passphrase**, Kursstand nach 1,1 s, Hinweis „Offline – gespeicherter Stand“, Rangliste aus dem Speicher 10 Zeilen; 24 von 24 Ansichten, 0 Konsolenfehler, 0 fehlgeschlagene Abrufe. Chromium: 24 von 24 Ansichten (App `1.18.1+01171ab1`), `test_2d` übersprungen. Nachrechnung und Kurs-Gegenprüfung wie zuvor (8d, 8e; die Titel der Hinweise jetzt vollständig). Emulator mit DEMO-Daten grün. **Neu gefunden mit Firefox 142 und WebKit 26:** „Datenstand & Betrieb“ 179 bzw. 90 px breiter als der Bildschirm (sonst 23 von 24 Ansichten ohne Fehler, Entsperren, Einzelansichten, Signale und erneutes Öffnen ohne Passphrase bestanden). Ursache: der Hinweis „eingeschränkt vergleichbar …“ ohne Umbruch – mit dem echten Datenstand (23.10. auch nach Methode 1.9.0) auch in Chromium 98 px zu breit, dort aber verdeckt, weil `window.innerWidth` mitwächst – behoben (Zeile oben) |
| GitHub Actions, 24.10.2026 19:57–20:01 Uhr | **„App mit echten Daten prüfen“ mit „Android“ und „Kurse“** (Commit `81b819a`, [Lauf 40118442565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40118442565)) – ausgelieferte App `1.18.0+134e25da`, Stand `2026-10-23_3f7ce5f3` | **Live-Prüfung:** 11 Tests, 10 bestanden, `test_2d` übersprungen (kein Zwischenstand – zählt nicht als bestanden), 24 von 24 Ansichten. **Nachrechnung:** wie unten (8d). **Kurse (nachträglich bei Nasdaq, Gegenprobe Yahoo):** bestanden mit Unterschieden zwischen den Anbietern – alle 571 abweichenden Tage und 618 abweichenden Renditen sind die Kurse von Yahoo, der Stand gleicht Yahoo an 18.764 von 18.764 Tagen (8e). **Android-Emulator mit echten Daten:** 24 von 24 Ansichten ohne Fehler, entsperrt in 3,0 s; **Neustart ohne Netz nicht bestanden:** richtiger Tab (einziger, mit Marke), Service Worker aktiv, Browser offline – die App zeigte „Keine Internetverbindung“ statt des gespeicherten Stands. **Fehler der App** (seit 1.15, erster Besuch ohne Neuladen): die vor der Übernahme durch den Service Worker geladenen Dateien lagen nicht in seinem Speicher, Signale nie – behoben in 1.18.1 (nächste Zeile oben) |
| GitHub Actions, 24.10.2026 19:36–19:49 Uhr | **Nach den Änderungen für die Aufträge von 19:07 und 19:29 Uhr** (Commits `abc553b` und `d4ec240`): „Prüfung“ ([40116903623](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116903623), [40117291992](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40117291992)), „App mit echten Daten prüfen“ mit Android und Kurse ([40116911344](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116911344)), nur Kurse ([40117299760](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40117299760)), „Android-Emulator prüfen“ ([40116912958](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116912958)), zweimal „Kurslauf kontrollieren“ ([40116914676](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116914676), [40116916313](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116916313)) | „Prüfung“ beide grün. **Nachrechnung:** Stand 13.10. reproduziert ja (9.649.807 Prüfungen, 0 Abweichungen), fachlich korrekt nein (1.280 bekannte Fehlerfälle), beide Ursachen in der aktuellen Version behoben; Stand 23.10. reproduziert und fachlich korrekt (8d). **Kurse:** zweimal rot – 136 große Abweichungen zu Nasdaq bei 5 Aktien, 618 abweichende Renditen; erst die Gegenprobe bei Yahoo (Zeile oben) zeigte, dass es die Kurse des Anbieters sind. **Android mit echten Daten:** 24 von 24 Ansichten, Neustart ohne Netz mit Zeitüberschreitung ohne Angabe des Zustands – deshalb die Prüfung erweitert (Marke, Zustand). **Emulator (DEMO):** grün; Systemschrift 130 % wirkt in diesem Chrome nicht auf die Seite (Textzeile 57,5 → 58,2 px, Schrift 16 px) – große Schrift weiter nur in der Desktop-Emulation geprüft. **Kurslauf-Kontrolle:** „NICHT BESTANDEN“ bzw. „AUSSTEHEND“, beide Läufe rot, das Prüfskript lief jeweils fehlerfrei (8f) |
| GitHub Actions, 24.10.2026 18:17–18:29 Uhr | **Nach den Korrekturen (Commit `19c6c74`):** „Prüfung“ ([40110861055](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110861055)), „Datenquellen prüfen“ ([40110875450](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110875450)), „App mit echten Daten prüfen“ ([40110877738](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110877738)) und zweimal „Kurslauf kontrollieren“ mit dem neuen Skript ([40110879657](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110879657), [40110881863](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110881863)) | Prüfung (18:17–18:28 Uhr): **568 Tests, 546 bestanden, 22 übersprungen** (nur noch die Live-Prüfungen mit eigenen Workflows, jede mit Namen), 0 fehlgeschlagen; Börsenkalender 4 von 4. Lokal danach erneut: 390 Unit-Tests (keiner übersprungen), 79 Integrationstests und die 4 Browser-Tests des Zwischenstands bestanden. Datenquellen: **15 Tests, 14 bestanden, 1 übersprungen** (EODHD), 0 fehlgeschlagen – die Liste je Test ist jetzt vollständig (`test_close_times_in_utc` bestanden). App: ausgeliefert **`1.18.0+134e25da`** (unverändert, App und Server wurden nicht geändert), Datenstand `2026-10-23_3f7ce5f3` (Kursstand 23.10., vollständig), Signal-Stand `20261024T150300Z`, 24 von 24 Ansichten ohne Fehler, **11 Tests: 10 bestanden, 1 übersprungen** (`test_2d`, kein Zwischenstand), 0 fehlgeschlagen; Nachrechnung Stand 23.10.: 9.987.000 Prüfungen, Stand 13.10.: 9.649.807 Prüfungen, je **0 Abweichungen**. Kontrolle in GitHub Actions: Lauf 40104747674 (von Hand, erzwungen) – `status.json` nennt den Stand `2026-10-23_3f7ce5f3` als neuesten, den nächsten Kursstand 26.10. ab 22:00 UTC und Signale zum Kursstand 23.10. (beide neuen Kriterien erfüllt); Urteil „nicht bestanden“, weil von Hand und nur 49 Notierungen offen. Lauf 40085906898 – „nachtlauf ohne zeitplan (Nachtlauf 40085893661, Auslöser workflow_dispatch)“, nicht bestanden |
| Entwicklungsumgebung, 24.10.2026 18:00–18:40 Uhr | **Offene Prüfungen abgeschlossen, soweit jetzt ausführbar** (Auftrag 17:38 Uhr): die 23 übersprungenen Tests einzeln geklärt (Abschnitt 8a), Prüffall 12.10. abgegrenzt (8c), Zeitplan des Nachtlaufs geprüft (8), Emulator und echtes Gerät getrennt (8b) | **Vier Fehler gefunden und behoben:** (1) Die Liste „je Test“ im Lauf „Datenquellen prüfen“ ließ `test_close_times_in_utc` aus (14 statt 15) – Auswertung erkennt den Testnamen jetzt auch hinter einem Bericht ohne Zeilenumbruch, gleicht mit „Ran N tests“ ab und warnt bei Lücken; Prüf-Workflows ungepuffert (3 Tests, einer mit echtem gepuffertem unittest-Lauf). (2) Tabelle in 12_Fehlende_Kurstage: R² von C stand als 0,99692 statt 0,99691 (doppelt gerundet) – korrigiert; die Hilfsausgabe `test_print_tables` ist durch die Prüfung `DocumentedTable` ersetzt, die die Tabelle in jedem Lauf gegen die unabhängige Rechnung prüft (2 Tests, einer als Gegenprobe). (3) Die Kurslauf-Kontrolle hätte einen **von Hand** gestarteten Nachtlauf als zeitgesteuert gezählt – jetzt zählt nur ein Nachtlauf mit Auslöser „schedule“; mit echtem Lauf 40085906898 gegengeprüft: „nachtlauf ohne zeitplan“, nicht bestanden (1 Test). (4) Die Kontrolle prüft zusätzlich, dass `status.json` den neuen Stand als neuesten nennt und **Signale zum neuen Kursstand** (1 Test). Dazu Test für den Termin 26.10., 23:37 Uhr MEZ. Python lokal: 565 Tests in einem Lauf (539 bestanden, 26 übersprungen: 22 Live-Prüfungen, 4 Kalendertests ohne `exchange_calendars`, 0 fehlgeschlagen), die 3 danach ergänzten Tests einzeln bestanden |
| GitHub Actions, 24.10.2026 17:52–18:03 Uhr | **„Prüfung“** (Commit `e6a96b2`, [Lauf 40108944849](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108944849)), **„Datenquellen prüfen“** ([40108950043](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108950043)) und **„App mit echten Daten prüfen“** ([40108951837](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108951837)) – Ergebnis je Test in der Laufübersicht | Prüfung: 561 Tests, **538 bestanden, 23 übersprungen** (jetzt mit Namen), 0 fehlgeschlagen; Kalender 4 von 4. Datenquellen: 15 Tests, **14 bestanden, 1 übersprungen** (EODHD ohne Freigabe) – die Liste je Test nannte nur 14 (Fehler 1 oben). App: 11 Tests, **10 bestanden, 1 übersprungen** (`test_2d`: kein Zwischenstand); App `1.18.0+134e25da`, Datenstand `2026-10-23_3f7ce5f3`, 24 von 24 Ansichten ohne Fehler, Signal-Stand `20261024T150300Z`. Nachrechnung: Stand 23.10. 9.987.000 Prüfungen, Stand 13.10. 9.649.807 Prüfungen, je **0 Abweichungen** (13.10. dazu die bekannten Fehler von 1.6.0) |
| GitHub Actions, 24.10.2026 17:28–17:35 Uhr | **Abnahme der ausgelieferten Version 1.18.0** – „App mit echten Daten prüfen“ (17:28–17:31) und „Android-Emulator prüfen“ (17:28–17:35) nach der Bereitstellung | **Alles in Ordnung:** App `1.18.0+134e25da`, Datenstand `2026-10-23_3f7ce5f3` (vollständig, 3 aufbewahrte Stände), **24 von 24 Ansichten ohne Fehler**, keine fehlgeschlagenen Abrufe, Signale mit Einzelansicht. **Nachrechnung** Stand 23.10.: **9.987.000 Prüfungen, 0 Abweichungen**, Wirkung des exakten Gleichstands wie im Manifest (Platz 1: 4, erste 10: 4/65 von 1.640). **Android** (Emulator, Chrome 124): installiert als Web-App-Verknüpfung, Start vom Startbildschirm im eigenen Fenster, Neustart ohne Netz mit Sperrbildschirm, TalkBack: Chromes Barrierefreiheits-Baum ohne unbenannte Bedienelemente |
| GitHub Actions, 24.10.2026 17:18–17:28 Uhr | **„Prüfung“ des Commits `3b6b607`** und **„Nur die Website neu bereitstellen“** | 558 Tests bestanden (23 übersprungen), Kalender 4 von 4; Bereitstellung 17:27–17:28: „App 1.18.0+134e25da neu zusammengesetzt; Datenstand unverändert (3 veröffentlichte Stände)“ |
| GitHub Actions, 24.10.2026 17:08–17:10 Uhr | **„App mit echten Daten prüfen“, zweiter Lauf** (nach der Bereitstellung der Signale) – ausgelieferte Version mit dem neu gerechneten Stand | **Alles in Ordnung:** App `1.18.0+e3048568`, Datenstand `2026-10-23_3f7ce5f3` (vollständig, 3 aufbewahrte Stände), **24 von 24 Ansichten ohne Fehler**, Signale (Stand `20261024T150300Z`) mit Einzelansicht. **Nachrechnung:** Stand 23.10. (Software 1.18.0, Methode 1.10.0) **9.987.000 Prüfungen, 0 Abweichungen**; Wirkung des exakten Gleichstands nach eigener Rechnung Platz 1: 4, erste 10: 4 (Aktien) bzw. 65 (nur Reihenfolge), irgendein Platz: 1.308 von 1.640 Ranglisten – **wie im Manifest** (`methodenwechsel_wirkung`). Prüffall-Stand 13.10. (Software 1.6.0): 9.649.807 Prüfungen, 0 Abweichungen, dazu als bekannte Fehler 1.278 × `gleichstand_rundung` (alle gemischten Ranglisten) und 2 × `reihe_vorhanden` – damaliges Verhalten bestätigt, fachlich falsch, Stand unverändert |
| GitHub Actions, 24.10.2026 17:04–17:07 Uhr | **„App mit echten Daten prüfen“, erster Lauf** – gestartet, während der Lauf noch die Signale bereitstellte (17:05 Uhr) | Nachrechnung 0 Abweichungen (wie oben). Live-Prüfung: 24 von 24 Ansichten ohne Fehler, aber **zwei Abrufe mit 404**: Signal-Dateien des eben ersetzten Signal-Stands (Einzelansicht und Signale). Ursache: Die App hatte den alten Signal-Stand geladen; bis zur nächsten Statusprüfung zeigte die Einzelansicht „Datei nicht gefunden“. **Behoben in 1.18.0:** Die Einzelansicht lädt dann den Status neu und zeigt den neuen Stand (Browser-Test `test_signal_details_follow_a_newly_deployed_signal_stand`) |
| GitHub Actions, 24.10.2026 17:03–17:04 Uhr | **„Fehlende Kurstage auswerten“ auf dem neuen Stand** `2026-10-23_3f7ce5f3` (Software 1.18.0, Methode 1.10.0) | Ranglisten des Skripts = veröffentlichte: **1.980 von 1.980**. Gleichstand: 336 gemischte Ranglisten mit rechnerisch gleichen Scores an der Spitze, **0** mit der niedrigeren Rendite vorn (bis 1.9.0: 69), exakter Vergleich = veröffentlicht in allen. Einfluss anderer Lückenregeln jetzt: streng Platz 1: 1 (bis 1.9.0: 7), erste 10: 31/34; wie Ausgangsmodell 0 (7), 3/3; ohne letzten Schlusskurs 0 (9), 2/14. Bestand unverändert (2.864 Paare mit Lücke, 14 Leerzeilen bei 8 Aktien, keine Aktie mit Lücke auf Platz 1) |
| GitHub Actions, 24.10.2026 16:57–17:05 Uhr | **Täglicher Lauf von Hand, erzwungen** (Stand mit Schlusskursen, „Neu berechnen“), um den 23.10. mit Methode 1.10.0 zu rechnen | **Stand `2026-10-23_3f7ce5f3` vollständig veröffentlicht** (Rechnung 16:57–17:01, Website 17:03, Kennzahlen bis 17:05, Signale bereitgestellt 17:05). Kurse aus dem Checkpoint des Laufs von 13:41 Uhr (49 Notierungen ohne Stichtagskurs erneut abgefragt) – dieselben Werte wie `2026-10-23_68f9fbe5`; dieser Stand (Methode 1.9.0) bleibt unter „Frühere Stände“ erhalten |
| GitHub Actions, 24.10.2026 16:39–16:50 und 16:45–16:56 Uhr | **„Prüfung“ der Commits `b2c0ddf` und `d7f5550`** (Version 1.18.0) | je **557 Tests bestanden** (23 übersprungen: 22 Live-Prüfungen mit Secrets, die Tabellenausgabe für die Doku), echte Börsenkalender 4 von 4, App-Build identisch |
| Entwicklungsumgebung, 24.10.2026 16:10–16:40 Uhr | **Version 1.18.0 – alle Tests** (Gleichstand exakt, Kennzeichnung fehlender Kurstage) | Python: **380 Unit-Tests** (1 übersprungen: Tabellenausgabe für die Doku), **79 Integrationstests** (darunter der Datenvertrag der App gegen echt erzeugte DEMO-Stände und die Nachrechnung), **72 Browser-Tests** auf simuliertem S25+ – alle bestanden; mit dem Browser-Test zur neuen Bereitstellung der Signale (17:20 Uhr) 73 von 73. App: **104 Tests** (88 bestanden, 16 Datenvertragstests über Python bestanden), Typprüfung ohne Fehler, Build `1.18.0+1da24bee`. Ein Zwischenlauf hatte zwei Fehler, beide in Tests, die noch die Methode 1.9.0 erwarteten (Datenvertrag, Zählung der verglichenen Ranglisten ohne die leeren); die Tests wurden angepasst, der Code blieb |
| Entwicklungsumgebung, 24.10.2026 16:15–16:35 Uhr | **Referenzfälle Gleichstand** (`tests/unit/test_referenz_gleichstand.py`, 11 Tests; Erwartung unabhängig mit exakten Brüchen) und **Gegenprobe** mit drei absichtlich falschen Regeln | bestanden: Platz 1 (15 Aktien), Grenze der ersten 10 (20 Aktien, dazu Plätze 5/6), gleicher Score und gleiche Rendite, kleinster Abstand (1.001 Aktien), 60 Zufallsuniversen, Veröffentlichungsprüfung, Methodenvergleich. **Gegenprobe:** Gleitkomma-Vergleich → 15, auf eine Stelle gerundeter Score → 2, „ISIN statt Rendite“ → 22 fehlschlagende Prüfungen. Referenzfall fehlende Kurstage (25 Tage, 50/50) jetzt D, A, J; App-Untergruppen nach derselben Regel (`app/tests/gleichstand.test.ts`) |
| Entwicklungsumgebung, 24.10.2026 16:23–16:27 Uhr | **Prüffall 13.10. mit beiden Gleichstandsregeln** (`tests/live/ausgangsmodell_nachrechnen.py` auf deiner HTML-Übersicht vom 14.10.; nur Zählwerte) | Regel des Ausgangsmodells: **1.971 von 1.980** Ranglisten gleich, Platz 1 und erste 10 in allen 1.980 (wie bisher). Exakte Regel (ab 1.10.0): 699 gleich (darunter 380 leere), **Platz 1 in 4, die ersten 10 in 61** Ranglisten anders, sonst erster Unterschied hinter Platz 10 (1.220) – alle innerhalb rechnerisch gleicher Scores: die bewusste Abweichung |
| GitHub Actions, 24.10.2026 14:28–15:35 Uhr | **Android-Emulator: echte Installation und TalkBack** (Workflow „Android-Emulator prüfen“, sieben Läufe; bis zum letzten 15:29–15:35 Uhr die Prüfung selbst verbessert: zweiter Dialog, Startbildschirm-Dialog, Erkennung der Verknüpfung, zweite Startbildschirmseite). Emulator Android 15, Chrome 124, Format S25+; installiert wird die **veröffentlichte Website** (ohne Passphrase – nur Sperrbildschirm), TalkBack mit dem DEMO-Stand | **Letzter Lauf vollständig grün.** Installation wie mit dem Finger: Chrome-Menü „Zum Startbildschirm hinzufügen“ → „Installieren“ → Dialog „App installieren“ → „Installieren“ → Startbildschirm fragt „Zum Startbildschirm hinzufügen“ → bestätigt; nach 13 s liegt **„TR-Vergleich“ auf dem Startbildschirm** (Seite 2). Chrome legt im Emulator eine **Web-App-Verknüpfung** an, **kein eigenes App-Paket (WebAPK)** – dafür braucht Chrome ein Google-Konto mit Play Store, das der Emulator nicht hat. **Vom Startbildschirm gestartet:** eigenes Fenster (`display-mode: standalone`, Chrome-Web-App-Fenster), keine Adressleiste, Sperrbildschirm, Service Worker aktiv, 384 CSS-Pixel breit. **Im Flugmodus neu gestartet:** eigenes Fenster und Sperrbildschirm aus dem Speicher (offline). **TalkBack eingeschaltet** (Tastsuche aktiv): Start 94, Rangliste 91, Alle Aktien 190, Hilfe 34 bedienbare Elemente – in Chromes Barrierefreiheits-Baum (den TalkBack bekommt) **keines ohne Namen**; im Android-Abbild zeigen zwei Suchfelder keinen eigenen Text, weil das Abbild den Hinweistext nicht mit ausgibt (Chrome nennt sie „Name, Ticker oder ISIN“ bzw. „Begriff suchen“). Nicht geprüft: Bedienung mit TalkBack-Gesten, WebAPK, Samsung Internet, echtes Gerät |
| Entwicklungsumgebung 14:51–15:00 Uhr, GitHub Actions 15:00–15:07 Uhr | **Version 1.17.1 – alle Tests** | GitHub „Prüfung“ (Commit f609152): **541 Tests bestanden** (23 übersprungen: Live-Prüfungen, die eigene Workflows mit Secrets brauchen, und die Tabellenausgabe für die Doku), echte Börsenkalender 4 von 4, App-Build identisch. Davon neu: 8 Referenzfälle fehlende Kurstage, 4 Tests der Kurslauf-Kontrolle, 1 Integrationstest TR-Liste in anderer Datei, 1 Test „ein Stand je Kurstag“, 1 Workflow-Test (Kontrolle als eigener, nur lesender Workflow). Lokal davor dieselben 541 Tests: 540 bestanden, 1 Fehler nur, weil eine Testdatei während des Laufs geändert wurde (danach einzeln bestanden) |
| GitHub Actions, 24.10.2026 14:40–14:47 Uhr | **Fehlende Kurstage: Einfluss auf die Ranglisten mit echten Daten** (Workflow „Fehlende Kurstage auswerten“, drei Läufe, zuletzt 14:46–14:47 Uhr; nur lesend, nur Zählwerte) auf dem Stand `2026-10-23_68f9fbe5` | Ranglisten des Skripts = veröffentlichte: **1.980 von 1.980**. 856.002 Aktie-Zeitraum-Paare in den Ranglisten (Gruppe A), **2.864 mit fehlender Sitzung** (2.839 mit genau einer), 108 Aktien; ausgeschlossen: 614 (Starttag ohne Kurs), 123 (mehr als 20 %), 2.610 (Schlusskurs zu alt); 1.121 Paare mit letztem Schlusskurs (30 Aktien). Beim Kursanbieter nachgesehen (108 von 108 Aktien, 21 s): 96 Tage ohne Zeile, **14 Leerzeilen** (8 Aktien, 162 Paare), 4 nachgeliefert. Unter den ersten 10 aller Ranglisten 22 von 16.400 Plätzen mit Lücke, **keiner auf Platz 1**. Andere Regel → anderer Platz 1 / andere erste 10 / nur andere Reihenfolge: streng 7 / 38 / 75, wie Ausgangsmodell 7 / 7 / 41, ohne letzten Schlusskurs 9 / 11 / 112 – **jeder Wechsel auf Platz 1 bei rechnerischem Gleichstand an der Spitze**. Gleichstand: 336 von 1.314 gemischten Ranglisten mit rechnerisch gleichem Score unter den ersten 11 (69 mit der niedrigeren Rendite vorn, 34 mit Gleichstand auf Platz 1); exakter Vergleich: Platz 1 in 4, erste 10 in 4 (Aktien) bzw. 65 (Reihenfolge) anders. Einzelheiten: [12_Fehlende_Kurstage](12_Fehlende_Kurstage.md) |
| Entwicklungsumgebung, 24.10.2026 14:20–15:00 Uhr | **Referenzfälle fehlende Kurstage** (`tests/unit/test_referenz_fehlende_kurstage.py`): zehn erfundene Aktien durch den ganzen Rechenkern, Erwartung unabhängig mit exakten Brüchen | **8 Tests bestanden** (1 übersprungen: Tabellenausgabe für die Doku): Status, Starttag, Kurse/Sitzungen, Rendite und R² für 1, 2, 3, 7, 25, 29, 30, 60 und 90 Tage; Leerzeile = fehlende Zeile (Zahl für Zahl gleich); R² ohne Auffüllen; Ranglisten 3, 7, 25 und 30 Tage in fünf Gewichtungen gleich der unabhängigen Rechnung; Einfluss auf die 30-Tage-Rangliste nach vier Regeln. **Gegenprobe:** mit 19 statt 20 % schlägt der Grenzfall D fehl, mit „Leerzeile schließt aus“ der Fall C (5 Zeiträume). Dabei gefunden: rechnerisch gleiche Scores entscheidet die letzte Binärstelle (Fall 25 Tage, 50/50) – wie im Ausgangsmodell: Stufe A des Prüffalls 13.10. mit Gleitkomma-Vergleich 1.272 von 1.278 gemischten Ranglisten gleich, mit exaktem Vergleich keine |
| Entwicklungsumgebung, 24.10.2026 14:45–15:00 Uhr | **Gleiche TR-Liste in anderer Datei** (Integrationstest `test_same_tr_list_in_another_file_keeps_the_stand`) und **ein Stand je Kurstag** (`test_one_stand_per_day_and_kind`) | bestanden: andere Dateifassung desselben Inhalts → „keine neuen Daten“, kein zweiter Stand; Stand mit der anderen Fassung gerechnet → bleibt gültig; echte Namensänderung → neu gerechnet. **Gegenprobe ohne die Korrektur:** „veroeffentlicht“ statt „keine_neuen_daten“ (Test rot). Anlass: am 23.10. wurde der 22.10. dreimal, am 24.10. der 23.10. zweimal veröffentlicht (Laufübersichten), „Frühere Stände“ zeigte den 23.10. doppelt |
| GitHub Actions / Entwicklungsumgebung, 24.10.2026 14:56–15:05 Uhr | **Kontrolle eines Kurslaufs** (`ops/kurslauf_kontrolle.py`, Workflow „Kurslauf kontrollieren“) an echten Läufen ausprobiert | Lauf von Hand 13:41 Uhr: „nicht bestanden“ (von Hand, 51 Notierungen); geplanter Lauf 11:17 Uhr (1.16): „nicht bestanden“ (86 min, noch ohne gleichzeitigen Abruf); geplanter Lauf 13:53 Uhr (Zeitplan 09:00): „keine neuen Daten“ – also kein Kurslauf. **Der erste zeitgesteuerte Lauf mit Abruf aller Notierungen steht noch aus** (Nachtlauf Montag, 26.10., 23:37 Uhr). 4 Unit-Tests der Kriterien bestanden. Workflow „Kurslauf kontrollieren“ in GitHub Actions ausprobiert (15:00 Uhr, 17 s, ab 24.10.): dieselben Urteile; als „erster zeitgesteuerter Lauf mit Abruf aller Notierungen“ nennt er den Lauf von 11:17 Uhr (noch 1.16) – nicht bestanden (86 min, ohne gleichzeitigen Abruf). Voreinstellung für Montag: ab 26.10. |
| Website, 24.10.2026 15:01 Uhr | **status.json nach dem geplanten Lauf 09:00 Uhr** (gestartet 13:53 Uhr, „keine neuen Daten“, Job „Kennzahlen“ 14:06 Uhr) | `naechster_kursstand` 26.10. ab 22:00 UTC vorhanden – zweite Bestätigung der Korrektur, diesmal nach einem Lauf mit Zeitplan |
| GitHub Actions, 24.10.2026 14:04–14:07 Uhr | **„App mit echten Daten prüfen“ nach dem Prüflauf** – erster Stand, den Software 1.17.0 im Betrieb gerechnet hat (Chromium im Format des S25+) | **App mit echten Daten: alles in Ordnung** (App `1.17.0+7d871934`, Datenstand `2026-10-23_68f9fbe5`, vollständig, 3 aufbewahrte Stände): **24 von 24 Ansichten ohne Fehler**; geöffnet in 0,3 s, entsperrt bis zur fertigen Startseite 0,3 s, erneut geöffnet 0,6 s ohne erneute Passphrase; Einzelansicht nach dem Antippen fertig in 0,1 s; **Installation (Chromium, dauerhaftes Profil): installierbar, installiert, erster Start mit Sperrbildschirm und Startseite**; Top 3 oben (Punkte absteigend), Bericht 1–30, Musterdepots („10 Sieger“ mit 10 Positionen), Signal-Stand des Prüflaufs (`20261024T114631Z`, 10.936 Aktien) geladen. **Nachrechnung (gleicher Lauf):** Stand 23.10. **mit Software 1.17.0 gerechnet: 9.986.999 Prüfungen, 0 Abweichungen** (10.995 Kursreihen, 856.002 Zeiträume in Ranglisten); Stand 13.10. (Software 1.6.0): 9.651.085 Prüfungen, 0 Abweichungen, dazu als Warnung die 2 Fälle des bekannten Fehlers von 1.6.0 – Job grün. Den Text unter dem Kursstand habe ich mit den veröffentlichten Werten aus der App-Funktion erzeugt (Stand 14:10 Uhr): „Neue Schlusskurse (Montag, 26. Oktober) gibt es ab Montag, 26. Oktober, 23:00 Uhr. Geplant: Nachtlauf Montag, 26. Oktober, 23:37 Uhr; fällt er aus, Morgenlauf Dienstag, 27. Oktober, 07:00 Uhr – …“. |
| Website, 24.10.2026 13:47 und 14:05 Uhr | **Erneute Kontrolle der veröffentlichten `status.json`** nach dem Prüflauf (über das Netz abgerufen) – nach dem Job „berechnen“ und nach dem Job „Kennzahlen“ | **`naechster_kursstand` vorhanden – Korrektur im Betrieb bestätigt:** 26.10.2026 ab 22:00 UTC (23:00 Uhr Winterzeit), 33 Börsen; Softwareversion 1.17.0, neuester Stand `2026-10-23_68f9fbe5`. Um 14:05 Uhr enthielt die Datei den Signal-Stand des Jobs „Kennzahlen“ (`20261024T114631Z`, zum neuen Stand) – sie stammt also vom frischen Rechner dieses Jobs, auf dem der Wert bis 1.16 verloren ging. |
| GitHub Actions, 24.10.2026 13:41–14:04 Uhr | **Täglicher Lauf von Hand** („Alles aktualisieren“ ausgeschaltet = offizieller Lauf), gestartet, um die Korrektur des nächsten Kursstands im Betrieb zu prüfen; erster täglicher Lauf mit Software 1.17.0 | **Grün.** Die TR-Liste war neu (dieselben 11.596 ISINs, +0 / −0), deshalb wurde der Stand 23.10. mit 1.17.0 neu gerechnet und **vollständig veröffentlicht** (`2026-10-23_68f9fbe5`). Kursabruf: 11.094 Notierungen aus dem Checkpoint, 51 ohne Stichtagskurs erneut abgerufen – **gleichzeitig: 51 Abrufe in 6 s (8,1 je Sekunde, 4 gleichzeitig über 2 Hosts)**, 0 Einzelfehler; danach 10.957 Notierungen mit Kurs am Stichtag (vorher 10.955), 1 Schlusskurs aus der Kursmeldung durch die nachgelieferte Tageskerze ersetzt. Job „berechnen“ 5 Minuten, „Kennzahlen“ 18 Minuten (387 Kennzahlen abgerufen, 0 Fehler; Signal-Stand mit 10.936 Aktien), Bereitstellung 5 s. Der vorige Stand `2026-10-23_bce9bf2d` bleibt unter „Frühere Stände“ lesbar (aufbewahrt: drei Stände). |
| Website, 24.10.2026 13:30 Uhr | **Endkontrolle der veröffentlichten `status.json`** (über das Netz abgerufen) | Softwareversion 1.17.0, letzter Kursstand 23.10., Zeitplan mit Nachtlauf 22:37 UTC Mo–Fr – aber **`naechster_kursstand` leer**. Ursache: Der Job „Kennzahlen“ und „Nur die Website“ schreiben die Statusdatei auf einem frischen Rechner, der den Wert nicht kannte. **Behoben** (Wert zusätzlich in der Datenbank, überholte Werte entfallen; neuer Integrationstest, Gegenprobe ohne die Korrektur schlägt fehl). **Im Betrieb bestätigt** mit dem Prüflauf 13:41–14:04 Uhr (Zeilen darüber). |
| GitHub Actions, 24.10.2026 13:09–13:11 Uhr | **„App mit echten Daten prüfen“ mit der veröffentlichten Version 1.17.0** (Chromium im Format des S25+, Datenstand 23.10.) | **App mit echten Daten: alles in Ordnung** (App `1.17.0+7d871934`, Datenstand `2026-10-23_bce9bf2d`, vollständig): **24 von 24 Ansichten ohne Fehler**; geöffnet in 0,2 s, entsperrt bis zur fertigen Startseite 0,4 s, erneut geöffnet 0,6 s ohne erneute Passphrase (1.16.0 am selben Vormittag: 0,2 / 0,4 / 0,6 s – gleich schnell); Einzelansicht nach dem Antippen fertig in 0,1 s; **Installation (Chromium, dauerhaftes Profil): installierbar, installiert, erster Start mit Sperrbildschirm und Startseite**; Top 3 oben (Punkte absteigend), Bericht 1–30, Musterdepots („10 Sieger“ mit 10 Positionen), Signale vom 24.10. geladen. **Nachrechnung (gleicher Lauf):** Stand 23.10. (heute mit Software 1.16.0 gerechnet) **9.987.042 Prüfungen, 0 Abweichungen**; Stand 13.10. (Software 1.6.0) **9.651.085 Prüfungen, 0 Abweichungen**, dazu als Warnung die 2 Fälle des bekannten Fehlers von 1.6.0 („damaliges Verhalten bestätigt, fachlich falsch“; der Stand bleibt unverändert als Originalreferenz) – Job grün. |
| GitHub Actions, 24.10.2026 13:08–13:09 Uhr | **Version 1.17.0 veröffentlicht**: „Nur die Website neu bereitstellen“, gestartet erst nach grüner „Prüfung“ des Builds und nach dem Ende des Tageslaufs | Bereitstellung in 53 s: „App 1.17.0+7d871934 neu zusammengesetzt; Datenstand unverändert (3 veröffentlichte Stände)“. **Die Website liefert danach `1.17.0+7d871934`** (version.json, abgerufen 13:09 Uhr). |
| GitHub Actions, 24.10.2026 12:44–13:11 Uhr | **Kursabruf-Tempo messen, alle Notierungen** (nur lesend: Zustand aus dem Release, nichts gespeichert; Stichtag 23.10., 11.145 Notierungen wie im Tageslauf, 143 davon mit vollem Abruf) | **Nacheinander wie bis 1.16:** 300 Abrufe in 119,6 s = **2,51 je Sekunde**. **Gleichzeitig wie ab 1.17** (4 Abrufer, Hosts query2 und query1, 0,25 s je Host): 10.845 Abrufe in 1.355,9 s (22,6 min) = **8,0 je Sekunde**, **0 × HTTP 429**. Hochgerechnet auf alle 11.145: **23,2 statt 74,0 Minuten**. Ergebnis je Notierung wie im Tageslauf desselben Stichtags: 11.006 mit Kursen, 138 „Symbol unbekannt (404)“, 1 ohne gültige Kerze. **Gleiche Daten:** zweiter gegen ersten Host (Stichprobe 200): Tage, Eröffnung, Hoch, Tief, Schluss und Umsatz alle bitgleich; gegen den gespeicherten Stand: Schlusskurse älterer Tage 95.626 von 95.628 bitgleich (2 um mehr als 20 % anders), Umsätze 95.627 von 95.628; letzter Tag (23.10.): Schlusskurse 11.001 von 11.002 bitgleich, Umsatz 10.864 von 11.002 – den Umsatz des letzten Tages ändert der Anbieter nachträglich (schon im Vergleich vom Vormittag: 32 von 426). Läuft parallel zur Kennzahlen-Abfrage des Tageslaufs (anderer Rechner). **Folge:** `abruf.chart_gleichzeitig: 4` eingeschaltet; im Tageslauf rechnet das erstmals mit dem Stand vom 26.10. |
| GitHub Actions, 24.10.2026 11:17–12:43 Uhr | **Täglicher Lauf mit Zeitplan** (Auslöser „schedule“, frühester Termin 07:00 Uhr; noch Software 1.16 mit Kursabruf nacheinander) – Vergleichswert für den gleichzeitigen Abruf | Stand **23.10.2026 vollständig veröffentlicht** (`2026-10-23_bce9bf2d`, alle 33 Börsen mit Sitzung, jede mit mindestens 97 % Stichtagskursen); 11.145 Notierungen abgerufen: 10.955 mit Kurs am Stichtag, 51 ohne Stichtagskurs, 139 ohne Kursdaten (Kürzel beim Kursanbieter unbekannt); Job „berechnen“ **86 Minuten** (09:17:41–10:43:53 UTC), der Kursabruf lief dabei noch nacheinander (höchstens 2,5 Abrufe je Sekunde; im Messlauf danach 2,51 gemessen). Start 4¼ Stunden nach dem frühesten Termin. |
| GitHub Actions, 24.10.2026 12:26 Uhr | **Nachtlauf-Kette, von Hand ausgelöst** – versehentlich: Beim Abfragen der Fehlerantworten von GitHub für den externen Auslöser (absichtlich ungültiges Token) setzte der Netz-Proxy dieser Entwicklungsumgebung die eigene GitHub-Anmeldung ein, und der Aufruf startete den Workflow „Nachtlauf“ wirklich | Workflow „Nachtlauf“ grün in 14 s, Hinweis „Täglicher Lauf gestartet“; GitHub legte „Täglicher Lauf“ als `github-actions[bot]` an – **die Kette funktioniert**. Der so angelegte Lauf ersetzte den wartenden Lauf von 07:45 Uhr (GitHub hält je Sperre nur einen wartenden Lauf); ich habe ihn um 12:54 Uhr abgebrochen, bevor er begann – am Samstag hätte er keine neuen Schlusskurse gefunden. Nicht geprüft damit: der Start durch GitHubs Zeitplan (erstmals 26.10.). Die Antworten 404 (falscher Workflow) und 422 (falscher Zweig) kamen dagegen echt von GitHub. |
| Entwicklungsumgebung, 24.10.2026 12:15–12:35 Uhr | **Externer Auslöser** (`ops/externer-ausloeser/nachtlauf-ausloeser.gs`) mit nachgebildeten Google-Diensten: neuer App-Test `app/tests/ausloeser.test.ts` | **7 Tests bestanden:** Adresse, Kopfzeilen und Nutzlast an GitHub; Wochentagsregel nach Berliner Datum über das Ende der Sommer- und den Beginn der Sommerzeit (Dienstag- bis Samstagnacht ja, Sonntag- und Montagnacht nein); ohne Token kein Aufruf; Antworten 401/403/404/422/429/5xx und fehlendes Netz ohne Ausnahme (keine Fehler-E-Mail von Google) mit Grund und nächstem Schritt; das Token steht nie im Protokoll; Zeitplan täglich gegen 00:40 Uhr. Gegenprobe: mit absichtlich falscher Wochentagsregel bzw. Zeitzone schlagen 1 bzw. 4 Tests fehl. Gefunden und behoben: Ohne Netz hätte das Skript eine Ausnahme geworfen (dann schickt Google eine Fehler-E-Mail), und HTTP 422 wurde als „überlastet“ erklärt. **Nicht geprüft:** in einem echten Google-Konto. |
| GitHub Actions, 24.10.2026 12:21–13:25 Uhr | **Android-Emulator, Wiederholungen bis zum endgültigen Build** (acht Läufe; dabei die Prüfung selbst verbessert). Die letzten beiden Läufe 12:56–13:00 und 13:21–13:25 Uhr mit dem veröffentlichten Build `1.17.0+7d871934` | **Beide letzten Läufe vollständig und gleich bestanden:** installierbar ohne Hindernisse; **offline:** Chrome ohne Netz neu geöffnet – gespeicherter Stand mit Hinweis; keine seitliche Verschiebung in 10 Ansichten hochkant und quer (die Einstellung 130 % Systemschrift wirkte im Emulator wieder nicht auf die Seite); **Bildschirmtastatur offen**, Fokus im Suchfeld, Feld sichtbar, sichtbare Höhe 728 → 474 px bei unveränderter Seitenhöhe (Tastatur über der Seite, Leiste unten bleibt). Unterwegs gefunden und behoben – an der Prüfung, nicht an der App: Jedes Öffnen per Befehl legte in Chrome einen neuen Tab an, sodass die Prüfung vermutlich zeitweise einen Tab im Hintergrund steuerte: In drei Läufen öffnete sich die Tastatur nicht („ohne Ergebnis“), und ein bloßes Neuladen ohne Netz zeigte einmal nicht den gespeicherten Stand. Seit nur noch ein Tab bleibt und vorn liegt, öffnet sich die Tastatur; offline wird jetzt als Neustart ohne Netz geprüft. Ein echtes Antippen per adb an der gemessenen Stelle setzte den Fokus nicht ins Suchfeld (Lauf 12:45–12:49 Uhr) bzw. fand das Suchfeld danach nicht mehr (Lauf 12:50–12:54 Uhr abgebrochen) – deshalb nicht verwendet. Im Abbild vorhanden: TalkBack (nicht benutzt), Google-Play-Dienste; Samsung Internet nicht. |
| GitHub Actions, 24.10.2026 11:46–11:56 Uhr | **Android-Emulator** (Workflow „Android-Emulator prüfen“, nur DEMO-Daten, keine Secrets): Android 15 (Google-APIs-Abbild) mit dem mitgelieferten **Chrome 124**, Bildschirm 1080 × 2340 bei 450 dpi = 384 CSS-Pixel wie das S25+; drei Anläufe (1: Emulator startete nicht – ohne Fehlerhinweis; nach dem Umbau des Starts als Skript mit festem AVD-Ordner lief er, 2: Verbindung riss nach dem Schriftgrößen-Wechsel ab, 3: vollständig) | **Emulator-Test bestanden:** Startseite mit Kursstand; **installierbar ohne Hindernisse** (Chrome für Android: `Page.getInstallabilityErrors` leer, Manifest ohne Fehler); **offline** gespeicherter Stand mit Hinweis „Offline – gespeicherter Stand“; **keine seitliche Verschiebung** in 10 Ansichten hochkant (384 × 728) und quer (832 × 280, Leiste links); **Bildschirmtastatur:** Tastatur offen, Fokus im Suchfeld, Feld sichtbar, sichtbare Höhe 728 → 474 px, Seitenhöhe unverändert 728 (Chrome legt die Tastatur über die Seite) – die Leiste unten bleibt deshalb wie vorgesehen stehen. **Nicht wirksam:** Systemschriftgröße 130 % änderte in Chrome 124 die Schriftgröße der Seite nicht (16 px) – große Schrift ist deshalb nur in der Desktop-Emulation geprüft (nächste Zeile). Kein Gerätetest; Samsung Internet gibt es im Emulator nicht, TalkBack ist im Abbild vorhanden, wurde aber nicht benutzt. |
| Entwicklungsumgebung, 24.10.2026 11:50–12:10 Uhr | **Große Schrift und schmale Bildschirme** (Chromium, DEMO, Schriftgröße über die Grundschrift der Seite): 384 px mit 100/130/150/175 %, 360 px mit 150 %, 320 px mit 100/130 %, quer 832 × 384 – je 21 Ansichten, gemessen: Seite breiter als der Bildschirm, Elemente außerhalb, abgeschnittener Text | Vorher (1.16-Stil): bei 150 % vier Ansichten seitlich verschoben (Abdeckung, Umschichtung, Bericht, Start), Titel der Kopfzeile und Punkte-Teile der Top-Liste abgeschnitten; bei 175 % sieben Ansichten. **Nachher: in allen Konfigurationen 0 Auffälligkeiten.** Ursachen behoben: Rasterspalten ohne `minmax(0, 1fr)`, Text ohne Umbruch, feste Kachelspalten, Eingabefeld mit Mindestbreite aus der Zeichenzahl. **Endkontrolle 12:42 Uhr** mit dem Build `1.17.0+493c4334` und **13:20 Uhr mit dem veröffentlichten Build `1.17.0+7d871934`** (DEMO jeweils neu erzeugt): 384 px mit 150 und 175 %, 360 px mit 150 %, 320 px mit 130 % – beide Male 0 Auffälligkeiten; Bildschirmfotos von Start, Rangliste und Matrix (150 %) und Datenstand angesehen, keine Skriptfehler. |
| GitHub Actions, 24.10.2026 11:46–11:48 Uhr | **„App mit echten Daten prüfen“** (Live-App noch 1.16.0) mit der **versionsbewussten Nachrechnung** | Live-App: 24 von 24 Ansichten ohne Fehler, Installation in Chromium bestanden. **Nachrechnung grün:** Stand 13.10. (Software 1.6.0) **9.651.085 Prüfungen, 0 Abweichungen**, dazu als Warnung „bekannter Fehler von Software 1.6.0 – 2 Fälle – damaliges Verhalten bestätigt, fachlich falsch“ (behoben in 1.13.0, nur Anzeige); Stand 22.10. (Software 1.15.0) **9.987.701 Prüfungen, 0 Abweichungen**. |
| Entwicklungsumgebung, 24.10.2026 11:30–11:50 Uhr | **Prüffall Ausgangsmodell** (`tests/live/ausgangsmodell_nachrechnen.py`) mit den Rechendaten aus deiner HTML-Übersicht (Stichtag 13.10.2026, 11.531 Aktien, 1.980 Ranglisten) | Rangfolge aus dessen Kennzahlen 1.971/1.980 gleich (9 nur Reihenfolge ab Platz 11, Rundung der Übersicht); Kennzahlen aus dessen Tageskursen: Startdatum 520.640/520.640, Rendite alle (≤ 1e-6), R² 103.147/103.147 (≤ 1e-9), Aufnahme V/U 580.561 gleich, Rest erklärt (Split im Zeitraum 3.121 – keine Split-Termine in der Übersicht –, Leerzeilen 148); ganze Kette mit dessen Split-Entscheidungen 1.579/1.980 gleich (Gruppe B 990/990), übrige 401 nur zusätzliche Aktien mit Leerzeile; Ø Tagesumsatz: Verhältnis je Währung konstant (USD genau 1 bei 3.504 Aktien). |
| GitHub Actions, 24.10.2026 10:52–10:58 Uhr | **Kursabruf vergleichen** (nur lesend, 11.145 Notierungen, Stichtag 23.10.): Sammelabfragen „spark“ und „quote“ gegen Chart-Abruf und gespeicherte Kurse, fünf Varianten der Sammelabfrage | spark 558 Abrufe in 140 s, quote 75 in 10 s, keine Drosselung; Schlusskurse aus „spark“ an 212.619 von 213.840 Tagen gleich (≤ 1e-6), an 1.221 abweichend (23 um mehr als 20 %), aber **kein Umsatz und keine Tage ohne Handel in spark (alle Varianten)** und **Umsatz aus quote bei 30 von 406 Stichproben um mehr als 20 % anders** → Sammelabruf nicht gleichwertig, bleibt aus (04_Datenquellen). |
| Entwicklungsumgebung, 24.10.2026 11:15–11:45 Uhr, Gesamtläufe 12:20–12:29 und 13:32–13:41 Uhr, Nachtests 12:58–13:19 Uhr | **Version 1.17.0** – alle Tests | **Letzter Gesamtlauf** (mit der Korrektur des nächsten Kursstands, 13:32–13:41 Uhr): **Python 526 Tests in 523 s bestanden** – 353 Unit-, 75 Integrations- (neu: nächster Kursstand auf frischem Rechner) und 72 Browser-Tests, 26 Live-Tests übersprungen. Auf GitHub (Workflow „Prüfung“, Commit 230c55c, 13:36–13:47 Uhr): **526 Tests bestanden** (22 Live-Tests übersprungen), echte Börsenkalender 4 von 4; ebenso grün für die Dokumentation danach (852883a). App-Tests zuletzt gegen 13:50 Uhr wiederholt: 98 (82 bestanden, 16 über Python, 0 Fehler), Typprüfung ohne Fehler. Nach der letzten App-Änderung (Text zur Aktualität, Build `1.17.0+7d871934`): Typprüfung ohne Fehler, App-Tests 98 (82 bestanden, 16 über Python), **Browser-Tests 72 bestanden** (138 s); mit eingeschaltetem gleichzeitigem Abruf (`abruf.chart_gleichzeitig: 4`) **353 Unit- und 74 Integrationstests bestanden** (13:13–13:19 Uhr). Letzter Gesamtlauf davor: Python **525 Tests in 535 s** – 353 Unit-, 74 Integrations- und 72 Browser-Tests bestanden, 26 Live-Tests übersprungen (laufen in GitHub Actions: 4 Kalendertests in „Prüfung“, die übrigen 22 in eigenen Workflows, teils mit Secrets); App: Typprüfung ohne Fehler, **98 Tests** (82 bestanden, 16 Datenvertragstests über Python), darunter neu 7 Tests des externen Auslösers mit nachgebildeten Google-Diensten (Gegenprobe: mit absichtlich falscher Wochentagsregel bzw. Zeitzone schlagen 1 bzw. 4 davon fehl). Erster Lauf 11:15–11:45 Uhr: Python 521 Tests bestanden, darunter neu 6 Tests des gleichzeitigen Chart-Abrufs (gleiche Kursreihen und Reihenfolge wie nacheinander, beide Hosts im Wechsel, Rückfall bei HTTP 429 ohne Verlust, Abbruch erst bei Drosselung auch einzeln, vorzeitiges Ende ohne Warten), Workflow-Tests (Nachtlauf: Zeit nach dem letzten Börsenschluss, nicht zur vollen Stunde, passt zur Konfiguration, nur `actions: write`; Mess- und Emulator-Workflows nur von Hand und ohne Hochladen, Emulator-Workflow und Nachtlauf ohne Secrets), Auslöser „nachtlauf“; **Browser-Tests 72 bestanden**, darunter neu die Bildschirmtastatur; **App: 75 Tests** (neu 6 zur Aktualität: nächster Nachtlauf und Morgenlauf über das Ende der Sommerzeit, überfällig nach 12 Stunden, fehlgeschlagener Lauf mit Grund in Alltagssprache, stummer Server, Zwischenstand). Gefunden und behoben: Die erste Fassung der Tastatur-Erkennung ließ die Leiste unten mitten im Tippen auf einen Knopf wieder erscheinen (2 Browser-Tests rot). |
| GitHub Actions, 24.10.2026 07:00–07:03 Uhr | **„App mit echten Daten prüfen“, zweiter Durchgang** mit den an 1.16 angepassten Prüfungen (vorher lokal gegen den verschlüsselten DEMO-Stand: 11 Live-Tests, 24 von 24 Ansichten ohne Fehler) | **App mit echten Daten: alles in Ordnung** (App `1.16.0+9504faaf`, Datenstand 22.10., vollständig): **24 von 24 Ansichten ohne Fehler**, darunter neu „Hilfe und Begriffe“ mit 26 Begriffen; geöffnet 0,3 s, entsperrt bis zur fertigen Startseite 0,4 s, erneut geöffnet 0,7 s ohne erneute Passphrase, Service Worker aktiv; **Installation (Chromium, dauerhaftes Profil): installierbar, installiert, erster Start mit Sperrbildschirm und Startseite, Kurzerklärung sichtbar**; Top 3 der erste Inhalt unter der einmaligen Kurzerklärung, Punkte absteigend; Einzelansicht nach dem Antippen fertig in 0,2 s; keine Konsolenfehler. **Nachrechnung** wie im ersten Durchgang: Stand 22.10. **9.976.704 Prüfungen, 0 Abweichungen**; Stand 13.10. (Software 1.6.0) die 2 bekannten Abweichungen „Kursreihe fehlt“ – Job deshalb rot. |
| GitHub Actions, 24.10.2026 06:39–06:57 Uhr | **Version 1.16.0 im Betrieb**: Prüfung, Website bereitstellen („Nur die Website neu bereitstellen“), „App mit echten Daten prüfen“ (erster Durchgang) | Workflow „Prüfung“ für beide Commits grün: **472 Tests** bestanden (517 s bzw. 330 s), darunter die **Installation als Web-App in Chromium auf dem GitHub-Runner**; 22 Live-Tests übersprungen (laufen in eigenen Workflows). **Bereitstellung** 06:52:09–06:53:27 Uhr (1:18 Minuten): „App 1.16.0+9504faaf neu zusammengesetzt; Datenstand unverändert (3 veröffentlichte Stände)“; die Website liefert danach `1.16.0+9504faaf`. **Live-Prüfung** (06:54 Uhr, Datenstand 22.10., vollständig): geöffnet 0,2 s, entsperrt bis zur fertigen Startseite 0,3 s; **Installation: installierbar, installiert, erster Start mit Sperrbildschirm und Startseite, Kurzerklärung sichtbar**; 23 von 24 Ansichten ohne Fehler. Rot waren zwei Prüfungen, die nicht an 1.16 angepasst waren: die Hilfe zählte als fehlerhaft, weil sie die Fehlermeldungen der App erklärt („Wenn etwas nicht klappt“), und „Top 3 oben“ schlug an, weil beim ersten Start einmalig die Kurzerklärung darüber steht. Beide Prüfungen sind angepasst (Erklärungen der Hilfe zählen nicht; die Top 3 müssen der erste Inhalt unter der Kurzerklärung sein). **Nachrechnung:** Stand 22.10.: **9.976.704 Prüfungen, 0 Abweichungen** (10.994 Kursreihen, 856.159 Zeiträume, 54 s); der alte Stand 13.10. (mit Software 1.6.0 gerechnet) zeigt weiter die **2 bekannten Abweichungen** „Kursreihe fehlt“ – deshalb ist dieser Job rot, wie bei jeder Nachrechnung seit dem 14.10. |
| Entwicklungsumgebung, 24.10.2026 05:30–06:40 Uhr | **Version 1.16.0** (verständlicher, robuster, einfacher zu bedienen; installierbare Testversion) | **Rundgang als neuer Nutzer** durch alle **26 Ansichten** (DEMO, S25+-Format 384 × 832, mit und ohne Verschlüsselung) und **18 Fehlerfälle** im Browser (leere und falsche Passphrase, Speicher gesperrt, offline, fehlende und beschädigte Dateien, Serverfehler 500, unbekannte Seite und ISIN, falsche Eingaben in Watchlist, Depot, Zeitraum und Einstellungen, Abbrechen, Zurück): **14 Fehler, 7 Verständnis- und 2 Bedienprobleme** gefunden und behoben (eines erst beim Prüfen der Installationsseite: „hat sich seit vor 11 Tagen nicht … gemeldet“); danach alle 18 Fälle erneut durchgespielt – jede Meldung nennt Ursache und nächsten Schritt, keine Skriptfehler in der Konsole. Python: **472 Tests** in 495 s bestanden (308 Unit, 67 Integration, **71 Browser** – neu 9, Abschnitt 3; 26 Live-Tests übersprungen: 11 brauchen die veröffentlichte App mit Passphrase, 11 die echten Datenquellen, 4 den echten Börsenkalender – sie laufen in GitHub Actions). Nach dem letzten Build (`1.16.0+9504faaf`) die **72 Browser- und Datenvertragstests** noch einmal: bestanden (147 s). App: Typprüfung ohne Fehler, **85 Tests** (69 bestanden, 16 Datenvertragstests laufen über Python; neu 7: Begriffe vollständig, kein Satz über 30 Wörter, Begriffssuche, Rangscore-Beispiel = Formel, Fehlermeldungen, Beträge, Zeitplan-Hinweis). Build zweimal gebaut: identisch. **Installation** (Chromium 141, dauerhaftes Profil): keine Installationshindernisse, als Web-App installiert und gestartet – erster Start mit Sperrbildschirm, nach der Passphrase die Startseite mit Kurzerklärung. Installationsseite `#/installieren` im gesperrten Zustand: Sobald Chrome die Installation anbietet, erscheint der Knopf „Jetzt installieren“ (Engagement-Prüfung von Chrome per Startschalter übersprungen; den Installationsdialog selbst kann ein Browser ohne Bildschirm nicht bestätigen). **Start mit 4-fach gedrosseltem Prozessor** (Median aus 7 Läufen): Skriptzeit 0,29 s → 0,28 s, sichtbar 0,68 s → 0,79 s (mehr Text auf dem Sperrbildschirm). Nicht geprüft: echtes Android-Gerät, Samsung Internet, TalkBack (Abschnitt 8). |
| GitHub Actions, 15. und 16.10.2026 | **Geplante Läufe** (Auslöser „schedule“, Zeitplan 07:00, 07:15, 07:45 und 09:00 Uhr), nachdem der Workflow am 14.10. mit deinem Konto aus- und wieder eingeschaltet wurde | **Zeitplan-Problem gelöst: GitHub startet die geplanten Läufe wieder** – an beiden Tagen alle vier, alle grün, aber jeweils **4¼ bis 5½ Stunden später** als eingestellt. **15.10.:** Die Läufe um 11:36, 11:53 und 12:20 Uhr (statt 07:00, 07:15 und 07:45 Uhr) warteten wie vorgesehen auf Tallinn (6 von 15 Kursen) und Warschau (8 von 153); der letzte Versuch um 14:32 Uhr (statt 09:00 Uhr) veröffentlichte den gekennzeichneten **Teilstand zum 14.10.** (online 14:36 Uhr, Signale 14:38 Uhr). **16.10.:** Der Lauf um 11:29 Uhr (statt 07:00 Uhr) holte die Kurse aller 11.081 Notierungen für den neuen Stichtag (Laufschritt 80:41 Minuten) und veröffentlichte den **vollständigen Stand zum 15.10.** (online 12:50 Uhr, Kennzahlen und Signale 13:02 Uhr). Den Lauf von 11:47 Uhr brach GitHub ab, weil schon der nächste wartete; die Läufe von 12:06 Uhr (begann erst um 13:02 Uhr, nach dem ersten) und 14:10 Uhr meldeten „Kein neuer abgeschlossener Börsentag“ und ergänzten nur Kennzahlen. Wer morgens nicht warten will, startet den Lauf mit „Jetzt aktualisieren“ selbst (fehlt der offizielle Stand des Vortags noch, dauert das wegen des Kursabrufs gut eine Stunde) |
| GitHub Actions, 14.10.2026 17:38–17:50 Uhr | **Version 1.15.0 im Betrieb**: „Alles aktualisieren“, Prüfung und „App mit echten Daten prüfen“ | Workflow „Prüfung“ für 1.15.0 grün (alle Tests einschließlich Browser und echter Börsenkalender). Lauf 17:38:48–17:43:19 Uhr bestanden (Rechnen 33 s, Sichern im Hintergrund 19,5 s, ganze Website 245,8 MB, Stände jetzt mit `pruefsummen.bin`): Zwischenstand mit **10.049 Aktien mit Kurs von heute** (bis 17:39 Uhr), alle Börsen mit Kurs. **Live-Prüfung (App 1.15.0+aee0d9eb): 23 von 23 Ansichten ohne Fehler**; geöffnet **0,2 s**, entsperrt bis zur fertigen Startseite **0,3 s** (App 1.14 um 17:27 Uhr: 1,5 s), erneut geöffnet **0,6 s** (0,7 s); Ansichten 0,0–0,3 s, Musterdepots 1,2 s (vorher 0,6 s – die Seite lädt die Kursreihen der Depotaktien nach, schwankt mit dem Netz); Einzelansicht nach dem Antippen 0,1 s. Deine 5 Aktien: **3 mit Platz, 0 wenig gehandelt, 2 ohne Top-10-Nennung** (genaue Zählung ab dieser Prüfung; um 17:27 Uhr zählte „mit Platz“ auch „Punkte ohne Platz“). **Nachrechnung Zwischenstand: 9.821.222 Prüfungen, 0 Abweichungen**, 827 Aktien mit dem Schlusskurs davor, **11.809 von 11.809** ihrer Zeiträume gleich wie im Stand mit Schlusskursen; Prüfsummen erstmals aus `pruefsummen.bin`. Stand 13.10. (Software 1.6.0) unverändert mit den 2 bekannten Abweichungen „Kursreihe fehlt“ |
| Entwicklungsumgebung, 14.10.2026 17:15–17:45 Uhr | **Version 1.15.0** (schneller, übersichtlicher) | Python: **308 Unit-Tests** (Prüfsummen jetzt in `pruefsummen.bin`: gleiche Dateien und Prüfsummen mit einem und mehreren Prozessen, Manifest ohne Prüfsummenliste), **67 Integrationstests** (neu: 2 – vorübergehender Serverfehler beim Sichern wird wiederholt und gelingt ohne Lücke, ein Client-Fehler wird nicht wiederholt; die Prüfsummen-Datei ist über ihre Prüfsumme im Manifest verankert und enthält `fx.bin`) und **62 Browser-Tests** (Startseite: Rendite-Leiter, Umschichtungs-Regel und Abdeckung unter „Mehr auf einen Blick“, drei Kandidaten, Auswahl und erste fünf Plätze in einem Abschnitt; Menü ☰ mit zwei Gruppen und 9 Einträgen). App: Typprüfung, **78 Tests** (62 bestanden, 16 Datenvertragstests über Python). **Geschwindigkeit** mit einem DEMO-Stand in voller Größe (10.817 Aktien, verschlüsselt, 1,6 MB Kerndateien), Chromium auf 384 × 832, Prozessor 4-mal gedrosselt, Netz 12 Mbit/s mit 60 ms, 3 s Tippen der Passphrase, je 2–3 Läufe: Entsperren bis fertige Startseite **1,9–2,5 s (1.14) → 1,4–1,5 s (1.15)**, erneut öffnen **1,8–2,2 s → 1,2–1,4 s**; Top nach Zahlen, Ranglisten, Einzelansicht unverändert 0,2–0,4 s. Profil des Entsperrens (1.15): Entschlüsseln, Entpacken und Lesen der Kerndateien (rund 9,7 MB JSON) und das erste Zeichnen der Startseite machen den Rest aus. Startseite im DEMO **4.859 statt 6.981 px** hoch |
| GitHub Actions, 14.10.2026 17:17–17:30 Uhr | **Version 1.14.0 im Betrieb**: „Alles aktualisieren“ und „App mit echten Daten prüfen“ | Erster Lauf (17:17 Uhr) **abgebrochen beim Sichern**: „Upload state.sqlite.tra.neu: HTTP 502“ – die Website blieb deshalb unverändert (Absicherung „bereitgestellt wird nur nach erfolgreichem Sichern“). Zweiter Lauf 17:19:43–17:22:36 Uhr (**2:53 Minuten**) bestanden: Zwischenstand 14.10. mit **10.020 Aktien mit Kurs von heute** (bis 17:20 Uhr), Toronto ohne aktuellen Kurs. **Nachrechnung Zwischenstand: 9.818.513 Prüfungen, 0 Abweichungen**, davon 856 Aktien mit dem Schlusskurs davor gerechnet, **13.092 von 13.092** ihrer Zeiträume gleich wie im Stand mit Schlusskursen. Stand mit Schlusskursen 13.10. (gerechnet mit Software 1.6.0): 9.640.207 Prüfungen, **2 Abweichungen** „Kursreihe fehlt“ – zwei Aktien sind als „mit Kursreihe“ gekennzeichnet, ohne Datei (Fehler der damaligen Software, seit 1.13 behoben; der Stand wird nicht nachträglich verändert und fällt mit dem nächsten Stand mit Schlusskursen weg). **Live-Prüfung** (zweiter Versuch 17:27 Uhr; der erste tippte die Passphrase, bevor der Service Worker die Seite neu lud – Prüfung angepasst, App ab 1.15 ohne dieses Neuladen): **23 von 23 Ansichten ohne Fehler**, geöffnet 0,3 s, entsperrt bis zur fertigen Startseite **1,5 s**, erneut geöffnet **0,7 s**, Ansichten 0,0–0,6 s (Musterdepots 0,6 s), Einzelansicht nach dem Antippen 0,1 s, Seite „Top nach Zahlen“ 0,0 s (alle Daten schon geladen); „10 Sieger“ mit **10 Positionen**; Top 3 mit 3 Zeilen, deine 5 Aktien, davon 3 mit Platz (2 wenig gehandelt) |
| Entwicklungsumgebung, 14.10.2026 16:35–17:15 Uhr | **Version 1.14.0** (alle Aktien bewertet – Methode `tr-methode-1.9.0`, Musterdepots vollständig, Top 3 nur handelbar, Auffällige ausblendbar) | Python: **308 Unit-Tests** (neu: eigener Stichtag im Stand mit Schlusskursen – Feiertag der Börse und nicht gelieferter Kurs zählen mit dem letzten Schlusskurs, zwei verpasste Sitzungen gelten als veraltet, ungültige Kurse und Kurse außerhalb von Sitzungen zählen nicht; Methodenvergleich 1.8.0 → 1.9.0 mit Status 7 bzw. 8 vorher; Spitzenreiter ohne Auffällige mit Platz in der vollständigen Rangliste), **65 Integrationstests** (Nachrechnung erlaubt das eigene Ende je Aktie, wenn das Manifest die Regel nennt) und **62 Browser-Tests** auf simuliertem S25+ bestanden (neu: Schalter „Auffällige ausblenden“ in Ranking und Renditeliste – Spitzenreiter wie `winners_klar`, Platz wie vollständig, gespeichert, unter Einstellungen abschaltbar; „10 Sieger“ mit zehn Positionen; DEMO-Stichtag Montag 12.10. mit Feiertag in Tokio: Tokioter Aktien zählen mit dem Schlusskurs vom Freitag, Zeile „Schlusskurs 09.10.“, Teilstand-Hinweis „Deren Aktien zählen mit ihrem letzten Schlusskurs“); drei Browser-Tests an die neue Regel angepasst (Starttage je Spitzenreiter aus den Serverdaten; gleiche Kursfenster nur noch, wenn sie für jede Aktie gleich sind – im DEMO wegen Tokio keine). App: Typprüfung, **78 Tests** (62 bestanden, 16 Datenvertragstests über Python; neu: Filter der App = `winners_klar` des Servers in allen 90 Zeiträumen beider Rendite-Ranglisten; Kennzeichen kaum Umsatz, nicht bestimmbarer Umsatz, Einzelsprung; Musterdepot aufgefüllt nach Top 3, dann Top 10) |
| GitHub Actions, 14.10.2026 16:23–16:28 Uhr | **Bestätigung** nach der Korrektur „Kursreihe vorhanden“: „Alles aktualisieren“ und „App mit echten Daten prüfen“ | Lauf **2:21 Minuten** (16:23:14–16:25:35 Uhr), Zwischenstand mit **9.869 Aktien mit Kurs von heute** (bis 16:23 Uhr). **Nachrechnung Zwischenstand 14.10.: 9.812.077 Prüfungen, 0 Abweichungen** (841.677 Zeiträume in Ranglisten); 1.007 Aktien ohne Kurs von heute zählen mit dem Schlusskurs davor – **22.014 von 22.014 Zeiträumen gleich** wie im Stand mit Schlusskursen. Stand 13.10. (Software 1.6.0): weiter 2 Abweichungen (altes Kennzeichen der zwei Aktien ohne gültige Kurse; der nächste Stand mit Schlusskursen hat die Korrektur). **Vergleich mit ChatGPT je Gruppe:** B 0/100: Plätze 1–5 gleich in 28 von 30, 1–10 in 22 (App Ø 638 Aktien mehr); B gewichtet: 1–5 in 20 von 33, 1–10 in 0 (Ø 219 mehr); A 0/100: 1 von 30 bzw. 0 (Ø 3.325 mehr); A gewichtet: 0 von 33 (Ø 993 mehr) – die Unterschiede wachsen mit der Zahl der Aktien, die ChatGPT fehlten. **Live-Prüfung der App: alles in Ordnung**, 23 von 23 Ansichten, Top 3 absteigend, entsperrt in 5,0 s |
| GitHub Actions, 14.10.2026 16:02–16:25 Uhr | **Version 1.13.0 im Betrieb** und **unabhängige Nachrechnung mit echten Daten** (neuer Job „Rechnung unabhängig nachprüfen“ im Workflow „App mit echten Daten prüfen“) | „Alles aktualisieren“ 16:02:42–16:05:33 Uhr (**2:51 Minuten**): Zwischenstand 14.10. mit **9.778 Aktien mit Kurs von heute** (New York geöffnet, Kurse bis 16:03 Uhr), 102 Sammelabfragen, Kurse 17 s, Rechnen 33 s (mehr Aktien mit Kurs von heute als am Vormittag), Schreiben 13 s, bereitstellen 52 s. **Nachrechnung** (dritter Lauf 16:19 Uhr, je Stand rund 24 s): **Zwischenstand 14.10.: 9.806.849 Prüfungen** – 10.876 Kursreihen, 841.021 Zeiträume in Ranglisten (Startsitzung, Kurse, Sitzungen, Start- und Endkurs, Rendite bitgleich, R², Zulassung, Trend-Status), 2.160 Ranglisten (A und B, elf Gewichtungen, Perzentile, Gleichstände), Ø Tagesumsatz, Häufigkeit, Prüfsummen; **1.098 Aktien mit dem Schlusskurs davor: 27.894 von 27.894 Zeiträumen gleich wie im Stand mit Schlusskursen**. **Stand 13.10.** (gerechnet mit Software 1.6.0): 9.640.207 Prüfungen; den Ø Tagesumsatz von 6.079 Aktien in anderer Währung als USD nur in Landeswährung nachgerechnet – dieser Stand hat noch keine Wechselkursdatei (`fx.bin` gibt es seit 1.9). **Gefunden:** je Stand 2 Abweichungen – zwei Aktien mit lauter ungültigen Kursen waren als „Kursreihe vorhanden“ markiert, ohne Datei (behoben, Unit-Test). Der erste Lauf meldete zusätzlich 6.079 Abweichungen beim Ø Umsatz in USD: Ursache war die fehlende Wechselkursdatei im alten Stand, nicht die Rechnung (Prüfung angepasst). **Vergleich mit Simons ChatGPT-Bericht 13.10.** (126 Ranglisten 1–30 Tage, 0/100, 40/60, 50/50, 60/40, A und B; ChatGPT mit eigenen Kursen: 6.006 Aktien mit Schlusskurs am 13.10., 4.348 ohne): App je Rangliste 188 bis 3.438 Aktien mehr (Median 757); Plätze 1–5 gleich in 49, 1–10 in 22 Ranglisten (Gruppe A: 1 bzw. 0 von 63); erste Plätze gleich verteilt in Gruppe B (33, 13, 12, 4, 1) und bei den Spitzen über A und B (66 und 25); häufigster Sieger je Gewichtung im gleichen Muster (0/100 eine Aktie mit 25 ersten Plätzen, 10/90 bis 100/0 eine andere). **Live-Prüfung der App:** 23 von 23 Ansichten ohne Fehler; die Meldung „Top 3 nicht absteigend“ im ersten Lauf kam aus dem Prüfskript (zählte die Punkte von „Deine Aktien“ mit) – angepasst, zweiter und dritter Lauf in Ordnung |
| Entwicklungsumgebung, 14.10.2026 15:20–16:05 Uhr | **Version 1.13.0** (Zwischenstand mit allen Aktien, einheitliche Zeilen bei „Deine Aktien“, Knöpfe „Schlusskurse …“) | Python: **298 Unit-Tests** (neu: eigener Stichtag je Aktie – eine Aktie ohne Kurs von heute hat im Zwischenstand Zahl für Zahl dieselben Werte wie eine Rechnung mit dem Handelstag davor als Stichtag: Status, Rendite, Start- und Endkurs, Startdatum, Zahl der Kurse und Sitzungen, R²; sie steht in den Ranglisten, Spitzenreiter mit eigenem Endtag; ohne eigenen Stichtag fehlt sie wie bis 1.12, Prüfwert des Stands mit Schlusskursen unverändert), **55 Integrationstests** (Zwischenstand vor Börsenbeginn in New York: US-Aktie mit dem Schlusskurs vom 12.10. in der Rangliste, Werte für 5, 30 und 90 Tage gleich wie im Stand mit Schlusskursen, Kursreihe endet am 12.10. ohne vorläufigen Punkt, der 13.10. zählt nicht als Lücke, Status mit `boersen_mit_schlusskurs`) und **61 Browser-Tests** bestanden (angepasst: „Deine Aktien“ in Rangfolge-Zeilen mit „Platz 2 · 1 Aktie liegt vorne“ auch auf „Top nach Zahlen“, Hinweis „Schlusskurs 12.10.“ in den Zeilen von Top 3 und Rangliste, Knöpfe „Schlusskurse 12.10.“, kein Wechselknopf mehr bei den Top 3). App: Typprüfung, **76 Tests** (61 bestanden, 15 über Python; neu: Knopfname mit Datum, Texte ohne „offiziell“, Satz zum Schlusskurs davor, kein doppelter Punkt), Build 1.13.0+b59dac8a. **Gefunden und behoben:** Auf „Top nach Zahlen“ fehlte bei eigenen Aktien der Satz „Platz 2 · 1 Aktie liegt vorne“ (Browser-Test schlug an); doppelter Punkt nach dem Datum im Hinweis („vom 13.10..“) |
| GitHub Actions, 14.10.2026 14:22–14:24 Uhr | **Website mit 3 statt 5 Ständen** (Simons Entscheidung 14:15 Uhr): „Alles aktualisieren“ | Lauf **1:52 Minuten** (14:22:03–14:23:55 Uhr) – auf einem langsameren Runner (Rechnen 20 s). Website **218,5 MB statt 325 MB**, **43.834 statt 65.550 Dateien** (Stände 32.994 Dateien, 184,5 MB: Zwischenstand 14.10., offizielle Stände 13.10. und 12.10.); prüfen **5 s** (vorher 6–8 s), hochladen 3 s (vorher 3–5 s), bereitstellen 16 s (schwankt bei GitHub Pages zwischen 2 und 22 s). Das Sichern im Hintergrund (17,7 s) war diesmal der letzte Schritt vor dem Bereitstellen: 5 s gewartet. Live-Prüfung um 14:24 Uhr: **23 von 23 Ansichten ohne Fehler**, „aufbewahrte Stände: 3“, Wechsel vom Zwischenstand in den offiziellen Stand und zurück, entsperrt in 5,1 s, erneut geöffnet in 1,7 s |
| Entwicklungsumgebung, 14.10.2026 14:15–14:27 Uhr | **Website mit 3 Ständen** (`aufbewahrung.site_snapshots: 3`, gleicher Rückfallwert im Code) | Python: **297 Unit-Tests** (neu: 3 – Konfiguration und Rückfallwert 3; die neuesten drei Stände samt Zwischenstand; der neueste vollständige Stand kommt zusätzlich dazu, wenn die drei neuesten Teilstände sind), **55 Integrationstests** und **60 Browser-Tests** bestanden; App unverändert (1.12.0+6d833660) |
| GitHub Actions, 14.10.2026 13:51–14:05 Uhr | **1.12.0, drei weitere Läufe** „Alles aktualisieren“ (Python-Umgebung aus dem Zwischenspeicher) und Live-Prüfungen | **14:03 Uhr: 2:04 Minuten** (Runner nach 5 s; Laufschritt 75 s mit Rechnen 19 s und Schreiben 10 s, prüfen 8 s, hochladen 5 s, Sichern 0 s gewartet, bereitstellen 17 s). **13:51 Uhr: 1:56 Minuten**, davon 21 s Warten auf einen Runner (bei GitHub); Umgebung aus dem Zwischenspeicher 2 s statt 11 s Installation; Laufschritt 63 s (Rechnen 15 s, Schreiben 8 s), prüfen 7 s, hochladen 3 s, Sichern am Ende 4 s gewartet, Bereitstellen als eigener Job 4 s Warten + 5 s. **13:56 Uhr mit Bereitstellung im selben Job: 2:06 Minuten** (Runner nach 5 s), auf diesem Runner langsamer gerechnet: Kursreihen laden 11 s, Rechnen 18 s, Schreiben 10 s (Laufschritt 73 s), prüfen 8 s, hochladen 5 s, Sichern 0 s gewartet, bereitstellen 22 s. Kurse abrufen in allen drei Läufen 11 s (62 Abfragen, 5.491–5.492 Aktien mit Kurs von heute). Live-Prüfungen um 13:49 Uhr und – nach der Bereitstellung im selben Job – um 13:58 Uhr: App 1.12.0+6d833660, je **23 von 23 Ansichten ohne Fehler** (Zwischenstand 13:48 bzw. 13:56 Uhr), entsperrt in 4,8 bzw. 5,1 s, erneut geöffnet in 1,7 bzw. 1,8 s; Top 3 oben auf der Startseite mit 3 Zeilen (US-Aktien im Zwischenstand vor Börsenbeginn ohne Platz, wie erwartet). Nebenbei „Sicherung prüfen“ (Wiederherstellung aus dem Release) um 13:43 Uhr bestanden |
| GitHub Actions, 14.10.2026 13:47–13:49 Uhr | **Version 1.12.0 im Betrieb:** „Alles aktualisieren“ (Voreinstellung) | Lauf **1:51 Minuten statt 3:02** (13:47:37–13:49:28 Uhr), darin einmalig 14 s für das Anlegen der Python-Umgebung im Zwischenspeicher. Laufschritt **48 s statt 102 s**: Zustand laden 6 s, Kurse abrufen **11 s statt 22 s** (40 Abrufe „quote“ → 5.814 Kurse, 22 Abrufe „spark“ → 0; 5.491 Aktien mit Kurs von heute, 31 Börsen mit Kurs, ohne Kurs BVMF, XMEX, XNYS, XTSE), Kursreihen laden 6 s + Rechnen 9 s (vorher zusammen 23 s), **Dateien schreiben 6 s statt 25 s**, ältere Stände 1 s statt 4 s, Website zusammenstellen 3 s statt 11 s. Danach: Website prüfen **6 s statt 14 s**, packen unter 1 s, **hochladen 5 s statt 14 s** (325 MB, 65.550 Dateien), Sichern lief im Hintergrund (16,4 s, am Ende 2 s gewartet), **bereitstellen 16 s statt 22 s**. **Beobachtet:** Fünf Läufe (13:38–13:43 und 14:00–14:02 Uhr), die unmittelbar nach einer Änderung der Workflow-Datei und dem Wieder-Einschalten des Workflows gestartet wurden, blieben bei GitHub vor dem Start stehen („Queued“ ohne Job) und lassen sich nicht abbrechen; mit einigen Sekunden Abstand gestartete Läufe begannen sofort. Zwischendurch wurde `actions/upload-artifact` von der Commit-Kennung auf die Versionsmarke `@v7` umgestellt – ob das nötig war, ist offen (siehe Fehlerbehebung) |
| Entwicklungsumgebung, 14.10.2026 13:10–13:40 Uhr | **Version 1.12.0** (Aktualisieren noch schneller) | Python: **294 Unit-Tests** (neu: parallele Kursabfragen liefern dieselben Kurse und Abrufe wie nacheinander, gemeinsamer Mindestabstand aller Abrufer, Drosselung stoppt alle und behält geladene Kurse; paralleles Schreiben ergibt dieselben Dateien und Prüfsummen wie ein Prozess; schnelle Umwandlung = bisherige; Sichern als eigener Prozess mit Ergebnisdatei und Warten am Ende – ohne Zugang meldet es den Fehler; Workflow: Pages-Artefakt im Format von upload-pages-artifact ohne Kompression, Bereitstellung erst nach Prüfung und erfolgreichem Sichern) und **55 Integrationstests** (neu: Zwischenstand sichert im Hintergrund, „sichern-warten“ meldet Erfolg und ohne Ergebnis einen Fehler; Website aus im Voraus entpackten Ständen); App: Typprüfung, 74 Tests (59 bestanden, 15 über Python), Build 1.12.0; **60 Browser-Tests** bestanden. Gemessen mit 6.000 synthetischen Aktien: Schreiben 17,6 s in einem Prozess, 10,0 s mit zwei Kernen |
| GitHub Actions, 14.10.2026 12:48–12:57 Uhr | **Version 1.10.0 im Betrieb:** „Alles aktualisieren“ (Voreinstellung) und danach „App mit echten Daten prüfen“ | Lauf **3 Minuten statt 7** (12:48:37–12:51:39 Uhr): Kurse abrufen 22 s statt 120 s (**62 statt 303 Sammelabfragen**, 5.471 Aktien mit Kurs von heute), Rechnen 23 s statt 45 s, Dateien schreiben 25 s statt 49 s, Sichern parallel 16 s (Warten darauf 1 s; vorher 54 s), Website 11 s. Live-Prüfung App 1.10.0+af61b2b0: **21 von 21 Ansichten ohne Fehler**, entsperrt in 4,2 s, erneut geöffnet in 1,7 s, Musterdepots mit 20 Aktien in der Häufigkeitsliste (Standard 40/60–60/40) |
| Entwicklungsumgebung, 14.10.2026 12:55–13:20 Uhr | **Version 1.11.0** (Top 3 nach Zahlen, Börsenwert, Volumen-Anstieg) | Python: **287 Unit-Tests** (neu: Börsenwert in EUR für USD- und Pence-Kurse) und **54 Integrationstests** bestanden; App: Typprüfung, **74 Tests** (59 bestanden, 15 Datenvertragstests über Python; neu: 8 zur Regel – Punkte je Teil, Abzug Börsenwert, Volumen nur bei steigendem Kurs, nur Aktien mit Top-10-Nennung, Gleichstand, Warnzeichen, Stand ohne Börsenwert, Trefferquote), Build 1.11.0; **60 Browser-Tests** bestanden (neu: Top 3 ganz oben auf der Startseite und Punkte **unabhängig nachgerechnet** aus Fensterköpfen und Signal-Stand, ganze Rangfolge, Merken → „Deine Aktien“ mit Platz, Filter „Ohne Warnzeichen“, Liste „Volumen gestiegen“, Börsenwert und Volumen-Leiste in der Einzelansicht; Breitenprüfung um drei Ansichten erweitert) |
| Entwicklungsumgebung, 14.10.2026 12:20–12:55 Uhr | **Version 1.10.0** (schneller aktualisieren, Lesbarkeit auf dem S25+, Musterdepots mit Standard 40/60, 50/50, 60/40) | Python: **286 Unit-Tests** (neu: Kursabfrage „quote“ mit bis zu 150 Werten je Abruf samt Rückfall auf „spark“, Anmeldung neu bei 401, gedrosselt; schnelles JSON = bisheriges JSON auch mit NaN und NumPy-Werten; gzip-Stufen; paralleles Rechnen auf mehreren Kernen = bisherige Schleife Zahl für Zahl samt Prüfsumme und Ranglisten; Reihenfolge der gestaffelten Aktualisierung; EUR-Umrechnung von Pence und Cent) und **54 Integrationstests** bestanden (neu: gestaffelte Aktualisierung – Stufe 1 rechnet nur die vorderen Aktien und lädt nichts hoch, Stufe 2 rechnet alle und sichert); App: Typprüfung, **66 Tests** (51 bestanden, 15 Datenvertragstests über Python; neu: Standardauswahl 40/60, 50/50, 60/40), Build 1.10.0; **59 Browser-Tests** bestanden (neu: keine von 29 Ansichten breiter als das Handy). **Gefunden und behoben:** die Einzelansicht war auf 384 px breiter als der Bildschirm (Tabelle „Rang je Gewichtung“: lange Gründe ohne Umbruch und unsichtbare Vorlesetexte) – das Handy zoomte heraus, „30 Tage“ war nicht antippbar; die bisherigen Breitenprüfungen hatten mit der mitwachsenden Fensterbreite verglichen. Paralleles Sichern: Der Zwischenstand lud beim Zusammenstellen der Website die Datenbank erneut herunter, während sie im Hintergrund ersetzt wurde (Test: HTTP 404) – jetzt werden nur noch Archive geladen. Umsatz in EUR im Signal-Stand bei Kursen in Pence, Cent und Agorot 10.000-fach zu hoch |
| GitHub Actions, 14.10.2026 11:17–11:25 Uhr | **„App mit echten Daten prüfen“** gegen die veröffentlichte App 1.9.2+5ad42731 (verschlüsselt, echter Zwischenstand vom 14.10. und offizieller Stand vom 13.10.) | Erste Prüfung (11:17 Uhr): 20 von 21 Ansichten – die Prüfung wartete in der Umschichtungs-Regel auf Zeilen, die App zeigte aber richtig „Im Zwischenstand nicht gerechnet“ (die Regel braucht Wochenschlusskurse); Prüfung angepasst und um den Wechsel in den offiziellen Stand ergänzt. **Zweite Prüfung (11:23 Uhr): alles in Ordnung** – entsperrt und geladen in 5,0 s, erneut geöffnet in 1,8 s ohne Passphrase, Service Worker aktiv, **21 von 21 Ansichten ohne Fehler**, keine Konsolenfehler; Bericht 1–30: 4 Tabellen, Matrix 30 Zeilen, 126 von 240 Ranglisten mit Spitzenreiter (Gleichmäßigkeit erst ab 15 Schlusskursen); **Musterdepots: 15 Aktien in den Häufigkeitslisten (5 gemeinsam), 4 Depots, „10 Sieger“ mit 10 Positionen, 30 Fenster, Basis USD (Wechselkurse im Zwischenstand vorhanden)**; Umschichtungs-Regel im offiziellen Stand 25 Zeilen, Rückweg zum Zwischenstand ja; Signale 10.822 Aktien, 7.745 mit Kursziel, Gesamtwertung stark 31 / mittel 794, Daytrader-Check 11 Punkte |
| GitHub Actions, 14.10.2026 11:05–11:14 Uhr | Lauf **„Alles aktualisieren“** mit der neuen Voreinstellung (Software 1.9.1, nichts im Formular geändert) | bestanden in 8½ Minuten: Zwischenstand Stichtag 14.10. mit **5.363 Aktien mit aktuellem Kurs** (bis 11:07 Uhr, davon 1.829 nach Börsenschluss in Asien und Australien), 303 Sammelabfragen, 30 Börsen mit Kurs; ohne Kurs BVMF, XDUB, XMEX, XNYS, XTSE (Amerika noch nicht geöffnet, Dublin ohne Kurs); offizieller Stand vom 13.10. lag bereits vor → Kennzahlen-Schritt richtig übersprungen; Website bereitgestellt |
| Entwicklungsumgebung, 14.10.2026 11:08–11:14 Uhr | **Version 1.9.2** (Feinschliff Musterdepots nach Sichtprüfung auf 384 × 832) | Sichtprüfung aller Abschnitte der Depots-Seite, der Startseite und der Seite „Aktualisieren“ (keine waagerechte Verschiebung, keine Konsolenfehler); gefunden und behoben: „außerhalb Top 10“ ragte über die Spalte (jetzt Rang der vollständigen Reihenfolge, grau über 10), krumme Achsenschritte (jetzt 0/10/20/30/40 %), „1 Tage“. Python: 270 Unit-Tests bestanden; App: 65 Tests (50 bestanden, 15 über Python; neu: Rang über 10 und ohne Nennung), Build 1.9.2; Browser-Tests Depots, Bericht, Startseiten-Hinweis, Tippflächen ≥ 44 px und Beschriftungen bestanden |
| Entwicklungsumgebung, 14.10.2026 10:40–11:05 Uhr | **Version 1.9.1** (alles selbst aktualisieren mit einem Tipp) | Python: **270 Unit-Tests** (Workflow: „Alles aktualisieren“ voreingestellt und oben im Formular, Kennzahlen-Job nach einem Zwischenstand nur bei neuem offiziellem Stand oder „erzwingen“) und **53 Integrationstests** bestanden (neu: ein Tipp ohne offiziellen Stand des letzten Börsentags rechnet zuerst den offiziellen Stand, meldet `kennzahlen=true`, der Kennzahlen-Schritt danach lässt den Zwischenstand auf der Website; zweiter Tipp nur Zwischenstand; „erzwingen“ rechnet trotz Voreinstellung den offiziellen Stand); App: 65 Tests (50 bestanden, 15 über Python), Build 1.9.1; **58 Browser-Tests** bestanden (Knopf „Kurse jetzt aktualisieren“ auf der Startseite, drei Schritte und „Weitere Möglichkeiten“). Live-Prüfung der App lokal gegen die DEMO-Website: 8 von 8 Prüfungen, 21 Ansichten ohne Fehler, Musterdepots mit 4 Depots, 10 Positionen, 30 Fenstern, Basis USD |
| Entwicklungsumgebung, 14.10.2026 10:05–10:35 Uhr | **Version 1.9.0** (Musterdepots, Wechselkursdatei `fx.bin`) | Python: **270 Unit-Tests** und **51 Integrationstests** bestanden (neu: `fx.bin` im Datenstand = gespeicherte EZB-Referenzkurse der letzten 100 Tage, nichts nach dem Stichtag, im Manifest und in den Prüfsummen); App: Typprüfung, **65 Tests** (50 bestanden, 15 Datenvertragstests über Python; neu: zwei Top-10-Listen mit Rang, gemeinsamen Aktien und Sortierung wie in der Datei, Startkurs am oder vor Stichtag − h mit Feiertagen, USD- und EUR-Rendite mit Kreuzkurs, fehlender Wechselkurs, Depot mit Beiträgen = Depotrendite, Endgewichte = 100 %, Endwerte, fehlender Startkurs mit neu verteilten Gewichten, 30 Fenster mit Bewertungsstart am Werktag, eigene Depots geprüft, Standard Dreier- und Viererdepot; Datenvertrag: Aktienrendite im Depot = Kursrendite der Ranglisten bei gleichem Starttag, USD-Aktien in USD unverändert), Build 1.9.0; **58 Browser-Tests** bestanden (neu: Musterdepots – Häufigkeitsliste mit gemeinsamen Aktien, Depotrendite unabhängig aus Kursreihen und Wechselkursen nachgerechnet in USD (30 Tage) und Originalwährung (14 Tage), Beiträge ergeben die Depotrendite, 30 Fenster in der Tabelle, eigenes Depot per Häkchen anlegen und löschen; Depots in den Prüfungen der Bedienelemente und Beschriftungen) |
| Entwicklungsumgebung, 14.10.2026 09:40–09:55 Uhr | **Version 1.8.2** (Gesamtwertung im Bericht 1–30) und erweiterte Live-Prüfung | Python: 270 Unit-Tests, Datenvertragstest der App; App: Typprüfung, **59 Tests** (45 bestanden, 14 Datenvertragstests über Python; neu: Gesamtwertung je ISIN nur ab `signale-v2`, kein Ersatzwert aus älteren Ständen), Build 1.8.2; **57 Browser-Tests** bestanden (Bericht-Test erweitert: Kästchen hinter dem Spitzenreiter = Gesamtwertung aus dem Signal-Stand, gerundet wie in der App; neu: Startseite mit den drei häufigsten Spitzenreitern des Berichts = Nachzählung, Antippen öffnet den Bericht mit der Aktie hervorgehoben). Live-Prüfung der App (`tests/live/test_app_live.py`) lokal gegen die DEMO-Website: 7 von 7 Prüfungen, 20 von 20 Ansichten ohne Fehler, Bericht 1–30 mit 4 Tabellen und 30 Matrixzeilen, Einzelansicht mit Gesamtwertung und 11 Daytrader-Punkten |
| Entwicklungsumgebung, 14.10.2026 09:10–09:35 Uhr | **Version 1.8.1** (Bericht 1–30 Tage) | Python: **270 Unit-Tests** und **50 Integrationstests** bestanden; App: Typprüfung, **58 Tests** (44 bestanden, 14 Datenvertragstests über Python; neu: 4 – Spitzenreiter 1–30 je Gruppe mit Wiederholungen je Spalte, leere kurze Zeiträume nur bei gleichem Grund in A und B zusammengefasst, Matrix mit vier Gewichtungen und Zählung über A und B, Einstieg in den Kursverlauf, Kennzahlen, CSV mit 240 Zeilen), Build 1.8.1; **56 Browser-Tests** bestanden (neu: Bericht 1–30 – Einstieg von der Startseite, vier Tabellen, jede Zelle = Platz 1 der Übersicht des Stands in A und B, zusammengefasste Zeilen nur bei wirklich leeren Zeiträumen, Kursrendite wie in der Fensterdatei, eine Gewichtung allein, Matrix A und B ohne seitliches Wischen, „Am häufigsten auf Platz 1“ = Nachzählung, Hervorheben mit der richtigen Zahl umrahmter Zellen und „Nächstes Vorkommen“, Markierung entfernen, Häufigkeit, CSV mit 240 Zeilen; Bericht auch in der Prüfung der Mindestgröße von Bedienelementen und der Beschriftungen) |
| Entwicklungsumgebung, 14.10.2026 08:45–09:05 Uhr | **Version 1.8.0** (Zwischenstand mit aktuellen Kursen) | Python: **270 Unit-Tests** (neu: 7 – begonnene Sitzungen je Börse, Wahl des Stichtags mit Mindestanteil und Lückenregel, Ø Tagesumsatz ohne den laufenden Tag bei gleicher Rendite, Archivnamen) und **50 Integrationstests** bestanden (neu: 7 – Zwischenstand mit vorläufigen Kursen, die nie gespeichert werden; US-Aktien vor Börsenbeginn „Kurs am Stichtag fehlt“; Status und Index; neuer Zwischenstand ersetzt den alten samt Archiv; offizieller Stand löst ihn ab; vor Börsenbeginn „keine neuen Daten“; zu wenige Kurse; `demo --zwischenstand`; `ci --zwischenstand` gegen die nachgebildete GitHub-API mit Aufräumen alter Archive im Release); App: Typprüfung, 54 Tests (40 bestanden, 14 Datenvertragstests über Python), Build 1.8.0; **55 Browser-Tests** bestanden (neu: 3 – Zwischenstand oben mit Kennzeichnung und Wechsel zum offiziellen Stand und zurück, Einzelansicht „(vorläufig)“, Status und Umschichtungs-Regel, Anleitung „Jetzt aktualisieren“). Dabei gefunden und behoben: beim Wechsel zwischen Ständen kurz ein 404 für die Umschichtungs-Regel des neuen Stands; eine CSS-Klasse des Daytrader-Checks überschrieb Ankreuzfelder |
| Entwicklungsumgebung, 14.10.2026 08:30–08:40 Uhr | **Version 1.7.1** (Daytrader-Check, „Was die Analysten denken“, Dafür/Dagegen) | App: 50 Tests (36 bestanden, 14 Datenvertragstests über Python; neu: Analysten-Text mit Richtung, Spanne, Quellen, Urteilen, Bewertung und Prognose; Dafür/Dagegen mit überkauftem RSI immer „dagegen“; Daytrader-Check mit Werten, Urteil je Punkt, relativer Stärke und Zählung), Build 1.7.1; Browser-Test der Einzelansicht erweitert (Daytrader-Check mit mindestens 11 Punkten und Erklärung, Analysten-Text, Dafür/Dagegen) |
| Entwicklungsumgebung, 14.10.2026 08:15–08:25 Uhr | **Version 1.7.0** (Gesamtwertung: Steig-Konstanz 30/60/90 Tage, Kursziel-Potenzial, Trefferquote der Steig-Konstanz) | Python: **262 Unit-Tests** (neu: 7 für Steig-Konstanz, Kursziel-Kurve und Gesamtwertung – stetiger Anstieg vor kurzem Schub, ohne Kursziel 0 Punkte, Zufallskurs nur mittlere Konstanz) und **43 Integrationstests** bestanden (Signal-Stand mit Gesamtwertung, Liste nach Gesamtwertung absteigend, neuer Stand bei älteren Rechenregeln); App: Typprüfung, 47 Tests (33 bestanden, 14 Datenvertragstests über Python; neu: Liste „Gesamt“ mit Rückfall für alte Stände, Steig-Konstanz je Zeile, Aufschlüsselung und Trefferquote), Build 1.7.0; **52 Browser-Tests** auf simuliertem S25+ bestanden (neu geprüft: Liste „Gesamt“ absteigend sortiert, Streifen „30 T ▲…“, Abschnitt Gesamtwertung mit vier Teilen, Tabelle und Erklärung) |
| Entwicklungsumgebung, 14.10.2026 07:40–07:50 Uhr | **Version 1.6.0** (Potenzial, Signale, neue Struktur; 1.5.4 Schlusskurs aus Kursmeldung) | Python: 255 Unit-Tests und 43 Integrationstests bestanden (darunter 14 neue Signal-Tests, 7 Ablauf-Tests für Kennzahlen und Signal-Stand, 5 Tests für den Schlusskurs aus der Kursmeldung, 6 für Kursziele/Crumb); App: Typprüfung, 45 Tests (31 bestanden, 14 Datenvertragstests über Python), Build; **52 Browser-Tests** auf simuliertem S25+ bestanden (neu: Kandidaten auf der Startseite, Einzelansicht mit Urteil und Erklärungen, Potenzial-Liste mit Filtern, Signale auf der verschlüsselten Website) |
| GitHub Actions „Datenquellen prüfen“, 14.10.2026 06:40–07:00 Uhr | Kursmeldung als Schlusskurs, Kursziele, weitere Quellen | Kursmeldung = letzte Stundenkerze bei 13 europäischen Werten ohne Tageskerze (0,0 Basispunkte), = Tageskerze bei 7 Werten mit vollständiger Kerze (0,0 Basispunkte); Kursziele bei 21 von 22 Testaktien weltweit, 50 Abrufe in 20 s ohne Drosselung; Nasdaq, Stocktwits, Trading Central (US) erreichbar; nach der Absicherung 15 Tests bestanden, 1 übersprungen (EODHD ohne Schlüssel) |
| Entwicklungsumgebung, 13.10.2026 22:12 Uhr | Alle Python-Tests, Version 1.5.2 | 315 Tests: **305 bestanden**, 10 übersprungen (6 Live-Tests ohne Netz, 4 Kalendertests ohne Bibliothek), 0 Fehler |
| Entwicklungsumgebung, 13.10.2026 | App 1.5.2: Typprüfung, 38 Tests, Build | ohne Fehler; 24 bestanden, 14 Datenvertragstests über Python (14 von 14 bestanden); Build byte-gleich |
| GitHub Actions „Prüfung“, 13.10.2026 | Versionen 1.3.0 (16:33 Uhr), 1.4.0 (16:56 Uhr), 1.4.1 (17:19 Uhr), 1.5.0 (18:41 Uhr, Commit 203d136), 1.5.1 (21:07 Uhr 75b340b, 21:17 Uhr 9902692, 21:37 Uhr 772a84e, 21:53 Uhr 7fd7552), **1.5.2 (22:13 Uhr, 62c7c5e)** | alle grün; 1.5.2: 315 Tests in 215,2 s, 6 Live-Tests übersprungen, echte Börsenkalender 4 von 4, `app/dist` identisch mit dem Build auf GitHub |
| GitHub Actions „Täglicher Lauf“ `nur_website`, 13.10.2026 18:48 Uhr | App 1.5.0 bereitstellen | grün in 37 s: „App 1.5.0+087dc246 neu zusammengesetzt“; `version.json` und `status.json` der Website zeigen 1.5.0 und den Zeitplan 07:00 |
| GitHub Actions „Prüfung“, 13.10.2026 | Version 1.1.0 (13:28 Uhr) und Folgeänderung (13:34 Uhr) | 218 bzw. 220 Tests bestanden, je 6 Live-Tests übersprungen; echte Börsenkalender 4 von 4 |
| GitHub Actions „App mit echten Daten prüfen“, 13.10.2026 22:52 Uhr (Commit 9405d65) | veröffentlichte App 1.5.2+02388482 mit dem echten Stand `2026-10-12_c3806c24`, Chromium im Format des S25+ | **alles in Ordnung:** entsperrt und geladen in 5,6 s; 17 von 17 Ansichten ohne Fehler (je 1,1–1,3 s; Rendite 90 Zeiträume, Ranking 10 Plätze, Matrix 990 Zellen); Einzelansicht der ersten Aktie mit 19 Kennzahlzeilen, Kursgrafik und zweitem Börsenplatz in 3,3 s; erneut geöffnet in 1,7 s ohne erneute Passphrase, Service Worker aktiv; keine Konsolenfehler, keine fehlgeschlagenen Abrufe. Vorläufe um 22:44 und 22:48 Uhr: Prüfskript wartete nicht auf die nachgeladene Kursreihe der Einzelansicht (behoben); einmal eine Antwort 503 ohne erkennbare Datei – im nächsten Lauf nicht wiederholt, seither werden fehlgeschlagene Abrufe mit Datei gemeldet |
| GitHub Actions „Datenquellen prüfen“, 13.10.2026 12:02 Uhr | echte TR-Liste, OpenFIGI, Yahoo | 7 bestanden, **1 fehlgeschlagen** (Yahoo ohne Schlusskurs 12.10.2026 in Europa und Asien), 1 übersprungen (EODHD ohne Schlüssel) |
| GitHub Actions „Täglicher Lauf“, 13.10.2026 | echte Läufe | **Erster echter Datenstand um 20:37 Uhr** (Teilstand: USA, Australien, Neuseeland), **erster vollständiger Stand um 21:50 Uhr** (alle 31 Börsen, nachdem Yahoo die Schlusskurse vom 12.10. nachgeliefert hatte), um 22:18 Uhr neu gerechnet mit 1.5.2 (Abgleich v3: 8 statt 75 auffällige Aktien); App 1.5.2 online. Die Läufe davor endeten mit „wartet auf Kursanbieter“ (Abschnitt 7) |

## Umgebung (Entwicklung)

| | |
|---|---|
| Rechner | Linux-Container, 2 vCPU (Intel Xeon 2,1 GHz), 8 GB RAM |
| Python | 3.13.16 (numpy 2.5.3, pandas 3.0.5, PyYAML 6.0.3, cryptography 50.0.1, requests 2.34.2, pdfplumber 0.11.10, pypdf 5.9.0) |
| Node.js / TypeScript | 22.22.0 / 6.0.3 |
| Browser-Tests | Playwright 1.56.0 mit Chromium 141.0.7390.37 |
| Netz | Nur lokale Verbindungen. TR-Liste, OpenFIGI, Yahoo, EZB, PyPI und npm-Registry waren gesperrt (z. B. EZB am 13.10.2026: „CONNECT tunnel failed, response 403“). |
| Daten | Ausschließlich klar gekennzeichnete synthetische Testdaten (DEMO: Namen beginnen mit „DEMO“, ISINs mit „ZZ“) und erzeugte Testreihen. Keine Livekurse. |

Die Workflows in GitHub Actions verwenden dieselbe Python-Version (3.13) und Node 22.

## 1. Gesamtlauf aller Python-Tests

```bash
PYTHONPATH=backend LOG_LEVEL=WARNING python -W always::ResourceWarning -m unittest discover -s tests -t . -v
```

**Ergebnis (13.10.2026, 22:12 Uhr, Version 1.5.2): 315 Tests, 305 bestanden, 10 übersprungen, 0 Fehler, Dauer 322,3 s, keine Ressourcenwarnung.** Version 1.5.0 war um 18:40 Uhr mit 298 Tests grün (288 bestanden, 293,8 s); 1.5.1/1.5.2 bringen vier Einheitentests zu fehlenden Börsentagen, neun zum Börsenplatz-Abgleich (Börsenkalender, Umsatz, Schwelle nach Tagesschwankung), je einen Pipeline-Test zur Teilstand-Schwelle und zu Fehlern im Abgleich sowie zwei Browser-Tests zum Teilstand dazu.

Ein Gesamtlauf kurz davor hatte einen Fehler: Ein älterer Browser-Test erwartete einen Text nur einmal auf der Seite, die neue Häufigkeitsansicht nennt ihn zweimal (sichtbar und für Screenreader). Der Test wurde präzisiert, die App blieb unverändert; maßgeblich ist der Lauf oben.

| Modul | Tests | Inhalt |
|---|---:|---|
| `tests/unit/test_metrics.py` | 14 | Rendite, OLS, R², Steigung, Rauschen, MDD, Referenz mit exakter Bruchrechnung und `numpy.polyfit`; **1.5:** positive Schlusskursvergleiche strikt gezählt |
| `tests/unit/test_windows.py` | 11 | Kalenderfenster 1–90, Startsitzung, fehlende Endkurse, Feiertage, Stichtag |
| `tests/unit/test_quality.py` | 26 | Zulassung (V/U), 98-%-/80-%-Grenzen, Splits, Einheiten, Sprünge, Kursbewegung ohne Umsatz; **1.5 (Methode 1.7.0):** fehlendes Volumen an einer Beobachtung, kein positives Volumen an Start oder Ende, gemeldeter Split im Fenster zurückgehalten (auch bei bereinigter Reihe, Freigabe nur nach Prüfung), jeweils mit Status der Vorversion; **1.5.1 (Methode 1.8.0):** höchstens 20 % fehlende Börsentage, ein fehlender Tag immer erlaubt (exakt als Bruch), Vorversion 98 % im Vergleich, ein fehlender Tag beim Kursanbieter wie am 12.10.2026 (Zeiträume 2–90 bewertet, 1 Tag ohne Startkurs, nichts aufgefüllt, Vergleich zählt 67 neu bewertete Paare aus Status 12), größere Lücken weiter ausgeschlossen, Volumenbezug wählbar |
| `tests/unit/test_ranking.py` | 24 | Perzentile, Gleichstände, alle elf Gewichtungen, native/common_trend, Untergruppen; **1.4:** Gruppe B (Vergleichsmengen V ∩ L und U ∩ L, eigene Perzentile, 0/100 und 100/0 in der Reihenfolge der Gruppe A, gemischte Gewichtungen können abweichen, leere Gruppe); **1.5:** Reihenfolge Score → Rendite → ISIN für alle Gewichtungen, bei gleichem Score und gleicher Rendite entscheidet die ISIN (nicht R²) |
| `tests/unit/test_frequency.py` | 16 | Top-1/3/10-Häufigkeiten, Nenner, Invarianten, Renditesieger, Gesamtmaximum |
| `tests/unit/test_engine_coverage.py` | 5 | Abdeckungsbilanz, Reproduzierbarkeit |
| `tests/unit/test_turnover.py` | 22 | **1.1:** Ø Tagesumsatz (Definition, fehlende Sitzungen, 16 von 20, Untereinheiten, Wechselkurse, Split), zwei Rendite-Ranglisten, Übernahmemuster |
| `tests/unit/test_ecb.py` | 11 | **1.1:** EZB-Datei (Parser, Schutz vor XML-Angriffen, HTTP-Fehler), Ablage im Lauf, Rückfall auf gespeicherte Kurse; **1.3:** ganze EZB-Reihe als ZIP (CSV, „N/A“, Rückblickzeitraum, unerwartete Archive), einmaliges Laden, Ausfall verkürzt nur den Rückblick |
| `tests/unit/test_rotation.py` | 12 | **1.3:** Wochenwerte (letzter und erster Kurs, Lücken nicht aufgefüllt, Volumen ohne Angabe, Sprünge über das Wochenende), Kandidatenauswahl (Umsatz, Umsatztage, Abdeckung, Tagessprung), erster Freitag im Monat, Haltepuffer, Ausführung zum ersten Kurs der Folgewoche, beschlossene Umschichtung am letzten Freitag, Vergleich gleich gewichtet, Kosten, Steuer mit Pauschbetrag, Erstattung und Verlusttopf, Tagesvorschlag |
| `tests/unit/test_venues.py` | 21 | **1.2:** Wahl des zweiten Börsenplatzes (Xetra vor Frankfurt, nie Referenz, gleiche Kursreihe oder OTC), Vergleich in Referenzwährung, Schwellen, Endkursabweichung, Pence, Wochenende, fehlende Vergleichskurse und Wechselkurse; **1.5.1 (`boersenplatz-v2`):** Lieferlücke an einem Sitzungstag wird nicht mit dem Freitagskurs überbrückt (v1 zum Vergleich: alle Zeiträume auffällig), Feiertag am zweiten Platz → letzte Sitzung davor, Lücke am Start nur für diesen Zeitraum, Kurse an Tagen ohne Sitzung ignoriert; **1.5.2 (`boersenplatz-v3`):** robuste Tagesschwankung unempfindlich gegen einen einzelnen Sprung, Schwelle mindestens 10 % und höchstens Faktor 2, stark schwankende Aktie innerhalb ihrer Schwankung unauffällig (nach fester Regel auffällig), Faktor 2,2 immer auffällig, kein Umsatz am Stichtag oder Start → kein Vergleich, unbekanntes Volumen zählt als vorhanden, Auswertung nach fester 10-%-Regel |
| `tests/unit/test_update.py` | 5 | **1.2:** Startlinks auf GitHub (nur in GitHub Actions, unsichere Werte abgewiesen), nächster möglicher Kursstichtag nach derselben Regel wie der Stichtag |
| `tests/unit/test_summary.py` | 5 | Kurzbericht des Laufs als GitHub-Hinweis (Zählungen vor Beispielen, Kürzung, Börsen ohne Kursdaten mit Beispielen) |
| `tests/unit/test_symbols.py` | 11 | **1.4.1:** Kürzel ohne Kursdaten (Börsentabelle v2, Schreibweisen, Suche nach ISIN, Plausibilität, Migration 0006) |
| `tests/unit/test_providers.py` | 30 | TR-PDF-Parser (erzeugte PDFs), Yahoo-/EODHD-Antwortformate, OpenFIGI-Zuordnung, Drosselung, Stichtag, Sommerzeit, Verschlüsselung, Schwärzung; Zeitzonen mit gleicher Verschiebung nur mit bestätigendem Börsencode |
| `tests/unit/test_workflows.py` | 8 | GitHub-Workflows: Auslöser, Rechte, Secrets, Bereitstellung nur nach bestandener Prüfung, Zeitplan = Konfiguration |
| `tests/integration/test_pipeline.py` | 27 | **1.4:** Gruppe B in Fenster-, Übersichts-, Häufigkeits- und Kursreihendateien (nur Aktien aus L, Vergleichsmenge U ∩ L, Kopfdatei, Spitzenreiter, Fundstellen, Rangmatrix, Kalenderstarts); **1.3:** Umschichtungs-Regel im Lauf (alle 24 Varianten, Prüftage, Ausführung am nächsten Handelstag, Käufe nur unter den ersten N, Trend gleich der Rendite aus der Kursreihe), Langhistorie in Etappen mit Wochenwerten und Neuladen nach Split, kein Langabruf bei Drosselung; Täglicher Lauf mit DEMO-Quelle: Veröffentlichung, Doppelstart, Checkpoint, erneuter Abruf fehlender Stichtagskurse, von Hand gestartete Läufe warten nur (letzter geplanter Versuch entscheidet), Ausfall, Parserfehler, atomares Schreiben, Tickerwechsel, Sicherung; beide Rendite-Ranglisten in allen Dateien gleich; Börsenplatz-Abgleich (Kennzeichen, keine Änderung von Rendite und Rang, fehlender Platz, Abruffehler, Drosselung, gespeicherte Wahl; **1.5.1:** Fehler der Quelle oder nicht lesbarer Börsenkalender verhindern die Veröffentlichung nicht); nächster Kursstand im Status |
| `tests/integration/test_ci_flow.py` | 7 | Kompletter Ablauf `traktien ci` gegen nachgebildete GitHub-REST-API auf frischen Runnern; lückenloser Austausch der Sicherung; nur Website neu bereitstellen; neue Passphrase |
| `tests/integration/test_app_contract.py` | 1 | Startet die 14 Datenvertragstests der App (Node) gegen echte DEMO-Dateien, unverschlüsselt und verschlüsselt |
| `tests/e2e/test_mobile_app.py` | 49 | Gebaute App im Browser auf simuliertem Galaxy S25+ (dazu Querformat und Desktop) |
| `tests/live/…` | 10 | **übersprungen** (6 Quellen ohne Netz, 4 Kalender ohne Bibliothek) – in GitHub Actions ausgeführt, Abschnitt 7 |

## 2. App (TypeScript)

```bash
cd app && npm run typecheck && npm test && npm run build
```

- Typprüfung: **ohne Fehler**.
- `npm test`: 38 Tests, **24 bestanden**, 14 übersprungen – die 14 Datenvertragstests brauchen erzeugte Datendateien und laufen über `tests/integration/test_app_contract.py`. Dort: **14 von 14 bestanden, 0 übersprungen** (der Python-Test verlangt ausdrücklich `# fail 0` und `# skipped 0`).
- **1.5 im Datenvertrag:** *Prüfung 20* – für jede der elf Gewichtungen und beide Gruppen ist jede Zeile von „Sieger nach Zeitraum“ (7 … 90 Tage) Platz 1 der vollständigen Rangliste desselben Fensters (Instrument, Rangscore bitgleich, Kursrendite, tatsächlicher Anfang, Zahl der Schlusskurse); die Zählung über die zehn Zeiträume stimmt mit einer unabhängigen Nachzählung überein und bleibt von der 90-Fenster-Zählung getrennt. *Identische Kursfenster:* `same_set` stimmt für V, U, V ∩ L und U ∩ L mit einer Nachrechnung aus den Fensterdateien (ISIN und tatsächliches Startdatum) überein; identische Bestände haben identische Ranglisten; „nur einmal zählen“ ergibt nie mehr Nennungen und als Nenner genau die Zahl verschiedener Fenster. *Methode 1.7.0:* Methodenvergleich im Manifest passt zu den Fenstern (V und U nach neuen Regeln = Summen der Fensterdateien, Wegfall mit Grund), positive Schlusskursvergleiche zwischen 0 und n − 1 und passend zum Vorzeichen der Rendite.
- Datenvertrag: Die App berechnet Perzentile und Scores aller elf Gewichtungen **bitgleich** zur Serverberechnung; Renditesieger (90 Zeilen) und Häufigkeiten stimmen mit der Serverreferenz überein; Untergruppenranking stimmt mit `traktien.analytics.ranking.rank_subgroup` überein; verschlüsselte Dateien: richtige Passphrase entschlüsselt, falsche Passphrase und vertauschte Dateien scheitern. **1.1:** Ranking 2 ist in jeder Fensterdatei genau Ranking 1 ohne die nicht aufgenommenen Aktien, mit gleichen Renditen, Start- und Endkursen; Start- und Endkurs ergeben die Rendite (Abweichung ≤ 10⁻¹²); die Häufigkeit mit Umsatzfilter zählt nur aufgenommene Aktien und nennt ihr Universum. **1.2:** Geprüft sind genau die ersten 10 Plätze beider Ranglisten; das Kennzeichen „Börsenplatz-Abweichung“ steht genau bei den auffälligen Vergleichen.
- **1.4 – Gruppe B im Datenvertrag:** Scores aller elf Gewichtungen der Gruppe B bitgleich zum Server (Fundstellen und Spitzenreiter, über 500 Vergleiche); Zählung der App (Platz 1, Top 3, Top 10, auswertbare Kombinationen) gleich der Serverreferenz für Gruppe A und B; Matrixzellen der Gruppe B nur Aktien aus L; „≡“ nur bei gleicher Aktie mit gleichem Start. Reine Funktionstests: identische Kursfenster, Leerzustände, Kennzeichnung (Anzahl über beide Gruppen, Farbplätze nach Anzahl, einmal ist keine Wiederholung), Häufigkeit nach Platz 1, dann Top 3, Top 10, ISIN; „nur einmal zählen“; A und B getrennt.
- **1.3 – Umschichtungs-Regel im Datenvertrag:** alle 24 Varianten lesbar, Standardvariante aus leerer Adresse, Orders je Entscheidungstag mit Ausführung am nächsten Handelstag, Aufteilung heute und nach den Änderungen jeweils 100 %, Käufe nur unter den ersten N, Verkäufe vor Käufen, beschlossene Umschichtung noch nicht im Rückblick; verschlüsselt an den eigenen Pfad gebunden. Reine Funktionstests: Variante aus der Adresse (unbekannte Werte → Standard), Eurobeträge, Begründungstexte, Aufteilung mit gleichmäßig gekürzten Käufen, Texte „beschlossen“/„nach heutigem Stand“.
- Reine Funktionstests 1.2: Texte zum zweiten Börsenplatz (Umrechnung, kein Ergebnis → keine Aussage, ältere Stände), Erkennen des Laufergebnisses beim Aktualisieren (neuer Stand, keine neuen Kurse, anderer Status, Zeitüberschreitung), „heute/morgen ab 23:00 Uhr“.
- Build: `1.5.0+087dc246`, 13 Dateien, zusammen 636 KiB. Ein erneuter Build ergibt byte-gleiche Dateien (geprüft mit SHA-256; Voraussetzung für die Prüfung „app/dist ist aktuell“ in GitHub Actions).

## 3. Browser-Tests (Emulation, kein echtes Gerät)

Chromium mit 384 × 832 CSS-Pixeln, Pixelverhältnis 2,8125, Touch, Sprache de-DE, Zeitzone Europe/Berlin – das entspricht der Bildschirmgröße des S25+, ersetzt aber **keinen Test auf dem Gerät** und ist als automatisierter DOM-Test auch **kein visueller Browsercheck**. Ein Test prüft zusätzlich 832 × 384 (Querformat) und 1280 × 800 (Desktop). 48 Tests, alle bestanden. Geprüft unter anderem:

- **1.16 – Verständlichkeit, Fehlerfälle, Installation (9 neue Tests):** Sperrbildschirm mit Zweck und drei Schritten, ohne Leiste unten, Menü gesperrt nur „Hilfe und Begriffe“ und „Installieren“; leere Eingabe → „Gib zuerst die Passphrase ein“ mit Fokus im Feld; falsche → „Diese Passphrase passt nicht“, Eingabe bleibt, „Passphrase vergessen?“; Hilfe gesperrt erreichbar; Passphrase mit Leerzeichen am Ende entsperrt. Kurzerklärung steht über den Top 3 und bleibt nach „Verstanden“ auch nach Neuladen weg; Hilfe über das Menü, Rechenbeispiel 80/40/30, Sprung zu „Häufige Fragen“, Begriffe filtern („R²“ → Gleichmäßigkeit, „xyzzy“ → kein Treffer mit Hinweis), Link `#/hilfe?begriff=rangscore` hebt den Begriff hervor und zeigt ihn auch bei aktivem Suchwort; ⓘ an „Rangscore“ über der Rangliste erklärt mit Beispiel und Link. Fehlende Datei (mit Selbstheilung und „Erneut versuchen“), beschädigte Datei, Serverfehler 500 → „Datei nicht gefunden“, „Daten nicht lesbar“, „Server antwortet nicht“ (nie „Keine Internetverbindung“); fehlende Fensterdatei in einer Ansicht → verständlicher Text, Pfad nur als technische Angabe. Unbekannte Seite, ungültige, leere und unbekannte ISIN mit „Zur Startseite“ bzw. „Aktie suchen“ (ISIN vorausgefüllt). Suche oben, „1 Treffer“ schon beim Tippen, „Keine Aktie passt zu „xyz123““. Startkapital: „abc“, leer, „0“ mit Hinweis, „2.500“ wird übernommen (Endwert 2.500,00), „-5“ beim Verlassen zurück auf 2500. Einstellungen: falsche Datei „keine Sicherung dieser App“ (ohne „JSON“) im Abschnitt selbst; „Schlüssel vergessen“ fragt, „Abbrechen“ lässt entsperrt, „Ja, vergessen“ sperrt. Freier Zeitraum 0 und 120 mit Hinweis „gewählt ist jetzt 1 Tag“ bzw. „sind jetzt 90 Tage“. **Installation:** dauerhaftes Chromium-Profil, Chrome meldet keine Hindernisse (`Page.getInstallabilityErrors` leer), Manifest ohne Fehler („TR-Vergleich“, eigenständiges Fenster, Symbole 192 und 512), `PWA.install` installiert, `PWA.launch` startet die App, sie zeigt die Startseite, Fenstertitel „TR-Aktienvergleich“.
- **1.5.1/1.5.2 – Börsenplatz-Abgleich `boersenplatz-v2`/`v3`:** „Datenstand & Betrieb“ (Zeilen „Vergleichskurs“, „Auffällig“ mit der Schwelle der Aktie, „Nach fester 10-%-Regel“ mit der Auswertung, „Verglichene Zeiträume“, Börsen mit Namen) und „So wird gerechnet“ nennen die Regel aus der Version im Datenstand; ältere Stände (v1, v2) behalten ihren Text (App-Test). Einzelansicht: „Schwelle 40 % (übliche Tagesschwankung dieser Aktie 8,0 %)“ (App-Test).
- **1.5.1 – Teilstand:** „Teilstand“ im Kopf jeder Ansicht; die Startseite nennt die Börsen ohne Stichtagskurse mit Namen (London, Xetra) und den Grund (fehlende Daten, nicht Kursentwicklung); „Datenstand & Betrieb“ zählt Börsen und Aktien mit Stichtagskurs. Fehlen wie am 12.10. 28 von 31 Börsen, nennt die Startseite die 3 enthaltenen (Australien, Neuseeland und USA), ohne Seitwärtsverschiebung auf 384 px; die vollständige Liste steht unter „Datenstand & Betrieb“. „So wird gerechnet“ zeigt den Methodenwechsel 1.7.0 → 1.8.0 mit den Regeln zu fehlenden Börsentagen.

- **1.5 – Prüfung 19 (feste Schnellwahl):** genau zehn Tasten 7 … 90 Tage; jede wählt exakt ihr Kalenderfenster (Adresse, aktive Taste, Anzeige, Ziel-Startdatum = Stichtag − h Kalendertage aus der Fensterdatei); Platz 1 und seine Kursrendite stimmen je Fenster mit der Fensterdatei des Stands überein, Gewichtung und Gruppe bleiben beim Wechsel erhalten (auch Gruppe B mit 0/100); bei 7 und 14 Tagen mit 60/40 der Leerzustand mit Grund; freie Eingabe 37 Tage ohne aktive Taste; im Einzelchart zeigt die Grafik für jede der zehn Tasten genau Anfangstag, Endtag, Zahl der Schlusskurse und Veränderung des Fensters dieser Aktie; Kursraster mit derselben Schnellwahl.
- **1.5 – „Sieger nach Zeitraum“ (Prüfung 20 in der Oberfläche):** zehn Zeilen ohne seitliches Scrollen; für 60/40, 0/100, 50/50, 100/0 und 10/90 ist jede Zelle (A und B) Platz 1 der Fensterdatei mit derselben Kursrendite; „Gleichmäßigkeit nicht berechenbar“ bei 7 und 14 Tagen ohne Ersatzaktie; Antippen zeigt Beginn, Ende, Schlusskurse und Referenzmarkt, „Ganze Rangliste“ öffnet dieselbe Aktie auf Platz 1; eigene Zählung über die zehn Zeiträume = Nachzählung.
- **1.5 – Häufigste Aktien:** Spalten Rang, Unternehmen/ISIN, Platz 1, Top 3, Top 10, Zugelassen; Platz 1, Top 3 und Top 10 jeder Zeile und der Nenner „berechenbare Kombinationen“ stimmen mit einer Nachzählung aus den Serverdaten überein – für alle Gewichtungen 1–90 Tage, für „nur mit Gleichmäßigkeitsanteil“ 31–60 Tage und für 50/50 mit A und B in der freien Spanne 21–45 Tage; Sortierung „Gewinnt am häufigsten“ und „Meiste Top-10-Nennungen“; „nur einmal zählen“ senkt nie eine Zahl über den vorherigen Wert hinaus; CSV und JSON enthalten Gruppen, Gewichtungen, Zeiträume, Zählweise und Snapshot; die Tabelle passt (auch mit A- und B-Beiträgen) ohne seitliches Blättern auf 384 px. Zusätzlich mit einem eigenen Skript bei 360 und 412 px Breite gemessen: kein seitliches Blättern in Häufigkeit und Zehn-Fenster-Zählung.
- **1.5 – Matrix 1–90:** Sprung zu 70 Tagen; JSON-Export mit 990 Zellen (Stichprobe = Spitzenreiter der Übersicht, leere Zellen mit Grund), CSV mit 990 Datenzeilen.
- **1.5 – Start, Watchlist, Datenstand:** Erststandard 90 Tage und 60/40, Auswahl 30 Tage / 50/50 / Gruppe B bleibt nach Neuladen erhalten und bestimmt die ersten fünf (= Fensterdatei); vier direkte Einstiege; ISIN-Import mit Zusammenführung doppelter und Meldung ungültiger ISINs, Export als Liste und CSV; Methodenwechsel 1.6.0 → 1.7.0 mit Ausgangsmodell, Metadaten-Export ohne Schlüssel oder Passphrase, frühere Stände mit Methodenversion.

- **1.4 – Matrix A/B** (ab 1.5 mit 90 Zeilen): sechster Reiter „Matrix“; Zeilen × 11 Gewichtungen, „nicht berechenbar“ bei kurzen Zeiträumen, „≡“ bei gleichem Kursfenster; Zeitraumspalte bleibt beim seitlichen Wischen stehen, nur die Matrix verschiebt sich; Antippen markiert alle Vorkommen derselben ISIN (Anzahl markierter Zellen = Zellen mit dieser ISIN), Kennzeichnung in Gruppe B gleich; „Rangliste …“ öffnet die Rangliste der Gruppe B mit der Aktie auf Platz 1; kompakte Liste mit 30 Zeilen; Häufigkeit absteigend nach Platz 1, A und B getrennt, „Identische Kursfenster nur einmal zählen“ fasst zusammen.

- **1.3 – Umschichtungs-Regel:** Startseite → „Regel ansehen“; gelbes Depot-Lineal, „Keine Änderung“ bei der Standardvariante, 5 Positionen, nächste Entscheidung, Rückblick-Diagramm mit drei Linien, keine Seitwärtsverschiebung; Wechsel auf 10 Aktien; wöchentliche Variante mit beschlossener Umschichtung („Was die Regel jetzt umsetzt“, zwei Lineale, Verkaufen zuerst); eigener Depotwert (ungültige Eingabe abgewiesen, 25.000 € übernommen, gleiche Anteile, nach Neuladen erhalten, zurücksetzbar); Variantentabelle wählt per Antippen; Orders je Entscheidungstag aufklappbar; Abschnitt „Was die Rechnung nicht zeigt“.

- **1.2 – Aktualisieren auf Wunsch:** ☰ → „Jetzt aktualisieren“ (auch ohne Datenstand erreichbar); Knopf „Lauf auf GitHub starten“ öffnet die Seite des Workflows in einem neuen Fenster; die App wartet, zeigt in allen Ansichten „Aktualisierung angefordert“, das Warten übersteht einen Neustart; meldet sich der Lauf („keine neuen Daten“), erscheint das Ergebnis mit Grund, bis es ausgeblendet wird; der nächste mögliche Kursstand („Dienstag, 13. Oktober 2026 … ab 23:00 Uhr“) steht vor dem Start da.
- **1.2 – zweiter Börsenplatz:** gelbes Kennzeichen „Börsenplatz-Abweichung“ beim Sieger mit abweichendem Frankfurter Kurs, Zeile „Vergleich mit Börse Frankfurt (S194.F): auffällige Abweichung – dort …, Endkurs …“; unauffällige Plätze mit Rendite dort; Einzelansicht mit Börse, Symbol, Umrechnung, Rendite dort und Abweichungen (auffällig nur in den längeren Zeiträumen, wo die Testkurse abweichen); Abschnitt in „Datenstand & Betrieb“.
- **1.1 – zwei Rendite-Ranglisten:** zwei getrennte Reiter „Alle Aktien“ und „Ø Umsatz ≥ 10 Mio. USD“; je Zeitraum zuerst der Sieger, Antippen öffnet die Top 10, von dort die vollständige Liste mit Seiten; Standardansicht 1–7 Tage. Je Aktie Rang, Name, Ticker, ISIN, Kursrendite, Start- und Endkurs mit Datum, Börse und Währung, Ø Tagesumsatz mit Berechnungsbasis und Hinweise. Aktien mit sehr niedrigem Umsatz sind in Ranking 1 gekennzeichnet und fehlen in Ranking 2. Zählungen stehen getrennt da. Startdatum nach Wochenende = letzter Schlusskurs davor; Einzelansicht zeigt Ø Tagesumsatz und beide Rendite-Plätze; Häufigkeitsliste nennt Universum und Umsatzfilter; Passphrase lässt sich vor dem ersten Datenstand eingeben.
- Start mit echtem Kursstand-Datum und DEMO-Kennzeichen in jeder Ansicht (11 Ansichten), Rendite-Leiter mit 90 Balken.
- Ranking: Zeitraum (Lineal, Tastatur, Plus/Minus, Schnellwahl), alle elf Gewichtungen per Schieberegler, Leerzustand mit Grund (1 Tag + Gleichmäßigkeit), Top 50.
- Jede genannte ISIN öffnet den Chart genau dieser Aktie (Ranking, Rendite-Liste, Häufigkeitsliste, Raster, Gesamtverzeichnis); Aktie ohne Kurse zeigt einen Leerzustand statt eines erfundenen Verlaufs.
- Einzelchart: Tooltip, Pos1/Ende ohne Seitensprung, Zoom per Knopf und per Zwei-Finger-Geste, Antippen, Zurück mit wiederhergestellter Scrollposition; 1-Tages-Fenster ohne erfundenen Tagesverlauf.
- Tooltip, Kurstabelle, Kennzahl und PNG-Export beruhen auf denselben Kursen; der PNG-Export enthält Kursstand, Snapshot, DEMO-Hinweis und „keine Liveansicht“.
- Chart-Raster: gleicher Zeitraum, mehrere Zeiträume (jede Zelle = angefragter Zeitraum, alle Dateien aus einem Snapshot), gemeinsamer Indexvergleich (Start = 100); Originalkurse mit Währung je Kachel; Skalenwahl bleibt nach Neuladen erhalten; große Auswahl seitenweise, nur sichtbare Kacheln laden Kurse (höchstens 12 je Seite).
- Ranking, CSV-Export und Raster verwenden dieselbe Auswahl, dasselbe Vergleichsfeld und denselben Snapshot; CSV ist gegen Formel-Injection geschützt.
- Häufigkeitsliste stimmt mit der Serverberechnung überein; Treffermatrix 90 × 11 öffnet Details.
- Offline nach erstem Besuch mit Hinweis „Offline – gespeicherter Stand“; neue App-Version behält Watchlist und Einstellungen.
- Verschlüsselte Website: falscher Schlüssel abgewiesen, richtiger Schlüssel öffnet; nach Neuladen weiter entsperrt.
- Alle Bedienelemente mindestens 44 × 44 Pixel und beschriftet; Querformat/Desktop mit Seitenleiste; Dunkelmodus.

Bildschirmfotos dieser Emulation: `docs/bilder/`.

## 4. Lauf ohne Handy, Wiederanlauf und Veröffentlichung (nachgebildetes GitHub)

`tests/integration/test_ci_flow.py` führt `python -m traktien ci` mehrfach auf jeweils frischen Arbeitsverzeichnissen gegen eine nachgebildete GitHub-REST-API aus (Release anlegen, Assets hoch-/herunterladen, löschen, umbenennen):

1. Erster Lauf: veröffentlicht, Ausgaben `deploy=true`, `status=veroeffentlicht`; Release „datenstand“ als Vorabversion mit `crypto.json`, `state.sqlite.tra`, `site-<id>.tar`, `evidence-<id>.tra`; kein Geheimnis in Assets; `verify-site` bestanden.
2. Zweiter Lauf auf neuem Runner: Zustand aus der Sicherung, Status `keine_neuen_daten`, der erste Stand bleibt veröffentlicht.
3. Mit verwaister Sperre in der Sicherung: Sperre wird freigegeben, alter Lauf als „abgebrochen“ markiert, Lauf erfolgreich.
4. Ohne `DATA_PASSPHRASE`: Abbruch, bevor irgendetwas hochgeladen oder gebaut wird.
5. Sicherung austauschen: Verbindungsabbruch beim Hochladen lässt die alte Sicherung unverändert; Abbruch beim Umbenennen hinterlässt die neueste vollständige Fassung, die der nächste Lauf übernimmt und repariert.
6. Nur Website (`--nur-website`): neue App-Hülle mit den vorhandenen Datenständen, Sicherung unverändert; zusammen mit „Zustand neu aufbauen“ entsteht in Sekunden ein neuer Schlüssel ohne Daten.

## 5. Sicherung und Wiederherstellung

```bash
PYTHONPATH=backend python -m traktien demo --fresh
PYTHONPATH=backend python -m traktien restore-test --state-dir build/demo-state
```

Ergebnis (DEMO-Zustand, 13.10.2026): `wiederherstellung_ok: true` – instrument 198/198, listing 195/195, daily_bar 26.575/26.575, run 1/1, snapshot_manifest 1/1, universe_member 198/198. Verschlüsselte Wiederherstellung in einem sauberen Verzeichnis und Abweisung eines falschen Schlüssels: `test_T55_backup_restores_in_clean_environment`. Details: 08_Backup_und_Wiederherstellung.

`python -m traktien verify-site --site build/demo-site`: 378 Datendateien, 0 Fehler.

## 6. Leistungsmessung (synthetisch)

```bash
PYTHONPATH=backend python tests/perf/perf_universe.py 11500 --encrypt
```

Gemessen am 13.10.2026 mit Version 1.1.0 (sechs Börsen in USD, EUR, GBp, HKD, AUD und JPY, synthetische Wechselkurse). Der Börsenplatz-Abgleich aus 1.2 ist nicht enthalten: Er besteht aus Abrufen beim Kursanbieter (höchstens 600 Aktien, Zeitbudget 15 Minuten) und rechnet nur wenig.

| Messgröße | Wert |
|---|---|
| Instrumente × Zeiträume | 11.500 × 90 = 1.035.000 |
| Rechenkern (alle Fenster, elf Gewichtungen, Ø Tagesumsatz, beide Rendite-Ranglisten, Häufigkeiten) | 56,0 s (1.0.0: 42,6 s) |
| Veröffentlichung (verschlüsselt) | 70,1 s, 11.684 Dateien |
| Größe eines Datenstands | 96,7 MB (Fenster 63,3, Kursreihen 32,3, Übrige 1,1); 1.0.0: 74,0 MB – mehr vor allem durch Start- und Endkurs je Aktie und Zeitraum |
| Höchster Arbeitsspeicher | 423 MB |
| Vergleichsfelder bei 30 Tagen | V = 10.804, U = 5.240, V ∩ L = 2.170 |
| Ø Tagesumsatz bestimmt / mindestens 10 Mio. USD | 11.500 / 2.315 |
| Gesamtdauer des Skripts | 129 s |

**Wiederholt am 13.10.2026, 21:30 Uhr, mit Version 1.5.1** (gleiches Skript, 11.500 Instrumente, verschlüsselt): Rechenkern 62,0 s, Veröffentlichung 76,3 s, 11.684 Dateien, zusammen 103,7 MB (Fenster 71,1, Kursreihen 31,3, Übrige 1,3), höchster Arbeitsspeicher 490 MB. Was das Handy beim Öffnen lädt, bleibt klein: `manifest.bin` 0,50 MB, `instruments.bin` 0,48 MB, `frequency.bin` 0,25 MB, `overview.bin` 0,03 MB, Kopf einer Rangliste höchstens 19 KB. Vollständige Ranglisten eines Zeitraums (im Mittel 0,77 MB, höchstens 0,86 MB) lädt die App nur für den gewählten Zeitraum und nur bei Bedarf, Kursreihen je Aktie (höchstens 4 KB) erst in der Einzelansicht. Zum Vergleich der echte Lauf: Kursabruf, Zuordnung und Abgleich brauchten am 13.10. zusammen 86 Minuten.

Nicht enthalten ist der Kursabruf über das Netz (eine Anfrage je Notierung, gedrosselt auf 2,5 je Sekunde, rechnerisch gut eine Stunde für 10.000 Notierungen) – er war hier nicht messbar.

Hochrechnung (nicht gemessen): Die DEMO-Datenbank belegt rund 110 Byte je Tageskurs einschließlich Indizes. Bei 11.500 Notierungen und 250 Tagen Aufbewahrung (≈ 175 Börsentage) wären das etwa 220 MB, komprimiert und verschlüsselt etwa 80 MB je Sicherung.

## 7. In GitHub Actions ausgeführt (13.10.2026)

Ergebnisse stehen als Hinweise in der Übersicht des jeweiligen Laufs (Actions → Lauf öffnen).

### Workflow „Prüfung“

21 Läufe am 13.10.2026 (bis 18:41 Uhr). Die ersten beiden scheiterten, weil `reportlab` (für den PDF-Rundlauftest) in `requirements-dev.txt` fehlte; seit der Korrektur um 10:58 Uhr sind alle Läufe grün. Version 1.1.0 (13:28 Uhr, Commit 1cdc1e6): **218 Tests bestanden (6 Live-Tests übersprungen)**, `npm ci` ohne Rückfall, Typprüfung und App-Tests bestanden, `app/dist` identisch mit dem Build auf GitHub; echte Börsenkalender `exchange_calendars`: **4 von 4 bestanden**. Folgeänderung (13:34 Uhr, Commit 852d017): **220 Tests bestanden**. Danach grün: 1.2.0 (14:19 Uhr), Folgeänderung (14:44 Uhr), 1.3.0 (16:33 Uhr), 1.4.0 (16:56 Uhr), 1.4.1 (17:19 Uhr) und 1.5.0 (18:41 Uhr, Commit 203d136): **298 Tests bestanden, 6 Live-Tests übersprungen**, echte Börsenkalender 4 von 4.

### Workflow „Datenquellen prüfen“ (12:02 Uhr)

| Prüfung | Ergebnis |
|---|---|
| TR-Instrumentenliste | bestanden: 11.560 ISINs im Aktienabschnitt, 0 ungültige, 0 doppelte, 1 Fortsetzungszeile; PDF 757.736 Byte, Stand 12.10.2026 08:06 Uhr; Apple, SAP, Deutsche Telekom gefunden |
| OpenFIGI | bestanden: Apple und SAP je 8 unterstützte Notierungen (u. a. Xetra und Frankfurt – die Grundlage des Börsenplatz-Abgleichs) |
| Yahoo Tageskurse und ISIN-Suche | bestanden: AAPL 31 Tageskurse bis 12.10.2026; ISIN-Suche findet AAPL |
| Yahoo Stichtagskurs je Börse | **fehlgeschlagen:** Schlusskurs vom 12.10.2026 fehlt bei allen 14 geprüften Börsen in Europa und Asien (Kerze vorhanden, Schlusskurs leer; beide Yahoo-Server, drei Abfragearten; Stundenkerzen vorhanden). Details: 04_Datenquellen_und_Abdeckung |
| EODHD | übersprungen (kein Schlüssel, kostenpflichtig, nicht freigegeben) |
| EZB-Referenzkurse | neu in 1.1 – in diesem Workflow noch nicht gelaufen; im Tageslauf vom 13.10. abends geladen (29 Währungen, Historie ab 16.05.2023) |

### Workflow „Täglicher Lauf“

| Start | Art | Ergebnis |
|---|---|---|
| 10:58 Uhr | erster echter Lauf (manuell) | TR-Liste übernommen, Zuordnung begonnen, Kurse abgerufen; `wartet_auf_provider` (Stichtagskurse 12.10. fehlen in Europa und Asien) → kein Datenstand |
| 12:05 Uhr | Lauf mit erneutem Abruf fehlender Stichtagskurse | nach 25 Minuten von Hand abgebrochen, um die App mit Passphrase-Eingabe bereitzustellen |
| 12:39 Uhr | `nur_website` + `zustand_neu_aufbauen` (neue Passphrase) | grün in 41 s: App 1.0.0 mit neuem Schlüssel online, Zustand leer |
| 12:40 Uhr | voller Lauf mit neuem Schlüssel (44 Minuten) | `wartet_auf_provider`. Kurzbericht: Identität 3.841 verifiziert, 133 unklar (davon 83 Wiener Aktien wegen Zeitzonenangabe – in 1.1 behoben), 26 kein Aktieninstrument, 7.560 offen; Kursabruf 3.916 Notierungen: 1.193 mit Stichtagskurs, 1.478 ohne Stichtagskurs (Europa/Asien am 12.10.), **1.162 ohne Kursdaten** (Ursache noch offen; der Kurzbericht nennt ab 1.1 die betroffenen Börsen mit Beispielen) |
| 13:35 Uhr | `nur_website` | grün: App 1.1.0 online |
| 13:35 Uhr | voller Lauf (Version 1.1 mit EZB-Kursen und neuem Kurzbericht, 55 Minuten) | `wartet_auf_provider`: Stichtagskurse 12.10. nur in Australien, Neuseeland und den USA vollständig (Xetra 17 von 439, London 4 von 689, Paris 1 von 515, übrige europäische und asiatische Börsen 0) |
| 14:24 Uhr | `nur_website` | grün: App 1.2.0 online |
| 14:44 Uhr | voller Lauf (70 Minuten) | `wartet_auf_provider`, gleiches Bild: USA 3.599 von 3.604, Australien 525 von 525, Europa und Asien weiter ohne Kurs vom 12.10. Kurzbericht: Identität 11.218 verifiziert, 235 unklar, 107 kein Aktieninstrument; Kursabruf: 5.281 mit Stichtagskurs, 4.176 ohne, 1.735 ohne Kursdaten (Toronto 960, Xetra 395, Stockholm 148, Singapur 82 – Anlass für 1.4.1) |
| 18:48 Uhr | `nur_website` | grün: App 1.5.0 online, weiterhin ohne Datenstand |
| 19:02 Uhr | zwei Starts ohne „erzwingen“ | der erste von Hand abgebrochen (er hätte nur weiter auf die fehlenden Kurse gewartet), der zweite von GitHub verworfen, weil ein neuerer Lauf in der Warteschlange stand |
| 19:08 Uhr | voller Lauf mit „erzwingen“ (Software 1.5.0, Methode 1.7.0; 19:11–20:37 Uhr, 86 Minuten) | **`veroeffentlicht`: erster echter Datenstand** `2026-10-12_5092bae0`, gekennzeichnet als Teilstand; Bereitstellung 20:37 Uhr grün. Stichtagskurse 12.10.: USA 3.623 von 3.628, Australien 525 von 525, Neuseeland 18 von 18, Xetra 17 von 439, Frankfurt 4 von 219, London 5 von 713, Bangkok 3 von 39, Paris 1 von 519, übrige Börsen in Europa und Asien 0. Identität: 11.141 verifiziert, 311 unklar, 108 kein Aktieninstrument. Kursabruf: 6.222 mit Stichtagskurs, 4.434 ohne, 1.792 ohne Kursdaten (Toronto 960, Xetra 395, Stockholm 148, Singapur 82, London 63); andere Kürzel 57 geprüft, 0 gefunden. EZB: 29 Währungen bis 13.10. Umschichtungs-Regel: Wochenwerte für 5.142 Aktien vollständig, Rückblick 06.10.2023–09.10.2026. Börsenplatz-Abgleich: 89 von 98 Aktien geprüft, 64 auffällig – ohne Xetra-Kurse vom 12.10. verglich `boersenplatz-v1` den Freitagskurs mit dem Montagskurs der Referenz, sodass jede Aktie mit mehr als 10 % Bewegung am Montag auffiel (geändert in 1.5.1, `boersenplatz-v2`) |
| 21:07 Uhr | voller Lauf mit „erzwingen“ (Software 1.5.1, Methode 1.8.0, `boersenplatz-v2`; 21:07–21:50 Uhr, 42 Minuten) | **`veroeffentlicht`: erster vollständiger Stand** `2026-10-12_9820e6d9` – Yahoo hatte die Schlusskurse vom 12.10. nachgeliefert. Stichtagskurse 12.10. an allen 31 Börsen mit Sitzung zwischen 97 und 100 % (Xetra 433 von 439, Frankfurt 216 von 219, London 695 von 713, Hongkong 734 von 735, Mailand 196 von 197, USA 3.623 von 3.628, übrige 100 %). Kursabruf: 10.622 mit Stichtagskurs, 34 ohne, 1.792 ohne Kursdaten. Wochenwerte 5.143 Aktien. Börsenplatz-Abgleich (v2): 102 von 110 Aktien geprüft, 75 auffällig; Zeiträume 3.080 auffällig, 5.084 unauffällig, 328 ohne Vergleichskurse – Anlass für `boersenplatz-v3` (1.5.2). Bereitstellung 21:50 Uhr grün |
| 21:17, 21:37, 21:53 Uhr | `nur_website` (eingereiht hinter dem Lauf) | 21:17 von GitHub verworfen (neuere Bereitstellung eingereiht); 21:37 grün: App 1.5.1+1089b596; 21:53 grün: App 1.5.1+cee5b7bd – „Datenstand unverändert (2 veröffentlichte Stände)“ |
| 22:13 Uhr | Lauf mit „erzwingen“ (Software 1.5.2, `boersenplatz-v3`; 22:13–22:18 Uhr, 6 Minuten) | **`veroeffentlicht`: vollständiger Stand** `2026-10-12_c3806c24` (gleiche Kurse; neue TR-Liste mit 11.531 ISINs, 29 weniger). Börsenplatz-Abgleich: 102 von 110 Aktien geprüft, **8 auffällig**; Zeiträume 51 auffällig, 1.305 unauffällig, 328 ohne Vergleichskurse, die übrigen ohne Umsatz am Vergleichsplatz. Auswertung: nach fester 10-%-Regel 3.080 Zeiträume (75 Aktien) auffällig – davon 2.934 ohne Umsatz am Vergleichsplatz, 95 innerhalb der üblichen Schwankung, 51 weiter auffällig. Bereitstellung 22:18 Uhr grün; `version.json` 1.5.2+02388482 und `status.json` (neuester und neuester vollständiger Stand `2026-10-12_c3806c24`, drei Stände aufbewahrt) über WebFetch um 22:25 Uhr gelesen |

Die Website `https://szymeklh87-commits.github.io/tr-aktienvergleich/` ist erreichbar und zeigt seit 20:37 Uhr den Teilstand vom 12.10. (`version.json`: App 1.5.0+087dc246, über WebFetch um 21:05 Uhr gelesen). Die Inhalte der Datenstände sind verschlüsselt und von hier aus nicht lesbar; Zahlen oben stammen aus dem Kurzbericht des Laufs. Auf dem echten Galaxy S25+ wurde die Passphrase eingegeben und gespeichert (Bildschirmfoto „Zugangsschlüssel gespeichert“).

## 8. Nicht geprüft (offen)

| Punkt | Grund | Was es abschließt |
|---|---|---|
| Inhalte des echten Datenstands (Ranglisten, Ranking 2, Methodenvergleich, Börsenplatz-Abgleich) im Einzelnen | verschlüsselt; die Live-Prüfung (22:52 Uhr) belegt, dass alle Ansichten mit den echten Daten laden und ohne Fehler angezeigt werden, prüft aber keine fachlichen Werte | Durchsicht auf dem S25+: ☰ → Datenstand & Betrieb (aufgenommene Aktien, Wechselkursstand, geprüfte/auffällige Aktien, Methodenwechsel) |
| Prüffall vom 12.10.2026 mit dem Originalarchiv `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` (Auftrag, Prüfung 13) | **Archiv nicht wiederherstellbar** – am 24.10.2026, 21:25–21:40 Uhr, selbst gesucht in Branches, Tags, Release, Actions-Artefakten und -Läufen, im ganzen Git-Verlauf, in Issues, Pull Requests, Wiki, Uploads und früheren Unterhaltungen, ohne Treffer (Fundstellen einzeln in Abschnitt 8c). Gefunden und geprüft: die drei **eigenen Originalstände der App** vom 12.10. mit dem Prüfnachweis ihres Laufs – reproduziert und gleich dem damaligen Lauf, fachlich korrekt nein (bekannte Fehler). Für den **13.10.** ist die Nachrechnung mit den Rechendaten aus deiner HTML-Übersicht gelaufen. Beides ersetzt das Archiv nicht | **Historischer Nachweis gegen das Ausgangsmodell: nicht möglich** (nur mit dem Archiv nachholbar; am 24.10.2026, 19:29 Uhr, hast du entschieden, keine ZIP-Dateien bereitzustellen). Geprüft wird stattdessen die aktuelle Berechnung (Abschnitte 8d und 8e; 09_Bekannte_Luecken, Abschnitt D) |
| Die 8 nach `boersenplatz-v3` auffälligen Aktien (51 Zeiträume) | Datenstand verschlüsselt, von hier aus nicht einzeln einsehbar | Einzelansicht auf dem Gerät: Kurse beider Plätze, Schwelle und Tagesschwankung; Ursache je Aktie benannt |
| Wirkung von Methode 1.8.0 auf echte Daten | **Ab 1.17.1 gemessen** für den Stand vom 23.10. (Überblick oben, [12_Fehlende_Kurstage](12_Fehlende_Kurstage.md)): Fehlende Kurstage betreffen 2.864 von 856.002 Paaren, keinen Platz 1; nach einer strengen Regel (jede Lücke schließt aus; ähnlich der 98-%-Regel bis 1.7.0, die erst ab 50 Sitzungen eine Lücke erlaubte) hätten 7 Ranglisten einen anderen Platz 1, ohne den letzten Schlusskurs (bis 1.8.0) 9 – jeweils nur durch einen Gleichstand an der Spitze | – |
| „Jetzt aktualisieren“ auf dem echten Gerät | Start über GitHub braucht die eigene Anmeldung | auf dem S25+: ☰ → Jetzt aktualisieren → Run workflow → App meldet das Ergebnis |
| EODHD (`test_eodhd_history`) | kein Schlüssel; kostenpflichtig, nicht freigegeben – im Lauf „Datenquellen prüfen“ übersprungen, zählt nicht als bestanden | nur nach deiner Freigabe |
| Nachtlauf über GitHubs Zeitplan (ab 1.17) | **Zeitplan geprüft (24.10.2026):** `37 22 * * 1-5` ohne Zeitzone, also UTC; Montag, 26.10.2026, 22:37 UTC = **23:37 Uhr MEZ** (die Sommerzeit endet am 25.10.; Test `test_night_run_on_26_october_2026_is_23_37_berlin_time`); Workflow „Nachtlauf“ aktiv. **Noch kein Lauf über den Zeitplan:** Der einzige Nachtlauf war ein Start von Hand (24.10., 12:26 Uhr, [Lauf 40085893661](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40085893661)). Der Nachweis ist erst nach dem 26.10. möglich; ein Lauf von Hand ersetzt ihn nicht. Die Kontrolle zählt ab 1.18 einen von Hand (oder über den externen Auslöser) gestarteten Nachtlauf nicht mehr als zeitgesteuert – bis dahin hätte sie ihn mitgezählt (an [Lauf 40085906898](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40085906898) mit echten Daten geprüft: „nachtlauf ohne zeitplan“, nicht bestanden) | **Eingerichtet:** geplante Aufgabe „Ersten zeitgesteuerten Kurslauf kontrollieren“, einmalig am **Dienstag, 27.10.2026, 09:30 Uhr MEZ** (08:30 UTC), meldet sich in dieser Sitzung: Nachtlauf mit Auslöser „schedule“ samt Verspätung, „Kurslauf kontrollieren“ (zehn Kriterien, 02_Einrichtung; maßgeblich ist allein „Abnahme Kurslauf: BESTANDEN“), „App mit echten Daten prüfen“ mit Kurs-Gegenprüfung (Datenstand 26.10. in der App, Nachrechnung, Signal-Stand), danach Zwischenstand und `test_2d`. Gab es den Lauf noch nicht, stellt sie den Stand fest und setzt eine weitere Kontrolle. **Zuletzt geprüft am 24.10.2026, 22:12 Uhr (Auftrag 21:23 Uhr, Punkt 4):** genau eine solche Aufgabe, eingeschaltet, einmalig, nächste Ausführung 27.10.2026 08:30 UTC = **09:30 Uhr Europe/Berlin** (MEZ, UTC+1 – die Sommerzeit endet am 25.10.) – keine zweite angelegt. Ihr Auftrag wurde in derselben Aufgabe ergänzt (20:59 und 22:12 Uhr): Nachweis nur mit dem Nachtlauf vom 26.10. über GitHubs Zeitplan (Auslöser „schedule“) – ein Start von Hand ersetzt ihn nicht, auch nicht grün –, danach die vollständige Abnahme mit allen zehn Kriterien (Tempo mit allen Mindestanforderungen), Kurs-Gegenprüfung und Kursursachen mit den neuen Urteilen, Android-Emulator, Firefox und WebKit mit echten Daten und zuletzt `test_2d` mit einem Zwischenstand. **Erneut geprüft am 25.10.2026, 12:33 Uhr (Auftrag 09:20 Uhr):** weiterhin genau eine solche Aufgabe, eingeschaltet, einmalig, nächste Ausführung 27.10.2026 08:30 UTC = 09:30 Uhr MEZ – keine zweite angelegt; ihr Auftrag in derselben Aufgabe um die Kursursachen dieses Auftrags ergänzt (vier Prüfjobs mit Job „welt“, strenge Beleglage, Absicherung mit Befund, Gegenprobe mit der unabhängigen Rechnung, Vergleich mit Lauf 40188406664) |
| Gleichzeitiger Kursabruf im täglichen Lauf (ab 1.17) | Gemessen ist er im Messlauf über alle Notierungen (nur lesend, Überblick oben); im täglichen Lauf bisher nur im Prüflauf vom 24.10. für 51 Notierungen (8,1 je Sekunde). Mit allen Notierungen rechnet er erst ab dem nächsten neuen Börsentag (Samstag und Sonntag keine neuen Kurse) | Lauf mit dem Stand vom 26.10.: Zeile „Chart-Abruf: … Abrufe in … s (… je Sekunde; 4 gleichzeitig über 2 Hosts …)“ in der Laufübersicht – geprüft wird das mit derselben Kontrolle (Kriterien „Kurse aller Notierungen“, „Tempo ≥ 6 je Sekunde“, „kein Rückfall wegen Drosselung“, „Dauer ≤ 60 min“) |
| Externer Auslöser in einem echten Google-Konto (ab 1.17, optional) | Braucht dein Google-Konto und ein Token von dir; geprüft nur mit nachgebildeten Google-Diensten | 02_Einrichtung, „Externer Auslöser“, Schritt 5 |
| Geplanter Lauf um 07:00 Uhr (bis 1.4: 06:00) | **erledigt am 15.10.2026:** Läufe mit Auslöser „schedule“ am 15. und 16.10., alle grün, aber 4¼ bis 5½ Stunden nach der eingestellten Zeit (Überblick, erste Zeile) | – (Verspätung: 09_Bekannte_Luecken, „GitHub-Zeitpläne“) |
| Umschichtungs-Regel im echten Zwischenstand (`test_2d_rotation_in_official_stand`) | Braucht einen aktiven Zwischenstand; am Wochenende gibt es keinen (nach dem Stand vom 23.10. kein Börsentag), deshalb in der Live-Prüfung übersprungen – zählt nicht als bestanden. Dieselbe Bedienung ist mit synthetischen Daten im Browser-Test `tests/e2e/test_intraday_app.py` geprüft (bestanden) | an einem Börsentag einen Zwischenstand rechnen, dann „App mit echten Daten prüfen“ – Schritt 4 der Kontrolle am 27.10. |
| Bedienung auf dem echten Galaxy S25+ | Auf dem Gerät belegt ist nur die Eingabe der Passphrase (Bildschirmfoto 13.10.); Installation und Verhalten sind dort **ungeprüft** (Abschnitt 8b) | Prüfanleitung in Abschnitt 8b |
| Installation auf Android (Chrome, Samsung Internet), TalkBack | **Im Android-Emulator geprüft** (Abschnitt 8b): Installation über Chromes Menü wie mit dem Finger, Start im eigenen Fenster, Neustart ohne Netz, TalkBack-Baum; ab 1.18 auch mit **echten Daten** in Chrome für Android (alle 24 Ansichten, Neustart im Flugmodus – mit 1.18.1 bestanden), ab 1.18.1 zusätzlich Firefox und WebKit. **Ungeprüft:** echtes S25+, Samsung Internet (im Abbild nicht vorhanden), WebAPK (im Emulator ohne Google-Konto nur eine Web-App-Verknüpfung), Bedienung mit TalkBack-Gesten | Prüfanleitung in Abschnitt 8b |
| Kurse und Ursachen über die geprüfte Auswahl hinaus (Stand 23.10.) | Geprüft sind 505 der 11.596 Aktien an 4,6 % der Kurstage (Abschnitt 8e, Punkt 6): 11.036 Aktien nicht ausgewählt (US-Aktien ohne Platz unter den ersten 20 und nicht in der Zufallsstichprobe, Aktien außerhalb der USA ohne Platz unter den ersten 10), 55 ausgewählte ohne abgesicherten Vergleich (30 bei CNBC nicht gefunden, 21 nicht ausreichend abgesichert, 4 ohne Kurse); an 1.032 abweichenden Aktientagen ist die Ursache nicht belegt (Prüfgrenze NYSE-Gruppe/Cboe, einzelne Abschlüsse nicht frei verfügbar) | weitere Quellen mit ISIN und Kurs (z. B. Kursarchive der Börsen – nicht angebunden) bzw. eine lizenzierte Quelle für offizielle Schlusskurse, nur nach deiner Freigabe |

### 8a. Die 23 übersprungenen Tests des Laufs „Prüfung“ (Stand 24.10.2026)

Im Lauf „Prüfung“ werden 23 Tests übersprungen – zuletzt im [Lauf 40108944849](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108944849)
(Commit `e6a96b2`, 17:52–18:03 Uhr): 561 Tests, **538 bestanden, 23 übersprungen, 0 fehlgeschlagen**; die Laufübersicht
nennt seitdem jeden übersprungenen Test mit Namen. Dort zählen sie **nicht** als bestanden. 22 brauchen Secrets oder echte
Quellen und gehören in eigene Workflows; einer war eine Hilfsausgabe. Ausgeführt am 24.10.2026, 17:52–17:54 Uhr, Ergebnis
je Test aus der Laufübersicht ([Datenquellen prüfen, Lauf 40108950043](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108950043),
[App mit echten Daten prüfen, Lauf 40108951837](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40108951837)):

| # | Test | Zweck | Grund des Überspringens in „Prüfung“ | Status |
|---:|---|---|---|---|
| 1 | `LiveAppTest.test_1_open_and_unlock` | ausgelieferte App öffnen, mit der Passphrase entsperren, Startseite fertig (Zeiten) | nur mit `TR_LIVE_APP=1` und `DATA_PASSPHRASE` (Secret nur im Workflow „App mit echten Daten prüfen“) | **bestanden** (0,3 s + 0,3 s) |
| 2 | `LiveAppTest.test_2_every_view` | alle 24 Ansichten mit echten Daten ohne Fehler und ohne fehlgeschlagenen Abruf | wie 1 | **bestanden** (24 von 24) |
| 3 | `LiveAppTest.test_2b_report_1_30` | Bericht 1–30: vier Tabellen, Matrix 30 Zeilen, Häufigkeit | wie 1 | **bestanden** |
| 4 | `LiveAppTest.test_2c_model_depots` | Musterdepots: Häufigkeit, vier Depots, „10 Sieger“ | wie 1 | **bestanden** |
| 5 | `LiveAppTest.test_2d_rotation_in_official_stand` | im Zwischenstand: Knopf „Schlusskurse … anzeigen“ zur Umschichtungs-Regel und zurück | wie 1 | **übersprungen – offen:** kein Zwischenstand aktiv (Wochenende); geprüft erst an einem Börsentag mit Zwischenstand (Kontrolle 27.10., Schritt 4). Mit synthetischen Daten: Browser-Test `test_intraday_app` bestanden |
| 6 | `LiveAppTest.test_2e_top3_by_numbers` | Top 3 nach Zahlen: Punkte 0–100, absteigend, Teile je Zeile | wie 1 | **bestanden** |
| 7 | `LiveAppTest.test_3_detail_of_first_stock` | Einzelansicht der ersten Aktie (30 Tage): Kennzahlen, Kursgrafik, zweiter Börsenplatz | wie 1 | **bestanden** |
| 8 | `LiveAppTest.test_3b_signal_detail_of_first_candidate` | Potenzial-Liste und Signal-Einzelansicht (Urteile, Signale, Prognose-Grafik, Gesamtwertung) | wie 1 | **bestanden** |
| 9 | `LiveAppTest.test_4_reopen_without_passphrase_and_offline_ready` | erneut öffnen ohne Passphrase, Service Worker aktiv | wie 1 | **bestanden** (0,8 s) |
| 10 | `LiveAppTest.test_5_no_console_errors` | keine Fehler in der Browser-Konsole | wie 1 | **bestanden** |
| 11 | `LiveAppTest.test_6_install_and_first_start` | Installation in Chromium (dauerhaftes Profil), erster Start mit Sperrbildschirm | wie 1 | **bestanden** |
| 12 | `SourcesLiveTest.test_tr_universe_pdf` | TR-Instrumentenliste laden und lesen | nur mit `TR_LIVE=1` (echte Quellen, Schlüssel nur im Workflow „Datenquellen prüfen“) | **bestanden** (11.596 ISINs, 0 ungültig, 0 doppelt) |
| 13 | `SourcesLiveTest.test_openfigi_mapping` | ISIN → Notierungen über OpenFIGI | wie 12 | **bestanden** |
| 14 | `SourcesLiveTest.test_yahoo_history_and_search` | Tageskurse und ISIN-Suche bei Yahoo | wie 12 | **bestanden** |
| 15 | `SourcesLiveTest.test_yahoo_delivers_cutoff_session_per_market` | Kerze des Stichtags je Börse über drei Zugänge | wie 12 | **bestanden** (Stichtag 23.10.) |
| 16 | `SourcesLiveTest.test_yahoo_quote_matches_daily_close` | letzte Kursmeldung = Schlusskurs der Tageskerze | wie 12 | **bestanden** (20 Werte, höchstens 0,1 bp Abweichung) |
| 17 | `SourcesLiveTest.test_yahoo_current_quotes_in_batches` | aktuelle Kurse in Sammelabfragen (Zwischenstand) | wie 12 | **bestanden** (21 von 21) |
| 18 | `SourcesLiveTest.test_yahoo_analyst_targets` | Kursziele und Empfehlungen, Serie ohne Drosselung | wie 12 | **bestanden** (50 von 50, 0 × HTTP 429) |
| 19 | `SourcesLiveTest.test_more_analyst_sources` | weitere Quellen erreichbar (Nasdaq, onvista, Stocktwits, Yahoo-Module) | wie 12 | **bestanden** |
| 20 | `SourcesLiveTest.test_yahoo_fundamentals_and_news` | Kennzahlen und Nachrichten | wie 12 | **bestanden** |
| 21 | `SourcesLiveTest.test_ecb_reference_rates` | EZB-Referenzkurse | wie 12 | **bestanden** (65 Kurstage) |
| 22 | `SourcesLiveTest.test_eodhd_history` | Kurshistorie über EODHD | wie 12; zusätzlich nur mit `EODHD_API_KEY` | **übersprungen – offen:** kostenpflichtig, keine Freigabe, kein Schlüssel |
| 23 | `MissingDaysReference.test_print_tables` | Werte für die Tabellen in 12_Fehlende_Kurstage ausgeben | nur mit `TR_REFERENZ_TABELLE` – eine Ausgabe ohne Prüfaussage | lokal ausgeführt (ohne Prüfaussage, zählt nicht als bestanden); **ersetzt** durch zwei echte Prüfungen (`DocumentedTable`): die Tabelle in 12_Fehlende_Kurstage wird in jedem Lauf gegen die unabhängige Rechnung geprüft – dabei einen Rundungsfehler gefunden und behoben (R² von C 0,99692 → 0,99691) |

**Ergebnis:** 20 der 23 Tests mit echten Daten ausgeführt und bestanden, die Hilfsausgabe durch zwei echte Prüfungen
ersetzt, **2 weiterhin übersprungen und offen** (`test_2d` bis zu einem Börsentag mit Zwischenstand, `test_eodhd_history`
ohne Freigabe). Seit dem [Lauf 40110861055](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110861055) (Commit `19c6c74`) sind es 22 übersprungene Tests (568 Tests, 546 bestanden); zuletzt mit 1.18.1 im [Lauf 40122471990](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40122471990): 611 Tests, 589 bestanden, dieselben 22 übersprungen. Die 10 Live-Tests der App außer `test_2d` bestanden auch mit 1.18.1 in Chromium ([Lauf 40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068); in Firefox und WebKit 9, dort ist `test_6` übersprungen – Installation nur in Chromium); die Quellen-Tests liefen zuletzt am 24.10. im Lauf [40110875450](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40110875450) – an der Datenbeschaffung hat 1.18.1 nichts geändert.

**Gefunden dabei:** Die Liste „je Test“ des Laufs „Datenquellen prüfen“ nannte **14 statt 15** Tests:
`ExchangeCalendarsLiveTest.test_close_times_in_utc` fehlte. Ursache: Der lange Bericht, den das Testmodul der Quellen am Ende
ausgibt, endete wegen gepufferter Ausgabe ohne Zeilenumbruch; unittest schrieb den nächsten Testnamen direkt dahinter
(`}test_close_times_in_utc (…) ... ok`), und die Auswertung erkannte die Zeile nicht. Das Gesamtergebnis war richtig
(„Ran 15 tests – OK (skipped=1)“, der übersprungene Test ist EODHD), der fehlende Test also bestanden. **Behoben:** Die
Auswertung erkennt solche Testnamen auch mitten in der Zeile, vergleicht die Zahl der Einzelergebnisse mit „Ran N tests“ und
meldet eine Lücke als Warnung („ohne Einzelergebnis“, nie als bestanden); die Prüf-Workflows laufen ungepuffert
(`PYTHONUNBUFFERED`). Tests: `test_head_glued_to_a_long_report_is_found`, `test_real_unittest_run_with_buffered_output`
(echter unittest-Lauf mit gepufferter Ausgabe), `test_unassigned_tests_are_named_and_never_counted_as_passed`.

In der App (`npm test`) werden 16 von 104 Tests übersprungen: die Datenvertragstests (`app/tests/contract.test.ts`), die
einen echt erzeugten Datenstand brauchen. Sie laufen im Lauf „Prüfung“ über `tests/integration/test_app_contract.py` mit
DEMO-Ständen des Servers (bestanden); lokal am 24.10. um 18:21 Uhr: 88 bestanden, 16 übersprungen, 0 fehlgeschlagen.

Lokal (Entwicklungsumgebung) werden zusätzlich die 4 Kalendertests (`ExchangeCalendarsLiveTest`) übersprungen:
`exchange_calendars` lässt sich hier nicht installieren (der Paketindex ist über den Proxy gesperrt). In GitHub Actions laufen
sie in jedem Lauf „Prüfung“ (4 von 4 bestanden) und in „Datenquellen prüfen“ (4 von 4).

### 8b. Gerät: Desktop-Simulation, Android-Emulator und echtes S25+ getrennt

Drei Prüforte; ein Ergebnis gilt nur für den Ort, an dem es entstanden ist (Auftrag 21:23 Uhr, Punkt 5):

- **Desktop-Simulation:** Playwright auf einem Linux-Rechner (GitHub Actions bzw. Entwicklungsumgebung) mit Chromium 141,
  Firefox 142 und WebKit 26 im Format des S25+ (384 × 832 CSS-Pixel, Touch) – kein Android, kein Gerät.
- **Android-Emulator:** Android 15 mit Chrome 124 im Format des S25+ (Einzelheiten unten) – echtes Chrome für Android,
  aber kein Samsung-Gerät, ohne Google-Konto und ohne Samsung Internet.
- **Echtes Galaxy S25+:** nur, was du selbst auf dem Gerät gemacht hast.

| Prüfung | Desktop-Simulation | Android-Emulator | Echtes S25+ |
|---|---|---|---|
| Alle 24 Ansichten mit echten Daten | Chromium, Firefox, WebKit je 24 von 24 ohne Fehler und ohne Überbreite – mit der ausgelieferten 1.18.2 [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565), mit 1.18.1 [40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068) | Chrome 124: 24 von 24 – mit 1.18.2 [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565), mit 1.18.1 [40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068) | offen – nicht durchgeführt |
| Entsperren, erneut öffnen ohne Passphrase | bestanden (alle drei Browser) | bestanden (echte Daten) | Passphrase eingegeben und gespeichert (Bildschirmfoto 13.10.); sonst offen |
| Neustart ohne Netz | Browser-Test `test_offline_restart_after_a_single_first_visit` (Chromium) und Live-Prüfung „erneut geöffnet, offline bereit“ | **bestanden** mit echten Daten im Flugmodus (ohne Passphrase, „Offline – gespeicherter Stand“; mit 1.18.2 [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565)) und mit DEMO-Daten als installierte App | offen – nicht durchgeführt |
| Hoch- und Querformat | 76 Browser-Tests (Chromium, hoch und quer) | DEMO: hoch 384 × 728 und quer 832 × 280, je 10 Ansichten ohne Verschiebung | offen – nicht durchgeführt |
| **Systemschrift** (große Schrift) | ab 1.18.2 Browser-Test `test_system_text_scale_up_to_200_percent_fits_the_phone`: Grundschrift 130, 150, 175 und 200 % in 33 Ansichten ohne Überbreite (vor der Korrektur mindestens 6 Ansichten bei 200 % zu breit, eine schon bei 175 %) – nachgestellt, nicht die Android-Einstellung | Systemschrift 130 % (Android meldet 1.3, Chrome 124 neu gestartet): **wirkt nicht auf die Texte der App** (Textzeile 57,5 → 58,2 px) – **nicht erfüllt**. Gegenproben ([40128638092](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128638092), [40129482881](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40129482881)): Kontrollseiten wachsen 16 → 20,8 px – langer Absatz mit und ohne `text-size-adjust: 100%`, kurze Texte in Karten –, ein langer Absatz mitten in der App ebenso, eine kurze Zeile in der App nicht (23,2 → 23,2 px). Ab 1.18.2 übernimmt die App die Systemschrift über `<meta name="text-scale" content="scale">`, das Chrome erst ab Version 146 umsetzt – **in Chrome 124 nicht prüfbar** (so auch das Urteil mit der ausgelieferten 1.18.2, [40133048985](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133048985)) | **offen – nicht durchgeführt** |
| **App-Installation** | Chromium mit dauerhaftem Profil: installierbar, installiert, erster Start (`test_6`, mit 1.18.2 [40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565)); in Firefox und WebKit übersprungen | über Chromes Menü wie mit dem Finger: **Web-App-Verknüpfung** (kein WebAPK – im Emulator ohne Google-Konto), Start im eigenen Fenster, Neustart im Flugmodus | **offen – nicht durchgeführt** (mit Google-Konto entstünde ein WebAPK, ungeprüft) |
| **TalkBack** | – | eingeschaltet: alle bedienbaren Elemente in Chromes Barrierefreiheits-Baum mit Namen (DEMO; im Android-Abbild 2 Suchfelder ohne eigenen Text, unten); **Bedienung mit Gesten nicht geprüft** | **offen – nicht durchgeführt** |
| **Samsung Internet** | – (gibt es dort nicht) | – (nicht im Abbild) | **offen – nicht durchgeführt** |
| Bildschirmtastatur | – | öffnet sich über die Entwicklerschnittstelle nicht – ohne Ergebnis | offen – nicht durchgeführt |

**Im Emulator geprüft** ([Android-Emulator prüfen, Lauf 40107137920](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40107137920),
24.10.2026, 17:28–17:35 Uhr, Commit `3b6b607`; mit 1.18.1: [Lauf 40123184881](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123184881), 20:59–21:05 Uhr; zuletzt mit der ausgelieferten 1.18.2: [Lauf 40133048985](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133048985), 23:10–23:17 Uhr – gleiche Ergebnisse, Systemschrift siehe Tabelle oben): Android 15 (Abbild `google_apis`, x86_64), Chrome 124, 1080 × 2340 Pixel
bei 450 dpi (Format des S25+); Play-Dienste und Play Store im Abbild, aber kein Google-Konto; Samsung Internet nicht im Abbild.

| Prüfung | Ergebnis im Emulator |
|---|---|
| Installation der veröffentlichten Website wie mit dem Finger | Chrome-Menü „Add to Home screen“ → „Install“ → Dialoge bestätigt; Symbol „TR-Vergleich“ nach 13 s auf dem Startbildschirm (Seite 2); installierbar ohne Hindernisse, Manifest ohne Fehler |
| Art der Installation | **Web-App-Verknüpfung, kein eigenes App-Paket (WebAPK)** – dafür braucht Chrome ein Google-Konto |
| Start vom Startbildschirm | eigenes Fenster (`WebappActivity`), keine Adressleiste, Sperrbildschirm, Service Worker aktiv, 384 CSS-Pixel breit |
| Neustart ohne Netz | eigenes Fenster und Sperrbildschirm aus dem Speicher; gespeicherter Stand mit Hinweis |
| Darstellung (DEMO-Daten) | Hochformat 384 × 728 und Querformat 832 × 280: in je 10 Ansichten nichts seitlich verschoben; Tastatur im Suchfeld: Feld bleibt sichtbar. Die Systemschrift auf 130 % wirkte im Emulator nicht auf die Texte der App, wohl aber auf Kontrollseiten (Tabelle oben); große Schrift ist in der Desktop-Simulation geprüft (ab 1.18.2: 130–200 %, 33 Ansichten) |
| TalkBack eingeschaltet (DEMO-Daten) | Start, Rangliste, Alle Aktien, Hilfe: alle bedienbaren Elemente in Chromes Barrierefreiheits-Baum mit Namen; im Android-Abbild zwei Suchfelder ohne eigenen Text (der Hinweistext wird dort nicht ausgegeben) |
| **Echte Daten** in Chrome für Android (ab 1.18; Job „android“ in „App mit echten Daten prüfen“) | veröffentlichte Website mit der Passphrase entsperrt, 24 von 24 Ansichten ohne Fehler und ohne Überbreite. **Neustart im Flugmodus:** mit 1.18.0 „Keine Internetverbindung“ statt des gespeicherten Stands ([Lauf 40118442565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40118442565) – Fehler der App, behoben in 1.18.1); mit 1.18.1 bestanden – ohne erneute Passphrase, Hinweis „Offline – gespeicherter Stand“, Rangliste aus dem Speicher ([Lauf 40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068)); mit 1.18.2 ebenso, Kursstand nach 1,3 s ([Lauf 40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565)) |
| **Firefox 142 und WebKit 26** (ab 1.18.1, Option „Weitere Browser“; Playwright im Format des S25+, kein Gerät) | Mit der ersten Fassung von 1.18.1 war „Datenstand & Betrieb“ 179 bzw. 90 px zu breit (Fehler der App, auch in Chromium, dort verdeckt – behoben); danach je **24 von 24 Ansichten** ohne Fehler ([Lauf 40123183068](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40123183068); mit 1.18.2 ebenso, [Lauf 40133046565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40133046565)). Samsung Internet und Chrome auf dem S25+ nutzen Chromium, Firefox und WebKit sind zusätzliche Browser |

Dazu in jeder Live-Prüfung die Installation in Chromium (`test_6`) und in jeder „Prüfung“ 76 Browser-Tests mit simuliertem
S25+ (Chromium, Hoch- und Querformat, ab 1.18.2 auch große Schrift bis 200 %).

**Ausdrücklich offen – auf dem echten S25+ nicht durchgeführt:** **Samsung Internet** (Installation, Darstellung, Service
Worker, dunkles Design), **TalkBack** (Bedienung mit Gesten), **Systemschrift** (Android-Einstellung „Schriftgröße“ auf dem
Gerät) und **App-Installation** (Chrome mit Google-Konto und damit das WebAPK) – dazu One UI, Gesten, Wechsel zwischen
WLAN und Mobilfunk und das Verhalten im Hintergrund. Ergebnisse aus Emulator oder Desktop-Simulation ersetzen diese
Prüfungen nicht. Belegt ist auf dem Gerät nur die Eingabe der Passphrase (Bildschirmfoto „Zugangsschlüssel gespeichert“,
13.10.).

**Kurze Prüfanleitung für das S25+** (etwa 10 Minuten; bei jeder Abweichung ein Bildschirmfoto mit Uhrzeit):

1. **Chrome:** `https://szymeklh87-commits.github.io/tr-aktienvergleich/` öffnen → ⋮ → „App installieren“ (oder „Zum
   Startbildschirm hinzufügen“ → „Installieren“). Erwartet: Symbol „TR-Vergleich“; unter Einstellungen → Apps steht
   „TR-Vergleich“ als eigene App (dann ist es ein WebAPK).
2. Vom Symbol starten: eigenes Fenster ohne Adressleiste → Sperrbildschirm → Passphrase → Startseite mit „Kursstand …“.
3. App schließen und wieder öffnen: je nach Einstellung ohne erneute Passphrase.
4. Flugmodus an, App neu starten: gespeicherter Stand mit Hinweis, dass keine Verbindung besteht. Flugmodus aus.
5. Ins Querformat drehen und die Schrift vergrößern (Einstellungen → Anzeige → Schriftgröße): nichts abgeschnitten.
6. **Samsung Internet:** dieselbe Adresse → ≡ unten rechts → „Seite hinzufügen zu“ → „Startbildschirm“ → „Hinzufügen“
   (wie 01_Kurzanleitung_Handy, Abschnitt 1); Schritte 2–5 wiederholen,
   dazu das dunkle Design von Samsung Internet ein- und ausschalten.
7. Optional TalkBack (Einstellungen → Bedienungshilfen): auf der Startseite mit Wischgesten durch die Elemente gehen –
   jedes sollte einen verständlichen Namen haben.

### 8c. Originalstand vom 12.10.2026: selbst gesucht – historischer Nachweis gegen das Ausgangsmodell nicht möglich

**Auftrag vom 24.10.2026, 21:23 Uhr:** die damaligen Originaldaten selbst beschaffen, ohne ZIP-Dateien anzufordern; nachträglich
beschaffte Kurse gelten nicht als Originaldaten. (Schon um 19:29 Uhr hattest du entschieden, keine ZIP-Dateien bereitzustellen.)

**Geprüfte Fundstellen** (24.10.2026, 21:25–21:40 Uhr, nur lesend). Gesucht wurde nach dem Archiv
`TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip`, nach den im Programmierauftrag (Abschnitt 26) genannten Dateien
`TR_Rendite_Gleichmaessigkeit_1_bis_90_Tage_2026-10-12.html` und `TR_Rendite_Gleichmaessigkeit_Rechendaten_2026-10-12.zip`
(Kursstichtag 09.10.2026) und nach jeder anderen Datendatei des Ausgangsmodells:

| Fundstelle | Umfang | Ergebnis |
|---|---|---|
| Branches und Refs | alle Refs des Repositorys | nur `main` und der Tag `datenstand` – keine weiteren Branches |
| Git-Verlauf | alle damals 146 Commits ab dem ersten (`dc57d13`, 13.10.2026, 00:11 Uhr), alle 335 jemals angelegten Pfade, die größten gespeicherten Inhalte | keine ZIP-, HTML- oder Datendatei des Ausgangsmodells; die größten Inhalte sind App-Bundles (etwa 810 KB). Einzige Datendatei: `tests/live/vergleich/chatgpt_2026-10-13.json` (Prüfwerte deines ChatGPT-Berichts vom 13.10., nur gesalzene Prüfsummen, keine Kurse). Die Archivnamen stehen nur in Doku, Code und `docs/auftrag/Programmierauftrag_v1.2.txt` |
| Tags und Releases | Tag `datenstand`, einziges Release `datenstand` (Vorabversion, 52 Dateien) | für den Kursstichtag 12.10. **drei eigene Stände dieser App** samt Prüfnachweis ihres Laufs (unten) – nichts vom Ausgangsmodell |
| Actions-Artefakte | alle 24 | nur `github-pages`, `github-pages-signale` und `datenquellen-bericht` (13./14.10.) – keine Rechendaten |
| Actions-Läufe | alle 61 Läufe vom 12. und 13.10. | nur Läufe dieser App; das Repository wurde am 13.10.2026 um 10:42 Uhr angelegt – vom 12.10. gibt es hier nichts |
| Issues, Pull Requests, Wiki | – | keine Issues, keine Pull Requests; das Wiki ist nicht lesbar (verlangt eine Anmeldung) |
| Projektdateien und Uploads | Arbeitsverzeichnis, angehängte Dateien | Programmierauftrag und zwei HTML-Übersichten vom 14.10.; kein Archiv |
| Frühere Unterhaltungen und gespeicherte Notizen | Suche nach den Archivnamen, „Rechendaten“ und „12.10.“ | kein Archiv |

**Ergebnis:**

1. **Originaldaten des Ausgangsmodells: nicht wiederherstellbar.** Das Archiv entstand in deinem ChatGPT-Konto und liegt an
   keiner zugänglichen Stelle. **Der historische Nachweis „App = Ausgangsmodell für den 12.10.“ ist damit nicht möglich** –
   er ist weder bestanden noch nicht bestanden. Nicht gemacht: keine Rekonstruktion; die Übernahme des Altbestands
   (Programmierauftrag, Abschnitt 26) bleibt, wie dort verlangt, nicht durchgeführt.
2. **Originaldaten der App vom 12.10.: erhalten und geprüft.** Im Release liegen die drei Stände, die diese App am 13.10. für
   den Kursstichtag 12.10. gerechnet hat, je mit dem verschlüsselten Prüfnachweis des damaligen Laufs (Eingangskurse,
   Renditen und R², so wie damals abgerufen und gerechnet). Job „Originalstand nachrechnen“ (neu in 1.18.1, eigene Rechnung
   ohne den Rechenkern der App), [Lauf 40126000729](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126000729), 24.10.2026, 21:35–21:38 Uhr:

| Stand (berechnet am 13.10.2026) | Software, Methode | Stand = damaliger Lauf (gegen den Prüfnachweis) | Damalige Berechnung reproduziert | Fachlich korrekt |
|---|---|---|---|---|
| `2026-10-12_5092bae0`, Teilstand, 20:33 Uhr | 1.5.0, tr-methode-1.7.0 | **ja** – Aktienliste gleich, Schlusskurse 723.555 von 723.555, Renditen 343.877 von 343.877, R² 270.687 von 270.687 | **ja** – 6.522.718 Prüfungen, 0 Abweichungen | **nein** – 1.280 bekannte Fehlerfälle (1.278 × `gleichstand_rundung`, 2 × `reihe_vorhanden`); beide Ursachen behoben (8d) |
| `2026-10-12_9820e6d9`, vollständig, 21:40 Uhr | 1.5.1, tr-methode-1.8.0 | **ja** – Schlusskurse 727.955, Renditen 667.273, R² 523.956, jeweils alle gleich | **ja** – 10.080.683 Prüfungen, 0 Abweichungen | **nein** – dieselben Fehlerarten (1.278 + 2) |
| `2026-10-12_c3806c24`, vollständig, 22:15 Uhr | 1.5.2, tr-methode-1.8.0 | **ja** – Schlusskurse 726.994, Renditen 666.734, R² 523.526, jeweils alle gleich | **ja** – 10.070.902 Prüfungen, 0 Abweichungen | **nein** – dieselben Fehlerarten (1.278 + 2) |

**Dabei gefunden und behoben (Fehler der Prüfung, nicht des Stands):** Die Nachrechnung erlaubte bei Ständen bis Software
1.5.0 eine fehlende Börsensitzung, die es damals nicht gab – die Regel gilt erst seit 1.5.1 und steht seitdem im Manifest.
Der erste Lauf ([40125726864](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40125726864)) meldete deshalb für `5092bae0` 170 Abweichungen; ohne Eintrag im Manifest gilt jetzt
keine geduldete Lücke (Commit `8bbc2bb`, Tests in `tests/unit/test_nachrechnen_regeln.py`), danach 0.

**Abgrenzung:** Das sind Ergebnisse dieser App mit den Kursen, die sie am 13.10. abgerufen hat – kein Nachweis, dass das
Ausgangsmodell dieselben Kurse oder Ranglisten hatte. Die am 24.10. bei Nasdaq und Yahoo abgerufenen Kurse (8e) sind
nachträglich beschafft und gelten nicht als Originaldaten.

**Fehlende Eingabedaten des Ausgangsmodells** (alle aus dem Archiv, Stichtag 12.10.2026):

1. die Tageskurse je Aktie, wie das Ausgangsmodell sie verwendet hat (Datum, Schlusskurs, Volumen, Notierung);
2. je Aktie und Zeitraum 1–90 Tage: Status, Startdatum, Zahl der Kurse, Rendite, R² und die übrigen Kennzahlen;
3. die 1.980 Ranglisten (90 Zeiträume × 11 Gewichtungen × 2 Gruppen) in voller Länge mit Scores;
4. die Aktienliste dieses Stands und die Split- und Ausschlussentscheidungen;
5. Versions- und Methodenangaben des Archivs (welche Fassung des Ausgangsmodells gerechnet hat).

**Dadurch ungeprüft:**

1. dass die App für den Stichtag 12.10. dieselben Ranglisten liefert wie das Ausgangsmodell – Platz 1, die ersten 10 und die
   ganze Reihenfolge in allen 1.980 Kombinationen;
2. wie das Ausgangsmodell den 12.10. selbst behandelt hat: Yahoo lieferte für diesen Tag am 13.10. zunächst an allen
   geprüften Börsen in Europa und Asien Tageskerzen ohne Schlusskurs und erst später die Kurse (04_Datenquellen,
   09_Bekannte_Luecken A); Tokio und Toronto hatten Feiertag. Ob das Ausgangsmodell diese Kurse schon hatte, sie als fehlend
   zählte, ersetzte oder den Zeitraum verwarf, ist offen – belegt ist sein Verhalten nur für den 13.10. (dort verwirft eine
   Leerzeile den Zeitraum, 09_Bekannte_Luecken D);
3. ob am 12.10. Zeiträume nach der Grenze für fehlende Börsentage anders zugelassen wurden als in der App;
4. die Zahlen des Archivs selbst (Zahl der Aktien, nicht leere Ranglisten) – sie sind nirgends belegt.

**Nachholbar nur mit dem Archiv:** `tests/live/ausgangsmodell_nachrechnen.py` sinngemäß auf dessen Kursreihen anwenden
(Aufbau des Archivs unbekannt, deshalb kein Importmodus vorab gebaut). Ein Vergleich mit den eigenen Ständen der App
(oben) ersetzt diese Prüfung nicht und wird nicht als solche gezählt.

### 8d. Stand vom 13.10.2026: „damalige Berechnung reproduziert“ getrennt von „fachlich korrekt“ – Ursachen der 1.280 Fehlerfälle behoben

**Nachweis:** „App mit echten Daten prüfen“, Job „Rechnung unabhängig nachprüfen“ – [Lauf 40116911344](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116911344)
(24.10.2026, 19:36–19:39 Uhr), gleich in [40117299760](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40117299760) und [40118442565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40118442565) (19:57–19:59 Uhr).
Gerechnet wird ohne den Rechenkern der App (`tests/live/nachrechnen.py`); nur für die Frage „behoben?“ ist der Rechenkern
der aktuellen Version der Prüfling.

| Frage | Ergebnis | Beleg |
|---|---|---|
| Stand 13.10. (Software 1.6.0, tr-methode-1.8.0): **damalige Berechnung reproduziert?** | **ja** – 9.649.807 Prüfungen, 0 Abweichungen (10.876 Kursreihen, 824.337 Zeiträume in Ranglisten) | Hinweis „Nachrechnung Stand mit Schlusskursen 2026-10-13“ |
| Stand 13.10.: **fachlich korrekt?** | **nein** – 1.280 bekannte Fehlerfälle: 1.278 × `gleichstand_rundung` (bei gemischter Gewichtung entschied bei rechnerisch gleichem Score die letzte Binärstelle des Gleitkomma-Scores statt der höheren Kursrendite; nur die Reihenfolge innerhalb gleicher Scores), 2 × `reihe_vorhanden` (Kennzeichen „Kursreihe vorhanden“ bei einer Aktie ohne gültigen Kurs; nur Anzeige) | zwei Warnungen „bekannter Fehler von Software 1.6.0“ |
| Ursache `gleichstand_rundung` in der aktuellen Version **behoben?** | **ja** – der Rechenkern von Software 1.18.0 ordnet auf den Werten dieses Stands **1.278 von 1.278** Fehlerfällen exakt (0 offen); 1.742 von 1.742 Ranglisten gleich der eigenen Rechnung | Hinweis „Stand 2026-10-13: Fehlerursachen und Methodenänderungen“. Gegenprobe: mit der alten Regel meldet dieselbe Prüfung „NICHT belegt“ (Integrationstest `test_fix_check_would_find_a_current_version_with_the_old_rule`); Referenzfälle `tests/unit/test_referenz_gleichstand.py` |
| Ursache `reihe_vorhanden` **behoben?** | **ja** – im Stand vom 23.10. (Software 1.18.0) 598 Aktien ohne gültigen Kurs, **0** davon mit dem Kennzeichen | derselbe Hinweis; Unit-Test `test_has_series_only_with_a_series_file` |
| Stand 23.10. (Software 1.18.0, tr-methode-1.10.0) | reproduziert **ja** (9.987.000 Prüfungen, 0 Abweichungen), fachlich korrekt **ja** (keine bekannten Fehler dieser Version) | Hinweis „Nachrechnung Stand mit Schlusskursen 2026-10-23“ |

**Beabsichtigte Methodenänderungen seit dem 13.10.** (keine Fehler; der Stand bleibt unverändert als Originalreferenz):
tr-methode-1.9.0 (Software 1.14.0, deine Entscheidung vom 14.10.) – Aktien ohne Schlusskurs am Stichtag zählen mit ihrem
letzten Schlusskurs (höchstens eine verpasste Sitzung); tr-methode-1.10.0 (Software 1.18.0, deine Entscheidung vom 24.10.)
– Gleichstand exakt: bei rechnerisch gleichem Score die höhere Kursrendite, dann die ISIN; zugleich die Korrektur von
`gleichstand_rundung`.

**Offen, nicht belegbar:** welche Kurse das Ausgangsmodell bzw. ChatGPT am 12. und 13.10. hatte (Abschnitt 8c). Der
Vergleich über Prüfwerte im selben Lauf (126 Ranglisten deines ChatGPT-Berichts) zählt nur Übereinstimmungen; ohne dessen
Eingabedaten lässt er keine Ursachen zu.

### 8e. Aktuelle Berechnung unabhängig geprüft – auch mit nachträglich beschafften Kursen

Auftrag vom 24.10.2026, 19:29 Uhr. **Nachträglich beschaffte Daten sind gekennzeichnet; sie belegen nicht, welche Daten das
Ausgangsmodell damals hatte.**

| Was | Wie | Ergebnis |
|---|---|---|
| Ranglisten und Berechnungen | eigene Rechnung ohne Rechenkern über den ganzen Stand vom 23.10. (Renditen bitgleich, R², Zulassung, alle 11 Gewichtungen in Gruppe A und B, Gleichstände, Ø Tagesumsatz, Häufigkeit, Prüfsummen) | **0 Abweichungen in 9.987.000 Prüfungen** (Abschnitt 8d) |
| Gleichstandsregel | Referenzfälle mit exakten Brüchen (11 Tests, Gegenprobe mit drei falschen Regeln) und die Nachrechnung (Gleichstandsplätze je Rangliste) | bestanden; im Stand vom 23.10. ändert der exakte Vergleich gegenüber Gleitkomma Platz 1 in 4 und die ersten 10 in 4 Ranglisten (Aktien) – wie im Manifest |
| Fehlende Kurstage | Referenzfälle durch den ganzen Rechenkern (8 Tests, Tabelle in 12_Fehlende_Kurstage gegen die eigene Rechnung geprüft) und die Auswertung mit echten Daten (Ranglisten des Skripts = veröffentlichte, 1.980 von 1.980); **nachträglich bei Nasdaq:** 4 Börsentage, an denen Nasdaq einen Kurs hat und der Stand keinen – alle 4 zählt die App als fehlenden Kurstag, und **Yahoo hat an keinem dieser Tage einen Kurs** (die Lücke liegt beim Anbieter, kein Ersatzkurs) | bestanden |
| **Kurse selbst** (nachträglich beschafft) | Job „Kurse unabhängig gegenprüfen (Nasdaq)“, zuletzt [Lauf 40128434473](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128434473), Abruf 24.10.2026, 22:10 Uhr (gleiche Zahlen wie [40118442565](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40118442565) um 19:59 Uhr): 307 US-Aktien des Stands vom 23.10. (157 aus den ersten 10 einer Rangliste, 150 zufällig), 272 bei Nasdaq gefunden (35 ohne Kurse, alle mit fünfstelligem Kürzel); je Börsentag und je Rendite 1–90 Tage verglichen, jede Abweichung per Gegenprobe bei Yahoo (eigene Auswertung) eingeordnet | **Nicht bestätigt** (Job rot; Urteil seit 22 Uhr – um 19:59 Uhr hieß es noch „bestanden mit Unterschieden zwischen den Anbietern“): Schlusskurse 18.182 von 18.753 gleich (96,96 %); abweichend 571 (Nachbartag 18, klein bis 0,5 % 417, groß 136); Renditen 23.656 von 24.274 gleich, 618 abweichend. Jede Abweichung ist der heutige Yahoo-Kurs (der Stand gleicht Yahoo an 18.764 von 18.764 Tagen) – das zeigt nur, dass die App die Kurse ihrer Quelle unverändert übernimmt, **nicht, dass es die Börsenkurse sind**. Groß weichen nur 5 Aktien ab, 4 davon unter 1 $ (bis 4 %; Renditen bis 4,72 Prozentpunkte, darunter Aktien unter den ersten 10). Belege und Wirkung auf die Ranglisten: unten, „Ursachen der Unterschiede“ |

Die Gegenprüfung lief am 24.10. dreimal: [40116911344](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116911344) und [40117299760](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40117299760) noch ohne
Gegenprobe – rot wegen 136 großer Abweichungen (der zweite Lauf mit anonymen Mustern: Verhältnis, Lage, Cent-Beträge);
erst die Gegenprobe bei Yahoo zeigte, dass alle Abweichungen die Kurse von Yahoo sind. Von 19:57 bis 22 Uhr galt „wie
Yahoo“ als Beleg (Urteil „bestanden mit Unterschieden zwischen den Anbietern“, Job grün). Nach deinem Hinweis von 21:23
Uhr – „Entspricht Yahoo“ reicht nicht als unabhängiger Nachweis – heißt das Urteil **„nicht bestätigt“** und der Job ist
rot; grün ist er nur noch, wenn alle Kurse wie bei Nasdaq sind. Die Ursachen der Unterschiede klärt der nächste Abschnitt
mit Belegen; was nicht belegt ist, bleibt ungeklärt. Allgemein gilt: Anbieter verwenden verschiedene Schlusskurse ([SEC,
Investor.gov: „Closing price“](https://www.investor.gov/introduction-investing/investing-basics/glossary/closing-price): „… may continue to be reported differently by various media and market data vendors“).

**Nicht gezeigt:** welche Kurse ein anderes Modell damals hatte; Aktien außerhalb der USA (Nasdaq führt sie nicht – seit dem
25.10., 09:20 Uhr die 156 mit Platz unter den ersten 10 gegen CNBC, unten); ob Yahoo
Kurse zwischen dem Abruf der App und der Gegenprobe geändert hat (dann gälte die Abweichung als unerklärt).

#### Strenge Beleglage, abgesicherte Zuordnung, gemeinsame Rechnung (b)+(c) und Abdeckung des ganzen Universums (Auftrag vom 25.10.2026, 09:20 Uhr)

**Ausgangslage geprüft (09:46 Uhr):** keine Änderungen seit Lauf 40162120622 – `main` = `1355c6d` (nur Dokumentation nach
`88d2733`), kein neuer täglicher oder Nachtlauf, ausgelieferte App `1.18.2+3a4bd974` (version.json), Datenstand
`2026-10-23_3f7ce5f3`. Während der Arbeit lief der tägliche Lauf über den Zeitplan (Sonntag, 11:44–11:56 Uhr,
[40186008825](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40186008825)): „keine neuen Daten“ (kein
neuer abgeschlossener Börsentag seit dem 23.10.), Datenstand unverändert; neu bereitgestellt nur Kennzahlen und der
Signal-Stand `20261025T104649Z`, die nicht in die Ranglisten eingehen. Geprüft wurde durchgehend gegen denselben Stand.

**Drei getrennte Ergebnisse** (Einzelheiten unten): *Softwaretests* – bestanden („Prüfung“ des endgültigen Codes `ddb4ff1`: 748 Tests, 726 bestanden, 22 übersprungen, 0 fehlgeschlagen). *Datenbestätigung* – an
**33.434 von 34.500** abgesichert verglichenen Aktientagen gleich der Vergleichsquelle, an 1.066 nicht; verglichen sind 505
der 11.596 Aktien des Universums, zusammen 34.500 der 750.366 Kurstage des Stands (4,6 %) – **keine Vollprüfung**. *Ursachenklärung* – von den 1.066
abweichenden Aktientagen ist die Ursache an **34** belegt (gemeldeter Split), **1.032 bleiben ungeklärt** (74 davon mit
plausibler Erklärung); die bisher als belegt gezählten 49, 56 und 2 Fälle sind keine belegten Ursachen.

**Gefundene Fehler am Code (zu den sechs Einwänden) – alle behoben** (Commit `438b2e1`, jeder mit Test):

| # | Einwand | Befund am Code bis `88d2733` | Behebung |
|---|---|---|---|
| 1 | Punkt 2 – Minutenkerze, Kursstufe, Umsatz 0 | als **belegte Ursache** gezählt (`letzter_abschluss`, `nasdaq_letzter_abschluss`, `rundung`, `kein_handel`); jeder Faktor eines üblichen Split-Verhältnisses galt als Split, jeder Vergleichskurs = `adjclose` als Dividendenbereinigung – ohne gemeldetes Ereignis | belegt nur mit gemeldetem Ereignis (Split passenden Verhältnisses bzw. Dividende nach dem Tag); alles andere „ungeklärt mit plausibler Erklärung“ |
| 2 | Punkt 2 – überlappende Fälle | Nasdaq-Historie und NOCP zählten denselben Aktientag je einmal | zusätzlich je Aktie und Tag genau einmal (maßgeblich der abgesicherte NOCP), mit der Überschneidung |
| 3 | Punkt 3 – Zuordnung | Nasdaq-Historie und NOCP ohne jede Prüfung der Wertpapieridentität (nur das Kürzel); CNBC galt als vergleichbar mit „nur Kürzel“, „Handelsplatz nicht angegeben“ und „Währung nicht angegeben“; Barchart allein über Kürzel und Kursniveau | Absicherung je Vergleich (ISIN → Kürzel laut OpenFIGI, Name und Art laut Quelle, Börse, Währung, Handelstag, Bereinigung, Kursniveau, Tage); fehlende Angabe = nicht bestanden; nicht abgesichert = kein Ersatzkurs, keine Bestätigung |
| 4 | Punkt 4 – OTC-Zeitstempel | der Handelstag des letzten Abschlusses wurde nach Ortszeit New York gewählt, weil diese Umrechnung zum Stand passte (`88d2733`), und der Abschluss diente als zweite Quelle | Bedeutung von „lastTradeTime“ nicht belegt → Zuordnung offen; der OTC-Abschluss ist weder Vergleichskurs noch zweite Quelle; nur Beobachtungen gezählt |
| 5 | Punkt 5 – Auslösersuche | einzelne Aktien, dann schrittweise hinzunehmen und weglassen – findet die kleinste Menge im Allgemeinen nicht (Gegenbeispiel im Test); dazu still auf 40 Kandidaten begrenzt | Teilmengen nach Größe, jede Größe vollständig (nachweislich kleinste); sonst irreduzible Menge mit genannter Grenze; Gegenprobe je Auslöser |
| 6 | Punkt 6 – Abdeckung | nur die US-Auswahl; die übrigen Plätze unter den ersten 10 ungeprüft | Job „welt“ (CNBC) und Abdeckung des ganzen Universums |
| 7 | beim Testen des neuen Codes, vor jedem Lauf | Währung der Kursmeldung in Großbuchstaben („GBp“ → „GBP“) und Vergleich ohne Groß-/Kleinschreibung: Kurse in Pfund wären als Pence verglichen worden (Faktor 100) | Schreibweise bleibt, Umrechnung über die Untereinheiten der App |
| 8 | beim Testen | „Art“ aus dem Namen ohne Wertpapierbeschreibung: „… - Warrants“ wäre als Aktie durchgegangen | Art aus dem vollständigen Namen |
| 9 | Durchsicht | Variante (a) hätte an Tagen mit Split-Faktor den unbereinigten Nasdaq-Kurs eingesetzt (im Lauf 40162120622 an 0 Tagen – ohne Wirkung) | solche Tage werden nie ersetzt |

**Im ersten Lauf mit dem neuen Code gefunden** ([40181869022](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40181869022), Commit `438b2e1`, 10:44–10:53 Uhr) – behoben in `09bc9e1`:

| # | Befund im Lauf 40181869022 | Ursache am Code | Behebung |
|---|---|---|---|
| 10 | In der Zuordnung des Jobs „gemeinsame Wirkung“ standen Aktien außerhalb der US-Auswahl mit „unter den ersten 10 in 0 Ranglisten“ – auch solche auf Platz 1 (z. B. der neue Spitzenreiter Z38) | die Plätze je Aktie kamen nur aus der US-Auswahl | Plätze unter den ersten 10 und auf Platz 1 aller Aktien aus allen Ranglisten (Integrationstest) |
| 11 | Die Namensprüfung hieß „Name der Quelle passt zum Stand (nur Hinweis)“ | Beschriftung falsch – gezählt wurde sie schon als Pflichtprüfung | Beschriftung ohne „nur Hinweis“ (Unit-Test) |
| 12 | „Abfrage minus Zeitstempel: unter 1 h“ bei allen 25 OTC-Zeitstempeln, obwohl der Abruf über 24 Stunden nach dem Stempel lag | gemessen war der Abstand zu `quoteTime` der Antwort, nicht zum Abruf | beide Abstände getrennt (`quoteTime` der Antwort; Uhr des Prüfrechners), dazu Minute, Sekunde, Bruchteil und Einheit des Stempels |
| 13 | 4 Stockholmer Aktien mit Gattung im Kürzel „nicht abgesichert“ (Aktie und Gattung) | OpenFIGI schreibt die Gattung ohne Trennzeichen, die App mit Bindestrich (Beispiel aus der Dokumentation, nicht aus dem Lauf: „ADDTB“ bzw. „ADDT-B.ST“) – diese dokumentierte andere Schreibweise der App (`symbol_variants`) galt nicht als dasselbe Kürzel | Kürzel in der Schreibweise der App oder einer ihrer dokumentierten Schreibweisen; eine andere Gattung bleibt ein anderes Kürzel (Unit-Test); „ISIN bei OpenFIGI unbekannt“ getrennt gezählt |
| 14 | Neue Spitzenreiter ohne Vergleichskurse (z. B. Z33) erschienen nur als „ausgewählt, aber ohne Vergleichskurse“ | die Legende kannte für Lücken weder Börse noch Grund | jede Aktie ohne abgesicherten Vergleich mit Buchstaben, Börse, Kursbereich, Plätzen, ungeprüften Tagen und Grund; dazu je Börse die nicht bestandenen Prüfungen und die Ranglisten, deren Platz 1 ungeprüft ist |
| 15 | Im Job „gemeinsame Wirkung“ fehlten 42 von 86 Teilen der Hinweise (GitHub zeigt je Job höchstens 50) | Langform in den Hinweisen | Hinweise in Kurzform (Legende im ersten Teil jedes Abschnitts), Zusammenfassung in Langform |
| 16 | Die früher als belegt gezählten 49/56/2 Fälle ließen sich nicht vollständig abstimmen | Vergleiche, die jetzt nicht abgesichert sind, wurden gar nicht mehr betrachtet | sie werden gezählt (verglichene und abweichende Tage, Einordnung, die sie in einem abgesicherten Vergleich bekämen) – weder Bestätigung noch Ursache noch Ersatzkurs |
| 17 | Eine US-Aktie ohne Nasdaq-Kurse an der NYSE hieß in der Legende „andere“ | nur OTC oder „andere“ unterschieden | Börse aus dem Börsencode der Kurse (Nasdaq, NYSE-Gruppe, Cboe, OTC) |

**Bei der Durchsicht des zweiten Laufs gefunden** ([40184599190](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40184599190), Commit `09bc9e1`, 11:23–11:33 Uhr) – behoben in `2fc32d3`:

| # | Befund im Lauf 40184599190 | Ursache am Code | Behebung |
|---|---|---|---|
| 18 | Punkt 5: Die Gegenprobe der Auslöser („Z31 allein“, „alle übrigen ohne Z31“) war keine unabhängige Bestätigung | gerechnet mit der schnellen Rechnung der Suche, die nur an der leeren und der vollen Menge gegen die unabhängige Rechnung geprüft war | Gegenprobe mit der unabhängigen Rechnung der Nachrechnung (`nachrechnen.rank_group`); bei Auslösermenge 1 zusätzlich jede ersetzte Aktie einzeln unabhängig; eine Abweichung von der Suche steht am Wechsel (Unit-Test mit verfälschter schneller Rechnung) |
| 19 | „227 Aktien und 12422 Tage ohne abgesicherten NOCP (nicht Nasdaq-notiert …)“ | nicht Nasdaq-notiert waren 180; dazu 38 ohne Nasdaq-Kurse und 9 mit nicht abgesicherter Zuordnung; die 12.422 Tage sind nur die der Aktien mit abgesichertem Nasdaq-Vergleich. Bei allen Vergleichen blieb offen, dass die nicht abgesicherten Aktien Teil der fehlenden Prüfmöglichkeit sind (nicht zusätzlich) | je Vergleich aufgeschlüsselt, die nicht abgesicherten ausdrücklich als Teil davon (Unit-Test mit den Zahlen des Laufs) |
| 20 | „Wechselwirkung … (1980 Ranglisten mit einer Änderung in einem Teil)“ | auch die 340 leeren Ranglisten mitgezählt (1.640 mit Einträgen); die Zählwerte der Änderungen waren nicht betroffen | nur Ranglisten mit Einträgen (Integrationstest; ohne die Korrektur rot: 1.980 > 1.640) |
| 21 | Bei nicht abgesicherten Aktien stand nur der Name der nicht bestandenen Prüfung – z. B. „Kursniveau“ bei einer Aktie mit 22 Plätzen 1 | kein Befund ausgegeben | Befund je nicht bestandener Prüfung aus Codes und Zahlen (Prüfziffer und Land der ISIN, Börsencodes bei OpenFIGI, Ähnlichkeit des Namens, Börse und Währung laut Quelle, Kursniveau im Median, Zahl der Tage, geprüfte Schreibweisen bei CNBC) – keine Namen, Kürzel oder ISIN (Unit-Tests) |

**Im dritten Lauf gefunden** ([40187567792](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40187567792), Commit `2fc32d3`, 12:07–12:18 Uhr) – behoben in `8b4b52e`:

| # | Befund im Lauf 40187567792 | Ursache am Code | Behebung |
|---|---|---|---|
| 22 | Im Job „zufall“ blieb ein Block von 100 ISINs bei OpenFIGI ohne Antwort („fehler_ProviderError“) – alle 100 Vergleiche galten als nicht ausreichend abgesichert (Zufallsstichprobe abgesichert 46 statt 137). Nach der Regel richtig, das Ergebnis des Laufs ist aber unbrauchbar und nicht verwendet | ein gescheiterter Block traf alle seine ISINs, ohne zweiten Versuch; die Fehlerart war ohne HTTP-Status | Pause von 60 s und zweiter Versuch des Blocks, danach Teilblöcke von 10 ISINs; nur was dann ohne Antwort bleibt, gilt als nicht geprüft; Fehlerart mit HTTP-Status und die Wiederholungen als Zählwerte (Unit-Tests: dauerhafter Fehler trifft nur den eigenen Teilblock, vorübergehender kostet keine Absicherung) |

**Bei der unabhängigen Gegenprüfung des Berichts gefunden** (die Gegenprüfung im Anschluss) – behoben in `ddb4ff1`, bestätigt in
[Lauf 40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763):

| # | Befund | Ursache am Code | Behebung |
|---|---|---|---|
| 23 | Im Job „außerhalb der US-Auswahl“ stand „0 Aktien ohne Antwort einer Quelle“ fest im Titel; eine Aktie, deren Kursmeldung oder Tageskerzen bei CNBC ohne Antwort blieben, hätte als „bei CNBC unter keiner Schreibweise gefunden“ gegolten. Die Lücken dort hießen „ohne Vergleichskurse (Nasdaq und Zusatzquellen)“, obwohl nur CNBC abgefragt wird. Im Lauf 40188406664 ohne Wirkung auf die Zahlen (alle 9 Kursmeldungen und 126 Kerzenabrufe „ok“) | `abruf_fehlgeschlagen` war im Job „welt“ fest 0, die Übergabe ohne „fehlgeschlagen“; ein Abruf mit HTTP-Fehler fiel in „nicht gefunden“ bzw. „keine Kurse“ | Anfrage ohne verwertbare Antwort (HTTP- oder Netzfehler, unlesbare Antwort) nach 15 s einmal wiederholt, danach **„ohne Antwort“** (Abruf fehlgeschlagen) mit Befund – in Titel, Abdeckung, Lücke und Übergabe; Zustand der Lücken ohne Nennung nicht abgefragter Quellen. Gegenprobe: der alte Code ordnet eine Kursmeldung mit HTTP 503 als „nicht_gefunden“ ein (Befund „bei CNBC gesucht unter 1 Schreibweisen“), der neue als „ohne_antwort“; 3 Unit-Tests, 1 Integrationstest |

**Unabhängige Gegenprüfung des Berichts** (25.10.2026, mittags; durch einen getrennten Prüfer, der den Bericht nicht geschrieben hat, Zahl für Zahl gegen die Hinweise von Lauf 40188406664 und den Code; Summen und Zerlegungen mit eigenen Skripten nachgerechnet): alle Summen und Zerlegungen gehen auf; gefunden und berichtigt:

| Befund der Gegenprüfung | Einordnung | Berichtigung |
|---|---|---|
| „weitere Quellen für die 30 bei CNBC nicht gefundenen Aktien (geprüft: CNBC, OTC Markets, Barchart, MarketWatch, Stooq …)“ | **falsch** – für Aktien außerhalb der US-Auswahl fragt der Job „welt“ nur CNBC ab; die übrigen Quellen nur die US-Jobs für die 38 US-Aktien ohne Nasdaq-Kurse | Text berichtigt (Punkt 6, Prüfstatus 6); die Lücken außerhalb der US-Auswahl hießen auch in der Ausgabe „ohne Vergleichskurse (Nasdaq und Zusatzquellen)“ – im Code berichtigt (Nr. 23) |
| „0 Aktien ohne Antwort, 0 fehlgeschlagene Abrufe“ | **falsch** im zweiten Teil – „Abruf fehlgeschlagen 0“ zählt Aktien ohne jede Antwort; bei den Zusatzquellen scheiterten Barchart (HTTP 403), MarketWatch (HTTP 401), die Kurshistorie von OTC Markets (HTTP 404) und Stooq (HTML statt Daten) bei jeder der 38 US-Aktien ohne Nasdaq-Kurse | Text berichtigt; dazu am Code: im Job „welt“ stand „ohne Antwort“ fest auf 0 (Nr. 23) |
| „nichts erst gemeinsam, nichts aufgehoben“ (Überblick) | ungenau – gilt auf Ebene der Ranglisten, nicht für einzelne Rangänderungen (782 bzw. 5.656) | eingeschränkt |
| „ohne Folge für Platz 1 und die ersten 10“, „erst unterhalb davon …“ | ungenau – die 782/5.656 zählen über die ganze Liste; belegt sind Platz 1, die Aktien der ersten 10 und die Reihenfolge in 29 von 36 Ranglisten | präzisiert |
| „an 4,6 % ihrer Tage“ | missverständlich – 4,6 % der Kurstage aller Aktien; die 505 selbst sind an fast allen ihrer Tage verglichen | umformuliert |
| „nur kostenpflichtig“ für NYSE-Gruppe und Cboe | ungenau – das kostenpflichtige Produkt ist für die NYSE belegt, für Cboe nur „nicht frei verfügbar“ | getrennt |
| Prüfstatus 4: Zusammenfassung des Jobs und Fundstellen | ungenau – 11 Teile nur in der nicht abrufbaren Zusammenfassung; 8 Buchstaben (Aktien in keiner Rangliste) ohne Fundstelle | als „nicht geprüft“ bzw. „ohne Fundstelle“ ausgewiesen |
| Z178 „ein anderes Wertpapier“ | Deutung als Tatsache | als nicht belegt formuliert |
| „weil nicht abgesicherte Vergleiche nichts mehr ersetzen“ | stärker als belegt | „u. a.“, andere Gründe nicht ausgeschlossen |
| „4 OTC-Aktien ohne Kurse“ | ungenau – ohne Vergleichskurse; Kurse im Stand haben sie | berichtigt |
| „je Aktie und Tag 71 + 2“ | ungenau – 71 nach der Vorrangregel (NOCP), nicht die bereinigte Menge aus 45 + 40 | Regel genannt |
| „ohne Börse 451 (ohne Kursreihe)“ | erschlossen – die Ausgabe sagt „Tage im Stand 0“ | wie ausgegeben |

Nicht aus den Hinweisen prüfbar (kein Fehler): Zeiten, Commits, frühere Läufe, die Recherche zu OTC Markets und Stooq.

Drei Tests prüften die alte, zu großzügige Einordnung und sind durch strengere ersetzt – keiner abgeschwächt:
`test_last_trade_from_two_minute_candles_is_evidence` → `test_last_trade_from_minute_candles_is_only_a_plausible_explanation`,
`test_dividend_adjustment_and_split` → `test_dividend_adjustment_and_split_need_a_reported_event`,
`test_green_only_when_complete_and_every_deviation_has_evidence` → `test_green_only_when_complete_secured_and_every_deviation_has_evidence`.
Neu insgesamt 50 Tests (`438b2e1`: 30, `09bc9e1`: 10, `2fc32d3`: 5, `8b4b52e`: 1, `ddb4ff1`: 4).

**Ergebnis** – [Lauf 40188406664](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664), 25.10.2026, 12:19–12:29 Uhr (MEZ), Commit `8b4b52e`
(endgültiger Code), Eingabe „ursachen_stand“ = `2026-10-23_3f7ce5f3`: vier Prüfjobs auf vier Rechnern
([erste 10](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002761), [Plätze 11–20](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002620), [Zufallsstichprobe](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002593),
[außerhalb der US-Auswahl](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002633)) und der Job
[„Ursachen – gemeinsame Wirkung aller Gruppen“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121155333880); „Prüfung“ desselben Commits
[40188407048](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188407048): 744 Tests, 722 bestanden, 22 übersprungen, 0 fehlgeschlagen; Kalender 4 von 4. Alle
Vergleichskurse nachträglich abgerufen – **keine Originaldaten**. OpenFIGI hat für alle 560 ISINs geantwortet (keine
Wiederholung nötig). Dieselben Zahlen wie in Lauf 40184599190 (Prüfsummen der Vergleichskurse gleich: erste 10
`2ddcd67633a03102`, Plätze 11–20 `8414fb849411bd7c`, Zufallsstichprobe `00b68f1ec014b090`, außerhalb der US-Auswahl
`4c391d9673b07f76`; Quelle je Aktie und Tag `d72f681a0cec39d2`) – neu sind nur die Gegenprobe mit der unabhängigen Rechnung,
die Befunde und die Aufschlüsselungen (Nr. 18–21). **Mit dem endgültigen Code bestätigt:**
[Lauf 40192915763](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40192915763) (Commit `ddb4ff1`, 13:23–13:32 Uhr, gleiche Eingaben) – die Hinweise aller fünf Jobs Zeile
für Zeile gegen diesen Lauf verglichen: gleich bis auf Dauer und Zeitstempel, eine Anfrage an Nasdaq mehr im Job „erste 10“
(266 statt 265) und die neuen Texte von Nr. 23; dieselben Prüfsummen, Titel und Buchstaben. Die Zahlen dieses Abschnitts
gelten für beide Läufe. Alle fünf Jobs rot – nicht wegen des Abrufs (0 Aktien ohne jede Antwort; ohne
Daten blieben nur die Zusatzquellen Barchart – HTTP 403 –, MarketWatch – HTTP 401 –, die Kurshistorie von OTC Markets – HTTP
404 – und Stooq – HTML statt Daten – bei allen 38 US-Aktien ohne Nasdaq-Kurse), sondern weil Aktien ohne abgesicherten
Vergleich bleiben und außer an den Split-Tagen keine Abweichung eine belegte Ursache hat:

| Job | Titel des Ergebnisses |
|---|---|
| erste 10 | UNVOLLSTÄNDIG – 0 Aktien ohne Antwort einer Quelle, 0 ohne Vergleichskurse, 4 nicht abgesichert; 433 von 451 abweichenden Aktientagen ungeklärt (45 davon mit plausibler Erklärung) |
| Plätze 11–20 | NICHT VOLLSTÄNDIG BELEGT – 94 von 94 abweichenden Aktientagen ungeklärt (4 davon mit plausibler Erklärung) |
| Zufallsstichprobe | UNVOLLSTÄNDIG – 0 Aktien ohne Antwort einer Quelle, 4 ohne Vergleichskurse, 9 nicht abgesichert; 438 von 454 abweichenden Aktientagen ungeklärt (24 davon mit plausibler Erklärung) |
| außerhalb der US-Auswahl | UNVOLLSTÄNDIG – 0 Aktien ohne Antwort einer Quelle, 30 ohne Vergleichskurse, 8 nicht abgesichert; 67 von 67 abweichenden Aktientagen ungeklärt (1 davon mit plausibler Erklärung) |
| gemeinsame Wirkung | UNVOLLSTÄNDIG – 55 von 560 ausgewählten Aktien ohne abgesicherten Vergleich; gemeinsame Wirkung der übrigen gerechnet |

Hinweise: erste 10 alle 19 Teile, Plätze 11–20 alle 9, Zufallsstichprobe alle 14, außerhalb der US-Auswahl alle 16;
gemeinsame Wirkung 44 von 55 – nicht als Hinweis 11 Teile „andere Reihenfolge der ersten 10 bei gleichen Aktien“ (1 Teil
„einzeln – (b), (c), (b)+(c)“, 10 Teile „übrige Varianten“), laut letztem Hinweis vollständig in der Zusammenfassung des Jobs.
Zusammenfassungen und Protokolle der Jobs sind über die Schnittstelle von hier aus nicht abrufbar (sie liegen auf einem
Speicher außerhalb von GitHub, Zugriff verweigert) – ausgewertet sind die Hinweise; die einzelnen Reihenfolgen für (b), (c)
und (b)+(c) stehen bei gleichen Kursen (gleiche Prüfsummen) auch in den Hinweisen von Lauf 40184599190. Im selben Lauf: App
`1.18.2+3a4bd974` mit echten Daten 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten
([Job „pruefen“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002660)); Nachrechnung des Stands 23.10. 0 Abweichungen in 9.987.000 Prüfungen, fachlich
korrekt ([Job „Rechnung unabhängig nachprüfen“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40188406664/job/121154002450)).

##### Punkt 1 – offizieller Schlusskurs und CNBC gemeinsam gegen denselben unveränderten Stand

Alle 1.640 Ranglisten mit Einträgen (von 1.980 möglichen) neu gerechnet, jede Variante gegen den unveränderten Stand.
**Quelle je Aktie und Tag** (Regel, im Job ausgewiesen): (b) offizieller Schlusskurs NOCP an jedem Tag mit Stand ≠ NOCP bei
Nasdaq-notierten Aktien der US-Auswahl mit abgesicherter Zuordnung; (c) CNBC an jedem abweichenden Tag bei US-Aktien ohne
Nasdaq-Kurse (die erste abgesicherte Zusatzquelle – in diesem Lauf immer CNBC); (d) CNBC an jedem abweichenden Tag bei
abgesicherten Aktien außerhalb der US-Auswahl; Tage, die um einen gemeldeten Split bereinigt gleich sind, nie ersetzt. Ersetzt
werden **691 Aktientage bei 73 Aktien** – NOCP 359 Tage bei 49 Aktien, CNBC (US) 265 bei 18, CNBC (außerhalb der US-Auswahl)
67 bei 6 –, **Überschneidung 0** (je Aktie und Tag genau eine Quelle), Prüfsumme `d72f681a0cec39d2`; jede Aktie mit jedem
Tag (Datum, Abweichung in %, Einordnung) im Abschnitt „Quelle je Aktie und Tag“ des Jobs. Nicht abgesicherte Vergleiche
ersetzen nichts.

| Variante (Kurse aller Jobs gemeinsam) | Platz 1 anders | andere Aktien unter den ersten 10 | andere Reihenfolge der ersten 10 (einschl. anderer Aktien) | irgendeine Änderung |
|---|---|---|---|---|
| (a) Nasdaq-Historie | 0 | 2 | 14 | 1.280 |
| (b) offizieller Schlusskurs (NOCP) | **4** | 6 | 33 | 1.116 |
| (c) CNBC – US-Aktien ohne Nasdaq-Kurse | 0 | 1 | 3 | 831 |
| (d) CNBC – außerhalb der US-Auswahl | 0 | 25 | 135 | 1.103 |
| **(b)+(c)** offizieller Schlusskurs und CNBC (US-Auswahl) | **4** | 7 | 36 | 1.154 |
| (c)+(d) alle CNBC-Kurse | 0 | 26 | 138 | 1.110 |
| **(b)+(c)+(d)** offizieller Schlusskurs und alle CNBC-Kurse | **4** | 32 | 166 | 1.311 |
| (a)+(c) | 0 | 3 | 17 | 1.285 |
| (a)+(c)+(d) | 0 | 28 | 152 | 1.440 |

**Wechselwirkung – entsteht etwas erst gemeinsam, hebt sich etwas auf?** Je Rangliste und Eigenschaft: „erst gemeinsam“ =
gemeinsam geändert, mit keinem Teil allein; „aufgehoben“ = mit einem Teil allein geändert, gemeinsam nicht; dazu je Aktie und
Rangliste die Rangänderungen über die ganze Liste (1.640 Ranglisten mit Einträgen):

| gemeinsam gegen die Teile | Platz 1 (gemeinsam / Teil 1 / Teil 2) | Aktien der ersten 10 | Reihenfolge der ersten 10 | irgendeine Änderung | erst gemeinsam / aufgehoben (Platz 1, Aktien und Reihenfolge der ersten 10, irgendeine Änderung) | Rangänderungen Aktie × Rangliste: gemeinsam / Teil 1 / Teil 2 – erst gemeinsam / aufgehoben |
|---|---|---|---|---|---|---|
| (b)+(c) gegen (b), (c) | 4 / 4 / 0 | 7 / 6 / 1 | 36 / 33 / 3 | 1.154 / 1.116 / 831 | **0 / 0** | 289.806 / 216.696 / 88.133 – 782 / 5.656 |
| (b)+(c)+(d) gegen (b), (c)+(d) | 4 / 4 / 0 | 32 / 6 / 26 | 166 / 33 / 138 | 1.311 / 1.116 / 1.110 | **0 / 0** | 353.754 / 216.696 / 170.665 – 2.122 / 12.573 |
| (c)+(d) gegen (c), (d) | 0 / 0 / 0 | 26 / 1 / 25 | 138 / 3 / 135 | 1.110 / 831 / 1.103 | **0 / 0** | 170.665 / 88.133 / 86.964 – 491 / 1.310 |
| (a)+(c) gegen (a), (c) | 0 / 0 / 0 | 3 / 2 / 1 | 17 / 14 / 3 | 1.285 / 1.280 / 831 | **0 / 0** | 181.920 / 98.759 / 88.133 – 517 / 2.279 |
| (a)+(c)+(d) gegen (a), (c)+(d) | 0 / 0 / 0 | 28 / 2 / 26 | 152 / 14 / 138 | 1.440 / 1.280 / 1.110 | **0 / 0** | 255.966 / 98.759 / 170.665 – 927 / 4.867 |

*Lesart:* Auf der Ebene der Ranglisten entsteht **nichts erst gemeinsam und nichts hebt sich auf** – jeder gemeinsame neue
Platz 1, jede gemeinsame Änderung der ersten 10 tritt auch mit einem Teil allein auf; gemeinsam auch kein anderer neuer
Platz 1 als einzeln. Unter den ersten 10 sind die gemeinsam geänderten Ranglisten genau die Vereinigung der Teile ((b)+(c): 6 + 1
Ranglisten mit anderen Aktien, 33 + 3 mit anderer Reihenfolge); die Aktien, die gemeinsam unter die ersten 10 kommen bzw. sie
verlassen, sind dieselben wie mit dem jeweiligen Teil. In den 29 dieser Ranglisten mit gleichen Aktien in anderer Reihenfolge
ist die gemeinsame Reihenfolge gleich der des Teils (einzeln ausgegeben in den Hinweisen von Lauf 40184599190 mit denselben
Prüfsummen der Vergleichskurse); für die 7 Ranglisten mit anderen Aktien ist die Reihenfolge innerhalb der ersten 10 nicht
einzeln ausgegeben. Über die ganze Liste überlagern sich die Teile: Mit (b)+(c) ändert sich der Rang von 782 Paaren aus
Aktie und Rangliste erst gemeinsam, 5.656 Rangänderungen eines Teils allein heben sich gemeinsam auf (die Aktie steht
gemeinsam wieder auf ihrem alten Platz) – gezählt über alle Plätze; wie viele davon innerhalb der ersten 10 liegen, ist nicht
ausgegeben.
**Zum Vergleich je Job allein** (Platz 1 / Aktien der ersten 10 / Reihenfolge / irgendeine Änderung): erste 10 (a) 0 / 2 / 14 /
1.169, (b) 4 / 6 / 33 / 949, (c) 0 / 0 / 1 / 183; Plätze 11–20 (a) 0 / 0 / 0 / 477, (b) 0 / 0 / 0 / 315, (c) 0 / 0 / 0 / 400;
Zufallsstichprobe (a) 0 / 0 / 0 / 842, (b) 0 / 0 / 0 / 656, (c) 0 / 1 / 2 / 820; außerhalb der US-Auswahl (d) 0 / 25 / 135 /
1.103. Kein neuer Platz 1 entsteht nur gemeinsam oder nur in einem Job allein. Gegen Lauf 40139805053 (gleicher Stand, damals ohne
Absicherung): Platz 1, Aktien und Reihenfolge der ersten 10 gleich, „irgendeine Änderung“ kleiner (erste 20 (a) 1.237 → 1.207,
(b) 1.034 → 1.004, Zufallsstichprobe (b) 781 → 656) – u. a., weil nicht abgesicherte Vergleiche nichts mehr ersetzen; die
Vergleichskurse sind neu abgerufen, andere Gründe sind deshalb nicht ausgeschlossen.

**Die vier geänderten Spitzenreiter** – dieselben in (b), (b)+(c) und (b)+(c)+(d), Werte wie in der App (Score =
w/100 · Perzentil des R² + (1 − w/100) · Perzentil der Rendite in der Vergleichsmenge):

| Rangliste | bisher → neu | bisheriger Spitzenreiter (vorher → nachher) | neuer Spitzenreiter (vorher → nachher) | Auslöser |
|---|---|---|---|---|
| 33, 34 und 35 Tage, Gruppe A, 10/90 (drei Ranglisten) | Z36 → Z33 (vorher Platz 2) | Z36: Rendite +50,16 %, R² 0,92909, Score 99,027 (Perzentil Rendite 99,010, R² 99,180) – unverändert | Z33: Rendite +66,40 %, R² 0,86912 – unverändert; Score 99,010 → **99,040** (Perzentil Rendite 99,488 → 99,522, R² 94,706) | Z31 allein |
| 45 Tage, Gruppe A, 80/20 | I → Z38 (vorher Platz 2) | I: Rendite +76,26 %, R² 0,93406 → 0,93403, Score 99,559 → 99,559 (Perzentil Rendite 99,213, R² 99,646) | Z38: Rendite +56,53 %, R² 0,94632 – unverändert; Score 99,559 → **99,567** (Perzentil Rendite 98,426 → 98,465, R² 99,843) | Z31 allein |

Vergleichsmenge 2.929 (33–35 Tage) bzw. 2.542 Aktien (45 Tage), vorher und nachher gleich. **Wirkung über die Ränge:** Die
Spitzenreiter selbst ändern sich kaum (I nur im R², durch 2 eigene NOCP-Tage); es ändert sich Z31 – mit dem offiziellen
Schlusskurs sinkt seine Rendite über 33–35 Tage von +73,10 % auf +66,38 % (vorher über beiden Spitzenreitern, danach zwischen
ihnen) und über 45 Tage von +59,12 % auf +56,03 % (vorher zwischen, danach unter beiden; R² 0,7826 → 0,74144 bzw. 0,76775 →
0,75412, jeweils unter beiden). Damit steigt das Perzentil der Rendite des neuen Spitzenreiters und sein Score über den des
bisherigen. **Z31:** Nasdaq-notiert, 1–10 $, bester Platz 7 (24 Tage, A, 0/100), unter den ersten 10 in 3 Ranglisten; der Stand weicht an
47 Tagen vom NOCP ab (von der Nasdaq-Historie an 15) –
im Zeitraum u. a. am 22.09. um −6,918 % (Stand, Nasdaq-Historie und NOCP verschieden), am 21.09. um −2,564 % (Stand = letzte
Minutenkerze, plausibel), am 18.09. um −0,040 % (Nasdaq-Historie = NOCP): **festgestellte Abweichungen, keine belegte
Ursache**. **Z33** (neuer Spitzenreiter in drei Ranglisten) ist eine Aktie der Börse Warschau ohne Vergleichskurse (bei CNBC
nicht gefunden) – ihre eigenen Kurse sind ungeprüft. **Z38** (XLON; unter den ersten 10 in 428 Ranglisten, Platz 1 in 164) ist mit CNBC abgesichert verglichen, 0 abweichende Tage;
die bisherigen Spitzenreiter Z36 und I (beide Nasdaq) weichen an 3 bzw. 2 Tagen vom NOCP ab.
Ebenso mit den Kursen des Jobs „erste 10“ allein (dort Buchstaben D → Z42 und B → Z45, Auslöser P).

**Punkt 1 – nicht gezeigt:** eine gemeinsame Rechnung mit Kursen, deren Zuordnung nicht abgesichert ist (sie ersetzen
nichts); ob der Stand oder der NOCP an Z31s Tagen den richtigen Schlusskurs trägt – der NOCP ist nach Nasdaq-Regel der
offizielle Schlusskurs, die Ursache des Unterschieds ist aber nicht belegt.

##### Punkt 2 – Ursachen streng nach Beleglage

Belegt ist eine Ursache nur, wenn ein gemeldetes Ereignis zeigt, wodurch der Unterschied entsteht (Split passenden
Verhältnisses bzw. Dividende nach dem Tag). Gleicher Kurs wie die letzte Minutenkerze vor 16:00 Uhr, ein Abstand unter einer
Kursstufe, gemeldeter Umsatz 0 mit dem Kurs des Vortags oder ein Faktor ohne gemeldeten Split sind **plausible
Erklärungen** – die Abweichung bleibt ungeklärt. Je Vergleich (Tage, nur abgesicherte Vergleiche; Summe der vier Prüfjobs,
im Job „gemeinsame Wirkung“ gleich ausgewiesen):

| Ergebnisart | gegen die Nasdaq-Historie | gegen den offiziellen Schlusskurs (NOCP) | gegen CNBC (US-Aktien ohne Nasdaq-Kurse) | gegen CNBC (außerhalb der US-Auswahl) |
|---|---|---|---|---|
| bestätigte Übereinstimmung | 24.036 | 11.818 | 1.620 | 7.915 |
| festgestellte Abweichung | 597 | 393 | 265 | 67 |
| – Ursache belegt | 0 | **34** (NOCP unbereinigt vor einem gemeldeten Split passenden Verhältnisses – nicht ersetzt) | 0 | 0 |
| – ungeklärt mit plausibler Erklärung | 45: Stand = letzte Minutenkerze 11, Nasdaq-Historie = letzte Minutenkerze 28, Umsatz 0 6 | 40: Stand = letzte Minutenkerze | 2: Abstand unter einer Kursstufe | 1: Umsatz 0 |
| – ungeklärt ohne Erklärung | 552: Befund „Nasdaq-Historie = NOCP, Stand nicht“ 226; ohne Befund 326 | 319: Befund Nasdaq-Historie = NOCP 228, Nasdaq-Historie = Stand 72, drei verschiedene Kurse 19 | 263 | 66 |
| fehlende Prüfmöglichkeit (Aktien; darin die nicht abgesicherten) | 47 ohne abgesicherte Nasdaq-Historie: 38 ohne Nasdaq-Kurse, 9 nicht abgesichert; 0 Tage nur im Stand | 227 ohne abgesicherten NOCP: nicht Nasdaq-notiert 180 (offizieller Schlusskurs der NYSE-Gruppe nur kostenpflichtig), ohne Nasdaq-Kurse 38, nicht abgesichert 9; 12.422 Tage der Aktien mit abgesichertem Nasdaq-Vergleich ohne NOCP | 8 ohne abgesicherte Vergleichskurse: 4 ohne Vergleichskurse, 4 nicht abgesichert; 185 Tage nur im Stand (an allen bei Yahoo ohne Umsatz) | 38 ohne abgesicherte Vergleichskurse: 30 bei CNBC nicht gefunden, 8 nicht abgesichert; 149 Tage nur im Stand |
| davon nicht ausreichend abgesichert (weder Bestätigung noch Ursache noch Ersatzkurs) | 9 Aktien, 606 Tage | 8 Aktien mit NOCP, 496 Tage | 4 Aktien, 30 Tage | 8 Aktien, 504 Tage |

Alle 597 abweichenden Tage gegen die Nasdaq-Historie (die 45 plausiblen eingeschlossen) nach Prüfgrenze bzw. Befund:
Prüfgrenze Heimatbörse der NYSE-Gruppe oder Cboe (offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar;
NYSE: nur im kostenpflichtigen Produkt „TAQ NYSE Closing Prices“) 341, Nasdaq-notiert mit Nasdaq-Historie = NOCP, Stand nicht 236, Nasdaq-notiert mit drei
verschiedenen Kursen 20. Die 326 Tage „ohne Befund“ sind Tage der Prüfgrenze und der drei verschiedenen Kurse ohne plausible
Erklärung – eine Prüfgrenze erklärt, warum kein Beleg möglich war, nicht die Abweichung.

**Überlappende Fälle nicht doppelt:** Nasdaq-Historie und NOCP vergleichen dieselben Aktientage. Je Aktie und Tag genau einmal
(maßgeblich der abgesicherte NOCP, sonst die Nasdaq-Historie): **24.633** verglichene Aktientage – bestätigte Übereinstimmung
23.899, belegt 34, plausibel 71, ohne Erklärung 629; davon in beiden Vergleichen abweichend 256, nur in der Nasdaq-Historie
341, nur im NOCP 137. Mit CNBC für US-Aktien ohne Nasdaq-Kurse (1.885 Aktientage anderer Aktien) und CNBC außerhalb der
US-Auswahl (7.982): **34.500 Aktientage, 1.066 eindeutige abweichende – belegt 34, ungeklärt 1.032** (plausibel 74, ohne
Erklärung 958). Je Job: erste 10 451 (belegt 18, plausibel 45), Plätze 11–20 94 (0, 4), Zufallsstichprobe 454 (16, 24),
außerhalb der US-Auswahl 67 (0, 1).

**Die bisher als belegt gezählten 49, 56 und 2 Fälle (Lauf 40162120622) – abgestimmt, keiner ist belegt:**

| bisher „belegt“ | jetzt in abgesicherten Vergleichen | jetzt in nicht abgesicherten Vergleichen (nur gezählt) | zusammen |
|---|---|---|---|
| Nasdaq-Historie 49: Stand = letzter Abschluss vor 16:00 Uhr 12, Nasdaq-Historie = letzter Abschluss 31, kein Umsatz 6 | **plausibel** 11 + 28 + 6 = 45 | 1 + 3 + 0 = 4 | 12 + 31 + 6 = **49** |
| NOCP 56: Stand = letzter Abschluss vor 16:00 Uhr | **plausibel** 40 | 16 | **56** |
| CNBC 2: Stand zwischen zwei Kursstufen | **plausibel** 2 | – | **2** |

Ebenso vollständig abgestimmt: gegen die Nasdaq-Historie damals 630 abweichende Tage = jetzt 597 (abgesichert) + 33 (nicht
abgesichert); gegen den NOCP damals 441 = jetzt 393 − 34 Split-Tage (damals „Faktor eines Splits – keine Abweichung“, jetzt
**belegt** mit gemeldetem Split) + 82 (nicht abgesichert); gegen CNBC 265 = 265. Die damals 581 bzw. 385 ungeklärten Tage
sind jetzt 552 + 29 bzw. 319 + 66 (Befunde in nicht abgesicherten Vergleichen). Die 49 + 56 + 2 = 107 Fälle waren keine
unabhängigen Fälle: Je Aktie und Tag genau einmal (Regel: maßgeblich der abgesicherte NOCP, sonst die Nasdaq-Historie) sind es
in den abgesicherten Vergleichen 71 + 2 (CNBC) plausible Aktientage statt 45 + 40 + 2 – die Differenz enthält Tage, die in
beiden Vergleichen plausibel sind, und solche, die nach dem NOCP ohne Erklärung bleiben; die nicht abgesicherten sind je
Vergleich gezählt.

##### Punkt 3 – Zuordnung der Vergleichskurse

Geprüft wird jede Zuordnung einzeln; **jede Prüfung muss bestanden sein**, eine fehlende Angabe gilt nie als bestanden.
*Aktie und Gattung:* ISIN des Stands → Notierungen laut OpenFIGI (je ISIN live abgefragt) – das abgefragte Kürzel gehört zu
dieser ISIN an einer Börse derselben Gruppe, in der Schreibweise der App oder einer ihrer dokumentierten anderen
Schreibweisen (nordische Gattungen); jede Gattung hat eine eigene ISIN. *Name und Art:* Name der Quelle (Wertpapierliste
„nasdaqtraded.txt“ von Nasdaq Trader bzw. Kursmeldung von CNBC) ähnlich dem Namen im Stand (mindestens 0,5); kein Fonds, Testwert,
Optionsschein, Bezugsrecht, keine Einheit oder Anleihe. *Notierung und Handelsplatz:* Börse laut Quelle = Börse der Kurse des
Stands (der offizielle Schlusskurs NOCP nur bei Nasdaq-notierten Aktien). *Währung* angegeben und gleich (GBp/GBP über die
Untereinheiten). *Handelstag* ohne Versatz (−1, 0, +1 geprüft). *Bereinigung* wie im Stand (ein Faktor nur mit gemeldetem
Split). *Kursniveau* Stand/Quelle im Median innerhalb von 2 %. *Tage:* mindestens 10 gemeinsame.

| Quelle | abgesichert | nicht bestanden (Zahl der Prüfungen; eine Aktie kann mehrere nicht bestehen) |
|---|---|---|
| OpenFIGI je ISIN (Abfrage) | Antwort mit Notierungen 554 von 560 | ISIN bei OpenFIGI unbekannt 3, Datensätze ohne Notierung an einer Börse der App 3 |
| Nasdaq-Historie | **357 von 366** | Aktie und Gattung 6 (die 6 ISINs oben), Art 2 (Optionsschein, Bezugsrecht, Einheit oder Anleihe laut Name), Name 1 |
| offizieller Schlusskurs NOCP | **177 von 185** | Aktie und Gattung 6, Art 2 |
| CNBC (US-Aktien ohne Nasdaq-Kurse) | **30 von 34** | mindestens 10 gemeinsame Tage 3, Börse 2, Kursniveau 1 |
| CNBC (außerhalb der US-Auswahl) | **118 von 126** | Kursniveau 4, Börse 3, Name 2, Aktie und Gattung 1 (OpenFIGI nennt für die ISIN an der LSE ein anderes Kürzel), Bereinigung 1, Währung 1; Kürzel in dokumentierter Schreibweise der App bestätigt (bestanden) 4 |

**Befunde der nicht abgesicherten Zuordnungen mit Plätzen unter den ersten 10** (Codes und Zahlen aus dem Lauf; Buchstaben
des Jobs „gemeinsame Wirkung“, in der App über die Fundstelle nachzusehen):

| Buchstabe | Börse, Kursbereich | Plätze unter den ersten 10 / Platz 1 | nicht bestanden | Befund |
|---|---|---|---|---|
| Z149 | XTSX, unter 1 (Landeswährung) | 97 / **22** | Kursniveau | Stand/CNBC im Median 1,059 (erlaubt 0,98 bis 1,02) – Name, Börse, Währung, Handelstag, Bereinigung und Tage bestanden; ob Stand oder CNBC abweicht, ist ohne dritte Quelle nicht zu entscheiden |
| Z152 | XLON, über 100 (Landeswährung) | 85 / 0 | Aktie und Gattung | OpenFIGI nennt für die ISIN an der LSE ein anderes Kürzel als die App (ISIN-Prüfziffer gültig, Land GB); Name, Börse, Kursniveau bestanden – ob die App die Gattung der ISIN führt, ist nicht belegt (in der App über die Fundstelle nachzusehen) |
| Z154 | Nasdaq, 10–100 $ | 40 / 0 | Aktie und Gattung | ISIN bei OpenFIGI unbekannt (Prüfziffer gültig, Land US) |
| Z161 | NYSE American, 10–100 $ | 14 / 0 | Name | Ähnlichkeit des Namens 0,25 (verlangt mindestens 0,5) |
| Z163 | XCNQ, unter 1 (Landeswährung) | 10 / 0 | Börse | CNBC führt das Kürzel an der TSX Venture, die App an der CSE – andere Notierung |
| Z165 | Nasdaq, 1–10 $ | 6 / 0 | Aktie und Gattung | OpenFIGI nennt die ISIN nur mit Börsencodes ER und X2 – keiner an einer Börse der App (Prüfziffer gültig, Land US) |
| Z166 | Nasdaq, 1–10 $ | 6 / 0 | Aktie und Gattung | ISIN bei OpenFIGI unbekannt (Prüfziffer gültig, Land US) |
| Z167 | XETR, über 100 (Landeswährung) | 5 / 0 | Name | Ähnlichkeit des Namens 0,25 |
| Z168 | XPAR, unter 1 (Landeswährung) | 4 / 0 | Kursniveau | im Median 1,094 |
| Z173 | XMAD, 10–100 (Landeswährung) | 2 / 0 | Börse | Börse der Kursmeldung nicht zuordenbar |
| Z175 | XTSX, unter 1 (Landeswährung) | 1 / 0 | Kursniveau | im Median 1,200 |
| Z178 | XHKG, 10–100 (Landeswährung) | 1 / 0 | Name, Börse, Währung, Bereinigung, Kursniveau | Ähnlichkeit 0,00, Währung laut CNBC USD, Kursniveau im Median 0,223 – kein Merkmal passt; ob CNBC unter dem Kürzel ein anderes Wertpapier führt, ist nicht belegt |

Ohne Platz unter den ersten 10 nicht abgesichert: 5 Nasdaq-Aktien der Zufallsstichprobe (2 laut Name bei Nasdaq Trader
Optionsschein, Bezugsrecht, Einheit oder Anleihe; eine ISIN bei OpenFIGI unbekannt; eine nur mit Börsencodes X2 und XE; eine
nur als Vorzugsaktie – Sektor „Pfd“ – an Nasdaq) und 4 OTC-Aktien (CNBC ohne Börse oder mit 0 bis 2 gemeinsamen Tagen).

**Nicht ausreichend abgesichert heißt:** weder Ersatzkurs noch bestätigte Übereinstimmung noch Ursache; die Kurse dieser
Aktien bleiben in allen Varianten unverändert, ihre Tage zählen nur in der Abstimmung (Punkt 2). Ergänzende Belege
beschafft: für jede ISIN die Antwort von OpenFIGI, die Wertpapierliste von Nasdaq Trader (14.246 Einträge), die Kursmeldung
von CNBC mit Name, Börse und Währung, Yahoo-Tageskurse für Bereinigung und Splits. Eine weitere Quelle, die ISIN und Kurs
zusammen nennt, ist für diese Aktien in den geprüften Quellen nicht gefunden.

##### Punkt 4 – „lastTradeTime“ bei OTC Markets

*Dokumentation:* In den frei zugänglichen Unterlagen von OTC Markets ist das Feld nicht beschrieben: Die Spezifikation der
Tagesdatei „EOD Pricing“ ([EOD Pricing Specification](https://www.otcmarkets.com/files/EOD_Pricing_Specification.pdf),
Version 1.9, Mai 2025) kennt nur „Price Last – Closing Price (last sale) for security for trading day“, ohne Datum oder Uhrzeit
des Abschlusses (die Dateien entstehen gegen 16:15 und 21:15 Uhr Ostküstenzeit, die zweite mit Stornos und Korrekturen des
Tages); die Spezifikation „OTCHistoryFile“ ([Version 2.3](https://www.otcmarkets.com/files/OTCHistoryFile_Specification_v2.3.pdf),
September 2023) beschreibt nur Kursstellungen (Zeitstempel auf die Millisekunde, Zeitzone nicht genannt). Die Schnittstelle der
Website, aus der „lastTradeTime“ stammt, ist nicht dokumentiert.

*Beobachtungen* (Lauf 40188406664, 38 US-Aktien ohne Nasdaq-Kurse: Kursmeldung mit Zeitstempel 25, mit nicht lesbarem Stempel
– Zahl außerhalb des Bereichs – 7, ohne Kursmeldung 6): Einheit Millisekunden bei allen 25. **Genau 00:00:00.000 Uhr UTC: 0 von
25** – die frühere Angabe „alle 25 Zeitstempel um 0 Uhr UTC“ zählte nur die Stunde; die im Auftrag genannten „25 Zeitstempel
exakt um 00:00 UTC“ gibt es nicht. Alle 25 liegen in der Stunde 00 UTC, Minute 06 bis 15, Sekunde 00, mit Bruchteil der
Sekunde – das entspricht 20:06 bis 20:15 Uhr New York am Freitag, 23.10. Als UTC-Datum fiele jeder Stempel auf Samstag, 24.10.
(kein Handelstag, bei Yahoo ohne Eintrag), nach Ortszeit New York auf den letzten Kurstag des Stands (bei Yahoo mit Umsatz).
`quoteTime` der Antwort minus Stempel: unter 1 Stunde bei allen 25; Abruf nach der Uhr des Prüfrechners minus Stempel: 24 bis
72 Stunden. `lastSale` = letzter Kurs des Stands bei 22 von 25, `previousClose` = vorletzter Kurs des Stands bei 22 von 25
(= letzter Kurs bei 2).

*Folgerung:* Ein kodiertes Tagesdatum (Mitternacht) liegt nicht vor. Dass alle 25 Stempel die Sekunde 00 mit Bruchteil in
einem Fenster von zehn Minuten nach 20 Uhr New York tragen, ist mit einzelnen Abschlusszeitpunkten ebenso vereinbar wie mit
dem Zeitpunkt einer Verarbeitung – **belegt ist keine der Deutungen**. Der Handelstag wird daraus **nicht** abgeleitet, auch
nicht aus der besser zum Stand passenden Umrechnung: Die Zuordnung bleibt **offen**, der letzte Abschluss bei OTC Markets ist
weder Vergleichskurs noch zweite Quelle. *Der Widerspruch im Bericht vom 25.10., 05:50 Uhr* („drei OTC-Bestätigungen
zugunsten von CNBC“ und zugleich „für die ungeklärten CNBC-Tage keine zweite Quelle“): Die drei „Bestätigungen“ beruhten auf
einer Tageszuordnung, die nur gewählt war, weil sie zum Stand passte (Commit `88d2733`) – also auf keinem Beleg; eine zweite
Quelle waren sie nicht. Seit `438b2e1` zählt der OTC-Abschluss nicht mehr als Quelle; an keinem der 265 von CNBC abweichenden
Tage gibt es eine zweite abgesicherte Quelle – der Widerspruch ist aufgelöst.

##### Punkt 5 – kleinste Auslösermenge

*Bis `88d2733`:* einzelne Aktien, dann schrittweise hinzunehmen und weglassen – das findet die kleinste Menge im Allgemeinen
nicht (Gegenbeispiel im Unit-Test `test_exact_search_finds_a_smaller_set_than_adding_and_removing`: das schrittweise Verfahren
endet bei drei Aktien, zwei reichen), und die Kandidaten waren still auf 40 begrenzt. *Seit `438b2e1`:* Teilmengen der im
Zeitraum ersetzten Aktien nach Größe, jede Größe vollständig (k = 1, 2, …), bis eine Teilmenge diesen neuen Platz 1 ergibt –
dann ist sie **nachweislich** die kleinste, weil jede kleinere geprüft ist (die leere Menge ergibt den bisherigen Platz 1);
Grenze 60.000 Auswertungen je Rangliste – reicht sie nicht, wird eine irreduzible Menge genannt (ohne jede ihrer Aktien kein
Wechsel) mit der geprüften Größe als Untergrenze („mindestens k“, ausdrücklich nicht „kleinste“). *Seit `2fc32d3`:*
Gegenprobe mit der **unabhängigen Rechnung** der Nachrechnung, bei Auslösermenge 1 jede einzelne ersetzte Aktie zusätzlich
unabhängig.

**Die vier Wechsel durch Z31 erneut bestätigt** (Lauf 40188406664): In allen vier Ranglisten und allen drei Varianten ist die kleinste
Auslösermenge **{Z31}** – nachweislich: jede einzelne der im Zeitraum ersetzten Aktien geprüft ((b) 32 bzw. 38, (b)+(c) 41 bzw.
50, (b)+(c)+(d) 46 bzw. 55 für 33–35 bzw. 45 Tage), nur Z31 allein ergibt den neuen Platz 1; die Grenze von 60.000
Auswertungen wurde nicht erreicht. **Gegenprobe mit der unabhängigen Rechnung:** Z31 allein → neuer Spitzenreiter (Z33 bzw.
Z38, wie mit allen ersetzten Kursen); alle übrigen ersetzten Kurse ohne Z31 → bisheriger Spitzenreiter (Z36 bzw. I) – ohne Z31
kein Wechsel; jede einzelne ersetzte Aktie auch unabhängig gerechnet: allein ausreichend nur Z31 – in allen zwölf Fällen „wie
die Suche“, keine Abweichung. Ebenso im Job „erste 10“ allein (dort heißt Z31 „P“: 14 bzw. 17 ersetzte Aktien, gleiches
Ergebnis).

##### Punkt 6 – Abdeckung des ganzen Aktienuniversums

**Universum:** 11.596 Aktien (TR-Liste, im täglichen Lauf vom 25.10. unverändert bestätigt). Ausgewählt **560**: 404 US-Aktien
(254 unter den ersten 20 einer Rangliste, 150 zufällig) und alle **156** Aktien außerhalb der USA mit mindestens einem Platz
unter den ersten 10 – darunter alle bislang ungeprüften Aktien mit Top-10-Platzierungen. **Abgesichert verglichen 505**,
nicht ausreichend abgesichert 21, ohne Vergleichskurse in den geprüften Quellen 34, ohne Antwort 0; nicht ausgewählt 11.036
(598 davon ohne Kursreihe). **Tage** im Prüfzeitraum 31.05.–23.10.2026: im Stand 750.366, abgesichert verglichen 34.500
(**4,6 %**). **Ranglisten:** 1.640 mit Einträgen; Plätze unter den ersten 10 16.400, davon bei Aktien mit abgesichertem
Vergleich **14.564 (88,8 %)**; Platz 1 bei **1.599 von 1.640 (97,5 %)**; Ranglisten mit allen ersten 10 abgesichert 521, mit
mehr als der Hälfte 1.116, mit höchstens der Hälfte 3, mit keiner 0. Eine Prüfung einzelner Tage gegen eine Quelle ist
**keine Vollprüfung** – Tage ohne Vergleich und nicht abgesicherte Aktien bleiben ungeprüft.

| Gruppe | Aktien | abgesichert verglichen | nicht ausreichend abgesichert | ohne Vergleichskurse |
|---|---|---|---|---|
| erste 10 (US) | 157 | 153 (Nasdaq 143 – davon mit NOCP 76 –, CNBC 10) | 4 | 0 |
| Plätze 11–20 (US) | 97 | 97 (Nasdaq 92 – mit NOCP 52 –, CNBC 5) | 0 | 0 |
| Zufallsstichprobe (US) | 150 | 137 (Nasdaq 122 – mit NOCP 49 –, CNBC 15) | 9 (Nasdaq 5, CNBC 4) | 4 |
| außerhalb der US-Auswahl (unter den ersten 10) | 156 | 118 (CNBC) | 8 | 30 |
| zusammen | 560 | 505 | 21 | 34 |

**Je Börse** (alle Aktien des Universums; Plätze in Klammern: davon bei Aktien mit abgesichertem Vergleich):

| Börse | Aktien im Universum | ausgewählt: abgesichert / nicht abgesichert / ohne Vergleichskurse | Plätze unter den ersten 10 | Plätze 1 | Tage im Stand / abgesichert verglichen |
|---|---|---|---|---|---|
| US (zusammengefasst) | 3.613 | 387 / 7 / 4 | 9.191 (9.177) | 1.111 (1.111) | 246.285 / 26.518 (10,8 %) |
| XNAS (in der App eigens geführt) | 32 | 0 / 6 / 0 | 52 (0) | 0 | 2.080 / 0 |
| XLON | 774 | 35 / 1 / 0 | 2.218 (2.133) | 354 (354) | 48.464 / 2.405 (5,0 %) |
| XWAR | 218 | 0 / 0 / 6 | 640 (0) | 16 (0) | 15.260 / 0 |
| XETR | 447 | 14 / 1 / 0 | 609 (604) | 5 (5) | 30.185 / 980 (3,2 %) |
| XTSE | 496 | 12 / 0 / 0 | 501 (501) | 1 (1) | 33.119 / 804 (2,4 %) |
| XSWX | 187 | 3 / 0 / 3 | 471 (184) | 1 (0) | 12.280 / 210 (1,7 %) |
| XASX | 528 | 9 / 0 / 0 | 435 (435) | 49 (49) | 36.741 / 581 (1,6 %) |
| XHKG | 734 | 8 / 1 / 0 | 382 (381) | 34 (34) | 49.816 / 544 (1,1 %) |
| XTSX | 580 | 5 / 2 / 0 | 354 (256) | 34 (12) | 38.386 / 278 (0,7 %) |
| XSTO | 326 | 8 / 0 / 0 | 264 (264) | 0 | 22.820 / 560 (2,5 %) |
| XTKS | 618 | 4 / 0 / 6 | 238 (153) | 9 (9) | 39.488 / 256 (0,6 %) |
| XJSE | 69 | 0 / 0 / 1 | 186 (0) | 0 | 4.692 / 0 |
| XWBO | 58 | 0 / 0 / 2 | 186 (0) | 1 (0) | 3.850 / 0 |
| XAMS | 77 | 2 / 0 / 0 | 176 (176) | 21 (21) | 5.249 / 140 (2,7 %) |
| XPAR | 514 | 10 / 1 / 0 | 152 (148) | 2 (2) | 35.792 / 668 (1,9 %) |
| XCSE | 70 | 0 / 0 / 4 | 142 (0) | 0 | 4.690 / 0 |
| BVMF | 10 | 1 / 0 / 0 | 71 (71) | 0 | 680 / 68 (10,0 %) |
| XMIL | 198 | 2 / 0 / 0 | 35 (35) | 0 | 13.767 / 140 (1,0 %) |
| XCNQ | 341 | 0 / 1 / 6 | 26 (0) | 1 (0) | 22.615 / 0 |
| XOSL, XIDX, XBRU, XFRA, XMAD, ASEX | 207, 79, 95, 232, 117, 101 | XOSL 1/0/0, XIDX 0/0/2, XBRU 2/0/0, XFRA 1/0/0, XMAD 0/1/0, ASEX 1/0/0 | 23 (23), 23 (0), 17 (17), 5 (5), 2 (0), 1 (1) | XFRA 1 (1) | 14.488 / 70, 5.372 / 0, 6.488 / 140, 15.209 / 70, 8.119 / 0, 7.070 / 68 |
| ohne Platz unter den ersten 10: XHEL 140, XSES 82, XBKK 43, XMEX 37, XLIS 27, XDUB 18, XNZE 18, XTAL 16, XTAE 14, XBUD 11, OTC 7, XPRA 7, XASE 2, ARCX 1, XSHE 1; ohne Börse 451 (ohne Kurstage im Stand) | 875 | nicht ausgewählt | 0 | 0 | 27.361 / 0 |

**Lücken – Ranglisten mit ungeprüftem Platz 1 (41 von 1.640, alle außerhalb der USA):**

| Aktie | Börse, Zustand | Ranglisten mit diesem Platz 1 (Tage/Gruppe/Gewichtung der Gleichmäßigkeit) |
|---|---|---|
| Z149 | XTSX, nicht abgesichert (Kursniveau 1,059) | 22: 58/A/10, 58/A/20, 64/A/10–30, 65/A/10–40, 66/A/10–40, 67/A/10–40, 71/A/10–50 |
| Z44 | XWAR, ohne Vergleichskurse | 13: 52–57/B/80 und /90, 59/B/90 |
| Z33 | XWAR, ohne Vergleichskurse | 3: 30, 31, 32/A/10 |
| Z64, Z148, Z150 | XSWX, XCNQ, XWBO – ohne Vergleichskurse | je 1: 58/B/90, 8/A/0, 71/B/100 |

**Lücken je Aktie (55 ausgewählte ohne abgesicherten Vergleich, Grund und Befund je Buchstabe im Job):** Je Grund: bei CNBC unter keiner geprüften Schreibweise gefunden 30 (XWAR 6 mit 640 Plätzen
unter den ersten 10 und 16 Plätzen 1, XSWX 3 mit 287 und 1, XJSE 1 mit 186, XWBO 2 mit 186 und 1, XCSE 4 mit 142, XTKS 6 mit 85,
XIDX 2 mit 23, XCNQ 6 mit 16 und 1); Nasdaq-Kurse, Zuordnung nicht ausreichend abgesichert 9 (66 Plätze); CNBC-Kurse außerhalb der
US-Auswahl, nicht ausreichend abgesichert 8 (205 Plätze, 22 Plätze 1); OTC ohne Vergleichskurse 4 und mit nicht abgesicherten CNBC-Kursen 4
(in keiner Rangliste). Zusammen **1.836 Plätze unter den ersten 10 und 41 Plätze 1** ohne abgesicherten Vergleich der Aktie,
**3.689 Kurstage** dieser Aktien ungeprüft. Die 42 Aktien mit Platz unter den ersten 10 einzeln (Buchstaben des Jobs
„gemeinsame Wirkung“ in Lauf 40188406664, in Lauf 40192915763 dieselben; in der App über die Fundstelle im Job nachzusehen):

| Buchstabe | Börse, Kursbereich | Plätze unter den ersten 10 / Platz 1 | ungeprüfte Tage | Zustand (nicht bestandene Prüfung) | Befund |
|---|---|---|---|---|---|
| Z149 | XTSX, unter 1 (Landeswährung) | 97 / 22 | 67 | nicht abgesichert (Kursniveau) | Kursniveau Stand/Quelle im Median 1,059 (erlaubt 0,98 bis 1,02) |
| Z44 | XWAR, über 100 (Landeswährung) | 95 / 13 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z33 | XWAR, unter 1 (Landeswährung) | 38 / 3 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z64 | XSWX, über 100 (Landeswährung) | 83 / 1 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung CH) |
| Z150 | XWBO, 10–100 (Landeswährung) | 45 / 1 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung AT) |
| Z148 | XCNQ, unter 1 (Landeswährung) | 4 / 1 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| Z68 | XWAR, 10–100 (Landeswährung) | 368 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z70 | XJSE, über 100 (Landeswährung) | 186 / 0 | 68 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung ZA) |
| Z55 | XSWX, über 100 (Landeswährung) | 143 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung CH) |
| L | XWBO, 10–100 (Landeswährung) | 141 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung AT) |
| Z151 | XCSE, über 100 (Landeswährung) | 87 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung DK) |
| Z85 | XWAR, 1–10 (Landeswährung) | 86 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z152 | XLON, über 100 (Landeswährung) | 85 / 0 | 69 | nicht abgesichert (Aktie und Gattung) | OpenFIGI nennt für die ISIN an XLON ein anderes Kürzel (Prüfziffer der ISIN gültig, Land GB) |
| Z46 | XSWX, unter 1 (Landeswährung) | 61 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung CH) |
| Z153 | XTKS, über 100 (Landeswährung) | 53 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z154 | Nasdaq, 10–100 $ | 40 / 0 | 69 | nicht abgesichert (Aktie und Gattung) | ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN gültig, Land US) |
| Z155 | XCSE, über 100 (Landeswährung) | 31 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung DK) |
| Z156 | XWAR, über 100 (Landeswährung) | 31 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z157 | XCSE, über 100 (Landeswährung) | 22 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung DK) |
| Z158 | XIDX, über 100 (Landeswährung) | 22 / 0 | 68 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung ID) |
| Z159 | XWAR, 1–10 (Landeswährung) | 22 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung PL) |
| Z161 | NYSE American, 10–100 $ | 14 / 0 | 69 | nicht abgesichert (Name) | Ähnlichkeit des Namens 0,25 (verlangt mindestens 0,5) |
| Z160 | XTKS, über 100 (Landeswährung) | 14 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z162 | XTKS, über 100 (Landeswährung) | 11 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z163 | XCNQ, unter 1 (Landeswährung) | 10 / 0 | 67 | nicht abgesichert (Börse) | Börse laut Quelle XTSX, Kurse des Stands XCNQ |
| Z165 | Nasdaq, 1–10 $ | 6 / 0 | 65 | nicht abgesichert (Aktie und Gattung) | OpenFIGI nennt die ISIN nur mit Börsencodes ER, X2 (Sektor Equity) – keiner an einer Börse der App (Prüfziffer der ISIN gültig, Land US) |
| Z166 | Nasdaq, 1–10 $ | 6 / 0 | 69 | nicht abgesichert (Aktie und Gattung) | ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN gültig, Land US) |
| Z164 | XCNQ, 1–10 (Landeswährung) | 6 / 0 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| Z167 | XETR, über 100 (Landeswährung) | 5 / 0 | 70 | nicht abgesichert (Name) | Ähnlichkeit des Namens 0,25 (verlangt mindestens 0,5) |
| Z168 | XPAR, unter 1 (Landeswährung) | 4 / 0 | 70 | nicht abgesichert (Kursniveau) | Kursniveau Stand/Quelle im Median 1,094 (erlaubt 0,98 bis 1,02) |
| Z169 | XCNQ, unter 1 (Landeswährung) | 3 / 0 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| Z170 | XTKS, über 100 (Landeswährung) | 3 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z171 | XTKS, über 100 (Landeswährung) | 3 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z172 | XCSE, über 100 (Landeswährung) | 2 / 0 | 70 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung DK) |
| Z173 | XMAD, 10–100 (Landeswährung) | 2 / 0 | 70 | nicht abgesichert (Börse) | Börse laut Quelle nicht zuordenbar, Kurse des Stands XMAD |
| E | XCNQ, unter 1 (Landeswährung) | 1 / 0 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| F | XCNQ, unter 1 (Landeswährung) | 1 / 0 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| Z174 | XCNQ, unter 1 (Landeswährung) | 1 / 0 | 67 | ohne Vergleichskurse | bei CNBC unter 2 Schreibweisen des Kürzels gesucht (Endung CNX, CA) |
| Z178 | XHKG, 10–100 (Landeswährung) | 1 / 0 | 68 | nicht abgesichert (Name, Börse, Währung, Bereinigung, Kursniveau) | Ähnlichkeit des Namens 0,00 (verlangt mindestens 0,5); Börse laut Quelle nicht zuordenbar, Kurse des Stands XHKG; Währung laut Quelle USD; Bereinigung Faktor ohne gemeldeten Split; Kursniveau Stand/Quelle im Median 0,223 (erlaubt 0,98 bis 1,02) |
| Z176 | XIDX, über 100 (Landeswährung) | 1 / 0 | 68 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung ID) |
| Z177 | XTKS, über 100 (Landeswährung) | 1 / 0 | 64 | ohne Vergleichskurse | bei CNBC unter 1 Schreibweise des Kürzels gesucht (Endung JP) |
| Z175 | XTSX, unter 1 (Landeswährung) | 1 / 0 | 67 | nicht abgesichert (Kursniveau) | Kursniveau Stand/Quelle im Median 1,200 (erlaubt 0,98 bis 1,02) |

Ohne Platz unter den ersten 10 (13): die 5 Nasdaq- und 4 OTC-Aktien mit nicht abgesicherter Zuordnung (Punkt 3) und die 4
OTC-Aktien ohne Vergleichskurse (folgender Absatz).

**Die „sieben Aktien ohne Vergleichskurse“ (Lauf 40162120622):** alle OTC-Aktien der Zufallsstichprobe, **in keiner Rangliste
des Stands** – sie wirken auf keine Rangliste. Mit den geprüften Quellen: 4 weiter ohne Vergleichskurse (CNBC antwortet, aber ohne Kerzen im Zeitraum;
OTC Markets ohne Kurshistorie – HTTP 404 –, Barchart HTTP 403, MarketWatch HTTP 401, Stooq ohne Schlüssel HTML statt Daten –
seit März 2026 nur mit Schlüssel, [pandas-datareader #1012](https://github.com/pydata/pandas-datareader/issues/1012)), 3 mit CNBC-Kursen, aber
weniger als 10 gemeinsamen Tagen (nicht abgesichert); dazu eine vierte OTC-Aktie mit CNBC-Kursen, für die CNBC keine Börse
angibt (bis 40162120622 „vergleichbar“, jetzt nicht abgesichert).

**Zwei Wertpapiere des Universums** sind laut Name bei Nasdaq Trader keine Aktien (Optionsschein, Bezugsrecht, Einheit oder
Anleihe; Zufallsstichprobe, beste Plätze 2.143 bzw. 1.704 – ohne Platz unter den ersten 10): Vergleich nicht abgesichert. Ob
die App sie als Aktie führen sollte, ist eine Frage der TR-Liste, hier nicht geprüft.

**Nicht gezeigt bzw. offen:** welche Kurse an den 1.032 ungeklärten Aktientagen richtig sind; die 11.036 nicht ausgewählten
Aktien und die 55 ausgewählten ohne abgesicherten Vergleich (keine Vollprüfung); Tage außerhalb des Prüfzeitraums 31.05.–23.10.;
offizielle Schlusskurse der NYSE-Gruppe (nur kostenpflichtig); die Bedeutung von „lastTradeTime“ (nicht dokumentiert); weitere
Quellen für die 30 bei CNBC nicht gefundenen Aktien – für sie ist **nur CNBC** abgefragt (OTC Markets, Barchart, MarketWatch und
Stooq fragen nur die US-Jobs ab, für die 38 US-Aktien ohne Nasdaq-Kurse, und lieferten dort bei keiner Aktie Daten: HTTP 404,
403, 401 bzw. HTML statt Daten); Kursarchive der Börsen selbst (z. B. Warschau, Kopenhagen, Wien) sind nicht angebunden – ob
sie vom Prüfrechner aus zugänglich sind und ISIN und Schlusskurs je Tag nennen, ist nicht geprüft; Originaldaten – alle
Vergleichskurse sind nachträglich beschafft.

#### Gemeinsame Neuberechnung, Zusatzquellen und Ursachen neu eingeordnet (Auftrag vom 25.10.2026, 03:47 Uhr)

**In der Einordnung überholt (seit dem Auftrag vom 25.10.2026, 09:20 Uhr – Abschnitt oben):** Die Zahlen dieses Abschnitts
gelten als Ergebnis des Laufs 40162120622 weiter, ihre Einordnung nicht: (1) „Ursache belegt“ 49 (Nasdaq-Historie), 56 (NOCP)
und 2 (CNBC) sind nur **plausible Erklärungen** (letzte Minutenkerze, Kursstufe, Umsatz 0) – belegt ist keiner; (2) Vergleiche
ohne Prüfung der Wertpapieridentität (Nasdaq-Historie, NOCP) bzw. mit „nur Kürzel“ oder ohne Angabe von Börse oder Währung
(CNBC) gelten heute als nicht abgesichert; (3) der „richtige Handelstag“ des OTC-Abschlusses war nur die besser zum Stand
passende Umrechnung – die Bedeutung von „lastTradeTime“ ist nicht belegt, die drei „Bestätigungen zugunsten von CNBC“ sind
keine zweite Quelle; (4) „alle 25 Zeitstempel um 0 Uhr UTC“ zählte nur die Stunde – genau 00:00:00 Uhr war keiner; (5) die
Auslöser wurden schrittweise gesucht, nicht nachweislich als kleinste Menge; (6) geprüft war nur die US-Auswahl. Maßgeblich
ist der Abschnitt oben.

**Ergebnis** – [Lauf 40162120622](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622), 25.10.2026, 05:30–05:38 Uhr (MEZ), Commit `88d2733`,
Eingabe „ursachen_stand“ = `2026-10-23_3f7ce5f3`: drei Prüfjobs auf drei Rechnern
([erste 10](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622/job/121075682036), [Plätze 11–20](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622/job/121075681968), [Zufallsstichprobe](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622/job/121075681975))
und der Job [„Ursachen – gemeinsame Wirkung aller Gruppen“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40162120622/job/121076785177).
Dieselben Zahlen wie in den Läufen 40160248028 und 40161469772 (unten, „Läufe davor“); neu war der letzte Abschluss bei OTC Markets „am richtigen Handelstag“ (überholt: nicht belegt, oben Punkt 4). Alle vier Jobs rot („UNVOLLSTÄNDIG“) – nicht wegen des Abrufs (0 Aktien ohne Antwort, 0 fehlgeschlagene
Abrufe), sondern weil 7 Aktien in den geprüften Quellen keine Vergleichskurse haben und Abweichungen ohne belegte Ursache
bleiben. Alle Hinweise ausgegeben (14, 7, 11 und 15 Teile, vom letzten Hinweis jedes Jobs bestätigt). Im selben Lauf: App
`1.18.2+3a4bd974` mit echten Daten 11 Tests (10 bestanden, `test_2d` übersprungen), 24 von 24 Ansichten; Nachrechnung des
Stands 0 Abweichungen in 9.987.000 Prüfungen.

**Keine Vollprüfung:** Die **404 ausgewählten US-Aktien** – die US-Aktien unter den ersten 20 irgendeiner Rangliste (254)
und 150 zufällig gewählte – sind **keine Vollprüfung aller Aktien der App**. Von den 16.400 Plätzen unter den ersten 10 der
1.640 nicht leeren Ranglisten belegen US-Aktien 9.243; die übrigen 7.157 Plätze gehören Aktien außerhalb der USA, für die
diese Prüfung keine Vergleichsquelle hat – sie sind hier nicht geprüft, ebenso wenig die US-Aktien außerhalb der ersten 20
und der Stichprobe.

**1. Gemeinsame Neuberechnung.** *Warum nicht mit den Kursen von Lauf 40139805053 selbst – der technische Grund:* Der Lauf
hat keine Artefakte (`gh api …/actions/runs/40139805053/artifacts`: 0) – die Live-Prüfung lädt nichts hoch, das verlangt der
bestehende Sicherheitstest `test_live_app_check_runs_only_when_started_by_hand`; Protokoll und Hinweise enthalten nur
Zählwerte und Buchstaben. Die Vergleichskurse lagen nur im Speicher der zwei Rechner und sind mit dem Lauf verloren.
*Seitdem:* Jeder Prüfjob übergibt seine Ersatzkurse **verschlüsselt** (AES-256-GCM mit dem Schlüssel des Stands, an Stand
und Job gebunden) als Ausgabe des Jobs; der Job „gemeinsame Wirkung“ öffnet sie im einzigen Schritt mit dem Secret und
rechnet alle 1.980 Ranglisten neu. Im Protokoll steht je Job nur eine Prüfsumme der Ersatzkurse – in den Läufen
40160248028, 40161469772 und 40162120622 jeweils dieselbe (erste 10 `d04228ee54fcd5fd`, Plätze 11–20 `8414fb849411bd7c`,
Zufallsstichprobe `b581135783c1b723`): drei Abrufe, dieselben Kurse. Abgerufen sind sie mit derselben Auswahl gegen
denselben Stand (nachträglich, keine Originaldaten). *Dass sie denen von 40139805053 entsprechen, belegt der Job selbst:* Er
rechnet auch die damalige Aufteilung (erste 20 / Zufallsstichprobe) und vergleicht je Variante alle vier Zählwerte mit
jenem Lauf – **„dieselbe Wirkung“** (erste 20 und Zufallsstichprobe, je (a) und (b)); ebenso gleich: NOCP 12.232 von 12.707
Tagen gleich, 25.239 Börsentage verglichen, 630 abweichend. Belegt ist damit die gleiche Wirkung, nicht Kurs für Kurs
dieselben Werte – die Kurse von 40139805053 gibt es nicht mehr.

**Wirkung gemeinsam** – Kurse aller drei Jobs zugleich, die 1.640 nicht leeren von 1.980 Ranglisten neu gerechnet:

| Variante | Platz 1 anders | andere Aktien unter den ersten 10 | andere Reihenfolge der ersten 10 (einschl. anderer Aktien) | irgendeine Änderung |
|---|---|---|---|---|
| (a) Nasdaq-Historie an allen abweichenden Tagen (366 Aktien) | **0** | 2 | 14 | 1.295 |
| (b) offizieller Schlusskurs (NOCP) an allen Tagen, an denen er vom Stand abweicht (185 Nasdaq-notierte Aktien) | **4** | 6 | 33 | 1.184 |
| (c) Zusatzquelle CNBC an allen abweichenden Tagen (31 Aktien ohne Nasdaq-Kurse) | **0** | 1 | 3 | 831 |
| (a)+(c) alle Vergleichskurse (397 Aktien) | **0** | 3 | 17 | 1.296 |

Je Job allein zum Vergleich (Platz 1 / Aktien der ersten 10 / Reihenfolge / irgendeine Änderung):

| Job | (a) | (b) | (c) |
|---|---|---|---|
| erste 10 (157 Aktien) | 0 / 2 / 14 / 1.201 | 4 / 6 / 33 / 981 | 0 / 0 / 1 / 183 |
| Plätze 11–20 (97) | 0 / 0 / 0 / 477 | 0 / 0 / 0 / 315 | 0 / 0 / 0 / 400 |
| Zufallsstichprobe (150) | 0 / 0 / 0 / 842 | 0 / 0 / 0 / 781 | 0 / 1 / 2 / 820 |
| erste 20, Aufteilung wie in 40139805053 | 0 / 2 / 14 / 1.237 | 4 / 6 / 33 / 1.034 | – |

**Gemeinsame Effekte:** Gemeinsam entsteht **kein weiterer Platz 1** – alle vier neuen Plätze 1 entstehen ebenso mit den
Kursen des Jobs „erste 10“ allein; „nur gemeinsam anders“ und „nur in einem Job allein anders“: keine. Unter den ersten 10
ist die gemeinsame Wirkung genau die Vereinigung der Wirkungen je Job ((a)+(c): 2 + 1 Ranglisten mit anderen Aktien,
14 + 3 mit anderer Reihenfolge, dieselben Ranglisten und Plätze) – keine Wirkung hebt sich auf, keine entsteht erst
zusammen. Nur unterhalb der ersten 10 überlagern sich die Jobs (irgendeine Änderung gemeinsam 1.295 statt 1.201 mit dem
Job „erste 10“ allein).

**Jede Rangliste mit neuem Platz 1** – nur in Variante (b); Buchstaben des gemeinsamen Jobs (Zuordnung unten); Abweichung =
Stand gegenüber dem NOCP; Score wie in der App (Score = w/100 · Perzentil des R² + (1 − w/100) · Perzentil der Rendite in
der Vergleichsmenge; die App zeigt eine Nachkommastelle, hier drei):

| # | Rangliste | bisher → neu | Rendite und R² (vorher → nachher) | Score (Perzentil der Rendite / des R²) | Auslöser und auslösende Kursänderungen | ohne Auslöser / je Job |
|---|---|---|---|---|---|---|
| 1–3 | [33](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=33&w=10&p=native&n=10), [34](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=34&w=10&p=native&n=10) und [35 Tage](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=35&w=10&p=native&n=10), Gruppe A, Gewichtung 10/90 (Gleichmäßigkeit 10 %, Rendite 90 %); Zeitraum jeweils ab 18.09.; Vergleichsmenge 2.929 Aktien | Z36 → Z33 (vorher Platz 2) | Z36 +50,16 %, R² 0,92909 – unverändert; Z33 +66,40 %, R² 0,86912 – unverändert | Z36 99,027 → 99,027 (99,010 / 99,180); Z33 99,010 → **99,040** (99,488 → 99,522 / 94,706) | **Z31 allein:** Rendite +73,10 % → +66,38 % (vorher über beiden Spitzenreitern, nachher zwischen ihnen – 0,02 Prozentpunkte unter Z33), R² 0,7826 → 0,74144 (vorher und nachher unter beiden); 15 ersetzte Tage: 18.09. −0,04 % (Nasdaq-Historie = NOCP), 21.09. −2,56 % (Stand = letzter Abschluss), 22.09. −6,92 % und 23.09. +1,32 % (drei verschiedene Kurse), 24.09. +3,07 % und 25.09. +0,69 % (Nasdaq-Historie = Stand, NOCP anders), 05.10. −0,86 %, 06.10. −0,85 %, 09.10. −2,34 % und 13.10. −3,62 % (Stand = letzter Abschluss) und 5 weitere | mit den übrigen 35 ersetzten Aktien, ohne Z31: Platz 1 bleibt Z36; mit den Kursen des Jobs „erste 10“ allein derselbe Wechsel |
| 4 | [45 Tage](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=45&w=80&p=native&n=10), Gruppe A, Gewichtung 80/20 (Gleichmäßigkeit 80 %, Rendite 20 %); ab 08.09.; Vergleichsmenge 2.542 | I → Z38 (vorher Platz 2) | I +76,26 % unverändert, R² 0,93406 → 0,93403 (I mit ersetzten Kursen); Z38 +56,53 %, R² 0,94632 – unverändert | I 99,559 → 99,559 (99,213 / 99,646); Z38 99,559 → **99,567** (98,426 → 98,465 / 99,843) – vorher **exakt gleicher Score**, nach der Gleichstandsregel I mit der höheren Rendite vorn | **Z31 allein:** Rendite +59,12 % → +56,03 % (vorher zwischen I und Z38, nachher unter beiden), R² 0,76775 → 0,75412 (unter beiden); 23 ersetzte Tage: 08.09. +1,99 %, 09.09. −1,96 %, 10.09. −3,04 %, 11.09. +13,36 %, 14.09. −1,84 % und 16.09. +2,03 % (drei verschiedene Kurse), 15.09. −2,56 % (Nasdaq-Historie = Stand, NOCP anders), 17.09. −0,01 % und 21.09. −2,56 % (Stand = letzter Abschluss), 18.09. −0,04 % (Nasdaq-Historie = NOCP) und 13 weitere | mit den übrigen 40 ersetzten Aktien, ohne Z31: Platz 1 bleibt I; mit „erste 10“ allein derselbe Wechsel |

In Lauf 40139805053 hießen dieselben Aktien D → Z50 (33–35 Tage) und B → **Z53** (45 Tage), der Auslöser Q – zugeordnet über
dieselbe Fundstelle (Tabelle „Zuordnung“ unten und im Abschnitt dieses Laufs).

**Wodurch der Wechsel entsteht:** In gewichteten Ranglisten zählt nicht der Wert von Rendite und R², sondern ihr Rang in der
Vergleichsmenge. Die Spitzenreiter ändern ihre Werte nicht (I nur in der fünften Stelle des R², ohne Wirkung auf seinen
Rang); es ändert sich die Rendite von **Z31**. Bei 33–35 Tagen sinkt sie von +73,10 % auf +66,38 % und liegt damit
0,02 Prozentpunkte unter Z33: Z33 hat eine Aktie mehr unter sich (Perzentil der Rendite +100/2.928 = +0,034), sein Score
steigt um 0,9 · 0,034 = 0,031 auf 99,040 – über Z36 mit 99,027 (Abstand vorher 0,017). Bei 45 Tagen sinkt die Rendite von
Z31 von +59,12 % (zwischen I und Z38) auf +56,03 % (unter beiden): Z38 gewinnt einen Rang der Rendite (+0,039), sein Score
um 0,2 · 0,039 = 0,008. Dort hatten I und Z38 vorher **rechnerisch denselben Score** (aus den Perzentilen nachgerechnet:
2 · (M − 1) · Score = 505.960 bei beiden), I stand nach der Gleichstandsregel (gleicher Score → höhere Rendite) vorn; danach
führt Z38 (506.000). Das R² von Z31 liegt in allen vier Ranglisten vorher und nachher unter beiden Spitzenreitern und
wirkt nicht. **Gemeinsame Effekte mehrerer Aktien:** keine – Z31 reicht jeweils allein, und mit allen übrigen ersetzten
Kursen ohne Z31 bleibt Platz 1 unverändert. **Belegt ist der Auslöser, nicht die Ursache der Kursabweichung:** Der
offizielle Schlusskurs von Z31 weicht an 47 Tagen vom Stand ab; unter den genannten Tagen ist die Ursache teils belegt
(Stand = letzter Abschluss vor 16:00 Uhr, ohne Schlussauktion), teils ein Befund ohne Ursache.

**Andere Aktien unter den ersten 10** (gemeinsam; * = Kurse dieser Aktie im Zeitraum ersetzt): (a) 50 Tage, A, 90/10 –
raus N, rein O; 52 Tage, A, 100/0 – raus P*, rein S. (b) dieselben beiden und 22 Tage, A, 60/40 – raus X, rein Y; 31 Tage,
A, 0/100 – raus Z31*, rein Z34; 32 Tage, A, 50/50 – raus Z35, rein Z33; 44 Tage, A, 10/90 – raus Z40, rein M. (c) 24 Tage,
A, 40/60 – raus Z47, rein Z48. (a)+(c): die drei aus (a) und (c). Wo weder die verdrängte noch die neue Aktie einen Stern
trägt, wirkt allein die Verschiebung der Ränge durch andere ersetzte Kurse – wie bei den neuen Plätzen 1.

**Andere Reihenfolge der ersten 10 bei gleichen Aktien** (gemeinsam; Plätze: vorher → nachher):

- (a), 12 Ranglisten: 1 Tage, A, 0/100 – Plätze 5–9: C D E F A* → A* C D E F; 18 Tage, A, 10/90 – 5/6: H G* → G* H;
  31 Tage, A, 30/70 – 8/9: J K → K J; 40, 41 und 42 Tage, A, 30/70 – 8/9: L M → M L; 51 Tage, A, 70/30 – 7–9: P* Q R → Q R P*;
  57 Tage, B, 20/80 – 6/7: U* M → M U*; 60 Tage, A, 10/90 – 2/3: U* I* → I* U*; 68, 69 und 70 Tage, B, 80/20 – 9/10: V W → W V.
- (b), 27 Ranglisten: 23 Tage, A, 0/100 – 4–7: Z26 Z27 Z28 Z* → Z* Z26 Z27 Z28; 23 Tage, A, 60/40 – 5/6: Z29 Z30 → Z30 Z29;
  24 Tage, A, 0/100 – 5–8: Z* Z32 Z31* Z27 → Z32 Z* Z27 Z31*; 25 Tage, A, 0/100 – 8–10: Z31* Z27 Z33 → Z27 Z33 Z31*;
  30 Tage, A, 0/100 – 8/9: Z26 Z* → Z* Z26; 33, 34 und 35 Tage, A, 10/90 – 1/2: Z36 Z33 → Z33 Z36; 39 Tage, A, 10/90 – 5–8:
  Z37 Z38 Z39 Z40 → Z38 Z37 Z40 Z39; 40, 41 und 42 Tage, A, 30/70 – 8/9: L M → M L; 40, 41 und 42 Tage, A, 40/60 – 3/4:
  Z40 Z41 → Z41 Z40; 43 Tage, A, 30/70 – 3/4: Z40 Z39 → Z39 Z40; 45 Tage, A, 80/20 – 1/2: I* Z38 → Z38 I*; 46 Tage, A, 40/60 –
  9/10: Z42 Z43 → Z43 Z42; 47, 48 und 49 Tage, A, 70/30 – 6/7: P* M → M P*; 51 Tage, A, 50/50 – 6/7: Z43 Z41 → Z41 Z43;
  51 Tage, A, 70/30 – 7–9: P* Q R → Q R P*; 53 Tage, A, 70/30 – 3–6: Z39 Z43 Q P* → Z43 Z39 P* Q; 57 Tage, A, 80/20 – 6/7:
  Z43 Z44 → Z44 Z43; 57 Tage, B, 20/80 – 6/7: U* M → M U*; 60 Tage, A, 10/90 – 2/3: U* I* → I* U*.
- (c), 2 Ranglisten: 2 Tage, A, 0/100 – 7/8: Z46 Z45* → Z45* Z46; 31 Tage, A, 90/10 – 3/4: Z49 Z50 → Z50 Z49.
- (a)+(c), 14 Ranglisten: die 12 aus (a) und die 2 aus (c), unverändert.

Mit den Ranglisten mit anderen Aktien zusammen sind das die 14, 33, 3 und 17 Ranglisten „andere Reihenfolge“ der Tabelle.

**2. Fehlende Vergleichsdaten – die 38 Aktien ohne Nasdaq-Kurse.** Yahoo liefert ihre Kurse aus dem OTC-Handel (PNK 27,
OQX 5, OQB 4) bzw. von der NYSE (2, Kürzel mit Gattung); 34 haben ein fünfstelliges Kürzel. Geprüft wurden fünf frei
zugängliche Quellen ohne Schlüssel und ohne Anmeldung, die Aktien unter den ersten 10 zuerst; vor jedem Vergleich je Aktie
Identität (ISIN bzw. CUSIP, sonst Name), Handelsplatz, Währung, Handelsdatum (Versatz um Tage), Kursniveau und Bereinigung:

| Quelle | was abgerufen wurde | Ergebnis bei den 38 Aktien | Verwendung |
|---|---|---|---|
| **CNBC** | Kursmeldung (Name, Börse, Währung) und Tageskerzen | Kursmeldung 38 von 38; Tageskerzen mit Kursen 34, ohne Kurse 4; **vergleichbar 31** – Name bestätigt 33 (nur Kürzel 1), Handelsplatz gleich 31 (nicht angegeben 3), Währung gleich 33 (nicht angegeben 1), Kursniveau passt 33 (eine Aktie ohne gemeinsamen Tag), Bereinigung wie im Stand 34, kein Versatz des Handelsdatums; nicht vergleichbar 3 (zu wenige gemeinsame Tage) | Vergleichsquelle |
| **OTC Markets** (Betreiber des OTC-Handels) | Firmenprofil, Kursmeldung, Kurshistorie unter drei Adressen | Profil 36 (HTTP 404: 2); Kursmeldung 32 (HTTP 403: 4, HTTP 404: 2), davon mit letztem Abschluss 25; **Kurshistorie unter allen drei Adressen HTTP 404 – in den geprüften Quellen nicht gefunden** | letzter Abschluss (`lastSale`) als zweite Quelle für seinen Tag – seit `88d2733` am Handelstag nach Ortszeit New York (alle 25 Zeitstempel um 0 Uhr UTC, also 20 Uhr New York am 23.10.; nach UTC lagen sie einen Tag nach dem Kursstand): **gleich dem Stand bei 22, abweichend bei 3 Aktien** – an diesen 3 Tagen zeigt CNBC jeweils denselben Kurs wie OTC Markets (zwei Quellen gegen den Stand; die Ursache bleibt ungeklärt). **Überholt:** die Tageszuordnung ist nicht belegt, der OTC-Abschluss ist keine zweite Quelle (oben Punkt 4) |
| **Barchart** | Tageskurse | HTTP 403 bei allen 38 – Abruf gescheitert | – |
| **MarketWatch** | CSV der Kurshistorie | HTTP 401 bei allen 38 – Abruf gescheitert | – |
| **Stooq** | CSV der Tageskurse | HTML statt Daten bei allen 38 – seit März 2026 nur mit Schlüssel ([pandas-datareader #1012](https://github.com/pydata/pandas-datareader/issues/1012)); einen kostenlosen Schlüssel müsstest du selbst anfordern | – |

**Je Gruppe:** erste 10 – alle 10 Aktien ohne Nasdaq-Kurse mit CNBC verglichen; Plätze 11–20 – 5 von 5; Zufallsstichprobe –
16 von 23, **7 ohne Vergleichskurse in den geprüften Quellen** (CNBC ohne Kurse 4, nicht vergleichbar 3; alle übrigen
Quellen wie oben gescheitert). **Schlusskursdefinition:** wie CNBC den Schlusskurs der Tageskerze bildet, ist in den
geprüften Quellen nicht gefunden; OTC Markets nennt in der Kursmeldung den letzten Abschluss. **Bereinigung:** bei keiner
Aktie gegenüber dem Stand dividendenbereinigt, kein Faktor eines Splits (Prüfung gegen Yahoo „adjclose“ und die
Kursniveaus). **Dividenden-Gegenproben bei Nasdaq:** die vier im Lauf 40139805053 fehlenden nachgeholt – jetzt **60 von
60** (erste 10: 28, Plätze 11–20: 13, Zufallsstichprobe: 19), 0 ohne Antwort; Minutenkurse 66 von 66. *Zwischen den
Läufen:* Die Kursmeldung von CNBC enthielt bei einer Aktie nicht jedes Mal Name, Börse und Währung (im Lauf 40161469772
vollständig, in 40160248028 und 40162120622 nicht) – ohne Einfluss auf den Vergleich (vergleichbar 31 in allen Läufen).

**Ergebnis gegen die Zusatzquelle:** 1.912 gemeinsame Tage, **bestätigte Übereinstimmung 1.647**, festgestellte Abweichung
265 – davon Ursache belegt 2 (Stand zwischen zwei Kursstufen, CNBC zeigt die Nachbarstufe), ungeklärt 263 (an keinem
davon eine zweite Quelle für den Tag); fehlende Vergleichsmöglichkeit: 227 Tage nur im Stand (alle ohne Umsatz bei Yahoo,
also fortgeschriebene Kurse) und die 7 Aktien ohne Vergleichskurse. Muster der 263 ungeklärten Tage: alle mit Umsatz in
beiden Quellen; CNBC mit Kursstufe 0,0001 bei 259 und 0,001 bei 4; Abstand 1 Stufe 31, 2 Stufen 28, 3–10 Stufen 69, über
10 Stufen 135; Stand höher 168, niedriger 95. Eine Ursache ist in den geprüften Quellen nicht gefunden (einzelne Abschlüsse
des OTC-Handels sind dort nicht frei verfügbar).

**3. Ursachen korrekt eingeordnet – die fünf Ergebnisarten** (Tage; „Ursache belegt“ nur, wenn gezeigt ist, wodurch der
Unterschied entsteht; eine Prüfgrenze erklärt, warum kein Beleg möglich war, nicht die Abweichung; die Spalten zählen je
Vergleich):

| Ergebnisart | gegen die Nasdaq-Historie | gegen den offiziellen Schlusskurs (NOCP) | gegen die Zusatzquelle (CNBC) |
|---|---|---|---|
| bestätigte Übereinstimmung | 24.609 | 12.232 | 1.647 |
| festgestellte Abweichung | 630 | 441 | 265 |
| – davon **Ursache belegt** (überholt: plausible Erklärungen, keine belegte Ursache – oben Punkt 2) | **49**: Stand = letzter Abschluss vor 16:00 Uhr (ohne Schlussauktion), Vergleichskurs ein anderer 12; Nasdaq-Historie = letzter Abschluss vor 16:00 Uhr, Stand ein anderer 31; kein Umsatz, Kurs des Vortags fortgeschrieben 6 | **56**: Stand = letzter Abschluss vor 16:00 Uhr (ohne Schlussauktion) | **2**: Stand zwischen zwei Kursstufen |
| – davon **Ursache ungeklärt** | **581**: Befund „Stand ≠ NOCP bei Nasdaq-Historie = NOCP“, der Kurs des Stands ist kein letzter Abschluss vor 16:00 Uhr 255; ohne Beleg 326 – Prüfgrenze bei Heimatbörse der NYSE-Gruppe oder Cboe 310, Nasdaq-notiert mit drei verschiedenen Kursen 16 | **385**: Befund – Nasdaq-Historie = NOCP, Stand nicht 257; Nasdaq-Historie = Stand, NOCP anders 106; drei verschiedene Kurse 22 | **263** |
| fehlende Vergleichsmöglichkeit | 38 Aktien ohne Nasdaq-Kurse (31 davon gegen CNBC verglichen); 11 Tage nur im Stand | 219 nicht Nasdaq-notierte Aktien mit 12.543 Tagen ohne NOCP – offizieller Schlusskurs der NYSE-Gruppe in den geprüften Quellen nur kostenpflichtig („TAQ NYSE Closing Prices“) | 7 Aktien ohne Vergleichskurse in den geprüften Quellen; 227 Tage nur im Stand |
| außerdem | Stand = offizieller Schlusskurs, abweichend nur die Nasdaq-Historie: 0 | Faktor eines Splits (NOCP unbereinigt): 34 – keine Abweichung | – |

**Je Gruppe** (gleich / abweichend / davon belegt / davon ungeklärt; Tage):

| Gruppe | gegen die Nasdaq-Historie | gegen den NOCP | gegen CNBC | fehlende Vergleichsmöglichkeit |
|---|---|---|---|---|
| erste 10 (157 Aktien) | 9.786 / 342 / 28 / 314 | 5.180 / 195 / 23 / 172 | 608 / 62 / 2 / 60 | 0 Aktien ohne Vergleichskurse; 78 Aktien ohne NOCP |
| Plätze 11–20 (97) | 6.294 / 54 / 3 / 51 | 3.561 / 27 / 2 / 25 | 303 / 36 / 0 / 36 | 0; 45 ohne NOCP |
| Zufallsstichprobe (150) | 8.529 / 234 / 18 / 216 | 3.491 / 219 / 31 / 188 | 736 / 167 / 0 / 167 | 7; 96 ohne NOCP |
| **zusammen (404)** | **24.609 / 630 / 49 / 581** | **12.232 / 441 / 56 / 385** | **1.647 / 265 / 2 / 263** | **7; 219 ohne NOCP** |

**Neu eingeordnet gegenüber Lauf 40139805053:** Dort zählten 304 der 630 Tage als „Ursache belegt“, 266 davon mit „Yahoo
nicht der offizielle Schlusskurs (Nasdaq-Historie = NOCP)“. Das ist ein **Befund**: Der Stand führt an dem Tag nicht den
offiziellen Schlusskurs – wodurch, zeigt er nicht. Seit dem 25.10. prüft das Skript an diesen Tagen zuerst, ob der Kurs des
Stands der letzte Abschluss vor 16:00 Uhr ist (dann fehlt ihm die Schlussauktion – das ist ein Beleg): bei 11 der 266
Tage ja (mit dem einen schon bisher so belegten Tag: 12); 255 bleiben ein Befund ohne belegte Ursache – der Kurs des Stands
steht nicht unter den Minutenkursen vor 16:00 Uhr, und die einzelnen Abschlüsse um 16:00 Uhr sind in den geprüften Quellen
nicht frei verfügbar. Ebenso ist „Nasdaq-Historie = letzter Abschluss“ kein Beleg, wenn die Nasdaq-Historie zugleich der
offizielle Schlusskurs ist (im Lauf 40158331688 an 12 Tagen so gezählt, behoben). Damit gegen die Nasdaq-Historie **belegt
49 von 630 Tagen** (bisher 304), **ungeklärt 581** (bisher 326); gegen den NOCP **belegt 56 von 441**, ungeklärt 385.
Dividendenbereinigung und Split: an 0 Tagen Ursache.

**4. Zuordnung der Buchstaben** – Datenstand `2026-10-23_3f7ce5f3` (Kursstand 23.10.2026). In der App mit der Passphrase
den Link der Fundstelle öffnen (oder „Rangliste“ mit Zeitraum, Gruppe und Gewichtung wählen), Einstellung „Auffällige
ausblenden“ aus; nach einem neueren Stand (ab dem Nachtlauf vom 26.10.) zuerst unter „Datenstand & Betrieb → Frühere
Stände“ den Kursstand 23.10.2026 „Anzeigen“. Jeder Buchstabe ist genau eine Aktie – ihr bester Platz in einer Rangliste des
Stands; die Buchstaben gelten je Job und Lauf. Hier die des gemeinsamen Jobs, rechts dieselbe Aktie in Lauf 40139805053
(Job „erste 20“, über dieselbe Fundstelle; „–“: dort nicht genannt):

| Buchstabe | Fundstelle in der App (Datenstand 2026-10-23_3f7ce5f3) | Art; Kurse im Prüfzeitraum | in Lauf 40139805053 („erste 20“) |
|---|---|---|---|
| A | [1 Tage, Gruppe A, 0/100, Platz 9](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | NYSE American, unter 1 $; unter den ersten 10 in 1 Rangliste; abweichend von der Nasdaq-Historie an 66 Tagen | V |
| B | [1 Tage, Gruppe A, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | NYSE American, unter 1 $; unter den ersten 10 in 1 Rangliste; abweichend von der Nasdaq-Historie an 34 Tagen | X |
| C | [1 Tage, Gruppe A, 0/100, Platz 5](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| D | [2 Tage, Gruppe A, 0/100, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=2&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| E | [1 Tage, Gruppe A, 0/100, Platz 7](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| F | [1 Tage, Gruppe A, 0/100, Platz 8](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| G | [18 Tage, Gruppe A, 10/90, Platz 6](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=10&p=native&n=10) | NYSE American, unter 1 $; unter den ersten 10 in 1 Rangliste; abweichend von der Nasdaq-Historie an 57 Tagen | W |
| H | [10 Tage, Gruppe B, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=10&w=0&p=native&n=10&g=b) | Nasdaq, 10–100 $; unter den ersten 10 in 19 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| I | [30 Tage, Gruppe A, 20/80, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=20&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 388 Ranglisten; abweichend von der Nasdaq-Historie an 2 Tagen, ungleich NOCP an 2 Tagen | B |
| J | [19 Tage, Gruppe B, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=19&w=10&p=native&n=10&g=b) | NYSE, 10–100 $; unter den ersten 10 in 204 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| K | [32 Tage, Gruppe A, 40/60, Platz 5](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=32&w=40&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 51 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| L | [45 Tage, Gruppe A, 10/90, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=45&w=10&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| M | [40 Tage, Gruppe B, 10/90, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=40&w=10&p=native&n=10&g=b) | NYSE, 1–10 $; unter den ersten 10 in 360 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | Z52 |
| N | [50 Tage, Gruppe A, 90/10, Platz 10](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=50&w=90&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z43 |
| O | [58 Tage, Gruppe B, 80/20, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=58&w=80&p=native&n=10&g=b) | NYSE, 10–100 $; unter den ersten 10 in 584 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | Z44 |
| P | [52 Tage, Gruppe A, 80/20, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=52&w=80&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 50 Ranglisten; abweichend von der Nasdaq-Historie an 2 Tagen, ungleich NOCP an 2 Tagen | F |
| Q | [65 Tage, Gruppe A, 70/30, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=65&w=70&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| R | [57 Tage, Gruppe A, 100/0, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=57&w=100&p=native&n=10) | NYSE, 10–100 $; unter den ersten 10 in 52 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| S | [59 Tage, Gruppe A, 100/0, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=59&w=100&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z45 |
| T | [53 Tage, Gruppe B, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=53&w=10&p=native&n=10&g=b) | Nasdaq, 1–10 $; unter den ersten 10 in 725 Ranglisten; abweichend von der Nasdaq-Historie an 3 Tagen, ungleich NOCP an 3 Tagen | A |
| U | [39 Tage, Gruppe B, 0/100, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=39&w=0&p=native&n=10&g=b) | Nasdaq, unter 1 $; unter den ersten 10 in 213 Ranglisten; abweichend von der Nasdaq-Historie an 43 Tagen, ungleich NOCP an 43 Tagen | C |
| V | [54 Tage, Gruppe B, 60/40, Platz 4](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=54&w=60&p=native&n=10&g=b) | NYSE, 10–100 $; unter den ersten 10 in 104 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| W | [72 Tage, Gruppe B, 70/30, Platz 6](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=72&w=70&p=native&n=10&g=b) | andere, 10–100 $; unter den ersten 10 in 53 Ranglisten; verglichen mit CNBC, abweichend an keinem Tag | – |
| X | [22 Tage, Gruppe A, 20/80, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=22&w=20&p=native&n=10) | NYSE, 1–10 $; unter den ersten 10 in 41 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | Z46 |
| Y | [18 Tage, Gruppe B, 30/70, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=30&p=native&n=10&g=b) | keine US-Aktie – Kurse unverändert | Z47 |
| Z | [22 Tage, Gruppe A, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=22&w=0&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 22 Ranglisten; abweichend von der Nasdaq-Historie an 1 Tag, ungleich NOCP an 12 Tagen | H |
| Z26 | [4 Tage, Gruppe B, 0/100, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=4&w=0&p=native&n=10&g=b) | Nasdaq, 10–100 $; unter den ersten 10 in 76 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| Z27 | [5 Tage, Gruppe A, 0/100, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=5&w=0&p=native&n=10) | Nasdaq, 10–100 $; unter den ersten 10 in 59 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| Z28 | [11 Tage, Gruppe A, 0/100, Platz 4](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=11&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z29 | [26 Tage, Gruppe A, 70/30, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=26&w=70&p=native&n=10) | Nasdaq, 10–100 $; unter den ersten 10 in 230 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| Z30 | [18 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=10&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 109 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |
| Z31 | [24 Tage, Gruppe A, 0/100, Platz 7](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=24&w=0&p=native&n=10) | Nasdaq, 1–10 $; unter den ersten 10 in 3 Ranglisten; abweichend von der Nasdaq-Historie an 15 Tagen, ungleich NOCP an 47 Tagen | Q |
| Z32 | [38 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=38&w=10&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z33 | [30 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=10&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z50 |
| Z34 | [30 Tage, Gruppe A, 0/100, Platz 6](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z48 |
| Z35 | [32 Tage, Gruppe A, 50/50, Platz 10](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=32&w=50&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z49 |
| Z36 | [31 Tage, Gruppe A, 20/80, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=31&w=20&p=native&n=10) | Nasdaq, 10–100 $; unter den ersten 10 in 185 Ranglisten; abweichend von der Nasdaq-Historie an 3 Tagen, ungleich NOCP an 3 Tagen | D |
| Z37 | [10 Tage, Gruppe A, 0/100, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=10&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z38 | [31 Tage, Gruppe B, 40/60, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=31&w=40&p=native&n=10&g=b) | keine US-Aktie – Kurse unverändert | Z53 |
| Z39 | [44 Tage, Gruppe A, 20/80, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=44&w=20&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z40 | [75 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=75&w=10&p=native&n=10) | keine US-Aktie – Kurse unverändert | Z51 |
| Z41 | [36 Tage, Gruppe A, 20/80, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=36&w=20&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z42 | [53 Tage, Gruppe A, 10/90, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=53&w=10&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z43 | [53 Tage, Gruppe A, 80/20, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=53&w=80&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z44 | [52 Tage, Gruppe B, 80/20, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=52&w=80&p=native&n=10&g=b) | keine US-Aktie – Kurse unverändert | – |
| Z45 | [4 Tage, Gruppe A, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=4&w=0&p=native&n=10) | OTC, unter 1 $; unter den ersten 10 in 2 Ranglisten; verglichen mit CNBC, abweichend an 53 Tagen | – |
| Z46 | [15 Tage, Gruppe A, 0/100, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=15&w=0&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z47 | [25 Tage, Gruppe A, 80/20, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=25&w=80&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z48 | [18 Tage, Gruppe A, 30/70, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=30&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z49 | [32 Tage, Gruppe A, 100/0, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=32&w=100&p=native&n=10) | keine US-Aktie – Kurse unverändert | – |
| Z50 | [24 Tage, Gruppe A, 70/30, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=24&w=70&p=native&n=10) | NYSE, 10–100 $; unter den ersten 10 in 248 Ranglisten; abweichend von der Nasdaq-Historie an keinem Tag | – |

**Fazit:** Abgerufen ist alles (0 Aktien ohne Antwort); verglichen sind 397 der 404 ausgewählten US-Aktien – 366 mit
Nasdaq, 31 mit CNBC –, 7 haben in den geprüften Quellen keine Vergleichskurse. Gegen die Nasdaq-Historie stimmen 24.609
Tage überein, 630 weichen ab: Ursache belegt an 49, ungeklärt an 581 (255 Befunde „Stand ≠ offizieller Schlusskurs“ ohne
belegte Ursache, 310 an der Prüfgrenze der NYSE-Gruppe, 16 mit drei verschiedenen Kursen); gegen CNBC stimmen 1.647 Tage
überein, 265 weichen ab (2 belegt). **Gemeinsam auf die Ranglisten:** mit Nasdaq-Historie und CNBC nie ein anderer Platz 1
(3 Ranglisten mit anderen Aktien unter den ersten 10, 17 mit anderer Reihenfolge), mit dem offiziellen Schlusskurs in 4 von
1.640 Ranglisten – jedes Mal allein ausgelöst durch die Rendite von Z31 über die Ränge, bei 45 Tagen aus einem exakten
Gleichstand heraus; die gemeinsame Rechnung ergibt keinen Platz 1, den nicht schon ein Job allein ergibt. Die Prüfung ist
**nicht vollständig** im Sinne des festgelegten Umfangs und **keine Vollprüfung** der App.

**Läufe davor (25.10.2026, Auftrag 03:47 Uhr):** [40158331688](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40158331688) (04:28–04:36 Uhr, Commit `a1bcf79`) – erste
gemeinsame Rechnung, gleiche Wirkung wie oben; gefunden: „Nasdaq-Historie = letzter Abschluss“ an 12 Tagen als Beleg
gezählt, obwohl die Nasdaq-Historie dort der offizielle Schlusskurs ist; unter den Auslösern standen neben Z31 bis zu drei
Aktien, die die Suche nur unterwegs hinzugenommen hatte; die Feldnamen der Kursmeldung von OTC Markets fehlten im Bericht –
behoben in `0c6f17c`. [40159274087](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40159274087) (04:43–05:01 Uhr, Commit `0c6f17c`) – gefunden: Bei Aktien mit
Gattung im Kürzel brach die Suche nach der Schreibweise bei Nasdaq nach HTTP 404 ab, Yahoo wurde dann nicht abgefragt und
der Handelsplatz galt als „anders“; der letzte Abschluss bei OTC Markets nahm den Zeitpunkt der Abfrage statt des
Abschlusses – behoben in `9a76490`. [40160248028](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40160248028) (05:00–05:07 Uhr, Commit `9a76490`) – dieselben
Zahlen wie oben; Platz 1 wechselte, obwohl Rendite und R² der Spitzenreiter gleich blieben, und der Tag des letzten
OTC-Abschlusses lag bei 25 Aktien nicht im Stand – deshalb in `0b7d8e8` Score, Perzentile und Lage des Auslösers je neuem
Platz 1 und die Lage dieses Tags; [40161469772](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40161469772) (05:19–05:27 Uhr, Commit `0b7d8e8`) zeigte: der Tag
liegt nach UTC einen Kalendertag nach dem Kursstand – deshalb in `88d2733` der Handelstag nach Ortszeit New York.

#### Ursachen der Unterschiede und Wirkung auf die Ranglisten (Auftrag 21:23 Uhr, Punkt 2)

Job „Ursachen der Kursunterschiede (Nasdaq)“ (`tests/live/kurse_ursachen.py`, neu in 1.18.1, Option „Ursachen“). Geprüft
werden die US-Aktien unter den ersten 20 irgendeiner Rangliste des Stands vom 23.10. und 150 zufällige. **Alles
nachträglich abgerufen** – Nasdaq-Historie, offizieller Schlusskurs der Nasdaq, Yahoo-Tages- und -Minutenkurse,
Dividenden –, keine Originaldaten. Was die Quellen als Schlusskurs definieren:

- **Offizieller Schlusskurs der Nasdaq (NOCP):** Preis der Schlussauktion „Closing Cross“, ersatzweise nach festen
  Regeln der letzte Abschluss vor 16:00 Uhr ([Nasdaq Rule 4754, SR-NASDAQ-2019-035](https://listingcenter.nasdaqomx.com/assets/rulebook/nasdaq/filings/SR-NASDAQ-2019-035_Notice_Approval.pdf)).
- **Offizieller Schlusskurs der NYSE-Börsen:** Preis der Schlussauktion, ohne Auktion der letzte Abschluss der
  Kernhandelszeit, ohne Abschluss der Kurs des Vortags ([NYSE Arca Rule 1.1(gg)](https://www.nyse.com/publicdocs/nyse/regulation/nyse-arca/NYSE_Arca_Rule_1.1.pdf)) –
  eine frei abrufbare Historie davon gibt es nicht.
- **Yahoo:** „Adjusted close is the closing price after adjustments for all applicable splits and dividend distributions“
  ([Yahoo-Hilfe](https://help.yahoo.com/kb/SLN28256.html)); welchen Schlusskurs Yahoo als „Close“ führt, sagt die Hilfe nicht.

**In der Einordnung überholt (seit dem 25.10.2026, 04:28 Uhr MEZ):** Die Zahlen der Abweichungen und die Wirkung je Job
unten gelten weiter – gemeinsam nachgerechnet mit „dieselbe Wirkung“ (Abschnitt „Gemeinsame Neuberechnung …“ oben). Hier
zählte „Ursache belegt“ aber auch Befunde (266 Tage „Yahoo nicht der offizielle Schlusskurs, Nasdaq-Historie = NOCP“), und
beim neuen Platz 1 für 45 Tage steht B unter den Auslösern, obwohl Q allein reicht. Maßgeblich ist die Einordnung oben.

**Ergebnis** – [Lauf 40139805053](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805053), 25.10.2026, 00:44–00:52 Uhr (MESZ), Commit `e90bad7`, zwei Jobs auf zwei Rechnern
([„erste 20“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805053/job/121008956743), [„Zufallsstichprobe“](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40139805053/job/121008956748)) – Nasdaq beantwortet je Rechner nur etwa 430 Anfragen
(vierter Lauf unten). Dieselben Zahlen wie im fünften Lauf, nur mit genauerer Lage der Nasdaq-Historie. **Beide Jobs rot
(„UNVOLLSTÄNDIG“)** – nicht wegen des Abrufs (in beiden Jobs 0 Aktien ohne Antwort), sondern weil 38 Aktien bei Nasdaq keine
Vergleichskurse haben und 326 abweichende Tage ohne belegte Ursache bleiben. Alle Hinweise sind ausgegeben (13 bzw. 5 Teile;
das bestätigt der letzte Hinweis jedes Jobs).

**Abdeckung je Gruppe** – fehlende Daten zählen nicht als geprüft:

| Gruppe | ausgewählt | erfolgreich verglichen | davon mit offiziellem Schlusskurs (Nasdaq-notiert) | keine Vergleichskurse bei Nasdaq | Abruf fehlgeschlagen |
|---|---|---|---|---|---|
| erste 10 (in mindestens einer Rangliste) | 157 | 147 | 79 | 10 | 0 |
| Plätze 11–20 (in keiner Rangliste unter den ersten 10) | 97 | 92 | 52 | 5 | 0 |
| erste 20 gesamt | 254 | 239 | 131 | 15 | 0 |
| Zufallsstichprobe | 150 | 127 | 54 | 23 | 0 |
| **zusammen** | **404** | **366** | **185** | **38** | **0** |

Ohne Vergleichskurse sind fast nur Aktien mit fünfstelligem Kürzel (34 von 38, die übrigen 4 mit vier Zeichen) – Nasdaq
führt sie nicht. **Nicht geprüft sind damit 10 der 157 US-Aktien unter den ersten 10.** Anfragen an Nasdaq: 430 bzw. 223;
im Job „erste 20“ blieben die letzten 4 Gegenproben der Dividenden ohne Antwort (keine bei einer Aktie unter den ersten 10).

**Kurse und Ursachen** – belegt ist eine Ursache nur mit einem Kurs aus einer zweiten Quelle; fehlender Zugang zum
offiziellen Schlusskurs erklärt die Grenze der Prüfung, nicht die Abweichung:

| Frage | erste 20 | Zufallsstichprobe | zusammen |
|---|---|---|---|
| Stand = offizieller Schlusskurs (NOCP) – Nasdaq-notierte Aktien, alle Tage | 8.741 von 8.981 Tagen (97,3 %); ungleich 222; Faktor eines Splits 18 (NOCP unbereinigt, nicht ersetzt) | 3.491 von 3.726 (93,7 %); ungleich 219; Faktor 16 | 12.232 von 12.707 (96,3 %); ungleich 441; Faktor 34 |
| Börsentage gegen die Nasdaq-Historie | 16.476 verglichen, 396 abweichend (bis 0,5 %: 292, darüber 92, Kurs eines Nachbartags 12) | 8.763 verglichen, 234 abweichend (186, 43, 5) | 25.239 verglichen, 630 abweichend |
| **Ursache belegt** | 172: Yahoo nicht der offizielle Schlusskurs (Nasdaq-Historie = NOCP) 146; Nasdaq-Historie = letzter Abschluss vor 16:00 Uhr, Stand ein anderer Kurs 19; kein Umsatz, Kurs des Vortags 6; Stand = letzter Abschluss, Nasdaq anders 1 | 132: Nasdaq-Historie = NOCP 120; Nasdaq-Historie = letzter Abschluss 12 | **304** |
| **Ungeklärt – Ursache offen** | 224 | 102 | **326** |
| davon Prüfgrenze (warum kein Beleg möglich war) | 212: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs nicht frei abrufbar | 98 | 310 |
| davon Befund ohne Ursache | 12: Nasdaq-notiert, Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse | 4 | 16 |

Muster der ungeklärten Tage (erste 20): alle 224 auf einer Kursstufe, Umsatz beider Quellen gleich an 194; Abstand 1 Stufe
48, 2 Stufen 15, 3–10 Stufen 49, über 10 Stufen 112; Stand höher 115, niedriger 109; 143 ohne Minutenkurs (älter als 58
Tage), 81 mit Minutenkursen, aber keinem passenden. Handelsdatum: Umsatz gleich an 16.307 von 16.476 Tagen; 11 Tage nur im
Stand (2 davon ohne Umsatz bei Yahoo), 4 nur bei Nasdaq (Yahoo ohne Kurs, in der App fehlender Kurstag). Bereinigung und
Kapitalmaßnahmen: Dividendenbereinigung und Split als Ursache an 0 Tagen; der unbereinigte NOCP vor Splits ist an 34 Tagen
als Faktor erkannt und nicht ersetzt; Aktien mit Ereignis im Zeitraum (erste 20): Dividende laut Yahoo 7, laut Nasdaq 7,
Split 2. **Aktien unter den ersten 10:** 147 verglichen – 119 ohne Abweichung zur Nasdaq-Historie (davon 2 nur mit anderem
offiziellem Schlusskurs), 20 mit belegter Ursache jeder Abweichung, 8 mit ungeklärten Tagen (H, J, O, Q, V, W, X, Y).

**Wirkung auf die Ranglisten** – unabhängige Rechnung, 1.980 Ranglisten, davon 1.640 nicht leer:

| Variante | Job „erste 20“ (Kurse von 239 Aktien) | Job „Zufallsstichprobe“ (127 Aktien) |
|---|---|---|
| (a) Nasdaq-Kurs an allen abweichenden Tagen | Platz 1 in **keiner** Rangliste anders; andere Aktien unter den ersten 10 in 2; andere Reihenfolge der ersten 10 in 14; irgendeine Änderung in 1.237 | erste 10 überall unverändert; irgendeine Änderung in 842 |
| (b) offizieller Schlusskurs an allen Tagen, an denen er vom Stand abweicht | Platz 1 in **4** Ranglisten anders; andere Aktien unter den ersten 10 in 6; andere Reihenfolge der ersten 10 in 33; irgendeine Änderung in 1.034 | erste 10 überall unverändert; irgendeine Änderung in 781 |

Beide Jobs zusammen (alle 366 Aktien zugleich) waren in diesem Lauf nicht gerechnet – die Kurse der beiden Rechner wurden
nicht zusammengeführt, die Live-Prüfung lädt nichts hoch. Seit dem 25.10. rechnet sie der Job „gemeinsame Wirkung“ (oben).

**Jede Rangliste mit neuem Platz 1** – nur in Variante (b):

| # | Zeitraum und Berechnungsmethode | bisher → neu | Rendite und R² der beiden | Auslösende Kursabweichungen (Stand gegenüber NOCP) | allein ausreichend |
|---|---|---|---|---|---|
| 1–3 | 33, 34 und 35 Tage, Gruppe A, Gewichtung 10/90 (Gleichmäßigkeit 10 %, Rendite 90 %) | D → Z50 (vorher Platz 2) | beide unverändert: D +50,16 %, R² 0,92909; Z50 +66,40 %, R² 0,86912 | nur Aktie **Q**, 15 Tage im Zeitraum, u. a. 18.09. −0,04 % (Nasdaq-Historie = NOCP), 21.09. −2,56 % (Nasdaq-Historie = Stand, NOCP anders), 22.09. −6,92 % und 23.09. +1,32 % (drei verschiedene Kurse), 24.09. +3,07 %, 25.09. +0,69 %, 05.10. −0,86 %, 06.10. −0,85 %, 09.10. −2,34 %, 13.10. −3,62 % (jeweils Nasdaq-Historie = Stand) und 5 weitere | Q |
| 4 | 45 Tage, Gruppe A, Gewichtung 80/20 (Gleichmäßigkeit 80 %, Rendite 20 %) | B → Z53 (vorher Platz 2) | B +76,26 % (unverändert), R² 0,93406 → 0,93403; Z53 +56,53 %, R² 0,94632 (unverändert) | B: 25.09. +0,12 %, 13.10. +0,09 % (Nasdaq-Historie = NOCP); Q: 23 Tage, u. a. 08.09. +1,99 %, 09.09. −1,96 %, 10.09. −3,04 %, 11.09. +13,36 %, 14.09. −1,84 %, 16.09. +2,03 % (drei verschiedene Kurse), 15.09. −2,56 %, 17.09. −0,01 %, 21.09. −2,56 % (Nasdaq-Historie = Stand), 18.09. −0,04 % (Nasdaq-Historie = NOCP) und 13 weitere | Q |

Die Spitzenreiter selbst ändern sich (fast) nicht: In gewichteten Ranglisten zählt der Rang von Rendite und R² in der
Gruppe; die geänderten Kurse von Q verschieben Ränge, und der Zweitplatzierte zieht vorbei. Ermittelt, indem jede dieser
Ranglisten nur mit den Kursen einzelner Aktien neu gerechnet wurde – die Kurse von Q allein reichen für alle vier Wechsel.
**Belegt ist der Auslöser, nicht die Ursache:** Warum der offizielle Schlusskurs von Q an 47 Tagen vom Stand abweicht
(meist bei gleicher Nasdaq-Historie und gleichem Stand, also gleichem letztem Kurs beider Quellen), ist offen – die Daten
der Schlussauktion sind nicht frei abrufbar.

**Andere Aktien unter den ersten 10** (ohne neuen Platz 1): (a) 50 Tage, Gruppe A, 90/10 – raus Z43, rein Z44; 52 Tage,
Gruppe A, 100/0 – raus F, rein Z45. (b) dieselben beiden und 22 Tage, Gruppe A, 60/40 – raus Z46, rein Z47; 31 Tage,
Gruppe A, 0/100 – raus Q, rein Z48; 32 Tage, Gruppe A, 50/50 – raus Z49, rein Z50; 44 Tage, Gruppe A, 10/90 – raus Z51,
rein Z52.

**Zuordnung der Buchstaben** – jeder Buchstabe ist genau eine Aktie: ihr bester Platz in einer Rangliste des Stands
`2026-10-23_3f7ce5f3` (Kursstand 23.10.2026; in der App mit der Passphrase über den Link der Fundstelle oder unter
„Rangliste“, Einstellung „Auffällige ausblenden“ aus; nach einem neueren Stand zuerst „Datenstand & Betrieb → Frühere
Stände“, Kursstand 23.10.2026 „Anzeigen“). Die Buchstaben gelten je Job und Lauf; hier Job „erste 20“ – alle in diesem
Abschnitt genannten, rechts dieselbe Aktie im gemeinsamen Job des Laufs 40162120622 (über dieselbe Fundstelle; „–“: dort
nicht genannt):

| Buchstabe | Fundstelle in der App | Art | im gemeinsamen Job |
|---|---|---|---|
| B | [30 Tage, Gruppe A, 20/80, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=20&p=native&n=10) | Nasdaq, 1–10 $ | I |
| D | [31 Tage, Gruppe A, 20/80, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=31&w=20&p=native&n=10) | Nasdaq, 10–100 $ | Z36 |
| F | [52 Tage, Gruppe A, 80/20, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=52&w=80&p=native&n=10) | Nasdaq, 1–10 $ | P |
| H | [22 Tage, Gruppe A, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=22&w=0&p=native&n=10) | Nasdaq, 1–10 $ | Z |
| J | [22 Tage, Gruppe A, 100/0, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=22&w=100&p=native&n=10) | NYSE, über 100 $ | – |
| O | [3 Tage, Gruppe A, 0/100, Platz 4](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=3&w=0&p=native&n=10) | NYSE, 1–10 $ | – |
| Q | [24 Tage, Gruppe A, 0/100, Platz 7](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=24&w=0&p=native&n=10) | Nasdaq, 1–10 $ | Z31 |
| V | [1 Tage, Gruppe A, 0/100, Platz 9](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | NYSE American, unter 1 $ | A |
| W | [18 Tage, Gruppe A, 10/90, Platz 6](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=10&p=native&n=10) | NYSE American, unter 1 $ | G |
| X | [1 Tage, Gruppe A, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10) | NYSE American, unter 1 $ | B |
| Y | [1 Tage, Gruppe B, 0/100, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=1&w=0&p=native&n=10&g=b) | NYSE, 1–10 $ | – |
| Z43 | [50 Tage, Gruppe A, 90/10, Platz 10](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=50&w=90&p=native&n=10) | keine US-Aktie | N |
| Z44 | [58 Tage, Gruppe B, 80/20, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=58&w=80&p=native&n=10&g=b) | NYSE, 10–100 $ | O |
| Z45 | [59 Tage, Gruppe A, 100/0, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=59&w=100&p=native&n=10) | keine US-Aktie | S |
| Z46 | [22 Tage, Gruppe A, 20/80, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=22&w=20&p=native&n=10) | NYSE, 1–10 $ | X |
| Z47 | [18 Tage, Gruppe B, 30/70, Platz 3](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=18&w=30&p=native&n=10&g=b) | keine US-Aktie | Y |
| Z48 | [30 Tage, Gruppe A, 0/100, Platz 6](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=0&p=native&n=10) | keine US-Aktie | Z34 |
| Z49 | [32 Tage, Gruppe A, 50/50, Platz 10](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=32&w=50&p=native&n=10) | keine US-Aktie | Z35 |
| Z50 | [30 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=30&w=10&p=native&n=10) | keine US-Aktie | Z33 |
| Z51 | [75 Tage, Gruppe A, 10/90, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=75&w=10&p=native&n=10) | keine US-Aktie | Z40 |
| Z52 | [40 Tage, Gruppe B, 10/90, Platz 2](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=40&w=10&p=native&n=10&g=b) | NYSE, 1–10 $ | M |
| Z53 | [31 Tage, Gruppe B, 40/60, Platz 1](https://szymeklh87-commits.github.io/tr-aktienvergleich/#/ranking?h=31&w=40&p=native&n=10&g=b) | keine US-Aktie | Z38 |

Die übrigen Buchstaben (A–Z und Z26–Z42 im Job „erste 20“, A–S im Job „Zufallsstichprobe“) stehen mit Fundstelle im
Hinweis „Zuordnung der Buchstaben“ des jeweiligen Jobs und in seiner Zusammenfassung.

**Fazit (00:52 Uhr MESZ – Einordnung überholt, siehe oben):** An 304 der 630 von der Nasdaq-Historie abweichenden Tage ist die Ursache belegt – meist (266) führt Yahoo dort
nicht den offiziellen Schlusskurs der Nasdaq, seltener ist einer der Kurse der letzte Abschluss vor 16:00 Uhr (32) oder es
gab keinen Umsatz (6). **326 Tage bleiben ungeklärt**; bei 310 davon liegt die Heimatbörse in der NYSE-Gruppe, deren
offizieller Schlusskurs nicht frei abrufbar ist – das ist die Grenze dieser Prüfung, keine Ursache. 38 Aktien (10 unter
den ersten 10) sind mangels Vergleichskursen nicht geprüft. **Auf die Ranglisten wirkt das so:** mit den Nasdaq-Kursen nie
auf Platz 1 (2 Ranglisten mit anderen Aktien unter den ersten 10), mit dem offiziellen Schlusskurs in 4 von 1.640
Ranglisten auf Platz 1 (6 mit anderen Aktien unter den ersten 10) – alle vier ausgelöst allein durch die offiziellen
Schlusskurse der Aktie Q. Die Prüfung ist damit **nicht vollständig** im Sinne des festgelegten Umfangs.

**Fünfter Lauf** ([40138800418](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40138800418), 25.10.2026, 00:30–00:38 Uhr, Commit `d634391`): erstmals in zwei Jobs, 0 Aktien
ohne Antwort, dieselben Zahlen wie oben. Gefunden: Die Lage der Nasdaq-Historie hieß „Nasdaq ein dritter Kurs“ auch an
Tagen, an denen sie dem Stand gleicht (bei Q die meisten), und im Job der Zufallsstichprobe standen die 157 US-Aktien unter
den ersten 10 als „ohne Nasdaq-Kurse“ statt „im anderen Job“ – beides behoben (Commit `e90bad7`, 2 Tests), danach der Lauf
oben.

**Vierter Lauf** ([40135600271](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40135600271), 24.10.2026, 23:45 Uhr bis 25.10., 00:25 Uhr, Commit `c27d225`) – **unvollständig**,
Job rot: zuerst die Aktien unter den ersten 10 abgefragt, dann die Plätze 11–20, zuletzt die Zufallsstichprobe. Je Gruppe:
erste 10 – 147 mit Kursen, 10 ohne Kurse bei Nasdaq, 0 ohne Antwort; Plätze 11–20 – 92 mit Kursen, 5 ohne Kurse, 0 ohne
Antwort; Zufallsstichprobe – 19 mit Kursen, 10 ohne Kurse, **121 ohne Antwort** (94 Verbindungsfehler, innen
`HTTPError`; 27 nach Ablauf des Zeitbudgets). Damit ist belegt, dass alle Aktien ohne Antwort aus der Zufallsstichprobe
stammen. Nasdaq antwortete **nach 430 Anfragen nicht mehr** – auch nicht nach zwei Pausen von je 180 s und mit 3 s
Abstand (insgesamt 938 Anfragen, ebenso alle 43 Abfragen der Dividenden). Die Ergebnisse gleichen dem dritten Lauf
(dieselben Zahlen bei NOCP, Ursachen, ungeklärten Tagen und Ranglisten); neu sind die geänderten Ranglisten mit
Buchstaben: (b) Platz 1 anders in 33, 34 und 35 Tage, Gruppe A, 10/90 (D → Z52) und 45 Tage, Gruppe A, 80/20 (B → Z55;
Buchstaben dieses Laufs, im Ergebnis oben Z50 bzw. Z53);
dazu zwei Aktien unter den ersten 10, bei denen nur der offizielle Schlusskurs vom Stand abweicht (eine an einem Tag um
5,37 %). Die Buchstaben dieses Laufs waren noch keiner Aktie zugeordnet, die Auslöser nicht ermittelt – deshalb
(Commits `4cd1976`, `d634391`): Abdeckung je Gruppe mit „erfolgreich verglichen / keine Vergleichskurse / Abruf
fehlgeschlagen“ (fehlende Vergleichskurse machen das Urteil „unvollständig“), jeder neue Platz 1 einzeln mit Methode,
Spitzenreitern, Rendite und R² vorher/nachher und den auslösenden Kursabweichungen, Zuordnung jedes Buchstabens über einen
Platz in einer Rangliste des Stands, Prüfgrenze getrennt von der Ursache, verlustfreie Verteilung der Hinweise und **zwei
Jobs auf zwei Rechnern** (erste 20 und Zufallsstichprobe).

**Dritter Lauf** ([40132947135](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40132947135), 24.10.2026, 23:09–23:31 Uhr, Commit `fbe62ad`) – **unvollständig**, Job rot:
404 US-Aktien ausgewählt (254 aus den ersten 20 einer Rangliste, 150 zufällig); **121 blieben ohne Antwort von Nasdaq**
(Verbindungsfehler, auch nach Pausen von 30 und 90 s – nachgeholt 0; ebenso alle 43 Abfragen der Nasdaq-Dividenden), 25
ohne Kurse bei Nasdaq. Die US-Aktien unter den ersten 10 waren vollständig (157: 147 verglichen, 10 ohne Nasdaq-Kurse, 0
ohne Antwort); ob die 121 alle zur Zufallsauswahl gehörten, zählte dieser Lauf nicht. Ergebnisse: offizieller
Schlusskurs bei 139 Nasdaq-notierten Aktien an 9.533 Tagen – Stand gleich 9.239 (96,9 %), ungleich 276, Faktor eines
Splits 18; gegen die Nasdaq-Historie 17.787 Tage, abweichend 491, belegt 231, ungeklärt 260 (248 davon bei Aktien der
NYSE-Gruppe). Ranglisten: (a) mit Nasdaq-Kursen Platz 1 in keiner anders, andere Aktien unter den ersten 10 in 2, andere
Reihenfolge der ersten 10 in 14; (b) mit dem offiziellen Schlusskurs **Platz 1 in 4 Ranglisten anders**, andere Aktien
unter den ersten 10 in 6, andere Reihenfolge in 33 – **in welchen Ranglisten und mit welchen Aktien, zeigte der Lauf
nicht.** Deshalb (Commit `c27d225`): zuerst die Aktien unter den ersten 10 abfragen (die häufigsten zuerst), bei vier
Aktien hintereinander ohne Antwort von Nasdaq 180 s Pause und doppelter Abstand (1 s, höchstens 3 s), Nachholrunden nach
60 und 180 s, Abruf je Gruppe und Art des Netzfehlers zählen, jede geänderte Rangliste einzeln ausgeben (Zeitraum, Gruppe,
Gewichtung, Buchstaben), Wirkung je Aktie in beiden Varianten, auch für Aktien mit nur anderem offiziellem Schlusskurs;
höchstens 10 Hinweise, Weggelassenes gezählt (4 neue Tests).

**Zweiter Lauf** ([40128434473](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40128434473), 22:08–23:08 Uhr): nach 60 Minuten von GitHub abgebrochen, ohne Ergebnis (Überblick).

**Erster Lauf** ([40126582787](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126582787), 24.10.2026, 21:43–21:52 Uhr) – **unvollständig**: 404 Aktien ausgewählt,
71 ohne Antwort von Nasdaq (Verbindungsfehler), 33 ohne Kurse bei Nasdaq; von 20.685 verglichenen Börsentagen wichen 525
ab, belegt 239 (232 × Yahoo nicht der offizielle Schlusskurs bei Nasdaq = NOCP, 6 × kein Umsatz und Kurs des Vortags, 1 ×
Stand = letzter Abschluss vor 16:00 Uhr), ungeklärt 286; Ranglisten mit den Nasdaq-Kursen: 1.640 von 1.980 neu gerechnet,
Platz 1 in keiner anders, andere Aktien unter den ersten 10 in 2, andere Reihenfolge der ersten 10 in 14. Der Job war
trotz der fehlenden Antworten grün – **behoben**: Nachholrunden mit Pause, Zeitbudget, rot bei unvollständigem Abruf oder
ungeklärten Tagen; dazu der Vergleich mit dem NOCP an allen Tagen, „Stand = NOCP“, Anzeigegenauigkeit, Minutenkurse für
58 Tage und die Ranglisten auch mit dem offiziellen Schlusskurs.

### 8f. Kurslauf-Kontrolle: fehlerfrei gelaufenes Prüfskript ist keine Abnahme

Ab 1.18 meldet die Kontrolle das fachliche Gesamtergebnis ausdrücklich („Abnahme Kurslauf: BESTANDEN / NICHT BESTANDEN /
AUSSTEHEND“) und macht daraus einen eigenen Schritt „Abnahme (fachliches Gesamtergebnis)“, der nur bei „bestanden“ grün
ist; der Schritt „Prüfskript“ zeigt getrennt, ob das Skript selbst fehlerfrei lief (02_Einrichtung, „Kurslauf kontrollieren“).

| Lauf der Kontrolle | Geprüft | Prüfskript | Abnahme |
|---|---|---|---|
| [40116914676](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116914676), 24.10.2026, 19:36 Uhr | Täglicher Lauf 40104747674 (von Hand, Stand 23.10.) | fehlerfrei | **NICHT BESTANDEN** (Workflow rot): 7 von 10 Kriterien – nicht erfüllt: zeitgesteuert (von Hand), alle Notierungen in diesem Lauf abgefragt (49 offen, 11.096 aus dem Checkpoint), Tempo über mindestens 10.000 Abrufe (nur 49 Abrufe). Erfüllt u. a.: Stand vollständig veröffentlicht, jede Notierung mit Ergebnis (11.145 von 11.145, 0 Abruf- und Einzelfehler), 0 × HTTP 429, „berechnen“ 5,8 min, status.json mit dem Stand und Signal-Stand `20261024T150300Z` dieses Stands |
| [40116916313](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40116916313), 24.10.2026, 19:36 Uhr | offizielle Läufe seit 26.10. | fehlerfrei | **AUSSTEHEND** (Workflow rot): noch kein zeitgesteuerter Lauf – nichts bestanden |
| [40126752930](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126752930), 24.10.2026, 21:45 Uhr (mit der neuen Anzeige) | Täglicher Lauf 40104747674 | fehlerfrei | **NICHT BESTANDEN** (Workflow rot), 7 von 10 Kriterien. Tempo jetzt mit allen Mindestanforderungen: „Abrufe 49 (verlangt mindestens 10.000: NICHT erfüllt); Messdauer 6 s; Geschwindigkeit 8,1 je Sekunde (verlangt mindestens 6: erfüllt); gleichzeitig über 2 Hosts ja (verlangt ja: erfüllt; laut Lauf „4 gleichzeitig über 2 Hosts, Abstand 0.25 s je Host“)“ |
| [40126755036](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40126755036), 24.10.2026, 21:45 Uhr | offizielle Läufe seit 26.10. | fehlerfrei | **AUSSTEHEND** (Workflow rot): „Noch kein zeitgesteuerter Kurslauf mit Abruf aller Notierungen seit 2026-10-26 (0 offizielle Läufe geprüft) – nichts bestanden“ |

**Tempo-Kriterium – alle Mindestanforderungen** (02_Einrichtung, „Kurslauf kontrollieren“): mindestens **10.000 Abrufe** in
diesem Lauf, **mindestens 6 je Sekunde** über die ganze Messdauer und **gleichzeitig über 2 Hosts**. Der bisher einzige
tägliche Lauf mit gleichzeitigem Abruf (40104747674) hatte 49 Abrufe in 6 s (8,1 je Sekunde, über 2 Hosts) – zu wenige
Abrufe, das Kriterium ist **nicht erfüllt**. Der Messlauf über alle Notierungen (24.10., 12:44–13:11 Uhr: 10.845 Abrufe in
1.355,9 s = 8,0 je Sekunde, 0 × HTTP 429, Überblick oben) war nur lesend und kein täglicher Lauf – er zählt nicht als Abnahme.

Gefunden und behoben (1.18.1): Beim Tempo stand ein ✗ neben „49 Abrufe in 6 s = 8,1 je Sekunde“, ohne dass zu sehen war,
warum – verlangt sind zusätzlich mindestens 10.000 Abrufe. Seit 21:44 Uhr nennt die Kontrolle jede Mindestanforderung mit
Ist-Wert und „erfüllt“/„NICHT erfüllt“ (Test `test_tempo_needs_the_full_fetch_and_says_why`: zu wenige Abrufe, zu
langsam, nicht gleichzeitig – jeweils einzeln), und die Laufübersicht hat einen Abschnitt **„Prüfstatus“**, getrennt nach
fachlicher Abnahme, nicht erfüllten Kriterien, erfüllten Kriterien, Ausstehendem und Prüfskript („fehlerfrei ausgeführt –
das ist weder ein Softwaretest noch eine Abnahme“; Tests `test_failed_acceptance_is_not_hidden_behind_a_successful_script`
und `test_pending_when_no_scheduled_full_run_exists`). Die Abnahme des ersten zeitgesteuerten Laufs prüft die
eingerichtete Aufgabe am 27.10.2026 um 09:30 Uhr (Abschnitt 8, Zeile „Nachtlauf“).

## 9. Erweiterungen 1.1 bis 1.5: Prüfungen aus den Aufträgen

| Vorgabe | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Aktie mit hoher Rendite und niedrigem Umsatz erscheint nur in Ranking 1 | `test_turnover.TwoReturnRankingsTests.test_low_turnover_top_return_only_in_ranking_1`; E2E `test_turnover_filter_tab_and_low_turnover_flags` (Kennzeichen „sehr niedriger Umsatz“) |
| Liquide Aktie erscheint in beiden Rankings | `test_liquid_stock_appears_in_both`; Vertrag „Zwei Rendite-Ranglisten“ |
| Fehlende Volumendaten verhindern Ranking 2 (und werden nicht als null gezählt) | `test_missing_volume_or_fx_prevents_ranking_2`, `TurnoverDefinitionTests.test_missing_volume_data_prevents_a_value`, `test_missing_sessions_are_not_counted_as_zero`, `test_reported_zero_volume_counts_as_zero_but_needs_16_positive_sessions` |
| Ohne Wechselkurs keine Aufnahme in Ranking 2, Ranking 1 bleibt | `test_missing_or_stale_fx_rate_prevents_usd_value`, `test_fx_conversion_decides_admission`; Rückfall auf gespeicherte EZB-Kurse: `test_ecb.DailyRunFxTests` |
| Wochenenden und Feiertage verschieben die angezeigten Vergleichsdaten korrekt | `test_weekend_and_holiday_move_start_dates`, `test_weekend_session_uses_previous_ecb_rate`; E2E `test_weekend_start_dates_in_return_rankings` |
| Beide Rankings: gleicher Stichtag, gleiche Formel, gleiche ungerundete Werte | `test_same_cutoff_formula_and_order`; Veröffentlichungsprüfung `ranking2_teilmenge_gleiche_rendite` in jedem Lauf; `test_pipeline.test_T47_overview_windows_series_and_frequency_agree`; Vertrag |
| Bestehende Qualitätsregeln gelten weiter | `test_existing_quality_rules_still_apply_to_ranking_1` |
| Kapitalmaßnahmen verzerren den Umsatz nicht | `test_split_inside_the_20_sessions_is_not_distorting_the_value` |
| Übernahmesprünge werden gekennzeichnet | `TakeoverPatternTests` (4 Tests) |
| Darstellung: Sieger → Top 10 → vollständige Liste, getrennte Zählungen | E2E `test_return_rankings_winner_top10_and_full_list`, `test_detail_shows_turnover_and_both_return_ranks` |
| Häufigkeit nennt Universum und Umsatzfilter, keine Vermischung | E2E `test_frequency_names_universe_and_turnover_filter`; Vertrag „Häufigkeit mit Umsatzfilter“ |
| **Auffällige Kursabweichungen zwischen Börsenplätzen (1.2, 1.5.1, 1.5.2)** | `test_venues` (21 Tests: Wahl des Platzes, Schwellen, Endkurs, Umrechnung, fehlende Kurse, Börsenkalender des zweiten Platzes, Umsatz und Schwelle nach Tagesschwankung); `test_pipeline.test_second_venue_flags_deviations_without_changing_returns_or_ranks`, `…_missing_failed_or_throttled_…`, `…_statuses_without_reuse`; Veröffentlichungsprüfung `boersenplatz_kennzeichen`; Vertrag „Zweiter Börsenplatz“; E2E `test_second_venue_deviation_in_lists_detail_and_status` |
| **Jederzeit aktualisieren (1.2, dein Wunsch vom 13.10.)** | `test_update` (5 Tests); `test_pipeline.test_status_names_next_possible_cutoff`; App-Funktionstest „Aktualisieren auf Wunsch“; E2E `test_update_on_demand_starts_on_github_and_reports_result` und `test_T59_first_use_without_snapshot_shows_setup_state` |

### Gruppenvergleich A/B (1.4, dein Auftrag „Beide Aktiengruppen über 1–30 Tage vergleichen“)

| Vorgabe (Punkt 7: „Prüfe insbesondere …“) | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Elf Gewichtungen in beiden Gruppen | Veröffentlichungsprüfungen `elf_gewichtungen` und `gruppe_b_eigene_vergleichsmenge`; `test_ranking.GroupBTests`; Vertrag „Gruppe B“ (Scores bitgleich) |
| Beide Umsatzgruppen getrennt, gleiche Formeln | `test_pipeline.test_group_b_in_windows_overview_frequency_and_series` (nur Aktien aus L, U ∩ L, 0/100 und 100/0 wie Gruppe A); `GroupBTests.test_mixed_weights_may_order_differently_than_filtering_group_a` dokumentiert die eigene Vergleichsmenge |
| Wiederholungszählung (Platz 1, Top 3, Top 10 je Rangliste höchstens einmal, nicht addiert) | App-Funktionstest „Gruppenvergleich“; Vertrag: Zählung = Serverreferenz für A und B; E2E `test_group_matrix_tabs_marks_list_frequency_and_identical_windows` |
| Wochenend-Doppelungen | Funktionstest (1 und 2 Tage mit gleichem Start → „≡“, „nur einmal zählen“ zählt einmal); Vertrag: „≡“ nur bei gleicher Aktie und gleichem Start; E2E (Hinweis zusammengefasster Fundstellen) |
| ISIN-Zuordnung | Kennzeichnung und Zählung über den Instrumentindex (= ISIN); E2E: markierte Zellen = Zellen mit derselben ISIN; Identitätsprüfungen unverändert (`test_providers`) |
| Fehlende Gleichmäßigkeitsdaten | Leerzustand `zu_wenig_tagesdaten` in Gruppe A und B (`test_pipeline`, E2E „nicht berechenbar: weniger als 15 Tageskurse“); keine Scores zum Füllen |

### Umschichtungs-Regel (1.3, deine Frage vom 13.10.)

| Vorgabe | Nachweis (alle bestanden am 13.10.2026) |
|---|---|
| Regel nur auf Aktien mit Ø Umsatz ≥ 10 Mio. USD, 5 Aktien je 20 %, monatlich, 3-Monats-Trend | `test_rotation.SelectionTests`, `BacktestTests.test_holds_the_best_and_keeps_within_buffer`; Standardvariante in `test_pipeline.RotationPipelineTests` |
| Tagesvorschlag: welche Aktie zu wie viel Prozent kaufen, was (teilweise) verkaufen, mit Grund | `PreviewTests`, `test_decision_on_the_last_friday_stays_pending`; App-Funktionstest „Umschichtungs-Regel“; E2E `test_rotation_rule_today_backtest_variants_and_own_amounts` |
| Kein Rechnen mit dem Kurs, der das Signal erzeugt hat | `test_trades_at_first_close_of_next_week_not_at_the_signal_close`; Vertrag: Ausführung jeder Order nach dem Entscheidungstag |
| Kosten und Steuern wie bei der Bank | `CostAndTaxTests` (Spanne, 1 €, Pauschbetrag, Erstattung im Jahr, Freigabe des Pauschbetrags, Verlusttopf) |
| Regel wird bei jedem Stand nachgeprüft | Veröffentlichungsprüfung `umschichtung_regel_eingehalten`; `test_pipeline.test_rule_files_are_complete_consistent_and_match_the_series` |
| Rückblick bei Drosselung, Split und fehlender EZB-Reihe | `test_long_history_is_loaded_in_stages_stored_weekly_and_refreshed_after_splits`, `test_T43_T44_throttling_checkpoint_and_resume_same_cutoff`, `test_ecb.test_history_outage_only_shortens_the_review` |

### Auftrag vom 13.10.2026 (1.5): die 20 verbindlichen Prüfungen

„Bestanden“ heißt: in der Entwicklungsumgebung am 13.10.2026 mit DEMO-Daten ausgeführt und grün (Abschnitte 1–3). Prüfung 13 ist **nicht ausgeführt**, Prüfung 17 nur in der Emulation.

| Nr. | Prüfung | Nachweis | Ergebnis |
|---:|---|---|---|
| 1 | 1–90 als Kalenderzeiträume, Wochenenden und Feiertage | `test_windows` (T21–T25, T27), E2E `test_weekend_start_dates_in_return_rankings`, E2E Prüfung 19 (Ziel-Start = Stichtag − h Kalendertage) | bestanden |
| 2 | Endkurs gehört zum Stichtag, keine aufgefüllten Sitzungen | `test_windows.test_T03…`, `test_T28…`; `pure.test.ts` T67/T68/T76 | bestanden |
| 3 | Renditeformel, Währungs- und Splitbasis | `test_metrics` (T01, T02), `test_quality` (T32, T33), Vertrag „Rendite = Endkurs / Startkurs − 1“ | bestanden |
| 4 | Preis-OLS, Steigung, R², Rauschen, größter Rückgang | `test_metrics` (Referenz mit exakter Bruchrechnung und `numpy.polyfit`) | bestanden |
| 5 | Zu kurze Historie: Rendite ja, Gleichmäßigkeit nein | `test_windows.test_T24…`, `test_quality.test_T04…`; E2E Prüfung 19/20 („nicht berechenbar“ bei 7 und 14 Tagen) | bestanden |
| 6 | Fallende Gerade trotz hohem R² nicht im Aufwärtsranking | `test_quality.test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings` | bestanden |
| 7 | Elf Gewichte, Perzentile, mittlere Ränge, N = 0 / N = 1, stabile Sortierung | `test_ranking` (T12–T20, T79–T85, `TieRuleTests`), Vertrag „Scores bitgleich“ | bestanden |
| 8 | Getrennte Normalisierung A/B, 20-Sitzungen-Grenze mit Währungseinheiten | `test_ranking.GroupBTests`, `test_turnover` (Pence, Wechselkurse, 16 von 20) | bestanden |
| 9 | Kein falscher B-Eintritt bei unvollständigem Volumen oder ungeklärtem Split | `test_turnover.test_missing_volume_or_fx_prevents_ranking_2`, `test_split_inside_the_20_sessions_is_not_distorting_the_value`; `test_quality.test_1_7_*` und `test_T32/T33` (Fenster zurückgehalten) | bestanden |
| 10 | Keine doppelte ISIN; 0/100 nicht doppelt gezählt | `test_frequency.test_T88…`, Veröffentlichungsprüfungen, E2E (markierte Zellen = Zellen derselben ISIN) | bestanden |
| 11 | Zähler, Nenner, Zeitfilter, Bereinigung identischer Fenster | Vertrag „frequency-v2“ und „Gruppe B“; `pure.test.ts` Gruppenvergleich; E2E `test_frequency_filters_order_counts_and_exports` | bestanden |
| 12 | Zählsummen passen zur Zahl tatsächlicher Ranglisten | `test_frequency` (T90 Invarianten), Vertrag T90/T92/T93, Vertrag „nur einmal zählen“ (Nenner = verschiedene Fenster), E2E Nenner = Nachzählung | bestanden |
| 13 | Import des historischen Prüffalls reproduziert dessen Ergebnisse | `tests/live/ausgangsmodell_nachrechnen.py` (ab 1.17) | **für den 12.10. nicht ausgeführt** (Archiv fehlt, Abschnitt 8c); für den 13.10. mit den Rechendaten aus der HTML-Übersicht ausgeführt – kein Ersatz für das Archiv |
| 14 | Wiederaufnahme nach Abbruch, Anbieterlimit, fehlgeschlagenem Lauf | `test_pipeline.test_T43_T44…`, `test_T44_provider_outage…`, `test_ci_flow` | bestanden |
| 15 | Atomare Veröffentlichung ohne vermischte Stichtage | `test_pipeline` (Absturz beim Schreiben, T45–T47), Veröffentlichungsprüfungen | bestanden |
| 16 | Keine Geheimnisse in App, Protokoll, Exporten | `test_providers.test_T52…`, `test_pipeline.test_T52…`, `test_ci_flow`, `verify-site`, E2E Metadaten-Export | bestanden |
| 17 | Mobil, Touch, Suche, Gruppen, alle 90 Fenster, Matrizen, Charts | 49 Browser-Tests (Abschnitt 3) | bestanden **nur in der Emulation** (384 × 832, 832 × 384, 1280 × 800); echtes S25+ offen |
| 18 | Chartdaten = Beobachtungen; Indexbasis und Achsen beschriftet | E2E T75/T78, T66/T69/T70, Prüfung 19 (Grafik = Fenster der Aktie) | bestanden |
| 19 | Zehn feste Tasten wählen exakt ihr Kalenderfenster; alles wechselt gemeinsam | E2E `test_spec19_fixed_chips_select_exact_calendar_window` | bestanden |
| 20 | Zehn-Fenster-Übersicht = vollständige Ranglisten je Gewichtung und Gruppe; Zählung getrennt | Vertrag „Prüfung 20“ (alle 11 Gewichtungen, A und B), E2E `test_spec20_winners_by_window_match_full_rankings` | bestanden |

## 10. Abnahmetests T01–T100: Zuordnung

„E2E“ = Browser-Emulation (Abschnitt 3), „Vertrag“ = App-Datenvertragstest (Abschnitt 2). Alle genannten Tests liefen am 12. und erneut am 13.10.2026 (zuletzt Version 1.5.0) und waren grün, sofern nicht anders vermerkt.

| Test | Nachweis |
|---|---|
| T01, T02, T05, T07, T10, T11 | `test_metrics`: test_T01…, test_T02…, test_T05…, test_T07…, test_T10…, test_T11… |
| T03, T21–T24, T27, T28 | `test_windows`: je ein gleichnamiger Test; T21 zusätzlich `test_quality.test_window_lengths_above_90_are_rejected_in_core` |
| T04 | `test_quality.test_T04…`; E2E `test_ranking_window_weight_and_empty_reason` |
| T06 | `test_metrics.test_T06…` (R² ≈ 1) und `test_quality.test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings` |
| T08, T09, T29–T33, T35 | `test_quality`: gleichnamige Tests (T29 und T32 je zwei) |
| T12–T20 | `test_ranking`: gleichnamige Tests; T20 zusätzlich Vertrag (Untergruppe) und E2E Watchlist-Untergruppe |
| T25 | `test_windows.test_T25…` (Feiertage je Börse), `test_providers.DaylightSavingTests` (Sommerzeitwechsel USA/Europa); echte Kalender: `tests.live.test_calendars_live` in GitHub Actions, 4 von 4 bestanden (Abschnitt 7) |
| T26 | `test_providers.test_T26_running_session_does_not_replace_final_close`, `test_T26_session_final_checker` |
| T34 | `test_providers.test_T34_dividend_adjusted_close_is_kept_separate` |
| T36 | `test_providers.test_country_preference_and_T36_one_reference_per_isin`, `test_frequency.test_T88_duplicate_isin_listings_are_rejected_upstream` |
| T37 | `test_pipeline.test_T37_ticker_change_keeps_name_isin_and_one_ranking_entry` |
| T38, T40 | `test_engine_coverage`; T40 zusätzlich `test_pipeline.test_idempotent_rerun_creates_no_second_snapshot` |
| T39 | `test_metrics.test_T39…` (exakte Bruchrechnung, `numpy.polyfit`); Vertrag: App-Scores bitgleich |
| T41 | `test_pipeline.test_T41_T60…`, `test_ci_flow`; echte Läufe in GitHub Actions am 13.10.2026 manuell gestartet (Abschnitt 7); geplante Läufe seit 15.10.2026 (Auslöser „schedule“, Überblick) |
| T42 | `test_pipeline` (Doppelstart, verwaiste Sperre), `test_ci_flow`, `test_workflows.test_T42…` |
| T43, T44 | `test_pipeline.test_T43_T44…`, `test_T44_provider_outage…`; `test_providers` (Retry-After, Dauerdrosselung, Zeitüberschreitung); `test_ci_flow.ReleaseReplaceTests` |
| T45, T46, T47 | `test_pipeline` (gleichnamig); T45 zusätzlich `test_providers.test_T45_guards…`; T47 zusätzlich E2E T64/T99 |
| T48, T49 | E2E `test_offline_after_first_visit`, `test_T49…` |
| T50 | `pure.test.ts` (Name, Alias, Ticker, ISIN); `test_pipeline.test_T37…` (alter Ticker bleibt suchbar) |
| T51 | E2E 90 Zeilen, T100, T66/T69/T70, 44-px-Ziele – Emulation; Gerät offen |
| T52 | `test_pipeline.test_T52…`, `test_providers.test_T52_secrets_are_redacted_in_logs`, `test_ci_flow`, `test_workflows.test_T52…`, `verify-site` |
| T53 | `test_workflows.test_T53…` (zwei Tests): Läufe nur per Zeitplan oder durch Berechtigte; es gibt keine Server-Schnittstelle, über die Dritte einen Lauf auslösen könnten |
| T54 | `pure.test.ts` (Formel-Injection), E2E CSV-Export |
| T55 | `test_pipeline.test_T55…`, `test_ci_flow`, `restore-test` (Abschnitt 5) |
| T56, T59 | `test_pipeline` und E2E (gleichnamig) |
| T57 | `pure.test.ts` „Prozentformat“: 0 → „0,00 %“ und „unverändert“, fehlend → „–“ und „nicht berechenbar“ |
| T58, T83 | `test_ranking.test_T83_native_zero_may_show_only_negative_returns` |
| T60 | `test_pipeline.test_T41_T60…`, E2E `test_T60_demo_is_marked_in_every_view`, CSV- und PNG-Test |
| T61, T62, T64, T71, T77, T99, T100 | E2E gleichnamig (T77 nur Emulation) |
| T63 | E2E `test_one_day_window_shows_only_daily_closes` |
| T65, T67, T68 | `pure.test.ts` |
| T66, T69, T70 | E2E `test_T66_T69_T70_grid_units_scales_and_full_labels` |
| T72, T74 | E2E `test_T72_T74…`: kein Livefeed eingerichtet und so beschriftet; alle Charts laufen ohne Livevertrag |
| T73 | entfällt: Es gibt keinen Livefeed, also keine Liveupdates |
| T75, T78 | E2E `test_T75_T78…` |
| T76 | `pure.test.ts` T67/T68: kein Auffüllen fehlender Tage, Lücken unterbrechen die Linie |
| T79–T85 | `test_ranking` (gleichnamig); T79 und T80 zusätzlich `pure.test.ts` (Parameterprüfung mit alten Aliasnamen); T81 zusätzlich Vertrag |
| T86–T98 | `test_frequency` (gleichnamig; T92 im Invariantentest); T90, T92–T95 zusätzlich Vertrag; E2E Häufigkeitsliste = Serverberechnung |
