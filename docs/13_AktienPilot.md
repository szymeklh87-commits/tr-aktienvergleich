Du bist ein erfahrener Quant-Entwickler und Software-Architekt. Entwickle „AktienPilot“ als integrierte Erweiterung meiner bestehenden Aktien-App „Aktien-Kompass / Lineal-Ranking“.

Repository: https://github.com/szymeklh87-commits/tr-aktienvergleich

AktienPilot erhält einen eigenen Bereich in der bestehenden PWA und klar getrennte Backend-Module. Die vorhandene Datenversorgung, Verschlüsselung, Veröffentlichung und getesteten Berechnungen werden weiterverwendet.

AktienPilot soll Aktien analysieren, nachvollziehbare Kauf- und Verkaufsentscheidungen berechnen, automatisch Musterdepots führen und später über geeignete Broker handeln können.

App-Sprache: Deutsch. Depotwährung: Euro. Geräte: Samsung Galaxy S25+ und Windows-PC. Möglichst wenig Einrichtung; keine Pflicht-Abonnements für SIGNAL und internen PAPER-Betrieb.

0. Arbeitsgrundlage und Vorrang
- Binde zuerst das Repository ein und lies gegebenenfalls vorhandene AGENTS.md-Dateien, README, docs/, Konfiguration, Workflows und relevanten Code. Falls das Repository umbenannt wurde, frage mich. Ist der Zugriff nicht möglich, bitte um einen ZIP-Upload.
- Arbeite auf einem eigenen Branch mit Pull Requests. Keine direkten Änderungen an main, kein automatisches Zusammenführen und keine Veröffentlichung neuer Produktivfunktionen ohne meine Zustimmung.
- Lege diesen Auftrag unverändert unter der nächsten freien Nummer als docs/NN_AktienPilot.md ab. Die Nummer 12 ist bereits durch docs/12_Fehlende_Kurstage.md belegt. Überschreibe keine vorhandene Dokumentation.
- Diese Auftragsdatei ist die Grundlage für spätere Chats. Ergänze Umsetzungsstand und Entscheidungen in einer separaten Datei. Änderungen am Auftrag benötigen meine Zustimmung.
- Bestehende, getestete Lösungen haben Vorrang vor vorgeschlagenen neuen Bibliotheken oder Architekturänderungen. Abweichungen müssen begründet, dokumentiert und getestet werden.
- Melde Widersprüche. Wähle bis zur Klärung eine Auslegung, die neue risikosteigernde Transaktionen verhindert und bestehende Schutzmaßnahmen erhält.

1. Ziel und verbindliche Grundsätze
- Ziel ist eine möglichst hohe Rendite nach Handelskosten und unter dokumentierten Steuerannahmen innerhalb festgelegter Risikogrenzen.
- Hauptvergleich ist Kaufen und Halten eines konkret ausgewählten MSCI-World-UCITS-ETF. Speichere ISIN, Notierung, Währung und Ausschüttungsart. Vergleiche identische Zeiträume, Kapitalzuflüsse und Bewertungsgrundlagen.
- Für den Robo-Kern wird zusätzlich eine Referenz mit gleicher Aktien-/Geldmarktaufteilung verwendet. Der MSCI-World-Vergleich bleibt sichtbar.
- Erfinde keine Kurse, Renditen, Erfolgsquoten oder Testergebnisse. Unterscheide Messwerte, historische Simulationen, Annahmen und synthetische Testdaten.
- Vergangene Überlegenheit ist keine Garantie zukünftiger Gewinne. Nicht ausreichend geprüfte Strategien dürfen keine neuen Echtgeld-Kaufanweisungen erzeugen – auch nicht im SIGNAL-Modus.
- Risikosenkende Maßnahmen für bereits verwaltete Positionen dürfen durch eine fehlende oder zurückgesetzte Strategiefreigabe nicht pauschal blockiert werden.

2. Bestehenden Stand bestätigen und erhalten
- Prüfe insbesondere den bekannten Aufbau: Python-Paket traktien unter backend/, TypeScript-/React-PWA unter app/, unittest- und npm-Tests, Konfiguration unter config/, verschlüsselte SQLite-Sicherung in Release-Assets und verschlüsselte Veröffentlichung über GitHub Pages.
- Der zuletzt geprüfte Workflow verwendet Python 3.13. Übernimm die tatsächlich vorhandene, getestete Version; führe keinen unbegründeten Versionswechsel durch.
- Der vorhandene Zeitplan lautet: regulärer Lauf um 07:00 Europe/Berlin, Wiederholungen um 07:15, 07:45 und 09:00 sowie Nachtlauf Montag bis Freitag um 22:37 UTC. Bestätige den aktuellen Codezustand und erhalte diese Abläufe, soweit kein begründeter Änderungsbedarf besteht.
- Prüfe vorhandene Funktionen für Abdeckung, Konsistenz, Herzschlag, Sicherung, Veröffentlichungsprüfung und Geheimnisschutz.
- Erhalte Rankings, Kursvergleiche, Häufigkeitslisten, Depotrechnungen, Exporte und historische Ergebnisse.

