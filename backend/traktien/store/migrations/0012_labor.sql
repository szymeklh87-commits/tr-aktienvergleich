-- Strategielabor (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15): Ergebnisse der Laborläufe (Varianten, Zeiträume,
-- Auswahl, Walk-forward, Vorschlag). Inhalt komprimiertes JSON (Schema tr-labor/1) mit Prüfsumme; DEMO und PAPER getrennt.
-- Ändert keine bestehende Tabelle.

CREATE TABLE ap_labor (
    id          TEXT PRIMARY KEY,           -- lab-… (aus Version, Datenstand, Handelstagen und Varianten – gleiche Eingaben, gleiche Kennung)
    datentag    TEXT NOT NULL,              -- letzter Handelstag der Nachrechnung (ISO)
    erstellt_am TEXT NOT NULL,
    version     TEXT NOT NULL,              -- labor-… (config/labor.yaml)
    modus       TEXT NOT NULL CHECK (modus IN ('DEMO', 'PAPER')),
    groesse     INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    inhalt      BLOB NOT NULL
);
