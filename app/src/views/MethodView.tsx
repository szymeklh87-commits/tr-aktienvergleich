import { KIND_INFO, KindChips } from '../components/explain';
import { sessionRuleText, volumeRuleText } from '../lib/codes';
import { venueDayRule, venueLimitSentence } from '../lib/venue';
import { useApp } from '../state/AppState';

function money(value: number): string {
  return `${(value / 1e6).toLocaleString('de-DE', { maximumFractionDigits: 1 })} Mio. USD`;
}

export function MethodView() {
  const { manifest } = useApp();
  const turnover = manifest?.turnover;
  const venue = manifest?.venue_check ?? null;
  const method = (manifest?.method ?? {}) as Record<string, unknown>;
  const minTrend = Number(method.min_obs_trend ?? 15);
  const anchor = Number(method.anchor_max_gap_days ?? 7);
  const jump = Number(method.jump_factor ?? 3);
  const sessionRule = sessionRuleText(method);
  const volumeRule = volumeRuleText(method);
  const rule = (method.rotation ?? {}) as Record<string, number | number[] | string>;
  const num = (key: string, fallback: number): number => (typeof rule[key] === 'number' ? (rule[key] as number) : fallback);
  const pctText = (value: number, digits = 0) => `${(value * 100).toLocaleString('de-DE', { maximumFractionDigits: digits })} %`;

  return (
    <article className="prose">
      <div className="notice notice-info method-short">
        <p className="notice-title">Kurz gesagt</p>
        <div className="notice-body">
          <p>
            Diese Seite ist die genaue Rechenvorschrift zum Nachprüfen. Für den Einstieg reicht die <a href="#/hilfe">Hilfe mit Begriffen und einem
            Rechenbeispiel</a>. Das Wichtigste in drei Sätzen: Für jeden Zeitraum von 1 bis 90 Tagen vergleicht die App den Schlusskurs am Anfang mit dem am Ende
            (Kursrendite). Sie misst, wie gerade der Kurs dabei gestiegen ist (Gleichmäßigkeit R²). Beides zusammen ergibt je nach Gewichtung den Rangscore, nach dem die
            Ranglisten sortiert sind.
          </p>
        </div>
      </div>
      <p className="lede">
        Die App beschreibt, was in der Vergangenheit passiert ist, und ordnet es nach festen Regeln. Sie gibt keine Anlageberatung und macht selbst keine Prognose; Kursziele
        und Empfehlungen stammen von Analysten und sind als „Prognose Dritter“ gekennzeichnet. Die Umschichtungs-Regel zeigt nur, was eine feste Rechenregel täte. Methodenversion:{' '}
        {manifest?.versions.method ?? 'tr-methode-1.7.0'}
        {manifest?.versions.reference_model ? `; übernommene Regeln des Ausgangsmodells ${manifest.versions.reference_model}` : ''}.
      </p>

      <h2>Vier Arten von Angaben</h2>
      <p>Über jeder Liste und jedem Abschnitt steht, welche Art von Angabe du siehst:</p>
      <ul className="explain-kinds">
        {(['rueckblick', 'rang', 'prognose', 'dritte'] as const).map((kind) => (
          <li key={kind}>
            <KindChips kinds={[kind]} label={KIND_INFO[kind].label} /> {KIND_INFO[kind].text}
          </li>
        ))}
      </ul>

      <h2>Zeitraum: 1 bis 90 Kalendertage</h2>
      <p>
        Alle Zeiträume enden am selben Kursstichtag D: dem jüngsten Handelstag, dessen Schlusskurse an allen an diesem Tag geöffneten Börsen bereits feststehen. „30 Tage“ heißt 30 Kalendertage zurück. Als Startkurs gilt der Schlusskurs der letzten Börsensitzung am oder vor diesem Ziel-Startdatum, höchstens {anchor} Kalendertage
        früher. Fehlt an dieser Sitzung ein Kurs, wird nicht auf einen älteren Kurs ausgewichen; der Zeitraum ist dann für diese Aktie nicht berechenbar.
      </p>
      <p>Wochenenden und Feiertage führen dazu, dass benachbarte Kalenderzeiträume manchmal dieselben tatsächlichen Start- und Endkurse haben. Jede Zeile nennt deshalb den tatsächlichen Beginn und das Ende.</p>

      <h2>Kursrendite</h2>
      <p className="formula">r = Schlusskurs am Ende ÷ Schlusskurs am Start − 1</p>
      <p>
        Gerechnet wird in der Notierungswährung der Referenzbörse, splitbereinigt, ohne Dividenden, Gebühren, Steuern und ohne Wechselkurseffekt. Ein Kurs in Pence (GBp) bleibt in Pence; die Rendite ist davon unabhängig. Für die reine Rendite reichen zwei echte Schlusskurse.
      </p>

      <h2>Zwei Rendite-Ranglisten</h2>
      <p>
        <strong>Höchste Kursrendite:</strong> alle Aktien mit veröffentlichter Kursrendite (Feld V), sortiert nur nach Kursrendite – das ist die Gewichtung 0 % Gleichmäßigkeit / 100 % Kursrendite. Es gibt keine
        Mindestgrenze für Aktienpreis, Börsenwert oder Umsatz; die Datenqualitätsprüfungen gelten trotzdem. Aktien mit einem Ø Tagesumsatz unter {money(turnover?.sehr_niedrig_usd ?? 1_000_000)} sind als
        „Kaum Umsatz“ gekennzeichnet, Zeiträume, in denen ein einzelner Handelstag mehr als die Hälfte der Kursbewegung erklärt, als „Einzelsprung“.
      </p>
      <p>
        <strong>Auffällige ausblenden</strong> (ab Version 1.14, Schalter in den Ranglisten und unter Einstellungen): blendet Aktien mit kaum Umsatz (oder nicht bestimmbarem Umsatz) und Zeiträume mit
        Einzelsprung aus. Gerechnet wird nichts neu: Plätze und Rangscores bleiben die der vollständigen Rangliste, ein Spitzenreiter ohne Auffällige kann also „Platz 3“ tragen.
      </p>
      <p>
        <strong>Höchste Kursrendite – Ø Tagesumsatz mindestens {money(turnover?.schwelle_usd ?? 10_000_000)}:</strong> dieselben Kurse, Zeiträume, derselbe Kursstichtag und dieselbe Renditeformel. Aufgenommen
        werden nur Aktien, deren Ø Tagesumsatz bestimmt ist und die Schwelle erreicht. Der Umsatz ist ein Aufnahmefilter, kein Sortierkriterium und kein zweiter Renditewert – die Reihenfolge ist exakt die der
        ersten Liste ohne die übrigen Aktien.
      </p>
      <p className="formula">Ø Tagesumsatz = Mittelwert über die letzten {turnover?.sitzungen ?? 20} abgeschlossenen Sitzungen von (Schlusskurs × gemeldetes Volumen)</p>
      <ul>
        <li>Kurs und Volumen stammen von derselben Notierung an der Referenzbörse, beide splitbereinigt. Liegt ein Split oder eine Zusammenlegung innerhalb der Sitzungen, gilt der Umsatz als nicht bestimmbar.</li>
        <li>Mindestens {turnover?.min_sitzungen_mit_umsatz ?? 16} der {turnover?.sitzungen ?? 20} Sitzungen brauchen ein positives Volumen. Fehlende Tage zählen nicht als null, sie werden ausgelassen.</li>
        <li>
          Andere Währungen werden nur für diesen Filter indikativ in US-Dollar umgerechnet, je Sitzung mit dem Referenzkurs dieses Tages oder dem letzten davor ({turnover?.wechselkurse.quelle ?? 'EZB-Referenzkurse'}). Kurse
          in Untereinheiten (Pence, Agorot, Cent) werden vorher in die Hauptwährung umgerechnet.
        </li>
        <li>Fehlen Volumen oder Wechselkurs, kommt die Aktie nicht in die zweite Liste; in der ersten kann sie trotzdem stehen.</li>
      </ul>
      <p>
        Hinweise in beiden Listen: ein einzelner Tag erklärt mehr als die Hälfte der Bewegung (Impulstag), Kurssprung ab 15 % mit anschließend kaum Bewegung (Übernahmemuster), Split im Zeitraum, geprüfter
        Kurssprung und auffällige Kursabweichung zwischen Börsenplätzen.
      </p>

      <h2>Abgleich mit einem zweiten Börsenplatz</h2>
      <p>
        Für jede Aktie, die in mindestens einem Zeitraum unter den ersten {venue?.plaetze ?? 10} Plätzen einer der beiden Rendite-Ranglisten steht, misst der Server die Kursrendite zusätzlich an einem zweiten
        Handelsplatz derselben ISIN – bevorzugt Xetra, dann Frankfurt, sonst eine andere unterstützte Börse (keine OTC-Märkte) – und zwar für alle ihre Zeiträume, umgerechnet in die Währung der
        Referenzbörse mit den EZB-Referenzkursen. Verwendet wird der {venueDayRule(venue)}
      </p>
      <p className="formula">Abweichung = (1 + Rendite am zweiten Platz) ÷ (1 + Rendite an der Referenzbörse) − 1</p>
      <p>
        {venueLimitSentence(venue)} Das deutet auf einen Datenfehler,
        eine nicht bereinigte Kapitalmaßnahme oder eine Handelsaussetzung hin. Es ist nur ein Hinweis: Rendite und Rang bleiben die der Referenzbörse. Fehlende Vergleichskurse werden nicht ersetzt; dann steht dort
        „Vergleichskurse fehlen“. Aktien auf späteren Plätzen werden nicht abgeglichen.
      </p>

      <h2>Gleichmäßigkeit (R²)</h2>
      <p>
        Durch die Tagesschlusskurse des Zeitraums wird die beste gerade Linie gelegt (kleinste Quadrate, Zeitachse in Handelsbeobachtungen 0, 1, 2 …). R² ist der Anteil der Kursschwankung, den diese Gerade erklärt:
      </p>
      <p className="formula">R² = 1 − Summe der quadrierten Abstände zur Geraden ÷ Summe der quadrierten Abstände zum Mittelwert</p>
      <p>
        Beispiel: R² = 0,9326 heißt, 93,26 % der Kursbewegung liegen auf einer Geraden – der Kurs ist sehr gleichmäßig gelaufen. R² sagt nichts über die Richtung; auch ein gleichmäßig fallender Kurs hat ein hohes R². Deshalb zählen für die Gleichmäßigkeit nur Aktien mit positiver Rendite und positiver
        Steigung. Ein stetig, aber gekrümmt steigender Kurs (zum Beispiel immer schneller) kann ein niedrigeres R² haben, obwohl er nie gefallen ist.
      </p>
      <h3>Ergänzende Kennzahlen</h3>
      <ul>
        <li>Relative Steigung: Steigung der Geraden je Handelstag in Prozent des Durchschnittskurses.</li>
        <li>Residualrauschen: typische Abweichung der Kurse von der Geraden in Prozent des Durchschnittskurses.</li>
        <li>Größter Rückgang: stärkster Fall von einem Zwischenhoch innerhalb des Zeitraums.</li>
        <li>Volumenabdeckung: Anteil der Tage mit belegtem Handelsumsatz.</li>
        <li>Positive Schlusskursvergleiche: an wie vielen Tagen der Schlusskurs über dem des Vortags lag (von allen Vergleichen im Zeitraum).</li>
      </ul>

      <h2>Wer wird verglichen?</h2>
      <p>Pro Zeitraum gibt es zwei Vergleichsfelder:</p>
      <ul>
        <li>
          <strong>V – Aktien mit veröffentlichter Kursrendite:</strong> eindeutig identifiziert, Schlusskurs am Stichtag und am Start (fehlt der Kurs am Stichtag – Feiertag der Börse,
          nicht geliefert oder im Zwischenstand Börse noch nicht geöffnet –, zählt der letzte Schlusskurs, höchstens eine verpasste Börsensitzung; die Zeiträume dieser Aktie enden dann
          dort), mindestens 2 echte Kurse, {sessionRule} – fehlende Tage werden
          nie aufgefüllt –, an jedem Kurstag ein gemeldetes Handelsvolumen, positives Volumen am ersten und letzten Kurstag, {volumeRule}, kein ungeklärter Kurssprung um mehr als das {jump}-Fache und kein
          gemeldeter Split im Zeitraum (außer nach dokumentierter Prüfung).
        </li>
        <li>
          <strong>U – gleichmäßig gestiegene Aktien:</strong> zusätzlich mindestens {minTrend} echte Tageskurse, positive Rendite, positive Steigung und ein berechenbares R². U ist immer ein Teil von V.
        </li>
      </ul>
      <p>In sehr kurzen Zeiträumen (etwa unter drei Wochen) gibt es weniger als {minTrend} Tageskurse. Dort bleibt die Gleichmäßigkeit leer; die reine Renditeliste funktioniert trotzdem.</p>

      <h2>Elf Gewichtungen</h2>
      <p>Die erste Zahl ist immer der Anteil Gleichmäßigkeit, die zweite der Anteil Kursrendite: 0/100, 10/90, 20/80 … 100/0. Innerhalb des Vergleichsfelds bekommt jede Aktie zwei Perzentile von 0 bis 100:</p>
      <p className="formula">P = 100 × (Durchschnittsrang − 1) ÷ (M − 1)</p>
      <p>
        M ist die Zahl der verglichenen Aktien; der Rang wird aufsteigend vergeben, exakt gleiche Werte erhalten denselben Durchschnittsrang. G ist das Perzentil von R², R das Perzentil der Kursrendite. Roh-Renditen
        werden nie direkt mit R² vermischt. Der Rangscore (0–100) lautet:
      </p>
      <p className="formula">Rangscore = w/100 × G + (1 − w/100) × R</p>
      <p>Beispiel 60/40 mit G = 80 und R = 60: 0,6 × 80 + 0,4 × 60 = 72. Bei 0/100 zählt nur die Rendite, bei 100/0 nur die Gleichmäßigkeit.</p>
      <p>Gibt es nur eine einzige qualifizierte Aktie, erhält sie Rangscore 100 mit dem Hinweis „Einziger qualifizierter Titel – keine relative Konkurrenzbewertung“. Der Rangscore ist keine Prognose, keine Wahrscheinlichkeit und keine erwartete Rendite; daneben stehen immer die tatsächliche Rendite und das tatsächliche R².</p>

      <h3>Nativ oder gleiches Vergleichsfeld</h3>
      <ul>
        <li>
          <strong>Nativ (Standard):</strong> 0/100 vergleicht alle Aktien aus V und lässt auch negative Renditen zu. Alle anderen Gewichtungen vergleichen nur U.
        </li>
        <li>
          <strong>Gleiches Vergleichsfeld:</strong> alle elf Gewichtungen vergleichen dieselben Aktien aus U. Nur so zeigt ein Vergleich zweier Gewichtungen allein die Wirkung der Gewichtung.
        </li>
      </ul>

      <h3>Reihenfolge und Gleichstände</h3>
      <p>Für alle elf Gewichtungen: höherer Rangscore zuerst, dann höhere Kursrendite, zuletzt ISIN – mit ungerundeten Werten (bei 0/100 entspricht der Rangscore der Rendite, bei 100/0 dem R²).</p>
      <p>Exakt gleiche Rangscores werden als Gleichstand gekennzeichnet; Rendite und ISIN legen nur die Anzeigereihenfolge fest.</p>

      <h2>Höchste Rendite 1–90 Tage</h2>
      <p>
        Für jeden der 90 Zeiträume steht die Aktie mit der höchsten Kursrendite aus V. Sind alle Renditen negativ, steht dort der geringste Verlust mit Vorzeichen. Das Gesamtmaximum ist der höchste Wert über alle geprüften Aktie-Zeitraum-Paare – ein rückblickend ausgewählter Bestwert,
        keine erwartete Rendite. Renditen verschiedener Zeiträume werden nie addiert oder auf ein Jahr hochgerechnet.
      </p>

      <h2>Gruppenvergleich A/B</h2>
      <p>
        Zwei Aktiengruppen mit demselben Kursstichtag, denselben Zeitregeln und derselben Renditeformel ({manifest?.versions.groups ?? 'gruppen-v1'}):
      </p>
      <ul>
        <li>
          <strong>Gruppe A – ohne Mindestumsatz:</strong> alle Aktien der TR-Liste mit ausreichender Datenqualität (Vergleichsfelder V und U wie oben).
        </li>
        <li>
          <strong>Gruppe B – höherer Handelsumsatz:</strong> dieselben Aktien, zusätzlich Ø Tagesumsatz mindestens {money(turnover?.schwelle_usd ?? 10_000_000)} über {turnover?.sitzungen ?? 20} abgeschlossene
          Sitzungen (Vergleichsfelder V ∩ L und U ∩ L).
        </li>
      </ul>
      <p>
        Beide Gruppen haben alle elf Gewichtungen, also bis zu 2 × 90 × 11 = 1.980 Ranglisten je Kursstichtag. Rendite und R² werden je Gruppe in Perzentile von 0 bis 100
        umgerechnet – <strong>innerhalb der Gruppe</strong>. Ein Rangscore der Gruppe B ist deshalb nicht mit einem Rangscore der Gruppe A vergleichbar. Für 0/100 und 100/0 ergibt das dieselbe Reihenfolge wie Gruppe A
        ohne die übrigen Aktien; gemischte Gewichtungen können abweichen. Gleichstände wie oben, zuletzt nach ISIN.
      </p>
      <p>
        <strong>Matrix:</strong> je Zeitraum 1–90 (Zeile) und Gewichtung (Spalte) die erstplatzierte Aktie mit Name, ISIN, Rangscore und Kursrendite. Fehlen für die Gleichmäßigkeit die nötigen {minTrend}
        Tageskurse, steht dort „nicht berechenbar“ – die reine Renditeliste erscheint trotzdem. Wiederkehrende Aktien tragen in beiden Gruppen und allen Ansichten dieselbe Farbe und „↻ Anzahl“ ihrer
        Platz-1-Vorkommen (Identität über die ISIN; Aktiengattungen und ADRs haben eigene ISINs). „≡“ kennzeichnet identische Kursfenster: derselbe Bestand aus ISIN und tatsächlichem Startdatum wie in den
        genannten Zeiträumen, also dieselbe Rangliste.
      </p>
      <p>
        <strong>Häufigkeitsranking:</strong> „gewinnt am häufigsten“ sortiert nach der Zahl der Ranglisten mit Platz 1, dann Top 3, Top 10, ISIN; „Meiste Top-10-Nennungen“ nach Top 10, Top 3, Platz 1, ISIN.
        Je Rangliste zählt eine Aktie höchstens einmal; Platz 1 zählt zugleich zu Top 3 und Top 10, die Spalten werden nie addiert. „Zugelassen“ ist die Zahl der Ranglisten der Auswahl, in denen die Aktie
        überhaupt einen Rang hat; der Nenner „berechenbare Kombinationen“ zählt die Ranglisten mit mindestens einer Aktie. Filter: Gruppe A, B oder beide (Treffer getrennt), alle elf Gewichtungen, nur die mit
        Gleichmäßigkeitsanteil oder eine, alle Zeiträume oder eine Spanne. „Identische Kursfenster nur einmal zählen“ fasst Ranglisten derselben Gruppe und Gewichtung mit gleichem ISIN-/Startdatumsbestand
        zusammen; verschiedene Gewichtungen bleiben verschieden.
      </p>

      <h2>Erweiterte Zählung (bisherige Häufigkeitsansicht)</h2>
      <p>
        Eine Zelle ist eine Kombination aus Zeitraum und Gewichtung eines Datenstands (höchstens 90 × 11 = 990). Ein Treffer ist ein Platz unter den ersten K (1, 3 oder 10) einer veröffentlichten Rangliste; jede Aktie zählt je Zelle höchstens einmal. Leere Zellen ohne Rangliste zählen nicht
        mit.
      </p>
      <ul>
        <li>N1, N3, N10: Zahl der Zellen mit Platz 1, Platz 1–3, Platz 1–10.</li>
        <li>E: Zahl der gültigen Ranglisten in der Auswahl. A: Zahl der Zellen, in denen die Aktie überhaupt bewertet wurde.</li>
        <li>Verschiedene Zeiträume: in wie vielen unterschiedlichen Zeiträumen die Aktie unter den ersten K war.</li>
      </ul>
      <p>
        Benachbarte Zeiträume und ähnliche Gewichtungen beruhen auf fast denselben Kursen. Viele Treffer sind deshalb keine unabhängigen Bestätigungen, und Anteile wie N10 ÷ E sind keine Wahrscheinlichkeit für künftige Gewinne. Native und gleiche Vergleichsfelder werden nie zusammengezählt.
      </p>

      <h2>Umschichtungs-Regel</h2>
      <p>
        Eine feste, mechanische Regel zum Ausprobieren ({manifest?.rotation?.version ?? 'rotation-v1'}). Sie hält gedanklich N Aktien zu gleichen Teilen und tauscht sie zu festen Terminen aus. Gerechnet wird mit
        Wochenwerten: je Aktie und Woche der letzte Schlusskurs, die Umsatzsumme und der Schlusskurs der ersten Sitzung.
      </p>
      <ul>
        <li>
          <strong>Auswahl am Prüftag:</strong> Ø Tagesumsatz der letzten {num('turnover_weeks', 4)} Wochen mindestens {money(num('min_turnover_usd', 10_000_000))} (Summe Schlusskurs × Volumen ÷ Sitzungen mit
          Volumen, in US-Dollar mit dem EZB-Referenzkurs), an mindestens {pctText(num('min_positive_share', 0.8))} der Sitzungen Umsatz, Kurse an mindestens {pctText(num('min_coverage', 0.9))} der Sitzungen im
          Trendzeitraum, kein Tagessprung über das {num('max_jump_factor', 3)}-Fache.
        </li>
        <li>
          <strong>Trend:</strong> Kursrendite über 13 Wochen (91 Tage) oder 4 Wochen (28 Tage) in Notierungswährung; höherer Trend zuerst, bei Gleichstand nach ISIN.
        </li>
      </ul>
      <p className="formula">Trend = Schlusskurs am Prüftag ÷ letzter Schlusskurs der Woche vor 13 (bzw. 4) Wochen − 1</p>
      <ul>
        <li>
          <strong>Termine:</strong> Entscheidung nach Börsenschluss am ersten Freitag im Monat (Variante: jeden Freitag), Ausführung zum Schlusskurs der ersten Sitzung danach – so, wie man frühestens handeln kann.
        </li>
        <li>
          <strong>Halten und Tauschen:</strong> Eine gehaltene Aktie bleibt, solange sie unter den ersten {num('keep_rank_factor', 2)} × N Plätzen liegt. Freie Plätze bekommen die bestplatzierten nicht gehaltenen
          Aktien mit je 1/N des Depotwerts. Gehaltene Aktien werden nur angeglichen, wenn ihr Anteil mehr als {Math.round(num('band', 0.05) * 100)} Prozentpunkte von 1/N abweicht. Reicht das Geld nicht für alle
          Käufe, werden sie gleichmäßig gekürzt; übriges Geld bleibt als Bargeld im Regeldepot.
        </li>
        <li>
          <strong>Kosten und Steuern:</strong> je Order {num('fee_eur', 1).toLocaleString('de-DE', { minimumFractionDigits: 2 })} € und {pctText(num('spread', 0.001), 1)} Kursabschlag. Abgeltungsteuer mit
          Solidaritätszuschlag ({pctText(num('tax_rate', 0.26375), 3)}) auf realisierte Gewinne nach Verlustverrechnung und Sparerpauschbetrag ({num('allowance_eur', 1000).toLocaleString('de-DE')} € je
          Kalenderjahr); Verluste werden im selben Jahr erstattet, sonst in den Verlusttopf vorgetragen. Keine Kirchensteuer, keine Quellensteuer, keine Dividenden.
        </li>
        <li>
          <strong>Bewertung:</strong> in Euro zu den Freitagsschlusskursen mit den EZB-Referenzkursen. Vergleichslinie: alle Kandidaten zu gleichen Teilen, an jedem Termin neu aufgeteilt, ohne Kosten.
        </li>
        <li>
          <strong>Rückblick:</strong> bis {num('history_years', 3)} Jahre, mit den Aktien, die heute in der TR-Liste stehen und heute mindestens {money(num('pool_min_turnover_usd', 2_000_000))} am Tag
          umsetzen. Aktien, die es nicht mehr gibt, fehlen – das Ergebnis ist dadurch eher zu gut.
        </li>
        <li>
          <strong>Tagesvorschlag:</strong> dieselbe Regel auf den neuesten Kursstand angewendet (Wochen rückwärts ab dem Kursstichtag), ausgehend vom Regeldepot nach der letzten Umschichtung im Rückblick.
        </li>
      </ul>

      <MethodChange />

      <h2>Daten und Grenzen</h2>
      <ul>
        <li>Das Aktienuniversum stammt aus der öffentlichen Instrumentenliste von Trade Republic (nur Aktienabschnitt). Eine Listung bedeutet nicht, dass eine Aktie im eigenen Konto jederzeit handelbar ist.</li>
        <li>Kurse: {manifest?.provider.prices ?? 'siehe Datenstand'}. {manifest?.provider.license_note ?? ''}</li>
        <li>Es werden ausschließlich Tagesschlusskurse verwendet. Live- oder Intradaykurse sind nicht eingerichtet; eine 1-Tages-Ansicht zeigt nur die zwei belegten Schlusskurse.</li>
        <li>Fehlende Börsensitzungen bleiben im Chart als Lücke sichtbar. Es werden keine Kurse erfunden oder aufgefüllt.</li>
        <li>Diese App ist kein Angebot von Trade Republic und steht in keiner Verbindung zu Trade Republic.</li>
      </ul>
    </article>
  );
}

