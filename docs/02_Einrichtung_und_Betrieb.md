# Einrichtung und Betrieb

Diese Anleitung bringt das Projekt einmalig auf GitHub. Danach läuft alles selbstständig: Jeden Morgen rechnet GitHub Actions die Ranglisten neu und veröffentlicht die App auf GitHub Pages. Es entstehen im Standardaufbau **keine laufenden Kosten** (Begründung unten).

## Überblick

| Baustein | Wofür | Kosten |
|---|---|---|
| GitHub-Konto (kostenlos) + öffentliches Repository | Code, Zeitplan, Speicher des verschlüsselten Zustands | 0 € |
| GitHub Actions | täglicher Lauf 07:00 Europe/Berlin, Wiederholungen | 0 € (Standard-Runner in öffentlichen Repositories) |
| GitHub Pages | Adresse der App für das Handy | 0 € (öffentliche Repositories, GitHub Free) |
| Yahoo Finance (inoffiziell) | Tageskurse | 0 €, ohne Vertrag, ohne Zusage |
| OpenFIGI | ISIN → Börsennotierung | 0 €, kostenloser API-Schlüssel optional |
| EODHD (optional) | vertraglich geregelte Kurse statt Yahoo | 19,99 USD/Monat (Plan „EOD Historical All-World“) – **nur nach deiner Freigabe** |

Warum öffentlich? GitHub Pages ist im kostenlosen Tarif nur für öffentliche Repositories verfügbar. Deshalb sind alle veröffentlichten Kursdaten, die Ranglisten und die Sicherung mit deiner Passphrase verschlüsselt (AES-256-GCM). Öffentlich lesbar sind nur der Programmcode, die leere App-Hülle und drei Betriebsdateien ohne Kurse (`status.json` mit Laufstatus, `snapshots/index.json` mit Datum und Anzahl je Datenstand, `crypto.json` mit den nicht geheimen Schlüsselparametern).

## Schritt 1 – Repository anlegen

1. Bei <https://github.com> kostenlos registrieren (falls noch kein Konto).
2. Oben rechts **+** → **New repository**.
3. Name: `tr-aktienvergleich`, Sichtbarkeit **Public**, ohne README/Lizenz anlegen → **Create repository**.

## Schritt 2 – Projektdateien hochladen

Variante A (ohne Programmierkenntnisse, am PC): Das ZIP entpacken. Im neuen Repository **uploading an existing file** wählen und den **Inhalt** des entpackten Ordners (inklusive des Ordners `.github`) in das Browserfenster ziehen → **Commit changes**. Wichtig: Der Ordner `.github/workflows` muss mit hochgeladen werden; in manchen Dateiansichten ist er versteckt.

Variante B (mit Git):

```bash
git remote add origin https://github.com/<dein-name>/tr-aktienvergleich.git
git push -u origin main
```

Variante C: Claude kann das Hochladen übernehmen, sobald der Repository-Zugang in dieser Unterhaltung freigegeben ist.

## Schritt 3 – Passphrase und optionale Schlüssel hinterlegen

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Pflicht | Inhalt |
|---|---|---|
| `DATA_PASSPHRASE` | ja | Lange, zufällige Passphrase (zum Beispiel fünf bis sechs zufällige Wörter). Im Passwortmanager notieren – sie wird auf dem Handy einmal eingegeben. Ohne sie bricht der Lauf bewusst ab, damit keine Kursdaten unverschlüsselt öffentlich werden. |
| `OPENFIGI_API_KEY` | empfohlen | Kostenloser Schlüssel von <https://www.openfigi.com/api>. Beschleunigt die erste ISIN-Zuordnung stark (25 Anfragen je 6 Sekunden mit je 100 ISINs statt 25 Anfragen je Minute). |
| `EODHD_API_KEY` | nein | Nur, wenn du später auf den kostenpflichtigen Anbieter EODHD umstellst (siehe 05_Konfiguration). |

Die Passphrase lässt sich später nicht ändern, ohne den gespeicherten Zustand neu aufzubauen (Lauf mit „zustand_neu_aufbauen“).

## Schritt 4 – GitHub Pages einschalten

**Settings** → **Pages** → bei *Build and deployment* unter *Source* **GitHub Actions** wählen. Mehr ist nicht nötig; die Umgebung `github-pages` legt GitHub selbst an.

Falls Läufe mit „Resource not accessible by integration“ scheitern: **Settings** → **Actions** → **General** → *Workflow permissions* → **Read and write permissions** → Save.

## Schritt 5 – Datenquellen prüfen (einmalig, ca. 2 Minuten)

**Actions** → links **Datenquellen prüfen** → **Run workflow**. Der Lauf ruft die TR-Instrumentenliste, OpenFIGI und Yahoo mit wenigen Testabfragen ab und prüft die Börsenkalender. Der Bericht `datenquellen-bericht.json` liegt danach unter *Artifacts* des Laufs (Anzahl ISINs im Aktienabschnitt, erkannte Abschnitte, Beispielabrufe). Schlägt ein Teil fehl, steht der Grund im Protokoll – siehe 06_Fehlerbehebung.

## Schritt 6 – Erster vollständiger Lauf

**Actions** → **Täglicher Lauf** → **Run workflow** (ohne Häkchen). Der erste Lauf ist der aufwendigste:

- Zuordnung aller ISINs zu einer Referenzbörse (OpenFIGI, ohne Schlüssel langsam),
- 400 Kalendertage Kurshistorie für jede Notierung (Yahoo ab 1.17 bis zu 8 Abrufe je Sekunde über zwei Hosts, bei Drosselung 2,5),
- danach Berechnung und Veröffentlichung.

Bei rund 10.000 Aktien dauert das geschätzt mehrere Stunden (noch nicht gemessen: die Datenquellen waren in der Entwicklungsumgebung gesperrt). Der Lauf speichert Zwischenstände (Checkpoints) und wird von den geplanten Läufen fortgesetzt; ein abgebrochener Lauf verliert keine bereits geladenen Kurse. Den Fortschritt zeigt das Protokoll des Laufs, später auch die App unter ☰ → Datenstand & Betrieb.

Wenn der Lauf grün ist, steht die Adresse der App unter **Settings** → **Pages** (Form `https://<dein-name>.github.io/tr-aktienvergleich/`).

## Schritt 7 – Handy

Adresse auf dem S25+ öffnen, installieren und Passphrase eingeben – siehe 01_Kurzanleitung_Handy.

## Schritt 8 – Zugang für „Jetzt aktualisieren“ (optional, ab 1.21)

