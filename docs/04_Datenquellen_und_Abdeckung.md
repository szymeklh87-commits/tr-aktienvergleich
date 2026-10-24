# Datenquellen, belegte Abdeckung und Lizenzgrenzen

## Geprüfter Stand (13.10.2026)

In der Entwicklungsumgebung waren die externen Quellen gesperrt. Am 13.10.2026 hat der Workflow **„Datenquellen prüfen“** in GitHub Actions die echten Quellen abgerufen (Ergebnisse stehen als Hinweise in der Übersicht des Laufs):

| Quelle | Ergebnis |
|---|---|
| TR-Instrumentenliste (PDF, Stand 12.10.2026 06:06 UTC, 758 KB) | Aktienabschnitt erkannt: **11.560 ISINs**, 0 ungültige, 0 doppelte, 1 Fortsetzungszeile; Abschnitte „Stocks“ und „ETF“; Apple, SAP und Deutsche Telekom gefunden |
| OpenFIGI (ohne Schlüssel) | Apple und SAP je 8 unterstützte Notierungen (u. a. XNYS:AAPL, XETR:SAP.DE, XFRA:SAP.F, XSWX:SAP.SW) |
| Yahoo Finance | AAPL: 31 Tageskurse bis 12.10.2026; ISIN-Suche findet AAPL. **Lücke:** siehe unten |
| Börsenkalender `exchange_calendars` | Alle konfigurierten Kalender vorhanden; Feiertage und Schlusszeiten (inkl. Sommerzeit, verkürzter Handel) stimmen |
| EODHD | nicht geprüft (kein Schlüssel hinterlegt) |

Der erste echte Lauf am selben Tag hat die Liste übernommen und mit der Zuordnung begonnen (höchstens 4.000 ISINs je Lauf; der Rest folgt in den nächsten Läufen).

### Lücke bei Yahoo: Schlusskurse vom 12.10.2026 (am 13.10. abends nachgeliefert)

Yahoo liefert für Montag, 12.10.2026, bei allen geprüften Börsen in Europa und Asien eine Tageskerze **ohne Schlusskurs** – geprüft mit je einem großen Wert an 14 Börsen (SAP an Xetra und Frankfurt, LVMH, Nestlé, HSBC, Inditex, AB InBev, Novo Nordisk, Nokia, Equinor, ČEZ, Tallink, Tencent, Kweichow Moutai), über beide Yahoo-Server und beide Abfragearten. Stundenkerzen für diesen Tag sind vorhanden; US-Werte sind vollständig. Der Fehler liegt also beim Anbieter, nicht in der App.

**Nachgeliefert:** Der Lauf ab 21:07 Uhr am 13.10. fand die Schlusskurse vom 12.10. an allen Börsen (Xetra 433 von 439, London 695 von 713, Hongkong 734 von 735, USA 3.623 von 3.628) und veröffentlichte um 21:50 Uhr den ersten **vollständigen** Stand. Um 19:05 Uhr fehlten sie noch; wann genau Yahoo sie nachlieferte, ist nicht bekannt.

Folgen bis dahin nach den Regeln der Methodik: Für den Stichtag 12.10. veröffentlichte der planmäßige Lauf keinen Stand (zu viele Börsen ohne Stichtagskurs); um 20:37 Uhr wurde von Hand ein gekennzeichneter Teilstand veröffentlicht (USA, Australien, Neuseeland). Solange der Kurs fehlt, zählt der 12.10. bei diesen Börsen als fehlende Sitzung. Ab Methode 1.8.0 schließt eine einzelne fehlende Sitzung einen Zeitraum nicht mehr aus (höchstens 20 % fehlende Tage); nur der Zeitraum, dessen Anfangskurs genau am 12.10. liegen müsste, bleibt für diese Aktien ohne Rendite (in der App mit Grund sichtbar). Liefert Yahoo den Kurs nach, übernimmt ihn der tägliche Lauf automatisch: Er fragt bei jeder Notierung die letzten 10 Tage erneut ab und alle 30 Tage die ganze Historie.

### Wiederholt am 13.10.: Absicherung über die Kursmeldung (ab 1.5.4)

