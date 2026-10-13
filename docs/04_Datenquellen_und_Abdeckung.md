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

### Lücke bei Yahoo: Schlusskurse vom 12.10.2026

Yahoo liefert für Montag, 12.10.2026, bei allen geprüften Börsen in Europa und Asien eine Tageskerze **ohne Schlusskurs** – geprüft mit je einem großen Wert an 14 Börsen (SAP an Xetra und Frankfurt, LVMH, Nestlé, HSBC, Inditex, AB InBev, Novo Nordisk, Nokia, Equinor, ČEZ, Tallink, Tencent, Kweichow Moutai), über beide Yahoo-Server und beide Abfragearten. Stundenkerzen für diesen Tag sind vorhanden; US-Werte sind vollständig. Der Fehler liegt also beim Anbieter, nicht in der App.

Folgen nach den Regeln der Methodik: Für den Stichtag 12.10. veröffentlicht der Lauf keinen Stand (zu viele Börsen ohne Stichtagskurs). Solange der Kurs fehlt, zählt der 12.10. bei diesen Börsen als fehlende Sitzung – Zeiträume, in denen dadurch weniger als 98 % der Sitzungen vorhanden sind oder deren Anfangskurs fehlt, werden für diese Aktien nicht bewertet (in der App mit Grund sichtbar). Liefert Yahoo den Kurs nach, übernimmt ihn der tägliche Lauf automatisch: Er fragt bei jeder Notierung die letzten 10 Tage erneut ab und alle 30 Tage die ganze Historie.

## Quellen im Standardaufbau

| Zweck | Quelle | Zugang | Kosten | Vertrag/Lizenz | Status |
|---|---|---|---|---|---|
| Aktienuniversum | Trade Republic „Instrument Universe“ (PDF, Aktienabschnitt) – `https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf` | öffentlich, ohne Anmeldung | 0 € | öffentliches Dokument; nur Listung, keine Zusage individueller Handelbarkeit | echt geprüft 13.10.2026: 11.560 ISINs |
| ISIN → Börsennotierung | OpenFIGI `/v3/mapping` | ohne Schlüssel 25 Anfragen/Minute (Dokumentation nennt 5 bzw. 10 ISINs je Anfrage, der Adapter halbiert bei Fehler 413 automatisch); mit kostenlosem Schlüssel 25 Anfragen je 6 Sekunden, 100 ISINs je Anfrage | 0 € | Nutzungsbedingungen von OpenFIGI | echt geprüft 13.10.2026 |
| ISIN → Börsennotierung (Ersatz) | Yahoo-Suche | inoffiziell | 0 € | kein Vertrag | wie oben |
| Tageskurse, Splits | Yahoo Finance Chart-Schnittstelle | inoffiziell, gedrosselt auf 2,5 Anfragen/Sekunde, Browser-Kennung über `curl_cffi` | 0 € | **kein Vertrag, keine Zusage**; Nutzung nur für den persönlichen Gebrauch; kann jederzeit drosseln oder sperren | echt geprüft 13.10.2026; erster Lauf ohne Drosselung; Lücke am 12.10.2026 (oben) |
| Wechselkurse (nur Umsatzfilter, ab 1.1) | EZB-Referenzkurse, `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml` (90 Tage, rund 30 Währungen je EUR, an TARGET-Arbeitstagen gegen 16:00 MEZ) | öffentlich, ohne Anmeldung; ein Abruf je Lauf, Sicherung in der Datenbank | 0 € | frei nutzbar; laut EZB nur zur Information, keine Transaktionskurse – hier nur für den indikativen Umsatzfilter | Parser mit nachgebildeter Datei getestet; echter Abruf im Workflow „Datenquellen prüfen“ (Hinweis „EZB-Referenzkurse“). Ohne EZB-Kurs (z. B. TWD, CLP) keine Aufnahme in Ranking 2 |
| Zweiter Börsenplatz (nur Hinweise, ab 1.2) | Notierungen derselben ISIN aus OpenFIGI (wie bei der Zuordnung), Schlusskurse vom Kursanbieter (Yahoo) | wie oben; nur für die ersten 10 Plätze beider Rendite-Ranglisten, höchstens 600 Aktien je Lauf, Wahl des Platzes 45 Tage gespeichert | 0 € | wie oben | mit DEMO-Daten getestet; echter Abruf mit dem ersten veröffentlichten Datenstand |
| Börsenkalender | Python-Bibliothek `exchange_calendars` (Feiertage, verkürzte Handelstage, Schlusszeiten) | offline | 0 € | Apache-2.0 | in GitHub Actions geprüft (4 Tests bestanden) |

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