Damit die App Kurse selbst anfordern und den Fortschritt zeigen kann, braucht sie einen eigenen, eng begrenzten Zugang.
Ohne ihn funktioniert alles wie bisher (Läufe startest du dann auf GitHub mit „Run workflow“).

1. In der App ☰ → **Einstellungen** → **Zugang für „Jetzt aktualisieren“** → **Neues Token auf GitHub anlegen**. GitHub
   öffnet ein vorausgefülltes Formular („Fine-grained token“).
2. **Repository access:** „Only select repositories“ → nur `tr-aktienvergleich`.
3. **Permissions → Repository permissions:** nur **Actions: Read and write** (Metadata „Read-only“ setzt GitHub selbst).
   Nichts anderes – vor allem nicht Contents, Workflows, Secrets oder Administration.
4. **Expiration:** 90 Tage. **Generate token** → Token kopieren.
5. In der App einfügen → **Zugang prüfen und speichern**. Bei einem Datenschlüssel aus einer älteren Version fragt die App
   einmal nach der Passphrase (damit der Zugang verschlüsselt gespeichert werden kann).

Was der Zugang darf: Läufe dieses Repositorys starten, abbrechen, wiederholen, ihren Fortschritt und ihre Protokolle lesen
oder löschen, Workflows ein- und ausschalten. Was er nicht darf: Code oder Workflow-Dateien ändern, Secrets lesen, den
Datenstand im Release ändern, Einstellungen ändern. **Widerrufen:** GitHub → Settings → Developer settings → Personal access
tokens → Fine-grained tokens → Token → Delete; in der App „Zugang entfernen“. Einzelheiten, Aufbau, Kosten und Messungen:
14_Aktualisieren.

## Datenqualität der Kurse prüfen (ab 1.19.0, bei Bedarf)

**Actions** → **Datenqualität der Kurse prüfen** → **Run workflow**. Seit 1.19.0 getrennt von „App mit echten Daten
prüfen“ (Auftrag vom 25.10.2026, 14:23 Uhr: „Trenne App-Fehler und Datenqualitätsbefunde in GitHub nachvollziehbar“): Ein
roter Lauf hier heißt „Kurse nicht vollständig bestätigt bzw. Ursachen nicht belegt“ – nicht „App defekt“. Die Prüfungen
sind unverändert streng (rot bei unvollständiger Abdeckung oder ungeklärten Abweichungen, kein `continue-on-error`). Alle
Jobs entschlüsseln den Stand nur im Prüfschritt mit `DATA_PASSPHRASE`; im öffentlichen Protokoll stehen nur Zählwerte,
Codes, Börsencodes und Buchstaben statt Namen, Kürzeln oder ISINs; hochgeladen wird nichts. Zusätze beim Start:

| Zusatz (Voreinstellung) | Job | Was er prüft |
|---|---|---|
| „Ursachen“ (an) und „Stand“ | „Ursachen der Kursunterschiede (…)“, „Ursachen – gemeinsame Wirkung aller Gruppen“ | wie bis 1.18.2 unter „App mit echten Daten prüfen“ (Abschnitt unten, Zusatz „Ursachen“); dazu ab 1.19.0 an jedem abweichenden Tag die **heutige Lieferung von Yahoo** – gleich dem Stand (Unterschied zwischen den Quellen) oder gleich dem Vergleichskurs (Stand veraltet) |
| „Kurse“ (aus) | „Kurse unabhängig gegenprüfen (Nasdaq)“ | wie bis 1.18.2 (Abschnitt unten, Zusatz „Kurse“) |
| „Auffällige“ (an) | „Börsenplatz-Abgleich – auffällige Aktien einzeln“ (`tests/live/boersenplatz_auffaellige.py`) | jede im Börsenplatz-Abgleich auffällige Aktie einzeln: Vergleichsplatz, Abweichung gegen Schwelle, Fundstelle, dazu CNBC als dritte Quelle für Start- und Endkurs der Referenz (nur mit passendem Namen, passender Börse und Währung); rot, solange nicht jede bestätigt ist |
| „Lücken“ (an) | „Datenlücken einzeln untersuchen“ (`tests/live/datenluecken.py`) | Hauptstatus der Abdeckungsbilanz, Gründe einer unklaren Identität, Aktien ohne Kursdaten je Börse und Schreibweise des Kürzels, fehlende Stichtagskurse, Ø-Umsatz-Status und fehlende Wechselkurse, Nichtaktien je Typ; heutige Nachfrage bei Yahoo (gleiches Kürzel, Endung „.IL“, Suche nach der ISIN). Ändert nichts; mögliche Korrekturen erscheinen als Warnung „vielleicht schließbar“ |
| „Spitzenreiter“ (an) | „Spitzenreiter gegen die Kursarchive der Börsen“ (`tests/live/spitzenreiter_boersen.py`) | Aktien an Warschau, Toronto und TSX Venture mit Platz unter den ersten 10 gegen die Quellen der Börsenbetreiber: Notierungsarchiv der GPW (volle Tabelle mit ISIN), Tagesstatistik der NewConnect, Kurshistorie bei TMX Money – dieselben strengen Prüfungen wie im Job „welt“, abweichende Tage neu gerechnet (Platz 1 vorher/nachher, Auslöser je Rangliste), Aktien mit nur abweichendem Kursniveau als eigene, ausdrücklich nicht abgesicherte Variante; dazu die Erreichbarkeit von Quellen für TWD und CLP. Rot, solange ein Spitzenreiter ungeprüft oder ein Kurs nicht bestätigt ist |

Die Ergebnisse stehen als Hinweise in der Laufübersicht. Die App rechnet unverändert mit den Kursen des Stands; was die
Prüfung für den Stand vom 23.10.2026 ergab, zeigt sie unter ☰ → Datenstand & Betrieb → „Unabhängige Kursprüfung“ und in
den betroffenen Ranglisten (07_Testbericht, Abschnitt 8g).

## App mit echten Daten prüfen (ab 1.5.2, bei Bedarf)

