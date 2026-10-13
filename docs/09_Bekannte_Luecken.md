# Bekannte Lücken und offene Punkte

Stand 13.10.2026 (Software 1.4.1). Zu jedem Punkt: was fehlt und welches überprüfbare Ergebnis ihn abschließt. „Fertig“ heißt in diesem Projekt nur, was tatsächlich ausgeführt und geprüft wurde (07_Testbericht).

## A. Betrieb, Freigaben und Gerät

| Punkt | Stand | Abgeschlossen, wenn … |
|---|---|---|
| Bereitstellung | **erledigt** (13.10.2026): Repository, Secret `DATA_PASSPHRASE`, GitHub Pages; die App ist unter `https://szymeklh87-commits.github.io/tr-aktienvergleich/` erreichbar | – |
| Erster echter Datenstand | Noch keiner veröffentlicht. Zum Stichtag 12.10. fehlen bei Yahoo die Schlusskurse in Europa und Asien (Abschnitt B); nach dem Schlüsselwechsel am 13.10. beginnt die Zuordnung der 11.560 ISINs von vorn (höchstens 4.000 je Lauf) | App zeigt einen Datenstand; ☰ → Datenstand & Betrieb nennt Status „veröffentlicht“ |
| Geplanter Betrieb | Bisher nur manuell gestartete Läufe | Lauf mit Auslöser „schedule“ um 06:00 Uhr, App zeigt den Herzschlag |
| Echte Datenquellen | Geprüft am 13.10.2026 (TR-Liste, OpenFIGI, Yahoo, Börsenkalender); EZB-Abruf neu in 1.1 und noch nicht in GitHub Actions gelaufen | Hinweis „EZB-Referenzkurse“ im Workflow „Datenquellen prüfen“ |
| Galaxy S25+ | Passphrase auf dem Gerät eingegeben und gespeichert; Ansichten mit Daten nur in der Emulation geprüft | Durchklicken nach der Checkliste in 01_Kurzanleitung_Handy, sobald ein Datenstand da ist |
| Kostenpflichtiger Kursanbieter | EODHD (19,99 USD/Monat) ist vorbereitet, aber nicht abgeschlossen | nur, wenn du dich dafür entscheidest: Secret `EODHD_API_KEY`, `anbieter.kurse: eodhd`, grüner Lauf |

## B. Grenzen der kostenlosen Datenbasis

