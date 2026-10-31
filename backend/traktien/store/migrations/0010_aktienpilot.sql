-- AktienPilot – Spielgeld-Robo (Auftrag docs/13_AktienPilot.md, Gesamtfassung 31.10.2026, Abschnitte 17–19, 29, 31):
-- virtuelle Depots, unveränderliches Ereignisjournal, Orders mit Begründung, Auswahl vor der Ausführung, Regelversionen,
-- Tageswerte, Journal, Automatikzustand, Eingänge des Bestätigungswegs, Ranglistenarchiv (Variante B „Platz 1 an
-- vergangenen Stichtagen“) und Kursreihen der Leitindizes und Kern-ETFs. Getrennt von den Ranglisten-Tabellen; nichts hier
-- ändert eine bestehende Tabelle.
-- Geldbeträge in EUR (Depotwährung), Kurse in der Basiswährung der Notierung. Zeitpunkte als ISO-8601 in UTC, Handelstage
-- als Tageszahl (Tage seit 1970-01-01) wie in daily_bar.
-- Echtgeld ist technisch ausgeschlossen (Abschnitt 29.1): Modus nur PAPER, SIGNAL (manuelle Übung) oder DEMO.

-- Depots: das gemeinsam budgetierte Pilotdepot, Forschungsdepots je Strategie/Regel, Vergleichsdepots (Welt-ETF, Kern)
CREATE TABLE ap_depot (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    art              TEXT NOT NULL CHECK (art IN ('pilot', 'forschung', 'vergleich')),
    modus            TEXT NOT NULL CHECK (modus IN ('PAPER', 'SIGNAL', 'DEMO')),
    definition_json  TEXT NOT NULL,           -- Startkapital, Anteile, Regeln (ID@Version), Kern-Zielaufteilung
    definition_sha   TEXT NOT NULL,
    test_id          TEXT NOT NULL,           -- neuer Spielgeldtest = neue Test-ID; alte Läufe bleiben archiviert
    start_tag        INTEGER NOT NULL,
    synthetisch      INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'aktiv' CHECK (status IN ('aktiv', 'pausiert', 'archiviert')),
    angelegt_am      TEXT NOT NULL,
    archiviert_am    TEXT
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

-- Virtuelle Orders mit Zeitregel (Datenstichtag, Veröffentlichung, Ausführungssitzung, Ablauf), Reservierung und Begründung
CREATE TABLE ap_order (
    id               TEXT PRIMARY KEY,
    depot_id         TEXT NOT NULL REFERENCES ap_depot(id),
    zuordnung        TEXT NOT NULL,
    isin             TEXT NOT NULL,
    richtung         TEXT NOT NULL CHECK (richtung IN ('kauf', 'verkauf')),
    stueck           INTEGER NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('offen', 'ausgefuehrt', 'teilweise', 'verfallen', 'abgelehnt', 'storniert')),
    datentag         INTEGER NOT NULL,
    sitzung          INTEGER,
    daten_json       TEXT NOT NULL,           -- vollständige Order (Grund, Regel, Zeitregel, Risikoprüfung, Stopplan)
    aktualisiert_am  TEXT NOT NULL
);
CREATE INDEX ap_order_depot_status ON ap_order(depot_id, status);

-- Auswahl vor der Ausführung: Kandidaten, Fundstellen, Bedingungen, Rang – je Depot, Strategie und Tag unveränderlich
CREATE TABLE ap_auswahl (
    id                TEXT PRIMARY KEY,
    depot_id          TEXT NOT NULL REFERENCES ap_depot(id),
    zuordnung         TEXT NOT NULL,
    entscheidungstag  INTEGER NOT NULL,
    datenstand        TEXT NOT NULL,
    regel             TEXT NOT NULL,          -- Regel-ID@Version
    regel_sha         TEXT NOT NULL,          -- Fingerabdruck der fachlichen Regelteile
    inhalt_json       TEXT NOT NULL,
    inhalt_sha256     TEXT NOT NULL,
    festgehalten_am   TEXT NOT NULL,
    UNIQUE (depot_id, zuordnung, entscheidungstag)
);

