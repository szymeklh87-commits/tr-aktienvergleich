# Änderungsprotokoll

Format: Version, Datum, Änderung, Begründung. Methodenänderungen (Fensterdefinition, Mindestbeobachtungen, Bereinigung, Perzentile, Gleichstandsregeln) erhöhen zusätzlich `methode_version` in `config/methode.yaml`. Veröffentlichte Datenstände tragen ihre Versionen und werden nie nachträglich verändert.

## 1.18.0 – 24.10.2026 (Gleichstand exakt – tr-methode-1.10.0; fehlende Kurstage verständlich gekennzeichnet)

Deine Entscheidungen vom 24.10. (16:00 Uhr): Gleichstände korrekt behandeln – bei mathematisch gleichem Score die höhere
Rendite, dann die ISIN; keine Rundung entscheidet, nichts wird pauschal gerundet. Fehlende Kurstage: die Regel bleibt (ein
fehlender Tag zählt als fehlend, kein Ersatzkurs, nicht null), unzureichende Daten verständlich kennzeichnen. Beides mit
unabhängig nachgerechneten Referenzfällen absichern, Platz 1 und die Top 10 besonders prüfen, die Wirkung dokumentieren,
die Methodenversion erhöhen, historische Stände unverändert lassen, veröffentlichen und die ausgelieferte Version prüfen.

**Versionen:** Server und App 1.18.0 · Methode **tr-methode-1.10.0** (Ranglistenversion `ranking-11w-v3`) · Datenformat
unverändert (drei zusätzliche Zähler im Methodenvergleich des Manifests). Stände bis 1.9.0 bleiben, wie sie berechnet wurden.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Gleichstand exakt** (`ranking-11w-v3`): Bei 10/90 … 90/10 vergleicht der Server den Score über die ganze Zahl K = w · (d_G − 2) + (100 − w) · (d_R − 2) aus den doppelten Durchschnittsrängen (= Score · 2 · (M − 1)). Rechnerisch gleiche Scores: höhere Kursrendite vorn, dann kleinere ISIN, als „gleichauf“ gekennzeichnet. Verschiedene Scores bleiben verschieden (kleinster Abstand 1 / (2 · (M − 1)), nichts wird gerundet). 0/100 und 100/0 unverändert | Gleitkomma-Score verglichen wie im Ausgangsmodell (`ranking-11w-v2`): bei rechnerisch gleichem Score entschied die letzte Binärstelle, kein „gleichauf“ | Deine Entscheidung; Methodik §7 und §15b |
| **App ordnet Untergruppen (Watchlist) genauso** (`exactScoreKey`) | Gleitkomma-Score | Gleiche Regel überall; Vertragstest gegen den Server |
| **Methodenvergleich jedes Laufs** rechnet die Vorversion mit deren Gleichstandsregel und zählt zusätzlich `top10_andere_aktien`, `top10_andere_reihenfolge`, `reihenfolge_geaendert`; die App zeigt die Zahlen unter Datenstand & Betrieb → Methodenwechsel | nur „anderer Spitzenreiter“ | Auftrag „Prüfe besonders Platz 1 und die Top 10 … dokumentiere die Auswirkungen“ |
| **Veröffentlichungsprüfung** `sortierregeln` prüft gemischte Gewichtungen mit dem exakten Schlüssel (Gruppe A und B) | Gleitkomma-Score | Sonst hätte die Prüfung die richtige Reihenfolge abgelehnt |
| **Unabhängige Nachrechnung versionsbewusst:** Stände ab `ranking-11w-v3` werden exakt geprüft; in älteren gilt die Gleitkomma-Reihenfolge als **bekannter Fehler** `gleichstand_rundung` (damaliges Verhalten bestätigt, fachlich falsch, keine Rechenabweichung); neue Prüfung `methodenwechsel_wirkung` zählt die Wirkung selbst und vergleicht mit dem Manifest | – | „Erhalte historische Stände unverändert“; bekannte Fehler dürfen nicht als korrekt gelten |
| **Frühere Stände:** Rechnet eine neue Methode einen Kurstag noch einmal, bleibt der Stand der alten Methode daneben erhalten | je Kurstag nur der neueste (ab 1.17.1) | Historische Stände bleiben sichtbar und unverändert („eingeschränkt vergleichbar“) |
| **Fehlende Kurstage verständlich:** Die Aktienseite nennt bei „Startkurs fehlt“ den Tag und bei „Zu viele Börsentage ohne Kurs“ die Zahlen des Zeitraums (Börsentage, Kurse, fehlende, Anteil, Regel); Statustexte 8, 11, 12 klarer; neue Begriffe „Gleichstand“ und „Fehlende Kurstage“ in der Hilfe | „Zu viele fehlende Sitzungen“ mit allgemeinem Text | Deine Entscheidung „kennzeichne unzureichende Daten verständlich“; Regel selbst unverändert |
| **Top 3 nach Zahlen: Punkte ohne Rundungsfehler** – Teilpunkte in ganzen Zehnteln summiert | Gleitkommasumme: z. B. 0,1 + 5,6 + 0,3 + 0,5 = 6,4999… → 6 statt 7 Punkte (in 0,2 % der geprüften Kombinationen) | „Verhindere, dass Rundungsfehler die Reihenfolge bestimmen“; Regel der Top 3 sonst unverändert |
| **Referenzfälle Gleichstand** (`tests/unit/test_referenz_gleichstand.py`, 11 Tests; Erwartung mit exakten Brüchen, unabhängig vom Rechenkern): Platz 1, Grenze der ersten 10, gleicher Score und gleiche Rendite, kleinster Abstand, 60 Zufallsuniversen, Veröffentlichungsprüfung, Methodenvergleich; App: `app/tests/gleichstand.test.ts`; Referenzfall fehlende Kurstage (25 Tage, 50/50) jetzt D, A, J | – | Auftrag; **Gegenprobe:** mit Gleitkomma-Vergleich 15, mit auf eine Stelle gerundetem Score 2, mit „ISIN statt Rendite“ 22 fehlschlagende Prüfungen |
| **Prüffall 13.10. (Rechendaten des Ausgangsmodells) mit beiden Regeln:** alte Regel 1.971 von 1.980 Ranglisten gleich (wie bisher); exakte Regel: Platz 1 in 4 und die ersten 10 in 61 von 1.980 Ranglisten anders, alle Unterschiede innerhalb rechnerisch gleicher Scores | nur alte Regel | Bewusste Abweichung vom Ausgangsmodell sichtbar machen (`tests/live/ausgangsmodell_nachrechnen.py`) |

## 1.17.1 – 24.10.2026 (Betriebsprüfungen: fehlende Kurstage, Android-Installation, Kontrolle des ersten Kurslaufs)

Dein Auftrag vom 24.10. (14:15 Uhr): die verbleibenden Betriebsprüfungen abschließen, die tatsächliche Android-Installation
prüfen, die Behandlung fehlender Kurstage mit nachvollziehbaren Referenztests absichern und ihren Einfluss auf die
Ranglisten dokumentieren, die Kontrolle des ersten zeitgesteuerten vollständigen Kurslaufs vorbereiten, gefundene Fehler
beheben.

**Versionen:** Server 1.17.1 · App unverändert `1.17.0+7d871934` · Methode unverändert `tr-methode-1.9.0` – Renditen,
Ranglisten und Datenformat wie in 1.17.0.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Dieselbe TR-Liste in anderer Datei rechnet nichts neu:** Liefert Trade Republic dieselbe Liste (gleiche ISINs, Namen, Gültigkeit) als andere PDF-Datei, bleibt die bisherige Liste gültig; ein Stand, der mit der anderen Fassung gerechnet wurde, gilt ebenso | Jede neue Dateifassung galt als neue Liste – der Lauf rechnete denselben Stichtag noch einmal und veröffentlichte ihn erneut: am 23.10. dreimal den 22.10. (Läufe 09:44, 10:31 und 12:29 UTC), am 24.10. zweimal den 23.10. (09:17 und 11:41 UTC); die Liste kam dabei mit „+0 / −0“ in wechselnden Dateifassungen | Gefunden bei der Kontrolle der Läufe vom 23. und 24.10.; ohne Korrektur hätte ab Montag oft ein Morgenlauf den Stand der Nacht ein zweites Mal gerechnet. Integrationstest mit Gegenprobe (ohne die Korrektur: neu veröffentlicht) |
| **Frühere Stände: je Kurstag einer** – die Website hält die drei neuesten Kurstage (je Tag die neueste Fassung, Zwischenstand als eigene Art) | Die drei neuesten Fassungen, auch vom selben Tag: am 24.10. zweimal der 23.10., dafür fehlte der 21.10. | „Frühere Stände“ soll ältere Tage zeigen, nicht zwei Fassungen desselben Tages |
| **Referenzfälle für fehlende Kurstage** (`tests/unit/test_referenz_fehlende_kurstage.py`, Beschreibung [12_Fehlende_Kurstage](docs/12_Fehlende_Kurstage.md)): zehn Fälle durch den ganzen Rechenkern – keine Zeile, Leerzeile, vier und fünf Lücken (Grenze 20 %), Starttag ohne Kurs, Stichtag ohne Kurs (letzter Schlusskurs), zwei verpasste Sitzungen, Feiertag, kurzer Zeitraum mit einer Lücke –, Erwartung unabhängig mit exakten Brüchen, dazu Ranglisten in fünf Gewichtungen | Die Regeln waren einzeln getestet, aber nicht als zusammenhängender, von Hand nachvollziehbarer Fall | Auftrag; Gegenprobe: mit 19 statt 20 % bzw. „Leerzeile schließt aus“ schlagen die passenden Fälle fehl |
| **Einfluss fehlender Kurstage gemessen** (Workflow „Fehlende Kurstage auswerten“, nur Zählwerte): Stand 23.10.: 2.864 von 856.002 Aktie-Zeitraum-Paaren mit Lücke (0,33 %), keine Aktie mit Lücke auf einem Platz 1, 14 Leerzeilen bei 8 Aktien; nach anderen Regeln 7–9 von 1.980 Ranglisten mit anderem Platz 1 – alle durch einen rechnerischen Gleichstand an der Spitze | – | Auftrag „Dokumentiere ihren Einfluss auf Ranglisten“ ([12](docs/12_Fehlende_Kurstage.md), Abschnitt 5) |
| **Gleichstand dokumentiert:** Rechnerisch gleiche Scores entscheidet wie im Ausgangsmodell die letzte Binärstelle, nicht die Rendite (Stand 23.10.: in 336 von 1.314 gemischten Ranglisten unter den ersten 11; mit exaktem Vergleich wäre Platz 1 in 4 Ranglisten anders) | in der Methodik nicht beschrieben | Gefunden mit den Referenzfällen; bleibt bis zu deiner Entscheidung wie im Ausgangsmodell (Prüffall: 1.272 von 1.278 gemischten Ranglisten gleich, mit exaktem Vergleich keine) |
| **Kurslauf kontrollieren** (Workflow, nur von Hand, ohne Secrets; `ops/kurslauf_kontrolle.py`): prüft jeden offiziellen Lauf ab einem Tag gegen feste Kriterien und nennt den ersten zeitgesteuerten Lauf mit Abruf aller Notierungen | Kontrolle nur von Hand in den Laufprotokollen | Auftrag „Bereite die Kontrolle des ersten zeitgesteuerten vollständigen Kurslaufs vor“; bewusst ohne Änderung an `taeglich.yml` (Zeitplan-Eigentümer) |
| **Android-Emulator: echte Installation** (`tests/live/android_install.py`): veröffentlichte Website über Chromes Menü und alle Dialoge installieren, Symbol auf dem Startbildschirm antippen, Start im eigenen Fenster ohne Adressleiste prüfen, im Flugmodus neu starten; **TalkBack** (`tests/live/android_talkback.py`): einschalten, Vorlese-Baum und Chromes Barrierefreiheits-Baum in vier Ansichten | Nur die Installierbarkeit abgefragt; TalkBack nicht benutzt | Auftrag „Prüfe insbesondere die tatsächliche Android-Installation“; Ergebnis 24.10., 15:35 Uhr: installiert (im Emulator als Web-App-Verknüpfung, kein WebAPK ohne Google-Konto), Start und Offline-Start bestanden, keine bedienbaren Elemente ohne Namen |

**Geprüft:** alle Tests (Python 541 in GitHub „Prüfung“, App unverändert 98), Referenzfälle mit Gegenprobe, Einfluss mit echten Daten (Workflow „Fehlende Kurstage auswerten“), Kontrolle an echten Läufen, Android-Emulator mit echter Installation und TalkBack – Einzelheiten im Testbericht (07), offene Punkte in 09.

## 1.17.0 – 24.10.2026 (Fertigstellung: schnellerer Kursabruf, Nachtlauf, verständliche Angaben, geprüfter Prüffall)

Deine Aufträge vom 24.10. (09:46 und 10:04 Uhr): die App vollständig fertigstellen – Kursabruf beschleunigen, automatische Aktualisierung zuverlässig machen, die Nachprüfung fachlich richtig abschließen, das historische Archiv suchen, Texte, Navigation, Tabellen, Bildschirmtastatur und Updates verbessern, vollständig testen (auch Android) und veröffentlichen.

**Versionen:** Software und App 1.17.0 · Methode unverändert `tr-methode-1.9.0` – alle Zahlen wie in 1.16, kein neues Datenformat (nur zwei zusätzliche Angaben in `status.json`).