/** Methodenwechsel: Regeln des Ausgangsmodells (ab 1.7.0), fehlende Börsentage (ab 1.8.0) und der Vergleich
 * mit der Vorversion auf denselben Kursen (Manifest `method_comparison`). */
export function MethodChange() {
  const { manifest, instruments } = useApp();
  const cmp = manifest?.method_comparison;
  const n = (value: number) => value.toLocaleString('de-DE');
  const byStatus = (counts: Record<string, number> | undefined): string => {
    const parts = Object.entries(counts ?? {})
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([code, count]) => `${manifest?.codes.status[code]?.kurz ?? `Status ${code}`}: ${n(count)}`);
    return parts.length ? parts.join('; ') : '–';
  };
  return (
    <>
      <h2>Methodenwechsel und Ausgangsmodell</h2>
      <p>
        Seit Methode 1.7.0 gelten die im Auftrag vom 13.10.2026 beschriebenen Regeln des Ausgangsmodells {cmp?.ausgangsmodell ?? 'TR-90D-11W-two-universes-v1.1'}. Seit Methode 1.8.0 schließt ein einzelner
        fehlender Börsentag beim Kursanbieter einen Zeitraum nicht mehr aus (deine Entscheidung vom 13.10.2026); aufgefüllt wird weiterhin nichts. Seit Methode 1.9.0 wird jede Aktie bewertet: Fehlt
        ihr Schlusskurs am Stichtag (Feiertag der Börse oder nicht geliefert), zählt ihr letzter Schlusskurs – höchstens eine verpasste Börsensitzung, ihre Zeiträume enden dort (dein Wunsch vom
        14.10.2026). Jeder Lauf rechnet dieselben Kurse zusätzlich nach den Regeln der Vorversion und zeigt die Unterschiede.
      </p>
      {cmp ? (
        <>
          <p>
            <strong>
              Vergleich {cmp.vorher} → {cmp.jetzt}
            </strong>{' '}
            auf den Kursen dieses Stands:
          </p>
          <ul>
            {cmp.regeln.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
          <dl className="kv">
            <div className="kv-row">
              <dt>Aktie-Zeitraum-Paare mit Kursrendite</dt>
              <dd>
                {n(cmp.paare.vorher_V)} nach {cmp.vorher}, {n(cmp.paare.jetzt_V)} nach {cmp.jetzt}
              </dd>
            </div>
            <div className="kv-row">
              <dt>davon gleichmäßig gestiegen (U)</dt>
              <dd>
                {n(cmp.paare.vorher_U)} → {n(cmp.paare.jetzt_U)}
              </dd>
            </div>
            <div className="kv-row">
              <dt>Nicht mehr bewertet</dt>
              <dd>
                {n(cmp.paare.nicht_mehr_bewertet)}
                {cmp.paare.grund
                  ? ` (Mehrfachnennung möglich – Volumen fehlt: ${n(cmp.paare.grund.volumen_fehlt)}; kein Umsatz an Start oder Ende: ${n(cmp.paare.grund.randvolumen)}; Split im Zeitraum: ${n(cmp.paare.grund.split_im_fenster)})`
                  : cmp.paare.nicht_mehr_bewertet
                    ? ` – jetzt: ${byStatus(cmp.paare.weggefallen_nach_status)}`
                    : ''}
              </dd>
            </div>
            <div className="kv-row">
              <dt>Neu bewertet</dt>
              <dd>
                {n(cmp.paare.neu_bewertet)}
                {cmp.paare.neu_bewertet && cmp.paare.hinzugekommen_aus_status ? ` – vorher: ${byStatus(cmp.paare.hinzugekommen_aus_status)}` : ''}
              </dd>
            </div>
            <div className="kv-row">
              <dt>Aktien mit mindestens einer Kursrendite</dt>
              <dd>
                {n(cmp.aktien.vorher_mit_rendite)} → {n(cmp.aktien.jetzt_mit_rendite)}
              </dd>
            </div>
            <div className="kv-row">
              <dt>Ranglisten mit anderem Spitzenreiter</dt>
              <dd>
                {n(cmp.ranglisten.spitze_geaendert)} von {n(cmp.ranglisten.verglichen)} verglichenen
              </dd>
            </div>
          </dl>
          {cmp.ranglisten.beispiele.length && instruments ? (
            <ul>
              {cmp.ranglisten.beispiele.map((b) => (
                <li key={`${b.gruppe}-${b.h}-${b.w}`}>
                  Gruppe {b.gruppe}, {b.h} Tage, {b.w}/{100 - b.w}: {b.vorher !== null ? instruments.name[b.vorher] : 'keine Rangliste'} → {b.jetzt !== null ? instruments.name[b.jetzt] : 'keine Rangliste'}
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <p>Dieser Datenstand wurde noch nach älteren Regeln berechnet; der Vergleich erscheint ab Methode 1.7.0.</p>
      )}
      <p>
        Die Reproduktion des historischen Prüffalls (Stichtag 12.10.2026) steht aus, weil dessen Archiv nicht vorliegt. Ob das Ausgangsmodell selbst eine Grenze für fehlende Börsentage kennt, zeigt erst
        dieses Archiv; diese App erlaubt höchstens 20 % fehlende Tage.
      </p>
    </>
  );
}
