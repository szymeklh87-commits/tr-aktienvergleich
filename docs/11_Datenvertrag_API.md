# Datenvertrag der statischen Schnittstelle (`static-api-v1`)

Die App liest ausschließlich statische Dateien unter `<website>/data/`. Es gibt keinen Server mit Eingaben, also auch keine Schnittstelle, über die jemand einen Lauf auslösen oder Daten verändern könnte. Jede Datei nennt ihr Schema (`schema`); inkompatible Änderungen bekommen eine neue Schemanummer.

## Dateien

| Pfad | Form | Schema | Inhalt |
|---|---|---|---|
| `data/status.json` | JSON, unverschlüsselt | `tr-status/1` | Betriebszustand: neuester und neuester vollständiger Datenstand, letzter Kursstichtag, letzter erfolgreicher Lauf (Herzschlag), letzter Lauf mit Status und Meldung, Zeitplan, Herzschlag-Grenze, Softwareversion, Verschlüsselung ja/nein, auf der Website vorhandene Stände; ab 1.2 `naechster_kursstand` (`datum`, `ab_utc`, `boersen`: nächster möglicher Kursstichtag und ab wann ein Lauf ihn berechnen kann) und `aktualisieren` (`starten_url`, `laeufe_url` auf GitHub; nur in GitHub Actions gesetzt); ab 1.17 in `schedule` zusätzlich `nachtlauf_utc` (z. B. `"22:37"`) und `nachtlauf_wochentage` (1 = Montag … 7 = Sonntag), in `last_run.trigger` auch `"nachtlauf"` (vom Workflow „Nachtlauf“ gestartet). Keine Kurse, keine Schlüssel. Die App liest die Datei mit Zeitstempel-Parameter (`?t=…`), um den Zwischenspeicher von GitHub Pages zu umgehen. |
| `data/crypto.json` | JSON, unverschlüsselt | `tr-crypto/1` | Schlüsselparameter ohne Geheimnis: `kdf` (PBKDF2-HMAC-SHA256), `iterations` (600.000), `salt_b64` (16 Byte), `cipher` (AES-256-GCM), `container` (TRA1), Prüfwert `check_b64` mit `check_aad`. Bei DEMO ohne Passphrase nur `enabled: false`. |
| `data/snapshots/index.json` | JSON, unverschlüsselt | `tr-snapshot-index/1` | Liste der Stände auf der Website: `snapshot_id`, Kursstichtag, Rechenzeit, Vollständigkeit, Datenmodus, Universumsgröße, vergleichbare Aktien im 30-Tage-Fenster, `supersedes`, alle Versionen. |
| `data/snapshots/<id>/manifest.bin` | TRA1 | `tr-manifest/1` | Stichtag, Rechen- und Veröffentlichungszeit, Lauf, Vollständigkeit je Börse, Idempotenzschlüssel, Versionen, Methodenparameter, Universumsnachweis (Quelle, Abrufzeit, Prüfsumme, Parserversion, ISIN-Zahl), Anbieter und Lizenzhinweis, `flags`, Prüfergebnisse, Codetabellen, Abdeckungsbilanz, `files` (bis 1.14: Prüfsummen aller Dateien in `sha256_plaintext`; ab 1.15: `bytes`, `anzahl`, `pruefsummen` = Name der Prüfsummen-Datei und `sha256_pruefsummen` = deren Prüfsumme) |
| `data/snapshots/<id>/pruefsummen.bin` (ab 1.15) | TRA1 | `tr-pruefsummen/1` | SHA-256 des Klartexts jeder Datei des Stands (`sha256_plaintext`, ohne Manifest); verankert über `manifest.files.sha256_pruefsummen`. Die App lädt sie nicht – das Manifest bleibt dadurch klein (bei rund 11.000 Kursreihen 0,5 MB weniger bei jedem Start) |
| `…/instruments.bin` | TRA1 | `tr-instruments/1` | Spaltenweise je Instrument (Index `idx` = Position): ISIN, Name, TR-Name, Aliasse (frühere Namen, Ticker, Symbole), Ticker, Symbol, Börse, MIC, Zeitzone, Währung, Kurseinheit, Typ, Identitätsstatus und Grund, Vorstatus, Gesamtstatus, Hinweis-Bits, letzter Kurs und Tag, `has_series`, Zugehörigkeit zu V und U je Fenster (Bitmasken), bestes Fenster; ab 1.1 `turnover` (Ø Tagesumsatz, siehe unten) |
| `…/overview.bin` | TRA1 | `tr-overview/1` | Je Fenster 1–90: Feldgrößen V, U und L, Spitzenreiter der 0/100-Liste auf V (`v0`) und jeder der elf Gewichtungen auf U (`u`), Renditesieger mit Gleichständen und Leerzustandsgrund (`winners`, genau 90 Zeilen, je Eintrag Start-/Endkurs `p0`/`p1` und Fensterhinweise `wf`), dasselbe für Ranking 2 (`winners_l`), Gesamtmaximum beider Listen (`overall_max`, `overall_max_l`) |
| `…/frequency.bin` | TRA1 | `tr-frequency/1` | Alle Top-10-Fundstellen je Fenster und Rangliste (`occ`, ab 1.1 auch `occ.v0l` für Ranking 2), Feldgrößen (`M.v0l`), Beschreibung der Universen (`universe`), Zählregeln, Serverreferenz der Häufigkeitsliste (native, alle Gewichtungen, Top 10) zum Abgleich in der App |
| `…/windows/<h>.bin` | TRA1 | `tr-window/1`, `part: kopf_50` | Kopfdatei: die ersten 50 Plätze jeder der dreizehn Ranglisten (v0, u0…u100, v0l) mit allen Kennzahlen |
| `…/windows/<h>.full.bin` | TRA1 | `tr-window/1`, `part: vollstaendig` | Alle Mitglieder von V mit Kennzahlen, alle Ranglisten vollständig, Status jedes Instruments (`status_b64`, 1 Byte je Instrument) |
| `…/series/<ISIN>.bin` | TRA1 | `tr-series/1` | Kursreihe (splitbereinigte Schlusskurse, Volumen, optional Eröffnung/Hoch/Tief und unbereinigter Schluss), fehlende erwartete Sitzungen (`gaps`), Startsitzung und Status je Fenster, Rangmatrix, Kapitalmaßnahmen, Quelle mit Abrufzeit und Revision |
| `…/rotation/index.bin` | TRA1 | `tr-rotation/1` | ab 1.3: Umschichtungs-Regel – Regelparameter, Kosten, Vorauswahl, Wochenraster, Fortschritt der Langhistorie, Kennzahlen und Kurzstand aller Varianten (siehe unten) |
| `…/rotation/<Variante>.bin` | TRA1 | `tr-rotation-variante/1` | ab 1.3: Verlauf, Orders und Tagesvorschlag einer Variante (`n5-monatlich-w13-k10000` usw.) |
| `…/fx.bin` | TRA1 | `tr-fx/1` | ab 1.9: Euro-Referenzkurse der letzten 100 Tage bis zum Stichtag – `tage` (aufsteigende Epochentage), `je_eur` (je Währung Einheiten je EUR, `null` an Tagen ohne Kurs), `quelle`, `url`, `abgerufen_utc`, `max_alter_tage` (5), `basis`. Rechengrundlage der Musterdepots in USD oder EUR; im Manifest `fx` (`datei`, `quelle`, `erster_tag`, `letzter_tag`, `waehrungen`, `max_alter_tage`) oder `null`, wenn keine Kurse vorlagen. Ältere Stände haben weder Datei noch Feld |

