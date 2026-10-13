-- 1.4.1 (Börsentabelle boersen-v2): Die Bloomberg-Sammelcodes CN (Kanada) und GR (Deutschland)
-- zeigen auf keine bestimmte Börse. Bisher führten sie zu Yahoo-Symbolen ohne Kurse, etwa „AAG.TO“
-- für eine TSX-Venture-Aktie (richtig „AAG.V“) oder „046.DE“ für eine nur in Frankfurt gehandelte
-- Aktie (richtig „046.F“). Betroffene Identitäten werden im nächsten Lauf neu geprüft.
UPDATE instrument SET identity_status = 'offen', identity_checked_at = NULL
WHERE id IN (
    SELECT instrument_id FROM listing
    WHERE is_reference = 1 AND exchange_key IN ('XTSE', 'XETR') AND last_fetch_status = 'keine_daten'
);

-- Kennt der Kursanbieter ein Symbol nicht, sucht der Lauf eine andere Schreibweise derselben Notierung
-- (z. B. „ADDT-B.ST“ statt „ADDTB.ST“, Suche nach der ISIN). Ein Versuch je Notierung und 30 Tage.
CREATE TABLE symbol_alternative (
    listing_id  INTEGER PRIMARY KEY REFERENCES listing(id),
    tried_at    TEXT NOT NULL,
    old_symbol  TEXT NOT NULL,
    found       TEXT
);
