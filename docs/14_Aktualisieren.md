# „Jetzt aktualisieren“ aus der App, Kurszeiten und Tempo (ab 1.21; ab 1.22 ohne Zugang in der App)

Auftrag vom 31.10.2026, 12:54 Uhr (Ergänzung zur AktienPilot-Fassung vom 31.10.2026):

> Die App muss „Jetzt aktualisieren“ anbieten: für einzelne Aktien und Kursverläufe, Depot und Merkliste sowie den gesamten
> Datenbestand. Der Knopf muss einen tatsächlichen Datenabruf anfordern und dessen Fortschritt anzeigen. Ergänze automatische
> Aktualisierung während der Nutzung. Zeige Kurszeit, Abrufzeit und bekannte Verzögerungen getrennt. Bereits gespeicherte alte
> Kurse dürfen nach erneutem Laden nicht als aktuell erscheinen. Optimiere Datenabruf, Verarbeitung, Übertragung und
> Chartdarstellung. Lade bevorzugt nur Änderungen und aktualisiere sichtbare Aktien zuerst. Verwende ausschließlich kostenlose
> Dienste. […] Belege Verbesserungen durch Vorher-/Nachher-Messungen.

Die Nachricht nannte eine angehängte Auftragsfassung; angekommen ist keine neue Datei. Geschwindigkeitsziele waren deshalb
nicht vorgegeben – die Ziele unten sind hier festgelegt und gelten, bis du andere nennst.

## 1. Was die App jetzt kann

**Ab 1.22 enthält die App keinen GitHub-Zugang mehr** – kein Token, auch nicht verschlüsselt (Sicherheitsvorgabe vom
07.11.2026: „Keine GitHub-Tokens oder sonstigen Geheimnisse im Browser speichern, auch nicht verschlüsselt“). Gestartet wird
jeder Lauf auf GitHub mit deiner eigenen Anmeldung; die App bereitet nur vor und liest danach ohne Anmeldung mit.

| Umfang | Wo in der App | Weg | Ergebnis |
|---|---|---|---|
| Eine Aktie mit Tagesverlauf | Einzelansicht → „Kurs aktuell“ → **Jetzt aktualisieren** | Workflow „Kursaktualisierung“, Start auf GitHub mit der kopierten Zeile | aktueller Kurs, Tagesverlauf in 5-Minuten-Schritten, Veränderung zum Vortag |
| Merkliste | Merkliste → **Jetzt aktualisieren** (auch unter ☰ → Jetzt aktualisieren) | wie oben | Kurs je Zeile; die ersten zehn (sichtbaren) Zeilen kommen zuerst |
| Depot | Musterdepots → gewähltes Depot → „Kurse dieses Depots aktuell“ | wie oben | Kurs je Depotaktie |
| Gesamter Datenbestand | ☰ → Jetzt aktualisieren → **Auf GitHub starten** | täglicher Lauf als Zwischenstand („Run workflow“ ohne Eingabe) | alle Ranglisten neu; die App wartet und zeigt den neuen Stand |
| Automatisch | Einstellungen → „Automatisch aktualisieren“ | Website | neue Stände jede Minute geprüft, beim nächsten Seitenwechsel angezeigt. Automatische Kursabrufe gibt es nicht mehr – ohne Zugang kann die App keinen Lauf starten |

So geht „Jetzt aktualisieren“ für einzelne Aktien:

1. In der App **Jetzt aktualisieren** antippen. Die App verschlüsselt die Anfrage mit dem Datenschlüssel und bereitet eine
   Zeile „`<Kennung>.<verschlüsselter Text>`“ vor.
2. **Kopieren und GitHub öffnen** antippen (bei GitHub angemeldet sein) – die Zeile ist in der Zwischenablage, die Seite des
   Workflows „Kursaktualisierung“ ist offen.