| `data/signale/<id>/signale.bin` | TRA1 | `tr-signale/1` | ab 1.6: Signal-Stand – Spalten je Aktie (`isin`, `kurz`, `kurz_ampel`, `kurz_grund`, `lang`, `lang_ampel`, `lang_grund`, `potenzial`, `ziel`, `ziel_tief`, `ziel_hoch`, `analysten`, `kaufen`, `handelbar`, `kurs`, `kurs_tag`, `sektor`, `punkte` je Signal, `merkmale` für Listen, `steigt_5`/`steigt_20`), `regeln` (Gewichte, Ampelregeln, Namen und Erklärungen der Signale, Hinweis), `kalibrierung` (Trefferquote je Punktebereich), `anzahl`, vorsortierte `listen` (`beide`, `kurz`, `lang`, `potenzial`, je bis 100 Indizes). Unabhängig vom Kurs-Datenstand; `snapshot_id` und `cutoff_day` nennen die Kurse, auf denen er beruht |
| `data/signale/<id>/details/<ISIN>.bin` | TRA1 | `tr-signal-detail/1` | ab 1.6: Einzelansicht – `komponenten` (je Signal Punkte, Text, Ton, Horizont), `merkmale`, Kursziel und Quellen (`ziel_quellen`), `wahrscheinlichkeit`, `prognose` (übliche Schwankung, Bänder 3 und 12 Monate), `kennzahlen` (Analysten, Empfehlungen der letzten 4 Monate, Urteile der Häuser, Bewertung, Wachstum, Finanzen, Risiko, Termine, Branche), `bewertung_tc`, `nasdaq`, `nachrichten`, `community`, `abgerufen` (Zeitpunkte je Quelle), `verlauf` (Tageskurse bis gut 1 Jahr), `wochen` (Wochenkurse davor, bis 3 Jahre) |