Am 14.10. um 06:41 Uhr fehlte der Schlusskurs vom 13.10. erneut bei Xetra, Frankfurt, Paris, Zürich, London, Madrid, Brüssel, Kopenhagen, Helsinki, Oslo und Prag – die Lücke ist also kein Einzelfall. Dieselbe Antwort enthält aber die **letzte Kursmeldung der Sitzung** (`regularMarketPrice` mit Zeitpunkt). Der Vergleich im Prüflauf um 06:46 Uhr:

| Vergleich | Ergebnis |
|---|---|
| Kursmeldung ↔ letzte Stundenkerze des Tages (13 europäische Werte ohne Schlusskurs) | **0,0 Basispunkte** Abweichung bei allen |
| Kursmeldung ↔ Tageskerze, wo sie vollständig ist (Apple, Coca-Cola, Royal Bank of Canada, Tallink, Tencent, Toyota, BHP) | **0,0 Basispunkte** Abweichung bei allen |
| Tageshoch, Tagestief und Umsatz in der Meldung | bei allen 20 Werten vorhanden |

Deshalb gilt ab 1.5.4: Ist die Sitzung laut Börsenkalender abgeschlossen (Schluss + 60 Minuten) und hat die Tageskerze keinen Schlusskurs, übernimmt der Lauf die Kursmeldung dieser Sitzung als Schlusskurs – gekennzeichnet in der Einzelansicht („Schlusskurs aus der letzten Kursmeldung …“) und unter ☰ → Datenstand & Betrieb (Anzahl). Kommt die Tageskerze später, ersetzt sie die Meldung beim nächsten Lauf ohne neue Kursrevision; eine Meldung überschreibt nie eine vorhandene Tageskerze.

### Kursziele, Kennzahlen, Nachrichten und Stimmung (ab 1.6)

Geprüft am 14.10.2026 mit dem Workflow „Datenquellen prüfen“ (nur Verfügbarkeit und Feldnamen im öffentlichen Protokoll, keine Werte):

| Quelle | Ergebnis | Nutzung in der App |
|---|---|---|
| Yahoo `quoteSummary` (Cookie + Crumb, nur im Speicher) | Kursziele bei **21 von 22** Testaktien weltweit (u. a. SAP, LVMH, Nestlé, HSBC, Toyota, Tencent, Kweichow Moutai, BHP, ČEZ, PKO; Tallink ohne Analysten); Serie von 50 Abrufen in 20 s ohne Drosselung; Kennzahlen (Bewertung, Wachstum, Finanzen, Termine, Branche) bei allen Märkten 28–34 von 34 Feldern | ein Abruf je Aktie, rotierend |
| Yahoo „Urteile der Häuser“ (`upgradeDowngradeHistory`) | Apple 62 Urteile in 180 Tagen (57 mit Kursziel), PDS Biotechnology 3; **europäische und asiatische Aktien: keine** | Einzelziele (US), Richtung der Analysten |
| Yahoo „insights“ (Trading Central, Argus) | Bewertung unter-/überbewertet und Ausblick nur bei US-Aktien | Bewertung (US) |
| Yahoo Nachrichtensuche | US-Kürzel: 18–19 Meldungen; Nicht-US-Kürzel (SAP.DE …): keine – deshalb Suche nach Firmennamen | Nachrichten der vorderen Kandidaten |
| Nasdaq (inoffiziell) | Konsens (tief/Ø/hoch) und Empfehlungsübersicht für US-Aktien | zweite Kurszielquelle (US) |
| Stocktwits | letzte 30 Beiträge je US-Kürzel, gut die Hälfte mit Stimmung markiert; ohne Schlüssel etwa 200 Abrufe je Stunde | Community (US, vordere Kandidaten) |
| onvista | keine Analystenfelder in der freien Schnittstelle | nicht genutzt |
| Trade Republic | Kursziel/Potenzial nur in der App nach Login | **nicht genutzt** (keine Zugangsdaten) |

Alle diese Schnittstellen sind inoffiziell bzw. ohne Vertrag und nur für die private Auswertung gedacht; die Daten werden wie die Kurse nur verschlüsselt veröffentlicht. Fällt eine Quelle aus, fehlt nur das betreffende Signal (grau) – Kurse und Ranglisten sind nicht betroffen.

### Kürzel ohne Kursdaten (ab 1.4.1)

Im Lauf vom 13.10.2026 lieferte Yahoo für 1.735 Notierungen gar keine Kurse – vor allem Toronto (960), Xetra (395), Stockholm (148) und Singapur (82). Das Kürzel aus der Identitätsquelle passte dort nicht zum Kursanbieter:

| Ursache | Beispiel | Abhilfe ab 1.4.1 |
|---|---|---|
| Sammelcodes der Identitätsquelle (OpenFIGI „CN“ für Kanada, „GR“ für Deutschland) wurden einer bestimmten Börse zugeordnet | „AAG.TO“ für eine Aktie der TSX Venture (richtig „AAG.V“), „046.DE“ für eine nur in Frankfurt gehandelte Aktie (richtig „046.F“) | Börsentabelle `boersen-v2`: CN und GR zeigen auf keine Börse mehr. Die betroffenen Identitäten (Toronto und Xetra ohne Kurse) werden einmal neu geprüft (Migration 0006) und erhalten ihre tatsächliche Börse |
| Aktiengattung ohne Trennzeichen | Stockholm „ADDTB.ST“ (richtig „ADDT-B.ST“) | Beim Abruf wird die Schreibweise mit Bindestrich versucht (Stockholm, Kopenhagen, Helsinki, Oslo, Island) |
| Börsenkürzel weicht vom Kürzel des Kursanbieters ab | Singapur „DBS.SI“ (Yahoo „D05.SI“) | Suche nach der ISIN beim Kursanbieter |

Regeln für ein anderes Kürzel: nur dieselbe Börse (eine andere Börse wählt allein die Identitätsprüfung nach Länderpräferenz), nur Aktieninstrumente, höchstens drei Kandidaten je Notierung. Jeder Kandidat muss die Plausibilitätsprüfung bestehen: Instrumenttyp, Zeitzone und Börsencode beim Kursanbieter, dieselbe Währung (Pence zählen zum Pfund) und ein Name, der zum TR-Namen oder zum Namen der Identitätsquelle passt (Ähnlichkeit mindestens 0,25 statt sonst 0,15 – ein falsch übernommenes Kürzel würde fremde Kurse einmischen). Ein gefundenes Kürzel ersetzt das alte, die Kurse werden als neue Datenrevision vollständig geladen und nie mit älteren Kursen gemischt; die nächste Identitätsprüfung behält die Korrektur bei. Je Lauf höchstens 300 Notierungen und 15 Minuten; erfolglose Suchen frühestens nach 30 Tagen erneut. Jede Übernahme steht im Protokoll des Laufs („Kürzel ADDTB.ST → ADDT-B.ST“), die Zählung im Kurzbericht („Andere Kürzel …: geprüft, gefunden“).

Nicht behebbar sind Notierungen, für die Yahoo unter keinem Kürzel Kurse führt (häufig US-Freiverkehr ohne Kursversorgung und Londoner Auslandswerte im International Order Book). Sie bleiben mit dem Grund „keine verwertbaren Kurse“ sichtbar.

## Quellen im Standardaufbau