| Änderung | Vorher | Begründung |
|---|---|---|
| **Kursabruf schneller:** dieselben Chart-Abrufe wie bisher, aber 4 gleichzeitig, abwechselnd über die Yahoo-Hosts query2 und query1 (je Host höchstens 4 Abrufe je Sekunde; `abruf.chart_gleichzeitig: 4`). **Gemessen** am 24.10.2026, 12:44–13:11 Uhr (Messlauf mit den echten Kursen, nur lesend): 10.845 Notierungen gleichzeitig in 22,6 Minuten (8,00 je Sekunde, ohne Drosselung (0 × HTTP 429)), hochgerechnet auf alle 11.145: **23,2 Minuten**; nacheinander wie bis 1.16 2,51 je Sekunde, hochgerechnet 74,0 Minuten. Dieselben Daten: Beide Hosts lieferten in einer Stichprobe von 200 Notierungen Feld für Feld bitgleiche Kurse und Umsätze; gegen den gespeicherten Stand (rund eine Stunde älter) waren von den älteren Tagen 95.626 von 95.628 Schlusskursen und 95.627 von 95.628 Umsätzen bitgleich, vom letzten Tag 11.001 von 11.002 Schlusskursen; den Umsatz des letzten Tages hatte der Anbieter bei 138 Notierungen inzwischen geändert (deshalb holt der Lauf die letzten zehn Tage jedes Mal neu). Bei einer Drosselung (HTTP 429) holt der Lauf den Rest automatisch nacheinander wie bis 1.16 | Ein Abruf nach dem anderen, 2,5 je Sekunde; Lauf mit neuen Schlusskursen 80–115 Minuten | Auftrag: „Kursabruf beschleunigen … Miss die tatsächliche Laufzeit.“ Im täglichen Lauf bisher nur für 51 Notierungen (Prüflauf vom 24.10.: 8,1 je Sekunde); für alle erstmals mit dem nächsten neuen Börsentag (Nachtlauf 26.10.) |
| **Sammelabruf geprüft und verworfen:** Vergleich mit echten Daten (11.145 Notierungen): Schlusskurse aus „spark“ an 212.619 von 213.840 Tagen bis auf Rundung gleich, aber ohne Umsatz und ohne Tage ohne Handel, Umsatz aus „quote“ bei 30 von 406 Stichproben um mehr als 20 % anders | Idee aus dem Rechercheauftrag (rechnerisch vier Minuten) | Nicht gleichwertig – andere Umsätze hätten Gruppe B und Volumen-Signale verändert; Code bleibt abgeschaltet (04_Datenquellen) |
| **Nachtlauf** (Workflow „Nachtlauf“, Mo–Fr 22:37 UTC = 00:37 Uhr Sommerzeit / 23:37 Uhr Winterzeit) startet den täglichen Lauf nach dem letzten Börsenschluss; die Läufe um 07:00–09:00 Uhr bleiben als Auffangnetz. Mit deinem Konto aktiviert (per Schnittstelle, wie am 14.10.) | Erster Lauf des Tages ab 07:00 geplant, gestartet 15.–24.10. zwischen 11:00 und 12:30 Uhr (meist vor 12 Uhr), neuer Stand zwischen 12:40 und 13:45 Uhr (16.–24.10.) | Neue Schlusskurse am frühen Morgen statt mittags – auch mit GitHubs Verzögerung |
| **Externer Auslöser (optional)** vorbereitet: Google-Apps-Script zum pünktlichen Start des Nachtlaufs; Token nur in den Skripteigenschaften, keine Fehler-E-Mails (auch ohne Netz keine Ausnahme), Grund und nächster Schritt je Antwort von GitHub im Protokoll, Token nie; Schritt-für-Schritt-Anleitung; 7 Tests mit nachgebildeten Google-Diensten | – | Pünktlich ohne GitHubs Zeitplan, falls gewünscht (02_Einrichtung) |
| **Aktualität in der App:** unter dem Kursstand „Neue Schlusskurse (Montag, 26. Oktober) gibt es ab … Geplant: Nachtlauf …; fällt er aus, Morgenlauf …“ – nur Läufe, die den nächsten Stand bringen können; Hinweise **„Neuer Kursstand überfällig“** und **„Letzte Aktualisierung fehlgeschlagen“** mit Grund in Alltagssprache und nächstem Schritt; unter Datenstand & Betrieb „Wie aktuell sind die Daten?“ | „nächster Lauf geplant ab 07:00 Uhr“; Fehler nur als Status-Wort | Auftrag: „Datenstand und Aktualisierungsfehler verständlich anzeigen“ |
| **Nächster Kursstand bleibt in `status.json`** – auch nach dem Job „Kennzahlen“ und nach „Nur die Website“ (der Wert steht ab 1.17 zusätzlich in der Datenbank); ein überholter Wert entfällt | Die Statusdatei dieser Schritte entsteht auf einem frischen Rechner, der den Wert nicht kannte – laut Code fehlte er deshalb nach jedem Tageslauf mit Kennzahlen, sichtbar am 24.10. nach „Nur die Website“; die App konnte dann weder „Neue Schlusskurse gibt es ab …“ noch „Neuer Kursstand überfällig“ zeigen | Gefunden bei der Endkontrolle der veröffentlichten `status.json` (24.10., 13:30 Uhr); **im Betrieb bestätigt** mit einem Tageslauf von Hand (24.10., 13:41–14:04 Uhr): Auch die Statusdatei des Jobs „Kennzahlen“ nennt jetzt den nächsten Kursstand (26.10. ab 22:00 UTC) |
| **Erklärung an Ort und Stelle** in allen Listen (Rangliste, Rendite, Leiter, Potenzial, Top, Sieger, Häufigkeit, Matrix, Bericht, Raster, Depots, Umschichtung, Abdeckung, Watchlist, Gewichtungsvergleich, Analyse): Kennzeichen der **Art der Angaben**, „Was du siehst“, „Was du hier tun kannst“, aufklappbar „So liest du die Zahlen“ mit Bedeutung jeder Zahl, Rechenweg und Rechenbeispiel | Einleitungstext, auf dem Handy auf drei Zeilen gekürzt | Auftrag: „Was sehe ich? Was bedeutet die Zahl? Wie entsteht das Ergebnis? Was kann ich hier tun?“ |
| **Vier Arten von Angaben** sichtbar getrennt – Rückblick, Rangbewertung, Prognose Dritter (gestrichelt), Angaben Dritter (gepunktet) – an jedem Abschnitt der Einzelansicht, an den Top 3, in der Methodik (eigener Abschnitt) und als vier neue Begriffe der Hilfe | Unterschied nur im Fließtext | „Historische Ergebnisse, Rangbewertungen und Prognosen eindeutig unterscheiden“ |
| **Große Schrift:** keine seitliche Verschiebung und kein abgeschnittener Text mehr – geprüft in 21 Ansichten bei 384 px Breite mit 130, 150 und 175 % Schriftgröße, bei 360 px mit 150 % und bei 320 px mit 130 % (Browser-Simulation); Kopfzeile zweizeilig statt „…“, Kacheln untereinander, Zahlen und Knöpfe brechen um | Bei 150 % in 4 Ansichten seitlich verschoben, Titel und Punkte-Teile abgeschnitten | Auftrag: „größere Schrift, keine abgeschnittenen Inhalte“ |
| **Bildschirmtastatur:** Die Leiste unten verschwindet nur, wenn der Browser die Seite beim Tippen wirklich verkleinert (Chrome auf Android legt die Tastatur über die Seite – dann bleibt alles, wie es ist), und kommt erst kurz nach dem Schließen der Tastatur zurück; das Querformat-Layout springt bei offener Tastatur nicht mehr an | Keine eigene Behandlung der Bildschirmtastatur. Die erste Fassung dafür blendete die Leiste bei jedem Fokus aus – ein Tipp auf „Übernehmen“ oder „Filter löschen“ konnte dann auf der wieder erscheinenden Leiste landen (im Browser-Test gefunden, vor der Veröffentlichung geändert) | Keine versehentlichen Aktionen |
| **Updates:** Das Web-App-Manifest wird immer zuerst vom Server geholt (offline aus dem Zwischenspeicher) | Manifest aus dem Zwischenspeicher | Name und Symbole einer neuen Version kommen sicher an |
| **Nachrechnung versionsbewusst:** Der alte Stand vom 13.10. (Software 1.6.0) wird nach seiner damaligen Version beurteilt – 2 Fälle eines bekannten, in 1.13 behobenen Anzeigefehlers als Warnung „damaliges Verhalten bestätigt, fachlich falsch“, keine Ausnahme ohne Bedingung; **17 unabhängige Referenzfälle** mit von Hand nachgerechneten Ergebnissen | Job seit 14.10. rot („2 Abweichungen“) | Bekannte Fehler gelten nicht als korrekt, nur weil Vergleichswerte passen |
| **Prüffall Ausgangsmodell nachgerechnet** (Stichtag 13.10.) mit dessen eigenen Kursreihen aus deiner HTML-Übersicht: Startdaten, Renditen und R² deckungsgleich, Aufnahme in V/U in 580.561 Paaren gleich (mehr bewertet nur 3.121 Paare mit Split im Zeitraum – die Übersicht enthält keine Split-Termine – und 148 mit Leerzeile), Ø Tagesumsatz nach derselben Regel (in USD genau gleich, sonst je Währung nur der Wechselkurs als Faktor); Ranglisten 1.971 von 1.980 gleich (Rest Rundung der Übersicht), ganze Kette 1.579 von 1.980, jede übrige Abweichung erklärt; einzige Regelabweichung: Leerzeilen des Kursanbieters | „nicht durchgeführt – Archiv fehlt“ | Archiv-ZIP nicht auffindbar, aber die Rechendaten stecken in der HTML-Datei (03_Methodik §14) |
| **Android-Emulator-Prüfung** (Workflow „Android-Emulator prüfen“, nur DEMO-Daten): Chrome 124 auf Android 15 im S25+-Format – installierbar ohne Hindernisse, nach Neustart ohne Netz der gespeicherte Stand, keine seitliche Verschiebung hoch und quer (die Systemschriftgröße von Android wirkte im Emulator nicht auf die Seite), Bildschirmtastatur verdeckt das Suchfeld nicht; meldet auch, was das Abbild mitbringt (TalkBack ja, Samsung Internet nein) | Nur Chromium unter Linux | Auftrag: „Android-Testmöglichkeiten nutzen, Emulator und Gerät unterscheiden“ |

**Geschwindigkeit:** Kursabruf siehe erste Zeile. App: Programmpaket 248 → 255 KB übertragen (gzip; +7 KB für die Erklärungen), Stildatei 16,2 → 16,8 KB. Live mit echten Daten (Chromium im S25+-Format, 13:09 Uhr): geöffnet 0,2 s, entsperrt bis zur fertigen Startseite 0,4 s, erneut geöffnet 0,6 s – wie 1.16.0 am selben Vormittag; Einzelansicht nach dem Antippen 0,1 s.

**Geprüft:** alle Tests (Python 526, App 98), Android-Emulator, große Schrift, Live-App mit echten Daten und Nachrechnung, dazu ein täglicher Lauf mit 1.17.0 im Betrieb (Stand 23.10. neu gerechnet: 24 von 24 Ansichten ohne Fehler, Nachrechnung 0 Abweichungen) – Einzelheiten und Grenzen im Testbericht (07) und in den Lücken (09).

## 1.16.0 – 24.10.2026 (Verständlicher, robuster, einfacher zu bedienen)

Dein Auftrag vom 24.10.: die App gründlich prüfen und so verbessern, dass **auch jemand ohne Vorwissen** versteht, wofür sie gedacht ist, was einzugeben ist und wie die Ergebnisse zu lesen sind – mit Fehlerfällen, einfachen Texten, Geschwindigkeit, Stabilität und einer installierbaren Testversion.

**Versionen:** Software und App 1.16.0 · Methode unverändert `tr-methode-1.9.0` – alle Zahlen wie in 1.15, kein neues Datenformat.

**Vorgehen:** Rundgang durch alle 26 Ansichten als neuer Nutzer (DEMO, S25+-Format) und 18 Fehlerfälle im Browser: leere und falsche Passphrase, Speicher gesperrt (Inkognito), offline, fehlende und beschädigte Dateien, Serverfehler, unbekannte Adressen und ISINs, falsche Eingaben in Watchlist, Depot, Zeitraum und Einstellungen, Abbrechen, Zurück. Gefunden wurden 14 Fehler, 7 Verständnis- und 2 Bedienprobleme (eines davon erst beim Prüfen der Installationsseite); alle sind behoben und mit Tests abgesichert.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Hilfe und Begriffe** (☰ und auf dem Sperrbildschirm): wofür die App ist, Erste Schritte, „So liest du eine Rangliste“ mit durchgerechnetem Beispiel (drei Aktien, Perzentile, Rangscore 60/40), welche Ansicht welche Frage beantwortet, **26 Begriffe von A bis Z** mit Beispiel und Suche, häufige Fragen, was bei Meldungen zu tun ist | Erklärungen verstreut, Fachwörter wie Rangscore, R², Perzentil, Gruppe A/B ohne Beispiel | Auch ohne Vorwissen verständlich |
| **Kurzerklärung beim ersten Start** („Neu hier? So funktioniert die App“, mit „Verstanden“ dauerhaft ausgeblendet); Hilfe-Link am Ende der Startseite | Kein Hinweis, wofür die App da ist | Zweck, Eingabe und Ergebnis auf einen Blick |
| **Sperrbildschirm neu:** Zweck der App, drei Schritte, Fehler direkt am Feld mit nächstem Schritt, Eingabe bleibt zum Korrigieren; Leerzeichen am Ende (Handy-Tastatur) entsperrt trotzdem; Leiste unten und Menü gesperrt nur mit Hilfe und Installieren | „Zugangsschlüssel eingeben“ mit Verweis auf „GitHub-Secret DATA_PASSPHRASE“; jeder Fehler hieß „passt nicht“ | Begriffe einheitlich („Passphrase“), keine Sackgassen |
| **Fehlermeldungen mit Ursache und nächstem Schritt** und „Erneut versuchen“: „Keine Internetverbindung“, „Server antwortet nicht“, „Datei nicht gefunden“, „Daten nicht lesbar“; die technische Angabe steht klein darunter | Dateipfade („snapshots/…/manifest.bin“), „Unbekanntes Dateiformat“, englische Browsermeldung; Serverfehler 500 wurde als „offline“ gemeldet | Gefunden im Fehlerfall-Test |
| **Fehlt eine Datei des Stands** (meist gerade ersetzt), lädt die App einmal selbst den neuesten Stand | Fehlermeldung | Robuster beim Veröffentlichen |
| **Passphrase nicht speicherbar** (z. B. Inkognito): App entsperrt trotzdem und sagt, dass sie beim nächsten Mal wieder fragt | Still – beim nächsten Öffnen kam unerwartet wieder der Sperrbildschirm | Ehrliche Rückmeldung |
| **Seite nicht gefunden / Keine gültige ISIN / Aktie nicht in diesem Datenstand** mit Knöpfen „Aktie suchen“ (ISIN schon eingetragen) und „Zur Startseite“; unbekannte ISIN fragt keine Datei mehr ab | Nur ein Satz, bei leerer ISIN unvollständig | Nächster Schritt statt Sackgasse |
| **Aktien suchen:** Suchfeld oben, Treffer schon beim Tippen, „Keine Aktie passt zu …“ mit Tipp | Suche ganz unten, Treffer erst nach Enter oder Verlassen des Felds | Häufigste Aufgabe zuerst |
| **Startkapital im Musterdepot:** frei tippen (auch leeren, „2.500“ oder „1.000,50“), Hinweis bei ungültigem Betrag, der letzte gültige Betrag bleibt | Feld ließ sich nicht leeren, falsche Werte sprangen still zurück | Gefunden im Fehlerfall-Test |
| **Freier Zeitraum:** bei 0, 91 oder Kommazahlen steht, was erlaubt ist und was gewählt wurde | Still auf 1 bzw. 90 gesetzt | Rückmeldung statt Rätsel |
| **Einstellungen:** Rückmeldung direkt unter der Aktion; „Schlüssel vergessen“ fragt vorher; falsche Datei: „keine Sicherung dieser App“ mit Hinweis auf die richtige Datei; dieselbe Datei lässt sich erneut wählen | Rückmeldung oben außer Sicht, Schlüssel ohne Rückfrage gelöscht, englische JSON-Meldung | Gefunden im Fehlerfall-Test |
| **Ranglisten:** Einleitung in kurzen Sätzen („So gehst du vor“) und über der Liste „Rechts in jeder Zeile: Prozentzahl, Rangscore, R²“ mit ⓘ und Beispiel | Zahlen ohne Erklärung an der Zeile | Ergebnisse lesbar |
| **Einfachere Texte** in Start, Rendite, Potenzial, Aktien, Depots („Rückblick-Rechnung“), Watchlist, Top nach Zahlen, Bericht, Matrix, Häufigste, Sieger, Raster, Umschichtungs-Regel, Datenstand und Methodik („Kurz gesagt“) | Lange Sätze mit Fachwörtern | Einfache Sprache; ein Test sichert: kein Satz der Begriffe länger als 30 Wörter |
| **Ehrliche Zeitangabe:** „geplant ab 7 Uhr, GitHub startet geplante Läufe oft einige Stunden später – zuletzt um … statt …“ | „täglich um 07:00 Uhr“, „jeden Morgen“ | Gemessen 15.–23.10.: erster Lauf meist zwischen 11 und 12 Uhr |
| Fenstertitel der Startseite „TR-Aktienvergleich“ | „TR-Aktienvergleich – TR-Aktienvergleich“ | Kleiner Fehler |
| Hinweis „Keine aktuelle Prüfung“: „Der tägliche Lauf hat sich zuletzt vor 11 Tagen erfolgreich gemeldet … Neu starten kannst du ihn unter ☰ → Jetzt aktualisieren.“ | „… hat sich seit vor 11 Tagen nicht erfolgreich gemeldet“ (falsches Deutsch, kein nächster Schritt) | Gefunden beim Prüfen der Installationsseite |
| **Installation wirklich geprüft:** Browser-Test und Live-Prüfung lassen Chrome die App auf Installierbarkeit prüfen, installieren sie als Web-App und starten sie (erster Start mit Passphrase) | Nur Manifest und Service Worker vorhanden | Auftrag: „tatsächliche Installation prüfen“ |

**Geschwindigkeit:** Start bis zum ersten Bild mit 4-fach gedrosseltem Prozessor (Median aus 7 Läufen, DEMO): Skriptzeit 0,29 s (1.15) → 0,28 s (1.16); bis die Seite sichtbar ist 0,68 s → 0,79 s, weil der Sperrbildschirm jetzt mehr Text zeigt (auf dem S25+ ohne Drosselung etwa ein Viertel davon). Das App-Paket wächst um 43 KB (Hilfetexte). Aufteilen in Teile hätte höchstens 0,1 s gespart (gedrosselt) und wurde deshalb nicht gemacht. Der eigentliche Engpass liegt auf dem Server: Der tägliche Lauf holt die Kurse aller rund 11.000 Notierungen einzeln mit höchstens 2,5 Abrufen je Sekunde (gut 70 Minuten); schneller abrufen ginge nur mit dem Risiko, vom Kursanbieter gedrosselt zu werden – unverändert, siehe 09_Bekannte_Luecken.

## 1.15.0 – 14.10.2026 (Schneller und übersichtlicher)

Deine Auswahl vom 14.10. (16:30 Uhr, „App optimieren“): **„Schneller“** und **„Übersichtlicher“** – die beiden übrigen deiner vier Punkte („Aussagekräftiger“ und „Musterdepots vollständig“ kamen mit 1.14).

**Versionen:** Software und App 1.15.0 · Methode unverändert `tr-methode-1.9.0` – alle Zahlen wie in 1.14. Neu im Datenstand ist nur die Datei `pruefsummen.bin` (siehe unten).

**Messung vorher:** Die Live-Prüfung meldete „Entsperren 5 s, Top-Seite 3,3 s, Einzelansicht 3,1 s“. Darin steckten feste Pausen der Prüfung selbst (1,5 s vor dem Entsperren, je 1 s Ruhezeit nach jeder Ansicht, bei der Einzelansicht drei davon). Mit echter App-Zeit gemessen (Live-Prüfung 17:27 Uhr, App 1.14, echte Daten): Entsperren bis zur fertigen Startseite **1,5 s**, erneut öffnen **0,7 s**, Top-Seite und Einzelansicht **0,1 s** nach dem Antippen, alle 23 Ansichten **unter 0,7 s**. Beschleunigt wurde deshalb vor allem der Start.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Kerndaten im Voraus laden:** Manifest, Aktienliste, Übersicht, Häufigkeit, Rangliste des gewählten Zeitraums und Signal-Stand werden gleichzeitig geladen – schon während du die Passphrase tippst | Erst Manifest und Aktienliste, danach der Rest; vor dem Entsperren nichts | Netz und Tippen laufen parallel |
| **Manifest 50-mal kleiner:** die Prüfsummen aller rund 11.000 Dateien stehen in einer eigenen Datei `pruefsummen.bin`, die nur die Nachrechnung braucht (das Manifest verankert sie über ihre Prüfsumme) | Gut 0,5 MB bei jedem Start, die die App nie las | Weniger laden und entschlüsseln |
| **Kein Neuladen beim ersten Besuch:** der Service Worker übernimmt die Seite ohne Neustart (nur nach einer App-Aktualisierung wird neu geladen) | Die App lud sich beim ersten Öffnen einmal neu – eine schon getippte Passphrase ging verloren | Gefunden bei der Live-Prüfung |
| Suchindex erst auf der Seite „Alle Aktien“, Signal-Index einmal je Signal-Stand | Bei jedem Start bzw. in jeder Ansicht neu für rund 11.000 Aktien | Weniger Rechenzeit beim Start |
| **Startseite übersichtlicher:** Top 3 → Kursstand in einer Zeile → Kandidaten (3 statt 5) → Bericht 1–30 → deine Rangliste mit Zeitraum, Gewichtung und den ersten fünf Plätzen in **einem** Abschnitt → Einstiege → **„Mehr auf einen Blick“** (aufklappbar: Sieger je Zeitraum, Rendite-Leiter, Höchstwert, Umschichtungs-Regel, Abdeckung) | Im DEMO 7.000 px lang (gut 8 Bildschirme), Auswahl und Rangliste getrennt | Wichtigste Zahlen zuerst; im DEMO jetzt 4.900 px |
| **Menü ☰ gestrafft:** oben die Ansichten (Aktualisieren, Top nach Zahlen, Bericht, Musterdepots, Watchlist), abgesetzt darunter die App (Datenstand, So wird gerechnet, Einstellungen, Installieren) | 11 Einträge in einer Liste, darunter doppelt „Kandidaten“ und „Analyse“ (stehen unten in der Leiste) | Weniger Suchen |
| **Sichern wiederholt** vorübergehende Fehler des Upload-Servers (HTTP 5xx, Verbindungsabbruch) bis zu viermal | Lauf 17:18 Uhr: „HTTP 502“ beim Sichern – die Website blieb deshalb unverändert, der Lauf war vergeblich | Die Bedingung „bereitgestellt wird nur nach erfolgreichem Sichern“ bleibt |
| **Live-Prüfung misst nur die App:** Zeit bis die Ansicht fertig ist, ohne Pausen der Prüfung; Entsperren wie bei der installierten App (nach Übernahme durch den Service Worker) | Siehe oben | Ehrliche Zahlen |

