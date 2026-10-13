# Datenvertrag der statischen Schnittstelle (`static-api-v1`)

Die App liest ausschließlich statische Dateien unter `<website>/data/`. Es gibt keinen Server mit Eingaben, also auch keine Schnittstelle, über die jemand einen Lauf auslösen oder Daten verändern könnte. Jede Datei nennt ihr Schema (`schema`); inkompatible Änderungen bekommen eine neue Schemanummer.

## Dateien

| Pfad | Form | Schema | Inhalt |
|---|---|---|---|
| `data/status.json` | JSON, unverschlüsselt | `tr-status/1` | Betriebszustand: neuester und neuester vollständiger Datenstand, letzter Kursstichtag, letzter erfolgreicher Lauf (Herzschlag), letzter Lauf mit Status und Meldung, Zeitplan, Herzschlag-Grenze, Softwareversion, Verschlüsselung ja/nein, auf der Website vorhandene Stände. Keine Kurse. |
| `data/crypto.json` | JSON, unverschlüsselt | `tr-crypto/1` | Schlüsselparameter ohne Geheimnis: `kdf` (PBKDF2-HMAC-SHA256), `iterations` (600.000), `salt_b64` (16 Byte), `cipher` (AES-256-GCM), `container` (TRA1), Prüfwert `check_b64` mit `check_aad`. Bei DEMO ohne Passphrase nur `enabled: false`. |
| `data/snapshots/index.json` | JSON, unverschlüsselt | `tr-snapshot-index/1` | Liste der Stände auf der Website: `snapshot_id`, Kursstichtag, Rechenzeit, Vollständigkeit, Datenmodus, Universumsgröße, vergleichbare Aktien im 30-Tage-Fenster, `supersedes`, alle Versionen. |
| `data/snapshots/<id>/manifest.bin` | TRA1 | `tr-manifest/1` | Stichtag, Rechen- und Veröffentlichungszeit, Lauf, Vollständigkeit je Börse, Idempotenzschlüssel, Versionen, Methodenparameter, Universumsnachweis (Quelle, Abrufzeit, Prüfsumme, Parserversion, ISIN-Zahl), Anbieter und Lizenzhinweis, `flags`, Prüfergebnisse, Codetabellen, Abdeckungsbilanz, Prüfsummen aller Dateien |
| `…/instruments.bin` | TRA1 | `tr-instruments/1` | Spaltenweise je Instrument (Index `idx` = Position): ISIN, Name, TR-Name, Aliasse (frühere Namen, Ticker, Symbole), Ticker, Symbol, Börse, MIC, Zeitzone, Währung, Kurseinheit, Typ, Identitätsstatus und Grund, Vorstatus, Gesamtstatus, Hinweis-Bits, letzter Kurs und Tag, `has_series`, Zugehörigkeit zu V und U je Fenster (Bitmasken), bestes Fenster; ab 1.1 `turnover` (Ø Tagesumsatz, siehe unten) |
| `…/overview.bin` | TRA1 | `tr-overview/1` | Je Fenster 1–90: Feldgrößen V, U und L, Spitzenreiter der 0/100-Liste auf V (`v0`) und jeder der elf Gewichtungen auf U (`u`), Renditesieger mit Gleichständen und Leerzustandsgrund (`winners`, genau 90 Zeilen, je Eintrag Start-/Endkurs `p0`/`p1` und Fensterhinweise `wf`), dasselbe für Ranking 2 (`winners_l`), Gesamtmaximum beider Listen (`overall_max`, `overall_max_l`) |
| `…/frequency.bin` | TRA1 | `tr-frequency/1` | Alle Top-10-Fundstellen je Fenster und Rangliste (`occ`, ab 1.1 auch `occ.v0l` für Ranking 2), Feldgrößen (`M.v0l`), Beschreibung der Universen (`universe`), Zählregeln, Serverreferenz der Häufigkeitsliste (native, alle Gewichtungen, Top 10) zum Abgleich in der App |
| `…/windows/<h>.bin` | TRA1 | `tr-window/1`, `part: kopf_50` | Kopfdatei: die ersten 50 Plätze jeder der dreizehn Ranglisten (v0, u0…u100, v0l) mit allen Kennzahlen |
| `…/windows/<h>.full.bin` | TRA1 | `tr-window/1`, `part: vollstaendig` | Alle Mitglieder von V mit Kennzahlen, alle Ranglisten vollständig, Status jedes Instruments (`status_b64`, 1 Byte je Instrument) |
| `…/series/<ISIN>.bin` | TRA1 | `tr-series/1` | Kursreihe (splitbereinigte Schlusskurse, Volumen, optional Eröffnung/Hoch/Tief und unbereinigter Schluss), fehlende erwartete Sitzungen (`gaps`), Startsitzung und Status je Fenster, Rangmatrix, Kapitalmaßnahmen, Quelle mit Abrufzeit und Revision |