| Zweck | Quelle | Zugang | Kosten | Vertrag/Lizenz | Status |
|---|---|---|---|---|---|
| Aktienuniversum | Trade Republic „Instrument Universe“ (PDF, Aktienabschnitt) – `https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf` | öffentlich, ohne Anmeldung | 0 € | öffentliches Dokument; nur Listung, keine Zusage individueller Handelbarkeit | echt geprüft 13.10.2026: 11.560 ISINs |
| ISIN → Börsennotierung | OpenFIGI `/v3/mapping` | ohne Schlüssel 25 Anfragen/Minute (Dokumentation nennt 5 bzw. 10 ISINs je Anfrage, der Adapter halbiert bei Fehler 413 automatisch); mit kostenlosem Schlüssel 25 Anfragen je 6 Sekunden, 100 ISINs je Anfrage | 0 € | Nutzungsbedingungen von OpenFIGI | echt geprüft 13.10.2026 |
| ISIN → Börsennotierung (Ersatz) | Yahoo-Suche | inoffiziell | 0 € | kein Vertrag | wie oben |
| Tageskurse, Splits | Yahoo Finance Chart-Schnittstelle | inoffiziell; ab 1.17 4 Abrufe gleichzeitig über die Hosts query2 und query1, je Host höchstens 4 je Sekunde (gemessen 8,00 je Sekunde, ohne Drosselung (0 × HTTP 429)); bei einer Drosselung automatisch nacheinander mit 2,5 je Sekunde wie bis 1.16; Browser-Kennung über `curl_cffi` | 0 € | **kein Vertrag, keine Zusage**; Nutzung nur für den persönlichen Gebrauch; kann jederzeit drosseln oder sperren | echt geprüft 13.10.2026; erster Lauf ohne Drosselung; Lücke am 12.10.2026 (oben) |
| Wechselkurse (nur Umsatzfilter, ab 1.1) | EZB-Referenzkurse, `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml` (90 Tage, rund 30 Währungen je EUR, an TARGET-Arbeitstagen gegen 16:00 MEZ) | öffentlich, ohne Anmeldung; ein Abruf je Lauf, Sicherung in der Datenbank | 0 € | frei nutzbar; laut EZB nur zur Information, keine Transaktionskurse – hier nur für den indikativen Umsatzfilter | Parser mit nachgebildeter Datei getestet; echter Abruf im Workflow „Datenquellen prüfen“ (Hinweis „EZB-Referenzkurse“). Ohne EZB-Kurs (z. B. TWD, CLP) keine Aufnahme in Ranking 2 |
| Wechselkurse für die Umschichtungs-Regel (ab 1.3) | EZB, ganze Reihe seit 1999 als ZIP mit einer CSV-Datei, `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip` (gut 0,5 MB) | öffentlich; einmal laden, dann nur noch die 90-Tage-Datei; gespeichert wird der Rückblickzeitraum (3 Jahre + 4 Monate) | 0 € | wie oben; hier für die Euro-Bewertung des gedachten Regeldepots | Parser mit nachgebildeter Datei getestet; echter Abruf mit dem ersten Lauf von 1.3. Fällt er aus, wird der Rückblick kürzer (Warnung im Kurzbericht) |
| Wochenwerte für die Umschichtungs-Regel (ab 1.3) | Yahoo Finance Chart-Schnittstelle, Tageskurse bis 3 Jahre je Aktie, verdichtet zu Wochenwerten | wie Tageskurse; einmal je Aktie mit Ø Tagesumsatz ab 2 Mio. USD (beim ersten Lauf einige Tausend Abrufe, danach nur neue Aktien und Splits) | 0 € | wie Tageskurse | mit DEMO-Daten getestet; echter Abruf mit dem ersten Lauf von 1.3 |
| Zweiter Börsenplatz (nur Hinweise, ab 1.2) | Notierungen derselben ISIN aus OpenFIGI (wie bei der Zuordnung), Schlusskurse vom Kursanbieter (Yahoo) | wie oben; nur für die ersten 10 Plätze beider Rendite-Ranglisten, höchstens 600 Aktien je Lauf, Wahl des Platzes 45 Tage gespeichert | 0 € | wie oben | mit DEMO-Daten getestet; echter Abruf mit dem ersten veröffentlichten Datenstand |
| Börsenkalender | Python-Bibliothek `exchange_calendars` (Feiertage, verkürzte Handelstage, Schlusszeiten) | offline | 0 € | Apache-2.0 | in GitHub Actions geprüft (4 Tests bestanden) |

## Sammelabruf statt Einzelabruf? Geprüft am 24.10.2026 (ab 1.17)

Der tägliche Lauf holt die Tageskerzen jeder Notierung einzeln über die Chart-Schnittstelle. Yahoo bietet daneben zwei Sammelabfragen: „spark“ (bis 20 Werte je Abruf, Tageskurse eines Monats) und „quote“ (bis 150 Werte je Abruf, letzte Kursmeldung mit Eröffnung, Hoch, Tief und Umsatz). Rechnerisch wären damit alle rund 11.000 Notierungen in etwa vier Minuten abgerufen. Vor einer Umstellung wurde mit echten Daten verglichen (Workflow „Kursabruf vergleichen“, nur lesend, Stichtag 23.10.2026, 11.145 Notierungen):