Gemessen in der Entwicklungsumgebung mit einem DEMO-Stand in voller Größe (10.817 Aktien, verschlüsselt), Handy-ähnlich gedrosselt (Prozessor 4-mal langsamer, Netz 12 Mbit/s mit 60 ms Verzögerung, 3 s Tippen der Passphrase), je zwei bis drei Läufe:

| Schritt | App 1.14 | App 1.15 |
|---|---|---|
| Entsperren bis fertige Startseite | 1,9–2,5 s | 1,4–1,5 s |
| Erneut öffnen bis fertige Startseite | 1,8–2,2 s | 1,2–1,4 s |
| Top nach Zahlen, Einzelansicht, Ranglisten | 0,2–0,4 s | 0,2–0,4 s (unverändert schnell) |

Im Betrieb mit echten Daten (Live-Prüfung, 14.10. 17:27 Uhr mit 1.14 und 17:45 Uhr mit 1.15): Entsperren bis zur fertigen Startseite **1,5 s → 0,3 s**, erneut öffnen 0,7 s → 0,6 s, alle 23 Ansichten ohne Fehler.

## 1.14.0 – 14.10.2026 (Alle Aktien bewertet, vollständige Musterdepots, Auffällige ausblendbar, Top 3 nur handelbar)

Deine Nachrichten vom 14.10.: 16:29 Uhr „Ja, wenn Kurse von heute fehlen von US-Börse, dann nimm von gestern. Alle Aktien sollen bewertet werden.“ – 16:30 Uhr „App optimieren.“ mit deiner Auswahl **„Aussagekräftiger“, „Schneller“, „Übersichtlicher“, „Musterdepots vollständig“**. Diese Version enthält die ersten drei Schritte (alle Aktien bewerten, Musterdepots, aussagekräftiger); „Schneller“ und „Übersichtlicher“ folgen als nächste Version.

**Versionen:** Software und App 1.14.0 · Methode **`tr-methode-1.9.0`** (vorher 1.8.0) – neu ist nur, welche Aktien ohne Schlusskurs am Stichtag mitzählen; alle übrigen Rechenregeln unverändert. Jeder Lauf vergleicht mit den Regeln von 1.8.0.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Alle Aktien bewertet (Methode 1.9.0):** Eine Aktie ohne Schlusskurs am Stichtag – Feiertag ihrer Börse oder Kurs nicht geliefert – zählt in **jedem Stand** mit ihrem letzten Schlusskurs, wenn ihre Börse seitdem höchstens eine Sitzung hatte. Ihre Zeiträume enden an diesem Tag (Zeile „Schlusskurs 12.10.“, Details und Export mit Ende je Aktie), die Werte sind Zahl für Zahl die eines Stands mit diesem Stichtag. Ältere Kurse (zwei oder mehr verpasste Sitzungen) gelten als veraltet. Im Zwischenstand zählen jetzt auch Aktien von Börsen mit Feiertag. Status-Seite: „Mit letztem Schlusskurs“ mit Anzahl; Teilstand-Hinweis entsprechend | Solche Aktien fehlten im Stand mit Schlusskursen („Kurs am Stichtag fehlt“, „Markt am Stichtag geschlossen“), im Zwischenstand bei Feiertagen | Dein Wunsch: alle Aktien bewerten, fehlende Kurse von gestern nehmen |
| **Musterdepots vollständig:** „10 Sieger“ hat immer zehn Positionen – haben weniger als zehn Aktien einen ersten Platz, füllen die nächsten nach Top-3-, dann Top-10-Nennungen auf (gekennzeichnet „Aufgefüllt – ohne ersten Platz“, mit Satz unter der Liste) | Bei wenigen Siegern (z. B. 4) hatte „10 Sieger“ nur 4 Positionen | Deine Wahl „Musterdepots vollständig“ |
| **Top 3 nur aus handelbaren Aktien:** Plätze in „Top nach Zahlen“ – und damit die Top 3 – bekommen nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD (Gruppe B); wenig gehandelte zeigen ihre Punkte ohne Platz („–“), einblendbar mit „Auch wenig gehandelte Aktien zeigen“. „Deine Aktien“: Platz nur unter den handelbaren | Alle Aktien mit Top-10-Nennung konkurrierten um die Top 3, auch Kleinstwerte | Deine Wahl „Aussagekräftiger“: ein Kauf zum angezeigten Kurs ist bei wenig gehandelten Aktien oft nicht möglich |
| **Auffällige kennzeichnen und ausblenden:** Kennzeichen **„Kaum Umsatz“** (Ø unter 1 Mio. USD am Tag) und **„Einzelsprung“** (ein Handelstag erklärt mehr als die Hälfte der Kursbewegung) in allen Ranglisten; Schalter **„Auffällige ausblenden“** in Rendite-Ranglisten, Ranking nach Gewichtung, Chart-Raster, Startseite und unter Einstellungen (gespeichert). Plätze bleiben die der vollständigen Rangliste („Platz 3 der vollständigen Rangliste – davor nur Auffällige“). Die Spitzenreiter ohne Auffällige rechnet der Server mit (`winners_klar`), die App filtert die Listen mit derselben Regel – der Datenvertragstest prüft die Gleichheit in allen 90 Zeiträumen | Kennzeichen „sehr niedriger Umsatz“ nur in den Rendite-Ranglisten, kein Ausblenden | Deine Wahl „Aussagekräftiger“: Kleinstwerte und einzelne Kurssprünge sollen das Bild nicht verzerren |
| Ranglisten mit „Auffällige ausblenden“ laden die vollständige Datei nur, wenn unter den ersten 50 Plätzen nicht genug unauffällige Aktien stehen | – | Kein unnötiger Download |
| Fehlerkorrektur gefunden bei der Nachrechnung: Eine Aktie, deren Kurse alle ungültig sind, meldet keine Kursreihe mehr (`has_series`) | Die App bot eine Kursgrafik an, deren Datei fehlte | Gefunden bei der unabhängigen Nachrechnung mit echten Daten |
| Nachrechnung: Ende je Aktie am letzten Schlusskurs erlaubt, wenn der Stand die Regel nennt (`letzter_schlusskurs` im Manifest) | – | Prüft die neue Regel mit |

## 1.13.0 – 14.10.2026 (Zwischenstand mit allen Aktien, einheitliche Zeilen, Knöpfe „Schlusskurse …“)

Deine Nachrichten vom 14.10.: 15:08 Uhr (mit zwei Bildschirmfotos) „Das sieht komisch aus auf dem ersten Bild. Dachte, du achtest darauf, dass alles vereinheitlicht ist. Und das oben ‚Offiziell‘ verwirrt mich.“ – 15:16 Uhr „Wo ist die Aktie in der App? Macht die App Sinn? Wird alles richtig berechnet? Kontrolliere.“ – und deine Wahl für den Zwischenstand vor Börsenbeginn: **„Mit letztem Schlusskurs“**.

**Versionen:** Software und App 1.13.0 · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`) – neu ist nur, welche Aktien ein Zwischenstand mitrechnet. Stände mit Schlusskursen Zahl für Zahl wie bisher.

| Änderung | Vorher | Begründung |
|---|---|---|
| **Zwischenstand mit allen Aktien:** Aktien ohne Kurs von heute – Börse noch nicht geöffnet (z. B. New York vor 15:30 Uhr) oder bis zum Abruf kein Handel – zählen mit dem **Schlusskurs des Handelstags davor**. Für sie ist dieser Tag der Stichtag: alle Zeiträume 1–90 Tage enden dort, die Werte sind Zahl für Zahl dieselben wie im Stand mit Schlusskursen (Test vergleicht jede Kennzahl). Sie stehen in allen Ranglisten, in Häufigkeit, Matrix, Bericht 1–30, Top 3 und „Deine Aktien“; jede Zeile zeigt „Schlusskurs 13.10.“, der Hinweis oben „New York noch nicht geöffnet – mit Schlusskurs vom 13.10.“, die Status-Seite die Anzahl („Mit Schlusskurs gerechnet“). Börsen mit Feiertag fehlen weiter wie im Stand mit Schlusskursen | Bis 15:30 Uhr fehlten alle US-Aktien im Zwischenstand („Kurs am Stichtag fehlt“), z. B. PDS – zu finden nur im Stand mit Schlusskursen | Deine Wahl: alle Aktien immer in Ranglisten und Top 3 |
| **„Deine Aktien“ in denselben Zeilen wie die Rangfolge:** Platz links (mit Stern), Name in voller Breite, ISIN, Punkte rechts; „Platz 4 · 3 Aktien liegen vorne“; Aktien ohne Platz mit „–“ und „ohne Punkte“, der Grund in einer Zeile darunter. Auf der Seite „Top nach Zahlen“ mit Teilen, Begründung und Warnzeichen wie die Rangfolge | Eigene, schmale Liste: der Grund stand rechts neben dem Namen und drückte ihn auf dem Handy auf wenige Buchstaben je Zeile zusammen („Kodia / k / Scien / ces“) | Alles gleich aufgebaut; Name immer lesbar |
| **Knöpfe nennen, was sie zeigen:** Hinweis oben „Zwischenstand – vorläufige Kurse vom 14.10. bis 15:00 Uhr“ mit dem Knopf **„Schlusskurse 13.10.“**; Startseite und Umschichtungs-Regel **„Schlusskurse 13.10. anzeigen“**; Erklärungen sprechen vom „Stand mit Schlusskursen“ | „Offiziell“, „Offiziellen Stand anzeigen“, „Top 3 im offiziellen Stand“ | „Offiziell“ klang, als wäre der Zwischenstand falsch; gemeint sind die letzten Schlusskurse aller Börsen |
| Rückweg aus dem Stand mit Schlusskursen: „Zwischenstand vom 14.10. verfügbar (Kurse bis 15:00 Uhr)“ mit „Anzeigen“ | „Zwischenstand von 14.10.2026 verfügbar“ | Gleiche Schreibweise wie oben |
| **Unabhängige Nachrechnung mit echten Daten** (Workflow „App mit echten Daten prüfen“, neuer Job „Rechnung unabhängig nachprüfen“, `tests/live/nachrechnen.py`): lädt die veröffentlichten Stände aus dem Release, entschlüsselt sie und rechnet ohne den Rechenkern nach – Startsitzung, Kurse und Sitzungen je Zeitraum, Start- und Endkurs, Kursrendite (bitgleich), R² (eigene Formel), Zulassung und Trend-Status, alle Ranglisten der Gruppen A und B mit Perzentilen, Score und Gleichständen, Ø Tagesumsatz und Gruppe B, Häufigkeit (Platz 1, Top 3, Top 10, Zeiträume, Gewichtungen), Prüfsummen aller Dateien; im Zwischenstand: Aktien mit dem Schlusskurs davor Zahl für Zahl wie im Stand mit Schlusskursen. Dazu der **Vergleich mit deinem ChatGPT-Bericht vom 13.10.** (126 Ranglisten 1–30 Tage, 0/100, 40/60, 50/50, 60/40, A und B) über Prüfwerte der ersten Plätze. Im Protokoll nur Zählwerte | – | Deine Frage „Wird alles richtig berechnet? Kontrolliere.“ – nachprüfbar statt behauptet |

## 1.12.0 – 14.10.2026 (Aktualisieren noch schneller)

Deine Nachricht vom 14.10. (13:07 Uhr): „Versuche, bei der Aktualisierung die Dauer so viel es geht zu beschleunigen.“

**Versionen:** Software 1.12.0 · Rechenregeln unverändert – Ergebnisse Zahl für Zahl gleich (Tests vergleichen Dateien und Prüfsummen).

| Änderung | Vorher (Messung 14.10., 1.10) | Begründung |
|---|---|---|
| **Kurse parallel abrufen:** drei gleichzeitige Abrufer mit gemeinsamem Mindestabstand (0,12 s je Host statt 0,4 s nacheinander); Drosselung stoppt alle sofort, bereits geladene Kurse bleiben | 22 s für 62 Abfragen | Der Abstand zwischen Abfragen bestimmte die Dauer, nicht das Netz |
| **Dateien parallel schreiben:** Arbeitspakete (Fenster, Kursreihen in Blöcken, Übersicht, Häufigkeit) auf alle Prozessorkerne verteilt; Werte schneller umgewandelt | 25 s | Lokal mit 6.000 Aktien gemessen: 17,6 s in einem Prozess, 10,0 s mit zwei Kernen (GitHub: vier) |
| **Ältere Stände im Voraus** laden und entpacken, während Kurse abgerufen und gerechnet werden; die Website legt danach nur noch Verweise an (keine Kopien) | 4 s laden + 11 s zusammenstellen | Lief bisher nach dem Rechnen |
| **Sichern als eigener Prozess:** läuft weiter, während der Workflow die Website prüft und hochlädt; gewartet wird erst am Ende des Jobs („Sichern abwarten“) – bereitgestellt wird nur nach erfolgreichem Sichern | 16 s | Nicht mehr auf dem Weg zur fertigen Website |
| **Python-Umgebung aus dem Zwischenspeicher** (neu installiert nur bei geänderten Abhängigkeiten) | 12 s | Jeder Lauf installierte alles neu |
| **Website ohne Kompression hochladen** (gleiches Pages-Artefakt wie bisher: eine `artifact.tar` ohne versteckte Dateien, aber ohne Packen und ohne Liste aller Dateien im Protokoll); die Bereitstellung fragt ihren Status zuerst nach 1 statt nach 5 Sekunden ab | 14 s hochladen + 22 s bereitstellen (327 MB) | Die Daten sind verschlüsselt und lassen sich nicht packen; die Bereitstellung wartete mit wachsenden Abständen (5 s, 7,5 s, 11 s …) |
| **Website mit 3 statt 5 Ständen** (deine Entscheidung, 14:15 Uhr): ein Zwischenstand zählt mit, der neueste vollständige Stand bleibt immer dabei; ältere Stände bleiben als Archiv im Release (`aufbewahrung.site_snapshots: 3`, gleicher Rückfallwert im Code) | 5 Stände, 325 MB, 65.550 Dateien | Weniger zu prüfen, hochzuladen und bereitzustellen |
| **Bereitstellen im selben Job** (Nachtrag nach der ersten Messung im Betrieb): die Website geht als letzter Schritt von „berechnen“ online – unter derselben Bedingung wie bisher (geprüft und gesichert) | 3–4 s Warten auf einen zweiten Runner + 2 s Start, an vollen Tagen mehr (13:51 Uhr: 21 s Warteschlange für den ersten Job) | Ein zweiter Job wartet jedes Mal erneut auf einen freien Runner |
| Prüfen der Website schneller: Dateien, die mit ihrem Schema beginnen, werden nicht mehr vollständig als JSON gelesen (Entschlüsselung und Geheimnis-Prüfung bleiben) | 14 s | Gleiche Sicherheit, weniger Rechenzeit |
| Börsenkalender merken sich Sitzungslisten und Uhrzeiten (Tausende Aktien je Börse fragen dasselbe) | – | Jede Abfrage über pandas kostete rund 1 ms |
| Laufübersicht: Kursreihen laden getrennt vom Rechnen, Abrufe je Weg („quote“/„spark“ mit gelieferten Kursen), Größe der Website | – | Damit die nächsten Schritte messbar sind |
| Top 3 im Zwischenstand: Hinweis auf Börsen ohne Kurs von heute mit Knopf **„Top 3 im offiziellen Stand“** | – | Vor 15:30 Uhr fehlen US-Aktien (z. B. PDS) im Zwischenstand |
| Die App schaut nach „Kurse jetzt aktualisieren“ **alle 15 Sekunden** nach (vorher jede Minute) und meldet den neuen Stand entsprechend früher; Texte nennen 2–3 Minuten statt 10–20 | bis 60 s Verzögerung | Der Lauf selbst ist jetzt kürzer als die alte Wartezeit |

## 1.11.0 – 14.10.2026 (Top 3 nach Zahlen, Börsenwert, Volumen-Anstieg sichtbar)

Deine Nachrichten vom 14.10. (12:05 und 12:38–12:42 Uhr): „Marktkapitalisierung berücksichtigen und bei den Aktien auflisten … bei welcher Aktie das Volumen angestiegen ist, sichtbar machen“, „Ranking mit Aktientipp, 3 Stück … auf die erste Seite als erstes“ und „nach berechenbaren Fakten ausrechnen … nach Berechnungen handeln, emotionslos“.

**Versionen:** Software 1.11.0 · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`) · Signal-Stand `signale-v2` mit neuem Feld `boersenwert_eur` (ab dem nächsten Kennzahlen-Lauf).