Alle Datumswerte in Dateien sind **Epochentage** (ganze Tage seit 1970-01-01, UTC) bzw. ISO-Datumsangaben; Zeitpunkte sind UTC (`…Z`).

## Container TRA1

```
"TRA1" | flags (1 Byte) | [IV, 12 Byte – nur verschlüsselt] | Nutzlast
flags: Bit 0 = verschlüsselt, Bit 1 = gzip
Nutzlast = AES-256-GCM(Schlüssel, IV, gzip(JSON), AAD = Pfad relativ zu data/)
Schlüssel = PBKDF2-HMAC-SHA256(Passphrase, salt, 600.000 Iterationen, 32 Byte)
```

Die AAD ist der Pfad ohne `data/`, z. B. `snapshots/2026-10-12_bb7f1a00/windows/30.bin`. Eine vertauschte oder veränderte Datei lässt sich deshalb nicht entschlüsseln. Die App prüft den Schlüssel einmal gegen `check_b64` (Klartext `TR-AKTIENVERGLEICH-SCHLUESSEL-OK`, AAD `crypto-check`) und entschlüsselt dann mit Web Crypto.

## Kennzahlen eines Fensters (`tr-window/1`, Feld `m`)

Parallele Listen, eine Position je Mitglied:

| Feld | Bedeutung |
|---|---|
| `idx` | Instrumentindex in `instruments.bin` |
| `start` | tatsächliche Startsitzung (Epochentag); Ende ist immer `cutoff_day` |
| `n`, `n_exp` | belegte und erwartete Börsensitzungen im Fenster |
| `r` | Kursrendite als Anteil (0,12 = +12 %) |
| `p0`, `p1` | Start- und Endkurs (Schluss an `start` bzw. `cutoff_day`, Kurseinheit der Notierung); `r = p1 / p0 − 1` (ab 1.1) |
| `r2` | Gleichmäßigkeit R² der Preis-OLS (null, wenn nicht definiert oder weniger als 15 Kurse) |
| `slope`, `noise` | relative Steigung je Sitzung und Residualrauschen in Prozent (null unter 15 Kursen) |
| `mdd` | größter Rückgang im Fenster als Anteil |
| `vol` | Anteil der Beobachtungen mit belegtem Umsatz |
| `wf` | Hinweis-Bits des Fensters (`codes.window_warnings`) |
| `a_rv` | doppelter Durchschnittsrang der Rendite in V |
| `a_gu`, `a_ru` | doppelte Durchschnittsränge von R² und Rendite in U (null, wenn nicht in U) |

Ranglisten: `orders.v0` (0/100 auf V), `orders.u["0"…"100"]` (elf Gewichtungen auf U) und ab 1.1 `orders.v0l` (Ranking 2: 0/100 auf V ∩ L, also `orders.v0` ohne Aktien unter der Umsatzschwelle), jeweils Instrumentindizes in Rangfolge; `counts.L` = Größe von V ∩ L. `ties` nennt alle Positionen, die mit dem vorigen oder dem nächsten Platz exakt gleichauf liegen (also jedes Mitglied einer Gleichstandsgruppe).

## Ø Tagesumsatz (`instruments.turnover`, Manifest `turnover`, ab 1.1)

