"""AktienPilot – Spielgeld-Robo mit eigenen Regeln aus den Analysewerten der App (Auftrag docs/13_AktienPilot.md,
Gesamtfassung 31.10.2026, Abschnitte 29–32).

Getrennte Fachmodule (Abschnitt 3) – vorhanden:

* ``config``      Konfiguration ``config/aktienpilot.yaml`` mit Prüfung (Nullbudget, Grenzen, Strategieparameter)
* ``katalog``     zentraler Kennzahlenkatalog: jede Analysegröße genau einmal, dieselbe Berechnung wie Rangliste und Chart
* ``regeln``      Regel-Baukasten: Schema ``tr-regel/1``, Prüfung, Versionen, Kopie (kein freier Code)
* ``auswertung``  Kandidaten, dreiwertige Filter (UND/ODER/NICHT), Sortierung, Score, Auswahl, freiwillige Ausstiege
* ``gewinnziel``  Gewinnmitnahme +30/+50/+100 % oder eigener Wert, ganz oder als Leiter
* ``vorlagen``    S1–S3, Lineal-Vorwärtsdepot und Beispielregeln als gewöhnliche Regeln
* ``indikatoren`` gleitende Durchschnitte, ATR, RSI, Regression logarithmierter Kurse, Perzentile, Übernachtlücken
* ``markt``       Marktdaten je Aktie (OHLCV, splitbereinigt), Wechselkurse, Leitindizes
* ``zeitregel``   Ausführungsprofile TAGESDATEN, VERZOEGERTER-EINSTIEG, FOLGETAG-SCHLUSS mit Börsenkalendern
* ``kosten``      Gebühren, Spread, Slippage, Währungs- und TR-Aufschlag
* ``buchhaltung`` Depotstand aus dem unveränderlichen Ereignisjournal (Töpfe, Positionen, FIFO-Lose, Bewertung in EUR)
* ``risiko``      zentraler Risiko-Manager (Stückzahl aus allen Grenzen, Verlustgrenzen)
* ``ausfuehrung`` interner PAPER-Simulator (Kosten, Liquidität, Teilausführung, Stops mit Kurslücke)
* ``motor``       gemeinsamer Tagesschritt für Vorwärts-PAPER, historische Simulation und DEMO; Robo-Kern
* ``speicher``    Tabellen ``ap_*`` (Migration 0010), eine Transaktion je Tagesschritt, Neustart aus dem Journal

Geplant (siehe docs/13_AktienPilot_Umsetzungsstand.md): Einbindung in den täglichen Lauf mit verschlüsselter
Veröffentlichung, Backtest-Labor, sicherer Ereignisweg vom Handy, Steuermodell und Export.

Kein Echtgeld: keine Orders an Trade Republic oder einen anderen Broker, keine inoffiziellen Schnittstellen, keine
kostenpflichtigen Dienste. LIVE ist reine Zukunftsspezifikation (Abschnitte 22 und 27) und nicht auswählbar.
"""

AP_VERSION = "aktienpilot-0.2.0"