| Prüfpunkt | Ergebnis |
|---|---|
| Dauer | spark: 558 Abrufe in 140 s; quote: 75 Abrufe in 10 s; keine Drosselung |
| Schlusskurse spark gegen gespeicherte Kurse | 212.619 Tage bis auf 1e-6 gleich (41.122 bitgleich, Rest Rundung der Sammelabfrage), 1.221 Tage abweichend (davon 23 um mehr als 20 %) |
| Fehlende Tage in spark | 20.587 Tage, die der Chart enthält: 11.146 Tage ohne Umsatz, 7.751 mit Kurs wie am Vortag, 1.690 sonstige – spark lässt Tage ohne Handel weg |
| Umsatz, Eröffnung, Hoch, Tief in spark | **nicht vorhanden** – alle geprüften Varianten (drei Adressen, fünf Feldauswahlen) liefern nur Schlusskurse und Zeitstempel |
| Umsatz aus „quote“ gegen die Tageskerze (Stichprobe: 406 Notierungen mit Meldung zum selben Tag) | bitgleich 176, bis 1 % 161, bis 20 % 39, **über 20 % 30** – deutlich abweichend vor allem in New York, Frankfurt, Stockholm und Bangkok |
| Chart frisch gegen gespeichert (Stichprobe) | ältere Tage 13.679 von 13.679 bitgleich; Umsatz des letzten Tages bei 32 von 426 nachträglich geändert (der tägliche Lauf holt deshalb die letzten 10 Tage jedes Mal neu) |

**Entscheidung:** Der Sammelabruf ist nicht gleichwertig – er brächte andere Umsätze (Ø Tagesumsatz, Gruppe B, Volumen-Signale) und ließe Tage ohne Handel weg. Er bleibt deshalb ausgeschaltet (`abruf.sammelabruf: false`, Code und Tests vorhanden). Schneller wird der Kursabruf stattdessen mit **denselben Chart-Abrufen, gleichzeitig über zwei Hosts** (`abruf.chart_gleichzeitig: 4`): gemessen am 24.10.2026, 12:44–13:11 Uhr: 10.845 Notierungen gleichzeitig in 22,6 Minuten (8,00 je Sekunde, ohne Drosselung (0 × HTTP 429)), hochgerechnet auf alle 11.145: **23,2 Minuten** statt hochgerechnet 74,0 Minuten nacheinander; Dieselben Daten: Beide Hosts lieferten in einer Stichprobe von 200 Notierungen Feld für Feld bitgleiche Kurse und Umsätze; gegen den gespeicherten Stand (rund eine Stunde älter) waren von den älteren Tagen 95.626 von 95.628 Schlusskursen und 95.627 von 95.628 Umsätzen bitgleich, vom letzten Tag 11.001 von 11.002 Schlusskursen; den Umsatz des letzten Tages hatte der Anbieter bei 138 Notierungen inzwischen geändert (deshalb holt der Lauf die letzten zehn Tage jedes Mal neu). (07_Testbericht). Die vier Minuten aus dem Rechercheauftrag hätten rund 46 Abrufe je Sekunde gebraucht – das wäre nur mit dem Sammelabruf möglich gewesen.

## Optionaler vertraglicher Kursanbieter

| Anbieter | Plan | Preis | Umfang | Hinweis |
|---|---|---|---|---|
| EODHD | „EOD Historical All-World“ (Historian) | 19,99 USD/Monat oder 199 USD/Jahr | Tagesdaten weltweit, 100.000 Abrufe/Tag, 1.000/Minute, 30+ Jahre Historie | Adapter vorhanden (`providers/eodhd.py`), aktivierbar über `anbieter.kurse: eodhd` und Secret `EODHD_API_KEY`. **Nicht ohne deine Freigabe abschließen.** Kostenloser Plan: 20 Abrufe/Tag – für ein ganzes Universum ungeeignet. |

Live- oder Intradaykurse sind nicht eingerichtet. Die App kennzeichnet das ausdrücklich („Heute / Kurs aktuell: nicht eingerichtet“) und zeigt nur Tagesschlusskurse.

## Unterstützte Referenzbörsen

Jede ISIN wird genau einer dieser Börsen zugeordnet (Länderpräferenz nach ISIN-Präfix, dann Standardreihenfolge; Details in `config/boersen.yaml`). Kalender mit „Ersatz“ nutzen den Kalender einer Schwesterbörse mit denselben Feiertagen – die App zeigt dazu einen Hinweis.

