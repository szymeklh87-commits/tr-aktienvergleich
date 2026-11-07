# Daytrading mit Minutenkursen – Stand der Vorbereitung (ab 1.22)

Auftrag vom 07.11.2026, Priorität 4: „Daytrading mit geeigneten Minutenkursen vorbereiten; kostenlose und zulässige
Datenquellen prüfen.“ Ergebnis: **Der Rechenkern und ein festgelegtes, prüfbares Kriterium sind fertig; eine Kandidatenliste
erscheint noch nicht.** Für die Aktien der App (rund 11.000, weltweit) gibt es keine Quelle für Minutenkurse, die zugleich
kostenlos, ausdrücklich zulässig und vollständig ist. Keine Orders, kein Echtgeld.

## Kursquellen für Minutenkurse (geprüft am 07.11.2026)

| Quelle | Märkte | Takt und Historie | Kosten, Konto | Zulässigkeit | Eignung |
|---|---|---|---|---|---|
| Yahoo Finance (Chart-Schnittstelle, wie für die Schlusskurse) | weltweit, alle Börsen der App | 1-Minuten-Kerzen der letzten Tage, 5-Minuten-Kerzen über Wochen (so schon für den „Tagesverlauf“ bei „Jetzt aktualisieren“ genutzt); je Börse verzögert | kostenlos, ohne Konto | inoffizielle Schnittstelle, Daten „nur zur Information“, keine zugesicherte Verfügbarkeit | Vorbereitung und rückwirkende Prüfung einzelner Aktien; keine Grundlage für Handelsentscheidungen mit Echtgeld |
| [Alpaca Market Data (Plan „Basic“)](https://docs.alpaca.markets/us/docs/about-market-data-api) | nur USA (Börse IEX) | Historie seit 2016 ohne die jüngsten 15 Minuten; Echtzeit nur IEX; 200 Abfragen je Minute | kostenlos, aber Konto mit API-Schlüssel nötig (läge nur als GitHub-Secret auf dem Server) | offizielle Schnittstelle mit eigenen Nutzungsbedingungen | US-Aktien – nur nach deiner Entscheidung (Konto) |
| [Twelve Data (Plan „Basic“)](https://twelvedata.com/pricing.md) | laut Preisliste USA | 8 Abfragen je Minute, 800 je Tag | kostenlos mit Konto | „internal non-display usage only“ – eine Anzeige in der App wäre nicht erlaubt | ungeeignet |
| Kostenpflichtige Anbieter (z. B. EODHD) | weltweit | Minutenkerzen | kostenpflichtig | Lizenz | nur mit deiner Freigabe (Befund F11) |

Lang & Schwarz (Handelsplatz von Trade Republic) und die Börsen-Websites zeigen Kurse an, bieten aber keine frei nutzbare
Schnittstelle; ein Auslesen der Websites wäre nicht zulässig.

## Was fertig ist

* **Rechenkern** `backend/traktien/analytics/intraday_scan.py`: VWAP, Spanne der ersten Minuten, relativer Umsatz gegenüber
  derselben Tageszeit früherer Tage, Bewegung seit Eröffnung – jeweils nur aus Kerzen bis zum jeweiligen Zeitpunkt (kein Blick
  in die Zukunft).
* **Kriterium `orb-1`** (Vorschlag, `config/daytrading.yaml`): Ausbruch aus der Spanne der ersten 15 Minuten, Kurs über VWAP,
  relativer Umsatz mindestens 2, Spanne höchstens 6 %. Einstieg = Schluss der Ausbruchskerze, Stop = Spannentief (höchstens 4 %
  entfernt), Ziel = Einstieg + 2 × Risiko, Ausstieg spätestens 15 Minuten vor Handelsende.
* **Rückwirkende Prüfung mit Kosten** (`backtest`): 1 € je Order und eine halbe Geld-Brief-Spanne je Seite; bei Stop und Ziel in
  derselben Kerze zählt vorsichtig der Stop. Freigabebedingungen in der Konfiguration: mindestens 60 Handelstage, 50 Trades
  und ein positives Ergebnis nach Kosten.
* Tests: `tests/unit/test_intraday_scan.py` (synthetische Kerzen; Tageswerte, Signal, kein Blick in die Zukunft, Kosten,
  vorsichtige Reihenfolge, ausgeschaltete Konfiguration).

## Was du entscheiden müsstest

1. **Quelle:** Yahoo (inoffiziell, weltweit, ohne Konto) nur für die Prüfung – oder zusätzlich ein Konto bei Alpaca für
   US-Aktien. Ein Konto lege ich nicht an.
2. **Freigabe der Liste:** erst wenn die rückwirkende Prüfung die Bedingungen erfüllt; dann `aktiv: true`.
