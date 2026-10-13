-- Zweiter Börsenplatz je ISIN für den Abgleich auffälliger Kursabweichungen (boersenplatz-v1).
-- Gespeichert wird nur die Wahl (Symbol und Börse) bzw. dass es keinen zweiten Platz gibt;
-- die Kurse des zweiten Platzes werden je Veröffentlichung frisch geladen und nicht gespeichert.
CREATE TABLE venue_listing (
    isin             TEXT PRIMARY KEY,
    status           TEXT NOT NULL CHECK (status IN ('gefunden', 'kein_vergleichsplatz')),
    provider_symbol  TEXT,
    exchange_key     TEXT,
    source           TEXT,
    checked_at       TEXT NOT NULL
);