`data/status.json` enthält ab 1.6 `signale` (`id`, `erstellt_utc`, `kursstand`, `snapshot_id`, Zählungen, `version`; ab 1.7 `gesamt_stark`, `gesamt_mittel`) – fehlt der Schlüssel, gibt es noch keinen Signal-Stand. AAD der Signal-Dateien ist wie bei den Datenständen der Pfad unterhalb von `data/` (z. B. `signale/<id>/signale.bin`).

**Ab 1.7 (`signale-v2`)** zusätzlich in `signale.bin`: `gesamt` (Gesamtwertung 0–100 je Aktie, `null` ohne 60 Tage Historie), `gesamt_stufe` (`stark`, `mittel`, `schwach`, `ohne`), `gesamt_teile` (`konstanz`, `kursziel`, `kurzfristig`, `qualitaet` – Punkte je Teil), `gesamt_steigt_20`/`gesamt_steigt_60` (Trefferquote der Steig-Konstanz für den Punktebereich der Aktie), `kalibrierung_konstanz` (Horizonte 20 und 60 Sitzungen), in `merkmale` `steig_30`/`tage_30` … `steig_90`/`tage_90` (Anstiegstage und Vergleiche je Zeitraum) und `r_30k`/`r_60k`/`r_90k` (Kursveränderung über 30/60/90 Kalendertage), in `regeln` `gesamt_gewichte`, `gesamt_namen`, `gesamt_erklaerungen`, `gesamt_regel`, `gesamt_stark_ab`, `gesamt_mittel_ab`, `konstanz_zeitraeume`, in `anzahl` `gesamt`, in `listen` `gesamt` (bis 150 Indizes). In `details/<ISIN>.bin`: `gesamt`, `gesamt_stufe`, `gesamt_teile`, `konstanz` (je Zeitraum `tage`, `steigtage`, `vergleiche`, `rendite`, `punkte`) und `wahrscheinlichkeit_gesamt`.

**Ab Software 1.11** zusätzlich in `signale.bin`: `boersenwert_eur` (Börsenwert je Aktie in EUR oder `null` – Yahoo „marketCap“ in der Hauptwährung der Notierung, auch bei Kursen in Pence, Cent oder Agorot, umgerechnet mit dem EZB-Referenzkurs des Kursstichtags; 4 signifikante Stellen); in `details/<ISIN>.bin` dasselbe als Einzelwert `boersenwert_eur`. Die Signal-Version bleibt `signale-v2` (zusätzliches Feld; ältere Apps ignorieren es, die App ab 1.11 kommt ohne es aus). Ab 1.10 tragen `status.json` und das Manifest eines Zwischenstands `zwischenstand.stufe` (`null` oder `{nummer, von, aktien?, grundlage?, beschreibung?}`) für die gestaffelte Aktualisierung.

