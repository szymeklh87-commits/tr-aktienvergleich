# „Jetzt aktualisieren“ aus der App, Kurszeiten und Tempo (ab 1.21)

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

| Umfang | Wo in der App | Weg | Ergebnis |
|---|---|---|---|
| Eine Aktie mit Tagesverlauf | Einzelansicht → „Kurs aktuell“ → **Jetzt aktualisieren** | Workflow „Kursaktualisierung“ | aktueller Kurs, Tagesverlauf in 5-Minuten-Schritten, Veränderung zum Vortag |
| Merkliste | Merkliste → **Jetzt aktualisieren** (auch unter ☰ → Jetzt aktualisieren) | Workflow „Kursaktualisierung“ | Kurs je Zeile; die ersten zehn (sichtbaren) Zeilen kommen zuerst |
| Depot | Musterdepots → gewähltes Depot → „Kurse dieses Depots aktuell“ | Workflow „Kursaktualisierung“ | Kurs je Depotaktie |
| Gesamter Datenbestand | ☰ → Jetzt aktualisieren → **Alles jetzt aktualisieren** | täglicher Lauf als Zwischenstand (wie bisher) | alle Ranglisten neu; der neue Stand erscheint automatisch |
| Automatisch | Einstellungen → „Automatisch aktualisieren“ | beides | neue Stände jede Minute geprüft, beim nächsten Seitenwechsel angezeigt; mit Zugang Kurse der sichtbaren Aktien und der Merkliste alle 15 Minuten (einstellbar 5–60, aus) – nur bei geöffneter App, während Börsen handeln, höchstens 6 je Stunde, Pause nach 10 Minuten ohne Bedienung |

Der Fortschritt steht direkt unter dem Knopf: „Anfrage wird gesendet“ → „Wartet auf einen GitHub-Rechner“ → „Kurse werden
abgerufen“ (mit dem Schritt des Laufs, z. B. „Schritt 5 von 6“) → „Teil 1 von 2 angekommen“ → „Kurse aktualisiert“ – mit
Laufzeit, Balken und Link zum Lauf auf GitHub. Fehler nennen den Grund (z. B. Zugang abgelaufen, Workflow noch nicht
freigegeben, Anfrage zu alt).

Ohne Zugang bleibt alles wie bisher: Läufe startest du auf GitHub („Run workflow“), die App wartet auf den neuen Stand.

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

## 4. Zugang, Rechte und Sicherheit

Der Zugang ist ein **feingranulares GitHub-Token**, das du selbst anlegst (Einstellungen → „Zugang für ‚Jetzt
aktualisieren‘“ → „Neues Token auf GitHub anlegen“; die Vorlage füllt Name, Beschreibung und das Recht vor –
[Vorlagenadressen laut GitHub-Changelog vom 26.08.2025](https://github.blog/changelog/2025-08-26-template-urls-for-fine-grained-pats-and-updated-permissions-ui)):

* Repository-Zugriff: **nur** `tr-aktienvergleich`; Recht: **nur „Actions: Read and write“** (Metadata „Read“ setzt GitHub dazu).
* Laut [GitHub-Dokumentation](https://docs.github.com/enterprise-cloud@latest//rest/actions/workflows) braucht „Create a workflow
  dispatch event“ genau dieses Recht; dasselbe Recht erlaubt auch „Enable/Disable a workflow“, Läufe abbrechen, wiederholen und
  löschen. **Nicht** erlaubt: Code und Workflow-Dateien ändern, Secrets lesen, Release-Assets (Datenstand) ändern, Einstellungen.
  Die App prüft beim Speichern, ob das Token Secrets lesen kann, und warnt dann („zu weitreichend“).
* Gespeichert wird das Token nur auf dem Gerät, verschlüsselt mit dem Datenschlüssel (AES-256-GCM, IndexedDB); gesperrt
  (Schlüssel vergessen) ist es nicht nutzbar. Es steht nie in einer Adresse, im Service-Worker-Cache, in einer Sicherungsdatei
  oder einem Protokoll. Die GitHub-Schnittstelle erlaubt Aufrufe aus dem Browser
  ([CORS laut GitHub](https://docs.github.com/en/rest/using-the-rest-api/using-cors-and-jsonp-to-make-cross-origin-requests)).
* Widerruf: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Delete. Ablauf empfohlen
  nach 90 Tagen; danach in der App ein neues eintragen.
* Frühere Regel „keine Schlüssel im Browser“: Die App selbst enthält weiterhin keinen Schlüssel. Der Zugang ist dein eigenes,
  freiwillig hinterlegtes, eng begrenztes Token; der AktienPilot-Auftrag sieht einen solchen geschützt gespeicherten Zugang auf
  dem Handy ausdrücklich vor (Abschnitt 4).

## 5. Kosten (Nullbudget)

| Dienst | Nutzung | Kosten | Grenze und Verhalten |
|---|---|---|---|
| GitHub Actions (öffentliches Repository, Standard-Runner) | Lauf „Kursaktualisierung“ (etwa 20–40 s je Anfrage) | 0 € – für öffentliche Repositorys kostenlos | Automatik höchstens 6 je Stunde und nur bei Nutzung; gleichzeitige Läufe stehen in einer eigenen Warteschlange |
| GitHub REST API | Lauf starten, Fortschritt, Lieferung laden | 0 € | 5.000 Anfragen je Stunde mit Token; eine Aktualisierung braucht etwa 20–40; bei erreichtem Limit meldet die App „Abfragelimit erreicht“ und versucht es später |
| GitHub-Repository (Branch „kurse-aktuell“) | Lieferungen der letzten zwei Tage | 0 € | ein Commit ohne Verlauf – wächst nicht |
| Yahoo Finance | Kurse wie bisher | 0 € | Daten „nur zur Information“, je Börse verzögert; ein Abruf je Anfrage (bis 150 Werte), Tagesverlauf nur für eine Aktie |

## 6. Geschwindigkeitsziele (festgelegt am 31.10.2026)

| Ziel | Messgröße | Wert |
|---|---|---|
| Z1 | Eine Aktie, Merkliste oder Depot (bis 50 Aktien): Tippen bis zum angezeigten neuen Kurs | Median ≤ 45 s; Serveranteil ohne GitHub-Wartezeit ≤ 20 s |
| Z2 | Gesamter Datenbestand (Zwischenstand): Tippen bis neue Daten in der App | ohne Wechsel zu GitHub; Median ≤ 150 s (vorher: etwa 2½–3 Minuten **plus** Wechsel zu GitHub und zwei Tipps dort) |
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

(wird mit den Messläufen ergänzt)

## 9. Grenzen

* **GitHub-Wartezeit** bis ein Rechner startet: gemessen 6–30 s (Median 7 s) – liegt bei GitHub, nicht beeinflussbar.
* **Bereitstellung der Website** (gesamter Datenbestand): GitHub Pages stellt immer die ganze Website bereit (rund 280 MB,
  2–32 s); einzelne Aktien umgehen das über den Lieferkanal.
* **Echtzeit** gibt es nicht: Yahoo liefert je Börse verzögert; die App nennt die Verzögerung und rechnet sie in den Zustand ein.
* **Workflow erst nach Freigabe:** GitHub startet Workflows über die Schnittstelle nur von `main`. Bis zur Freigabe meldet die
  App beim Antippen „Workflow noch nicht vorhanden“; der gesamte Datenbestand funktioniert sofort.