**Actions** → **App mit echten Daten prüfen** → **Run workflow**. Ein Chromium im Format des Galaxy S25+ (384 × 832, Touch) öffnet die veröffentlichte Website, entsperrt sie mit dem Secret `DATA_PASSPHRASE`, ruft alle 17 Ansichten und die Einzelansicht der ersten Aktie auf und öffnet die App ein zweites Mal (gespeicherter Schlüssel, Service Worker). Nach etwa 2 Minuten steht in der Laufübersicht „App mit echten Daten: alles in Ordnung“ oder die gefundenen Fehler, je Ansicht mit Ladezeit, dazu Fehler der Browser-Konsole und fehlgeschlagene Abrufe. Das Protokoll enthält nur Version, Datum des Kursstands, Zählungen und Zeiten – keine Kurse, Namen oder Ranglisten (das Protokoll eines öffentlichen Repositorys ist öffentlich). Der Workflow hat keinen Zeitplan und lädt keine Dateien hoch.

**Rechnung unabhängig nachprüfen (ab 1.13, zweiter Job im selben Workflow):** `tests/live/nachrechnen.py` lädt den neuesten Stand mit Schlusskursen und den Zwischenstand aus dem Release „datenstand“, entschlüsselt sie mit `DATA_PASSPHRASE` und rechnet alles nach, was die App anzeigt – ohne den Rechenkern, mit eigener, kurzer Rechnung nach der Methodik: Startsitzung, Zahl der Kurse und Sitzungen, Start- und Endkurs, Kursrendite (bitgleich), R², Zulassung und Trend-Status je Aktie und Zeitraum 1–90; alle Ranglisten der Gruppen A und B (Perzentile, Score, Reihenfolge, Gleichstände); Ø Tagesumsatz mit den EZB-Kursen und die Aufnahme in Gruppe B; Häufigkeit (Platz 1, Top 3, Top 10); Prüfsummen aller Dateien; im Zwischenstand die Aktien mit dem Schlusskurs davor gegen den Stand mit Schlusskursen. Mit `--vergleich tests/live/vergleich/chatgpt_2026-10-13.json` vergleicht er zusätzlich mit deinem ChatGPT-Bericht vom 13.10.: Anzahl der Aktien je Rangliste, erste 5/10 Plätze, Musterdepots „Sieger“ und „Top 10“ (Bericht 1–30, A und B) – über gesalzene SHA-256-Prüfwerte, die Vergleichsdatei enthält keine Namen oder ISINs. Ergebnis als Hinweise in der Laufübersicht: „Nachrechnung … 0 Abweichungen“ bzw. jede Abweichung mit Anzahl und Zeitraum. Lokal gegen einen Website-Ordner: `DATA_PASSPHRASE=… python tests/live/nachrechnen.py --quelle site --site <Ordner>`.

**Zusätze zum Ankreuzen beim Start (voreingestellt aus; ab 1.18 „Android“ und „Kurse“, ab 1.18.1 „Weitere Browser“,
„Originalstände“ und „Ursachen“; seit 1.19.0 sind „Kurse“ und „Ursachen“ in den Workflow „Datenqualität der Kurse
prüfen“ umgezogen – oben –, hier bleiben „Android“, „Weitere Browser“ und „Originalstände“):**

- **„Android“** – Job „Android-Emulator mit echten Daten“: dieselbe Website in Chrome für Android im Emulator (Android 15,
  Format des S25+), mit der Passphrase entsperrt, alle 24 Ansichten, danach Neustart ohne Netz (`tests/live/android_echte_daten.py`,
  etwa 10 Minuten). Emulator, kein Gerät.
- **„Kurse“** – Job „Kurse unabhängig gegenprüfen (Nasdaq)“: für eine Auswahl von US-Aktien (alle aus den ersten 10 einer
  Rangliste und 150 zufällige) die Schlusskurse nachträglich bei Nasdaq abgerufen und mit dem Stand verglichen – je
  Börsentag, fehlende Tage und die Renditen 1–90 Tage (`tests/live/kurse_gegenpruefen.py`, etwa 5 Minuten). Ein zweiter
  Anbieter neben Yahoo; nachträglich beschaffte Kurse belegen nicht, welche Kurse ein anderes Modell damals hatte.
  Jede Abweichung wird per **Gegenprobe bei Yahoo** (Quelle der App, eigene Auswertung) eingeordnet: *wie Yahoo* (die App
  hat den Kurs ihrer Quelle – ob es der Börsenkurs ist, zeigt das nicht), *vorläufig aus der Kursmeldung* (in der
  Kursreihe markiert), *ohne Yahoo-Kurs* oder *unerklärt*. Urteil in der zweiten Zeile: **bestanden** (alles wie bei
  Nasdaq – nur dann ist der Job grün), **nicht bestätigt** (Abweichungen, die nur „wie Yahoo“ sind; ab dem 24.10.2026,
  22 Uhr – bis dahin hieß das „bestanden mit Unterschieden zwischen den Anbietern“ und der Job war grün) oder **nicht
  bestanden** (eine Abweichung auch gegen Yahoo unerklärt oder eine Quelle nur teilweise erreichbar).
