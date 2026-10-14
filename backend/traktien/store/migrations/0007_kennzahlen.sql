-- 1.6.0: Kennzahlen, Kursziele und Signale je Aktie (Potenzial-Ranking).
--
-- stock_facts: ein Abruf je Aktie (Yahoo quoteSummary: Kursziele, Empfehlungen, Analystenurteile,
--   Bewertung, Wachstum, Finanzen, Termine, Branche) – kompakt als JSON, rotierend aktualisiert.
-- stock_extra: Ergänzungen mit eigener Rotation – Bewertung/Ausblick (nur US), zweite Kurszielquelle
--   (Nasdaq, nur US), Nachrichten und Community-Stimmung (nur für vordere Kandidaten).
-- target_history: Kursziele je Abruftag – Grundlage, um später die Treffsicherheit zu messen.
CREATE TABLE stock_facts (
    isin        TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ok', 'keine_daten', 'fehler')),
    fetched_at  TEXT NOT NULL,
    payload     TEXT,
    error       TEXT
);

CREATE TABLE stock_extra (
    isin        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('bewertung', 'nasdaq', 'nachrichten', 'community')),
    status      TEXT NOT NULL CHECK (status IN ('ok', 'keine_daten', 'fehler')),
    fetched_at  TEXT NOT NULL,
    payload     TEXT,
    PRIMARY KEY (isin, kind)
) WITHOUT ROWID;

CREATE TABLE target_history (
    isin         TEXT NOT NULL,
    day          INTEGER NOT NULL,
    target_mean  REAL,
    target_low   REAL,
    target_high  REAL,
    analysts     INTEGER,
    rec_mean     REAL,
    buy_share    REAL,
    PRIMARY KEY (isin, day)
) WITHOUT ROWID;

-- Veröffentlichte Signal-Stände (unabhängig von den Kurs-Datenständen aktualisierbar)
CREATE TABLE signal_stand (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    snapshot_id   TEXT,
    cutoff_day    INTEGER,
    stocks        INTEGER NOT NULL,
    with_facts    INTEGER NOT NULL,
    summary_json  TEXT NOT NULL,
    archive       TEXT NOT NULL
);