**Ab Software 1.14 (Methode `tr-methode-1.9.0`):** Im Manifest `letzter_schlusskurs` = `{aktien, je_kalender, max_verpasste_sitzungen, beschreibung}` – Aktien ohne Kurs am Stichtag, die mit ihrem letzten Schlusskurs zählen (ihr Ende je Aktie ist `instruments.last_close_day`, wenn es vor `cutoff_day` liegt; alle Fenster dieser Aktie enden dort). In `overview.bin` zusätzlich `winners_klar` und `winners_l_klar` (je 90 Zeilen wie `winners`, ohne Aktien mit Ø Tagesumsatz unter `klar_regel.umsatz_unter_usd` oder nicht bestimmbar und ohne Fensterhinweis Bit `klar_regel.einzelsprung_bit`; je Zeile `rank` = Platz in der vollständigen Rangliste, `M` = Zahl der Unauffälligen, `empty: "nur_auffaellige"`, wenn alle auffällig sind) und `klar_regel` (`umsatz_unter_usd`, `einzelsprung_bit`, `text`). Ältere Apps ignorieren die Felder; die App ab 1.14 kommt ohne sie aus (dann vollständige Listen).

**Zwischenstand (ab 1.8):** ein Stand wie die offiziellen (gleiche Dateien unter `data/snapshots/<id>/`), Kennung `JJJJ-MM-TT_zHHMM…`. Im Manifest `art: "zwischenstand"` und `zwischenstand` (`stichtag`, `kurse_ab_utc`, `kurse_bis_utc`, `abgerufen_utc`, `aktien_mit_kurs`, `davon_sitzung_beendet`, `abrufe`, `gedrosselt`, `offizieller_stand`, `offizieller_stichtag`, `tagwahl`, `boersen_mit_kurs`, `boersen_ohne_kurs`, `oeffnung_utc`, `beschreibung`), `provider.intraday: true`, `rotation: null`, `venue_check` mit Hinweis „nicht geprüft“. In `series/<ISIN>.bin` kennzeichnet `provisional` (`day`, `time_utc`, `session_closed`) den vorläufigen letzten Punkt. Im Index trägt der Eintrag `art`, `kurse_bis_utc`, `aktien_mit_kurs`, `offizieller_stand`. In `status.json`: `zwischenstand` (`snapshot_id`, `stichtag`, `kurse_bis_utc`, `erstellt_utc`, `aktien_mit_kurs`, `offizieller_stand`) – nur solange er neuer ist als der neueste offizielle Stand; dann zeigt `latest_snapshot_id` auf ihn und `latest_official_snapshot_id` auf den offiziellen Stand.

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
| `up` | Zahl positiver Schlusskursvergleiche p_i > p_(i−1) im Fenster (von `n − 1` möglichen; ab 1.5, `kennzahlen-v2`) |
| `vol` | Anteil der Beobachtungen mit belegtem Umsatz |
| `wf` | Hinweis-Bits des Fensters (`codes.window_warnings`) |
| `a_rv` | doppelter Durchschnittsrang der Rendite in V |
| `a_gu`, `a_ru` | doppelte Durchschnittsränge von R² und Rendite in U (null, wenn nicht in U) |

Ranglisten: `orders.v0` (0/100 auf V), `orders.u["0"…"100"]` (elf Gewichtungen auf U) und ab 1.1 `orders.v0l` (Ranking 2: 0/100 auf V ∩ L, also `orders.v0` ohne Aktien unter der Umsatzschwelle), jeweils Instrumentindizes in Rangfolge; `counts.L` = Größe von V ∩ L. `ties` nennt alle Positionen, die mit dem vorigen oder dem nächsten Platz exakt gleichauf liegen (also jedes Mitglied einer Gleichstandsgruppe). Reihenfolge ab `ranking-11w-v2` (1.5): ungerundeter Score absteigend, dann ungerundete Kursrendite absteigend, dann ISIN aufsteigend – für alle elf Gewichtungen (bis 1.4 bei 100/0: R², dann Steigung, Rauschen; bei gemischten Gewichtungen zwischen Rendite und ISIN zusätzlich R²).

## Ø Tagesumsatz (`instruments.turnover`, Manifest `turnover`, ab 1.1)

