# Kennzahlen, Parameter und Doppelungen (Abschnitte 31.8 und 32)

Bestandsaufnahme vom 31.10.2026 auf dem Integrationsbranch `gesamtauftrag` (Stand vor dem Kennzahlenkatalog), danach
fortgeschrieben. Sie ist das in Abschnitt 32.4 verlangte Verzeichnis: vorhandene Kennzahlen und Parameter, echte Doppelungen,
fachlich notwendige Unterschiede und veraltete Aliase – jeweils mit Status.

**Status:** offen · bereinigt (mit Test) · bewusst getrennt (fachlich verschiedene Größe, Begründung) · gespiegelt (zweite
Implementierung nur zur Anzeige, bitgleich gegen die Python-Fassung getestet).

Die verbindliche Verbindung zwischen Analyse-App und Robo ist der Kennzahlenkatalog
[`backend/traktien/aktienpilot/katalog.py`](../backend/traktien/aktienpilot/katalog.py): eine ID je Kennzahl mit Definition,
Einheit, Parametern, Operatoren, Quelle, Methodenversion, Aufwärmphase, Fehlwertregel und Verfügbarkeit. Er liest die Felder
derselben Berechnung, aus der die App-Daten geschrieben werden (Test `tests/unit/test_aktienpilot_katalog.py`,
„GleicheBerechnungTests“).

## 1. Woher Werte eines früheren Tages kommen (Point-in-Time)

| Ablage | Inhalt | Aufbewahrung | Folge für Regeln |
|---|---|---|---|
| `daily_bar` (+ `bar_revision`, `corporate_action`) | Tageskurse OHLCV, splitbereinigt, Rohkurs, Total-Return-Kurs | 430 Tage, nur letzte Revision | alle Kurs-, Fenster-, Rang- und Technikwerte nachrechenbar – mit heutiger Revision und heutigem Universum („nachgerechnet“, mögliche Rückschau-Verzerrung) |
| Release-Archive `site-/evidence-<id>` | veröffentlichte Stände | 60 Snapshot-Stände, 3 Signal-Stände | tatsächlich veröffentlichte damalige Ranglisten (Quelle für Variante B rückwirkend) |
| `ap_rang_archiv` (neu, Migration 0010) | Top 10 je Zeitraum, Gewichtung, Gruppe, Vergleichsfeld | ab Inbetriebnahme, 120 Tage | Variante B „Platz 1 an vergangenen Stichtagen“ vorwärts |
| `week_bar`, `fx_rate` | Wochenwerte, EZB-Kurse | ≈ 3,4 / 3,5 Jahre | Umschichtungs-Regel, Umsatz, Depots |
| `target_history` | Yahoo-Kursziel Mittel/Tief/Hoch, Analysten, Empfehlung | unbegrenzt, je Abruftag | Kursziel-Abstand (nur Yahoo-Anteil) |
| `stock_facts`, `stock_extra` | Fundamentaldaten, Nachrichten, Community | nur letzter Abruf | **nur vorwärts** (im Katalog `backtest = nur_vorwaerts`) |
| `universe_snapshot/member/change` | TR-Verzeichnis je Version | unbegrenzt | TR-Zugehörigkeit zum Zeitpunkt |

Nur rückblickend bekannt und für Regeln gesperrt: spätere Sieger (`spaeterer_sieger`), Gesamtmaximum, Trefferquoten der
Signal-Kalibrierung (In-Sample), Methodenvergleich, Ranglistenvergleich des Kursabgleichs.

## 2. Doppelungen und ihr Status