- **„Ursachen“** – Jobs „Ursachen der Kursunterschiede (…)“ (`tests/live/kurse_ursachen.py`, zusammen 40 bis 60 Minuten;
  der Abruf hat je Job ein Zeitbudget von 35 Minuten, danach endet das Skript mit „unvollständig“ statt ohne Ergebnis):
  vergleicht die Kurse des Stands nachträglich mit frei zugänglichen Quellen – Nasdaq-Historie, offizieller Schlusskurs der
  Nasdaq (NOCP) für alle Nasdaq-notierten Aktien an allen Tagen, Zusatzquellen und CNBC – und rechnet alle Ranglisten mit
  den Vergleichskursen neu (Platz 1, erste 10, Reihenfolge). Nachträglich beschaffte Kurse sind keine Originaldaten.
  **Absicherung jeder Zuordnung** (seit dem 25.10.2026, 09:20 Uhr, `tests/live/kurse_absicherung.py`): verglichen wird nur,
  wenn jede Prüfung bestanden ist – Aktie und Gattung über die ISIN des Stands (OpenFIGI: das abgefragte Kürzel gehört zur
  ISIN, in der Schreibweise der App oder einer ihrer dokumentierten anderen Schreibweisen wie „ADDT-B.ST“ für „ADDTB“), Name und
  Art laut Quelle (Wertpapierliste von Nasdaq Trader bzw. Kursmeldung von CNBC; kein Fonds, Optionsschein,
  Testwert – der Grund wird gezählt), Börse der Quelle = Börse der Kurse des Stands, Währung angegeben und gleich (Untereinheiten wie GBp umgerechnet),
  Handelstag ohne Versatz, Bereinigung wie im Stand (ein Faktor nur mit gemeldetem Split), Kursniveau, mindestens 10 Tage.
  Eine fehlende Angabe gilt nie als bestanden; ein nicht abgesicherter Vergleich liefert weder Ersatzkurse noch Bestätigungen
  und zählt als „nicht ausreichend abgesichert“ (nicht geprüft). OpenFIGI fragt ohne Schlüssel (25 Anfragen je Minute); ein
  kostenloser Schlüssel kann als Secret `OPENFIGI_API_KEY` hinterlegt werden (nur im Prüfschritt, nie im Protokoll) – nötig
  ist er nicht.
  **Ergebnisarten** je Vergleich (Nasdaq-Historie, NOCP, Zusatzquellen, CNBC außerhalb der US-Auswahl): bestätigte
  Übereinstimmung, festgestellte Abweichung – davon **Ursache belegt** (nur mit gemeldetem Ereignis: Split passenden
  Verhältnisses bzw. Dividende nach dem Tag), **ungeklärt mit plausibler Erklärung** (Stand oder Quelle = letzte
  Minutenkerze vor 16:00 Uhr, Abstand unter einer Kursstufe, Umsatz 0 mit dem Kurs des Vortags, Faktor ohne gemeldeten
  Split), **ungeklärt ohne Erklärung** (auch der Befund „Nasdaq-Historie = NOCP, Stand nicht“) –, fehlende
  Prüfmöglichkeit und nicht abgesichert. Zusätzlich **je Aktie und Tag genau einmal** (Nasdaq-Historie und NOCP überschneiden
  sich; maßgeblich ist der abgesicherte NOCP), mit der Zahl der Tage, die in beiden bzw. nur einem Vergleich abweichen.
  Prüfgrenzen (z. B. Heimatbörse der NYSE-Gruppe: offizieller Schlusskurs nur im kostenpflichtigen Produkt „TAQ NYSE
  Closing Prices“) erklären, warum kein Beleg möglich war, nicht die Abweichung.
  Weil Nasdaq je Rechner nur etwa 430 Anfragen beantwortet, laufen **drei US-Jobs auf drei Rechnern**: „erste10“ (US-Aktien
  unter den ersten 10 einer Rangliste, die häufigsten zuerst), „plaetze11_20“ (übrige unter den ersten 20) und „zufall“
  (150 zufällig gewählte); dazu seit dem 25.10.2026, 09:20 Uhr **„welt“**: alle Aktien außerhalb der US-Auswahl mit
  mindestens einem Platz unter den ersten 10 gegen CNBC (`tests/live/kurse_welt.py`; Kürzel bei CNBC nach festen Regeln je
  Börse, belegt erst durch die Kursmeldung; **nur CNBC** – die Zusatzquellen der US-Jobs werden hier nicht abgefragt). Eine
  Anfrage an CNBC ohne verwertbare Antwort (HTTP- oder Netzfehler, unlesbare Antwort) wird nach 15 s einmal wiederholt; bleibt
  sie ohne Antwort, zählt die Aktie als **„ohne Antwort“** (Abruf fehlgeschlagen), nicht als „bei CNBC nicht gefunden“ – bis
  zum Lauf 40188406664 stand „ohne Antwort“ im Job „welt“ fest auf 0. Für US-Aktien ohne Nasdaq-Kurse fragt jeder US-Job **Zusatzquellen** ohne
  Schlüssel und Anmeldung ab (`tests/live/kurse_zusatzquellen.py`: OTC Markets, CNBC, Barchart, MarketWatch, Stooq) und
  vergleicht mit der ersten abgesicherten. Der letzte Abschluss bei OTC Markets ist **weder Vergleichskurs noch zweite
  Quelle**: die Bedeutung des Felds „lastTradeTime“ ist nicht dokumentiert; gezählt werden nur Beobachtungen (Uhrzeit des
  Stempels in UTC nach Stunde, Minute, Sekunde und Bruchteil – genau 00:00:00.000 Uhr getrennt gezählt –, Tag nach UTC bzw.
  New York, Abstand zu „quoteTime“ der Antwort und zum Abruf nach der Uhr des Prüfrechners, lastSale und previousClose gegen
  den Stand). Nicht abgesicherte Vergleiche werden für die **Abstimmung mit den Läufen vor der Absicherung** nur gezählt
  (verglichene und abweichende Tage mit der Einordnung, die sie in einem abgesicherten Vergleich bekämen) – weder Bestätigung
  noch Ursache noch Ersatzkurs. Netz- und Serverfehler werden in bis zu zwei
  weiteren Runden nachgeholt (nach 60 und 180 s), bleiben bei Nasdaq vier Aktien hintereinander ohne Antwort, folgt eine
  Pause von 180 s und der doppelte Abstand.
  Ausgegeben werden je Gruppe „abgesichert verglichen (mit Nasdaq bzw. Zusatzquelle) / nicht ausreichend abgesichert / keine
  Vergleichskurse / Abruf fehlgeschlagen“ – fehlende Daten zählen nicht als geprüft –, die Absicherung je Quelle mit den
  nicht bestandenen Prüfungen, jede Rangliste mit neuem Platz 1 einzeln (Zeitraum, Gruppe, Gewichtung, bisheriger und neuer
  Spitzenreiter, Rendite und R² vorher/nachher, Score wie in der App mit den Perzentilen und der Größe der
  Vergleichsmenge, **kleinste Auslösermenge** – Teilmengen der ersetzten Aktien nach Größe, jede Größe vollständig; reicht das
  Budget nicht, eine irreduzible Menge mit der Grenze „mindestens k Aktien“, ausdrücklich nicht „kleinste“ –, die
  auslösenden Kursabweichungen mit Datum und Einordnung, die Lage jedes Auslösers gegenüber beiden Spitzenreitern und die
  **Gegenprobe** je Auslöser: allein und alle übrigen ersetzten Kurse ohne ihn – seit dem 25.10.2026, 11:45 Uhr mit der
  unabhängigen Rechnung der Nachrechnung, nicht mit der schnellen Rechnung der Suche; bei Auslösermenge 1 zusätzlich jede
  einzelne ersetzte Aktie unabhängig, eine Abweichung von der Suche steht am Wechsel) und die **Zuordnung jedes Buchstabens** zu
  genau einer Aktie über ihren besten Platz in einer Rangliste des Stands (in der App mit der Passphrase nachzusehen,
  Einstellung „Auffällige ausblenden“ aus; nach einem neueren Stand über „Datenstand & Betrieb → Frühere Stände“).
  **Lücken je Aktie:** jede ausgewählte Aktie ohne abgesicherten Vergleich bekommt einen Buchstaben mit Börse, Kursbereich,
  Plätzen unter den ersten 10 und auf Platz 1, ungeprüften Tagen und Grund (ohne Vergleichskurse, nicht abgesichert mit den
  nicht bestandenen Prüfungen); dazu je Börse die nicht bestandenen Prüfungen und die Ranglisten, deren Platz 1 ungeprüft ist.
  Seit dem 25.10.2026, 11:45 Uhr steht bei jeder nicht bestandenen Prüfung ein **Befund** aus Codes und Zahlen (keine Namen,
  Kürzel oder ISIN): bei „Aktie und Gattung“ Form, Prüfziffer und Land der ISIN und die Börsencodes, an denen OpenFIGI sie
  führt; beim Namen die Ähnlichkeit; bei der Börse die Börse laut Quelle; bei der Währung die Währung laut Quelle; beim
  Kursniveau das Verhältnis Stand/Quelle im Median; bei zu wenigen Tagen ihre Zahl; ohne Treffer bei CNBC die Zahl der
  geprüften Schreibweisen. Die fehlende Prüfmöglichkeit ist je Vergleich aufgeschlüsselt (beim NOCP: nicht Nasdaq-notiert,
  Nasdaq-notiert ohne NOCP, ohne Nasdaq-Kurse, nicht abgesichert) – die nicht abgesicherten Aktien sind ein Teil davon.
  **Gemeinsame Wirkung (Job „Ursachen – gemeinsame Wirkung aller Gruppen“):** Jeder Job gibt seine Ersatzkurse verschlüsselt
  (Schlüssel des Stands, AES-256-GCM, an Stand und Job gebunden) als Ausgabe des Jobs weiter – kein Artefakt, im Protokoll
  nur eine Prüfsumme. Der gemeinsame Job rechnet alle Ranglisten gegen denselben unveränderten Stand: (a) Nasdaq-Historie,
  (b) NOCP, (c) Zusatzquellen, (d) CNBC außerhalb der US-Auswahl und gemeinsam (b)+(c), (c)+(d), (b)+(c)+(d), (a)+(c),
  (a)+(c)+(d) – je Paar die **Wechselwirkung** (Platz 1, Aktien und Reihenfolge der ersten 10, irgendeine Änderung und
  die Ränge aller Aktien: erst gemeinsam entstanden, aufgehoben, auch einzeln), die **Quelle je Aktie und Tag** (Regel,
  Prüfsumme, Überschneidung) und die **Abdeckung des ganzen Aktienuniversums** nach Börse, Aktien, Tagen im Prüfzeitraum
  und Ranglisten; dazu jeden US-Job allein und die Aufteilung bis zum 24.10. (erste 20 / Zufallsstichprobe) zum Vergleich
  mit Lauf 40139805053. Eingabe **„ursachen_stand“** (z. B. `2026-10-23_3f7ce5f3`; leer = letzter Stand mit Schlusskursen)
  hält alle Jobs eines Laufs auf demselben Stand. GitHub zeigt je Schritt höchstens 10 Hinweise je Art und je Job höchstens
  50: die übrigen kommen in den Schritten „Einzelheiten 2–5“, der letzte Hinweis bestätigt „Alle N Teile ausgegeben“ oder
  zählt, was fehlt; der gemeinsame Job schreibt seine Hinweise in Kurzform (Rangliste als Tage/Gruppe/Gewichtung, Kurzzeichen
  der Einordnung je Tag – Legende im ersten Teil jedes Abschnitts); vollständig und in Langform steht alles in der
  Zusammenfassung des Jobs (hochgeladen wird nichts). Titel: „Kursursachen (erste 10) bzw.
  (Plätze 11–20), (Zufallsstichprobe), (außerhalb der US-Auswahl): jede Abweichung belegt“ (grün), „NICHT VOLLSTÄNDIG
  BELEGT“ oder „UNVOLLSTÄNDIG“ (rot, auch bei Aktien ohne Vergleichskurse oder ohne abgesicherte Zuordnung); „Kursursachen
  gemeinsam: alle … abgesichert verglichen“ (grün) oder „UNVOLLSTÄNDIG“ (rot).