Parallele Listen je Instrument: `status` (`ok`, `keine_kurse`, `kalender_fehlt`, `zu_wenige_sitzungen`, `daten_fehlen`, `zu_wenig_umsatztage`, `kapitalmassnahme`, `waehrung_unbekannt`, `wechselkurs_fehlt`; Texte in `manifest.codes.turnover_status`), `usd` (Ø in USD, indikativ), `local` (Ø in Hauptwährung), `currency`, `sessions` (betrachtete Sitzungen), `with_data` (davon mit Kurs und Volumen), `positive` (davon mit Umsatz), `first`/`last` (erste und letzte betrachtete Sitzung), `fx_first`/`fx_last` (verwendete EZB-Kurstage), `liquid` (in L).

Das Manifest beschreibt unter `turnover` Definition, Schwellen, Wechselkursquelle (`wechselkurse.quelle`, `url`, `abgerufen_utc`, `erster_kurstag`, `letzter_kurstag`, `waehrungen`, `max_alter_tage`) und Zählungen je Status. Die Prüfung `ranking2_teilmenge_gleiche_rendite` im Manifest bestätigt, dass `orders.v0l` exakt `orders.v0` ohne die nicht aufgenommenen Aktien ist.

## Zweiter Börsenplatz (`instruments.venue`, `windows/<h>.xv`, Manifest `venue_check`, ab 1.2)

Nur geprüfte Aktien, dünn besetzt (Listen gleicher Länge, Schlüssel `idx` = Instrumentindex):

- `instruments.venue`: `status` je Aktie (`geprueft`, `kein_vergleichsplatz`, `abruf_fehlgeschlagen`, `nicht_geprueft`; Texte in `manifest.codes.venue_status`), `symbol`, `exchange_key`, `exchange` (Name), `currency` (Hauptwährung), `price_unit` (wie geliefert, z. B. GBp), `level` (Endkurs dort, umgerechnet, ÷ Endkurs Referenz − 1), `level_flag` (über der Schwelle), `end_day`, `end_price` (Schlusskurs dort, gelieferte Einheit).
- `windows/<h>.bin` und `windows/<h>.full.bin`, Feld `xv` (nur Aktien der jeweiligen Datei): `status` je Aktie und Zeitraum (`ok`, `abweichung`, `keine_kurse`, `wechselkurs_fehlt`; Texte in `manifest.codes.venue_pair_status`), `r` (Kursrendite dort, in Referenzwährung), `dev` ((1 + r dort) / (1 + r Referenz) − 1), `d0`/`d1` (verwendete Kurstage dort), `p0`/`p1` (Schlusskurse dort).
- `overview.bin`: jede Siegerzeile (`winners`, `winners_l`) trägt dasselbe Ergebnis als `xv` (oder `null`, wenn nicht geprüft).
- Fensterhinweis Bit 5 (`m.wf`, `entries[].wf`) = „Auffällige Kursabweichung zwischen Börsenplätzen“, gesetzt genau bei `xv.status = abweichung` (Prüfung `boersenplatz_kennzeichen`).
- Manifest `venue_check`: Version, Regeln (`plaetze`, `bevorzugt`, `schwelle_wertentwicklung`, `schwelle_endkurs`, `max_abstand_tage`, `max_aktien`), `beschreibung`, `hinweis` (z. B. Zeitbudget erreicht), ab 1.5.1 `abgebrochen` (`true`: Abgleich wegen eines Fehlers übersprungen, keine Ergebnisse und keine Kennzeichen; die App zeigt dann „In diesem Datenstand nicht abgeglichen“); ab `boersenplatz-v3` zusätzlich `schwankung_faktor`, `schwankung_sitzungen`, `schwelle_hoechstens`, `nur_mit_umsatz` und `auswertung` (was nach der festen 10-%-Regel auffällig gewesen wäre: `feste_schwelle_auffaellig`, `feste_schwelle_aktien`, `davon_ohne_umsatz`, `davon_in_schwankungsbreite`, `davon_weiter_auffaellig`, `schwelle_median`, `schwelle_max`, `schwelle_erhoeht_aktien`). `instruments.venue` hat ab v3 je geprüfter Aktie `noise` (übliche Tagesschwankung, logarithmisch), `limit_r` und `limit_l` (angewandte Schwellen als Abweichung, z. B. 0,40); neuer Zeitraum-Status `kein_handel` (kein Umsatz am Vergleichsplatz am Start- oder Enddatum) und Zählungen (`kandidaten`, je Status, auffällige Aktien, Aktie-Zeitraum-Paare je Status). Ältere Stände haben keinen Abschnitt; die App zeigt dann „nicht abgeglichen“.

