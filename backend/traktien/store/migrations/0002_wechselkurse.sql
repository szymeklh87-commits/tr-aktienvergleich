-- Referenzkurse je EUR (EZB) für den indikativen Umsatzfilter in USD.
-- Ein Kurs je Kurstag und Währung; ältere Einträge räumt der tägliche Lauf auf.
CREATE TABLE fx_rate (
    day         INTEGER NOT NULL,
    currency    TEXT NOT NULL,
    per_eur     REAL NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (day, currency)
);
