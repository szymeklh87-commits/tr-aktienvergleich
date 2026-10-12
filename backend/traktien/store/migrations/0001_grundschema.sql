-- Grundschema TR-Aktienvergleich (SQLite)
-- Zeitpunkte: ISO-8601 in UTC mit "Z". Sitzungsdaten: Epochentag (Tage seit 1970-01-01).
-- Fehlende mathematische Werte: NULL (niemals 0).

CREATE TABLE universe_snapshot (
    id                  TEXT PRIMARY KEY,
    source_url          TEXT NOT NULL,
    retrieved_at        TEXT NOT NULL,
    http_last_modified  TEXT,
    http_etag           TEXT,
    pdf_creation_date   TEXT,
    pdf_mod_date        TEXT,
    sha256              TEXT NOT NULL,
    parser_version      TEXT NOT NULL,
    isin_count          INTEGER NOT NULL,
    invalid_isins       INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL CHECK (status IN ('akzeptiert', 'zur_pruefung', 'abgelehnt')),
    status_reason       TEXT NOT NULL,
    previous_id         TEXT,
    added_count         INTEGER NOT NULL DEFAULT 0,
    removed_count       INTEGER NOT NULL DEFAULT 0,
    data_mode           TEXT NOT NULL DEFAULT 'produktiv',
    created_at          TEXT NOT NULL
);

CREATE TABLE universe_member (
    universe_id  TEXT NOT NULL REFERENCES universe_snapshot(id),
    isin         TEXT NOT NULL,
    tr_name      TEXT NOT NULL,
    isin_valid   INTEGER NOT NULL,
    page         INTEGER,
    PRIMARY KEY (universe_id, isin)
);

CREATE TABLE universe_change (
    id           INTEGER PRIMARY KEY,
    universe_id  TEXT NOT NULL REFERENCES universe_snapshot(id),
    isin         TEXT NOT NULL,
    change       TEXT NOT NULL CHECK (change IN ('neu', 'entfallen', 'name_geaendert')),
    detail       TEXT,
    recorded_at  TEXT NOT NULL
);
CREATE INDEX universe_change_by_isin ON universe_change(isin);