| # | Was | Fundstellen | Befund | Status / Maßnahme |
|---|---|---|---|---|
| P1 | Fenster 1–90 | `config/methode.yaml`, `config.py`, `analytics/windows.py`, `frequency.py`, `snapshot_writer.py`, `lib/scoring.ts`, `lib/storage.ts`, `lib/frequency.ts`, `lib/groups.ts`, `controls.tsx`, `GridView.tsx`, `FrequencyView.tsx`, `GroupFrequencyView.tsx` | gleich, als Literale verteilt | Katalog: aus `MethodConfig` (bereinigt für Regeln); App-Literale offen |
| P2 | elf Gewichtungen | `methode.yaml`, `config.py`, `lib/scoring.ts`, `lib/storage.ts` (`WEIGHT_SET`) | gleich | Katalog: aus `MethodConfig.weights`; `WEIGHT_SET` offen |
| P3 | Modus- und Politiknamen | `config.py` ↔ `lib/scoring.ts` | gleich | offen (Suchalias aus einer Quelle) |
| P4 | Top-K 1/3/10, Fundstellen ≤ 10, Kopf 50 | `config.py`, `lib/frequency.ts`, `lib/storage.ts`, `frequency.py`, `snapshot_writer.py`, `lib/scoring.ts` | gleich | offen (Methodenparameter ins Manifest) |
| P5 | Längen 20/100/150/200 | `lib/depots.ts`, `rotation.py`, `pipeline.yaml`, `signals_writer.py`, `snapshot_writer.py` | verschiedene Zwecke | bewusst getrennt (eindeutig benennen) |
| P6 | mindestens 15 Kurse für R² | `methode.yaml`, `config.py`, `metrics.py`, `codes.py`, `lib/codes.ts`, **`DetailView.tsx` (Logik `< 15`)**, Texte in 6 Ansichten | Wert gleich, nicht an die Methode gekoppelt | Katalog bereinigt (`min_obs_trend`); App offen |
| P7 | Anker 7 Kalendertage | `methode.yaml`, `config.py`, `windows.py`, `codes.py`, `signals.py`, `lib/depots.ts`, `lib/chartmath.ts` | Wert gleich, Regel abweichend (B2) | offen |
| P8 | Abdeckung 20 % / 1 Tag / 80 % Volumen | `methode.yaml`, `config.py`, `codes.py`, `lib/glossary.ts`, `lib/codes.ts` | gleich, Glossar fest | offen (Glossartext aus dem Manifest) |
| P9 | Umsatzschwellen | 10 Mio. USD (Gruppe B, Umschichtung), 2 Mio. USD (Vorauswahl), 2 Mio. EUR (AktienPilot-Handelsfilter), 50/2 Mio. EUR (Spreadstufen `ap/kosten.py`), 250.000 EUR (`signals.py`), 1 Mio. EUR (`lib/top.ts`) | Werte, Währungen und Definitionen abweichend | bewusst getrennt nach Zweck, offen: ein benannter Liquiditätsblock |
| P10 | sehr niedriger Umsatz 1 Mio. USD | `methode.yaml`, `config.py`, `lib/turnover.ts`, Texte | Texte fest | offen |
| P11 | Bit „Einzelsprung“ | `codes.py` ↔ `lib/turnover.ts` | gleich | offen (aus dem Manifest lesen) |
| P12 | Status-/Bitnummern und Kurztexte | `codes.py` ↔ `lib/codes.ts` | Nummern gleich, Texte nur in TS | offen |
| P13 | Yahoo-Verzögerung je Börse, Plausibilität 0–240 | `jobs/kursaktualisierung.py` ↔ `lib/livekurse.ts`; `providers/yahoo.py` ↔ `lib/livekurse.ts` | gleich (59 Endungen verglichen) | offen (aus einer Datei erzeugen) |
| P14 | Abrufprotokoll der Kursaktualisierung | `jobs/kursaktualisierung.py` ↔ `lib/aktualisierung.ts`, `lib/livekurse.ts` | gleich | gespiegelt, gemeinsamer Vertragstest vorhanden |
| P15 | Datenalter / „aktuell“ | `lib/livekurse.ts`, `jobs/kursaktualisierung.py`, `methode.yaml`, `lib/depots.ts` (≤ 7 T), `aktienpilot.yaml` (3 Sitzungen), `lib/freshness.ts`, `pipeline.yaml` | abweichende Regeln je Zweck | Katalog: `datenalter` (eine Definition); übrige offen |
| P16 | Höchstalter Wechselkurs | `methode.yaml` (5), `config.py`, `fx.py`, `lib/depots.ts`, **`jobs/facts.py` (14)** | abweichend | offen |
| P17 | Kosten und Steuern | Umschichtung (`methode.yaml`, `rotation.py`: pauschal 0,1 %) ↔ AktienPilot (`aktienpilot.yaml`, `ap/kosten.py`: Spread nach Liquidität, Slippage, FX, TR-Aufschlag) | Steuer gleich, Spread abweichend | offen: ein Kostenmodell (`ap/kosten.py`) |
| P18 | Umschichtungs-Defaults dreifach | `methode.yaml` ↔ `config.py` ↔ `rotation.py` | gleich | offen |
| P19 | Konfigurations-Defaults in Code und YAML | `config.py` ↔ `methode.yaml`; `ap/config.py` ↔ `aktienpilot.yaml`; `jobs/facts.py` ↔ `pipeline.yaml` | gleich | offen: YAML maßgeblich, Test Code ↔ YAML |
| P20 | Aufbewahrung | `pipeline.yaml` ↔ `site.py`, `cli.py`, `jobs/state.py`, `jobs/daily.py` | gleich | offen |
| P21 | Standardauswahl Bericht/Depots/Top | `lib/report.ts`, `lib/depots.ts`, `lib/top.ts` ↔ Lineal-Vorlage (`aktienpilot.yaml`) | in TS doppelt; Lineal fachlich eigen | offen |
| P22 | Ansichts-Defaults | `lib/storage.ts` ↔ `lib/scoring.ts`, `GridView.tsx`, `FrequencyView.tsx`, `ReturnLadderView.tsx`, `MatrixView.tsx`, `ReturnRankingsView.tsx` | teils abweichend | offen (`DEFAULT_PREFS` als einzige Quelle) |
| P23 | Automatik-Takt, Grenzen Regeldepot | `lib/aktualisierung.ts` ↔ `lib/storage.ts`; `lib/rotation.ts` ↔ `lib/storage.ts` | gleich | offen (importieren statt kopieren) |
| P24 | ISIN-Prüfung | `util/isin.py` ↔ `lib/instruments.ts` (Prüfziffer) ↔ `lib/depots.ts`, `lib/storage.ts`, `lib/livekurse.ts` (nur Muster) | abweichend | offen (eine TS-Funktion mit Prüfziffer) |
| P25 | Börsenstammdaten | `boersen.yaml` ↔ `lib/markets.ts`, `lib/aktualisierung.ts` (Handelszeiten fest), `aktienpilot.yaml` (Leitindizes) | verteilt | offen |
| P26 | Untereinheiten GBp/ZAc/ILA | `providers/exchanges.py` ↔ `lib/depots.ts` | gleich | offen |
| P27 | Signal-Schwellen 65/50 | `signals.py` ↔ Texte in `signals_writer.py`, `lib/signals.ts`, `lib/glossary.ts` | Werte gleich, Texte fest | offen |
| P28 | RSI-/Volumengrenzen | „überkauft“ > 75 (`signals.py`, `lib/top.ts`, `lib/signals.ts`), daneben 78/72 (`lib/signals.ts`); Volumenfaktor 1,5 (`lib/signals.ts`, `lib/top.ts`, S2) | teils abweichend | offen (benannte Schwellen) |
| P29 | Ampel-Reihenfolge | `signals_writer.py` ↔ `lib/signals.ts` | gleich | offen |
| B1 | Perzentil, Score, exakter Schlüssel, Untergruppe | `analytics/ranking.py` ↔ `lib/scoring.ts`, `lib/subgroup.ts` | bitgleich getestet | gespiegelt (Anzeige); Regelmotor nur Python |
| B2 | Fensterrendite | Rechenkern (`windows.py`) ↔ **`lib/depots.ts`** (Start = letzter Kurs ≤ Ziel, Ende bis 7 Tage alt, ohne Zulassung) ↔ `signals.py` (`r_30k…` aus Rohkursen) ↔ `lib/chartmath.ts` | abweichend | Katalog: nur Rechenkern (`rendite`); App/Signale offen |
| B3 | Anstiegstage | `metrics.py` (`up`) ↔ `signals.py` (Steig-Konstanz) | gleiche Idee, andere Eingaben | Katalog: `aufwaertstage` aus dem Rechenkern; Signale offen |
| B4 | Häufigkeit | `analytics/frequency.py` ↔ `lib/frequency.ts` (gegen Referenz getestet) ↔ `lib/groups.ts` (v2 „einmal zählen“ nur in TS) | Endtag je Fundstelle weicht ab; v2 nur App | Katalog: Python-Funktion; offen: v2 nach Python |
| B5 | Spitzenreiter ohne Auffällige | `snapshot_writer.py` ↔ `lib/turnover.ts` | gleich, getestet | gespiegelt |
| B6 | Ø Tagesumsatz | `turnover.py` (20 Kalendersitzungen, USD) ↔ `signals.py` (20 Kerzen, EUR) ↔ `jobs/facts.py` (30 T) ↔ `rotation.py` (4 Wochen) ↔ `ap/risiko.py` | 5 Definitionen | Katalog: `tagesumsatz_usd` (Rechenkern); Varianten offen |
| B7 | relatives Volumen | `signals.py` ↔ `lib/chartmath.ts` | abweichend | Katalog: `volumenfaktor` (ap/indikatoren-Regel, fehlende ≠ 0); übrige offen |
| B8 | SMA, RSI, ATR, Hoch | `signals.py` ↔ `ap/indikatoren.py` | ATR abweichend (einfaches Mittel gegenüber Wilder) | offen: Signale auf `ap/indikatoren.py` umstellen (neue Signalversion) |
| B9 | Perzentil-Varianten | `ap/indikatoren.py` ↔ `signals.py` ↔ `lib/signals.ts` | zwei Formeln | offen (eindeutig benennen) |
| B10 | FX-Umrechnung | `fx.py` ↔ `lib/depots.ts` | gleich | offen |
| B11 | Tagesänderung | Rechenkern (h = 1) ↔ `signals.py` ↔ `lib/livekurse.ts` | drei Quellen | Katalog: `tagesaenderung` (Schluss zu Schluss), Live getrennt |
| B12 | Signal-Listen | `signals_writer.py` ↔ `lib/signals.ts` | Schwellen abweichend | offen |
| B13 | Preis-OLS im Chart | `metrics.py` ↔ `lib/chartmath.ts` | gleich, getestet | gespiegelt |
| B14 | „handelbar“ zweimal in `signals.py` | – | gleich | offen |
| B15 | Handelszeiten | `lib/aktualisierung.ts` ↔ Börsenkalender | ohne Feiertage | offen |
| T1 | CSV-Spalten | 11 Ansichten | gleiche Kennzahl, andere Spaltennamen | offen (Spaltenname aus dem Katalog) |
| T2 | Erklärtexte mit Zahlen | `lib/glossary.ts`, `lib/signals.ts`, `signals.py`, `codes.py`, `HelpView.tsx`, `MethodView.tsx`, `docs/03` | fest, teils veraltet | offen (Erklärung im Katalog) |
| R1 | zweite Backtest-Engine | `analytics/rotation.py::backtest` (Umschichtungs-Regel) | eigene Engine | offen: Umschichtungs-Regel als Regel des Baukastens führen |