| Punkt | Bedeutung | Abgeschlossen bzw. entschärft, wenn … |
|---|---|---|
| Yahoo Finance ist inoffiziell | Kein Vertrag, keine Zusage. Drosselung oder Sperre sind jederzeit möglich; die Abdeckung schwankt dann. Der Lauf bricht kontrolliert ab, setzt später fort und behält den letzten guten Stand. | Abdeckungsbilanz der ersten produktiven Läufe liegt vor; bei dauerhaften Sperren Entscheidung für einen lizenzierten Anbieter |
| **Yahoo: Schlusskurse vom 12.10.2026 fehlen** | Für Europa und Asien liefert Yahoo für diesen Montag Kerzen ohne Schlusskurs (geprüft an 14 Börsen; US-Werte vollständig). Zum Stichtag 12.10. gibt es deshalb keinen Datenstand. Solange der Kurs fehlt, zählt der Tag bei diesen Börsen als fehlende Sitzung: Zeiträume mit weniger als 98 % Sitzungen oder mit fehlendem Anfangskurs am 12.10. werden für diese Aktien nicht bewertet (mit Grund sichtbar). Die Läufe fragen die letzten 10 Tage täglich erneut ab und übernehmen nachgelieferte Kurse automatisch. | Yahoo liefert den Kurs nach (Workflow „Datenquellen prüfen“ grün) – oder Entscheidung für eine andere Quelle |
| TR-Listenparser | Mit dem echten PDF geprüft (13.10.2026: 11.560 ISINs, keine Prüfhinweise). Ändert TR das Layout, hält der Lauf die neue Liste zurück und rechnet mit der letzten geprüften weiter. | – (Prüfung läuft täglich) |
| Börsenkalender | Echte Bibliothek in GitHub Actions geprüft (4 von 4 Tests). Einige Börsen nutzen den Kalender einer Schwesterbörse (TSX Venture/CSE → TSX, KOSDAQ → KRX, NSE → BSE, Shenzhen → Shanghai); die App weist darauf hin. | – |
| Kapitalmaßnahmen | Splits kommen aus der Kursquelle; zusätzlich Sprung-, Einheiten- und Umsatzprüfungen sowie manuelle Prüfentscheidungen (`config/pruefungen.yaml`). Es gibt keine unabhängige Ereignisquelle für Spin-offs, Fusionen, Bezugsrechte oder ISIN-Wechsel. | optional: lizenzierte Ereignisdaten; bis dahin werden auffällige Fenster zurückgehalten statt als Sieger gezeigt |
| Live-/Intradaykurse | Bewusst nicht eingerichtet (kein passender Vertrag). Die App zeigt nur Tagesschlusskurse und sagt das. T73 entfällt. | nur mit einem lizenzierten Feed |
| Kursrendite in Notierungswährung | Ohne Dividenden, Kosten, Steuern und EUR-Wechselkurseffekt (so festgelegt). USD-Kurse werden nie als TR-Euro-Kurse ausgegeben. | optionale Erweiterung „EUR-Gesamtrendite“ (Auftrag Abschnitt 30) |
| Ø Tagesumsatz nur an der Referenzbörse | Gemessen wird das Volumen der einen Referenznotierung (bei US-Werten das zusammengefasste US-Volumen des Kursanbieters), nicht die Summe aller Handelsplätze. Eine Aktie, die vor allem anderswo gehandelt wird, kann deshalb unter 10 Mio. USD fallen. | optional: zweite Notierung je Aktie laden (mehr Abrufe) |
| Volumen-Bereinigung bei Splits | Yahoo meldet Volumen wie die Kurse splitbereinigt; überprüft ist das nur an Einzelfällen, nicht systematisch. Liegt ein Split innerhalb der 20 Sitzungen, gilt der Umsatz deshalb als nicht bestimmbar. | lizenzierte Daten mit dokumentierter Volumenbereinigung |
| Wechselkurse für den Umsatzfilter | EZB-Referenzkurse decken nicht alle Notierungswährungen ab – u. a. fehlen der Taiwan-Dollar (TWD) und der Chilenische Peso (CLP). Aktien in diesen Währungen kommen nicht in Ranking 2 (in Ranking 1 schon), mit Grund „Wechselkurs fehlt“. Fällt die EZB-Quelle aus, nutzt der Lauf die gespeicherten Kurse; sind sie älter als 5 Tage, gibt es keinen USD-Wert. | zusätzliche Kursquelle für diese Währungen |
| Abgleich zwischen Börsenplätzen nur für die ersten Plätze | Seit 1.2 werden die Aktien unter den ersten 10 Plätzen beider Rendite-Ranglisten mit einem zweiten Börsenplatz verglichen (bevorzugt Xetra, dann Frankfurt) und Abweichungen über 10 % gekennzeichnet. Aktien auf späteren Plätzen werden nicht abgeglichen. Vergleichskurse kommen vom selben Anbieter (Yahoo); bei wenig gehandelten Frankfurter Notierungen können veraltete Kurse einen Hinweis auslösen, der kein Fehler der Referenz ist. Ohne zweite Notierung bei der Identitätsquelle (häufig bei kleinen Werten) bleibt es bei „kein zweiter Börsenplatz“. Mit echten Daten noch nicht gelaufen. | erster echter Datenstand: ☰ → Datenstand & Betrieb → „Abgleich mit einem zweiten Börsenplatz“ nennt geprüfte und auffällige Aktien |

| Umschichtungs-Regel: nur heutige Aktien | Der Rückblick (bis 3 Jahre) rechnet mit Aktien, die heute in der TR-Liste stehen und heute mindestens 2 Mio. USD am Tag umsetzen. Insolvente, übernommene oder abgestürzte Aktien fehlen (Überlebensverzerrung) – das Ergebnis ist eher zu gut. Die App sagt das auf der Seite. | nur mit historischen Listen und Kursen auch nicht mehr gelisteter Aktien (lizenzierte Daten) |
| Umschichtungs-Regel: vereinfachte Ausführung, Kosten und Steuern | Ausführung zum Schlusskurs des ersten Handelstags nach der Entscheidung, Bruchteile, 1 € + 0,1 % je Order, Abgeltungsteuer mit Soli, Pauschbetrag und Verlusttopf; keine Dividenden, Quellensteuer, Kirchensteuer oder Umtauschkosten. | – (bewusst einfach, auf der Seite und in der Methodik genannt) |
| Umschichtungs-Regel: Langhistorie beim ersten Lauf | Der erste Lauf mit 1.3 lädt bis zu 3 Jahre Wochenwerte für alle Aktien ab 2 Mio. USD Tagesumsatz (gut 25–35 Minuten zusätzlich). Reicht die Zeit nicht, folgt der Rest im nächsten Lauf; bis dahin zeigt die App „Rückblick noch vorläufig“. Mit echten Daten noch nicht gelaufen. | App zeigt keinen Hinweis „Rückblick noch vorläufig“ mehr |
| Notierungen ohne Kursdaten | Im Lauf vom 13.10. lieferte Yahoo für 1.735 Notierungen keine Kurse (vor allem Toronto 960, Xetra 395, Stockholm 148, Singapur 82): die Kürzel aus der Identitätsquelle passten nicht zum Kursanbieter. Ab 1.4.1 werden Sammelcodes nicht mehr einer Börse zugeordnet, betroffene Identitäten neu geprüft und andere Kürzel derselben Börse gesucht (04_Datenquellen_und_Abdeckung, „Kürzel ohne Kursdaten“) – höchstens 300 Notierungen je Lauf, also über mehrere Tage. Mit echten Daten noch nicht gelaufen. Notierungen ohne Kurse unter jedem Kürzel bleiben mit Grund sichtbar. | Kurzbericht „Keine Kursdaten je Börse“ zeigt deutlich kleinere Zahlen; „Andere Kürzel … gefunden“ im Kurzbericht |

