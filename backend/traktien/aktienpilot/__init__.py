"""AktienPilot – Analyse, nachvollziehbare Kauf- und Verkaufsentscheidungen, vorwärts laufende Musterdepots (Auftrag
docs/13_AktienPilot.md, Fassung 31.10.2026).

Getrennte Fachmodule (Abschnitt 3):

* ``config``      Konfiguration ``config/aktienpilot.yaml`` mit Prüfung (Nullbudget, Grenzen, Strategieparameter)
* ``indikatoren`` Gleitende Durchschnitte, ATR, RSI, Regression logarithmierter Kurse, Perzentile, Übernachtlücken
* ``markt``       Marktdaten je Aktie (OHLCV in Notierungswährung, splitbereinigt), Wechselkurse, Leitindizes
* ``zeitregel``   Ausführungsprofile TAGESDATEN, VERZOEGERTER-EINSTIEG, FOLGETAG-SCHLUSS mit Börsenkalendern
* ``kosten``      Gebühren, Spread, Slippage, Währungsaufschlag
* ``buchhaltung`` Depotstand aus dem unveränderlichen Ereignisjournal (Guthaben, Positionen, FIFO-Lose, Bewertung in EUR)
* ``risiko``      zentraler Risiko-Manager (Stückzahl, Grenzen, Reservierungen, Verlustgrenzen)
* ``ausfuehrung`` PAPER-Simulator (konservativ bei Limit, Stop und Kurslücken)
* ``strategien``  Lineal-Vorwärtsmodell, S1 Momentum-Rotation, S2 Swing-Breakout, S3 Mean-Reversion, S4 Robo-Kern
* ``motor``       gemeinsamer Entscheidungs- und Ausführungsschritt für Backtest, PAPER und SIGNAL
* ``backtest``    Walk-Forward, Monte-Carlo, Block-Bootstrap, Kennzahlen, HTML-Bericht
* ``speicher``    Tabellen ``ap_*`` (Migration 0010), Transaktionen, Wiederholungsschutz
* ``bestaetigung`` verschlüsselter Bestätigungsweg ohne eigenen Server (Eingang, Prüfung, Verarbeitung)
* ``steuern``     Steuerannahmen (Modellrechnung, keine Steuerabrechnung) und Belegexport
* ``freigabe``    Echtgeldfreigabe nach Abschnitt 22 (standardmäßig gesperrt)

Keine Orders an Trade Republic, keine inoffiziellen Schnittstellen, keine kostenpflichtigen Dienste.
"""

AP_VERSION = "aktienpilot-0.1.0"