- **„Originalstände“** – Job „Originalstand nachrechnen“ für die drei Stände vom 12.10.2026 im Release, je mit dem
  Prüfnachweis ihres damaligen Laufs (Eingangskurse, Renditen, R²): „Stand = damaliger Lauf“, „damalige Berechnung
  reproduziert“ und „fachlich korrekt“ getrennt (Testbericht 8c). Das sind Originaldaten dieser App, nicht des
  Ausgangsmodells.
- **„Weitere Browser“** – Job „Weitere Browser mit echten Daten“: dieselbe Live-Prüfung wie „pruefen“ in **Firefox** und
  **WebKit** (Format des S25+, etwa 5 Minuten); die Installation als Web-App prüft nur Chromium (dort übersprungen, mit
  Grund). Chrome und Samsung Internet auf dem S25+ nutzen Chromium – die beiden anderen sind zusätzliche Browser, kein Gerät.

**Getrennte Urteile der Nachrechnung (ab 1.18):** Je Stand steht „Damalige Berechnung reproduziert“ (keine Rechenabweichung
nach der Methode des Stands) getrennt von „Fachlich korrekt“ (keine bekannten Fehler dieser Version). Bei einem Stand mit
bekannten Fehlern zeigt ein eigener Hinweis, ob ihre Ursache in der aktuellen Version behoben ist – mit dem Rechenkern
der aktuellen Version auf den Werten des Stands – und welche beabsichtigten Methodenänderungen seitdem kamen (keine Fehler).

## Täglicher Betrieb

