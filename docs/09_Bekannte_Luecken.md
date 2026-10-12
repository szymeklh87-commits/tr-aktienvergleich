# Bekannte Lücken und offene Punkte

Stand 12.10.2026. Zu jedem Punkt: was fehlt und welches überprüfbare Ergebnis ihn abschließt. „Fertig“ heißt in diesem Projekt nur, was tatsächlich ausgeführt und geprüft wurde (07_Testbericht).

## A. Braucht deinen Zugang, deine Freigabe oder dein Gerät

| Punkt | Was fehlt | Abgeschlossen, wenn … |
|---|---|---|
| Bereitstellung | GitHub-Repository, Secret `DATA_PASSPHRASE`, Pages-Einstellung (02_Einrichtung, Schritte 1–4). In dieser Sitzung gab es keinen GitHub-Zugang. | „Täglicher Lauf“ ist grün und die Pages-Adresse `https://<dein-name>.github.io/tr-aktienvergleich/` öffnet die App |
| Täglicher Betrieb | Kein echter geplanter Lauf bisher – es gibt deshalb auch noch keinen „letzten erfolgreichen Lauf“ und keinen echten Kursstichtag | App zeigt unter ☰ → Datenstand & Betrieb einen geplanten Lauf um 06:00 mit Status „veröffentlicht“ oder „geprüft“ |
| Echte Datenquellen | TR-Liste, OpenFIGI und Yahoo waren in der Entwicklungsumgebung gesperrt | Workflow „Datenquellen prüfen“ grün; `datenquellen-bericht.json` nennt die ISIN-Zahl des Aktienabschnitts und erfolgreiche Beispielabrufe |
| Galaxy S25+ | Nur Emulation getestet (Bildschirmgröße, Touch); kein echtes Gerät | Installation über Chrome oder Samsung Internet, Entsperren, Start, Ranking, Einzelchart, Raster und Offline-Anzeige auf dem Gerät geöffnet (Checkliste in 01_Kurzanleitung_Handy) |
| Kostenpflichtiger Kursanbieter | EODHD (19,99 USD/Monat) ist vorbereitet, aber nicht abgeschlossen | nur, wenn du dich dafür entscheidest: Secret `EODHD_API_KEY`, `anbieter.kurse: eodhd`, grüner Lauf |

## B. Grenzen der kostenlosen Datenbasis

| Punkt | Bedeutung | Abgeschlossen bzw. entschärft, wenn … |
|---|---|---|
| Yahoo Finance ist inoffiziell | Kein Vertrag, keine Zusage. Drosselung oder Sperre sind jederzeit möglich; die Abdeckung schwankt dann. Der Lauf bricht kontrolliert ab, setzt später fort und behält den letzten guten Stand. | Abdeckungsbilanz der ersten produktiven Läufe liegt vor; bei dauerhaften Sperren Entscheidung für einen lizenzierten Anbieter |
| TR-Listenparser | Nur mit erzeugten PDFs im erwarteten Aufbau getestet; das echte PDF konnte nicht geladen werden. Ändert TR das Layout, hält der Lauf die neue Liste zurück und rechnet mit der letzten geprüften weiter – beim allerersten Lauf gibt es aber noch keine. | Erster Lauf liest den Aktienabschnitt mit plausibler Größe (frühere Auswertung: 11.560 ISINs) und ohne Prüfhinweis |
| Börsenkalender | `exchange_calendars` lief nur in der Logik mit Testkalendern; die echte Bibliothek prüft erst der Workflow „Prüfung“. Einige Börsen nutzen den Kalender einer Schwesterbörse (TSX Venture/CSE → TSX, KOSDAQ → KRX, NSE → BSE, Shenzhen → Shanghai); die App weist darauf hin. | `tests.live.test_calendars_live` grün in GitHub Actions |
| Kapitalmaßnahmen | Splits kommen aus der Kursquelle; zusätzlich Sprung-, Einheiten- und Umsatzprüfungen sowie manuelle Prüfentscheidungen (`config/pruefungen.yaml`). Es gibt keine unabhängige Ereignisquelle für Spin-offs, Fusionen, Bezugsrechte oder ISIN-Wechsel. | optional: lizenzierte Ereignisdaten; bis dahin werden auffällige Fenster zurückgehalten statt als Sieger gezeigt |
| Live-/Intradaykurse | Bewusst nicht eingerichtet (kein passender Vertrag). Die App zeigt nur Tagesschlusskurse und sagt das. T73 entfällt. | nur mit einem lizenzierten Feed |
| Kursrendite in Notierungswährung | Ohne Dividenden, Kosten, Steuern und EUR-Wechselkurseffekt (so festgelegt). | optionale Erweiterung „EUR-Gesamtrendite“ (Auftrag Abschnitt 30) |

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
| Lockdatei der App | `app/package-lock.json` wurde aus einer vorhandenen Installation erzeugt (kein Registry-Zugang) und enthält nur das Linux-x64-Paket von esbuild. `npm ci` auf Windows oder macOS kann deshalb scheitern; dort `npm install` verwenden. Der Workflow „Prüfung“ fällt bei Bedarf auf `npm install` zurück. | erster grüner Workflow „Prüfung“ |
| GitHub-Zeitpläne | GitHub kann geplante Läufe verzögern oder bei hoher Last auslassen. Gegenmittel: drei Wiederholungen, Herzschlag-Anzeige in der App, E-Mail bei rotem Lauf. Eine unabhängige Überwachung von außen gibt es nicht. | – (Betriebsrisiko, sichtbar gemacht) |
| Inaktivität | GitHub schaltet Zeitpläne nach 60 Tagen ohne Repository-Aktivität ab; der Lauf schreibt deshalb spätestens alle 45 Tage einen Aktivitätsnachweis. Ob GitHub diesen Nachweis in jedem Fall als Aktivität wertet, ist nicht garantiert. | nach mehr als 60 Tagen läuft der Zeitplan noch; sonst Actions → Täglicher Lauf → Enable workflow |
| Öffentliches Repository | Für kostenloses GitHub Pages nötig. Code und App-Hülle sind öffentlich, alle Daten verschlüsselt. Ein privates Repository mit Pages kostet Geld (GitHub Pro) und wäre nur nach deiner Freigabe möglich. | – |
| Größe | Ein Datenstand ≈ 74 MB (gemessen, 11.500 synthetische Aktien); 5 auf der Website ≈ 370 MB (Grenze von GitHub Pages: 1 GB). | – |
| Barrierefreiheit | Automatisch geprüft: Beschriftung aller Bedienelemente, Mindestgröße 44 px, Tastaturbedienung der Diagramme. Kein Test mit Screenreader auf dem Gerät. | Test mit TalkBack auf dem S25+ |