3. Referenztests und Methodenversionen
- Bekannte externe Referenz: Zwei_Zehnerdepots_1_bis_30_Tage_Beitraege.html, Auswertung vom 30.10.2026, Modell TR-90D-11W-two-universes-v1.1.
- Die bestehende App enthält bereits bewusst beschlossene Weiterentwicklungen, unter anderem zu fehlenden Kurstagen, letzten verfügbaren Schlusskursen und exakter Gleichstandsbehandlung.
- Reproduziere deshalb jeden archivierten Referenzstand mit seiner damaligen Methodenversion. Erzwinge keine Gleichheit zwischen unterschiedlichen Methoden.
- Ergänze einen Golden-Master-Test für die aktuelle Methode auf einem fest gespeicherten Datenstand. Dokumentiere erwartete Unterschiede zum Ausgangsmodell ausdrücklich.
- Fehlen notwendige Originaldaten, melde die fehlende Referenzprüfung. Behaupte keinen bestandenen Vergleich. Andere unabhängige Arbeiten dürfen weitergehen; Änderungen am betroffenen Rankingkern bleiben bis zu ausreichender Absicherung zurückgestellt.
- Archiviere künftig Referenzdaten, Quellenstände, Konfiguration, Methodenversion und erwartete Ergebnisse.
- Korrigiere nachgewiesene Fehler mit Tests und Versionsangabe. Keine stillen Formeländerungen und keine nachträgliche Überschreibung historischer Ergebnisse.

4. Architektur und Betriebsstufen
- Stufe 1 umfasst SIGNAL und PAPER innerhalb der bestehenden GitHub-Actions-Pipeline und verschlüsselten PWA. Dafür ist kein dauerhaft eingeschalteter eigener Rechner erforderlich.
- Stufe 2 umfasst optional LIVE ab P7: ein eigener Dienst mit FastAPI, APScheduler und SQLite auf einem dauerhaft verfügbaren Rechner. Er verwendet dieselben geprüften Fachmodule.
- Trenne Daten, Strategie, Portfolio, Risiko, Ausführung, Steuern und Darstellung. Halte neue AktienPilot-Tabellen und Module klar von bestehenden Rankingfunktionen getrennt.
- Behalte das vorhandene Konfigurationsformat bei und erweitere dessen Validierung. Neue Bibliotheken nur bei begründetem Nutzen.
- Geheimnisse gehören in GitHub Secrets beziehungsweise die .env der LIVE-Stufe. Keine Geheimnisse im Repository, Build, Log oder veröffentlichten Datenbestand.
- Ist das Code-Repository öffentlich (GitHub Pages im kostenlosen Konto setzt das voraus), sind Workflow-Logs, Artefakte, Pull-Request-Texte und Commit-Nachrichten öffentlich einsehbar. Depot-, Positions- und Bestätigungsdaten erscheinen dort nie im Klartext – auch nicht in Fehlermeldungen oder Testausgaben.
- Implementiere Transaktionen, Migrationen, Sicherungen und gemeinsame Schreibsperren. Täglicher Lauf, Bestätigungsverarbeitung und Veröffentlichung dürfen sich nicht gegenseitig überschreiben.
- Das Handy zeigt Ergebnisse, entschlüsselt Daten und erfasst Eingaben. Handelsberechnungen und verbindliche Risikoprüfungen erfolgen im Backend.

5. Betriebsmodi und gemeinsame Schnittstelle
- SIGNAL ist der Standard für Trade Republic. Es werden keine Orders an Trade Republic übertragen.
- Ein Signal enthält ISIN, Name, Richtung, Stückzahl, Referenzkurs mit Quelle und Zeitstempel, Limit, Stop, Gültigkeitsdauer, Ausführungsprofil und Begründung. Kurse anderer Börsen werden nie als ausführbare TR-Kurse bezeichnet.
- Ich führe die Order selbst aus und bestätige Stückzahl, Preis, Zeitpunkt und Gebühren. Unterstütze Teilausführungen, Überspringen, Storno und die Bestätigung eines gesetzten Stops.
- PAPER verwendet zunächst einen internen Simulator im täglichen Lauf. Ein optionaler Alpaca-Paper-Adapter folgt später. Ergebnisse verschiedener Simulatoren bleiben getrennt.
- LIVE wird für Alpaca, eToro Public API und Interactive Brokers über ib_async und IB Gateway vorbereitet. Implementiere z