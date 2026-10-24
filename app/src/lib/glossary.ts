/* Begriffe der App in einfachem Deutsch (ab 1.16): eine Erklärung je Begriff, mit Beispiel.
 * Genutzt von der Hilfe (☰ → Hilfe und Begriffe) und von <Term> an den Stellen, an denen ein Begriff vorkommt.
 * Regeln: kurze Sätze, ein Wort je Sache, erst die Bedeutung, dann die Rechnung. */

export interface GlossaryEntry {
  /** Anker für Links: #/hilfe?begriff=<id> */
  id: string;
  term: string;
  /** Weitere Wörter, unter denen man den Begriff sucht */
  also?: string[];
  /** Ein bis drei kurze Sätze: was es bedeutet */
  text: string;
  /** Ein Zahlenbeispiel */
  example?: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  {
    id: 'auffaellig',
    term: 'Auffällige: kaum Umsatz, Einzelsprung',
    also: ['kaum Umsatz', 'Einzelsprung', 'ausblenden'],
    text: 'Zwei Kennzeichen in den Rendite-Ranglisten. „Kaum Umsatz“: Die Aktie wird im Schnitt für weniger als 1 Mio. US-Dollar am Tag gehandelt. Dann können schon kleine Käufe den Kurs stark bewegen. „Einzelsprung“: Der Anstieg stammt fast nur von einem einzigen Tag. Mit dem Schalter „Auffällige ausblenden“ verschwinden diese Zeilen. Die Platznummern der übrigen Aktien bleiben gleich.',
    example: 'Eine Aktie steigt in 30 Tagen um 40 %, davon 35 % an einem einzigen Tag. Sie bekommt das Kennzeichen „Einzelsprung“.',
  },
  {
    id: 'beitrag',
    term: 'Beitrag in Prozentpunkten (PP)',
    also: ['PP', 'Prozentpunkte', 'Depotrendite'],
    text: 'Zeigt in einem Musterdepot, wie viel eine Aktie zur Rendite des ganzen Depots beigetragen hat. Alle Beiträge zusammen ergeben die Depotrendite. Prozentpunkte sind der einfache Abstand zwischen zwei Prozentzahlen.',
    example: 'Die Aktie hat am Anfang 10 % Anteil am Depot und steigt um 30 %. Ihr Beitrag ist 10 % × 30 % = 3 Prozentpunkte.',
  },
  {
    id: 'datenstand',
    term: 'Datenstand',
    also: ['Stand', 'Snapshot', 'neuer Stand'],
    text: 'Ein fertig berechneter Satz aller Ranglisten zu einem Kursstand. Die App zeigt immer genau einen Datenstand. Ist ein neuerer da, bietet sie ihn mit einem Knopf an. Deine Ansicht ändert sich erst, wenn du wechselst.',
  },
  {
    id: 'fehlende-kurstage',
    term: 'Fehlende Kurstage',
    also: ['Lücke', 'nicht berechenbar', 'Startkurs fehlt', 'Börsentage ohne Kurs'],
    text: 'An manchen Börsentagen liefert der Kursanbieter für eine Aktie keinen Schlusskurs. Die App zählt so einen Tag als fehlend: Sie setzt keinen Ersatzkurs ein und rechnet nicht mit null. Ein Zeitraum bleibt bewertbar, wenn Start- und Endkurs da sind und höchstens jeder fünfte Börsentag fehlt. Ein einzelner fehlender Tag ist immer erlaubt. Sonst nennt die Aktienseite den Grund mit den Zahlen des Zeitraums.',
    example: '30 Tage mit 23 Börsentagen: 19 Kurse reichen (4 fehlen, 17 %), 18 Kurse nicht (5 fehlen, 22 %).',
  },
  {
    id: 'gesamtwertung',
    term: 'Gesamtwertung (0 bis 100)',
    also: ['Potenzial-Liste', 'Kandidaten'],
    text: 'Die Zahl auf der Seite „Potenzial“. Sie fasst vier Teile zusammen. Am meisten zählen regelmäßiges Steigen in 30, 60 und 90 Tagen (35 %) und der Abstand zum Kursziel der Analysten (35 %). Dazu kommen Aufmerksamkeit und Schwung (15 %) sowie Qualität (15 %). Ab 65 gilt sie als stark, ab 50 als mittel. Sie ordnet nur und sagt nichts über die Zukunft.',
    example: 'Steig-Konstanz 80 Punkte, Kursziel 60, Schwung 50, Qualität 40: 0,35 × 80 + 0,35 × 60 + 0,15 × 50 + 0,15 × 40 = 62,5 – also „mittel“.',
  },
  {
    id: 'gewichtung',
    term: 'Gewichtung, zum Beispiel 60/40',
    also: ['60/40', '50/50', '40/60', '0/100', '100/0'],
    text: 'Legt fest, wie stark Gleichmäßigkeit und Kursrendite den Rangscore bestimmen. Die erste Zahl gehört immer zur Gleichmäßigkeit, die zweite zur Kursrendite. „Nur Kursrendite“ (0/100) ordnet allein nach dem Anstieg. „Nur Gleichmäßigkeit“ (100/0) allein nach der Gleichmäßigkeit.',
    example: '60/40 heißt: 60 % Gleichmäßigkeit und 40 % Kursrendite.',
  },
  {
    id: 'gleichmaessigkeit',
    term: 'Gleichmäßigkeit (R²)',
    also: ['R²', 'R2', 'Bestimmtheitsmaß', 'gleichmäßig gestiegen'],
    text: 'Zeigt, wie nah die Schlusskurse im Zeitraum an einer geraden Linie liegen. 1 heißt: alle Kurse liegen genau auf einer Linie. 0 heißt: keine Linie erkennbar. R² sagt nichts über die Richtung. Deshalb kommen in die Rangliste mit Gleichmäßigkeit nur Aktien, die im Zeitraum gestiegen sind. Berechnet wird R² erst ab 15 Tageskursen, also ab etwa drei Wochen.',
    example: 'Aktie A steigt fast jeden Tag ein kleines Stück: R² 0,95. Aktie B springt auf und ab und endet trotzdem 20 % höher: R² 0,30.',
  },
  {
    id: 'gleichstand',
    term: 'Gleichstand',
    also: ['gleicher Rangscore', 'gleichauf', 'Reihenfolge'],
    text: 'Zwei Aktien haben rechnerisch denselben Rangscore. Dann steht die mit der höheren Kursrendite vorn, bei gleicher Rendite die mit der kleineren ISIN. Die App vergleicht dabei exakt und rundet nicht. Verschiedene Rangscores bleiben verschieden, auch wenn sie mit einer Nachkommastelle gleich aussehen. In der Rangliste steht dann „gleichauf“.',
    example: 'Gewichtung 60/40: Aktie X hat die Perzentile G 50 und R 90, Aktie Y G 80 und R 45. Beide Rangscores sind 66. X ist stärker gestiegen und steht vorn.',
  },
  {
    id: 'gruppe',
    term: 'Gruppe A und Gruppe B',
    also: ['Aktiengruppe', 'Gruppe A', 'Gruppe B', 'handelbar'],
    text: 'Gruppe A enthält alle vergleichbaren Aktien. Gruppe B enthält nur gut gehandelte Aktien: Ø Tagesumsatz ab 10 Mio. US-Dollar. Gruppe B ist ein Teil von Gruppe A. Die Rangscores beider Gruppen sind nicht vergleichbar, weil jede Gruppe nur in sich verglichen wird.',
    example: 'Eine kleine Aktie mit 0,3 Mio. US-Dollar Umsatz am Tag steht nur in Gruppe A.',
  },
  {
    id: 'isin',
    term: 'ISIN',
    also: ['Kennnummer', 'WKN'],
    text: 'Die internationale Kennnummer einer Aktie: 12 Zeichen, zwei Buchstaben für das Land, am Ende eine Prüfziffer. Mit der ISIN findest du dieselbe Aktie auch in der Trade-Republic-App. Tippe auf das Kopier-Symbol neben der ISIN, um sie zu kopieren.',
    example: 'DE0007164600 ist die ISIN einer deutschen Aktie.',
  },
  {
    id: 'kalendertage',
    term: 'Kalendertage und Handelstage',
    also: ['Zeitraum', 'Tage', 'Handelstag'],
    text: 'Zeiträume zählen Kalendertage, also mit Wochenenden und Feiertagen. Handelstage sind nur die Tage, an denen die Börse offen ist. Fällt der Starttag auf ein Wochenende, zählt der letzte Schlusskurs davor.',
    example: '30 Kalendertage sind gut 20 Handelstage.',
  },
  {
    id: 'kursrendite',
    term: 'Kursrendite',
    also: ['Rendite', 'Anstieg'],
    text: 'Um wie viel Prozent der Kurs im Zeitraum gestiegen oder gefallen ist. Ohne Dividenden, Gebühren und Steuern, in der Währung der Börse.',
    example: 'Startkurs 50 €, Schlusskurs 55 €: (55 − 50) ÷ 50 = +10 %.',
  },
  {
    id: 'kursstand',
    term: 'Kursstand (Stichtag)',
    also: ['Stichtag', 'Kursstichtag'],
    text: 'Der Börsentag, dessen Schlusskurse die Ranglisten verwenden. Alle Zeiträume enden an diesem Tag. Der Kursstand steht oben rechts in der App.',
    example: 'Kursstand 23.10.2026 und Zeitraum 30 Tage: Verglichen wird der Schlusskurs vom 23.09.2026 (oder vom Börsentag davor) mit dem vom 23.10.2026.',
  },
  {
    id: 'kursziel',
    term: 'Kursziel und Potenzial',
    also: ['Potenzial', 'Analysten', 'Abstand zum Kursziel'],
    text: 'Das Kursziel ist eine Schätzung von Analysten, wo der Kurs in etwa 12 Monaten stehen könnte. Das Potenzial ist der Abstand zwischen heutigem Kurs und dem durchschnittlichen Kursziel. Kursziele sind Meinungen. Sie sind oft zu optimistisch und ändern sich häufig.',
    example: 'Kurs 40 €, durchschnittliches Kursziel 50 €: Potenzial (50 − 40) ÷ 40 = +25 %.',
  },
  {
    id: 'musterdepot',
    term: 'Musterdepot',
    also: ['Depot', 'Rückblick-Rechnung', 'Zehnerdepot'],
    text: 'Eine Rechnung im Rückblick: Wie hätte sich ein Depot entwickelt, wenn man am Anfang des Zeitraums jede Aktie mit dem gleichen Betrag gekauft und dann nichts mehr verändert hätte? Die Aktien sind mit heutigem Wissen ausgewählt. Deshalb sieht das Ergebnis fast immer besser aus, als ein echtes Depot gewesen wäre. Gebühren, Steuern und Dividenden sind nicht enthalten.',
    example: '1.000 USD auf 10 Aktien verteilt, je 100 USD. Steigen sie im Schnitt um 20 %, ist das Depot am Ende 1.200 USD wert.',
  },
  {
    id: 'passphrase',
    term: 'Passphrase',
    also: ['Kennwort', 'Passwort', 'Zugangsschlüssel', 'Schlüssel', 'entsperren'],
    text: 'Das Kennwort, mit dem die Kursdaten verschlüsselt sind. Du gibst es auf jedem Gerät nur einmal ein. Die App speichert danach einen daraus berechneten Schlüssel, nicht die Passphrase selbst. Unter ☰ → Einstellungen kannst du den Schlüssel wieder löschen.',
  },
  {
    id: 'perzentil',
    term: 'Perzentil',
    also: ['Prozentrang'],
    text: 'Zeigt, wo eine Aktie im Vergleich zu den anderen steht: 0 ist die schlechteste, 100 die beste. Gleiche Werte bekommen das gleiche Perzentil.',
    example: 'Rendite-Perzentil 80 heißt: etwa 80 % der verglichenen Aktien sind weniger gestiegen.',
  },
  {
    id: 'rangscore',
    term: 'Rangscore (0 bis 100)',
    also: ['Score', 'Platz', 'Rangliste'],
    text: 'Die Zahl, nach der die Rangliste mit Gleichmäßigkeit sortiert ist. Höher ist besser. Sie verbindet die Perzentile von Gleichmäßigkeit und Kursrendite nach der gewählten Gewichtung.',
    example: 'Gewichtung 60/40, Gleichmäßigkeit-Perzentil 50, Rendite-Perzentil 90: 0,6 × 50 + 0,4 × 90 = 66.',
  },
  {
    id: 'rsi',
    term: 'RSI (überkauft)',
    also: ['überkauft', 'überverkauft', 'Relative-Stärke-Index'],
    text: 'Der Relative-Stärke-Index vergleicht die Kursgewinne der letzten 14 Tage mit den Verlusten. Skala 0 bis 100. Über 70 gilt eine Aktie als „überkauft“, also stark gestiegen. Unter 30 als „überverkauft“. Das heißt nicht, dass der Kurs jetzt fallen oder steigen muss.',
    example: 'RSI 78: In den letzten 14 Tagen überwogen die Gewinne deutlich.',
  },
  {
    id: 'schlusskurs',
    term: 'Schlusskurs',
    also: ['Schlusskurs 09.10.', 'letzter Schlusskurs'],
    text: 'Der letzte Kurs eines Handelstags an der Börse, so wie ihn der Kursanbieter meldet. Steht in einer Zeile „Schlusskurs“ mit einem älteren Datum, fehlte der Kurs vom Kursstand-Tag, zum Beispiel wegen eines Feiertags an dieser Börse. Dann zählt der letzte Schlusskurs davor.',
    example: '„Schlusskurs 09.10.“ bei Kursstand 12.10.: Für diese Aktie gab es am 12.10. keinen Kurs, gerechnet wird mit dem vom 09.10.',
  },
  {
    id: 'steigkonstanz',
    term: 'Steig-Konstanz',
    also: ['Anstiegstage', '▲'],
    text: 'Zählt, an wie vielen Handelstagen der Schlusskurs höher war als am Tag davor – über 30, 60 und 90 Tage. Daraus entstehen 0 bis 100 Punkte: 40 % Anstiegstage geben 0 Punkte, 65 % und mehr geben 100 Punkte.',
    example: '▲ 15/21 heißt: an 15 von 21 Handelstagen gestiegen. Das sind 71 %, also volle Punkte.',
  },
  {
    id: 'tagesumsatz',
    term: 'Ø Tagesumsatz',
    also: ['Umsatz', 'Liquidität', 'gehandelt'],
    text: 'Für wie viel Geld die Aktie im Schnitt an einem Börsentag gehandelt wurde: Schlusskurs mal Stückzahl, über die letzten 20 Börsentage, umgerechnet in US-Dollar. Ist der Umsatz klein, können schon wenige Käufe den Kurs stark bewegen, und ein Kauf zum angezeigten Kurs ist oft nicht möglich.',
    example: 'Kurs 20 USD, im Schnitt 600.000 Stück am Tag: Ø Tagesumsatz 12 Mio. USD.',
  },
  {
    id: 'teilstand',
    term: 'Teilstand',
    also: ['unvollständig', 'Börse fehlt'],
    text: 'Ein Datenstand, bei dem der Kursanbieter für einzelne Börsen noch keine Schlusskurse geliefert hat. Die App nennt diese Börsen. Ihre Aktien zählen mit dem letzten Schlusskurs, wenn er höchstens eine Börsensitzung alt ist. Sonst fehlen sie in diesem Stand. Der nächste Lauf ergänzt nachgelieferte Kurse von selbst.',
  },
  {
    id: 'top-nach-zahlen',
    term: 'Top nach Zahlen (Punkte)',
    also: ['Top 3', 'Punkte', 'Rangfolge'],
    text: 'Eine feste Punkteregel für die Top 3 auf der Startseite. Bis zu 40 Punkte für „oft vorne“ in den Ranglisten, 25 für regelmäßiges Steigen, 20 für den Abstand zum Kursziel und 15 für steigendes Volumen. Bei kleinem Börsenwert gibt es Abzug. Einen Platz bekommen nur gut gehandelte Aktien (Gruppe B).',
    example: 'Oft vorne 34 + steigt stetig 25 + Analysten 3 + Volumen 12 = 74 Punkte.',
  },
  {
    id: 'umschichtung',
    term: 'Umschichtungs-Regel',
    also: ['Regel', 'Umschichten', 'Rückblick'],
    text: 'Eine feste Rechenregel zum Ausprobieren. Sie hält die 5 gut gehandelten Aktien mit dem stärksten Anstieg der letzten 13 Wochen zu gleichen Teilen. Einmal im Monat prüft sie, ob sie tauscht. Die App zeigt, welche Aktien die Regel heute halten würde und wie sie in den letzten Jahren nach Kosten und Steuern abgeschnitten hätte. Das ist ein Rückblick, kein Versprechen.',
  },
  {
    id: 'vergleichsfeld',
    term: 'Vergleichsfeld',
    also: ['verglichen', 'Teiluniversum', 'vergleichbar'],
    text: 'Die Aktien, mit denen in einer Rangliste verglichen wird. In der reinen Rendite-Rangliste sind das alle Aktien mit gültigen Kursen im Zeitraum. In der Rangliste mit Gleichmäßigkeit nur die gleichmäßig gestiegenen: mindestens 15 Tageskurse, positive Rendite und steigender Trend.',
    example: '„122 von 188 Aktien“ heißt: 188 Aktien haben eine Rendite im Zeitraum, 122 davon sind gleichmäßig gestiegen und haben einen Rangscore.',
  },
  {
    id: 'watchlist',
    term: 'Watchlist',
    also: ['Stern', 'merken', 'Merkliste'],
    text: 'Deine Merkliste in dieser App. Tippe bei einer Aktie auf den Stern ☆, um sie zu merken. Die Watchlist liegt nur auf diesem Gerät. Unter ☰ → Einstellungen kannst du sie als Datei sichern und auf ein anderes Gerät übertragen. Mit der Watchlist bei Trade Republic ist sie nicht verbunden.',
  },
  {
    id: 'rueckblick',
    term: 'Rückblick (Art der Angabe)',
    also: ['historisch', 'vergangene Kurse', 'Art der Angaben'],
    text: 'Zahlen aus der Vergangenheit: Kurse bis zum Kursstand oder gemeldete Geschäftszahlen. Sie zeigen, was war, und sagen nichts darüber, wie es weitergeht. Die App kennzeichnet sie mit „Rückblick“.',
    example: 'Kursrendite 30 Tage +12 %: Der Kurs stieg vom Schlusskurs vor 30 Tagen bis zum Kursstand um 12 %.',
  },
  {
    id: 'rangbewertung',
    term: 'Rangbewertung (Art der Angabe)',
    also: ['Platz', 'Rang', 'Punkte', 'Art der Angaben'],
    text: 'Ein Platz oder eine Punktzahl im Vergleich mit den anderen Aktien – nach einer festen Regel dieser App aus Rückblick-Zahlen (und bei „Top nach Zahlen“ auch Kurszielen). Eine Rangbewertung ist keine Vorhersage und keine Empfehlung.',
    example: 'Platz 1 von 412 bei 60/40: Diese Aktie hat in dieser Auswahl den höchsten Rangscore – im Rückblick, nicht für die Zukunft.',
  },
  {
    id: 'prognose',
    term: 'Prognose Dritter (Art der Angabe)',
    also: ['Kursziel', 'Analysten', 'Empfehlung', 'Vorhersage', 'Art der Angaben'],
    text: 'Einschätzungen anderer, vor allem von Analysten: Kursziele, Kaufen/Halten/Verkaufen, Ausblicke. Die App gibt sie nur wieder und macht selbst keine Prognose. Prognosen können falsch sein und sind oft zu optimistisch.',
    example: 'Ø Kursziel 120 € bei einem Kurs von 100 €: Die Analysten erwarten im Schnitt +20 % in etwa 12 Monaten – eine Erwartung, kein Ergebnis.',
  },
  {
    id: 'angaben-dritter',
    term: 'Angaben Dritter (Art der Angabe)',
    also: ['Nachrichten', 'Community', 'Stimmung', 'Art der Angaben'],
    text: 'Meldungen und Stimmungen aus anderen Quellen, zum Beispiel Nachrichten-Überschriften oder Beiträge einer Community. Die App übernimmt sie ungeprüft und zählt nur, ob sie eher positiv oder negativ klingen.',
  },
  {
    id: 'zwischenstand',
    term: 'Zwischenstand',
    also: ['vorläufig', 'aktuelle Kurse', 'Intraday'],
    text: 'Vorläufige Ranglisten während eines Börsentags. Sie nutzen die zuletzt gemeldeten Kurse, die etwa 15 bis 20 Minuten verzögert sind. Ein Zwischenstand entsteht nur, wenn du ihn mit „Jetzt aktualisieren“ startest. Der nächste Stand mit Schlusskursen ersetzt ihn.',
  },
];

const BY_ID = new Map(GLOSSARY.map((entry) => [entry.id, entry]));

export function glossaryEntry(id: string): GlossaryEntry | undefined {
  return BY_ID.get(id);
}

/** Einträge, deren Begriff, Synonyme oder Text die Suche enthalten (ohne Groß-/Kleinschreibung). */
export function searchGlossary(query: string): GlossaryEntry[] {
  const q = query.trim().toLowerCase();
  const sorted = [...GLOSSARY].sort((a, b) => a.term.localeCompare(b.term, 'de'));
  if (!q) return sorted;
  const hit = (s: string) => s.toLowerCase().includes(q);
  const strong = sorted.filter((e) => hit(e.term) || (e.also ?? []).some(hit));
  const weak = sorted.filter((e) => !strong.includes(e) && (hit(e.text) || hit(e.example ?? '')));
  return [...strong, ...weak];
}