| Änderung | Begründung |
|---|---|
| **Top 3 nach Zahlen** ganz oben auf der Startseite: feste Regel über alle Aktien mit Top-10-Nennung – bis 40 Punkte „oft vorne“ (Anteil der gültigen Standard-Ranglisten 40/60, 50/50, 60/40 · 1–30 Tage · A und B unter den ersten 10), 25 „steigt stetig“ (Steig-Konstanz), 20 Analysten (Kursziel-Punkte, voll ab 5 Analysten), 15 Volumen (letzte Sitzung im Vergleich zum Ø der 20 davor, nur bei steigendem Kurs), Abzug für Börsenwert unter 300 Mio. € (−10) bzw. 50 Mio. € (−20). Je Aktie: Punkte je Teil, Begründung, Warnzeichen, Trefferquote der Vergangenheit | Dein Wunsch: emotionslos nach Zahlen, die besten drei sofort sehen |
| **Deine Aktien**: Aktien aus den Musterdepots und der Watchlist mit Platz und Punkten nach derselben Regel („3 Aktien liegen vorne“) | „Ist PDS noch vorne, gibt es etwas Besseres?“ – beantwortet die App jeden Tag neu |
| Neue Seite **Top nach Zahlen** (☰ und „Alle Plätze und Regel“): ganze Rangfolge, Filter „Ohne Warnzeichen“, Regel mit Rechenbeispiel | Nachvollziehbar statt Blackbox |
| **Börsenwert** in EUR im Signal-Stand (Yahoo „marketCap“, EZB-Kurs; GBp/ZAc/ILA richtig umgerechnet), angezeigt in der Top-Liste, in den Kandidaten und in der Einzelansicht | Marktkapitalisierung berücksichtigen und auflisten |
| **Volumen-Anstieg sichtbar**: Liste „Volumen“ unter Potenzial (ab 1,5-fach, steigende Kurse zuerst), Zeile „Volumen zuletzt“ in der Einzelansicht, **Volumen-Leiste** unter der Kursgrafik – Tage mit mehr als doppelt so viel Volumen wie im Ø der 20 Sitzungen davor blau | Wo das Volumen gestiegen ist, sichtbar machen |
| Hinweise zu DEMO und Zwischenstand auch auf der Startseite als schmale Zeile; die Einzelheiten zum Zwischenstand stehen im Kopf der Startseite (mit „Offiziellen Stand anzeigen“) | Die Top 3 stehen sonst nicht oben |
| Auswahlleisten mit vielen Optionen halten die gewählte Option sichtbar; Listen „Kurz“/„Lang“ statt „Kurzfristig“/„Langfristig“ | Fünf Listen passen auf 384 px |

## 1.10.0 – 14.10.2026 (Schneller aktualisieren, besser lesbar auf dem S25+, Musterdepots wie Datei v3 mit Standard 40/60, 50/50, 60/40)

Deine Nachrichten vom 14.10. (11:33–12:20 Uhr): „Es sollte auf das Samsung S25+ passen … leserlich“, „die Geschwindigkeit der Analyse der Berechnungen erhöhen, dass die App flüssig läuft“, die neue Datei „Zwei_Zehnerdepots_1_bis_30_Tage_Beitraege-1.html“ („Anpassen um App genauer zu machen … so leicht erklärbar … so effizient wie es nur geht“), „40/60, 50/50, 60/40 … als Zusatzoption“ und „40/60, 50/50, 60/40 als Standard und das ausführlichere als Option“.

**Versionen:** Software 1.10.0 · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`, Signale `signale-v2`) – Ergebnisse Zahl für Zahl gleich, nur schneller.

| Änderung | Begründung |
|---|---|
| **Kursabruf im Zwischenstand:** zuerst die Kursabfrage „quote“ mit bis zu 150 Werten je Abruf (rund 40 statt 303 Abrufe); was sie nicht liefert, holt wie bisher „spark“ (20 Werte je Abruf) | Gemessen am 14.10.: Kursabruf 120 s von gut 5 Minuten Rechenschritt |
| **Rechnen auf mehreren Prozessorkernen** (GitHub: 4) – die Kennzahlen aller Aktien in Blöcken; Ergebnis und Prüfsumme identisch zur bisherigen Schleife (Test) | Rechnen 45 s |
| **Dateien schreiben schneller:** JSON direkt kodiert (bisheriger Umweg nur noch bei nicht endlichen Zahlen), gzip-Stufe 5 statt 9 (Dateien ~2 % größer), kein fsync je Datei | Schreiben 49 s; lokal gemessen 76 → 35 s |
| **Sichern parallel:** Datenbank packen (gzip-Stufe 3) und hochladen läuft, während die Website zusammengestellt wird; der Zwischenstand lädt die eben gerechnete Datenbank dabei nicht mehr ein zweites Mal herunter; **Prüfung der Website** auf mehreren Kernen | Sichern 54 s, Prüfen 26 s |
| Laufübersicht zeigt die **Dauer je Abschnitt** (Zustand laden, Kurse, Rechnen, Schreiben, Sichern, Website) | Damit Fortschritt messbar bleibt |
| **Lesbarkeit S25+:** keine Schrift mehr unter 12 px (Kleingedrucktes, Grafikachsen, Ränge); Hinweise zu DEMO und Zwischenstand außerhalb der Startseite als schmale Zeile mit Knopf „Offiziell“; lange Einleitungen auf drei Zeilen gekürzt mit „Mehr zu dieser Ansicht“; aktiver Unterreiter und gewählter Zeitraum werden in die Mitte gescrollt; vier Reiter der Einzelansicht passen nebeneinander („Rendite“); Tabelle „Rang je Gewichtung“, Kursvergleichstabelle und Börsentabelle ohne Seitwärtswischen; Formeln unter „So wird gerechnet“ brechen um; Titel und Stand oben passen auch bei Bildschirmzoom (360 und 336 px geprüft) | Auf dem Handy begann der Inhalt erst nach zwei Hinweisblöcken (~470 px); Prüfung aller 32 Ansichten bei 384/360/336 px |
| **Musterdepots wie Datei v3:** Häufigkeit mit **Standard 40/60, 50/50, 60/40** (1–30 Tage, A und B); Optionen „Ausführlich: alle 11 Gewichtungen“, „Bericht: 0/100, 40/60, 50/50, 60/40“, jede einzelne Gewichtung, 1–90 Tage; **Top 20** (oder Top 10), „In beiden Top 20“ grün | Deine Datei und deine Wünsche (kürzere Auswertung als Standard) |
| Drei Erklärblöcke: **Wer gewinnt bei welcher Gewichtung am häufigsten?**, **Wie werden 0/100 bis 100/0 berechnet?** (mit echtem 30-Tage-Beispiel, Score mit zwei Nachkommastellen, Rendite, R²) und **Was ändert sich mit allen elf Gewichtungen?** (Rang und Nennungen Standard → elf) – gerechnet erst beim Aufklappen | So leicht erklärbar wie in der Datei, ohne die Seite zu verlangsamen |
| Behoben: **Einzelansicht breiter als das Handy** – lange Gründe ohne Rang („zu wenige Kurse“) und unsichtbare Vorlesetexte der Tabelle „Rang je Gewichtung“ machten die Seite breiter als 384 px; das Handy zoomte heraus, Knöpfe lagen außerhalb des Bildschirms. Jetzt brechen die Gründe um, Tabellen halten ihren Inhalt im eigenen Rahmen, und ein neuer Browser-Test misst 29 Ansichten gegen die Gerätebreite | Gefunden vom Browser-Test „Zeitraum wechseln“; die bisherigen Breitenprüfungen verglichen mit der Fensterbreite, die beim Herauszoomen mitwächst |
| Behoben: **Umsatz in EUR im Signal-Stand** war bei Aktien aus London, Johannesburg und Tel Aviv (Kurse in Pence, Cent, Agorot) 10.000-fach zu hoch – die Umrechnung teilte durch den Faktor 0,01, statt mit ihm malzunehmen. Betroffen: Ampel „kurzfristig“ (grau unter 250.000 € Umsatz am Tag), Daytrader-Check „Umsatz“, Reihenfolge des Kennzahlen-Abrufs. Richtig ab dem nächsten Kennzahlen-Lauf | Gefunden beim Vorbereiten des Börsenwerts in EUR; neuer Test mit GBp und ZAc |
| Vorbereitet (noch nicht im Workflow aktiv): **gestaffelte Aktualisierung** – `ci --zwischenstand --stufe 1` holt zuerst nur die Kurse der Aktien, die sich im letzten Stand in den oberen Rängen wiederholen (Standardauswahl zuerst), rechnet und stellt sie bereit, ohne den Zustand zu sichern; `--gestaffelt` kennzeichnet den vollen Lauf als Stufe 2. Status und Manifest tragen `zwischenstand.stufe` | Dein Wunsch: schnell erste Ergebnisse, die dann mit allen Aktien verfeinert werden; Workflow und Anzeige folgen |
| „10 Sieger“ und „10 Top-10“ entstehen aus der Standardauswahl (bis 1.9.2: Bericht mit vier Gewichtungen); Kursvergleich zusätzlich mit „In beiden Top 20“, „Beide Top 20 zusammen“, „Top 20 · erste Plätze“, „Top 20 · Top-10-Nennungen“ | Liste und Depots passen zusammen |

## 1.9.2 – 14.10.2026 (Musterdepots: Feinschliff nach Sichtprüfung auf Handybreite)

**Versionen:** Software 1.9.2 · Rechenregeln unverändert · nur die App ändert sich.

| Änderung | Begründung |
|---|---|
| Häufigkeitsliste: statt „außerhalb Top 10“ steht der **Rang in der vollständigen Reihenfolge** (z. B. „Rang 14“, grau = außerhalb dieser Top-10-Liste; „–“ ohne Nennung); auch die CSV enthält diesen Rang | Der lange Text ragte auf 384 px Breite über die Spalte hinaus; der echte Rang sagt zudem mehr |
| Grafik „Alle Depots · 1–30 Tage“: **runde Achsenschritte** (z. B. 0, 10, 20, 30, 40 %) statt krummer Werte wie −2 %, +12 %, +26 % | Leichter abzulesen |
| Tabelle „Alle Depots“: „1 Tag“ statt „1 Tage“ | Sprachlich richtig |
| Live-Prüfung „App mit echten Daten prüfen“: im Zwischenstand gilt bei der Umschichtungs-Regel der Hinweis „Im Zwischenstand nicht gerechnet“ als richtig; neuer Schritt öffnet die Regel im offiziellen Stand und prüft den Rückweg zum Zwischenstand; der Bericht nennt Zwischenstand (Aktien mit Kurs von heute) und offiziellen Stand getrennt | Die erste Prüfung mit echtem Zwischenstand meldete dort fälschlich einen Fehler (sie wartete 60 s auf Zeilen, die es im Zwischenstand bewusst nicht gibt) |

## 1.9.1 – 14.10.2026 (Alles selbst aktualisieren mit einem Tipp; Zeitplan repariert)

Deine Nachricht vom 14.10. (10:38 Uhr): „Ich will das aber auch selber jederzeit aktualisieren können: die Kurse, Berechnungen, Top 10.“

**Versionen:** Software 1.9.1 · Rechenregeln unverändert.

| Änderung | Begründung |
|---|---|
| **„Alles aktualisieren“ ist die Voreinstellung** eines von Hand gestarteten Laufs (Workflow-Eingabe `zwischenstand`, jetzt oben im Formular und standardmäßig an): einfach „Run workflow“ bestätigen. Der Lauf holt die aktuellen Kurse und rechnet alle Ranglisten 1–90, Bericht 1–30, Top-10-Listen, Häufigkeit und Musterdepots neu; fehlt der offizielle Stand des letzten Börsentags, entsteht er zuerst – und danach wie beim täglichen Lauf Kennzahlen, Kursziele und Gesamtwertung (Ausgabe `kennzahlen` des Laufs) | Selbst aktualisieren ohne Haken und ohne Vorwissen, welche Option die richtige ist |
| „Erzwingen“ und „Zustand neu aufbauen“ meinen weiterhin den offiziellen Lauf, auch wenn der Zwischenstand voreingestellt ist | Kein Durcheinander bei Sonderfällen |
| App: Knopf **„Kurse jetzt aktualisieren“** oben auf der Startseite; die Seite „Jetzt aktualisieren“ erklärt in drei Schritten, was neu gerechnet wird, Sonderfälle unter „Weitere Möglichkeiten“ | Schneller erreichbar und verständlicher |
| Behoben: Der Kennzahlen-Schritt nach einem Zwischenstand-Lauf schrieb den Status mit festem Datenmodus – in Testumgebungen fehlte danach der Zwischenstand im Status | Gefunden beim neuen Test „offizieller Stand zuerst, dann Kennzahlen, Zwischenstand bleibt“ |
| **Zeitplan:** Der tägliche Lauf um 07:00 Uhr hatte nie von selbst gestartet. GitHub ordnet einen Zeitplan dem Konto zu, das die Cron-Zeilen zuletzt geändert hat – hier Commits von Claude, das keinen Zugriff auf dein Repository hat. Der Workflow wurde deshalb mit deinem Zugang einmal deaktiviert und wieder aktiviert (danach gehört der Zeitplan deinem Konto); ob der Lauf morgen um 07:00 Uhr startet, prüfe ich | Damit der Morgenlauf ohne Zutun kommt |

## 1.9.0 – 14.10.2026 (Musterdepots: zwei Zehnerdepots, eigene Depots, Beiträge je Aktie)

Deine Nachricht vom 14.10. (10:01 Uhr) zur Datei „Zwei_Zehnerdepots_1_bis_30_Tage_Beitraege.html“: „Implementieren“.

**Versionen:** Software 1.9.0 · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`, Signale `signale-v2`) · neue Datei `fx.bin` im Datenstand (Euro-Referenzkurse der letzten 100 Tage), Manifest-Feld `fx`.

| Änderung | Begründung |
|---|---|
| Neue Ansicht **Depots** (Rendite → Depots, Menü ☰ → Musterdepots, Links im Bericht 1–30 und auf der Startseite) | Der „Aktien-Kompass“ aus deiner Datei, täglich mit den neuen Kursen und auch im Zwischenstand |
| **Welche Aktien erscheinen am häufigsten?** Die zehn Aktien mit den meisten ersten Plätzen und die zehn mit den meisten Top-10-Nennungen, beide Listen zusammen, gemeinsame grün hinterlegt; Auswertung „Bericht 1–30“, „Gesamt 1–90“ oder „Höchste Rendite“; Rang in beiden Listen, Zahl der auswertbaren Kombinationen, Gesamtwertung; **Kurzfassung kopieren** und Tabelle als CSV | Wie die Schnellübersicht der Datei |
| **Zwei Zehnerdepots** – „10 Sieger“ (häufigste erste Plätze) und „10 Top-10“ (häufigste Top-10-Nennungen), immer aus der Auswahl des Berichts 1–30 (vier Gewichtungen, Gruppe A und B) – plus **eigene Depots** auf dem Gerät; voreingestellt dein **Dreierdepot** (Everpure, Kodiak, PDS) und **Viererdepot** (Everpure, Lindblad, Shopify, PDS), änderbar und löschbar; neue Depots per Häkchen in der Liste oder mit ISINs | Die vier Depots der Datei – die beiden Zehnerdepots entstehen jeden Tag neu aus den aktuellen Ranglisten |
| Je Depot und Zeitraum (1–30 Kalendertage, Ende = Kursstichtag): **Depotrendite**, **Endwert** aus frei wählbarem Startkapital, **Beitrag jeder Aktie in Prozentpunkten** (Balken), Aktienrendite, Start- und Endgewicht, Endwert der Position, Start- und Endkurs mit Datum, Wechselkurs; Sortierung nach Beitrag, Rendite oder Name; † bei Umsatzhinweisen (Kurs ohne gemeldeten Umsatz, sehr geringer Ø Tagesumsatz); CSV | Wie „Beitrag zum Depot · Ranking“ in der Datei |
| Rechenbasis **USD** (wie in der Datei), **EUR** oder Originalwährung – mit den EZB-Referenzkursen des jeweiligen Kurstags | Vergleichbar über Währungen; EUR passt zum TR-Depot |
| **Alle Depots · 1–30 Tage** als Grafik (eine Linie je Depot, Antippen zeigt die Werte) und Tabelle; **Kurse im direkten Vergleich** (Start = 100) für das gewählte Depot, die gemeinsamen Aktien beider Top-10-Listen oder alle Aktien beider Listen, dazu „im Kursraster“ | Wie „Alle vier Depots“ und „Kursvergleich“ in der Datei |
| Rechenweg: gleiche Startbeträge, danach unveränderte Stückzahlen, jedes Fenster eine eigene Rechnung; Start = letzter echter Schlusskurs am oder vor Stichtag − Tage (höchstens 7 Tage davor, wie in den Ranglisten); fehlt ein Kurs, bleibt die Aktie in diesem Fenster draußen (mit Grund), nichts wird aufgefüllt; ohne Kosten, Steuern, Dividenden | Nachvollziehbar und ohne erfundene Kurse; Hinweis „Rückblickende Auswahl“ steht oben auf der Seite |

## 1.8.2 – 14.10.2026 (Bericht 1–30 mit Gesamtwertung)

**Versionen:** Software 1.8.2 · Rechenregeln unverändert (Methode `tr-methode-1.8.0`, Signale `signale-v2`) · nur die App ändert sich.

