-- Musterbereiche (Auftrag docs/13_AktienPilot.md, Abschnitt 26; Gesamtauftrag docs/17_Gesamtauftrag_Robo.md, Abschnitt 8):
-- Journal der Zustandswechsel (nur anhängen – die damalige Einordnung bleibt erhalten, auch wenn Kurse später revidiert
-- werden) und der verschlüsselte Stand für die App. Ändert keine bestehende Tabelle.

CREATE TABLE muster_ereignis (
    id           TEXT NOT NULL,              -- Musterkennung m-… (Modul, ISIN, erster Tag der Instanz)
    modul        TEXT NOT NULL CHECK (modul IN ('A', 'B', 'C')),
    isin         TEXT NOT NULL,
    zustand      TEXT NOT NULL,
    tag          INTEGER NOT NULL,           -- Handelstag des Zustandswechsels (Tage seit 1970-01-01)
    datenstand   TEXT NOT NULL,              -- Snapshot, mit dem der Wechsel erkannt wurde
    version      TEXT NOT NULL,              -- Regelversion (config/muster.yaml)
    erfasst_am   TEXT NOT NULL,
    PRIMARY KEY (id, zustand, tag)
);
CREATE INDEX muster_ereignis_tag ON muster_ereignis(tag);

CREATE TABLE muster_stand (
    id          TEXT PRIMARY KEY,
    datentag    INTEGER NOT NULL,
    erstellt_am TEXT NOT NULL,
    groesse     INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    inhalt      BLOB NOT NULL
);