| Gruppenvergleich: kurze Zeiträume | Unter etwa drei Wochen gibt es weniger als 15 Tageskurse; Gleichmäßigkeit und damit 10 der 11 Gewichtungen sind dort „nicht berechenbar“ (in der Matrix 1–30 Tage meist die Zeilen 1–20). Bewusst so: keine Scores aus zwei Kursen. | – (Methodenregel) |
| Gruppenvergleich: Scores der Gruppe B | Perzentile innerhalb der Gruppe B; ein Score von B ist nicht mit A vergleichbar (die App sagt das an der Rangliste). Mit echten Daten noch nicht gelaufen. | erster Datenstand mit 1.4: Matrix A/B zeigt beide Gruppen |

## C. Bewusst nicht umgesetzt

| Punkt | Begründung |
|---|---|
| Übernahme der früheren Auswertung (HTML/ZIP, Kursstichtag 09.10.2026) | Die Dateien lagen nicht vor. **Altbestand-Übernahme nicht durchgeführt**; kein Vergleich mit dem alten Archiv, keine daraus übernommenen Gewinner. Mit den Dateien ist ein Methodenvergleich auf gleichem Inputstand möglich. |
| Rangänderung zum Vortag | Nicht angezeigt. Der Auftrag erlaubt sie nur bei gleicher Methodik und klarer Vergleichsdefinition; frühere Stände lassen sich stattdessen unverändert öffnen (☰ → Datenstand & Betrieb → Frühere Stände). |
| Hintergrundaktualisierung im Browser (Periodic Background Sync) | Der Browser bestimmt Zeitpunkt und Bedingungen selbst; die Pflichtberechnung läuft deshalb auf dem Server. |
| Benutzerkonten | Eine einzige Passphrase schützt die Daten; Watchlist und Einstellungen bleiben auf dem Gerät. Kein Login, keine Trade-Republic-Zugangsdaten. |
| iPhone/iPad | Ziel ist Android (S25+). Die Web-App funktioniert grundsätzlich auch in Safari, wurde dort aber nicht geprüft. |

## D. Technische Hinweise

| Punkt | Bedeutung | Abgeschlossen, wenn … |
|---|---|---|
| Lockdatei der App | `app/package-lock.json` wurde aus einer vorhandenen Installation erzeugt (kein Registry-Zugang) und enthält nur das Linux-x64-Paket von esbuild. In GitHub Actions läuft `npm ci` ohne Rückfall (geprüft 13.10.2026); auf Windows oder macOS kann es scheitern – dort `npm install` verwenden. | – |
| GitHub-Zeitpläne | GitHub kann geplante Läufe verzögern oder bei hoher Last auslassen. Gegenmittel: drei Wiederholungen, Herzschlag-Anzeige in der App, E-Mail bei rotem Lauf. Eine unabhängige Überwachung von außen gibt es nicht. | – (Betriebsrisiko, sichtbar gemacht) |
| Inaktivität | GitHub schaltet Zeitpläne nach 60 Tagen ohne Repository-Aktivität ab; der Lauf schreibt deshalb spätestens alle 45 Tage einen Aktivitätsnachweis. Ob GitHub diesen Nachweis in jedem Fall als Aktivität wertet, ist nicht garantiert. | nach mehr als 60 Tagen läuft der Zeitplan noch; sonst Actions → Täglicher Lauf → Enable workflow |
| Öffentliches Repository | Für kostenloses GitHub Pages nötig. Code und App-Hülle sind öffentlich, alle Daten verschlüsselt. Ein privates Repository mit Pages kostet Geld (GitHub Pro) und wäre nur nach deiner Freigabe möglich. | – |
| Größe | Ein Datenstand ≈ 97 MB (gemessen mit 1.1.0, 11.500 synthetische Aktien); 5 auf der Website ≈ 485 MB (Grenze von GitHub Pages: 1 GB). | – |
| Barrierefreiheit | Automatisch geprüft: Beschriftung aller Bedienelemente, Mindestgröße 44 px, Tastaturbedienung der Diagramme. Kein Test mit Screenreader auf dem Gerät. | Test mit TalkBack auf dem S25+ |