| Änderung | Begründung |
|---|---|
| Im Bericht 1–30 steht hinter jedem Namen (Tabellen, „Am häufigsten auf Platz 1“, Häufigkeit) ein kleines Kästchen mit der **Gesamtwertung 0–100** der Aktie (grün ab 65, gelb ab 50); die Leiste der hervorgehobenen Aktie nennt sie mit Stufe | Rückblick (wer lag vorne) und Blick nach vorn (Steig-Konstanz 30/60/90 Tage, Kursziel, Aufmerksamkeit, Qualität) auf einen Blick – genau die Aktien, die oft vorne liegen **und** stark bewertet sind, fallen sofort auf |
| Nur mit einem Signal-Stand ab `signale-v2`; ältere Stände zeigen kein Kästchen (kein Ersatzwert) | Keine Zahl, die anders gerechnet ist als die Gesamtwertung |
| **Startseite:** direkt unter „Kandidaten mit Potenzial“ der Block **Bericht 1–30 Tage** mit den drei Aktien, die am häufigsten auf Platz 1 liegen (mit Gesamtwertung); Antippen öffnet den Bericht mit dieser Aktie hervorgehoben | Der Bericht ist dir wichtig – er soll nicht erst nach viermal Scrollen kommen |
| Die Prüfung „App mit echten Daten prüfen“ ruft den Bericht 1–30 auf und meldet Gesamtwertung und Daytrader-Check der Einzelansicht (nur Zählungen) | Die neuen Teile werden auch mit echten Daten geprüft |

## 1.8.1 – 14.10.2026 (Bericht 1–30 Tage in der App)

Deine Nachricht vom 14.10. (08:51 Uhr) zur Datei „TR_1_bis_30_Tage_Rendite_Gleichmaessigkeit_ISIN.html“: „Sowas ist für mich wichtig.“ Der Bericht steht jetzt als eigene Seite in der App – täglich automatisch mit den neuen Kursen und auch mit dem Zwischenstand.

**Versionen:** Software 1.8.1 · Rechenregeln unverändert (Methode `tr-methode-1.8.0`, Signale `signale-v2`) · nur die App ändert sich, die Zahlen kommen unverändert aus dem Datenstand.

| Änderung | Begründung |
|---|---|
| Neue Seite **Bericht 1–30** (Rendite → Bericht 1–30, auf der Startseite als erster Einstieg, im Menü ☰): oben die Kennzahlen wie in der Datei (ISINs im TR-Verzeichnis, geladene Kursreihen, Aktien in mindestens einem 1–30-Tage-Fenster, Ranglisten mit Spitzenreiter von 240), dann **vier Tabellen untereinander** – 0/100, 40/60, 50/50, 60/40 – je Zeitraum 1–30 Tage die Aktie auf Platz 1 in **Gruppe A und B nebeneinander** mit Name, ISIN, Kursrendite, Zeitraum, Währung und Score; ↻ zählt, wie oft dieselbe Aktie in einer Spalte vorne liegt | Die Ansicht aus deiner Datei, aber jeden Tag aktuell und mit allen Aktien des Datenstands |
| Kurze Zeiträume ohne Spitzenreiter (bei 40/60, 50/50, 60/40 weniger als 15 Schlusskurse) werden zu einer Zeile „1–19 · Nicht berechenbar …“ zusammengefasst; eine Gewichtung lässt sich auch allein zeigen | Weniger leere Zeilen beim Durchscrollen, nichts wird ersetzt oder hochgerechnet |
| **Alle vier Gewichtungen nebeneinander** als Matrix (Gruppe A oder B), passend auf den Bildschirm des S25+ ohne seitliches Wischen; gleiche Farbe und ↻ für wiederkehrende Aktien | Wie „30 Zeiträume × vier Varianten“ in der Datei |
| **Am häufigsten auf Platz 1** (fünf Aktien) oben und **„Welche Aktie erscheint am häufigsten?“** unten mit den Filtern der Datei (Gruppen, Gewichtungen, Ranking nach ersten Plätzen oder Top-10-Nennungen, gleiche Kursfenster einmal) | Der schnelle Überblick, den du bei der Fülle an Aktien suchst |
| Antippen einer Aktie in Matrix oder Häufigkeit **hebt alle ihre Vorkommen auf der Seite hervor**; eine Leiste unten nennt die Zahl der ersten Plätze (A und B) und springt mit „Nächstes Vorkommen“ von Fundstelle zu Fundstelle, „Kursverlauf“ öffnet die Aktie | Wie „Antippen markiert die ISIN in der Siegermatrix“ in der Datei |
| Wege zur vollständigen Rangliste, zu den Kursverläufen im Raster, zur Abdeckung aller ISINs und zur Rechenvorschrift; **CSV** mit allen 30 × 4 × 2 Spitzenreitern (Rendite, Score, R², Start, Ende, Einheit, Grund bei leeren Feldern) | Alles aus der Datei an einer Stelle, zum Weiterrechnen in Excel |

## 1.8.0 – 14.10.2026 (Zwischenstand: Ranglisten mit aktuellen Kursen auf Knopfdruck)

Dein Wunsch vom 14.10.: „Es muss nicht Livekurs sein. Aber kann man das nicht so einstellen, dass ich jederzeit die Kurse aktualisieren kann? Und dazu die Berechnungen jederzeit aktualisieren.“