-- Regelversionen (Regel-Baukasten, Abschnitt 31): jede fachliche Änderung = neue Version; alte Versionen bleiben
CREATE TABLE ap_regel (
    id           TEXT NOT NULL,
    version      INTEGER NOT NULL,
    name         TEXT NOT NULL,
    inhalt_json  TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    quelle       TEXT NOT NULL CHECK (quelle IN ('vorlage', 'app', 'konfiguration', 'test')),
    erstellt_am  TEXT NOT NULL,
    PRIMARY KEY (id, version)
);

-- Tageswerte je Depot (Gesamt, Kern, aktiver Teil, Guthaben, Einzahlungen, Kosten, Verluststufe)
CREATE TABLE ap_wert (
    depot_id    TEXT NOT NULL REFERENCES ap_depot(id),
    tag         INTEGER NOT NULL,
    daten_json  TEXT NOT NULL,
    PRIMARY KEY (depot_id, tag)
);

-- Journal: jede Entscheidung (auch „nicht gehandelt“) mit Begründung, Ausführungen, Stops, Gewinnmitnahmen, Verluststufen
CREATE TABLE ap_protokoll (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    depot_id    TEXT,
    tag         INTEGER,
    zeit        TEXT NOT NULL,
    art         TEXT NOT NULL,
    zuordnung   TEXT,
    text        TEXT NOT NULL,
    daten_json  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ap_protokoll_depot_tag ON ap_protokoll(depot_id, tag);

-- Zustand je Depot (Positionen mit Stop und Gewinnstufen, Sperren, Verlustgrenzen, letzter Stichtag) als JSON
CREATE TABLE ap_zustand (
    schluessel      TEXT PRIMARY KEY,
    wert_json       TEXT NOT NULL,
    aktualisiert_am TEXT NOT NULL
);

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

-- Verarbeitung je Depot und Datenstichtag genau einmal (Wiederholungsläufe buchen nichts doppelt)
CREATE TABLE ap_tageslauf (
    depot_id       TEXT NOT NULL REFERENCES ap_depot(id),
    tag            INTEGER NOT NULL,
    lauf_id        TEXT NOT NULL,
    verarbeitet_am TEXT NOT NULL,
    ergebnis_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (depot_id, tag)
);

-- Archiv der veröffentlichten Spitzenplätze je Stichtag (Variante B, Abschnitt 31.2): Top 10 je Zeitraum, Gewichtung,
-- Gruppe und Vergleichsfeld als komprimiertes JSON; nur tatsächlich veröffentlichte Stände, nie nachträglich aufgefüllt
CREATE TABLE ap_rang_archiv (
    tag          INTEGER PRIMARY KEY,
    snapshot_id  TEXT NOT NULL,
    inhalt       BLOB NOT NULL,
    erstellt_am  TEXT NOT NULL
);

-- Kursreihen außerhalb des TR-Aktienuniversums: Leitindizes des Marktfilters und Kern-ETFs (Welt, Geldmarkt)
CREATE TABLE ap_marktreihe (
    symbol       TEXT NOT NULL,
    tag          INTEGER NOT NULL,
    open         REAL,
    high         REAL,
    low          REAL,
    close        REAL NOT NULL,
    volume       REAL,
    waehrung     TEXT,
    abgerufen_am TEXT NOT NULL,
    PRIMARY KEY (symbol, tag)
) WITHOUT ROWID;

-- Historische Tests: reproduzierbar mit Datenstand, Code- und Regelversion und Kennzahlen (Abschnitt 14)
CREATE TABLE ap_backtest (
    id                TEXT PRIMARY KEY,
    regel             TEXT NOT NULL,          -- Regel-ID@Version
    regel_sha         TEXT NOT NULL,
    datenstand        TEXT NOT NULL,
    software          TEXT NOT NULL,
    von_tag           INTEGER NOT NULL,
    bis_tag           INTEGER NOT NULL,
    kennzahlen_json   TEXT NOT NULL,
    synthetisch       INTEGER NOT NULL DEFAULT 0,
    erstellt_am       TEXT NOT NULL
);