| Uhrzeit (Europe/Berlin) | Lauf |
|---|---|
| Mo–Fr 00:37 (Sommerzeit) bzw. 23:37 (Winterzeit) | **Nachtlauf (ab 1.17)**, Workflow „Nachtlauf“ (`nachtlauf.yml`, 22:37 UTC): startet den täglichen Lauf, sobald alle Börsen des Tages geschlossen haben (spätester Schluss etwa 21:00 UTC plus eine Stunde Nachlieferungsfrist). Auch mit GitHubs Verzögerung ist der neue Stand so meist am frühen Morgen da statt mittags. Pünktlich auf die Minute nur mit dem optionalen externen Auslöser (unten) |
| 07:00 | regulärer Lauf: neuer Börsenschluss des Vortags wird berechnet und veröffentlicht (bis 1.4: 06:00). GitHub startet geplante Läufe aber oft 4 bis 5 Stunden später (gemessen 15.–23.10.2026: erster Lauf zwischen 11:00 und 12:30 Uhr); der Lauf selbst dauert dann 80 bis 115 Minuten, siehe 09_Bekannte_Luecken |
| 07:15, 07:45, 09:00 | Wiederholungen: setzen einen unvollständigen Lauf fort oder bestätigen „kein neuer Börsenschluss“ |
| jederzeit | von Hand: in der App **Kurse jetzt aktualisieren** (Startseite) oder ☰ → **Jetzt aktualisieren** → „Jetzt aktualisieren“, oder direkt Actions → Täglicher Lauf → Run workflow. Ab 1.9.1 ist **„Alles aktualisieren“** voreingestellt: fehlt der offizielle Stand des letzten Börsentags, entsteht er zuerst (danach Kennzahlen und Signale), dann der Zwischenstand mit den aktuellen Kursen. Neue Schlusskurse frühestens etwa eine Stunde nach US-Börsenschluss (meist gegen 23 Uhr) |
| während des Handels | derselbe Lauf von Hand (Voreinstellung „Alles aktualisieren“, ab 1.8 als Haken „Zwischenstand“): vorläufige Ranglisten mit den aktuellen, verzögerten Kursen; ersetzt einen früheren Zwischenstand, wird vom nächsten offiziellen Stand abgelöst |

- Kursstichtag ist der jüngste Handelstag, dessen Schlusskurse an allen an diesem Tag geöffneten Börsen feststehen (plus 60 Minuten Nachlieferungsfrist). Um 07:00 ist das der Vortag; Tokio und Sydney handeln zu dieser Zeit schon den neuen Tag und werden dafür nicht abgewartet.
- Fehlen Kurse einzelner Börsen noch, wartet der Lauf auf die nächste Wiederholung. Erst der letzte geplante Versuch (09:00) entscheidet: deutlich markierter **Teilstand** (ab 1.5.1: mindestens 75 % der erwarteten Aktien mit Schlusskurs am Stichtag; bis 1.5.0: 90 % der Börsen) oder Fehlschlag mit E-Mail von GitHub. Einen Teilstand sofort erzwingen: Actions → Täglicher Lauf → Run workflow mit „erzwingen“. Von Hand gestartete Läufe („Jetzt aktualisieren“) warten in diesem Fall nur weiter – sie zählen nicht als Wiederholung und erzeugen keinen roten Lauf.
- GitHub kann geplante Läufe verzögern oder bei hoher Last verwerfen. Deshalb gibt es Wiederholungen und eine Herzschlag-Prüfung: Meldet sich der Lauf länger als 30 Stunden nicht, zeigt die App „Keine aktuelle Prüfung“.
- GitHub deaktiviert Zeitpläne in öffentlichen Repositories nach 60 Tagen ohne Aktivität. Der Lauf schreibt deshalb spätestens alle 45 Tage einen Aktivitätsnachweis (`ops/letzte-aktivitaet.txt`).
- Bei einem fehlgeschlagenen geplanten Lauf schickt GitHub eine E-Mail an das Konto, das den Zeitplan zuletzt geändert hat.
- **Zeitplan-Eigentümer:** GitHub verbindet den Zeitplan mit dem Konto, das die Cron-Zeilen zuletzt geändert oder den Workflow zuletzt aktiviert hat. Hat dieses Konto keinen Zugriff auf das Repository (Commits von Claude), startet GitHub keine geplanten Läufe – so am 13. und 14.10.2026. Abhilfe: Workflow „Täglicher Lauf“ mit deinem Konto deaktivieren und wieder aktivieren (am 14.10. per API mit deinem Zugang erledigt, nach jeder Änderung an der Workflow-Datei wiederholt).

## Kurslauf kontrollieren (ab 1.17.1)

**Actions** → **Kurslauf kontrollieren** → **Run workflow** (nur lesend, ohne Secrets, etwa 30 Sekunden). Ohne Laufnummer
prüft der Workflow alle offiziellen Läufe von „Täglicher Lauf“ ab dem eingetragenen Tag (Voreinstellung 26.10.2026, der
erste Börsentag mit Nachtlauf) und beurteilt den **ersten zeitgesteuerten Lauf mit Abruf aller Notierungen**.

**Abnahme und Prüfskript sind zweierlei (ab 1.18).** Der Lauf hat zwei Schritte: „Prüfskript ausführen“ ist grün, wenn das
Skript fehlerfrei lief – auch wenn die Abnahme nicht bestanden ist. Das fachliche Gesamtergebnis zeigt allein der Schritt
**„Abnahme (fachliches Gesamtergebnis)“** und der Hinweis „Abnahme Kurslauf: BESTANDEN / NICHT BESTANDEN / AUSSTEHEND“:

| Ergebnis | Bedeutung | Lauf in GitHub |
|---|---|---|
| BESTANDEN | der beurteilte Lauf erfüllt alle Kriterien | grün |
| NICHT BESTANDEN | mindestens ein Kriterium nicht erfüllt – der Hinweis nennt jedes | rot (Schritt „Abnahme“) |
| AUSSTEHEND | noch kein zeitgesteuerter Lauf mit Abruf aller Notierungen – nichts bestanden | rot (Schritt „Abnahme“) |
| Prüfskript abgebrochen | kein fachliches Ergebnis | rot (Schritt „Prüfskript ausführen“) |

Ein grüner Lauf heißt also: Abnahme bestanden. Die Laufübersicht hat dazu ab 1.18.1 einen Abschnitt **„Prüfstatus“**:
fachliche Abnahme, nicht erfüllte Kriterien (mit Ist-Werten), erfüllte Kriterien, Ausstehendes („ein Start von Hand
ersetzt diesen Nachweis nicht“), Prüfskript („fehlerfrei ausgeführt – das ist weder ein Softwaretest noch eine Abnahme“)
und Softwaretests (nicht Teil dieser Kontrolle, Workflow „Prüfung“).
Lokal gibt `python3 ops/kurslauf_kontrolle.py` dasselbe als Rückgabewert
zurück (0 bestanden, 10 nicht bestanden, 11 ausstehend, 2 abgebrochen); lokal ist die veröffentlichte `status.json` nicht
abrufbar, deshalb gibt es dort nie „bestanden“.

Kriterien (`ops/kurslauf_kontrolle.py`, alle müssen erfüllt sein):