CREATE TABLE instrument (
    id                   INTEGER PRIMARY KEY,
    isin                 TEXT NOT NULL UNIQUE,
    full_name            TEXT,
    instrument_type      TEXT NOT NULL DEFAULT 'unklar',
    issuer_id            TEXT,
    identity_status      TEXT NOT NULL DEFAULT 'offen'
                         CHECK (identity_status IN ('offen', 'verifiziert', 'unklar', 'kein_aktieninstrument', 'isin_ungueltig')),
    identity_reason      TEXT,
    identity_checked_at  TEXT,
    identity_source      TEXT,
    warnings             INTEGER NOT NULL DEFAULT 0,
    valid_from           TEXT,
    valid_to             TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE instrument_alias (
    instrument_id  INTEGER NOT NULL REFERENCES instrument(id),
    alias          TEXT NOT NULL,
    kind           TEXT NOT NULL CHECK (kind IN ('name', 'tr_name', 'ticker', 'symbol')),
    source         TEXT NOT NULL,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL,
    PRIMARY KEY (instrument_id, alias, kind)
);

CREATE TABLE listing (
    id                  INTEGER PRIMARY KEY,
    instrument_id       INTEGER NOT NULL REFERENCES instrument(id),
    provider            TEXT NOT NULL,
    provider_symbol     TEXT NOT NULL,
    ticker              TEXT,
    exchange_key        TEXT,
    mic                 TEXT,
    exchange_name       TEXT,
    exchange_tz         TEXT,
    calendar_code       TEXT,
    currency            TEXT,
    price_unit          TEXT,
    unit_factor         REAL,
    is_reference        INTEGER NOT NULL DEFAULT 0,
    selection_reason    TEXT,
    figi                TEXT,
    composite_figi      TEXT,
    share_class_figi    TEXT,
    data_revision       INTEGER NOT NULL DEFAULT 0,
    last_full_fetch_at  TEXT,
    last_fetch_at       TEXT,
    last_fetch_status   TEXT,
    last_error          TEXT,
    provider_name       TEXT,
    provider_exchange   TEXT,
    provider_type       TEXT,
    hold_all            INTEGER NOT NULL DEFAULT 0,
    hold_reason         TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (provider, provider_symbol)
);
CREATE UNIQUE INDEX listing_one_reference ON listing(instrument_id) WHERE is_reference = 1;

CREATE TABLE daily_bar (
    listing_id    INTEGER NOT NULL REFERENCES listing(id),
    session_day   INTEGER NOT NULL,
    revision      INTEGER NOT NULL,
    open          REAL,
    high          REAL,
    low           REAL,
    close_split   REAL NOT NULL,
    close_raw     REAL,
    close_total   REAL,
    volume        REAL,
    bar_time_utc  TEXT,
    fetched_at    TEXT NOT NULL,
    quality       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (listing_id, revision, session_day)
) WITHOUT ROWID;

CREATE TABLE bar_revision (
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    revision    INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    reason      TEXT NOT NULL,
    bars        INTEGER NOT NULL,
    PRIMARY KEY (listing_id, revision)
);

CREATE TABLE corporate_action (
    id               INTEGER PRIMARY KEY,
    listing_id       INTEGER NOT NULL REFERENCES listing(id),
    kind             TEXT NOT NULL CHECK (kind IN ('split', 'dividende', 'waehrungswechsel', 'sonstiges')),
    ex_day           INTEGER NOT NULL,
    factor           REAL,
    amount           REAL,
    currency_before  TEXT,
    currency_after   TEXT,
    source           TEXT NOT NULL,
    first_seen       TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'erfasst',
    UNIQUE (listing_id, kind, ex_day)
);

CREATE TABLE review_decision (
    isin        TEXT NOT NULL,
    day         INTEGER NOT NULL,
    decision    TEXT NOT NULL CHECK (decision IN ('freigegeben', 'zurueckhalten')),
    source      TEXT,
    note        TEXT,
    decided_at  TEXT NOT NULL,
    PRIMARY KEY (isin, day)
);

CREATE TABLE run (
    id                 TEXT PRIMARY KEY,
    trigger            TEXT NOT NULL,
    planned_start      TEXT,
    started_at         TEXT NOT NULL,
    finished_at        TEXT,
    cutoff_day         INTEGER,
    universe_id        TEXT,
    data_revision      TEXT,
    method_version     TEXT,
    metrics_version    TEXT,
    ranking_version    TEXT,
    frequency_version  TEXT,
    software_version   TEXT,
    status             TEXT NOT NULL CHECK (status IN (
                          'geplant', 'laeuft', 'wartet_auf_provider', 'teilweise_berechnet',
                          'vollstaendig_berechnet', 'geprueft', 'veroeffentlicht',
                          'keine_neuen_daten', 'fehlgeschlagen', 'abgebrochen')),
    status_detail      TEXT,
    attempt            INTEGER NOT NULL DEFAULT 1,
    checkpoint         TEXT,
    error_count        INTEGER NOT NULL DEFAULT 0,
    requests           INTEGER NOT NULL DEFAULT 0,
    throttled          INTEGER NOT NULL DEFAULT 0,
    heartbeat_at       TEXT,
    snapshot_id        TEXT,
    data_mode          TEXT NOT NULL DEFAULT 'produktiv'
);

CREATE TABLE run_event (
    id       INTEGER PRIMARY KEY,
    run_id   TEXT NOT NULL REFERENCES run(id),
    at       TEXT NOT NULL,
    level    TEXT NOT NULL,
    step     TEXT NOT NULL,
    message  TEXT NOT NULL
);

CREATE TABLE run_lock (
    name          TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    acquired_at   TEXT NOT NULL,
    heartbeat_at  TEXT NOT NULL
);

CREATE TABLE fetch_checkpoint (
    target_key  TEXT NOT NULL,
    listing_id  INTEGER NOT NULL,
    status      TEXT NOT NULL,
    at          TEXT NOT NULL,
    PRIMARY KEY (target_key, listing_id)
);

CREATE TABLE snapshot_manifest (
    id               TEXT PRIMARY KEY,
    idempotency_key  TEXT NOT NULL UNIQUE,
    cutoff_day       INTEGER NOT NULL,
    computed_at      TEXT NOT NULL,
    published_at     TEXT,
    completeness     TEXT NOT NULL CHECK (completeness IN ('vollstaendig', 'teilstand')),
    data_mode        TEXT NOT NULL CHECK (data_mode IN ('produktiv', 'demo', 'import')),
    universe_id      TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    supersedes       TEXT,
    summary_json     TEXT NOT NULL,
    site_archive     TEXT,
    evidence_archive TEXT,
    status           TEXT NOT NULL CHECK (status IN ('geprueft', 'veroeffentlicht', 'zurueckgezogen'))
);

CREATE TABLE kv (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
