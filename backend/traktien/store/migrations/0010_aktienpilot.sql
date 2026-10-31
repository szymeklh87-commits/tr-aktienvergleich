-- AktienPilot (Auftrag vom 31.10.2026, docs/13_AktienPilot.md): Musterdepots, unveränderliches Ereignisjournal, Auswahl vor
-- der Ausführung, Signale, Orders, Ausführungen, Schutz-Stops, Eingänge des Bestätigungswegs, Automatikzustand, Freigaben und
-- Backtests. Getrennt von den Ranglisten-Tabellen; nichts hier ändert eine bestehende Tabelle.
-- Geldbeträge in EUR (Depotwährung), Kurse in der Notierungswährung. Zeitpunkte als ISO-8601 in UTC, Handelstage als Tageszahl
-- (Tage seit 1970-01-01) wie in daily_bar.

-- Depots: das gemeinsam budgetierte Pilotdepot, Forschungs- und Vergleichsdepots (virtuell), der eingegebene Bestand
CREATE TABLE ap_depot (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    art               TEXT NOT NULL CHECK (art IN ('pilot', 'forschung', 'vergleich', 'bestand')),
    modus             TEXT NOT NULL CHECK (modus IN ('PAPER', 'SIGNAL', 'LIVE')),
    strategie         TEXT,
    strategie_version TEXT,
    parameter_json    TEXT NOT NULL DEFAULT '{}',
    startkapital_eur  REAL,
    start_tag         INTEGER,
    synthetisch       INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'aktiv',
    angelegt_am       TEXT NOT NULL
);

-- Ereignisjournal: jede Geld- und Bestandsbewegung genau einmal; Korrekturen als eigenes Ereignis, nie als Änderung
CREATE TABLE ap_ereignis (
    id             TEXT PRIMARY KEY,
    depot_id       TEXT NOT NULL REFERENCES ap_depot(id),
    seq            INTEGER NOT NULL,
    zeit           TEXT NOT NULL,
    tag            INTEGER NOT NULL,
    typ            TEXT NOT NULL,
    isin           TEXT,
    stueck         REAL,
    kurs           REAL,
    waehrung       TEXT,
    fx_eur         REAL,
    fx_quelle      TEXT,
    betrag_eur     REAL NOT NULL DEFAULT 0,
    gebuehren_eur  REAL NOT NULL DEFAULT 0,
    quelle         TEXT NOT NULL,
    order_id       TEXT,
    signal_id      TEXT,
    verwaltet      INTEGER NOT NULL DEFAULT 1,
    nutzlast_json  TEXT NOT NULL DEFAULT '{}',
    erfasst_am     TEXT NOT NULL,
    UNIQUE (depot_id, seq)
);
CREATE INDEX ap_ereignis_depot_tag ON ap_ereignis(depot_id, tag);
CREATE INDEX ap_ereignis_isin ON ap_ereignis(isin);

-- Auswahl vor der Ausführung: Rangliste und Ziele eines Entscheidungstags, unveränderlich (Prüfsumme)
CREATE TABLE ap_auswahl (
    id                TEXT PRIMARY KEY,
    depot_id          TEXT NOT NULL REFERENCES ap_depot(id),
    entscheidungstag  INTEGER NOT NULL,
    datenstand        TEXT NOT NULL,
    strategie_version TEXT NOT NULL,
    parameter_hash    TEXT NOT NULL,
    inhalt_json       TEXT NOT NULL,
    inhalt_sha256     TEXT NOT NULL,
    festgehalten_am   TEXT NOT NULL,
    UNIQUE (depot_id, entscheidungstag)
);

-- Signale (Handlungsanweisungen bzw. Musterorders) mit Referenzkurs, Limit, Stop, Gültigkeit und Risikoprüfung
CREATE TABLE ap_signal (
    id                     TEXT PRIMARY KEY,
    depot_id               TEXT NOT NULL REFERENCES ap_depot(id),
    auswahl_id             TEXT REFERENCES ap_auswahl(id),
    modus                  TEXT NOT NULL CHECK (modus IN ('PAPER', 'SIGNAL', 'LIVE')),
    echtgeld               INTEGER NOT NULL DEFAULT 0,
    isin                   TEXT NOT NULL,
    name                   TEXT,
    richtung               TEXT NOT NULL CHECK (richtung IN ('kauf', 'verkauf')),
    stueck                 REAL NOT NULL,
    referenzkurs           REAL,
    referenz_quelle        TEXT,
    referenz_zeit          TEXT,
    waehrung               TEXT,
    limit_kurs             REAL,
    stop_kurs              REAL,
    gueltig_bis            TEXT,
    profil                 TEXT NOT NULL,
    datenzeit              TEXT NOT NULL,
    berechnet_am           TEXT NOT NULL,
    veroeffentlicht_am     TEXT,
    frueheste_ausfuehrung  TEXT,
    begruendung            TEXT NOT NULL,
    risiko_json            TEXT NOT NULL,
    status                 TEXT NOT NULL,
    status_grund           TEXT,
    aktualisiert_am        TEXT NOT NULL
);
CREATE INDEX ap_signal_depot_status ON ap_signal(depot_id, status);