| Kriterium | Soll |
|---|---|
| zeitgesteuert | Auslöser „schedule“ (Zeitplan) oder vom Workflow „Nachtlauf“ gestartet, der selbst über GitHubs Zeitplan ausgelöst wurde (ab 1.18; ein Nachtlauf von Hand oder über den externen Auslöser zählt nicht); beim Nachtlauf werden dessen Laufnummer und die Verspätung gegenüber 22:37 UTC genannt |
| neuer Kursstand | vollständig veröffentlicht |
| Kurse aller Notierungen | in diesem Lauf abgefragt: mindestens 10.000, **keine aus dem Checkpoint** eines früheren Laufs (ab 1.18 streng) |
| jede Notierung mit Ergebnis | ok, keine Daten, ohne Stichtagskurs … zusammen = alle Notierungen; **kein Abruffehler, kein Einzelfehler** (ab 1.18); der Anteil mit Kurs zum Stichtag steht dabei (24.10.: 98,3 %) |
| Tempo | alle drei Mindestanforderungen: **mindestens 10.000 Abrufe** in diesem Lauf, **mindestens 6 Abrufe je Sekunde** über die ganze Messdauer, **gleichzeitig über zwei Hosts** (Messlauf vom 24.10., nur lesend: 10.845 Abrufe, 8,0 je Sekunde). Der Ist-Wert nennt jede einzeln mit „erfüllt“/„NICHT erfüllt“, z. B. „Abrufe 49 (verlangt mindestens 10.000: NICHT erfüllt); Messdauer 6 s; Geschwindigkeit 8,1 je Sekunde (verlangt mindestens 6: erfüllt); gleichzeitig über 2 Hosts ja (…: erfüllt)“ |
| Drosselung | kein Rückfall auf den einzelnen Abruf wegen HTTP 429 |
| Dauer | Job „berechnen“ höchstens 60 Minuten (bis 1.16: 80–115); dazu zur Information die Zeit bis zur Website mit Signalen |
| Kennzahlen und Website | Job „kennzahlen“ und Bereitstellung erfolgreich |
| `status.json` | neuer Kursstand als neuester Stand (unter einem später gerechneten Zwischenstand dessen Stand mit Schlusskursen) und der nächste Kursstand danach |
| Signale (ab 1.18) | `status.json` nennt einen Signal-Stand **genau dieses Stands** (`snapshot_id`), zu dessen Kursstand, **nach dem Start des Laufs** erstellt – nicht nur „Job grün“ |

Ist seit dem beurteilten Lauf ein neuerer Stand veröffentlicht, sind die beiden letzten Kriterien für ihn „nicht mehr
beurteilbar“ (zählt nicht als erfüllt) – die Kontrolle gehört deshalb kurz nach den Lauf.

Die Datei des täglichen Laufs (`taeglich.yml`) wird dafür bewusst nicht geändert: GitHub verbindet deren Zeitplan mit dem
Konto, das sie zuletzt geändert bzw. aktiviert hat (Abschnitt „Täglicher Betrieb“). Die Live-Prüfung der App und die
unabhängige Nachrechnung brauchen die Passphrase und bleiben im Workflow „App mit echten Daten prüfen“.

## Externer Auslöser (optional, ab 1.17)

GitHub beginnt geplante Läufe oft Stunden später (gemessen 15.–24.10.2026: der erste geplante Lauf des Tages begann zwischen 11:00 und 12:30 Uhr statt um 07:00 Uhr, also 4 bis 5½ Stunden später). Der Nachtlauf gleicht das aus, weil er früh genug geplant ist. Wer den neuen Stand pünktlich kurz nach Mitternacht haben möchte, kann den Workflow „Nachtlauf“ zusätzlich von außen starten lassen – kostenlos mit Google Apps Script (eigenes Google-Konto, läuft in Googles Rechenzentrum, das Handy muss nicht an sein). Nötig ist das nicht; ohne diesen Auslöser ändert sich nichts.

1. **Token anlegen (GitHub):** github.com → Profilbild → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token. Name „Nachtlauf-Auslöser“, Ablauf nach Wahl (zum Beispiel 1 Jahr), **Repository access: Only select repositories → tr-aktienvergleich**, **Permissions → Repository permissions → Actions: Read and write** (sonst nichts). Token kopieren – es wird nur einmal angezeigt.
2. **Skript anlegen (Google):** script.google.com → Neues Projekt → Namen geben → den Inhalt von [`ops/externer-ausloeser/nachtlauf-ausloeser.gs`](../ops/externer-ausloeser/nachtlauf-ausloeser.gs) einfügen → speichern.
3. **Token hinterlegen:** Projekteinstellungen (Zahnrad) → **Skripteigenschaften** → Eigenschaft `GITHUB_TOKEN`, Wert = das Token → speichern. Das Token gehört nur dorthin – nicht in den Code, nicht in eine E-Mail oder einen Chat.
4. **Zeitplan anlegen:** Im Editor die Funktion `zeitplanEinrichten` auswählen → Ausführen → Zugriff erlauben (Google fragt einmal, ob das Skript einen externen Dienst aufrufen und ohne dich laufen darf). Ab dann startet das Skript täglich gegen 00:40 Uhr Berliner Zeit (± 15 Minuten), in den Nächten nach Samstag und Sonntag tut es nichts.
5. **Ausprobieren:** Funktion `jetztTesten` ausführen. Auf GitHub erscheint unter Actions ein Lauf „Nachtlauf“, kurz danach „Täglicher Lauf“. Unter Apps Script → Ausführungen steht „Nachtlauf gestartet (HTTP 204)“.

Bei einem Fehler schreibt das Skript nur ins Ausführungsprotokoll (keine Fehler-E-Mails); bleibt der Stand aus, zeigt die App „Neuer Kursstand überfällig“. Abschalten: in Apps Script unter Auslöser den Auslöser löschen und das Token auf GitHub widerrufen. Läuft das Token ab, meldet das Protokoll „HTTP 401“ – dann ein neues anlegen (Schritt 1) und in Schritt 3 ersetzen.

Geprüft ist das Skript mit nachgebildeten Google-Diensten im App-Test `app/tests/ausloeser.test.ts` (läuft bei jeder Änderung im Workflow „Prüfung“): Adresse, Kopfzeilen und Nutzlast des Aufrufs, die Wochentagsregel nach Berliner Datum über den Wechsel von Sommer- und Winterzeit, fehlendes Token, Fehlerantworten (401, 403, 404, 422, 429, 5xx) und fehlendes Netz ohne Ausnahme, das Token nie im Protokoll, der Zeitplan. **Nicht geprüft:** in einem echten Google-Konto und gegen GitHub selbst – das zeigt erst Schritt 5.