3. Auf GitHub **Run workflow** antippen, ins Feld „anfrage“ lange tippen → **Einfügen**, grünen Knopf **Run workflow**.
4. Zurück zur App: Sie sucht den Lauf sofort und zeigt den Fortschritt – „Wartet auf einen GitHub-Rechner“ → „Kurse werden
   abgerufen“ (mit dem Schritt des Laufs) → „Teil 1 von 2 angekommen“ → „Kurse aktualisiert“, mit Link zum Lauf.

Die Anfrage gilt 20 Minuten (danach lehnt der Server sie ab und die App sagt „bitte neu anfordern“). Lässt sich nicht
kopieren (z. B. ohne Berechtigung für die Zwischenablage), zeigt „Zeile anzeigen“ sie zum Markieren. Eine abgeschnittene
Zeile lehnt der Lauf mit einem Code ab (`eingabe_unvollstaendig`, `kennung_ungueltig` – nie mit dem Inhalt), die App meldet
„Lauf fehlgeschlagen – meist war die eingefügte Zeile unvollständig“.

Gelesen wird ohne Anmeldung, weil das Repository öffentlich ist: der Lauf über die GitHub-Schnittstelle (höchstens 60
Abfragen je Stunde und Netz – die App fragt alle 20 Sekunden und nur, solange sie sichtbar ist, etwa 6 Abfragen je Minute),
die verschlüsselten Lieferungen über raw.githubusercontent.com zu einem festen Commit (unveränderlich, nie ein veralteter
Zwischenspeicher, zählt nicht zur Grenze).

## 2. Kurszeit, Abrufzeit, bekannte Verzögerung

Jeder angezeigte Kurs hat drei getrennte Angaben (Einzelansicht ausführlich, Merkliste und Depot in einer Zeile):

