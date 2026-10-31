-- Kursabgleich (ab 1.20.0): Kurse aus den Archiven der Börsen (amtliche Quellen), Stand des Abrufs und Nachweis der
-- übernommenen Kurse. Die Kurse der Hauptquelle (daily_bar) bleiben unverändert gespeichert; die Auswahlregel
-- (analytics/kursabgleich.py) wird bei jeder Berechnung neu angewendet.

-- Tageskurse einer Notierung aus einer Quelle der Börse, unbereinigt wie veröffentlicht
CREATE TABLE boersenkurs (
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    source      TEXT NOT NULL,
    day         INTEGER NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL NOT NULL,
    volume      REAL,
    trades      REAL,
    decimals    INTEGER,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (listing_id, source, day)
) WITHOUT ROWID;

-- Tagesdateien der Börsen (GPW, NewConnect): je Sitzung, ob und mit welchem Ergebnis sie gelesen wurde
CREATE TABLE boersenquelle_tag (
    source      TEXT NOT NULL,
    day         INTEGER NOT NULL,
    status      TEXT NOT NULL,
    rows        INTEGER NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 1,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (source, day)
) WITHOUT ROWID;

-- Abruf je Notierung und Quelle (TMX, Nasdaq-NOCP; für GPW/NewConnect die Zuordnung über die ISIN)
CREATE TABLE boersenquelle_notierung (
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    source      TEXT NOT NULL,
    status      TEXT NOT NULL,
    symbol      TEXT,
    name        TEXT,
    exchange    TEXT,
    currency    TEXT,
    detail      TEXT,
    first_day   INTEGER,
    last_day    INTEGER,
    checked_at  TEXT NOT NULL,
    checked_for INTEGER,
    PRIMARY KEY (listing_id, source)
) WITHOUT ROWID;

-- Nachweis: jeder Tag, an dem der verwendete Kurs bzw. Umsatz von der Hauptquelle abweicht (letzte Berechnung)
CREATE TABLE kurskorrektur (
    listing_id   INTEGER NOT NULL REFERENCES listing(id),
    day          INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    source       TEXT NOT NULL,
    old_close    REAL,
    new_close    REAL NOT NULL,
    official_raw REAL NOT NULL,
    old_volume   REAL,
    new_volume   REAL,
    rule         TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    PRIMARY KEY (listing_id, day, reason)
) WITHOUT ROWID;