## Laufzeiten und Größen (gemessen, siehe 07_Testbericht)

Lasttest mit 11.500 synthetischen Aktien (2 vCPU): Rechenkern 43 s, verschlüsselte Veröffentlichung 57 s, 74 MB je Datenstand, 411 MB Arbeitsspeicher. Täglich dominiert der Kursabruf (eine Anfrage je Notierung): bis 1.16 nacheinander mit 2,5 je Sekunde – der Lauf mit neuen Schlusskursen dauerte 80 bis 115 Minuten (gemessen 16.–23.10.2026); ab 1.17 4 gleichzeitig über zwei Hosts – im Messlauf vom 24.10.2026, 12:44–13:11 Uhr 10.845 Notierungen gleichzeitig in 22,6 Minuten (8,00 je Sekunde, ohne Drosselung (0 × HTTP 429)), hochgerechnet auf alle 11.145: **23,2 Minuten**. Im täglichen Lauf kommt das Speichern dazu; gemessen wird das erstmals mit dem nächsten neuen Börsentag (07_Testbericht). Die Website behält drei Datenstände (ab 14.10.2026, vorher fünf; weit unter der 1-GB-Grenze von GitHub Pages), die Release-Assets 60 Archive.

Ab 1.3 lädt der erste Lauf zusätzlich die Wochenwerte für die Umschichtungs-Regel (bis 3 Jahre je Aktie mit Ø Tagesumsatz ab 2 Mio. USD; höchstens 40 Minuten, der Rest im nächsten Lauf). Danach kommen täglich nur neu aufgenommene Aktien und Aktien nach einem Split dazu. Die gesicherte Datenbank wächst dadurch um die Wochenwerte (einige Zehntausend Zeilen je 100 Aktien).

## Monatliche Kostenannahmen

| Posten | Annahme | Monatlich |
|---|---|---|
| GitHub Actions | öffentliches Repository, Standard-Runner (auch „Kursaktualisierung“ aus der App, ab 1.21) | 0 € |
| GitHub Pages | öffentliches Repository, < 1 GB, < 100 GB Datenverkehr | 0 € |
| Release-Assets (verschlüsselter Zustand, Archive) | öffentliches Repository | 0 € |
| Yahoo Finance | inoffiziell, kein Vertrag | 0 € |
| OpenFIGI | kostenloser Schlüssel | 0 € |
| **Summe Standardaufbau** | | **0 €** |
| optional EODHD „EOD Historical All-World“ | 100.000 Abrufe/Tag, nur nach Freigabe | 19,99 USD (199 USD jährlich) |

Die kostenlose Lösung hat Grenzen: Yahoo ist keine vertraglich zugesicherte Quelle und kann Abrufe drosseln oder sperren. Es gibt keine erfundene kostenlose Vollabdeckung – welche Aktien tatsächlich berechnet wurden, zeigt jede Veröffentlichung in der Abdeckungsbilanz.

## Änderungen am Projekt

Jede Änderung im Repository startet den Workflow **Prüfung** (alle Tests, App-Build, Browser-Tests). Nach Änderungen an der App `cd app && npm ci && npm run build` ausführen und `app/dist` mit einchecken – die Prüfung meldet sonst „app/dist ist veraltet“.

## Abschalten

**Actions** → **Täglicher Lauf** → **⋯** → **Disable workflow**. Die zuletzt veröffentlichte App bleibt bis zum Löschen des Repositorys erreichbar.

## Rechenzeit und Prozessorkerne (ab 1.10, erweitert in 1.12)

Der Lauf rechnet die Kennzahlen aller Aktien, schreibt die Dateien (ab 1.12) und prüft die Website auf mehreren Prozessorkernen (GitHub-Runner: 4). Die Zahl lässt sich mit der Umgebungsvariablen `TRAKTIEN_RECHENPROZESSE` festlegen (z. B. `1` für einen einzigen Prozess); ohne Angabe gilt die Zahl der Kerne, höchstens 4. Das Ergebnis ist in jedem Fall dasselbe (gleiche Prüfsummen). In der Laufübersicht steht unter „Dauer“, wie lange jeder Abschnitt gebraucht hat (Zustand laden, Kurse abrufen, Kursreihen laden, Rechnen, Dateien schreiben, Website), unter „Website“ die Größe der veröffentlichten Dateien.

**Ab 1.12 beim Zwischenstand („Alles aktualisieren“):**

- Die aktuellen Kurse kommen über drei gleichzeitige Abrufer mit gemeinsamem Mindestabstand von 0,12 s je Host. Meldet Yahoo eine Drosselung, enden alle Abrufe sofort; bereits geladene Kurse bleiben.
- Ältere Stände und der Signal-Stand werden schon während des Kursabrufs geladen und entpackt (Ordner `state/site_cache`); die Website verweist danach nur noch auf diese Dateien.
- Gesichert wird als eigener Prozess (`traktien sichern`, Protokoll `state/.sichern.log`), während der Workflow die Website prüft und hochlädt. Der letzte Schritt des Jobs („Sichern abwarten“, `traktien sichern-warten`) wartet darauf; schlägt das Sichern fehl, wird der Job rot und nichts bereitgestellt. Ab 1.15 wiederholt das Hochladen vorübergehende Fehler des Upload-Servers (HTTP 5xx, 429, Verbindungsabbruch) bis zu viermal mit 5, 15 und 30 s Abstand (Anlass: „HTTP 502“ am 14.10.2026, 17:18 Uhr); andere Fehler (z. B. 401, 422) brechen sofort ab.
- Die Python-Umgebung liegt im Zwischenspeicher von GitHub Actions (Schlüssel: Python-Version und `backend/requirements.txt`); neu installiert wird nur nach einer Änderung.
- Die Website wird ohne Kompression hochgeladen (Schritte „Website packen“ und „Website als Pages-Artefakt“ mit `actions/upload-artifact`, `compression-level: 0`). Das Artefakt hat dasselbe Format wie mit `actions/upload-pages-artifact` – eine `artifact.tar` ohne `.git`, `.github` und versteckte Dateien –, `actions/deploy-pages` stellt es unverändert bereit und fragt den Status zuerst nach 1 Sekunde ab (`reporting_interval: 1000`). Bereitgestellt wird im selben Job als letzter Schritt („Website bereitstellen“, Umgebung `github-pages`) – erst nach erfolgreicher Prüfung und erfolgreichem Sichern; ein eigener Job „bereitstellen“, der erneut auf einen freien Runner warten müsste, entfällt.