Parallele Listen je Instrument: `status` (`ok`, `keine_kurse`, `kalender_fehlt`, `zu_wenige_sitzungen`, `daten_fehlen`, `zu_wenig_umsatztage`, `kapitalmassnahme`, `waehrung_unbekannt`, `wechselkurs_fehlt`; Texte in `manifest.codes.turnover_status`), `usd` (Ø in USD, indikativ), `local` (Ø in Hauptwährung), `currency`, `sessions` (betrachtete Sitzungen), `with_data` (davon mit Kurs und Volumen), `positive` (davon mit Umsatz), `first`/`last` (erste und letzte betrachtete Sitzung), `fx_first`/`fx_last` (verwendete EZB-Kurstage), `liquid` (in L).

Das Manifest beschreibt unter `turnover` Definition, Schwellen, Wechselkursquelle (`wechselkurse.quelle`, `url`, `abgerufen_utc`, `erster_kurstag`, `letzter_kurstag`, `waehrungen`, `max_alter_tage`) und Zählungen je Status. Die Prüfung `ranking2_teilmenge_gleiche_rendite` im Manifest bestätigt, dass `orders.v0l` exakt `orders.v0` ohne die nicht aufgenommenen Aktien ist.

## Rechenvorschrift der App (bitgleich zum Server)

```
Perzentil P = 100 · (a/2 − 1) / (M − 1),  bei M = 1: P = 100      (a = doppelter Durchschnittsrang)
Score(w)    = (w/100) · G + (1 − w/100) · R;  w = 0 → R, w = 100 → G
```

`R` ist das Renditeperzentil, `G` das R²-Perzentil. Vergleichsfeld: nativ 0/100 → V (`a_rv`), alle anderen → U (`a_gu`, `a_ru`); Modus „gleiches Feld“ → alle elf auf U. Gerundet wird nur in der Anzeige. Der Datenvertragstest prüft die Gleichheit mit der Serverberechnung für alle Fenster und Gewichtungen.

## Rangmatrix je Aktie (`tr-series/1`, `ranks_b64`)

90 × Spaltenzahl Werte `uint16` little-endian, Base64. Zeile = Fenster 1–90, Spalten laut `rank_columns` = `v0, u0, u10, …, u100` und ab 1.1 zusätzlich `v0l` (Ranking 2), also 13 Spalten. Die App greift über den Spaltennamen zu. 0 = kein Rang. Natives Vergleichsfeld: Spalte `v0` für 0/100, sonst `u<w>`; gleiches Vergleichsfeld: `u<w>` für alle elf.

## Codes

`manifest.codes` enthält die vollständigen Texte; die App zeigt nur diese.

| Status | Bedeutung | | Status | Bedeutung |
|---:|---|---|---:|---|
| 1 | ISIN ungültig | | 10 | Keine Startsitzung (7 Tage) |
| 2 | Kein Aktieninstrument | | 11 | Startkurs fehlt |
| 3 | Identität noch nicht geprüft | | 12 | Zu viele fehlende Sitzungen (< 98 %) |
| 4 | Identität unklar | | 13 | Kapitalmaßnahme/Datenfehler prüfen |
| 5 | Börsenkalender fehlt | | 14 | Zu wenig belegtes Volumen (< 80 %) |
| 6 | Daten fehlen | | 15 | Rendite veröffentlicht, zu wenig Tagesdaten für Gleichmäßigkeit |
| 7 | Markt am Stichtag geschlossen | | 16 | Rendite veröffentlicht, nicht steigend |
| 8 | Schlusskurs am Stichtag fehlt | | 17 | Rendite veröffentlicht, Gleichmäßigkeit nicht definiert |
| 9 | Zu kurze Historie | | 18 | Gleichmäßig steigend bewertbar |

Rendite veröffentlicht (Menge V): Status 15–18. Gleichmäßig steigend (Menge U): Status 18.

## Regeln für die App

- Alle Dateien einer Ansicht stammen aus genau einem Stand; die App verwirft Dateien, deren `snapshot_id` nicht zum aktiven Stand passt, und Fensterdaten, deren `h` nicht zur Auswahl passt.
- Daten werden nie aufgefüllt: fehlende Sitzungen bleiben Lücken, ein fehlender Wert bleibt „–“ mit Grund.
- Ein älterer Stand wird als „älterer Stand“ gekennzeichnet, DEMO-Daten in jeder Ansicht und jedem Export als DEMO.