**Versionen:** Software 1.8.0 · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`) · Signale `signale-v2` · Datenbank-Migration 0008 (Tabelle `zwischenstand`).

| Änderung | Begründung |
|---|---|
| **Zwischenstand** (Workflow-Eingabe `zwischenstand`, in der App unter ☰ → Jetzt aktualisieren erklärt): holt die aktuellen Kurse aller Aktien, deren Börse heute schon gehandelt hat (Sammelabfragen zu je 20 Werten, je nach Börse etwa 15–20 Minuten verzögert), und rechnet alle Ranglisten 1–90 Tage, beide Gruppen, Häufigkeit und Matrix mit diesen Kursen als vorläufiger letzter Beobachtung – in etwa 10–15 Minuten | Jederzeit aktualisieren, ohne auf den nächsten Börsenschluss zu warten |
| Vorläufige Kurse werden **nie gespeichert** und ersetzen nie einen Schlusskurs; Aktien von Börsen, die heute noch nicht gehandelt haben (z. B. USA vor 15:30 Uhr), fehlen im Zwischenstand – nichts wird fortgeschrieben. Ø Tagesumsatz (Gruppe B) ohne den laufenden Tag. Fehlt der offizielle Stand des letzten Börsentags, läuft zuerst der tägliche Lauf | Gleiche Regeln wie im offiziellen Stand, ehrliche Lücken statt geschätzter Kurse |
| App: „Zwischenstand 13.10. 12:15“ in der Kopfzeile, Hinweisleiste mit den Börsen ohne Kurs („USA noch nicht geöffnet“) und „Offiziellen Stand anzeigen“, Erklärung „Was ist ein Zwischenstand?“ auf der Startseite, „Kurs … heute 12:15 Uhr (vorläufig)“ in der Einzelansicht, „Letzter Punkt: vorläufiger Kurs“ unter den Charts, alle Angaben unter Datenstand & Betrieb; ein vorhandener Zwischenstand wird beim offiziellen Stand angeboten | Immer klar, ob Schlusskurse oder vorläufige Kurse angezeigt werden |
| Es gibt höchstens einen Zwischenstand; ein neuer ersetzt den alten (auch im Release), der nächste offizielle Stand mit gleichem oder späterem Stichtag löst ihn ab. Zwischenstände zählen nicht als Versuch des täglichen Laufs | Kein Durcheinander mehrerer vorläufiger Stände |
| Behoben: Beim Wechsel zwischen zwei Ständen lud die Startseite kurz die Umschichtungs-Regel des falschen Stands (404 in der Konsole) | Gefunden im Browser-Test des Zwischenstands |

## 1.7.1 – 14.10.2026 (Daytrader-Check, „Was die Analysten denken“, Dafür/Dagegen)

Offene Wünsche vom 14.10. umgesetzt: eine gebündelte Anzeige für Daytrader („Ich weiß nicht, worauf Daytrader achten – finde es heraus und zeig es mir gebündelt“), ein Text, „was Analysten zurzeit über die Aktie denken“, und auf einen Blick, was für eine Aktie spricht.

**Versionen:** Software 1.7.1 · Signale `signale-v2` (unverändert) · Ranglisten unverändert (Methode `tr-methode-1.8.0`). Nur die App ändert sich – die Texte entstehen aus den vorhandenen Daten des Signal-Stands.

| Änderung | Begründung |
|---|---|
| **Daytrader-Check** in der Einzelansicht (Überblick): Liquidität (Ø Umsatz in €), relatives Volumen, Tagesspanne (ATR), Kurslücke zur Eröffnung, Trend, Ausbruch (20-Tage-Hoch), RSI, relative Stärke zum Markt (Perzentil der 20-Tage-Rendite), Steigetage, Anlass (Nachrichten), nächste Geschäftszahlen, bei US-Aktien Leerverkaufsquote und Community – je Punkt ✓/✗/– mit Wert und Erklärung zum Antippen; oben „7 von 11 bewertbaren Punkten sprechen dafür“ | Das sind die Größen, auf die Daytrader üblicherweise achten (Umsatz, Bewegung, Katalysator, Trend, Stärke, Termine); gebündelt statt verstreut |
| **„Was die Analysten denken“** oben im Reiter Analysten: Sätze aus Empfehlungen (mit Richtung gegenüber vor drei Monaten), Ø Kursziel mit vorsichtigstem und höchstem Ziel, Spanne der Quellen, letzte Urteile der Häuser (angehoben/gesenkt, Hoch-/Herabstufungen), Bewertung von Trading Central, Prognose für Gewinn und Umsatz, nächster Termin | Der gewünschte Text zur Grafik – automatisch und nachvollziehbar aus den gezeigten Zahlen |
| **Dafür / Dagegen** unter der Gesamtwertung: Steig-Konstanz, Kursziel und alle Signale mit klarer Richtung; ein überkaufter RSI, wenige Analysten, Zahlen in den nächsten 14 Tagen und wenig Umsatz stehen immer unter „dagegen“ | „Sofort sehen, ob die Aktie gut ist“ – und was dagegen spricht |

## 1.7.0 – 14.10.2026 (Gesamtwertung: Steig-Konstanz 30/60/90 Tage + Kursziel)

Deine Vorgaben vom 14.10. (07:52 und 07:54 Uhr): Eine Aktie, die über 30, 60 oder 90 Tage häufiger steigt, ist lukrativer; ist dazu das Kursziel deutlich positiv (z. B. +100 %), soll sie bevorzugt werden – und die App soll das für **alle** Trade-Republic-Aktien auswerten, weil bei der Fülle der Überblick fehlt.

**Versionen:** Software 1.7.0 · Signale `signale-v2` (vorher v1) · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| **Gesamtwertung (0–100) für jede Aktie:** 35 % Steig-Konstanz + 35 % Kursziel-Potenzial + 15 % Aufmerksamkeit & Schwung + 15 % Qualität; ab 65 stark (grün), ab 50 mittel (gelb) | Eine Zahl, nach der alle Aktien geordnet werden – die aussichtsreichsten stehen oben |
| **Steig-Konstanz:** an wie vielen Handelstagen der letzten 30, 60 und 90 Kalendertage der Schlusskurs höher war als am Vortag (z. B. 15 von 21); 40 % = 0 Punkte, 65 % = 100; ist der Kurs über einen Zeitraum gefallen, zählt dieser höchstens 25 Punkte | „Wer über alle Zeiträume häufig steigt, ist gefragter“ – ein kurzer Schub zählt weniger als ein stetiger Anstieg |
| **Kursziel-Potenzial:** 100 · (1 − e^(−Steigerung/0,35)): +25 % = 51, +50 % = 76, +100 % = 94; mit weniger als 5 Analysten anteilig; ohne Kursziel 0 | Höhere Kursziele zählen mehr, einzelne Ausreißer-Ziele weniger |
| **Trefferquote der Steig-Konstanz:** wie oft Aktien mit ähnlicher Steig-Konstanz 20 bzw. 60 Handelstage später höher standen (aus der eigenen Kurshistorie, mit Vergleich zu allen Aktien) | „Mit Wahrscheinlichkeiten arbeiten“ – gemessen, nicht geschätzt; Kursziele lassen sich so (noch) nicht prüfen |
| **Liste „Gesamt“** ersetzt „Beides stark“ – ganz oben auf der Startseite und in Potenzial; je Zeile die Gesamtwertung, der Streifen „30 T ▲15/21 · 60 T ▲31/42 · 90 T ▲45/63“ und die Gründe; Filter „nur stark“ | Schneller Überblick ohne Suchen |
| **Einzelansicht:** neuer erster Abschnitt „Gesamtwertung“ mit den vier Teilen (Punkte und Beitrag), Steig-Konstanz je Zeitraum (Tabelle) und Trefferquote; im Kopf „Gesamt 78“ neben den Ampeln | Nachvollziehbar, warum eine Aktie oben steht |
| Ein Signal-Stand mit älteren Rechenregeln wird beim nächsten Kennzahlen-Lauf sofort neu berechnet (auch ohne neue Kennzahlen); die vorderen 150 der Gesamtwertung bekommen zuerst aktuelle Kennzahlen, Nachrichten und Community | Die neue Wertung steht ohne Warten auf den nächsten Tag bereit |

## 1.6.0 – 14.10.2026 (Potenzial: Signale kurz- und langfristig, Kursziele, Prognose, neue Struktur)

Dein Auftrag vom 14.10. (06:33–07:11 Uhr): Potenzial und Kursziel je Aktie wie in der TR-App, mehrere Quellen, Durchschnitt, Ampel, Prognose, Kursverlauf mit Zeiträumen, Ranking der Aktien mit dem besten Potenzial direkt am Anfang der Startseite, Stimmung der Community als Grafik, kurzfristige (Daytrader) und langfristige Sicht, Erklärungen zu allen Angaben, einfache und effiziente Struktur, jederzeit aktualisierbar.

**Versionen:** Software 1.6.0 · Signale `signale-v1` (neu) · Rechenregeln der Ranglisten unverändert (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| **Zwei Urteile je Aktie mit Ampel:** *kurzfristig* aus relativem Volumen, Schwung (20 Tage im Verhältnis zur üblichen Schwankung), Steigetagen und Serie, Trendlage (20-/50-Tage-Linie), Ausbruch (20-Tage-Hoch), RSI, Nachrichten und Community; *langfristig* aus Kursziel (erwartete Steigerung, Anteil „Kaufen“, Zahl der Analysten), Bewertung, Wachstum und Finanzen, langfristigem Trend und Richtung der Analystenurteile. Jedes Signal 0–100 Punkte mit Satz, feste Ampelregeln, fehlende Daten werden nie geschätzt | „Diese Aktie hat Potenzial, weil …“ – nachvollziehbar statt Blackbox |
| **Trefferquote der Vergangenheit:** Der technische Teil des kurzfristigen Urteils wird für jede Aktie und jeden vergangenen Tag gleich berechnet; gezählt wird, wie oft der Kurs 5 bzw. 20 Handelstage später höher stand – je Punktebereich und für alle Aktien zum Vergleich | „Mit Wahrscheinlichkeiten arbeiten“ – eine gemessene Häufigkeit statt einer erfundenen Prognose |
| **Prognose-Grafik:** Kursverlauf und 12 Monate voraus – Ø Kursziel, Spanne vom tiefsten zum höchsten Ziel und die übliche Schwankung der Aktie (2 von 3 Fällen); dazu die Gewinn- und Umsatzprognosen der Analysten | Langfristige Sicht „gibt Sicherheit“, wenn es kurzfristig nicht klappt – mit ehrlicher Streuung |
| **Kursziele aus mehreren Quellen:** Yahoo-Konsens (weltweit), bei US-Aktien zusätzlich Nasdaq-Konsens und der Ø der Einzelziele der Häuser (90 Tage); Ø Kursziel der App = Mittel der Quellen. Kursziele werden ab heute täglich gespeichert (Grundlage für eine spätere Trefferquote der Kursziele) | Das TR-Kursziel selbst steht nur in der TR-App nach Login und wird nicht abgerufen |
| **Startseite beginnt mit „Kandidaten mit Potenzial“** (Beides stark · Kurzfristig · Langfristig · Kursziel), neue Ansicht **Potenzial** mit Filtern (Analysten, Branche, nur grün, Gruppe B) | Kandidaten schnell finden, ohne zu suchen |
| **Einzelansicht** mit Reitern Überblick (Urteil, Prognose, Kursverlauf **1W/1M/3M/6M/1J/Max**, Signale), Analysten (Kursziele je Quelle, Kaufen/Halten/Verkaufen über 4 Monate, Urteile der Häuser, Bewertung, Nachrichten, **Community-Grafik**), Kennzahlen (mit Erklärung je Zeile), Rendite 1–90 | Alles zu einer Aktie an einer Stelle |
| **Neue Struktur:** unten Start · Rendite · Potenzial · Aktien · Analyse; Unterreiter für Rendite (Rendite 1–90, Gleichmäßig + Rendite, Sieger) und Aktien (Alle, Watchlist); Analyse-Werkzeuge mit je einem Satz, wofür sie gut sind; ⓘ-Erklärungen an Signalen, Kennzahlen und Abschnitten | „Logisch aufgebaut, einfach zu verstehen, effizient“ |
| **Kennzahlen-Job** im täglichen Lauf *nach* der Bereitstellung der Kurse (neue Ranglisten warten nicht), rotierend mit Zeitbudget (20 Min., bei der Erstbefüllung 45 Min.); Workflow-Eingabe **„Nur Kennzahlen, Kursziele und Signale aktualisieren“** für jederzeit | Jederzeit aktualisierbar, ohne den täglichen Lauf zu verlängern |
| Kurshistorie im Zustand auf gut ein Jahr verlängert (Erstimport 400 statt 200 Tage, Aufbewahrung 430 Tage; bestehende Historien werden mit dem täglichen Abruf verlängert, höchstens 4.000 je Lauf) | Kursverlauf 1J, 200-Tage-Linie |

## 1.5.4 – 14.10.2026 (Schlusskurs aus der Kursmeldung, wenn die Tageskerze noch leer ist)

Die Live-Prüfung um 06:41 Uhr zeigte erneut: Yahoo legt die Tageskerze vom 13.10. für Xetra, Frankfurt, Paris, Zürich, London, Madrid, Brüssel, Kopenhagen, Helsinki, Oslo und Prag an, **aber ohne Schlusskurs** – wie schon am 12.10., als die Kurse erst am Abend des Folgetags kamen. Der letzte gemeldete Kurs derselben Antwort (`regularMarketPrice`, z. B. SAP um 17:39 Uhr) ist dagegen vorhanden.

**Versionen:** Software 1.5.4 · Rechenregeln unverändert (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| Fehlt nach Börsenschluss der Schlusskurs der Tageskerze, gilt der **letzte gemeldete Kurs dieser Sitzung** aus derselben Antwort – nur wenn die Sitzung laut Börsenkalender abgeschlossen ist (Schluss + 60 Minuten), die Meldung zu dieser Sitzung gehört und keine spätere Sitzung mit Kurs vorliegt. Tageshoch, -tief und Umsatz kommen ebenfalls aus der Meldung | Ohne Absicherung warten die Morgenläufe auf Kurse, die Yahoo erst einen Tag später nachliefert; der planmäßige Stand käme dann höchstens als Teilstand |
| Solche Kurse sind **gekennzeichnet** (Einzelansicht: Hinweis „Schlusskurs aus der letzten Kursmeldung …“; Datenstand & Betrieb: Anzahl der Aktien) und werden **automatisch ersetzt**, sobald die Tageskerze kommt (jeder Lauf fragt die letzten 10 Tage erneut ab) – ohne neue Kursrevision. Eine Kursmeldung überschreibt nie eine vorhandene Tageskerze | Nachvollziehbar statt stillschweigend; der endgültige Schlusskurs gewinnt immer |
| Live-Prüfung „Datenquellen prüfen“: neuer Vergleich Kursmeldung ↔ Tageskerze ↔ letzte Stundenkerze (Abweichung in Basispunkten), aktuelle Kurse in Sammelabfragen, Kursziele der Analysten und weitere Quellen (nur Verfügbarkeit, keine Werte im öffentlichen Protokoll) | Grundlage für die Absicherung und für die nächsten Funktionen (Potenzial, Zwischenstand) |

## 1.5.3 – 14.10.2026 (Markierter Zeitraum erklärt sich selbst)

**Versionen:** Software 1.5.3 · sonst wie 1.5.2 (nur die App ändert sich, keine Rechenregeln).

| Änderung | Begründung |
|---|---|
| Der Zeitraum, zu dem „Zu Zeitraum springen“ führt, trägt unter der gelben Zahl jetzt das Wort **„gewählt“** – in „Rendite 1–90“ sowie in Matrix und Liste; für Bildschirmleser als aktueller Eintrag gekennzeichnet (`aria-current`) | Deine Frage am 14.10.: „Warum ist das gelb?“ – die Markierung war ohne Erklärung nicht zu verstehen |

## 1.5.2 – 13.10.2026 (Börsenplatz-Abgleich v3, erster vollständiger Datenstand)

Um 21:07 Uhr hat ein Lauf mit 1.5.1 festgestellt, dass Yahoo die Schlusskurse vom 12.10. inzwischen nachgeliefert hat; um 21:50 Uhr war der **erste vollständige Datenstand** online (`2026-10-12_9820e6d9`, alle Börsen mit Stichtagskursen, Xetra 433 von 439, London 695 von 713, Hongkong 734 von 735, USA 3.623 von 3.628). Dabei zeigte sich: Auch mit vollständigen Kursen waren nach `boersenplatz-v2` 75 von 102 geprüften Spitzenaktien in 3.080 von 8.492 Zeiträumen „auffällig“ – die feste 10-%-Schwelle passt nicht zu den stark schwankenden Werten, die oben in den Rendite-Ranglisten stehen.

**Versionen:** Software 1.5.2 · Börsenplatz-Abgleich `boersenplatz-v3` (vorher v2) · übrige wie 1.5.1 (Methode `tr-methode-1.8.0`).

| Änderung | Begründung |
|---|---|
| **Börsenplatz-Abgleich `boersenplatz-v3`:** verglichen werden nur Schlusskurse mit Umsatz am zweiten Platz (sonst „kein Umsatz am Vergleichsplatz“); die Schwelle wächst mit der üblichen Tagesschwankung der Aktie (robuste Standardabweichung der letzten 20 Tagesrenditen, 3-fach, bei der Wertentwicklung × √2), mindestens 10 % wie bisher, Abweichungen ab Faktor 2 immer auffällig | Schlusszeiten der Börsenplätze liegen Stunden auseinander (Xetra 17:30 Uhr, New York 22:00 Uhr); bei einer Aktie mit 8 % üblicher Tagesbewegung erklärt das allein Abweichungen weit über 10 %. Kurse ohne Umsatz sind nur fortgeschrieben. Rendite und Rang ändern sich nicht |
| Jeder Lauf weist aus, was nach der festen 10-%-Regel auffällig gewesen wäre und warum es das nicht mehr ist (ohne Umsatz am Vergleichsplatz, innerhalb der üblichen Schwankung, weiter auffällig) – im Kurzbericht des Laufs und unter ☰ → Datenstand & Betrieb (`venue_check.auswertung`) | Die Wirkung der neuen Regel bleibt nachprüfbar statt nur behauptet |
| Einzelansicht nennt die Schwelle der Aktie und ihre übliche Tagesschwankung („Schwelle 40 % (übliche Tagesschwankung dieser Aktie 8,0 %)“); „So wird gerechnet“ und „Datenstand & Betrieb“ erklären die Regel je nach Version des Datenstands | Ältere Stände (v1, v2) behalten ihren Text |
| Neuer Workflow **App mit echten Daten prüfen** (nur von Hand): öffnet die veröffentlichte App im Format des S25+, entsperrt sie mit dem Secret, ruft alle Ansichten und eine Einzelansicht auf und meldet Fehler, Ladezeiten, Konsolenfehler und fehlgeschlagene Abrufe – ohne Kurse oder Namen im öffentlichen Protokoll | Die echten Daten sind verschlüsselt und von der Entwicklungsumgebung aus nicht lesbar; so ist die fertige App mit echten Daten geprüft, ohne dass jemand die Passphrase sieht |
| **Ergebnis mit echten Daten** (Lauf um 22:13 Uhr, Stand `2026-10-12_c3806c24`, vollständig): nach der festen 10-%-Regel wären 3.080 Zeiträume (75 Aktien) auffällig gewesen – davon beruhten **2.934 auf Kursen ohne Umsatz am Vergleichsplatz**, 95 lagen innerhalb der üblichen Schwankung, **51 Zeiträume (8 Aktien) bleiben auffällig**. 1.305 Zeiträume sind unauffällig, 328 ohne Vergleichskurse | Bestätigt die Ursache: fortgeschriebene Kurse ohne Handel am zweiten Platz, nicht Fehler der Referenzkurse |

## 1.5.1 – 13.10.2026 (Fehlende Börsentage beim Kursanbieter, erster Datenstand)

Yahoo liefert für Montag, 12.10.2026, in Europa und Asien keine Schlusskurse (am 13.10. um 19:05 Uhr erneut geprüft). Nach der 98-%-Regel aus dem ersten Auftrag wären europäische und asiatische Aktien dadurch bis etwa Weihnachten aus allen Zeiträumen von 2 bis 68 Tagen herausgefallen. Deine Entscheidung vom 13.10.2026: „wie Ausgangsmodell“.

**Versionen:** Software 1.5.1 · Methode `tr-methode-1.8.0` (vorher 1.7.0) · Börsenplatz-Abgleich `boersenplatz-v2` (vorher v1) · übrige wie 1.5.0.

| Änderung | Begründung |
|---|---|
| **Methode 1.8.0:** Ein Zeitraum bleibt bewertbar, wenn höchstens 20 % der erwarteten Börsentage ohne Kurs sind; ein einzelner fehlender Tag ist immer erlaubt (vorher höchstens 2 %). Nichts wird aufgefüllt; Start- und Endkurs bleiben Pflicht; Volumenregeln unverändert (80 % der Kurstage, Volumen an jeder Beobachtung, Randvolumen, Split im Fenster) | Ein Datenloch des Kursanbieters soll Aktien nicht wochenlang aus den Ranglisten nehmen; das Ausgangsmodell kennt keine 98-%-Regel |
| Methodenvergleich jetzt allgemein: jeder Lauf rechnet nach den Zulassungsregeln der Vorversion (`vorherige_regeln` in `config/methode.yaml`) und nennt weggefallene Paare nach ihrem neuen und hinzugekommene nach ihrem alten Status; die Texte der Änderungen stehen in der Konfiguration | Transparenter Vergleich für jeden künftigen Methodenwechsel, nicht nur 1.6.0 → 1.7.0 |
| Statustexte 12 und 14 nennen die Schwellen der jeweiligen Methodenversion | Die App zeigt nur Texte aus dem Datenstand |
| **Teilstand verständlich:** Startseite nennt die Börsen ohne Stichtagskurse mit Namen („London, Xetra, …“) und sagt, dass deren Aktien wegen fehlender Daten fehlen; fehlen mehr Börsen, als geliefert haben, nennt sie stattdessen die enthaltenen („Enthalten sind nur Aktien von 3 der 31 Börsen mit Handel am Stichtag: Australien, Neuseeland und USA“). „Datenstand & Betrieb“ zählt Börsen und Aktien mit Stichtagskurs und listet alle fehlenden Börsen | Der erste echte Stand ist ein Teilstand mit 28 fehlenden Börsen – eine Liste mit 28 Namen auf der Startseite wäre unübersichtlich |
| **Erster echter Datenstand** zum Stichtag 12.10.2026 als gekennzeichneter Teilstand: Lauf mit „erzwingen“ von 19:11 bis 20:37 Uhr (noch Software 1.5.0, Methode 1.7.0), Stand `2026-10-12_5092bae0`. Schlusskurse vom 12.10.: USA 3.623 von 3.628, Australien 525 von 525, Neuseeland 18 von 18; Europa und Asien fast keine (Xetra 17 von 439, London 5 von 713) | Du wolltest die App sofort nutzen; ein gekennzeichneter Teilbericht ist laut Auftrag erlaubt |
| **Börsenplatz-Abgleich `boersenplatz-v2`:** Hatte der zweite Börsenplatz am Start- oder Enddatum eine Sitzung (Börsenkalender), zählt nur der Schlusskurs genau dieses Tages; fehlt er beim Kursanbieter, heißt es „Vergleichskurse fehlen“. An Feiertagen dort weiter die letzte Sitzung davor (höchstens 4 Tage). Vorher galt der letzte gelieferte Kurs bis 4 Tage vorher | Im ersten echten Stand fehlten die Xetra-Kurse vom 12.10.; der Abgleich verglich deshalb den Freitagskurs in Deutschland mit dem Montagskurs in den USA. Jede Aktie mit mehr als 10 % Bewegung am Montag erschien so als auffällig, auch ohne Kursfehler (64 von 89 geprüften Aktien gekennzeichnet) |
| „Datenstand & Betrieb“: Methodenwechsel nennt neu **und** nicht mehr bewertete Paare (bisher nur weggefallene – ab 1.8.0 kommen vor allem Paare hinzu); Abgleich mit zweitem Börsenplatz zählt die tatsächlich verglichenen Zeiträume und nennt die übrigen mit Grund („Vergleichskurse fehlen: …“); Börsen mit Namen statt Kalendercodes | Ohne diese Zählung hätte „0 auffällig“ im Teilstand vom 12.10. nach einem geprüften Stand ausgesehen, obwohl mangels Xetra-Kursen kaum verglichen werden konnte |
| Ein Fehler im Börsenplatz-Abgleich verhindert die Veröffentlichung nicht mehr: Der Stand erscheint ohne Abgleich und ohne Kennzeichen, mit Hinweis (`venue_check.abgebrochen`); ein nicht lesbarer Börsenkalender des zweiten Platzes macht nur die betroffenen Aktien „nicht geprüft“ | Der Abgleich ist nur ein Hinweis; vorher hätte eine Ausnahme dort den ganzen Tageslauf scheitern lassen |
| Teilstand am letzten geplanten Versuch (09:00): jetzt, wenn mindestens 75 % der erwarteten **Aktien** einen Schlusskurs am Stichtag haben (vorher 90 % der **Börsen** – Tallinn mit 15 Aktien zählte so viel wie Hongkong mit 735) | Fehlt z. B. nur Hongkong, soll der Stand mit Europa und USA erscheinen statt gar keiner |

## 1.5.0 – 13.10.2026 (Auftrag „1–90 Tage, Rendite, Gleichmäßigkeit, Umsatzvergleich und Kursgrafiken“)

Nach deinem Programmierauftrag mit Auftragsstand 13.10.2026. Vieles bestand schon (90 Zeiträume, elf Gewichtungen, Gruppen A und B, Charts, Raster, täglicher Lauf); dieser Stand übernimmt die dokumentierten Regeln des Ausgangsmodells als neue Methodenversion und ergänzt die verlangten Ansichten. Die Dateien `TR_Rankings_1_bis_90_Tage_11_Gewichtungen.html` und `TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip` lagen nicht vor – die Reproduktion des historischen Prüffalls ist deshalb **nicht** durchgeführt (09_Bekannte_Luecken). Werte des Prüffalls sind nirgends fest eingebaut.

**Versionen:** Software 1.5.0 · Methode `tr-methode-1.7.0` (vorher 1.6.0) · Kennzahlen `kennzahlen-v2` · Ranking `ranking-11w-v2` · Häufigkeit `frequency-v2` · Ausgangsmodell `TR-90D-11W-two-universes-v1.1` (dokumentierte Regeln übernommen) · unverändert: Gruppen `gruppen-v1`, Umsatz `umsatz-v1`, Regel `rotation-v1`, Schnittstelle `static-api-v1` (nur neue Felder), Datenbank (keine Migration).

| Änderung | Begründung |
|---|---|
| **Regeln des Ausgangsmodells** (Methode 1.7.0): Tagesvolumen an jeder Beobachtung gemeldet (endlich, nicht negativ), positives Volumen an Start- und Endbeobachtung, gemeldeter Split bzw. Zusammenlegung im Fenster zurückgehalten (Freigabe nur mit dokumentierter Prüfung); Status 13 und 14 mit erweiterten Texten | Auftrag Abschnitt 5: Formeln des Ausgangsmodells übernehmen, nichts stillschweigend ändern |
| Gleichstand für alle Gewichtungen: Score, dann Kursrendite, dann ISIN (`ranking-11w-v2`; vorher zusätzlich R² bzw. Steigung und Rauschen) | Auftrag Abschnitt 7 |
| **Methodenvergleich in jedem Lauf**: dieselben Kurse zusätzlich nach den Regeln von 1.6.0 gerechnet; Manifest `method_comparison` mit Paaren vorher/jetzt, Wegfall je Grund und geänderten Spitzenplätzen samt Beispielen; sichtbar unter ☰ → Datenstand & Betrieb und „So wird gerechnet“ | „Ein fachlicher Fehler ist transparent mit einer neuen Version und einem Vergleich zum bisherigen Ergebnis zu beheben“ |
| Neue Kennzahl **positive Schlusskursvergleiche** je Aktie und Fenster (`m.up`, `kennzahlen-v2`); Spitzenreiter der Übersicht tragen die Zahl ihrer Schlusskurse (`n`) | Details der Einzelrangliste und der Siegerübersicht laut Auftrag |
| **Identische Kursfenster exakt**: gleicher Bestand aus ISIN und tatsächlichem Startdatum je Gruppe und Vergleichsmenge (`same_set`, `frequency-v2`) statt Näherung über die Startsitzung je Börsenkalender | Auftrag Abschnitt 8: ein Gleichstand nur beim Gewinner reicht nicht |
| **Feste Schnellwahl 7, 14, 21, 30, 40, 50, 60, 70, 80, 90 Tage** (große Tasten, aktive markiert) plus Feld „Freier Zeitraum 1–90 Tage“ und Lineal – auf Start, Ranking, Kurschart, Chart-Raster, Gewichtungsvergleich und Abdeckung; Sprungtasten in Rendite und Matrix. „30 Tage“ bleibt 30 Kalendertage | Verbindliche Ergänzung des Auftrags |
| Neue Ansicht **Sieger nach Zeitraum** (☰, Kurzfassung auf der Startseite): zehn Zeilen, Gruppe A und B nebeneinander, Gewichtung 0/100 … 100/0, Beginn/Ende/Schlusskurse/Referenzmarkt per Antippen, „Gleichmäßigkeit nicht berechenbar“ bei 7 und 14 Tagen, eigene Zählung über genau diese zehn Zeiträume | Auftrag Abschnitt 9 |
| **Startseite** neu: Kursstichtag, Berechnungszeit, Tageslauf, Abdeckung „berechnet / identifiziert“ getrennt von den TR-Einträgen; Auswahl Gruppe, Zeitraum und Gewichtung (gemerkt, Erststandard 90 Tage und 60/40, alle elf Stufen direkt antippbar); erste fünf; Einstiege „Höchste Rendite“, „Gleichmäßigkeit + Rendite“, „Häufigste Aktien“, „Kursvergleich“ | Auftrag Abschnitt 9, Startansicht |
| **Rendite**: Standard alle 90 Zeiträume mit Sieger A und B nebeneinander, Top 10 beider Gruppen aufklappbar | Ansicht „Höchste Rendite“ |
| **Ranking**: Zeile mit Rangscore, Kursrendite, R², Referenzschluss mit Währung und Ø Tagesumsatz; „Details“ mit Ticker, Referenzbörse, Anfang, Schlusskursen, Steigung, Rauschen, größtem Rückgang, positiven Schlusskursvergleichen, Datenquelle, Datenalter und Prüfstatus; Export CSV und JSON | Einzelrangliste laut Auftrag |
| **Matrix** 1–90 × 11 je Gruppe (Bereiche 1–30, 31–60, 61–90; feste Kopfzeile und Zeitraumspalte; Sprung zu einem Zeitraum); Wiederholungszeichen „↻ N“; Export CSV und JSON | Auftrag: Matrix mit Zeilen 1–90 |
| **Häufigste Aktien** (Reiter „Häufig“) neu: Gruppe A, B oder beide (Beiträge getrennt), alle Gewichtungen, nur mit Gleichmäßigkeitsanteil oder eine; alle Zeiträume, 1–30, 31–60, 61–90 oder frei; identische Fenster wahlweise einmal; Sortierung „Gewinnt am häufigsten“ oder „Meiste Top-10-Nennungen“; Nenner „berechenbare Kombinationen“; Export CSV und JSON mit allen Filtern. Die bisherige Ansicht bleibt als „Erweiterte Zählung“ | Auftrag Abschnitt 8 |
| **Watchlist**: ISINs einfügen (Prüfziffer, Doppelte zusammengeführt, Ungültige genannt, keine Zuordnung über Namen) und als ISIN-Liste oder CSV exportieren | Auftrag: Favoriten nach ISIN importieren/exportieren |
| **Datenstand & Betrieb**: Ausgangsmodell, Methodenwechsel, Berechnungsmetadaten als JSON, druckbare Zusammenfassung; frühere Stände mit Methodenversion und „eingeschränkt vergleichbar“ bei anderer Methode | Exporte und Nachvollziehbarkeit (Auftrag Abschnitte 11 und 13) |
| Täglicher Lauf um **07:00 Europe/Berlin** (Wiederholungen 07:15, 07:45, 09:00; vorher 06:00) | Auftrag: konfigurierbarer Erststandard 07:00 |
| Einstellungen v2: frühere Einstellungen werden übernommen, Zeitraum und Gewichtung einmal auf 90 Tage und 60/40 gesetzt; Gruppe und Sortierung der Häufigkeit werden gemerkt | „Letzte Auswahl lokal merken; anfänglich 90 Tage und 60/40“ |
| Fehler behoben: Rückmeldung des ISIN-Imports verschwand beim ersten Import; Wahl „Frei“ in der Häufigkeit zeigte bei einer vorgegebenen Spanne keine Eingabefelder | gefunden durch die neuen Browser-Tests |
| Häufigkeitstabelle und Zählung der zehn Zeiträume passen ohne seitliches Blättern auf 360–412 px breite Bildschirme; Hover-Hervorhebungen nur noch bei Geräten mit Maus (auf dem Handy bleibt nach dem Antippen keine Hervorhebung „hängen“) | Sichtprüfung der Bildschirmfotos; „horizontales Scrollen nur dort, wo eine Matrix es erfordert“ |

## 1.4.1 – 13.10.2026 (Kürzel ohne Kursdaten)

Der erste echte Lauf fand für 1.735 Notierungen keine Kurse, weil das Kürzel aus der Identitätsquelle nicht zum Kursanbieter passte. Ranglisten und Formeln sind unverändert.

**Versionen:** Software 1.4.1 · Börsentabelle `boersen-v2` (vorher v1) · Datenbank-Migration 0006 · übrige unverändert.

| Änderung | Begründung |
|---|---|
| Börsentabelle `boersen-v2`: die OpenFIGI-Sammelcodes CN (Kanada) und GR (Deutschland) zeigen auf keine Börse mehr | Sie führten zu Yahoo-Kürzeln ohne Kurse (TSX-Venture-Aktien als „.TO“, Frankfurter Werte als „.DE“) |
| Migration 0006: Identitäten mit Referenz Toronto oder Xetra und ohne Kursdaten werden einmal neu geprüft; neue Tabelle `symbol_alternative` | Die neue Zuordnung greift sofort, nicht erst nach 45 Tagen |
| Kennt der Kursanbieter ein Kürzel nicht: andere Schreibweise (nordische Aktiengattungen „ADDT-B.ST“) und Suche nach der ISIN, nur an derselben Börse, mit Plausibilitätsprüfung (Typ, Zeitzone, Börsencode, Währung, Name ≥ 0,25); höchstens 300 Notierungen und 15 Minuten je Lauf, Wiederholung nach 30 Tagen | Kursdaten für richtig zugeordnete Aktien, ohne fremde Kurse einzumischen |
| Ein gefundenes Kürzel bleibt auch nach der nächsten Identitätsprüfung erhalten; Übernahmen im Protokoll, Zählung im Kurzbericht | Nachvollziehbar und stabil |

## 1.4.0 – 13.10.2026 (Gruppenvergleich A/B über 1–30 Tage)

Nach deinem Auftrag „Beide Aktiengruppen über 1–30 Tage vergleichen“ (13.10.2026). Vieles davon gab es schon (90 Zeiträume, elf Gewichtungen, Ranking 2 mit Umsatzfilter, Häufigkeiten, Charts mit „Start = 100“); neu ist die Gruppe B mit allen elf Gewichtungen und die Vergleichsansicht. Bestehende Formeln sind unverändert.

**Versionen:** Software 1.4.0 · Methode `tr-methode-1.6.0` (vorher 1.5.0; neue veröffentlichte Ranglisten) · neu: Gruppenvergleich `gruppen-v1` · unverändert: Kennzahlen `kennzahlen-v1`, Ranking `ranking-11w-v1`, Häufigkeit `frequency-v1`, Umsatz `umsatz-v1`, Schnittstelle `static-api-v1` (nur neue Felder).

| Änderung | Begründung |
|---|---|
| **Gruppe B** (Ø Tagesumsatz ≥ 10 Mio. USD über 20 Sitzungen) mit allen elf Gewichtungen für alle 90 Zeiträume: Vergleichsmengen V ∩ L und U ∩ L, Perzentile und Scores innerhalb der Gruppe (`group_b_ranking`); 0/100 nativ = Ranking 2 | Auftrag: getrennte Ranglisten je Gruppe, 2 × 30 × 11 = 660 je Kursstichtag (die App zeigt 1–30, wahlweise 31–90) |
| Neue Veröffentlichungsprüfung `gruppe_b_eigene_vergleichsmenge` (jetzt 15 Prüfungen): Mengen, alle Gewichtungen, 0/100 und 100/0 in der Reihenfolge der Gruppe A, Sortierregeln, Scores 0–100 | Gleiche Regeln für beide Gruppen, nachprüfbar |
| Datenvertrag (nur Ergänzungen): `orders.ul`, `ties.ul`, `counts.UL`, `m.a_rvl/a_gul/a_rul` je Fenster; `overview.v0l/ul`; `frequency.occ.ul`, `M.ul`, `server_reference_b`, `starts` (Startsitzung je Börsenkalender); `instruments.calendar`; Rangmatrix mit 24 Spalten; `liquid` im Nachweisarchiv | Die App rechnet Scores der Gruppe B bitgleich nach und zählt ohne zusätzliche Dateien |
| App: neue Hauptansicht **Matrix** (sechster Reiter): Reiter Gruppe A / Gruppe B; **Matrix** 1–30 × 11 mit fester Zeitraumspalte und seitlich verschiebbaren Gewichtungen, Zelle = Spitzenaktie mit Name, ISIN, Score, Kursrendite; „nicht berechenbar“ mit Grund; **Liste** (kompakt, je Gewichtung); **Häufigkeit** | Auftrag Punkt 4 und 5, auf dem S25+ bedienbar |
| Wiederkehrende Aktien: dieselbe ISIN trägt in beiden Gruppen und allen Ansichten dieselbe Farbe (acht häufigste) und „×Anzahl“; Antippen markiert alle Vorkommen und öffnet auf Wunsch Rangliste (mit Gruppe) und Kursverlauf | Auftrag: Farbe plus lesbares Zeichen, Identität nur über ISIN |
| Häufigkeitsranking je Gruppe: Platz 1, dann Top 3, Top 10, ISIN; Spalten Rang, Name, ISIN, Platz-1-, Top-3-, Top-10-Vorkommen, auswertbare Kombinationen; alle oder eine Gewichtung; A und B getrennt nebeneinander | Auftrag Punkt 5; die bisherige Häufigkeitsansicht mit ihren Regeln bleibt unverändert |
| Identische Kursfenster: „≡“ in Matrix und Liste; Schalter „Identische Kursfenster nur einmal zählen“ (Gruppe, Gewichtung, tatsächlicher Start und Ende) | Auftrag Punkt 6: Wochenend-Doppelungen sichtbar und wahlweise einmal gezählt |
| Ranking und Chart-Raster mit Aktiengruppe; Einzelansicht zeigt Rang und Score in Gruppe B | Antippen in der Matrix führt zur vollständigen Rangliste der Gruppe |
| Kopf der Matrix: Kursstichtag, Rechenzeit, berechnete und nicht berechenbare Ranglisten mit Grund, Feldgrößen | Auftrag Punkt 7: Datenabdeckung und fehlende Berechnungen sichtbar |

## 1.3.0 – 13.10.2026 (Umschichtungs-Regel: Tagesvorschlag und Rückblick)

Nach deiner Frage vom 13.10.2026 („Algorithmus … Wegen Umschichtung … Tipp geben, 10, 20 % oder so vom ganzen Kapital in die Aktie zu stecken oder einen Teil zu verkaufen und umzuschichten“) und deiner Auswahl: Simulator + Tagesvorschlag, monatlich mit 3-Monats-Trend, 5 Aktien je 20 %, nur Ø Umsatz ≥ 10 Mio. USD. Eine feste Rechenregel, keine Anlageberatung. Die Ranglisten bleiben unverändert.

**Versionen:** Software 1.3.0 · Methode `tr-methode-1.5.0` (vorher 1.4.0) · neu: Regel `rotation-v1` · übrige wie 1.2.0 (Schnittstelle `static-api-v1`, nur neue Dateien und Felder).

| Änderung | Begründung |
|---|---|
| **Umschichtungs-Regel** (`analytics/rotation.py`): Kandidaten mit Ø Tagesumsatz ≥ 10 Mio. USD (4 Wochen), Kursen an ≥ 90 % der Sitzungen und ohne Tagessprung über Faktor 3; Rangfolge nach Kursrendite über 13 (oder 4) Wochen; Entscheidung am ersten Freitag im Monat (oder jeden Freitag), **Ausführung zum Schlusskurs des nächsten Handelstags**; halten bis Platz 2 × N, freie Plätze an die Besten, je 1/N, Angleichen erst ab 5 Prozentpunkten | Deine Auswahl; der Haltepuffer verhindert ständiges Hin- und Herschichten, die Ausführung am nächsten Handelstag entspricht dem frühestmöglichen echten Handeln |
| **Kosten und Steuern** wie bei der Bank: 1 € + 0,1 % Spanne je Order, Abgeltungsteuer mit Soli (26,375 %) nach Verlusttopf und Sparerpauschbetrag (1.000 € je Jahr); Verluste erstatten Steuer desselben Jahres und geben verbrauchten Pauschbetrag frei, der Rest geht in den Verlusttopf | Ein Rückblick ohne Kosten und Steuern wäre zu schön; Vergleichslinie „ohne Kosten“ zeigt, was sie ausmachen |
| **Rückblick** bis 3 Jahre für alle 24 Varianten (5/10 Aktien, monatlich/wöchentlich, 13/4 Wochen, 5.000/10.000/25.000 €) mit Vergleich „alle Kandidaten zu gleichen Teilen“; Kennzahlen Endwert, Rendite, pro Jahr (ab 1 Jahr), größter Rückgang, Orders, Kosten, Steuern | Simulator: Varianten im selben Zeitraum vergleichbar |
| **Tagesvorschlag**: Regeldepot heute mit Anteilen und Beträgen, Änderungen mit Grund („nur noch Platz 12 – gehalten wird bis Platz 10“, „Platz 3, noch nicht im Regeldepot“), nach einem Prüftag als „beschlossen“ gekennzeichnet; Beträge auf einen eigenen Depotwert umrechenbar (nur auf dem Gerät gespeichert) | Deine Frage nach „10, 20 % vom Kapital“ und „einen Teil verkaufen“ |
| **Wochenwerte** (`analytics/weekly.py`, Tabellen `week_bar` und `long_history`, Migration `0005_wochenwerte.sql`): einmaliger Langabruf bis 3 Jahre für Aktien ab 2 Mio. USD Tagesumsatz (höchstens 6.000 bzw. 40 Minuten je Lauf, Rest im nächsten Lauf), jüngere Wochen in jedem Lauf aus den geprüften Tageskursen; nach einem Split zuerst neu laden | 150 Tage Tageskurse reichen für einen Rückblick nicht; Wochenwerte halten die Sicherung klein |
| **EZB-Kurshistorie** (ZIP mit der ganzen Reihe, einmalig, gespeichert für den Rückblickzeitraum) | Euro-Bewertung des Regeldepots in früheren Wochen |
| Neue Veröffentlichungsprüfung `umschichtung_regel_eingehalten` (jetzt 14 Prüfungen): alle Varianten, vollständige positive Verläufe, Käufe nur unter den ersten N, höchstens N Positionen, kein negatives Bargeld, Gebühren = Orders × 1 €, Orders nur an Prüftagen | Die Regel wird bei jedem Stand nachgeprüft |
| Datenvertrag (nur Ergänzungen): `rotation/index.bin`, `rotation/<Variante>.bin`, Manifest `rotation`, Version `rotation` | Die App lädt nur die gewählte Variante |
| App: neue Seite ☰ → **Umschichtungs-Regel** mit gelbem Depot-Lineal (Aufteilung heute und nach den Änderungen), Änderungsliste, Bestand, Rückblick-Diagramm (100 = Startkapital), Kennzahlen, Variantentabelle, Orders je Entscheidungstag, Rangfolge heute und „Was die Rechnung nicht zeigt“; Kurzfassung auf der Startseite; Methodik-Abschnitt | Auf dem S25+ bedienbar; Grenzen (nur heutige Aktien, vereinfachte Steuer) stehen auf derselben Seite |
| Idempotenzschlüssel enthält den Stand der Langhistorie | Ein später nachgeladener Rückblick ergibt bei einem erneuten Lauf einen neuen Stand statt „nichts Neues“ |

## 1.2.0 – 13.10.2026 (Abgleich mit einem zweiten Börsenplatz, Aktualisieren auf Wunsch)

Ergänzt den letzten offenen Punkt deines Auftrags vom 13.10.2026 („auffällige Kursabweichungen zwischen Börsenplätzen“ kennzeichnen) und deinen Wunsch, jederzeit selbst aktualisieren zu können. Noch kein echter Datenstand veröffentlicht; ältere Stände sind nicht betroffen.

**Versionen:** Software 1.2.0 · Methode `tr-methode-1.4.0` · neu: Abgleich `boersenplatz-v1` · übrige wie 1.1.0.

| Änderung | Begründung |
|---|---|
| **Abgleich mit einem zweiten Börsenplatz** für jede Aktie unter den ersten 10 Plätzen von Ranking 1 oder 2 (in allen ihren Zeiträumen): zweite Notierung derselben ISIN aus OpenFIGI (Xetra, dann Frankfurt, dann weitere; nie OTC, nie dieselbe Kursreihe), Schlusskurse vom selben Anbieter, Umrechnung in die Referenzwährung mit EZB-Kursen. Auffällig bei mehr als 10 % Abweichung der Wertentwicklung oder des Endkurses → Fensterhinweis 5 „Auffällige Kursabweichung zwischen Börsenplätzen“ | Auftrag: Kursabweichungen zwischen Börsenplätzen kennzeichnen. Nur ein Hinweis – Rendite und Rang bleiben die der Referenzbörse (Methodik: eine Referenznotierung je ISIN) |
| Schritt läuft erst, wenn veröffentlicht wird; Zeitbudget 15 Minuten, höchstens 600 Aktien; Drosselung oder Zeitbudget beenden ihn, übrige Aktien „nicht geprüft“; Wahl des Platzes 45 Tage gespeichert (Tabelle `venue_listing`, Migration `0004_boersenplatz.sql`) | Keine zusätzlichen Abrufe bei Läufen ohne Veröffentlichung; ein Ausfall darf keinen Datenstand verhindern |
| Neue Veröffentlichungsprüfung `boersenplatz_kennzeichen` (jetzt 13 Prüfungen) | Hinweis genau bei den auffälligen Vergleichen |
| Datenvertrag (nur Ergänzungen): `instruments.venue`, `windows/<h>.xv`, `xv` je Siegerzeile, Manifest `venue_check`, Codes `venue_status`/`venue_pair_status` | Anzeige ohne zusätzliche Dateien |
| App: Zeile „Vergleich mit Börse … : unauffällig / auffällige Abweichung“ bei den vorderen Plätzen, gelbes Kennzeichen „Börsenplatz-Abweichung“, Einzelansicht mit Börse, Symbol, Kursen, Rendite dort und Abweichungen, Abschnitt in „Datenstand & Betrieb“ und Methodik, CSV-Spalte „Zweiter Börsenplatz“ | Auftrag: Hinweise je Aktie sichtbar |
| DEMO: synthetischer zweiter Börsenplatz Frankfurt mit zwei bewusst abweichenden Testaktien | Tests ohne Netz |
| **Jetzt aktualisieren:** neue Seite (☰, Datenstand & Betrieb, Startseite ohne Datenstand) mit „Lauf auf GitHub starten“; danach liest die App `status.json` jede Minute und meldet „Aktualisierung fertig“ (mit „Neuen Stand anzeigen“), „Lauf beendet – keine neuen Kurse“ mit Grund oder nach drei Stunden „Noch kein Ergebnis“; Warten übersteht einen Neustart der App | Dein Wunsch: jederzeit aktualisieren. Gestartet wird mit deiner GitHub-Anmeldung, weil die App keinen Schlüssel enthalten darf |
| `status.json`: `naechster_kursstand` (nächster möglicher Kursstichtag und ab wann, gleiche Regel wie der Stichtag) und `aktualisieren` (Links auf GitHub, nur in GitHub Actions) | Die App sagt vor dem Start, ob ein Lauf jetzt neue Kurse bringen kann |
| Von Hand gestartete Läufe warten bei fehlenden Stichtagskursen nur weiter; über Teilstand oder Fehlschlag entscheidet allein der vierte **geplante** Versuch eines Stichtags (bisher zählten alle Läufe) | Mit „Jetzt aktualisieren“ wären die Wiederholungen sonst schnell aufgebraucht und ein zusätzlicher Start vor 23 Uhr hätte einen roten Lauf mit E-Mail ausgelöst |
| Kurzbericht: Zählungen (Identität, Kursabruf, Börsen ohne Kursdaten) vor den Beispielen; Beispiele ohne Stichtagskurs in einer Zeile | Im Lauf vom 13.10., 13:35 Uhr verdrängten 26 Beispielzeilen die neue Zeile „Keine Kursdaten je Börse“ aus dem von GitHub gekürzten Hinweis |
| Statusdateien werden mit Zeitstempel-Parameter gelesen; der Service Worker speichert sie unter festem Namen | Sonst zeigt GitHub Pages bis zu 10 Minuten alte Angaben, und der Offline-Speicher würde mit jeder Abfrage wachsen |

## 1.1.0 – 13.10.2026 (zwei Rendite-Ranglisten mit Umsatzfilter)

Erweiterung nach deinem Auftrag vom 13.10.2026. Es gab noch keinen veröffentlichten echten Datenstand; ältere Stände sind deshalb nicht betroffen. Stände ohne die neuen Felder (DEMO-Stände aus 1.0.0) zeigt die App weiter an und nennt den fehlenden Umsatzfilter.

**Versionen:** Software 1.1.0 · Methode `tr-methode-1.3.0` (vorher 1.2.0) · neu: Umsatz `umsatz-v1` · unverändert: Kennzahlen `kennzahlen-v1`, Ranking `ranking-11w-v1`, Häufigkeit `frequency-v1`, Schnittstelle `static-api-v1` (nur neue Felder, keine geänderten).

| Änderung | Begründung |
|---|---|
| **Ranking 1 „Höchste Kursrendite“**: alle Aktien mit veröffentlichter Kursrendite (Menge V), je Zeitraum 1–90 eine eigene Liste, sortiert nur nach der ungerundeten Kursrendite (0 % Gleichmäßigkeit / 100 % Kursrendite). Keine Mindestgrenzen für Kurs, Börsenwert oder Umsatz; die bisherigen Datenqualitätsprüfungen gelten weiter | Auftrag: reine Renditeliste über das ganze TR-Angebot |
| **Ranking 2 „Höchste Kursrendite – Ø Tagesumsatz mindestens 10 Mio. USD“**: dieselben Kurse, Zeiträume, Formel und Reihenfolge wie Ranking 1, nur Aktien mit bestimmtem Ø Tagesumsatz ≥ 10 Mio. USD (Menge V ∩ L). Der Umsatz ist Aufnahmefilter, kein Sortierkriterium | Auftrag |
| **Ø Tagesumsatz** je Aktie: Schlusskurs × gemeldetes Volumen je Sitzung über die letzten 20 abgeschlossenen Sitzungen der Referenzbörse (Börsenkalender), arithmetischer Mittelwert über die Sitzungen mit Daten; mindestens 16 Sitzungen mit positivem Volumen; fehlende Daten zählen nicht als null; Split innerhalb der 20 Sitzungen → nicht bestimmbar; Untereinheiten (Pence, Agorot, Cent) in Hauptwährung | Auftrag: Kapitalmaßnahmen dürfen nicht verzerren, keine Nullen für fehlende Daten |
| **Wechselkurse:** neuer Laufschritt „wechselkurse“ mit den EZB-Referenzkursen (90-Tage-Datei, ein Abruf je Lauf), gesichert in der neuen Tabelle `fx_rate` (Migration `0002_wechselkurse.sql`, läuft automatisch); bei Ausfall gespeicherte Kurse mit Warnung; je Sitzung der Kurs des Tages oder der letzte davor, höchstens 5 Tage alt. Quelle, Abrufzeit und Kurstage stehen im Manifest und in der App | Auftrag: Wechselkursquelle und Datenzeit dokumentieren; ohne Kurs keine Aufnahme in Ranking 2 |
| Kennzeichen „sehr niedriger Umsatz“ (Ø unter 1 Mio. USD) und „Umsatz nicht bestimmbar“ mit Grund (Hinweise 14 und 15) | Auftrag: sehr niedrigen Handelsumsatz deutlich kennzeichnen |
| Neuer Fensterhinweis **Übernahmemuster** (4): größter Tagesanstieg ≥ 15 %, danach mindestens 3 Sitzungen mit höchstens ±1 % Bewegung | Auftrag: Übernahmesprünge kennzeichnen; die Rendite bleibt veröffentlicht |
| Neue Veröffentlichungsprüfung `ranking2_teilmenge_gleiche_rendite` (jetzt 12 Prüfungen): Ranking 2 ist exakt Ranking 1 ohne die nicht aufgenommenen Aktien | Auftrag: beide Ranglisten mit demselben Stichtag und derselben Formel |
| Datenvertrag (nur Ergänzungen): Ø Umsatz je Instrument (`instruments.turnover`), Start- und Endkurs je Aktie und Zeitraum (`m.p0`, `m.p1`), Reihenfolge und Gleichstände von Ranking 2 (`orders.v0l`, `ties.v0l`, `counts.L`), Sieger von Ranking 2 (`winners_l`, `overall_max_l`), Häufigkeiten mit Universumsnamen (`occ.v0l`, `M.v0l`, `universe`), Manifest-Abschnitt `turnover`, Rangmatrix mit 13. Spalte `v0l` | Anzeige von Start-/Endkurs mit Datum und Umsatzbasis ohne zusätzliche Abrufe |
| App: Bereich „Rendite“ mit zwei getrennten Reitern; je Zeitraum zuerst der Sieger, Antippen → Top 10 → vollständige Liste; Standardansicht 1–7 Tage. Je Aktie Rang, Name, Ticker, ISIN, Kursrendite, Start- und Endkurs mit Datum, Börse und Währung, Ø Tagesumsatz mit Berechnungsbasis, Hinweise. Getrennte Zählungen: TR-Instrumente, geladene Kursreihen, bewertete Aktien je Rangliste | Auftrag: auf dem S25+ bedienbar, Teiluniversum nie als vollständige Prüfung |
| App: Einzelansicht mit Ø Tagesumsatz und beiden Rendite-Plätzen; Häufigkeit nennt ihr Universum, bei „Nur Rendite“ wahlweise mit Umsatzfilter (nie gemischt); Datenstand & Betrieb mit Umsatzfilter und Wechselkursstand; Methodik-Abschnitt „Zwei Rendite-Ranglisten“ | Auftrag: Häufigkeitslisten nennen Universum und Filter |
| Kurzbericht des Laufs nennt den Wechselkursschritt; DEMO-Quelle liefert synthetische Wechselkurse | Sichtbarkeit im Betrieb; Tests ohne Netz |
| Identitätsprüfung: Zeitzonen mit ganzjährig gleicher UTC-Verschiebung gelten als passend, wenn der Börsencode des Kursanbieters die Börse bestätigt; bisher deshalb „unklare“ Identitäten werden einmalig neu geprüft (Migration `0003_zeitzonen_neu_pruefen.sql`); Notierungen mit zunächst unklarer Identität werden für denselben Stichtag erneut abgerufen | Erster voller Lauf am 13.10.2026: 83 Wiener Aktien „unklar“, weil Yahoo für Wien „Europe/Amsterdam“ meldet (gleiche Uhrzeit, Börsencode VIE) |
| Kurzbericht des Laufs: Notierungen ohne Kursdaten und mit Abruffehlern je Börse mit Beispielen und Grund | Erster voller Lauf: 1.162 von 3.916 Notierungen ohne Daten – der Bericht zeigt jetzt, welche Börsen und Symbolformate betroffen sind |
| Leistungsmessung mit sechs Währungen und Wechselkursen | Größe eines Datenstands steigt von 74 auf 97 MB (gemessen, vor allem Start- und Endkurse) |

Noch nicht enthalten: Abgleich auffälliger Kursabweichungen zwischen Börsenplätzen – folgt in 1.2.0.

## 1.0.0 – 12.10.2026 (erste Fassung, noch kein produktiver Datenstand)

Umsetzung des Programmierauftrags v1.2. Bisher wurde kein echter Datenstand veröffentlicht; es gibt deshalb keine älteren Stände, die von einer Methodenänderung betroffen wären.

**Versionen:** Software 1.0.0 · Methode `tr-methode-1.2.0` · Kennzahlen `kennzahlen-v1` · Ranking `ranking-11w-v1` · Häufigkeit `frequency-v1` · Schnittstelle `static-api-v1` · Börsentabelle `boersen-v1`.

### Umfang

- Täglicher Serverlauf in GitHub Actions (06:00 Europe/Berlin, Wiederholungen 06:15, 06:45, 08:00) mit Checkpoints, Doppelstart-Schutz, verschlüsselter Sicherung im Release und Veröffentlichung auf GitHub Pages.
- Universum aus der öffentlichen TR-Instrumentenliste (Aktienabschnitt), Zuordnung jeder ISIN zu genau einer Referenznotierung, Börsenkalender je Referenzbörse, gemeinsamer Kursstichtag.
- Rechenkern: 90 Kalenderfenster, Qualitätsregeln (98 % Sitzungen, 80 % Volumen, 15 Kurse für Gleichmäßigkeit), Preis-OLS mit R², Kursrendite, MDD, alle elf Gewichtungen 0/100 bis 100/0 nativ und im gleichen Vergleichsfeld, Renditesieger 1–90, Häufigkeiten Top 1/3/10, Gesamtmaximum.
- Installierbare Web-App für das Galaxy S25+: Start, Rendite 1–90, Ranking, Gewichtungsvergleich, Häufigkeit mit Treffermatrix, Chart-Raster, Einzelcharts, Watchlist, Gesamtverzeichnis mit Status je Aktie, Datenstand & Betrieb, Methodik, Export (CSV, PNG), offline lesbar.

### Änderungen während der Entwicklung (vor der ersten Veröffentlichung)

| Änderung | Begründung |
|---|---|
| Neue Prüfregel: Kursbewegung über 10 % an einem Tag **ohne belegten Umsatz** am Fensterbeginn oder -ende hält das Fenster zurück (Status 13), freigebbar über `config/pruefungen.yaml` | Einzelne Geisterkurse ohne Handel könnten sonst ungeprüft zum Tagessieger werden (Auftrag: keine ungeprüften Spitzengewinner) |
| Residuen der OLS zentriert berechnet; nahezu konstante Reihen ergeben „R² nicht stabil bestimmbar“ statt eines Laufabbruchs | Numerische Stabilität; ein einzelner Sonderfall darf den Tageslauf nicht stoppen |
| Fensterlängen außerhalb 1–90 werden auch im Rechenkern abgewiesen | Auftrag T21 |
| Gesamtmaximum zählt dieselbe Aktie mit demselben tatsächlichen Zeitraum nicht als Gleichstand mit sich selbst; gleiche Zeiträume werden genannt | Keine Scheingleichstände (T95, T97) |
| Verwaiste Sperren aus einem abgebrochenen Runner werden beim nächsten Lauf freigegeben und als „abgebrochen“ protokolliert | Ein abgestürzter Lauf darf alle folgenden nicht blockieren |
| Kein `--soft-fail` im Workflow: ein fehlgeschlagener Lauf bleibt rot, der Status wird trotzdem veröffentlicht | GitHub soll per E-Mail benachrichtigen; der letzte gute Stand bleibt sichtbar |
| Bereitstellung auf GitHub Pages nur nach bestandener `verify-site`-Prüfung | Vorher hätten die mit `always()` laufenden Schritte die Website auch nach einer fehlgeschlagenen Prüfung (z. B. Geheimnis in einer Datei) hochgeladen |
| Datenbanksicherung wird lückenlos ausgetauscht (Zwischenname, löschen, umbenennen); `crypto.json` nur noch hochgeladen, wenn es fehlt | Vorher hätte ein Abbruch zwischen Löschen und Hochladen die einzige Sicherung gekostet |
| Angezeigte Stammdaten (Name, Ticker, Börse, Identität) gehören zum Idempotenzschlüssel; frühere Ticker und Symbole bleiben als Suchbegriffe erhalten | Ein Tickerwechsel am selben Stichtag ergibt eine neue Revision statt eines veralteten Tickers (T37, T50) |
| Aufbewahrung der Tageskurse im Zustand 250 statt 400 Tage | Die Rechnung braucht 150 Tage; kleinere Sicherung, schnellere Läufe |
| Diagramme: Pos1/Ende/Pfeiltasten scrollen die Seite nicht mehr mit; Zwei-Finger-Zoom auch dort, wo der Browser `touch-action` auf SVG-Elementen nicht beachtet | Bedienbarkeit auf Android und mit Tastatur (T77) |
| Kurzer Titel „Rendite 1–90“ in der App-Leiste | Langer Titel wurde neben Datum und Kennzeichen abgeschnitten |
| Workflows und Tests auf Python 3.13 vereinheitlicht | Dieselbe Version wie in den ausgeführten Tests |
| Lockdatei der App auf die öffentliche npm-Registry umgestellt | GitHub Actions erreicht nur die öffentliche Registry |
| Offene Datenbankverbindungen in `ci` und `restore-test` werden geschlossen | Ressourcenwarnungen in Tests; sauberes Beenden |
| Rückfallwert für `aufbewahrung.site_snapshots` im Code 5 statt 7 | Gleich dem dokumentierten und konfigurierten Wert |
| App-Build: Dateinamen aus dem Inhalt statt aus esbuilds `[hash]` | esbuilds Hash hängt vom Projektpfad ab; in GitHub Actions hätte die Prüfung „app/dist ist veraltet“ sonst immer angeschlagen |
| `.gitignore`: lokale Datenordner nur im Hauptverzeichnis ausgeschlossen | Das Muster `state/` hatte den Quellordner `app/src/state` ausgeschlossen; er fehlte im ersten Commit und ZIP |
| Vorschau-Build als eine HTML-Datei mit eingebetteten DEMO-Daten (`app/scripts/build_preview.mjs`); ohne Service Worker, Downloads, Drucken und Installation; übernimmt das Farbschema des umgebenden Rahmens | Die App lässt sich vor der GitHub-Einrichtung in Claude ansehen; echte Kursdaten werden nie eingebettet |

### Nach der ersten Bereitstellung (13.10.2026, Builds 1.0.0)

| Änderung | Begründung |
|---|---|
| `reportlab` in `backend/requirements-dev.txt` | Der PDF-Rundlauftest des Universum-Parsers lief lokal nur, weil reportlab dort vorinstalliert war; im ersten Lauf „Prüfung“ auf GitHub fehlte das Paket |
| Workflow „Prüfung“ zeigt fehlgeschlagene Tests als Hinweise in der Laufübersicht | Die Ursache ist sichtbar, ohne das Protokoll herunterzuladen |
| Notierungen ohne Kurs am Stichtag und Abruffehler werden im nächsten Versuch für denselben Stichtag erneut abgerufen (Abrufstatus `ohne_stichtag`) | Bisher galt eine Notierung nach dem ersten Abruf als erledigt; die Wiederholungen um 06:15, 06:45 und 08:00 konnten verspätet gelieferte Schlusskurse deshalb nicht übernehmen. Anlass: erster echter Lauf am 13.10.2026 |
| Kurzbericht des täglichen Laufs als Hinweis in der GitHub-Laufübersicht: Ergebnis, Stichtag, TR-Liste, Identitätsprüfung, Kursabruf, Stichtagskurse je Markt mit Beispielen | Das Protokoll eines Laufs ist nur als Ganzes abrufbar; der Grund für „wartet auf Anbieter“ war nicht erkennbar |
| Workflow „Datenquellen prüfen“: Stichtagskurs je Börse bei Yahoo (ein liquider Wert je Börse, drei Abfragevarianten, Stundenkerzen) und Kennzahlen je Quelle als Hinweise | Prüft genau das, worauf der tägliche Lauf angewiesen ist: den Schlusskurs des gemeinsamen Stichtags |
| App: Passphrase lässt sich schon vor dem ersten Datenstand eingeben und prüfen; der Grund des letzten Laufs steht lesbar mit Uhrzeit im Leerzustand | Bisher fragte die App erst nach der Passphrase, wenn ein Datenstand existierte – nach der Einrichtung war unklar, wo sie einzugeben ist |
| Täglicher Lauf: Eingabe `nur_website` (`traktien ci --nur-website`) stellt nur die Website neu bereit – App-Hülle neu, Datenstände und Sicherung unverändert | Eine geänderte App war bisher erst nach dem nächsten vollständigen Lauf online (bis zu Stunden) |
