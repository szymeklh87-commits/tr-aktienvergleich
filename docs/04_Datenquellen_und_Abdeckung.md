# Datenquellen, belegte Abdeckung und Lizenzgrenzen

## Ehrlicher Stand vorab

In der Entwicklungsumgebung waren alle externen Datenquellen gesperrt (kein Netzzugang außer zu Paketquellen). **Keine der unten genannten echten Quellen wurde deshalb bisher tatsächlich abgerufen.** Die Adapter sind implementiert und mit gespeicherten Antwortformaten, synthetischen Daten und Fehlerfällen getestet. Die echte Machbarkeit belegt der Workflow **„Datenquellen prüfen“** in GitHub Actions (siehe 02_Einrichtung_und_Betrieb, Schritt 5); sein Bericht gehört in diese Datei, sobald er vorliegt.

## Quellen im Standardaufbau

| Zweck | Quelle | Zugang | Kosten | Vertrag/Lizenz | Status |
|---|---|---|---|---|---|
| Aktienuniversum | Trade Republic „Instrument Universe“ (PDF, Aktienabschnitt) – `https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf` | öffentlich, ohne Anmeldung | 0 € | öffentliches Dokument; nur Listung, keine Zusage individueller Handelbarkeit | Parser getestet mit erzeugten PDFs; echter Abruf offen |
| ISIN → Börsennotierung | OpenFIGI `/v3/mapping` | ohne Schlüssel 25 Anfragen/Minute (Dokumentation nennt 5 bzw. 10 ISINs je Anfrage, der Adapter halbiert bei Fehler 413 automatisch); mit kostenlosem Schlüssel 25 Anfragen je 6 Sekunden, 100 ISINs je Anfrage | 0 € | Nutzungsbedingungen von OpenFIGI | Adapter getestet; echter Abruf offen |
| ISIN → Börsennotierung (Ersatz) | Yahoo-Suche | inoffiziell | 0 € | kein Vertrag | wie oben |
| Tageskurse, Splits | Yahoo Finance Chart-Schnittstelle | inoffiziell, gedrosselt auf 2,5 Anfragen/Sekunde, Browser-Kennung über `curl_cffi` | 0 € | **kein Vertrag, keine Zusage**; Nutzung nur für den persönlichen Gebrauch; kann jederzeit drosseln oder sperren | Adapter getestet (Antwortformat, Splits, Pence, laufende Sitzung); echter Abruf offen |
| Börsenkalender | Python-Bibliothek `exchange_calendars` (Feiertage, verkürzte Handelstage, Schlusszeiten) | offline | 0 € | Apache-2.0 | Anbindung geschrieben; Tests laufen in GitHub Actions (in der Entwicklungsumgebung nicht installierbar) |

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