| Schlüssel | Börse | Kalender | Einheit | Yahoo-Endung |
|---|---|---|---|---|
| US, XNYS, XNAS, XASE, ARCX, BATS, OTC | USA (NYSE, Nasdaq, NYSE American, Arca, Cboe BZX, OTC) | XNYS | USD | – |
| XETR / XFRA | Xetra / Börse Frankfurt | XETR / XFRA | EUR | .DE / .F |
| XLON | London Stock Exchange | XLON | **GBp (Pence)** | .L |
| XHKG | Hongkong | XHKG | HKD | .HK |
| XTKS | Tokio | XTKS | JPY | .T |
| XASX | ASX | XASX | AUD | .AX |
| XTSE, XTSX, XCNQ | Toronto, TSX Venture, CSE | XTSE (Venture/CSE als Ersatz) | CAD | .TO, .V, .CN |
| XSWX | SIX | XSWX | CHF | .SW |
| XPAR, XAMS, XBRU, XLIS, XDUB | Euronext Paris, Amsterdam, Brüssel, Lissabon, Dublin | jeweils eigener | EUR | .PA, .AS, .BR, .LS, .IR |
| XMIL, XMAD, XWBO | Mailand, Madrid, Wien | jeweils eigener | EUR | .MI, .MC, .VI |
| XSTO, XCSE, XHEL, XOSL, XICE, XTAL | Nasdaq Nordic, Oslo, Tallinn | jeweils eigener | SEK, DKK, EUR, NOK, ISK, EUR | .ST, .CO, .HE, .OL, .IC, .TL |
| XWAR, XPRA, XBUD, ASEX, XIST | Warschau, Prag, Budapest, Athen, Istanbul | jeweils eigener | PLN, CZK, HUF, EUR, TRY | .WA, .PR, .BD, .AT, .IS |
| XTAE | Tel Aviv | XTAE | **ILA (Agorot)** | .TA |
| XJSE | Johannesburg | XJSE | **ZAc (Cent)** | .JO |
| XSES, XKRX, XKOS, XTAI, XNSE | Singapur, Korea (KOSPI, KOSDAQ), Taiwan, Indien (NSE) | XSES, XKRX, XKRX (Ersatz), XTAI, XBOM (Ersatz) | SGD, KRW, TWD, INR | .SI, .KS, .KQ, .TW, .NS |
| XNZE, XMEX, BVMF, XSGO | Neuseeland, Mexiko, São Paulo, Santiago | jeweils eigener | NZD, MXN, BRL, CLP | .NZ, .MX, .SA, .SN |
| XSHG, XSHE, XKLS, XBKK, XIDX | Shanghai, Shenzhen, Malaysia, Thailand, Indonesien | XSHG (Shenzhen als Ersatz), XKLS, XBKK, XIDX | CNY, MYR, THB, IDR | .SS, .SZ, .KL, .BK, .JK |

Untereinheiten (Pence, Agorot, Cent) werden als solche angezeigt; die Kursrendite ist davon unabhängig. Ein Einheitenwechsel im Datenstrom wird als Sprung erkannt und zurückgehalten.

## Wie Abdeckung sichtbar wird

Jeder veröffentlichte Stand enthält eine Abdeckungsbilanz (App: ☰ → Alle Aktien & Abdeckung, ☰ → Datenstand & Betrieb):

- ISINs im Aktienabschnitt der TR-Liste, eindeutig zugeordnete Instrumente, geladene Historien, Instrumente mit mindestens einem Renditezeitraum,
- je Zeitraum: Aktien mit veröffentlichter Rendite (V) und gleichmäßig gestiegene Aktien (U),
- genau ein Hauptstatus je Aktie – die Summe ergibt immer das gesamte Universum (geprüft vor jeder Veröffentlichung),
- zusätzliche Hinweise (Mehrfachnennung): Pence-Kurse, Ersatzkalender, Splits, wenig Umsatz, OTC, Kursbewegung ohne Umsatz usw.

„Vollständig“ heißt immer: vollständig für genau das benannte Universum und die erfüllten Prüfungen – nicht „alle Aktien der Welt“ und nicht „alle Kurse angefragt“.

## Lizenz- und Nutzungsgrenzen

- Kursdaten werden ausschließlich verschlüsselt veröffentlicht und sind nur mit der Passphrase lesbar. Exporte (CSV, PNG) sind für den persönlichen Gebrauch gedacht.
- Yahoo-Daten sind ohne Vertrag; für eine Weitergabe an Dritte oder kommerzielle Nutzung wäre ein lizenzierter Anbieter nötig.
- Die App gibt sich nicht als Produkt von Trade Republic aus, verwendet kein TR-Logo und fragt nie nach TR-Zugangsdaten.