## Gruppe B (ab 1.4, `gruppen-v1`)

Alle Felder sind Ergänzungen; ältere Stände haben sie nicht (die App zeigt dann „Gruppe B noch nicht berechnet“).

- `windows/<h>.bin` und `.full.bin`: `orders.ul` und `ties.ul` (je Gewichtung `"0"` … `"100"`, Vergleichsmenge U ∩ L), `counts.UL`, je Mitglied `m.a_rvl` (doppelter Durchschnittsrang der Rendite in V ∩ L), `m.a_gul`, `m.a_rul` (R² und Rendite in U ∩ L; `null` außerhalb). Gruppe B nativ 0/100 = `orders.v0l` (Ranking 2). Scores: `P = 100 · (a/2 − 1) / (M − 1)` mit M = `counts.L` bzw. `counts.UL`, Score wie in Gruppe A.
- `overview.bin`: `v0l` (Spitzenreiter 0/100 der Gruppe B je Zeitraum, gleiches Zeilenformat wie `v0`) und `ul` (je Gewichtung), `counts.UL`; neuer Leerzustand `keine_aktie_mit_umsatz`.
- `frequency.bin`: `occ.ul` (Top-10-Fundstellen je Gewichtung), `M.ul`, `universe.ul`, `server_reference_b` (Referenz der Gruppe B wie `server_reference`), `starts` (Startsitzung je Börsenkalender für die Zeiträume 1–90; Grundlage für „identische Kursfenster nur einmal zählen“).
- `instruments.bin`: `calendar` (Börsenkalender der Referenznotierung).
- `series/<ISIN>.bin`: Rangmatrix mit 24 Spalten (`v0, u0 … u100, v0l, ul0 … ul100`).
- Nachweisarchiv: zusätzlich `liquid` (Menge L), damit Ranking 2 und Gruppe B reproduzierbar sind.

## Ab 1.5 (`tr-methode-1.7.0`, `kennzahlen-v2`, `ranking-11w-v2`, `frequency-v2`)

Alles Ergänzungen; ältere Stände haben die Felder nicht, die App fällt dann auf die bisherige Darstellung zurück.

- `windows/<h>.bin` und `.full.bin`: `m.up` (siehe oben).
- `overview.bin`: jede Spitzenreiterzeile (`v0`, `u`, `v0l`, `ul`) trägt `n` = Zahl der Schlusskurse der Spitzenaktie im Fenster. Neu `same_set` = `{v0, u, v0l, ul}`: je Vergleichsmenge 90 Zahlen; Eintrag `k` ist der kleinste Zeitraum mit demselben Bestand aus ISIN und tatsächlichem Startdatum wie Zeitraum `k + 1` (sonst `k + 1` selbst). Gleicher Wert bedeutet: identisches Kursfenster, identische Rangliste. U gilt für alle Gewichtungen 10/90 … 100/0 gemeinsam, weil der Bestand nicht von der Gewichtung abhängt.
- `frequency.bin`: dieselbe Angabe `same_set`; Grundlage für „identische Kursfenster nur einmal zählen“ (`aggregation_version` `frequency-v2`). Bis 1.4 wurde näherungsweise über gleiche Startsitzungen je Börsenkalender (`starts`) zusammengefasst; das Feld bleibt erhalten.
- Manifest `method_comparison`: Vergleich mit den Regeln der Vorversion auf denselben Kursen – `vorher`, `jetzt`, `ausgangsmodell`, `regeln` (Texte), `paare` (`vorher_V`, `jetzt_V`, `vorher_U`, `jetzt_U`, `nicht_mehr_bewertet`, `neu_bewertet` und die Gründe), `aktien` (`vorher_mit_rendite`, `jetzt_mit_rendite`), `ranglisten` (`verglichen`, `spitze_geaendert`, bis zu zwölf `beispiele` mit `gruppe`, `h`, `w`, `vorher`, `jetzt` als Instrumentindex, `hinweis`). Gründe: in Ständen mit Methode 1.7.0 `paare.grund` mit `volumen_fehlt`, `randvolumen`, `split_im_fenster` (Mehrfachnennung möglich); ab 1.8.0 `paare.weggefallen_nach_status` (Statusnummer nach den neuen Regeln → Anzahl) und `paare.hinzugekommen_aus_status` (Statusnummer nach den alten Regeln → Anzahl), jede Veränderung genau einmal. Manifest `versions` zusätzlich `reference_model`; `method` (Methodenparameter) ab 1.8.0 zusätzlich `tolerated_missing_sessions`, `volume_basis`, `previous_rules`, `change_notes`.
- `snapshots/index.json`: jeder Eintrag trägt `versions` (wie im Manifest); die App kennzeichnet frühere Stände mit anderer Methodenversion als „eingeschränkt vergleichbar“.
- Status 13 und 14 haben erweiterte Texte (gemeldeter Split im Fenster; fehlendes oder an Start/Ende nicht positives Volumen). Die Statusnummern sind unverändert.