## 3. Gleiche Namen für verschiedene Größen (bewusst getrennt, Abschnitt 32.2)

* **Gleichmäßigkeit**: R² der Preisregression des Lineals über Kalendertage (`r2`) – R² der Log-Regression über
  Handelssitzungen in S1 (`log_r2`) – Steig-Konstanz der Signale. Im Katalog getrennte IDs mit Erklärung.
* **60/40**: Bewertungsgewicht Gleichmäßigkeit/Rendite der Rangliste (`gewicht`) – S1-Gewichte von R²/Steigung –
  Kapitalgewichte (`kapital`) einer Regel.
* **Trend**: Wochenrendite der Umschichtung – Lage zu MA20/50 (Signale) – Marktfilter MA200.
* **Schwankung**: Rauschen um die Gerade (`rauschen`), σ 60, Börsenplatz-Rauschen, Jahresschwankung der Prognose, ATR.
* **Impulstag** (Schlüssel) = **Einzelsprung** (App): Alias.
* URL-Parameter `w` (Gewichtung, in der Umschichtung Trendwochen, im Bericht die Auswahl) und `n` (Listenlänge bzw.
  Aktienanzahl).

## 4. Einstellungen, die an mehreren Stellen liegen

| Einstellung | Orte | Status |
|---|---|---|
| Zeitraum `h` | Einstellungen (90), URL je Ansicht, Rendite-Liste (min(h, 7)), Häufigkeit `von/bis`, Depots `t/zr`; Lineal-Vorlage 30 | offen (zurückgeschrieben nur von Ranking, Start, Einstellungen) |
| Gewichtung `w` | Einstellungen (60), URL, Häufigkeit/Leiter fest 60, Matrix 0; Lineal-Vorlage 50 | offen |
| Gruppe A/B | Einstellungen, URL `g`, `gruppen/fg`, Potenzial `g=b`; Lineal-Vorlage A | offen |
| Auffällige ausblenden | Einstellungen `ohneAuffaellige`, Top `ohne=1` | offen (zwei Schalter) |
| Häufigkeit-Gewichtungen | `frequencyWeights` (nirgends verwendet), URL `tab/w`, `gw/fw` | offen |
| Merkliste | `tr-vergleich:watchlist:v1`, Raster-URL `isins/titel` | offen |
| Aktualisierungsaufträge | `tr-vergleich:aktualisierungen:v1`, `tr-aktualisierung-v1` | offen (zwei Schlüssel) |
| Methode, Betrieb, AktienPilot | YAML und Code-Defaults (P18/P19) | offen |

## 5. Was der Katalog noch nicht abdeckt (Stand 31.10.2026)

Signale (Gesamt-, Kurz-, Langwertung, 13 Komponenten, Steig-Konstanz, Trefferquoten), Kursziel-Spanne und Kaufen-Anteil,
Börsenwert, KGV/PEG/Beta/52-Wochen-Hoch/-Tief, Termin der Geschäftszahlen, Nachrichten, Community; Start-/Endkurs und
Startsitzung, Hauptstatus 1–18, übrige Hinweis-Bits, Umsatzstatus; Identitätsstatus, Instrumenttyp, TR-Verzeichnis, Merkliste;
Zwischenstand und Live-Kurszustand; App-Rechnungen „Top nach Zahlen“, Musterdepot-Rendite, Umschichtung; Börsenplatz-Abweichung
als Zahl; Total Return; Einstand, offene Orders, realisierter Gewinn, Budget, Zielgewicht. Diese Liste wird beim Ausbau
abgearbeitet; jede neue Kennzahl bekommt einen Registrierungs- und Gleichheitstest (Abschnitt 31.8).