-- Orders (Musterorders im PAPER-Betrieb, bestätigungspflichtige Anweisungen im SIGNAL-Betrieb, Schutz-Stops)
CREATE TABLE ap_order (
    id                     TEXT PRIMARY KEY,
    depot_id               TEXT NOT NULL REFERENCES ap_depot(id),
    signal_id              TEXT REFERENCES ap_signal(id),
    art                    TEXT NOT NULL CHECK (art IN ('markt', 'limit', 'stop')),
    richtung               TEXT NOT NULL CHECK (richtung IN ('kauf', 'verkauf')),
    isin                   TEXT NOT NULL,
    stueck                 REAL NOT NULL,
    limit_kurs             REAL,
    stop_kurs              REAL,
    profil                 TEXT NOT NULL,
    frueheste_ausfuehrung  TEXT NOT NULL,
    gueltig_bis            TEXT,
    reserviert_eur         REAL NOT NULL DEFAULT 0,
    status                 TEXT NOT NULL,
    ausgefuehrt_stueck     REAL NOT NULL DEFAULT 0,
    grund                  TEXT,
    erstellt_am            TEXT NOT NULL,
    aktualisiert_am        TEXT NOT NULL
);
CREATE INDEX ap_order_depot_status ON ap_order(depot_id, status);

-- Ausführungen (simuliert oder bestätigt); Teilausführungen als mehrere Zeilen
CREATE TABLE ap_ausfuehrung (
    id             TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL REFERENCES ap_order(id),
    zeit           TEXT NOT NULL,
    stueck         REAL NOT NULL,
    kurs           REAL NOT NULL,
    gebuehren_eur  REAL NOT NULL DEFAULT 0,
    quelle         TEXT NOT NULL,
    ereignis_id    TEXT REFERENCES ap_ereignis(id),
    erfasst_am     TEXT NOT NULL
);

-- Schutz-Stops je Position: geplant, bestätigt (beim Broker gesetzt), ausgelöst, aufgehoben
CREATE TABLE ap_stop (
    id              TEXT PRIMARY KEY,
    depot_id        TEXT NOT NULL REFERENCES ap_depot(id),
    isin            TEXT NOT NULL,
    stop_kurs       REAL NOT NULL,
    berechnet_tag   INTEGER NOT NULL,
    wirksam_ab      TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('geplant', 'bestaetigt', 'ausgeloest', 'aufgehoben')),
    quelle          TEXT NOT NULL,
    aktualisiert_am TEXT NOT NULL
);
CREATE INDEX ap_stop_depot ON ap_stop(depot_id, isin, status);

-- Eingänge des Bestätigungswegs: jede Ereignis-ID genau einmal (Schutz vor Wiederholung und Doppelverarbeitung)
CREATE TABLE ap_eingang (
    id             TEXT PRIMARY KEY,
    quelle         TEXT NOT NULL,
    typ            TEXT,
    groesse        INTEGER NOT NULL,
    sha256         TEXT NOT NULL,
    erstellt_am    TEXT,
    empfangen_am   TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('verarbeitet', 'abgelehnt')),
    grund          TEXT,
    verarbeitet_am TEXT NOT NULL
);

-- Zustand der Automatik (Pause, Verlustgrenzen, Höchststand des aktiven Teils) – je Schlüssel ein JSON-Wert
CREATE TABLE ap_zustand (
    schluessel      TEXT PRIMARY KEY,
    wert_json       TEXT NOT NULL,
    aktualisiert_am TEXT NOT NULL
);

-- Protokoll jeder Zustandsänderung (Pause, Not-Aus, Freigabe, Grenzänderung)
CREATE TABLE ap_protokoll (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zeit        TEXT NOT NULL,
    art         TEXT NOT NULL,
    text        TEXT NOT NULL,
    daten_json  TEXT NOT NULL DEFAULT '{}'
);

-- Echtgeldfreigabe je Strategieversion (Abschnitt 22); der einmalige Code nur als Hash
CREATE TABLE ap_freigabe (
    id                TEXT PRIMARY KEY,
    strategie         TEXT NOT NULL,
    strategie_version TEXT NOT NULL,
    bindung_sha256    TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('gesperrt', 'freigabefaehig', 'freigegeben', 'zurueckgesetzt')),
    pruefbericht_json TEXT NOT NULL,
    code_sha256       TEXT,
    code_gueltig_bis  TEXT,
    erstellt_am       TEXT NOT NULL,
    aktualisiert_am   TEXT NOT NULL
);

-- Backtests: reproduzierbar mit Datenstand, Code- und Strategieversion, Parametern und Zufallsstartwert
CREATE TABLE ap_backtest (
    id                TEXT PRIMARY KEY,
    strategie         TEXT NOT NULL,
    strategie_version TEXT NOT NULL,
    parameter_json    TEXT NOT NULL,
    datenstand        TEXT NOT NULL,
    software          TEXT NOT NULL,
    zufallsstart      INTEGER NOT NULL,
    von_tag           INTEGER NOT NULL,
    bis_tag           INTEGER NOT NULL,
    kennzahlen_json   TEXT NOT NULL,
    bericht_datei     TEXT,
    synthetisch       INTEGER NOT NULL DEFAULT 0,
    erstellt_am       TEXT NOT NULL
);

-- Verarbeitung je Depot und Entscheidungstag genau einmal (Wiederholungsläufe buchen nichts doppelt)
CREATE TABLE ap_tageslauf (
    depot_id       TEXT NOT NULL REFERENCES ap_depot(id),
    tag            INTEGER NOT NULL,
    lauf_id        TEXT NOT NULL,
    verarbeitet_am TEXT NOT NULL,
    ergebnis_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (depot_id, tag)
);