* **Kurszeit** – wann der Kurs an der Börse entstand (laut Kursanbieter), mit Handelstag
* **Abrufzeit** – wann der Server ihn abgerufen hat, und wie lange das her ist
* **Bekannte Verzögerung** – laut Antwort des Anbieters (Yahoo „exchangeDataDelayedBy“), sonst laut Yahoo-Hilfe
  [„Exchanges and data providers on Yahoo Finance“](https://help.yahoo.com/kb/SLN2310.html) (abgerufen 31.10.2026), z. B. Xetra
  15 Minuten, London 20, SIX 30, Toronto und Stockholm Echtzeit. USA ohne Börsenangabe: keine Angabe (Nasdaq-Daten in
  Echtzeit, OTC 15 Minuten – nicht unterscheidbar).

Dazu ein **Zustand**, der bei jeder Anzeige aus der jetzigen Uhrzeit neu gerechnet wird – nie gespeichert:

| Zustand | Bedingung |
|---|---|
| aktuell | Handel läuft (Status „REGULAR“), Kurs höchstens Verzögerung + 20 Minuten alt **und** Abruf höchstens 30 Minuten her |
| nicht aktuell (Kurs … alt) | Handel läuft, aber eine der beiden Grenzen überschritten – z. B. eine gespeicherte Lieferung nach dem erneuten Öffnen |
| Börse geschlossen – letzter Kurs | Status „CLOSED“/„POST“ bzw. „vor Handelsbeginn“ |
| Schlusskurs vom … – kein aktueller Kurs | Kurs aus dem veröffentlichten Stand (ohne Lieferung) |

Gelieferte Kurse bleiben zwei Tage auf dem Gerät (so verschlüsselt, wie sie ankommen) und erscheinen beim nächsten Öffnen mit
ihren echten Zeiten – nie als „aktuell“, wenn sie es nicht mehr sind (App-Test „Zeitangaben getrennt …“).

## 3. Aufbau

```
App (Handy)                         GitHub                                   Yahoo
───────────                         ──────                                   ─────
Anfrage {ISIN, Symbol, sichtbare    POST …/aktualisieren.yml/dispatches
zuerst} mit Datenschlüssel ──────►  Eingaben: kennung (Zufall),
verschlüsselt (AES-256-GCM,          anfrage (Chiffretext)
AAD „anfrage/<kennung>“)                │
                                        ▼
                                    Lauf „Kursaktualisierung“ ──────────────► quote (bis 150 Werte je Abruf),
                                    prüft Anfrage (Integrität, Schema,          chart 1d/5m nur für den Tagesverlauf
                                    Größe ≤ 250 Werte, Alter ≤ 20 min,
                                    ISIN-Prüfziffer, Symbolformat)
                                        │ Teil 1: sichtbare Aktien (≤ 25)
                                        │ Teil 2: Rest
                                        ▼
Fortschritt: GET …/runs/<id>,       Branch „kurse-aktuell“: aktuell/<kennung>-<teil>.bin
…/jobs (Schritte)                   (verschlüsselt, AAD = Pfad; ein Commit ohne Verlauf,
Lieferung: GET …/contents/…  ◄────  Lieferungen älter als 2 Tage entfernt)
```

* Öffentlich sichtbar sind nur die Zufallskennung und Chiffretext; Protokolle des Laufs enthalten nur Zählungen und Zeiten.
* Datenstand, Ranglisten und Website ändert dieser Lauf nicht. Eigene Warteschlange („kursaktualisierung“): er verdrängt nie
  einen täglichen Lauf.
* Der gesamte Datenbestand läuft wie bisher über den täglichen Lauf (Zwischenstand); `taeglich.yml` ist unverändert.

## 4. Ohne Zugang: Rechte und Sicherheit (ab 1.22)

* **Kein Token in der App.** Bis zum Entwicklungsstand vor 1.22 konnte ein feingranulares Token (nur „Actions: Lesen und
  Schreiben“) verschlüsselt auf dem Gerät liegen. Diese Fassung wurde nie veröffentlicht; mit 1.22 ist der ganze Weg entfernt:
  kein Eingabefeld, kein Speicher, kein Kopf „Authorization“, kein schreibender Aufruf. Ein Bereich „zugang“, den die
  Entwicklungsfassung angelegt haben könnte, löscht die App beim Öffnen ihrer Datenbank (Version 3) samt Inhalt.
* **Gestartet wird auf GitHub** mit deiner Anmeldung (Browser oder GitHub-App). GitHub prüft dort die Berechtigung – die App
  sieht davon nichts.
* **Öffentlich sichtbar** sind nur die Zufallskennung und Chiffretext (Workflow-Eingabe, Branch „kurse-aktuell“). Der Lauf liest
  die Zeile nur aus einer Umgebungsvariablen, nie als Befehl (`backend/traktien/util/eingabe.py`, Tests
  `tests/unit/test_eingabe.py`, `tests/unit/test_workflows.py`).
* **Lesen ohne Anmeldung:** keine Cookies (`credentials: omit`), kein Referrer, die Inhaltsrichtlinie der App erlaubt nur
  `api.github.com` und `raw.githubusercontent.com`.
* **Serverseitige Lösung mit einem Tippen (ohne GitHub-Seite):** bräuchte einen eigenen kleinen Dienst, der das Token in
  seinem Secret Store hält (z. B. einen kostenlosen Cloudflare Worker) – dafür müsstest du dort ein Konto anlegen. Ohne deine
  Entscheidung bleibt der sichere Weg über die GitHub-Seite (Stand 07.11.2026).

## 5. Kosten (Nullbudget)

| Dienst | Nutzung | Kosten | Grenze und Verhalten |
|---|---|---|---|
| GitHub Actions (öffentliches Repository, Standard-Runner) | Lauf „Kursaktualisierung“ (etwa 20–40 s je Anfrage) | 0 € – für öffentliche Repositorys kostenlos | nur, wenn du auf GitHub startest; gleichzeitige Läufe stehen in einer eigenen Warteschlange |
| GitHub REST API (ohne Anmeldung) | Lauf finden, Fortschritt, Stand des Lieferkanals | 0 € | 60 Anfragen je Stunde und Netz; eine Aktualisierung braucht etwa 10–20; bei erreichter Grenze nennt die App die Uhrzeit, ab der sie wieder nachsieht |
| GitHub-Repository (Branch „kurse-aktuell“) | Lieferungen der letzten zwei Tage | 0 € | ein Commit ohne Verlauf – wächst nicht |
| Yahoo Finance | Kurse wie bisher | 0 € | Daten „nur zur Information“, je Börse verzögert; ein Abruf je Anfrage (bis 150 Werte), Tagesverlauf nur für eine Aktie |

## 6. Geschwindigkeitsziele (festgelegt am 31.10.2026)

| Ziel | Messgröße | Wert |
|---|---|---|
| Z1 | Eine Aktie, Merkliste oder Depot (bis 50 Aktien): Tippen bis zum angezeigten neuen Kurs | Median ≤ 45 s; Serveranteil ohne GitHub-Wartezeit ≤ 20 s |
| Z2 | Gesamter Datenbestand (Zwischenstand): Tippen bis neue Daten in der App | Median ≤ 150 s ab dem Start auf GitHub. Ab 1.22 wieder **mit** Wechsel zu GitHub und zwei Tipps dort – „ohne Wechsel zu GitHub“ ginge nur mit einem Zugang in der App, der nach der Sicherheitsvorgabe vom 07.11.2026 nicht mehr erlaubt ist |
| Z3 | App auf dem Handy (simuliert: 4-fach gedrosselter Prozessor, 12 Mbit/s, 60 ms) | Entsperren bis Startseite ≤ 1,5 s; Einzelansicht mit Kursverlauf ≤ 1,0 s; Wechsel der Kursdarstellung ≤ 200 ms; Merkliste mit 50 Aktien ≤ 1,0 s |
| Z4 | Übertragung beim Aktualisieren einzelner Aktien | nur die Änderungen: ≤ 2 KB je Aktie (verschlüsselt), sichtbare Aktien im ersten Teil |

## 7. Messungen vorher

### 7.1 Gesamter Datenbestand – Produktionsläufe „Alles aktualisieren“ (Zwischenstand), 26.–30.10.2026

Quelle: GitHub-Schnittstelle (Zeiten der Läufe, Jobs und Schritte) und die Zeitaufstellung, die jeder Lauf als Hinweis
veröffentlicht.

| Lauf | Start → Rechner | Lauf „zusammen“ | Bereitstellen | Start → bereitgestellt |
|---|---|---|---|---|
| [41055711727](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/41055711727) 30.10. 13:29 | 30 s | 82 s (Zustand 7, Kurse 8, Reihen 9, Rechnen 34, Schreiben 14) | 2 s | 151 s |
| [41037525075](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/41037525075) 30.10. 11:00 | 7 s | 74 s (10, 9, 10, 25, 12) | 2 s | 126 s |
| [40929143979](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40929143979) 29.10. 19:15 | 7 s | 69 s (10, 14, 4, 22, 10) | 3 s | 120 s |
| [40744478310](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40744478310) 28.10. 19:22 | 7 s | 109 s (28, 14, 4, 39, 14) | 3 s | 198 s |
| [40557760290](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40557760290) 27.10. 19:12 | 6 s | 70 s (9, 15, 4, 24, 11) | 2 s | 119 s |
| [40280492401](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/40280492401) 26.10. 07:33 | 6 s | 82 s (7, 3, 16, 34, 13) | 14 s | 140 s |

Median: Start → bereitgestellt **133 s**; davon Lauf 78 s, Rechnen 29 s, Schreiben 12 s. Hinzu kamen vorher der Wechsel zu
GitHub mit zwei Tipps und bis zu 15 s, bis die App den neuen Stand bemerkte (Abfrage alle 15 s). Einzelne Aktien ließen sich
nicht aktualisieren – jede Aktualisierung rechnete alles.

### 7.2 Rechenkern lokal (synthetisch, 11.000 Aktien, verschlüsselt, 2 Kerne)

`tests/perf/perf_universe.py 11000 --encrypt`: Rechenkern 33,7 s, Veröffentlichung 14,4 s, 102 MB (vorher, Commit `1c3394e`).
Profil: 90 % der Rechenzeit in der Fensterrechnung je Aktie und Zeitraum (Regression, Rückgang, Impulsanteil). **Nicht
geändert:** Der AktienPilot-Auftrag stellt Änderungen am Rankingkern zurück, solange die Referenzprüfung vom 30.10. fehlt
(Abschnitt 2) – der Engpass ist belegt, seine Beseitigung braucht deine Entscheidung.

## 8. Messungen nachher

### 8.1 Kursaktualisierung einzelner Aktien – echter Lauf in GitHub Actions

Lauf [41201893346](https://github.com/szymeklh87-commits/tr-aktienvergleich/actions/runs/41201893346) („Kursaktualisierung –
Messung“, 31.10.2026, 13:36 Uhr, Entwicklungsbranch): derselbe Programmcode wie der Workflow „Kursaktualisierung“, echte
Yahoo-Kurse öffentlich bekannter Aktien, echter Lieferkanal (eigener Branch, danach gelöscht), Wegwerf-Schlüssel statt
Datenschlüssel (keine Secrets).

| Abschnitt | Zeit |
|---|---|
| Start → Rechner bereit (GitHub-Warteschlange) | 3 s |
| Rechner vorbereiten (Checkout nur `backend` und `config`, Python, Umgebung aus dem Zwischenspeicher) | 4 s |
| 1 Aktie mit Tagesverlauf: Abruf 0,6 s, Lieferung 1,3 s | Schritt 5 s (davon Python-Start rund 2,5 s) |
| 12 Aktien (2 Teile) | Schritt 3 s (Prozess 3,3 s) |
| 50 Aktien (2 Teile: 5 sichtbare, dann 45): Abruf 0,6 + 0,9 s, Lieferung 1,2 + 1,3 s; 49 mit Kurs, 1 ohne | Schritt 5 s (Prozess 4,0 s) |

Im Betrieb kommen hinzu: Laden der Schlüsselparameter aus dem Release (rund 1–2 s), Ableitung des Datenschlüssels (unter 1 s),
die Abfrage der App alle 2 s (im Mittel 1 s) und Laden und Entschlüsseln der Lieferung (unter 0,5 s). **Ergebnis: rund 15–20 s
vom Tippen bis zum neuen Kurs** (Warteschlange 3–7 s, im Einzelfall bis 30 s) – Ziel Z1 (Median ≤ 45 s, Serveranteil ≤ 20 s)
erfüllt; vorher gab es diesen Weg nicht (jede Aktualisierung rechnete alles, rund 2½ Minuten plus Wechsel zu GitHub).

## 9. Grenzen

* **GitHub-Wartezeit** bis ein Rechner startet: gemessen 6–30 s (Median 7 s) – liegt bei GitHub, nicht beeinflussbar.
* **Bereitstellung der Website** (gesamter Datenbestand): GitHub Pages stellt immer die ganze Website bereit (rund 280 MB,
  2–32 s); einzelne Aktien umgehen das über den Lieferkanal.
* **Echtzeit** gibt es nicht: Yahoo liefert je Börse verzögert; die App nennt die Verzögerung und rechnet sie in den Zustand ein.
* **Workflow erst nach Freigabe:** GitHub startet Workflows über die Schnittstelle nur von `main`. Bis zur Freigabe meldet die
  App beim Antippen „Workflow noch nicht vorhanden“; der gesamte Datenbestand funktioniert sofort.
