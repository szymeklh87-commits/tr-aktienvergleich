-- Wochenwerte für die Umschichtungs-Regel (rotation-v1): je Notierung und Woche (Schlüssel =
-- Freitag) letzter Schlusskurs, Umsatzsumme, Sitzungszählungen, größte Tagesbewegung sowie
-- Schlusskurs und Tag der ersten Sitzung (Ausführung einer am Freitag zuvor beschlossenen Order).
-- Ältere Wochen stammen aus einem einmaligen Langabruf (bis 3 Jahre), jüngere werden in jedem
-- Lauf aus den Tageskursen neu verdichtet.
CREATE TABLE week_bar (
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    week_end    INTEGER NOT NULL,
    close       REAL,
    turnover    REAL NOT NULL,
    with_data   INTEGER NOT NULL,
    positive    INTEGER NOT NULL,
    observed    INTEGER NOT NULL,
    sessions    INTEGER NOT NULL,
    jump        REAL NOT NULL,
    first_close REAL,
    first_day   INTEGER,
    PRIMARY KEY (listing_id, week_end)
) WITHOUT ROWID;

-- Langhistorie je Notierung: offen (noch nicht geladen), ok, keine_daten, erneut (z. B. nach Split)
CREATE TABLE long_history (
    listing_id   INTEGER PRIMARY KEY REFERENCES listing(id),
    status       TEXT NOT NULL CHECK (status IN ('offen', 'ok', 'keine_daten', 'erneut')),
    first_week   INTEGER,
    fetched_at   TEXT,
    last_error   TEXT,
    added_at     TEXT NOT NULL
);
