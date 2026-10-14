-- Zwischenstand (ab 1.8): vorläufiger Datenstand mit aktuellen Kursen während des Handelstags.
-- Eigene Tabelle, damit die Regeln der offiziellen Datenstände (Stichtag, Wiederholungen, Teilstand)
-- unberührt bleiben. Gespeichert wird nur der jeweils neueste Zwischenstand.
CREATE TABLE zwischenstand (
    id            TEXT PRIMARY KEY,
    cutoff_day    INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    quotes_until  TEXT,
    data_mode     TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    official_id   TEXT,
    summary_json  TEXT NOT NULL,
    site_archive  TEXT NOT NULL
);