## Umschichtungs-Regel (`rotation/…`, Manifest `rotation`, ab 1.3)

Instrumente stehen als Index `idx` in `instruments.bin`; Tage sind Epochentage; Beträge in Euro auf Cent, Anteile, Renditen und Trends auf sechs signifikante Stellen gerundet.

- `rotation/index.bin`: `stichtag`, `standard` (Schlüssel der Standardvariante), `vorauswahl` (Aktien mit Wochenwerten), `raster` (`von`, `bis`, `wochen`, `erste_woche_mit_daten`), `langhistorie` (`aktien`, `geladen`, `offen`, `ohne_daten`), `hinweis`, `regel` (alle Parameter aus `methode.yaml`), `kosten` (`order_eur`, `spanne`, `steuersatz`, `freibetrag_eur`) und `varianten` – je Variante `key`, `aktien`, `rhythmus`, `trend_wochen`, `kapital`, `status` (`ok` oder `zu_wenig_historie`), `kennzahlen`, `aenderungen_heute`, `beschlossen_am`, `naechste_entscheidung`.
- `kennzahlen`: `start_day`, `end_day`, `tage`, `startkapital`, `endwert`, `endwert_ohne_kosten`, `vergleich_endwert`, `rendite`, `rendite_ohne_kosten`, `vergleich_rendite`, `rendite_pro_jahr` und `vergleich_pro_jahr` (null unter 365 Tagen), `max_rueckgang`, `vergleich_max_rueckgang`, `umschichtungen`, `orders`, `kaeufe`, `verkaeufe`, `gebuehren`, `spanne`, `steuern`, `verlusttopf`.
- `rotation/<Variante>.bin`: `verlauf` (`tage` = Freitage, `depot`, `ohne_kosten`, `vergleich` in Euro), `umschichtungen` (Prüftage mit ausgeführten Orders), `orders` spaltenweise (`tag` = Prüftag der Entscheidung, `ausfuehrung` = Handelstag, `idx`, `aktion` ∈ {`kauf`, `verkauf`, `aufstocken`, `reduzieren`}, `wert`, `anteil_vorher`, `anteil_nachher`, `platz`, `trend`, `gebuehr`, `spanne`, `steuer` (negativ = Erstattung), `gewinn` (nur Verkäufe)) und `vorschlag`: `tag`, `beschlossen_am` (Prüftag einer beschlossenen, noch nicht ausgeführten Umschichtung, sonst null), `naechste_entscheidung`, `depotwert`, `bargeld`, `bestand` (`idx`, `stueck`, `wert`, `anteil`, `seit`, `einstand`, `rendite`, `platz`, `trend`), `aenderungen` (`idx`, `aktion`, `anteil_vorher`, `anteil_nachher`, `wert`, `platz`, `trend`, `grund` ∈ {`nicht_mehr_kandidat`, `platz_ausserhalb_puffer`, `anteil_angleichen`, `neu_unter_den_besten`}) und `rangliste` (erste 20 Kandidaten: `idx`, `platz`, `trend`, `umsatz_usd`, `gehalten`).
- Manifest `rotation`: Version, Standardvariante, Zahl der Varianten, Vorauswahl, Raster, Langhistorie, Status und Kennzahlen der Standardvariante, Hinweis, Kurzbeschreibung. Ältere Stände haben keinen Abschnitt; die App zeigt dann „noch nicht gerechnet“.

