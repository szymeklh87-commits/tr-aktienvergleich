-- Prüfregel geändert (1.1.0): Zeitzonen mit ganzjährig gleicher UTC-Verschiebung gelten als
-- passend, wenn der Börsencode des Kursanbieters die Börse bestätigt (z. B. Wien: Yahoo meldet
-- „Europe/Amsterdam“ mit Börsencode VIE). Bisher deshalb als „unklar“ markierte Identitäten
-- werden im nächsten Lauf neu geprüft statt erst nach 45 Tagen.
UPDATE instrument SET identity_status = 'offen', identity_checked_at = NULL
WHERE identity_status = 'unklar' AND identity_reason LIKE 'Zeitzone %';
