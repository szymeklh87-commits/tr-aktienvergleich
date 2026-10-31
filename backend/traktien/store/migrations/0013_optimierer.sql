-- Depot-Optimierer (Aufträge vom 31.10.2026, 18 und 19): Forschungsergebnisse mit Modellen sowie die täglichen Prognosen und
-- Empfehlungen. Prognosen und Empfehlungen werden nur angehängt und nie geändert oder gelöscht (Auftrag 18, Abschnitt 15:
-- „Diese Prognose darf nachträglich nicht verändert werden“). DEMO und PAPER getrennt. Ändert keine bestehende Tabelle.

CREATE TABLE ap_optimierer (
    id          TEXT PRIMARY KEY,           -- opt-… (aus Version, Datenstand, Tagen und Merkmalen – gleiche Eingaben, gleiche Kennung)
    datentag    TEXT NOT NULL,              -- Stichtag der Merkmale (ISO)
    erstellt_am TEXT NOT NULL,
    version     TEXT NOT NULL,
    modus       TEXT NOT NULL CHECK (modus IN ('DEMO', 'PAPER')),
    groesse     INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    inhalt      BLOB NOT NULL                -- komprimiertes JSON (Schema tr-optimierer/1)
);

CREATE TABLE ap_prognose (
    datentag     INTEGER NOT NULL,          -- Stichtag der Prognose (Epochentag)
    modell_id    TEXT NOT NULL,             -- Forschungslauf, aus dem das Modell stammt
    horizont     TEXT NOT NULL,             -- w1 … w52
    isin         TEXT NOT NULL,
    modus        TEXT NOT NULL CHECK (modus IN ('DEMO', 'PAPER')),
    wertung_rang REAL,                      -- Querschnittsrang der Modellwertung 0–1
    eignung      REAL,                      -- Eignungswert 0–100
    erwartet_pct REAL,
    positiv_pct  REAL,
    q10_pct      REAL,
    q50_pct      REAL,
    q90_pct      REAL,
    kurs_eur     REAL,                      -- Schlusskurs in Euro am Stichtag (Ausgangspunkt der Kontrolle)
    auswahl      TEXT NOT NULL,             -- spitze (beste Eignung) | stichprobe (Kontrolle der Kalibrierung über alle Dezile)
    erstellt_am  TEXT NOT NULL,
    PRIMARY KEY (datentag, modell_id, horizont, isin)
);

CREATE TRIGGER ap_prognose_keine_aenderung BEFORE UPDATE ON ap_prognose BEGIN SELECT RAISE(ABORT, 'Prognosen sind unveränderlich'); END;

CREATE TRIGGER ap_prognose_kein_loeschen BEFORE DELETE ON ap_prognose BEGIN SELECT RAISE(ABORT, 'Prognosen werden nicht gelöscht'); END;

CREATE TABLE ap_empfehlung (
    datentag    INTEGER NOT NULL,
    variante    TEXT NOT NULL,              -- rendite | ausgewogen | stabil | kurz | mittel | lang
    modus       TEXT NOT NULL CHECK (modus IN ('DEMO', 'PAPER')),
    modell_id   TEXT NOT NULL,
    erstellt_am TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    inhalt      TEXT NOT NULL,              -- JSON: Positionen, Gewichte, Kennzahlen, Veränderungen mit Begründung
    PRIMARY KEY (datentag, variante, modus)
);

CREATE TRIGGER ap_empfehlung_keine_aenderung BEFORE UPDATE ON ap_empfehlung BEGIN SELECT RAISE(ABORT, 'Empfehlungen sind unveränderlich'); END;

CREATE TRIGGER ap_empfehlung_kein_loeschen BEFORE DELETE ON ap_empfehlung BEGIN SELECT RAISE(ABORT, 'Empfehlungen werden nicht gelöscht'); END;