## Rechenvorschrift der App (bitgleich zum Server)

```
Perzentil P = 100 · (a/2 − 1) / (M − 1),  bei M = 1: P = 100      (a = doppelter Durchschnittsrang)
Score(w)    = (w/100) · G + (1 − w/100) · R;  w = 0 → R, w = 100 → G
```

`R` ist das Renditeperzentil, `G` das R²-Perzentil. Vergleichsfeld: nativ 0/100 → V (`a_rv`), alle anderen → U (`a_gu`, `a_ru`); Modus „gleiches Feld“ → alle elf auf U. Gerundet wird nur in der Anzeige. Der Datenvertragstest prüft die Gleichheit mit der Serverberechnung für alle Fenster und Gewichtungen.

## Rangmatrix je Aktie (`tr-series/1`, `ranks_b64`)

90 × Spaltenzahl Werte `uint16` little-endian, Base64. Zeile = Fenster 1–90, Spalten laut `rank_columns` = `v0, u0, u10, …, u100`, ab 1.1 zusätzlich `v0l` (Ranking 2), ab 1.4 `ul0 … ul100` (Gruppe B), also 24 Spalten. Die App greift über den Spaltennamen zu. 0 = kein Rang. Natives Vergleichsfeld: Spalte `v0` für 0/100, sonst `u<w>`; gleiches Vergleichsfeld: `u<w>` für alle elf.

## Codes

`manifest.codes` enthält die vollständigen Texte; die App zeigt nur diese.

| Status | Bedeutung | | Status | Bedeutung |
|---:|---|---|---:|---|
| 1 | ISIN ungültig | | 10 | Keine Startsitzung (7 Tage) |
| 2 | Kein Aktieninstrument | | 11 | Startkurs fehlt |
| 3 | Identität noch nicht geprüft | | 12 | Zu viele fehlende Sitzungen (ab 1.8.0: mehr als 20 %, eine immer erlaubt; bis 1.7.0: < 98 %) |
| 4 | Identität unklar | | 13 | Kapitalmaßnahme/Datenfehler prüfen (ab 1.7.0 auch gemeldeter Split im Fenster) |
| 5 | Börsenkalender fehlt | | 14 | Zu wenig belegtes Volumen (ab 1.7.0: Volumen fehlt an einer Beobachtung, Start/Ende ohne positives Volumen oder < 80 % positiv) |
| 6 | Daten fehlen | | 15 | Rendite veröffentlicht, zu wenig Tagesdaten für Gleichmäßigkeit |
| 7 | Markt am Stichtag geschlossen (ab 1.9.0 nur, wenn auch der letzte Schlusskurs veraltet ist) | | 16 | Rendite veröffentlicht, nicht steigend |
| 8 | Schlusskurs am Stichtag fehlt (ab 1.9.0 nur bei mehr als einer verpassten Sitzung) | | 17 | Rendite veröffentlicht, Gleichmäßigkeit nicht definiert |
| 9 | Zu kurze Historie | | 18 | Gleichmäßig steigend bewertbar |

Rendite veröffentlicht (Menge V): Status 15–18. Gleichmäßig steigend (Menge U): Status 18.

## Regeln für die App

- Alle Dateien einer Ansicht stammen aus genau einem Stand; die App verwirft Dateien, deren `snapshot_id` nicht zum aktiven Stand passt, und Fensterdaten, deren `h` nicht zur Auswahl passt.
- Daten werden nie aufgefüllt: fehlende Sitzungen bleiben Lücken, ein fehlender Wert bleibt „–“ mit Grund.
- Ein älterer Stand wird als „älterer Stand“ gekennzeichnet, DEMO-Daten in jeder Ansicht und jedem Export als DEMO.
